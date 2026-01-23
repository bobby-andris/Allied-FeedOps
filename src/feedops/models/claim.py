"""Claim model for tracking content claims and their sources."""
from pydantic import BaseModel


class Claim(BaseModel):
    """A factual claim in generated content with source attribution.

    Claims must be verified against source data before publication.
    Any claim without a valid source_field or mismatched source_value
    is considered unverified and should be rejected.
    """

    claim: str
    """The claim text as it appears in generated content."""

    source_field: str
    """The field name in ParentSKU/Variant this claim is based on."""

    source_value: str
    """The value from the source field that supports this claim."""

    verified: bool = False
    """Whether this claim has been verified against actual source data."""

    rejection_reason: str | None = None
    """If verified=False after verification, explains why."""
