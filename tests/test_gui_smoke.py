import os
import tempfile

from tools import jarvis_gui


def test_set_env_key_tmp(tmp_path):
    env = tmp_path / ".env"
    # monkeypatch REPO_ROOT by setting ENV_FILE path temporarily
    old = jarvis_gui.ENV_FILE
    try:
        jarvis_gui.ENV_FILE = env
        jarvis_gui.set_env_key("TEST_KEY", "VALUE")
        text = env.read_text()
        assert "TEST_KEY=VALUE" in text
    finally:
        jarvis_gui.ENV_FILE = old


def test_start_stop_process_monkeypatched(monkeypatch):
    # monkeypatch subprocess.Popen to a fake object
    class FakeProc:
        def __init__(self):
            self.stdout = []

        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout=None):
            pass

        def kill(self):
            pass

    fake = FakeProc()
    monkeypatch.setattr(jarvis_gui.subprocess, "Popen", lambda *a, **k: fake)
    # Start should not raise
    jarvis_gui.start_jarvis_process()
    jarvis_gui.stop_jarvis_process()
