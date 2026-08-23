import os


def test_live_provider_is_explicitly_opt_in(monkeypatch):
    monkeypatch.delenv("EX021_LIVE", raising=False)
    assert os.getenv("EX021_LIVE") != "1"
