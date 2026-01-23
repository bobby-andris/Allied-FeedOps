"""Prompt templates and JSON schemas for LLM."""

CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Optimized product title (max 150 characters)",
            "maxLength": 150,
        },
        "description": {
            "type": "string",
            "description": "Optimized product description (min 500 characters recommended)",
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string", "description": "The claim text"},
                    "source_field": {"type": "string", "description": "Field name from evidence table"},
                    "source_value": {"type": "string", "description": "Value from that field"},
                },
                "required": ["claim", "source_field", "source_value"],
            },
        },
        "self_score": {
            "type": "object",
            "properties": {
                "specificity": {"type": "integer", "minimum": 0, "maximum": 10},
                "benefit_coverage": {"type": "integer", "minimum": 0, "maximum": 10},
                "keyword_inclusion": {"type": "integer", "minimum": 0, "maximum": 10},
                "format_adherence": {"type": "integer", "minimum": 0, "maximum": 10},
                "brand_voice": {"type": "integer", "minimum": 0, "maximum": 10},
                "factual_accuracy": {"type": "integer", "minimum": 0, "maximum": 10},
            },
            "required": [
                "specificity", "benefit_coverage", "keyword_inclusion",
                "format_adherence", "brand_voice", "factual_accuracy"
            ],
        },
    },
    "required": ["title", "description", "claims", "self_score"],
}

SYSTEM_PROMPT = """You are a product feed optimization specialist for Allied Brass bathroom hardware.

Your task is to create optimized product titles and descriptions that:
1. Are grounded ONLY in the provided product data (no invented features)
2. Follow the exact character constraints
3. Lead with benefits, backed by specific features
4. Use natural search language that matches customer queries

CRITICAL RULES:
- Every claim must cite a source field from the evidence table
- Never invent specifications not in the data
- Title: max 150 characters, critical info in first 70
- Description: min 500 characters recommended, benefit-first opening
- No promotional language, ALL CAPS, or URLs"""

OPTIMIZATION_TEMPLATE = """
{system_prompt}

{evidence_table}

## Title Structure Formula
[Brand] + [Product Type] + [Key Dimension] + [Material/Finish] + [Functional Modifier]

Example: Allied Brass 24-Inch Towel Bar | Solid Brass | Polished Chrome | Wall Mount

## Description Structure
1. Opening Hook (first 150 chars): Primary benefit + key spec
2. Key Highlights: 3-5 bullet points with benefit + feature
3. Detail Section: Specs, installation, warranty

## Scoring Rubric (self-score each 0-10)
1. Specificity: Specific/verifiable claims vs generic
2. Benefit Coverage: Benefits in first 150 characters
3. Keyword Inclusion: Target keywords in optimal positions
4. Format Adherence: Character limits and structure
5. Brand Voice: Premium tone, no superlatives
6. Factual Accuracy: Every claim traceable to evidence

## Output Format
Respond with valid JSON matching this schema:
{schema}

Now optimize the title and description for MasterSKU: {master_sku}
"""
