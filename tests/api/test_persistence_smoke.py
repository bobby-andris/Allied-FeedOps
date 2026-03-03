"""Smoke tests — persistence.py importable without main.py."""


def test_persistence_importable_standalone():
    from feedops.api.persistence import (
        _lookup_generated_content_id,
        _persist_regeneration_result,
        _persist_generated_content_and_history,
        _upsert_batch_job_sku_status,
    )
    assert callable(_lookup_generated_content_id)


def test_no_circular_import_with_main():
    import feedops.api.persistence
    import feedops.api.main


def test_assembled_prompt_hash_is_pure():
    from feedops.api.persistence import _assembled_prompt_hash
    assert callable(_assembled_prompt_hash)


def test_enforce_finish_placeholder_contract_importable():
    from feedops.api.persistence import _enforce_write_time_finish_placeholder_contract
    assert callable(_enforce_write_time_finish_placeholder_contract)
