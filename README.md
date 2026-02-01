# red-willow

[![CI](https://github.com/AbdulRhaman297/red-willow/actions/workflows/ci.yml/badge.svg)](https://github.com/AbdulRhaman297/red-willow/actions)
[![Codecov](https://img.shields.io/codecov/c/github/AbdulRhaman297/red-willow.svg?logo=codecov)](https://codecov.io/gh/AbdulRhaman297/red-willow)

Jarvis-like voice assistant for quick lookups (Shodan, ipinfo, OpenWeather, Wikipedia).

## ⚠️ Note
This repository is intended for defensive or educational purposes. Do not use these tools to attack systems you do not own or have explicit permission to test.

---

## 🔧 Setup
1. Copy `.env.example` → `.env` and fill your API keys (or export env vars directly).

   - Or run the interactive helper to create `.env` (it hides input):
     ```bash
     bash scripts/setup_env.sh
     ```
   - Check your env keys quickly with:
     ```bash
     bash scripts/check_env.sh
     ```

2. Install dependencies:

   pip install -r requirements.txt

If you don't need voice I/O, the script will fall back to typed input/output when necessary.

## 🧩 Environment variables
- `SHODAN_API_KEY` — (optional) Shodan API key for host lookups
- `IPINFO_TOKEN` — (optional) ipinfo token
- `OPENWEATHER_API_KEY` — (optional) OpenWeather API key

### Jarvis (Hybrid assistant) — additional env vars
- `GROQ_API_KEY` — (required to use Groq (Llama 3) for fast replies)
- `GOOGLE_API_KEY` — (required for Google Gemini if using API key authentication)
- `GOOGLE_APPLICATION_CREDENTIALS` — (optional) path to Google service account JSON **alternative** to `GOOGLE_API_KEY`

Notes about Google client library:
- This project prefers the newer `google-genai` client (install via `pip install google-genai`). Older `google-generativeai` may still work but is deprecated.
- `JARVIS_CHROMA_DIR` — (optional) path for local ChromaDB storage (default: `./.chroma`)

Notes:
- You can put these in `.env` (repo already supports `python-dotenv`), or export them in your shell before running `jarvis.py`.
- The assistant falls back to typed input/output when microphone or TTS isn't available.

### Interactive setup helper
- Use the existing Bash helper (Linux/macOS): `scripts/setup_env.sh`
- Or the cross-platform Python helper: `python scripts/setup_jarvis_env.py` — this will prompt for keys and write them to `.env` safely.

### Windows-specific microphone & webcam setup 🔧
If you're on Windows, follow these steps to verify hardware and grant permissions:

1. Open Privacy settings for microphone and camera (run in PowerShell or CMD):
   - `start ms-settings:privacy-microphone`
   - `start ms-settings:privacy-webcam`

2. Check devices via PowerShell (run as Administrator):
   - `Get-PnpDevice -Class Camera`  # lists camera devices
   - `Get-PnpDevice -Class AudioEndpoint`  # lists audio endpoints

3. If devices are disabled, enable them from Device Manager or via Windows Settings.
4. When the script first captures audio/video, Windows may prompt for permission; make sure you allow access for the terminal app you're using.

For running Jarvis continuously in the background on Windows, you can either:
- Use Task Scheduler to run `python path\to\jarvis.py --background --wake-word` at logon, or
- Use NSSM (Non-Sucking Service Manager) to install Jarvis as a service:
  1. Download and extract NSSM (https://nssm.cc/)
  2. `nssm install Jarvis "C:\Python\python.exe" "C:\path\to\jarvis.py" --background --wake-word`

> Tip: Install `pocketsphinx` (offline keyword spotting): `pip install pocketsphinx` — Jarvis will use it for low-latency wake-word detection if available.
### GUI helper (Windows)
A lightweight GUI lets you manage Jarvis as a background service:

- Launch: `python tools/jarvis_gui.py`
- Features:
  - Shows microphone and camera status (green/red indicators)
  - Secure fields to enter `GROQ_API_KEY` and `GOOGLE_API_KEY` (saved to `.env`)
  - Real-time scrolling logs from the Jarvis background process
  - Start / Stop Jarvis background process
  - Minimize to system tray (requires `pystray` + `pillow`)

Install GUI extras:
```bash
pip install pystray pillow
```

For testing & setup on Windows (recommended):
1. Run the PowerShell commands above to ensure permissions are granted.
2. Install `pocketsphinx` for offline wake-word detection: `pip install pocketsphinx`.
3. Confirm the default Windows microphone is the intended device (use Device Manager or the PowerShell commands above).

### Setting Jarvis default microphone (optional)
Use the helper PowerShell script to list input devices and select which one Jarvis should use:

```powershell
cd scripts
./set_default_mic.ps1
```

- The script will save your choice to `.env` under `JARVIS_MIC_NAME`.
- Optionally, install `AudioDeviceCmdlets` to let the script set the system default mic automatically:
  - Install-Module -Name AudioDeviceCmdlets -Scope CurrentUser

For running Jarvis headless with wake-word on login, consider using Task Scheduler (see `scripts/register_task.ps1`) or NSSM as described earlier.
### Memory management (ChromaDB)
- Export memories to JSON: `python tools/jarvis_manage.py export --out memories.json`
- Import memories from JSON: `python tools/jarvis_manage.py import --in memories.json`
- These tools will use the repo's configured Chroma collection and are CI/test friendly.

## ▶️ Run

Run directly:

```bash
python main.py
```

Install and run via pip (editable install for development):

```bash
python -m pip install -e .
jarvis --help
```

You can also run a single command non-interactively:

```bash
python main.py --command "weather London"
python main.py --command "shodan 8.8.8.8" --no-audio
```

## 🧭 Contributing
See `CONTRIBUTING.md` for contribution guidelines and how to run tests locally.

## 🔁 Examples
A simple demo script is available in `examples/run_demo.sh`:

```bash
chmod +x examples/run_demo.sh
./examples/run_demo.sh "weather London"
```

CLI flags:
- `--debug` — enable DEBUG logging (same as `enable_debug()`)
- `--log-file <path>` — write logs to `<path>` (overrides the `LOG_FILE` env var)

## ℹ️ Notes
- The script uses environment variables; you can use `python-dotenv` by creating a `.env` file.
- If `SpeechRecognition` or microphone is not available, the script will ask for typed commands instead.

## ✅ Tests & CI
- Unit tests are in `tests/` and use `pytest`.
- A GitHub Actions workflow (`.github/workflows/ci.yml`) runs the test suite on push and PRs to `main`.

## 🛠️ Development
- Formatting and linting are configured via `.pre-commit-config.yaml` (black, flake8). Run `pre-commit install` after installing dev deps.
