from feedops.pipeline.generator import parse_candidate_response


def test_parse_candidate_response_normalizes_pipes_and_trims() -> None:
    response = {
        "google_title": "Paper Towel Holder, Brass Paper Towel Holders Collection, | Allied Brass",
        "google_short_title": "Towel Bar 30-Inch | Allied Brass",
        "google_description": "X" * 600,
        "bing_title": "Paper Towel Holder, Brass Paper Towel Holders Collection, | Allied Brass",
        "bing_description": "Y" * 600,
        "shopify_title": "Paper Towel Holder, Brass Paper Towel Holders Collection, | Allied Brass",
        "shopify_description": "<p>Desc</p>",
        "claims": [],
        "self_score": {
            "specificity": 8,
            "benefit_coverage": 8,
            "keyword_inclusion": 8,
            "format_adherence": 8,
            "brand_voice": 8,
            "factual_accuracy": 9,
        },
    }

    candidate = parse_candidate_response(response)

    assert "|" not in candidate.google_title
    assert candidate.google_title.endswith("Allied Brass")
    assert ", ," not in candidate.google_title
    assert candidate.google_title == "Paper Towel Holder, Allied Brass"

    assert len(candidate.google_title) <= 150
    assert len(candidate.bing_title) <= 150
    assert len(candidate.google_short_title) <= 70
