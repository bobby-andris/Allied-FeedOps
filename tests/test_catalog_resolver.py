"""Tests for catalog path resolver."""

from __future__ import annotations

from pathlib import Path

import pytest


def _write_min_catalog(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("MasterSKU,OPTION SKU\nTEST,TEST-01\n")


def test_resolve_catalog_prefers_cli_path(tmp_path):
    from feedops.loaders.catalog_resolver import resolve_catalog_path

    cli_path = tmp_path / "custom.csv"
    _write_min_catalog(cli_path)

    resolved = resolve_catalog_path(str(cli_path), start_dir=tmp_path, env={})
    assert resolved == cli_path


def test_resolve_catalog_errors_on_missing_cli_path(tmp_path):
    from feedops.loaders.catalog_resolver import resolve_catalog_path

    missing = tmp_path / "missing.csv"
    with pytest.raises(FileNotFoundError):
        resolve_catalog_path(str(missing), start_dir=tmp_path, env={})


def test_resolve_catalog_discovers_parent(tmp_path):
    from feedops.loaders.catalog_resolver import resolve_catalog_path

    repo_root = tmp_path / "repo"
    catalog = repo_root / "data" / "catalog" / "Product Catalog.csv"
    _write_min_catalog(catalog)

    worktree = repo_root / ".worktrees" / "branch"
    worktree.mkdir(parents=True, exist_ok=True)

    resolved = resolve_catalog_path(None, start_dir=worktree, env={})
    assert resolved == catalog


def test_resolve_catalog_uses_cache_when_no_local(tmp_path):
    from feedops.loaders.catalog_resolver import resolve_catalog_path

    cache_path = tmp_path / ".cache" / "feedops" / "catalog" / "Product Catalog.csv"
    _write_min_catalog(cache_path)

    resolved = resolve_catalog_path(
        None,
        start_dir=tmp_path / "repo" / ".worktrees" / "branch",
        env={"FEEDOPS_CATALOG_CACHE_PATH": str(cache_path)},
    )
    assert resolved == cache_path
