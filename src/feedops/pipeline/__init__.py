"""FeedOps optimization pipeline."""
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.verifier import verify_claims
from feedops.pipeline.generator import build_prompt, generate_candidate
from feedops.pipeline.prompts import CANDIDATE_SCHEMA
from feedops.pipeline.reporter import generate_report, generate_patch_preview

__all__ = [
    "build_evidence_table",
    "format_evidence_markdown",
    "verify_claims",
    "build_prompt",
    "generate_candidate",
    "CANDIDATE_SCHEMA",
    "generate_report",
    "generate_patch_preview",
]
