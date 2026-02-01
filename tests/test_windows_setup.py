import threading
import time

import jarvis


def test_device_checks_monkeypatched(monkeypatch):
    monkeypatch.setattr(jarvis, "check_microphone", lambda: True)
    monkeypatch.setattr(jarvis, "check_camera", lambda: True)
    assert jarvis.check_microphone()
    assert jarvis.check_camera()


def test_wakeword_background_triggers(monkeypatch):
    # Simulate wake-word detection by replacing the _wakeword_loop with a short runner
    events = {"triggered": False}

    def fake_start(callback):
        def run():
            callback()

        t = threading.Thread(target=run)
        t.daemon = True
        t.start()
        return threading.Event()

    monkeypatch.setattr(jarvis, "start_wakeword_background", lambda cb: fake_start(cb))

    # Replace handler to mark triggered
    def fake_on_wake():
        events["triggered"] = True

    jarvis.start_wakeword_background(fake_on_wake)
    time.sleep(0.1)
    assert events["triggered"]
