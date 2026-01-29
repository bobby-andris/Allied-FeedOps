from feedops.dashboard.variant_warnings import summarize_variant_title_warnings


def test_summarize_variant_title_warnings_counts_types():
    patches = [
        {"_meta": {"variant_title_warnings": ["Duplicate variant title detected: 'x'"]}},
        {
            "_meta": {
                "variant_title_warnings": [
                    "Finish 'Satin Nickel' appears after the first 70 characters; "
                    "consider moving finish earlier for variant differentiation."
                ]
            }
        },
        {"_meta": {}},
    ]
    summary = summarize_variant_title_warnings(patches)
    assert summary["total_patches"] == 3
    assert summary["patches_with_warnings"] == 2
    assert summary["warning_counts"]["duplicate"] == 1
    assert summary["warning_counts"]["finish_after_visible_chars"] == 1

