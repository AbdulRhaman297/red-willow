import types

import main


class DummyResponse:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data or {}
        self.text = text

    def json(self):
        return self._data


def test_shodan_missing_key(monkeypatch):
    monkeypatch.setenv("SHODAN_API_KEY", "")
    # reload module to pick up env change
    import importlib

    importlib.reload(main)

    res = main.shodan_lookup("8.8.8.8")
    assert "Shodan API key not set" in res


def test_shodan_valid_response(monkeypatch):
    monkeypatch.setenv("SHODAN_API_KEY", "FAKE")
    # reload to pick up env change
    import importlib

    importlib.reload(main)

    def fake_get(url, timeout=None):
        return DummyResponse(
            200, {"ip_str": "8.8.8.8", "org": "Google", "ports": [53, 443]}
        )

    monkeypatch.setattr(main, "requests", types.SimpleNamespace(get=fake_get))
    res = main.shodan_lookup("8.8.8.8")
    assert "IP: 8.8.8.8" in res
    assert "Organization: Google" in res


def test_ipinfo_no_ip(monkeypatch):
    res = main.ipinfo_lookup("not an ip")
    assert "No valid IPv4 address" in res


def test_ipinfo_valid(monkeypatch):
    def fake_get(url, timeout=None):
        return DummyResponse(
            200,
            {
                "ip": "1.2.3.4",
                "city": "Testville",
                "region": "TestRegion",
                "country": "TS",
                "org": "TestOrg",
            },
        )

    monkeypatch.setattr(main, "requests", types.SimpleNamespace(get=fake_get))
    res = main.ipinfo_lookup("1.2.3.4")
    assert "City: Testville" in res


def test_weather_missing_key(monkeypatch):
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
    import importlib

    importlib.reload(main)
    res = main.weather_lookup("London")
    assert "OpenWeather API key not set" in res


def test_weather_valid(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "FAKE")
    # reload to pick up env change
    import importlib

    importlib.reload(main)

    def fake_get(url, timeout=None):
        return DummyResponse(
            200, {"weather": [{"description": "sunny"}], "main": {"temp": 20}}
        )

    monkeypatch.setattr(main, "requests", types.SimpleNamespace(get=fake_get))
    res = main.weather_lookup("London")
    assert "Weather in London" in res


def test_wiki_no_topic():
    res = main.wiki_lookup("")
    assert "Please specify a topic" in res


def test_wiki_valid(monkeypatch):
    def fake_get(url, timeout=None):
        return DummyResponse(200, {"extract": "An example page summary."})

    monkeypatch.setattr(main, "requests", types.SimpleNamespace(get=fake_get))
    res = main.wiki_lookup("Python")
    assert "example page summary" in res.lower()
