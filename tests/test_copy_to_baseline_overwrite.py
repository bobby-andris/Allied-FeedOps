import json
from pathlib import Path


def test_copy_to_baseline_overwrite_replaces_existing_files(tmp_path: Path):
    from feedops.pipeline.copy_to_baseline import copy_to_baseline

    candidate = tmp_path / "candidate"
    baseline = tmp_path / "baseline"
    candidate.mkdir()
    baseline.mkdir()

    (candidate / "google-patch-ABC.json").write_text(json.dumps({"title": "new"}))
    (baseline / "google-patch-ABC.json").write_text(json.dumps({"title": "old"}))

    copy_to_baseline(candidate, baseline, dry_run=False, overwrite_existing=True)

    payload = json.loads((baseline / "google-patch-ABC.json").read_text())
    assert payload["title"] == "new"

