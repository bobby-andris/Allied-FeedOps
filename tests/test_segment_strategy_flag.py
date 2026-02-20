from feedops.pipeline.segment_strategy import (
    DEFAULT_STRATEGY,
    resolve_segment_strategy,
)


def test_resolve_segment_strategy_returns_default_when_flag_disabled():
    strategy = resolve_segment_strategy(["towel bars"], enabled=False)
    assert strategy.id == DEFAULT_STRATEGY.id


def test_resolve_segment_strategy_uses_label_mapping_when_flag_enabled():
    strategy = resolve_segment_strategy(["towel bars"], enabled=True)
    assert strategy.id == "segment_towel_bars"
