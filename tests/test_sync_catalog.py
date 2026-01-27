"""Tests for sync-catalog command implementation."""

from __future__ import annotations

import sys
from pathlib import Path


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub")


def test_sync_catalog_defaults_use_catalog_env(monkeypatch, tmp_path):
    from feedops.cli import sync as sync_module

    catalog_path = tmp_path / "catalog.csv"
    mc_path = tmp_path / "mc.jsonl"

    calls: dict[str, Path] = {}

    def fake_shopify(output_path: Path, *_args, **_kwargs):
        calls["catalog"] = Path(output_path)

    def fake_mapi(output_path: Path, *_args, **_kwargs):
        calls["mc"] = Path(output_path)

    monkeypatch.setattr(sync_module, "write_shopify_catalog_csv", fake_shopify)
    monkeypatch.setattr(sync_module, "write_merchant_center_snapshot", fake_mapi)

    sync_module.sync_catalog(
        source="auto",
        output_catalog=None,
        output_mc_metadata=str(mc_path),
        limit=1,
        force=True,
        ttl_hours=24,
        env={"CATALOG_PATH": str(catalog_path)},
    )

    assert calls["catalog"] == catalog_path
    assert calls["mc"] == mc_path


def test_sync_catalog_skips_fresh_without_force(monkeypatch, tmp_path):
    from feedops.cli import sync as sync_module

    catalog_path = tmp_path / "catalog.csv"
    mc_path = tmp_path / "mc.jsonl"
    _touch(catalog_path)
    _touch(mc_path)

    calls = {"catalog": 0, "mc": 0}

    def fake_shopify(*_args, **_kwargs):
        calls["catalog"] += 1

    def fake_mapi(*_args, **_kwargs):
        calls["mc"] += 1

    monkeypatch.setattr(sync_module, "write_shopify_catalog_csv", fake_shopify)
    monkeypatch.setattr(sync_module, "write_merchant_center_snapshot", fake_mapi)

    sync_module.sync_catalog(
        source="auto",
        output_catalog=str(catalog_path),
        output_mc_metadata=str(mc_path),
        limit=None,
        force=False,
        ttl_hours=24,
        env={},
    )

    assert calls["catalog"] == 0
    assert calls["mc"] == 0


def test_sync_catalog_source_forces_shopify(monkeypatch, tmp_path):
    from feedops.cli import sync as sync_module

    catalog_path = tmp_path / "catalog.csv"
    mc_path = tmp_path / "mc.jsonl"
    _touch(catalog_path)
    _touch(mc_path)

    calls = {"catalog": 0, "mc": 0}

    def fake_shopify(*_args, **_kwargs):
        calls["catalog"] += 1

    def fake_mapi(*_args, **_kwargs):
        calls["mc"] += 1

    monkeypatch.setattr(sync_module, "write_shopify_catalog_csv", fake_shopify)
    monkeypatch.setattr(sync_module, "write_merchant_center_snapshot", fake_mapi)

    sync_module.sync_catalog(
        source="shopify",
        output_catalog=str(catalog_path),
        output_mc_metadata=str(mc_path),
        limit=None,
        force=False,
        ttl_hours=24,
        env={},
    )

    assert calls["catalog"] == 1
    assert calls["mc"] == 0


def test_sync_catalog_force_refreshes_both(monkeypatch, tmp_path):
    from feedops.cli import sync as sync_module

    catalog_path = tmp_path / "catalog.csv"
    mc_path = tmp_path / "mc.jsonl"
    _touch(catalog_path)
    _touch(mc_path)

    calls = {"catalog": 0, "mc": 0}

    def fake_shopify(*_args, **_kwargs):
        calls["catalog"] += 1

    def fake_mapi(*_args, **_kwargs):
        calls["mc"] += 1

    monkeypatch.setattr(sync_module, "write_shopify_catalog_csv", fake_shopify)
    monkeypatch.setattr(sync_module, "write_merchant_center_snapshot", fake_mapi)

    sync_module.sync_catalog(
        source="auto",
        output_catalog=str(catalog_path),
        output_mc_metadata=str(mc_path),
        limit=None,
        force=True,
        ttl_hours=24,
        env={},
    )

    assert calls["catalog"] == 1
    assert calls["mc"] == 1


def test_sync_catalog_runs_mc_before_shopify(monkeypatch, tmp_path):
    from feedops.cli import sync as sync_module

    catalog_path = tmp_path / "catalog.csv"
    mc_path = tmp_path / "mc.jsonl"

    order: list[str] = []

    def fake_shopify(*_args, **_kwargs):
        order.append("shopify")

    def fake_mapi(*_args, **_kwargs):
        order.append("mapi")

    monkeypatch.setattr(sync_module, "write_shopify_catalog_csv", fake_shopify)
    monkeypatch.setattr(sync_module, "write_merchant_center_snapshot", fake_mapi)

    sync_module.sync_catalog(
        source="auto",
        output_catalog=str(catalog_path),
        output_mc_metadata=str(mc_path),
        limit=None,
        force=True,
        ttl_hours=24,
        env={},
    )

    assert order == ["mapi", "shopify"]


def test_sync_catalog_shopify_writes_catalog_csv(monkeypatch, tmp_path):
    from feedops.cli import sync as sync_module
    from feedops.integrations import shopify_catalog

    catalog_path = tmp_path / "catalog.csv"
    mc_path = tmp_path / "mc.jsonl"
    sample_product = {
        "id": "gid://shopify/Product/123",
        "legacyResourceId": "123",
        "title": "Test Product",
        "descriptionHtml": "<p>Test description</p>",
        "productType": "Towel Bars",
        "vendor": "Allied Brass",
        "tags": [],
        "collections": {"nodes": [{"title": "Test Collection"}]},
        "featuredMedia": {"image": {"url": "https://example.com/main.jpg"}},
        "metafields": {"nodes": []},
        "variants": {
            "nodes": [
                {
                    "id": "gid://shopify/ProductVariant/456",
                    "legacyResourceId": "456",
                    "sku": "TEST-ABR",
                    "barcode": "1234567890",
                    "title": "Antique Brass",
                    "position": 1,
                    "selectedOptions": [{"name": "Finish", "value": "Antique Brass"}],
                    "media": {"nodes": []},
                }
            ]
        },
    }

    monkeypatch.setattr(
        shopify_catalog,
        "fetch_shopify_products",
        lambda *_args, **_kwargs: [sample_product],
    )

    sync_module.sync_catalog(
        source="shopify",
        output_catalog=str(catalog_path),
        output_mc_metadata=str(mc_path),
        limit=1,
        force=True,
        ttl_hours=0,
        env={},
    )

    header = catalog_path.read_text().splitlines()[0].split(",")
    assert "MasterSKU" in header
    assert "GMCID" in header


def test_sync_catalog_reports_progress(capsys, monkeypatch, tmp_path):
    from feedops.cli import sync as sync_module

    catalog_path = tmp_path / "catalog.csv"
    mc_path = tmp_path / "mc.jsonl"

    monkeypatch.setattr(
        sync_module, "write_shopify_catalog_csv", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        sync_module, "write_merchant_center_snapshot", lambda *_a, **_k: None
    )

    sync_module.sync_catalog(
        source="auto",
        output_catalog=str(catalog_path),
        output_mc_metadata=str(mc_path),
        limit=None,
        force=True,
        ttl_hours=24,
        env={},
    )

    output = capsys.readouterr().out
    assert "Catalog sync: starting" in output
    assert "Shopify catalog: refreshing" in output
    assert "Merchant Center metadata: refreshing" in output
    assert "Catalog sync: complete" in output


def test_sync_catalog_progress_flushes(monkeypatch, tmp_path):
    from feedops.cli import sync as sync_module

    class DummyStdout:
        def __init__(self) -> None:
            self.writes: list[str] = []
            self.flush_count = 0

        def write(self, text: str) -> int:
            self.writes.append(text)
            return len(text)

        def flush(self) -> None:
            self.flush_count += 1

    dummy = DummyStdout()
    monkeypatch.setattr(sys, "stdout", dummy)
    monkeypatch.setattr(
        sync_module, "write_shopify_catalog_csv", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        sync_module, "write_merchant_center_snapshot", lambda *_a, **_k: None
    )

    sync_module.sync_catalog(
        source="auto",
        output_catalog=str(tmp_path / "catalog.csv"),
        output_mc_metadata=str(tmp_path / "mc.jsonl"),
        limit=None,
        force=True,
        ttl_hours=24,
        env={},
    )

    output = "".join(dummy.writes)
    assert "Catalog sync: starting" in output
    assert dummy.flush_count > 0
