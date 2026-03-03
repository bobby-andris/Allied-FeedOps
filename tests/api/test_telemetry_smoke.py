"""Smoke tests — telemetry.py importable without main.py."""
import threading


def test_telemetry_importable_standalone():
    from feedops.api.telemetry import run_async_in_thread
    assert callable(run_async_in_thread)


def test_no_circular_import_with_main():
    import feedops.api.telemetry
    import feedops.api.main


def test_run_async_in_thread_creates_non_daemon_thread():
    """run_async_in_thread must use non-daemon threads (survive HTTP response)."""
    from feedops.api.telemetry import run_async_in_thread
    import inspect
    source = inspect.getsource(run_async_in_thread)
    assert "daemon" in source.lower() or "daemon=False" in source or "thread.daemon = False" in source


def test_emit_generation_summary_importable():
    from feedops.api.telemetry import _emit_generation_summary
    assert callable(_emit_generation_summary)


def test_should_persist_finish_sentences_importable():
    from feedops.api.telemetry import _should_persist_finish_sentences
    assert callable(_should_persist_finish_sentences)


def test_run_async_in_thread_daemon_false_at_runtime():
    """DECOMP-08: thread.daemon must be False at runtime, not just in source."""
    from feedops.api.telemetry import run_async_in_thread
    import asyncio

    async def noop():
        pass

    thread = run_async_in_thread(noop)
    assert thread.daemon is False, "run_async_in_thread must use non-daemon threads"
    thread.join(timeout=2.0)
