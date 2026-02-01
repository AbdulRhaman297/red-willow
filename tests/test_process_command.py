import types

import main


class DummyResponse:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data or {}
        self.text = text

    def json(self):
        return self._data


def test_process_shodan(monkeypatch):
    monkeypatch.setattr(main, "SHODAN_API_KEY", "FAKE")

    def fake_get(url, timeout=None):
        return DummyResponse(
            200,
            {"ip_str": "8.8.8.8", "org": "Google", "ports": [53]},
        )

    monkeypatch.setattr(main, "requests", types.SimpleNamespace(get=fake_get))
    output = []
    monkeypatch.setattr(main, "speak", lambda t: output.append(t))
    res = main.process_command("shodan 8.8.8.8")
    assert "IP: 8.8.8.8" in res
    assert output and "IP: 8.8.8.8" in output[0]


def test_process_weather(monkeypatch):
    monkeypatch.setattr(main, "OPENWEATHER_API_KEY", "FAKE")

    def fake_get(url, timeout=None):
        return DummyResponse(
            200, {"weather": [{"description": "cloudy"}], "main": {"temp": 12}}
        )

    monkeypatch.setattr(main, "requests", types.SimpleNamespace(get=fake_get))
    output = []
    monkeypatch.setattr(main, "speak", lambda t: output.append(t))
    res = main.process_command("weather in Testville")
    assert "weather in testville" in res.lower()
    assert output and "weather in testville" in output[0].lower()


def test_process_wikipedia(monkeypatch):
    def fake_get(url, timeout=None):
        return DummyResponse(200, {"extract": "Summary text"})

    monkeypatch.setattr(main, "requests", types.SimpleNamespace(get=fake_get))
    output = []
    monkeypatch.setattr(main, "speak", lambda t: output.append(t))
    res = main.process_command("wikipedia Python")
    assert "Summary text" in res
    assert output and "Summary text" in output[0]


def test_unrecognized(monkeypatch):
    output = []
    monkeypatch.setattr(main, "speak", lambda t: output.append(t))
    res = main.process_command("something random")
    assert "Command not recognized" in res
    assert output and "Command not recognized" in output[0]
