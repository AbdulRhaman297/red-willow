import pytest

import jarvis


def test_listen_uses_speech_recognition(monkeypatch):
    # Mock Recognizer methods and Microphone context manager
    class DummyAudio:
        pass

    class FakeRecognizer:
        def listen(self, src, timeout=None, phrase_time_limit=None):
            return DummyAudio()

        def recognize_google(self, audio):
            return "Hello Jarvis"

    class FakeMicrophone:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(jarvis, "_recognizer", FakeRecognizer())
    # patch the module-level sr to have a Microphone class that doesn't require PyAudio
    if hasattr(jarvis, "sr") and jarvis.sr is not None:
        monkeypatch.setattr(jarvis.sr, "Microphone", FakeMicrophone)

    out = jarvis.listen()
    assert out == "Hello Jarvis"


def test_main_loop_dry_run_no_audio(monkeypatch):
    # Simulate two listens: first return a query, second return 'exit' to terminate loop
    calls = {"n": 0}

    def fake_listen(timeout=6.0, phrase_time_limit=20.0):
        calls["n"] += 1
        return "hello" if calls["n"] == 1 else "exit"

    def fake_groq(prompt: str):
        return "simulated response"

    # Capture speak calls by setting NO_AUDIO
    monkeypatch.setattr(jarvis, "listen", fake_listen)
    monkeypatch.setattr(jarvis, "call_groq", fake_groq)
    prev_dry = jarvis.DRY_RUN
    prev_noaudio = jarvis.NO_AUDIO
    try:
        jarvis.set_options(dry_run=True, no_audio=True)
        # Running the main loop should exit cleanly
        jarvis.main_loop()
        assert calls["n"] >= 2
    finally:
        jarvis.set_options(dry_run=prev_dry, no_audio=prev_noaudio)
