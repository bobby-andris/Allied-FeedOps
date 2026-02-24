from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_script_module(filename: str, module_name: str):
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    script_path = scripts_dir / filename
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_select_unseen_skus_is_deterministic_and_excludes_inputs(monkeypatch) -> None:
    batch = _load_script_module("batch_ab_test.py", "batch_ab_test_module")

    catalog = {"A", "B", "C", "D", "E", "F", "G"}
    generated = {"A", "B"}
    excluded = {"C"}

    def _fake_fetch(table_name: str) -> set[str]:
        if table_name == "product_catalog":
            return catalog
        if table_name == "generated_content":
            return generated
        raise AssertionError(f"Unexpected table: {table_name}")

    monkeypatch.setattr(batch, "_fetch_distinct_master_skus", _fake_fetch)

    sample_one = batch.select_unseen_skus(
        unseen_count=3,
        unseen_seed=52,
        excluded_skus=excluded,
    )
    sample_two = batch.select_unseen_skus(
        unseen_count=3,
        unseen_seed=52,
        excluded_skus=excluded,
    )

    assert sample_one == sample_two
    assert len(sample_one) == 3
    assert set(sample_one).isdisjoint(generated)
    assert set(sample_one).isdisjoint(excluded)


def test_resolve_run_skus_unseen_mode_excludes_canonical(monkeypatch) -> None:
    batch = _load_script_module("batch_ab_test.py", "batch_ab_test_module_resolve")
    monkeypatch.setattr(
        batch,
        "select_unseen_skus",
        lambda **_kwargs: ["SKU-1", "SKU-2", "SKU-3", "SKU-4", "SKU-5"],
    )

    skus, meta = batch.resolve_run_skus(
        explicit_skus=None,
        unseen_count=5,
        unseen_seed=52,
        include_canonical=False,
    )

    assert skus == ["SKU-1", "SKU-2", "SKU-3", "SKU-4", "SKU-5"]
    assert meta["mode"] == "unseen"
    assert meta["unseen_count"] == 5
    assert meta["unseen_seed"] == 52
