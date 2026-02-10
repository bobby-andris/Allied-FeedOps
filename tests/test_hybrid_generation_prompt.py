from feedops.api.hybrid_generation import build_variant_adaptation_prompt
from feedops.api.prompt_loader import get_finish_list


def test_variant_description_prompt_uses_canonical_finish_list():
    prompt, requires_json = build_variant_adaptation_prompt(
        content_type="description",
        platform="google",
        base_sku="FT-2",
        variant_sku="FT-2/22",
        base_content="Base description",
        base_spec="18-Inch",
        variant_spec="22-Inch",
    )

    assert requires_json is True
    for finish in get_finish_list():
        assert f'"{finish}"' in prompt


def test_variant_description_prompt_does_not_include_legacy_finish_names():
    prompt, _ = build_variant_adaptation_prompt(
        content_type="description",
        platform="google",
        base_sku="FT-2",
        variant_sku="FT-2/22",
        base_content="Base description",
        base_spec="18-Inch",
        variant_spec="22-Inch",
    )

    assert '"Antique Silver"' not in prompt
    assert '"Weathered Iron"' not in prompt
    assert '"French Gold"' not in prompt
