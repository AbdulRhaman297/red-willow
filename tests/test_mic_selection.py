import importlib
import os

import pytest

import jarvis


def test_get_available_mics_monkeypatch(monkeypatch):
    class FakePyAudio:
        def __init__(self):
            pass

        def get_device_count(self):
            return 2

        def get_device_info_by_index(self, i):
            if i == 0:
                return {"name": "Microphone A", "maxInputChannels": 1}
            return {"name": "Microphone B", "maxInputChannels": 1}

        def terminate(self):
            pass

    monkeypatch.setattr("jarvis.pyaudio", None, raising=False)
    # monkeypatch import of pyaudio within function by injecting a dummy module into sys.modules
    import sys
    import types

    fake = types.SimpleNamespace(PyAudio=lambda: FakePyAudio())
    sys.modules["pyaudio"] = fake

    mics = jarvis.get_available_mics()
    assert len(mics) >= 2
    del sys.modules["pyaudio"]


def test_verify_and_select_prefers_configured(monkeypatch):
    class FakePyAudio:
        def __init__(self):
            pass

        def get_device_count(self):
            return 2

        def get_device_info_by_index(self, i):
            if i == 0:
                return {"name": "Internal Mic", "maxInputChannels": 1}
            return {"name": "USB Mic", "maxInputChannels": 1}

        def terminate(self):
            pass

    import sys
    import types

    sys.modules["pyaudio"] = types.SimpleNamespace(PyAudio=lambda: FakePyAudio())
    os.environ["JARVIS_MIC_NAME"] = "USB"
    idx = jarvis.verify_and_select_mic()
    assert idx == 1
    del sys.modules["pyaudio"]
    os.environ.pop("JARVIS_MIC_NAME", None)


def test_verify_and_select_missing_config(monkeypatch):
    class FakePyAudio:
        def __init__(self):
            pass

        def get_device_count(self):
            return 1

        def get_device_info_by_index(self, i):
            return {"name": "Only Mic", "maxInputChannels": 1}

        def terminate(self):
            pass

    import sys
    import types

    sys.modules["pyaudio"] = types.SimpleNamespace(PyAudio=lambda: FakePyAudio())
    os.environ["JARVIS_MIC_NAME"] = "NonExistentMic"
    idx = jarvis.verify_and_select_mic()
    assert idx == 0
    del sys.modules["pyaudio"]
    os.environ.pop("JARVIS_MIC_NAME", None)
