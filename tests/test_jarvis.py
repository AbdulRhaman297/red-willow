import os
import time

import pytest

import jarvis


def test_choose_api_short_simple():
    assert jarvis.choose_api("hello how are you", []) == "groq"


def test_choose_api_long_or_history_uses_gemini():
    long_text = "x" * 300
    assert jarvis.choose_api(long_text, []) == "gemini"
    assert jarvis.choose_api("please analyze this", ["h"] * 10) == "gemini"


def test_build_prompt_includes_memories_and_history():
    mems = [{"text": "remember this", "meta": {}}]
    hist = ["User: hi", "Jarvis: hello"]
    prompt = jarvis.build_prompt("What's up", mems, hist)
    assert "remember this" in prompt
    assert "User: What's up" in prompt


def test_call_groq_key_missing_message():
    old = os.environ.pop("GROQ_API_KEY", None)
    try:
        out = jarvis.call_groq("test")
        assert "Groq API key not set" in out
    finally:
        if old is not None:
            os.environ["GROQ_API_KEY"] = old


def test_call_gemini_key_missing_message():
    old1 = os.environ.pop("GOOGLE_API_KEY", None)
    old2 = os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    try:
        out = jarvis.call_gemini("test")
        assert "Google API credentials not found" in out
    finally:
        if old1 is not None:
            os.environ["GOOGLE_API_KEY"] = old1
        if old2 is not None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old2


@pytest.mark.skipif(jarvis._memory_col is None, reason="ChromaDB not available")
def test_add_and_query_memory():
    # add a unique memory and ensure it can be found
    text = f"pytest-memory-{int(time.time())}"
    jarvis.add_memory(text, meta={"test": True})
    res = jarvis.query_memories(text, k=5)
    assert any(
        text in m["text"]
        for m in [
            {"text": r, "meta": m}
            for r, m in zip(
                res and [r["text"] for r in res] or [],
                res and [r["meta"] for r in res] or [],
            )
        ]
    )
