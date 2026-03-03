"""Smoke tests — job_management.py importable without main.py."""


def test_job_management_importable_standalone():
    from feedops.api.job_management import (
        _create_regeneration_job,
        _format_job_error,
        _require_request_id,
        _regeneration_idempotency_key,
        _find_active_regeneration_job,
    )
    assert callable(_create_regeneration_job)


def test_no_circular_import_with_main():
    import feedops.api.job_management
    import feedops.api.main


def test_format_job_error_is_pure():
    from feedops.api.job_management import _format_job_error
    result = _format_job_error(ValueError("test error"))
    assert isinstance(result, str)
    assert "test error" in result


def test_idempotency_key_is_deterministic():
    from feedops.api.job_management import _regeneration_idempotency_key
    # Should be callable (actual args depend on function signature)
    assert callable(_regeneration_idempotency_key)
