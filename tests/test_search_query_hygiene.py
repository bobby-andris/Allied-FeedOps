from feedops.integrations.search_query_insights import (
    build_relevance_anchor_terms,
    filter_search_queries_by_relevance,
)


def test_filter_search_queries_by_relevance_drops_competitor_noise():
    queries = [
        {"query_text": "wall mount towel bar brass", "total_impressions": 1200},
        {"query_text": "moen towel bar", "total_impressions": 2100},
        {"query_text": "https://example.com", "total_impressions": 500},
        {"query_text": "paper towel holder", "total_impressions": 900},
    ]

    anchors = build_relevance_anchor_terms("Towel Bars", "wall mounted towel bars")
    filtered = filter_search_queries_by_relevance(queries, anchors, min_keep=2)

    texts = [row["query_text"] for row in filtered]
    assert "wall mount towel bar brass" in texts
    assert "moen towel bar" not in texts
    assert "https://example.com" not in texts


def test_filter_search_queries_by_relevance_uses_clean_fallback_when_overlap_sparse():
    queries = [
        {"query_text": "bathroom hardware set", "total_impressions": 800},
        {"query_text": "solid brass towel ring", "total_impressions": 700},
        {"query_text": "allied brass accessories", "total_impressions": 650},
    ]

    anchors = build_relevance_anchor_terms("toilet paper holders")
    filtered = filter_search_queries_by_relevance(queries, anchors, min_keep=2)

    # No strict overlap with anchor, but clean fallbacks should still be preserved.
    assert len(filtered) >= 2
    assert all("http" not in row["query_text"] for row in filtered)

