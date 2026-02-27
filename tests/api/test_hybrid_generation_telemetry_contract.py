from pathlib import Path


def test_hybrid_regeneration_history_persists_telemetry_fields() -> None:
    source = Path("src/feedops/api/hybrid_generation.py").read_text()

    assert '"tokens_used": platform_telemetry.get("tokens_used")' in source
    assert '"cost_usd": platform_telemetry.get("cost_usd")' in source
    assert '"latency_ms": platform_telemetry.get("latency_ms")' in source
    assert '"provider_attempt_count": platform_telemetry.get("provider_attempt_count")' in source
    assert '"parse_retry_count": platform_telemetry.get("parse_retry_count")' in source
