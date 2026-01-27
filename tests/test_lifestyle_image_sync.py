import json


def test_sync_lifestyle_images_copies_and_rewrites(tmp_path):
    repo_root = tmp_path
    image_dir = repo_root / "data" / "lifestyle_images"
    image_dir.mkdir(parents=True)
    image_path = image_dir / "TEST-SKU_var1_20260125_000000.png"
    image_path.write_bytes(b"fake-png")

    exports_dir = repo_root / "exports" / "run-1"
    exports_dir.mkdir(parents=True)
    patch_path = exports_dir / "google-patch-TEST-SKU.json"
    patch_path.write_text(
        json.dumps(
            {
                "title": "Test Title",
                "description": "Test Description",
                "lifestyle_images": [
                    {
                        "image_path": "data/lifestyle_images/TEST-SKU_var1_20260125_000000.png",
                        "variation_num": 1,
                        "generation_success": True,
                        "prompt_used": "prompt",
                        "timestamp": "2026-01-25T00:00:00",
                    }
                ],
            }
        )
    )

    from feedops.quality import data_loader

    sync = getattr(data_loader, "sync_lifestyle_images", None)
    assert sync is not None

    stats = sync(exports_dir, repo_root=repo_root)

    updated = json.loads(patch_path.read_text())
    new_path = updated["lifestyle_images"][0]["image_path"]

    assert new_path == "exports/run-1/images/TEST-SKU_var1_20260125_000000.png"
    assert (repo_root / new_path).exists()
    assert stats["images_copied"] == 1
    assert stats["files_updated"] == 1


def test_load_exports_dir_defaults_selected_lifestyle_image(tmp_path):
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True)

    patch_path = exports_dir / "google-patch-TEST-SKU.json"
    patch_path.write_text(
        json.dumps(
            {
                "title": "Test Title",
                "description": "Test Description",
                "lifestyle_images": [
                    {
                        "image_path": "data/lifestyle_images/TEST-SKU_var2_20260125_000000.png",
                        "variation_num": 2,
                        "generation_success": True,
                        "prompt_used": "prompt",
                        "timestamp": "2026-01-25T00:00:00",
                    }
                ],
            }
        )
    )

    from feedops.quality.data_loader import load_exports_dir

    exports = load_exports_dir(exports_dir)
    content = exports["TEST-SKU"]["google"]
    assert content.selected_lifestyle_image == 2
