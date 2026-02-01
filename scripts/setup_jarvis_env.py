#!/usr/bin/env python3
"""Cross-platform interactive helper to set Jarvis environment keys.
Writes to `.env` in repo root (creates if missing) and ensures keys are present.

Usage: python scripts/setup_jarvis_env.py
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"

KEYS = [
    ("SHODAN_API_KEY", "Shodan API key (optional)"),
    ("IPINFO_TOKEN", "ipinfo token (optional)"),
    ("OPENWEATHER_API_KEY", "OpenWeather API key (optional)"),
    ("GROQ_API_KEY", "Groq API key (required for Groq)"),
    ("GOOGLE_API_KEY", "Google API key (optional, or use service account)"),
    (
        "GOOGLE_APPLICATION_CREDENTIALS",
        "Path to Google service account JSON (optional)",
    ),
]


def prompt_secret(prompt: str) -> str:
    val = getpass.getpass(prompt + ": ")
    return val.strip()


def set_key(key: str, value: str, file_path: Path) -> None:
    # safely set or replace key in file
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.touch(exist_ok=True)
    text = file_path.read_text()
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
    file_path.write_text("\n".join(out) + "\n")


def main():
    print(
        f"This will interactively update {ENV_FILE} with Jarvis keys (press Enter to skip optional)."
    )
    for key, desc in KEYS:
        if key == "GOOGLE_APPLICATION_CREDENTIALS":
            val = input(f"{desc} (path) [optional]: ").strip()
        else:
            val = prompt_secret(desc)
        if val:
            set_key(key, val, ENV_FILE)
    # ensure .env is in .gitignore
    gitignore = REPO_ROOT / ".gitignore"
    if gitignore.exists():
        gi = gitignore.read_text()
        if ".env" not in gi:
            gitignore.write_text(gi + "\n.env\n")
            print("Added .env to .gitignore")
    print(
        "Done. To load now, run: set -a && source .env && set +a (or relaunch your shell)"
    )


if __name__ == "__main__":
    main()
