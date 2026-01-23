"""Validation utilities for generated candidates."""
import re

from feedops.models import Candidate

CUSTOMER_FIELDS = (
    "google_title",
    "google_short_title",
    "google_description",
    "bing_title",
    "bing_description",
    "shopify_title",
    "shopify_description",
)

PARENTHETICAL_CITATION_PATTERN = re.compile(r"\(catalog_csv\.[^)]+\)")


def validate_candidate_content(candidate: Candidate) -> list[str]:
    """Validate customer-facing fields for citation leakage."""
    errors: list[str] = []

    for field in CUSTOMER_FIELDS:
        value = getattr(candidate, field, "")
        parenthetical_match = PARENTHETICAL_CITATION_PATTERN.search(value)
        if parenthetical_match:
            errors.append(
                f"{field} contains parenthetical source reference {parenthetical_match.group(0)}"
            )
            continue
        if "catalog_csv." in value:
            errors.append(f"{field} contains source citation reference 'catalog_csv.'")

    return errors
