"""Catalog path resolution utilities."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

DEFAULT_CATALOG_RELATIVE = Path("data") / "catalog" / "Product Catalog.csv"
DEFAULT_CACHE_PATH = (
    Path.home() / ".cache" / "feedops" / "catalog" / "Product Catalog.csv"
)


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _find_in_parents(start_dir: Path, *, max_depth: int) -> Path | None:
    current = start_dir.resolve()
    for _ in range(max_depth + 1):
        candidate = current / DEFAULT_CATALOG_RELATIVE
        if candidate.exists():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def resolve_catalog_path(
    catalog_arg: str | None,
    *,
    start_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
    max_parent_depth: int = 5,
) -> Path:
    """Resolve catalog path using CLI arg, env, parent search, or cache.

    Args:
        catalog_arg: CLI --catalog value.
        start_dir: Directory to begin parent discovery.
        env: Environment mapping (defaults to os.environ).
        max_parent_depth: Max parent levels to search.

    Returns:
        Path to existing catalog CSV.
    """
    env = env or os.environ

    if catalog_arg:
        cli_path = Path(catalog_arg).expanduser()
        if cli_path.exists():
            return cli_path
        raise FileNotFoundError(f"Catalog not found: {cli_path}")

    env_catalog = env.get("CATALOG_PATH", str(DEFAULT_CATALOG_RELATIVE))
    if env_catalog:
        env_path = Path(env_catalog).expanduser()
        if env_path.exists():
            return env_path

    base_dir = start_dir or Path.cwd()
    parent_match = _find_in_parents(Path(base_dir), max_depth=max_parent_depth)
    if parent_match:
        return parent_match

    cache_path = Path(
        env.get("FEEDOPS_CATALOG_CACHE_PATH", str(DEFAULT_CACHE_PATH))
    ).expanduser()
    if cache_path.exists():
        return cache_path

    if _truthy(env.get("FEEDOPS_CATALOG_AUTO_SYNC")):
        from feedops.cli.sync import sync_catalog  # pragma: no cover

        synced = sync_catalog(
            source="auto",
            output_catalog=str(cache_path),
            output_mc_metadata=None,
            limit=None,
            force=False,
            ttl_hours=None,
        )
        if synced and cache_path.exists():
            return cache_path

    raise FileNotFoundError(
        "Catalog not found. Run `feedops sync-catalog` or set `CATALOG_PATH`."
    )
