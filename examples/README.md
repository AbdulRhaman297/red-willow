# Examples — red-willow

These examples show basic usage of the assistant in non-interactive mode.

Run a single command (weather):

```bash
python -m main --command "weather London" --no-audio
# or after installing package
jarvis --command "weather London" --no-audio
```

Shodan lookup:

```bash
jarvis --command "shodan 8.8.8.8" --no-audio
```

Run interactively (speech if available):

```bash
jarvis
```

Notes:
- For audio support, install `pyttsx3` and `SpeechRecognition` (and optionally `pyaudio` for mic input).
- Use `.env` or environment variables for API keys: `SHODAN_API_KEY`, `IPINFO_TOKEN`, `OPENWEATHER_API_KEY`.
