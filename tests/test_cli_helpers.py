from feedops.cli import main as cli_main


def test_should_auto_sync_when_cache_missing(monkeypatch):
    monkeypatch.setattr(cli_main, "get_cached_shopify_age_hours", lambda *_: None)

    should_sync, age = cli_main._should_auto_sync("ABC", 24.0)

    assert should_sync is True
    assert age is None


def test_should_auto_sync_when_cache_stale(monkeypatch):
    monkeypatch.setattr(cli_main, "get_cached_shopify_age_hours", lambda *_: 26.0)

    should_sync, age = cli_main._should_auto_sync("ABC", 24.0)

    assert should_sync is True
    assert age == 26.0


def test_should_auto_sync_when_cache_fresh(monkeypatch):
    monkeypatch.setattr(cli_main, "get_cached_shopify_age_hours", lambda *_: 2.0)

    should_sync, age = cli_main._should_auto_sync("ABC", 24.0)

    assert should_sync is False
    assert age == 2.0
