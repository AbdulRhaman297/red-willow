#!/usr/bin/env python3
"""Jarvis — Hybrid voice assistant (Groq + Gemini) with local long-term memory (ChromaDB).

- Fast replies: Groq (Llama 3) for short/simple queries
- Smart/long-context: Google Gemini (Gemini 1.5 Flash) for complex or long-history queries
- Long-term memory: ChromaDB (local, DuckDB+Parquet) + sentence-transformers
- Interface: SpeechRecognition (mic) + pyttsx3 (offline TTS)

USAGE
- Set API keys in your environment or in `.env` (requires `python-dotenv`) as described in README.
- Install dependencies (see `requirements.txt`) and run: `python jarvis.py`
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Dict, List

# Voice/Audio
try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    import speech_recognition as sr
except Exception:
    sr = None

# Local vector database
try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
except Exception:
    chromadb = None

# Optional model clients (guarded imports)
try:
    import groq
except Exception:
    groq = None

# Use the current Google GenAI client if available (new package `google-genai`)
try:
    from google import genai
except Exception:
    genai = None

# -------------------------
# Configuration
# -------------------------
DB_DIR = os.getenv("JARVIS_CHROMA_DIR", "./.chroma")
COLLECTION_NAME = os.getenv("JARVIS_COLLECTION", "jarvis_memories")
TOP_K = int(os.getenv("JARVIS_TOP_K", "4"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_SA = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

REQUEST_TIMEOUT = 10

# Runtime options (modifiable via CLI or tests)
NO_AUDIO = False
DRY_RUN = False

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("jarvis")

# -------------------------
# TTS
# -------------------------
_tts = None
if pyttsx3:
    try:
        _tts = pyttsx3.init()
    except Exception:
        _tts = None


def speak(text: str) -> None:
    """Speak text in a background thread (or print as fallback). Respects NO_AUDIO flag."""
    if NO_AUDIO:
        logger.debug("NO_AUDIO set; skipping speak: %s", text)
        return

    def _do():
        if _tts:
            try:
                _tts.say(text)
                _tts.runAndWait()
            except Exception:
                logger.exception("TTS failed, printing instead")
                print("Jarvis:", text)
        else:
            print("Jarvis:", text)

    threading.Thread(target=_do, daemon=True).start()


# -------------------------
# Speech input
# -------------------------
_recognizer = sr.Recognizer() if sr else None


def listen(timeout: float = 6.0, phrase_time_limit: float = 20.0) -> str:
    """Listen for a single utterance and return text.

    Falls back to typed input if microphone or recognition fails.
    """
    if _recognizer is None:
        return input("Type command: ").strip()

    try:
        with sr.Microphone() as src:
            print("Listening...")
            audio = _recognizer.listen(
                src, timeout=timeout, phrase_time_limit=phrase_time_limit
            )
        text = _recognizer.recognize_google(audio)
        print("You said:", text)
        return text.strip()
    except sr.WaitTimeoutError:
        print("Listening timed out. Try again or type a command.")
        return ""
    except sr.UnknownValueError:
        print("Could not understand audio.")
        return ""
    except Exception as e:
        logger.warning("SR/microphone error: %s", e)
        # fallback to typed input; in tests this avoids reading stdin when capture is on
        try:
            return input("Type command: ").strip()
        except Exception:
            return ""


# -------------------------
# Device verification & Wake-word listener
# -------------------------

# pocketsphinx (offline) wake-word support (optional)
try:
    from pocketsphinx import LiveSpeech  # type: ignore

    _POCKETSPHINX_AVAILABLE = True
except Exception:
    _POCKETSPHINX_AVAILABLE = False

WAKE_WORD = os.getenv("JARVIS_WAKE_WORD", "jarvis").lower()


def get_available_mics() -> List[Dict]:
    """Return a list of available input audio devices as dicts: {'index': i, 'name': name}.

    If PyAudio is unavailable, returns an empty list.
    """
    out: List[Dict] = []
    try:
        import pyaudio

        p = pyaudio.PyAudio()
        count = p.get_device_count()
        for i in range(count):
            try:
                info = p.get_device_info_by_index(i)
                # check if device has input channels
                if info.get("maxInputChannels", 0) > 0:
                    out.append({"index": i, "name": info.get("name")})
            except Exception:
                continue
        p.terminate()
    except Exception:
        logger.debug("PyAudio not available or failed to enumerate devices")
    return out


def check_microphone() -> bool:
    """Check for at least one audio input device (PyAudio) or the configured JARVIS_MIC_NAME.

    Returns True if a usable device is available; otherwise False.
    """
    mics = get_available_mics()
    if not mics:
        logger.debug("No audio input devices detected via PyAudio")
        return False
    # If a specific device name is configured, ensure it exists
    cfg = os.getenv("JARVIS_MIC_NAME")
    if cfg:
        for d in mics:
            if cfg.lower() in (d["name"] or "").lower():
                logger.debug("Configured Jarvis mic '%s' found as device: %s", cfg, d)
                return True
        logger.warning(
            "Configured Jarvis mic '%s' not found among devices: %s",
            cfg,
            [d["name"] for d in mics],
        )
        return False
    return True


def verify_and_select_mic() -> Optional[int]:
    """Verify configured mic exists and return its device index, or pick the first available.

    Returns device index if found; None otherwise.
    """
    mics = get_available_mics()
    if not mics:
        logger.warning("No microphones available.")
        return None
    cfg = os.getenv("JARVIS_MIC_NAME")
    if cfg:
        for d in mics:
            if cfg.lower() in (d["name"] or "").lower():
                logger.info(
                    "Using configured microphone: %s (index %s)", d["name"], d["index"]
                )
                return d["index"]
        logger.warning(
            "Configured microphone '%s' not found; defaulting to first available device: %s",
            cfg,
            mics[0]["name"],
        )
    # default to first available
    logger.info(
        "Selecting default microphone: %s (index %s)", mics[0]["name"], mics[0]["index"]
    )
    return mics[0]["index"]


def check_camera() -> bool:
    """Check if a webcam can be opened via OpenCV."""
    try:
        import cv2

        cap = cv2.VideoCapture(
            0, cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        )
        ok = cap is not None and cap.isOpened()
        try:
            cap.release()
        except Exception:
            pass
        return bool(ok)
    except Exception:
        logger.debug("OpenCV not available or camera not found")
        return False


def _wakeword_loop(stop_event, callback_on_wake):
    """Continuously listen for the configured wake word, then invoke callback_on_wake()."""
    logger.info("Wake-word listener started (wake word: '%s')", WAKE_WORD)
    if _POCKETSPHINX_AVAILABLE:
        try:
            speech = LiveSpeech(lm=False, keyphrase=WAKE_WORD, kws_threshold=1e-20)
            for phrase in speech:
                if stop_event.is_set():
                    break
                try:
                    text = str(phrase).lower()
                    if WAKE_WORD in text:
                        logger.info("Wake word detected (pocketsphinx): %s", text)
                        callback_on_wake()
                except Exception:
                    continue
        except Exception:
            logger.exception("pocketsphinx wake loop failed; falling back to polling")

    # Fallback: periodic short recognition using the existing `listen()` function
    while not stop_event.is_set():
        try:
            # Short listen: quick timeout so this loop is responsive
            text = listen(timeout=2.0, phrase_time_limit=3.0)
            if text and WAKE_WORD in text.lower():
                logger.info("Wake word detected (fallback) in: %s", text)
                callback_on_wake()
        except Exception:
            logger.debug("Wake-word fallback listen error", exc_info=True)
        finally:
            # Small sleep to avoid busy loop
            time.sleep(0.3)


def start_wakeword_background(callback_on_wake) -> "threading.Event":
    """Start the wake-word listener in a background thread. Returns a stop_event to stop it."""
    stop_event = threading.Event()
    t = threading.Thread(
        target=_wakeword_loop, args=(stop_event, callback_on_wake), daemon=True
    )
    t.start()
    return stop_event


# -------------------------
# Chroma local memory
# -------------------------

_chroma_client = None
_memory_col = None


def init_chroma(db_dir: str | None = None):
    """Initialize or reinitialize Chroma client with optional `db_dir`. Returns (client, collection) or (None, None)."""
    if not chromadb:
        logger.info("ChromaDB not installed; skipping memory initialization")
        return None, None
    _db = db_dir or DB_DIR
    try:
        client = chromadb.Client(
            Settings(chroma_db_impl="duckdb+parquet", persist_directory=_db)
        )
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        col = client.get_or_create_collection(
            name=COLLECTION_NAME, embedding_function=embedding_fn
        )
        logger.debug("Initialized ChromaDB at %s", _db)
        return client, col
    except Exception:
        logger.exception("Failed to init ChromaDB locally; memory disabled.")
        return None, None


# initialize once with DB_DIR
_chroma_client, _memory_col = init_chroma(DB_DIR)


def add_memory(text: str, meta: Dict | None = None) -> None:
    if _memory_col is None:
        return
    if meta is None:
        meta = {}
    _id = f"mem_{int(time.time()*1000)}"
    try:
        _memory_col.add(ids=[_id], documents=[text], metadatas=[meta])
    except Exception:
        logger.exception("Failed to add memory")


def query_memories(query_text: str, k: int = TOP_K) -> List[Dict]:
    if _memory_col is None:
        return []
    try:
        res = _memory_col.query(query_texts=[query_text], n_results=k)
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        return [{"text": d, "meta": m} for d, m in zip(docs, metas)]
    except Exception:
        logger.exception("Memory query failed")
        return []


# -------------------------
# API selection heuristic
# -------------------------

SHORT_HISTORY: List[str] = []


def choose_api(user_text: str, history: List[str]) -> str:
    u = user_text.lower()
    if any(
        k in u
        for k in [
            "remember",
            "remind",
            "what did i",
            "previously",
            "earlier",
            "past",
            "recall",
        ]
    ):
        return "gemini"
    if (
        len(user_text) > 200
        or len(history) > 8
        or any(
            w in u
            for w in [
                "analyze",
                "explain",
                "summarize",
                "plan",
                "optimize",
                "compare",
                "why",
            ]
        )
    ):
        return "gemini"
    return "groq"


# -------------------------
# Groq call (fast short replies)
# -------------------------


def call_groq(prompt: str) -> str:
    if DRY_RUN:
        return "[dry-run] Groq simulated response"
    if not GROQ_API_KEY:
        return "Groq API key not set (set GROQ_API_KEY in your environment or .env)."
    if groq is None:
        return "`groq` package not installed."

    try:
        client = groq.Client(api_key=GROQ_API_KEY)
        resp = client.completions.create(model="llama-3", prompt=prompt, max_tokens=512)
        # adjust as needed to match SDK shape
        if hasattr(resp, "choices"):
            return getattr(resp.choices[0], "text", str(resp))
        return str(resp)
    except Exception as e:
        logger.exception("Groq API error")
        return f"[Groq error] {e}"


# -------------------------
# Gemini call (complex/long context)
# -------------------------


def call_gemini(prompt: str) -> str:
    if DRY_RUN:
        return "[dry-run] Gemini simulated response"
    if not (GOOGLE_API_KEY or GOOGLE_SA):
        return "Google API credentials not found. Set GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS."
    if genai is None:
        return "`google-genai` package not installed."
    try:
        # `google.genai` usage: configure then call ChatCompletion.create
        if GOOGLE_API_KEY:
            try:
                genai.configure(api_key=GOOGLE_API_KEY)
            except Exception:
                # some genai versions may use different config flow; ignore if it fails
                logger.debug("genai.configure failed (ignored)")
        # prefer ChatCompletion if available
        if hasattr(genai, "ChatCompletion"):
            resp = genai.ChatCompletion.create(
                model="gemini-1.5",
                messages=[{"role": "user", "content": prompt}],
                max_output_tokens=1024,
            )
            choice = resp.choices[0]
            msg = getattr(choice, "message", None)
            if msg:
                return msg.get("content", str(resp))
            return str(resp)
        # fallback to older interface if present
        if hasattr(genai, "chat") and hasattr(genai.chat, "completions"):
            resp = genai.chat.completions.create(
                model="gemini-1.5",
                messages=[{"role": "user", "content": prompt}],
                max_output_tokens=1024,
            )
            choice = resp.choices[0]
            msg = getattr(choice, "message", None)
            if msg:
                return msg.get("content", str(resp))
            return str(resp)
        return "Gemini client available but no known call pattern found."
    except Exception as e:
        logger.exception("Gemini API error")
        return f"[Gemini error] {e}"


# -------------------------
# Conversation flow
# -------------------------


def build_prompt(user_text: str, memories: List[Dict], history: List[str]) -> str:
    mem_text = (
        "\n".join(f"- {m['text']}" for m in memories)
        if memories
        else "No relevant memories."
    )
    hist_text = "\n".join(history[-6:]) if history else ""
    return f"Context - Relevant memories:\n{mem_text}\n\nConversation history:\n{hist_text}\n\nUser: {user_text}\nJarvis:"


def handle_input(user_text: str) -> str:
    if not user_text:
        return ""
    SHORT_HISTORY.append(f"User: {user_text}")
    memories = query_memories(user_text, k=TOP_K)
    api = choose_api(user_text, SHORT_HISTORY)
    prompt = build_prompt(user_text, memories, SHORT_HISTORY)
    resp = call_groq(prompt) if api == "groq" else call_gemini(prompt)
    SHORT_HISTORY.append(f"Jarvis: {resp}")
    add_memory(user_text, meta={"type": "user"})
    add_memory(resp, meta={"type": "assistant"})
    try:
        if _chroma_client:
            _chroma_client.persist()
    except Exception:
        logger.exception("Failed to persist ChromaDB")
    return resp


# -------------------------
# Main loop
# -------------------------


def set_options(
    no_audio: bool | None = None,
    dry_run: bool | None = None,
    db_dir: str | None = None,
    log_file: str | None = None,
    debug: bool | None = None,
):
    """Configure runtime flags and (re)initialize components as needed."""
    global NO_AUDIO, DRY_RUN, _chroma_client, _memory_col, DB_DIR
    if no_audio is not None:
        NO_AUDIO = no_audio
    if dry_run is not None:
        DRY_RUN = dry_run
    if db_dir:
        DB_DIR = db_dir
        _chroma_client, _memory_col = init_chroma(DB_DIR)
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
    if debug:
        logger.setLevel(logging.DEBUG)


def _on_wake_detected_interactive():
    """Callback invoked when wake word is detected: listens for a command and handles it."""
    try:
        speak("Yes?")
        cmd = listen(timeout=8.0, phrase_time_limit=20.0)
        if not cmd:
            speak("I didn't catch that.")
            return
        resp = handle_input(cmd)
        speak(resp)
    except Exception:
        logger.exception("Error handling command after wake word")


def main():
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--no-audio", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--db-dir")
    p.add_argument("--debug", action="store_true")
    p.add_argument(
        "--background",
        action="store_true",
        help="Run in background and listen for wake word",
    )
    p.add_argument(
        "--wake-word",
        action="store_true",
        help="Enable wake-word activation (background mode)",
    )

    args = p.parse_args()
    set_options(
        no_audio=args.no_audio,
        dry_run=args.dry_run,
        db_dir=args.db_dir,
        debug=args.debug,
    )

    # Device verification on Windows
    if platform.system() == "Windows":
        mic_ok = check_microphone()
        cam_ok = check_camera()
        if not mic_ok:
            logger.warning(
                "Microphone not detected. Check Windows Settings > Privacy & security > Microphone."
            )
        if not cam_ok:
            logger.warning(
                "Camera not detected. Check Windows Settings > Privacy & security > Camera."
            )

    greet = f"{time_greeting()} I am Jarvis. How can I assist?"
    speak(greet)
    print(greet)

    # Background/wake-word mode
    if args.background or args.wake_word:
        stop_event = start_wakeword_background(_on_wake_detected_interactive)
        speak("Running in background. Say the wake word to interact.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_event.set()
            speak("Shutting down background listener.")
            sys.exit(0)

    # Interactive loop (default)
    try:
        while True:
            txt = listen()
            if not txt:
                continue
            if txt.lower().strip() in ("exit", "quit", "goodbye"):
                speak("Goodbye, Sir.")
                break
            out = handle_input(txt)
            speak(out)
    except KeyboardInterrupt:
        speak("Shutting down.")
        sys.exit(0)


if __name__ == "__main__":
    main()


def main_loop() -> None:
    """Run the interactive main loop; exposed for tests and programmatic use."""
    speak("Jarvis online. Say 'exit' to quit.")
    while True:
        try:
            txt = listen()
            if not txt:
                continue
            if txt.lower().strip() in ("exit", "quit", "goodbye"):
                speak("Goodbye.")
                break
            out = handle_input(txt)
            speak(out)
        except KeyboardInterrupt:
            speak("Shutting down.")
            break


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Jarvis hybrid assistant")
    parser.add_argument("--no-audio", action="store_true", help="Disable audio output")
    parser.add_argument(
        "--dry-run", action="store_true", help="Simulate API calls without network"
    )
    parser.add_argument("--db-dir", help="Path for local ChromaDB storage")
    parser.add_argument("--log-file", help="Write logs to file")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()
    set_options(
        no_audio=args.no_audio,
        dry_run=args.dry_run,
        db_dir=args.db_dir,
        log_file=args.log_file,
        debug=args.debug,
    )

    logger.info("Jarvis starting (dry-run=%s, no-audio=%s)", DRY_RUN, NO_AUDIO)
    speak("Jarvis online. Say 'exit' to quit.")
    try:
        main_loop()
    except KeyboardInterrupt:
        speak("Shutting down.")


if __name__ == "__main__":
    main()
