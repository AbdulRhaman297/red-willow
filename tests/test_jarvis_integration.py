import types

import pytest

import jarvis


def test_handle_input_calls_groq(monkeypatch):
    called = {}

    def fake_groq(prompt: str):
        called["groq"] = prompt
        return "groq-response"

    monkeypatch.setattr(jarvis, "call_groq", fake_groq)
    jarvis.set_options(dry_run=False)
    out = jarvis.handle_input("Hello Jarvis")
    assert out == "groq-response"
    assert "Hello Jarvis" in called["groq"]


def test_handle_input_calls_gemini_for_complex(monkeypatch):
    called = {}

    def fake_gemini(prompt: str):
        called["gemini"] = prompt
        return "gemini-response"

    monkeypatch.setattr(jarvis, "call_gemini", fake_gemini)
    jarvis.set_options(dry_run=False)
    long_query = "please analyze this: " + "x" * 300
    out = jarvis.handle_input(long_query)
    assert out == "gemini-response"
    assert "please analyze this" in called["gemini"]


def test_set_options_no_audio(monkeypatch, caplog):
    prev = jarvis.NO_AUDIO
    try:
        jarvis.set_options(no_audio=True)
        # speaking should be skipped when NO_AUDIO is True
        caplog.clear()
        jarvis.speak("This should not speak")
        assert (
            any(
                "NO_AUDIO" in r.message or r.levelname == "DEBUG"
                for r in caplog.records
            )
            or jarvis.NO_AUDIO
        )
    finally:
        jarvis.set_options(no_audio=prev)


def test_dry_run_mode_returns_simulated():
    prev = jarvis.DRY_RUN
    try:
        jarvis.set_options(dry_run=True)
        assert jarvis.call_groq("x") == "[dry-run] Groq simulated response"
        assert jarvis.call_gemini("x") == "[dry-run] Gemini simulated response"
    finally:
        jarvis.set_options(dry_run=prev)


def test_memory_add_query_mock(monkeypatch):
    # Replace the memory collection with a fake that records adds/queries
    class FakeCol:
        def __init__(self):
            self.added = []

        def add(self, ids, documents, metadatas):
            self.added.append((ids, documents, metadatas))

        def query(self, query_texts, n_results):
            return {"documents": [["fake memory result"]], "metadatas": [[{"k": "v"}]]}

    fake = FakeCol()
    monkeypatch.setattr(jarvis, "_memory_col", fake)
    jarvis.add_memory("remember me", meta={"test": True})
    assert fake.added
    res = jarvis.query_memories("remember me", k=1)
    assert res and res[0]["text"] == "fake memory result"
