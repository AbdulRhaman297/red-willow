#!/usr/bin/env python3
"""Jarvis GUI helper (Windows-focused) to control background Jarvis service.

Features:
- Status indicators for microphone and camera
- Secure fields to enter GROQ and Google keys (masked)
- Scrollable log area showing real-time Jarvis output
- Start/Stop background Jarvis process
- Minimize to System Tray (uses pystray + Pillow)

Usage: python tools/jarvis_gui.py

Note: This GUI is designed for Windows, but will run on other OSes with limited features.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = None

# import the project's helpers
import jarvis

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"
JARVIS_SCRIPT = REPO_ROOT / "jarvis.py"
PY = sys.executable

LOG_QUEUE: "queue.Queue[str]" = queue.Queue()
PROCESS: subprocess.Popen | None = None
PROCESS_LOCK = threading.Lock()
STOP_READER = threading.Event()

# -------------------------
# Utilities
# -------------------------


def append_log(text: str) -> None:
    LOG_QUEUE.put(text)


def set_env_key(key: str, value: str) -> None:
    """Set or replace a key=value in .env file (create if missing)."""
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = ENV_FILE.read_text() if ENV_FILE.exists() else ""
    lines = text.splitlines()
    out = []
    replaced = False
    for line in lines:
        if line.startswith(key + "="):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(out) + "\n")


# -------------------------
# Process management
# -------------------------


def start_jarvis_process() -> None:
    global PROCESS, STOP_READER
    with PROCESS_LOCK:
        if PROCESS is not None and PROCESS.poll() is None:
            append_log("Jarvis already running.")
            return
        if not JARVIS_SCRIPT.exists():
            append_log("jarvis.py not found in repository root.")
            return
        cmd = [PY, "-u", str(JARVIS_SCRIPT), "--background", "--wake-word"]
        append_log(f"Starting Jarvis: {cmd}")
        STOP_READER.clear()
        PROCESS = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
        )
        threading.Thread(
            target=_reader_thread, args=(PROCESS.stdout,), daemon=True
        ).start()


def stop_jarvis_process() -> None:
    global PROCESS, STOP_READER
    with PROCESS_LOCK:
        if PROCESS is None or PROCESS.poll() is not None:
            append_log("Jarvis is not running.")
            PROCESS = None
            return
        append_log("Stopping Jarvis process...")
        try:
            PROCESS.terminate()
            PROCESS.wait(timeout=5)
            append_log("Jarvis stopped.")
        except Exception:
            try:
                PROCESS.kill()
            except Exception:
                pass
        finally:
            STOP_READER.set()
            PROCESS = None


def _reader_thread(pipe) -> None:
    try:
        for line in iter(pipe.readline, ""):
            if not line:
                break
            append_log(line.rstrip("\n"))
    except Exception:
        append_log("Reader thread encountered an error.")
    finally:
        STOP_READER.set()


# -------------------------
# Tray icon
# -------------------------


def _create_image() -> Image.Image:
    # simple square icon
    img = Image.new("RGB", (64, 64), color=(30, 30, 30))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 56, 56), fill=(70, 130, 180))
    return img


class JarvisGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Jarvis Control")
        root.geometry("700x500")
        self._build()
        self._start_log_updater()
        self.tray_icon = None

    def _build(self):
        pad = 8
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=pad, pady=pad)

        # Status indicators
        self.mic_status = ttk.Label(top, text="Mic: Unknown", foreground="orange")
        self.cam_status = ttk.Label(top, text="Cam: Unknown", foreground="orange")
        self.mic_status.pack(side=tk.LEFT, padx=6)
        self.cam_status.pack(side=tk.LEFT, padx=6)

        check_btn = ttk.Button(top, text="Check Devices", command=self.check_devices)
        check_btn.pack(side=tk.LEFT, padx=6)

        # Keys frame
        keys_frame = ttk.Labelframe(self.root, text="API Keys (stored in .env)")
        keys_frame.pack(fill=tk.X, padx=pad, pady=(0, pad))

        ttk.Label(keys_frame, text="GROQ_API_KEY:").grid(
            row=0, column=0, sticky=tk.W, padx=4, pady=4
        )
        self.groq_var = tk.StringVar()
        self.groq_entry = ttk.Entry(keys_frame, textvariable=self.groq_var, show="*")
        self.groq_entry.grid(row=0, column=1, sticky=tk.EW, padx=4, pady=4)

        ttk.Label(keys_frame, text="GOOGLE_API_KEY:").grid(
            row=1, column=0, sticky=tk.W, padx=4, pady=4
        )
        self.google_var = tk.StringVar()
        self.google_entry = ttk.Entry(
            keys_frame, textvariable=self.google_var, show="*"
        )
        self.google_entry.grid(row=1, column=1, sticky=tk.EW, padx=4, pady=4)

        keys_frame.columnconfigure(1, weight=1)

        keys_btn = ttk.Button(keys_frame, text="Save Keys", command=self.save_keys)
        keys_btn.grid(row=0, column=2, rowspan=2, padx=6)

        # Controls
        ctrl = ttk.Frame(self.root)
        ctrl.pack(fill=tk.X, padx=pad, pady=(0, pad))

        self.start_btn = ttk.Button(
            ctrl, text="Start Jarvis", command=start_jarvis_process
        )
        self.stop_btn = ttk.Button(
            ctrl, text="Stop Jarvis", command=stop_jarvis_process
        )
        self.tray_btn = ttk.Button(
            ctrl, text="Minimize to Tray", command=self.minimize_to_tray
        )

        self.start_btn.pack(side=tk.LEFT, padx=6)
        self.stop_btn.pack(side=tk.LEFT, padx=6)
        self.tray_btn.pack(side=tk.LEFT, padx=6)

        # Log area
        log_frame = ttk.Labelframe(self.root, text="Jarvis Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=pad, pady=(0, pad))

        self.log_text = ScrolledText(log_frame, state=tk.DISABLED, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Fill initial statuses
        self.check_devices()

    def check_devices(self):
        mic = jarvis.check_microphone()
        cam = jarvis.check_camera()
        self._set_status(self.mic_status, "Mic", mic)
        self._set_status(self.cam_status, "Cam", cam)

    def _set_status(self, label: ttk.Label, name: str, ok: bool):
        if ok:
            label.config(text=f"{name}: OK", foreground="green")
        else:
            label.config(text=f"{name}: Missing", foreground="red")

    def save_keys(self):
        g = self.groq_var.get().strip()
        gg = self.google_var.get().strip()
        if g:
            set_env_key("GROQ_API_KEY", g)
            append_log("Saved GROQ_API_KEY to .env")
        if gg:
            set_env_key("GOOGLE_API_KEY", gg)
            append_log("Saved GOOGLE_API_KEY to .env")
        messagebox.showinfo("Saved", "Keys saved to .env")

    def append_log(self, text: str):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _start_log_updater(self):
        def poll():
            try:
                while True:
                    try:
                        s = LOG_QUEUE.get_nowait()
                    except queue.Empty:
                        break
                    self.append_log(s)
            finally:
                self.root.after(200, poll)

        self.root.after(200, poll)

    def minimize_to_tray(self):
        if pystray is None:
            messagebox.showwarning(
                "Tray not available",
                "pystray or pillow not installed; cannot minimize to tray.",
            )
            return
        # hide window and create tray icon
        self.root.withdraw()
        image = _create_image()

        def on_show(icon, item):
            self.root.after(0, self.root.deiconify)
            icon.stop()

        def on_quit(icon, item):
            stop_jarvis_process()
            icon.stop()
            self.root.after(0, self.root.quit)

        menu = pystray.Menu(
            pystray.MenuItem("Show", on_show), pystray.MenuItem("Quit", on_quit)
        )
        icon = pystray.Icon("jarvis", image, "Jarvis", menu)
        self.tray_icon = icon
        threading.Thread(target=icon.run, daemon=True).start()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def on_close(self):
        # stop background process if running
        stop_jarvis_process()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = JarvisGUI(root)
    app.run()


if __name__ == "__main__":
    main()
