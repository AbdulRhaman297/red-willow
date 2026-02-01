#!/usr/bin/env python3
"""Jarvis-like assistant — safer defaults and better error handling.

Improvements:
- Load API keys from environment (.env supported if python-dotenv is installed)
- Non-blocking TTS (runs in a background thread)
- Fallback to text input if microphone or SpeechRecognition isn't available
- Request timeouts and status checks
- Safer input parsing for IPs, cities, and wiki topics
"""

import json
import logging
import os
import re
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from urllib.parse import quote_plus

# Optional third-party imports; handle missing modules gracefully
try:
    import requests
except ImportError:
    print("Missing dependency: requests. Install with `pip install requests`")
    raise

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    import speech_recognition as sr
except Exception:
    sr = None

# Try to import dotenv loader but do NOT automatically call it on import.
# Auto-loading .env at import time can interfere with test expectations that rely
# on program environment variables being controlled by the test harness.
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

# ==========================
# CONFIGURATION
# ==========================
SHODAN_API_KEY = os.getenv("SHODAN_API_KEY")
IPINFO_TOKEN = os.getenv("IPINFO_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

REQUEST_TIMEOUT = 10  # seconds for external API calls

# ==========================
# LOGGING
# ==========================
LOG_FILE = os.getenv("LOG_FILE")  # optional file path to write logs
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

# create module logger
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# attach handler(s)
if LOG_FILE:
    fh = RotatingFileHandler(LOG_FILE, maxBytes=10_000_00, backupCount=3)
    fh.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(fh)
else:
    sh = logging.StreamHandler()
    sh.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    sh.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(sh)

# also configure root basic settings for third-party libs (optional)
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format=LOG_FORMAT)

# ==========================
# LOG CONTROLS
# ==========================


def set_log_level(level_name: str):
    """Set the module logger level and update all handlers."""
    lvl = getattr(logging, level_name.upper(), None)
    if lvl is None:
        raise ValueError(f"Unknown log level: {level_name}")
    logger.setLevel(lvl)
    for h in logger.handlers:
        h.setLevel(lvl)


def set_log_file(path: str):
    """Set or replace the file handler for logging at `path`."""
    # remove existing RotatingFileHandler if present
    for h in list(logger.handlers):
        if isinstance(h, RotatingFileHandler):
            logger.removeHandler(h)

    fh = RotatingFileHandler(path, maxBytes=10_000_00, backupCount=3)
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    fh.setLevel(logger.level)
    logger.addHandler(fh)


def enable_debug():
    """Convenience to enable DEBUG logging."""
    set_log_level("DEBUG")


# ==========================
# TTS (Text-to-Speech)
# ==========================
engine = None
if pyttsx3:
    try:
        engine = pyttsx3.init()
    except Exception:
        engine = None


def speak(text: str):
    """Speak text in a background thread; fallback to print if TTS not available."""

    def _speak():
        if engine:
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                logger.exception("TTS engine error; falling back to print")
                print(text)
        else:
            print(text)

    t = threading.Thread(target=_speak, daemon=True)
    t.start()


# ==========================
# LISTEN (Speech Recognition)
# ==========================


def listen() -> str:
    """Listen for a voice command. If microphone or SR isn't available, fall back to typed input."""
    if sr is None:
        # SpeechRecognition not installed or failed to import
        return input("Type command: ").strip().lower()

    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("🎤 Listening... (press Ctrl+C to cancel)")
            # small timeout to avoid blocking forever
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
    except sr.WaitTimeoutError:
        print("⏱️ Listening timed out; try again or type a command.")
        return ""
    except Exception as e:
        logger.warning("Microphone not available or error initializing: %s", e)
        # fallback to typed input
        return input("Type command: ").strip().lower()

    try:
        command = recognizer.recognize_google(audio)
        print(f"🗣️ You said: {command}")
        return command.lower()
    except sr.UnknownValueError:
        print("❌ Could not understand audio.")
        return ""
    except sr.RequestError as e:
        logger.warning("Speech recognition service error: %s", e)
        return input("Type command: ").strip().lower()


# ==========================
# HELPERS
# ==========================

IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def _extract_ip(text: str):
    m = IP_RE.search(text)
    return m.group(0) if m else None


# ==========================
# API MODULES
# ==========================


def shodan_lookup(ip: str) -> str:
    if not SHODAN_API_KEY:
        return "Shodan API key not set. Export SHODAN_API_KEY or add to .env"

    if not _extract_ip(ip):
        return "No valid IPv4 address found in input."

    base = "https://api.shodan.io/shodan/host"
    url = f"{base}/{ip}?key={SHODAN_API_KEY}"
    try:
        res = requests.get(url, timeout=REQUEST_TIMEOUT)
        if res.status_code != 200:
            return f"Shodan API error: {res.status_code} - {res.text}"
        data = res.json()
        if "error" in data:
            return f"Shodan error: {data['error']}"
        info = (
            f"IP: {data.get('ip_str')}\n"
            f"Organization: {data.get('org')}\n"
            f"Open Ports: {data.get('ports')}"
        )
        return info
    except requests.RequestException as e:
        return f"Network error contacting Shodan: {e}"
    except ValueError:
        return "Unexpected response from Shodan (invalid JSON)"


def ipinfo_lookup(ip: str) -> str:
    if not _extract_ip(ip):
        return "No valid IPv4 address found in input."

    if IPINFO_TOKEN:
        url = f"https://ipinfo.io/{ip}?token={IPINFO_TOKEN}"
    else:
        url = f"https://ipinfo.io/{ip}"
    try:
        res = requests.get(url, timeout=REQUEST_TIMEOUT)
        if res.status_code != 200:
            return f"ipinfo error: {res.status_code} - {res.text}"
        data = res.json()
        info = (
            f"IP: {data.get('ip')}\n"
            f"City: {data.get('city')}\n"
            f"Region: {data.get('region')}\n"
            f"Country: {data.get('country')}\n"
            f"Org: {data.get('org')}"
        )
        return info
    except requests.RequestException as e:
        return f"Network error contacting ipinfo: {e}"


def weather_lookup(city: str) -> str:
    city = city.strip()
    if not city:
        return "Please specify a city for weather lookup."
    if not OPENWEATHER_API_KEY:
        return "OpenWeather API key not set. Export OPENWEATHER_API_KEY or add to .env"

    q = quote_plus(city)
    url = f"https://api.openweathermap.org/data/2.5/weather?q={q}&appid={OPENWEATHER_API_KEY}&units=metric"
    try:
        res = requests.get(url, timeout=REQUEST_TIMEOUT)
        data = res.json()
        if res.status_code != 200:
            return f"Weather error: {data.get('message', res.text)}"
        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        return f"Weather in {city}: {desc}, {temp}°C"
    except requests.RequestException as e:
        return f"Network error contacting OpenWeather: {e}"
    except (KeyError, ValueError):
        return "Unexpected response from weather service."


def wiki_lookup(query: str) -> str:
    query = query.strip()
    if not query:
        return "Please specify a topic to search on Wikipedia."
    q = quote_plus(query)
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{q}"
    try:
        res = requests.get(url, timeout=REQUEST_TIMEOUT)
        if res.status_code != 200:
            return f"Wikipedia error: {res.status_code}"
        data = res.json()
        return data.get("extract", "No summary found.")
    except requests.RequestException as e:
        return f"Network error contacting Wikipedia: {e}"
    except ValueError:
        return "Unexpected response from Wikipedia (invalid JSON)"


# ==========================
# COMMAND PROCESSOR
# ==========================


def process_command(command: str):
    """Process a command, speak/print the result, and return the result string.

    Returns:
        str: The result text (or 'exit' for exit commands).
    """
    command = command.lower().strip()
    if not command:
        return ""

    logger.info("Processing command: %s", command)

    if "shodan" in command:
        ip = _extract_ip(command)
        if not ip:
            res = "Please provide an IPv4 address for Shodan lookup."
            speak(res)
            return res
        result = shodan_lookup(ip)
        print(result)
        speak(result)
        return result

    if "ipinfo" in command or "ip info" in command:
        ip = _extract_ip(command)
        if not ip:
            res = "Please provide an IPv4 address for IP info lookup."
            speak(res)
            return res
        result = ipinfo_lookup(ip)
        print(result)
        speak(result)
        return result

    m = re.search(r"weather(?: in)?\s+(.+)", command)
    if m:
        city = m.group(1).strip()
        result = weather_lookup(city)
        print(result)
        speak(result)
        return result

    m = re.search(r"(?:wikipedia|who is|who's)\s+(.+)", command)
    if m:
        topic = m.group(1).strip()
        result = wiki_lookup(topic)
        print(result)
        speak(result)
        return result

    if "exit" in command or "quit" in command:
        speak("Goodbye.")
        sys.exit(0)
        return "exit"

    res = "Command not recognized. Try: shodan <ip>, ipinfo <ip>, weather <city>, wikipedia <topic>"
    speak(res)
    return res


def run_single_command(command: str, no_audio: bool = False) -> str:
    """Run a single command and return the result. Optionally disable audio output."""
    if no_audio:
        # temporarily disable speak by replacing with a no-op
        orig_speak = globals().get("speak")
        try:
            globals()["speak"] = lambda text: None
            return process_command(command)
        finally:
            globals()["speak"] = orig_speak
    return process_command(command)


# ==========================
# MAIN LOOP
# ==========================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Jarvis-like assistant")
    parser.add_argument(
        "--command", "-c", help="Run a single command and exit", type=str
    )
    parser.add_argument(
        "--no-audio", action="store_true", help="Disable audio output (speak)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--log-file", help="Path to write logs (overrides LOG_FILE env var)"
    )
    args = parser.parse_args()

    if args.debug:
        enable_debug()

    if args.log_file:
        set_log_file(args.log_file)

    if args.command:
        res = run_single_command(args.command, no_audio=args.no_audio)
        if res:
            print(res)
        return

    speak("Jarvis online. How can I assist?")
    try:
        while True:
            command = listen()
            if command:
                process_command(command)
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Shutting down (KeyboardInterrupt)")
        speak("Goodbye.")
        sys.exit(0)


if __name__ == "__main__":
    # Load .env at runtime when running the script directly, but avoid doing
    # this automatically during import (helps tests that manipulate env vars).
    if load_dotenv:
        try:
            load_dotenv()
        except Exception:
            # Some dotenv versions may assert in weird contexts; ignore safely
            pass
    main()
