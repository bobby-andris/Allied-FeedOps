"""CLI integration tests for catalog resolver usage."""

from __future__ import annotations

from pathlib import Path

import pytest


class _DummyScore:
    composite = 0.0
    approval_status = "approved"


class _DummyCandidate:
    final_score = _DummyScore()


class _DummyResult:
    candidate = _DummyCandidate()


def test_healthcheck_uses_resolver(monkeypatch, tmp_path):
    from feedops.cli import main

    catalog = tmp_path / "catalog.csv"
    catalog.write_text("MasterSKU,OPTION SKU\nTEST,TEST-01\n")

    called = {}

    def fake_resolve(*_args, **_kwargs):
        called["ok"] = True
        return catalog

    monkeypatch.setattr(main, "resolve_catalog_path", fake_resolve, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    main.healthcheck()
    assert called.get("ok") is True


def test_list_skus_uses_resolver(monkeypatch, tmp_path):
    import feedops.loaders
    from feedops.cli import main

    catalog = tmp_path / "catalog.csv"
    catalog.write_text("MasterSKU,OPTION SKU\nTEST,TEST-01\n")

    called = {}

    def fake_resolve(*_args, **_kwargs):
        called["ok"] = True
        return catalog

    monkeypatch.setattr(main, "resolve_catalog_path", fake_resolve, raising=False)
    monkeypatch.setattr(feedops.loaders, "load_catalog", lambda _path: object())
    monkeypatch.setattr(feedops.loaders, "list_master_skus", lambda _df: ["TEST"])

    main.list_skus(limit=1, catalog=None)
    assert called.get("ok") is True


def test_optimize_uses_resolver(monkeypatch, tmp_path):
    from feedops.cli import main

    catalog = tmp_path / "catalog.csv"
    catalog.write_text("MasterSKU,OPTION SKU\nTEST,TEST-01\n")

    called = {}

    def fake_resolve(*_args, **_kwargs):
        called["ok"] = True
        return catalog

    def fake_run(coro):
        coro.close()
        return _DummyResult()

    monkeypatch.setattr(main, "resolve_catalog_path", fake_resolve, raising=False)
    monkeypatch.setattr(main.asyncio, "run", fake_run)

    main.optimize(parent_sku="TEST", dry_run=True, catalog=None, candidate_weights=None)
    assert called.get("ok") is True


def test_review_dashboard_uses_resolver(monkeypatch, tmp_path):
    import subprocess

    from feedops.cli import main

    catalog = tmp_path / "catalog.csv"
    catalog.write_text("MasterSKU,OPTION SKU\nTEST,TEST-01\n")

    called = {}

    def fake_resolve(*_args, **_kwargs):
        called["ok"] = True
        return catalog

    def fake_run(cmd, env, check):
        assert env.get("FEEDOPS_CATALOG_PATH") == str(catalog)
        return None

    monkeypatch.setattr(main, "resolve_catalog_path", fake_resolve, raising=False)
    monkeypatch.setattr(subprocess, "run", fake_run)

    main.review_dashboard(catalog=None)
    assert called.get("ok") is True
    assert called.get("ok") is True
