import feedops.quality.shopify_live as shopify_live


def test_load_shopify_live_snapshot_missing_sku(monkeypatch):
    monkeypatch.delenv("SHOPIFY_STORE_URL", raising=False)
    monkeypatch.delenv("SHOPIFY_ACCESS_TOKEN", raising=False)
    snap = shopify_live.load_shopify_live_snapshot("")
    assert snap.error


def test_load_shopify_live_snapshot_missing_credentials(monkeypatch):
    monkeypatch.delenv("SHOPIFY_STORE_URL", raising=False)
    monkeypatch.delenv("SHOPIFY_ACCESS_TOKEN", raising=False)
    snap = shopify_live.load_shopify_live_snapshot("BSK-275LA")
    assert snap.error
    assert snap.title == ""
    assert snap.description == ""


def test_load_shopify_live_snapshot_handles_loader_exception(monkeypatch):
    monkeypatch.setenv("SHOPIFY_STORE_URL", "example.myshopify.com")
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "shpat_example")

    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(shopify_live, "load_parent_sku_unified_with_status", boom)

    snap = shopify_live.load_shopify_live_snapshot("BSK-275LA")
    assert snap.error and "boom" in snap.error

