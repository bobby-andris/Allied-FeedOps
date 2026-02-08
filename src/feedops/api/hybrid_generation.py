"""
Hybrid Content Generation for Multi-SKU Products

Adapts content from a base SKU for variant SKUs with focused prompting.
Maintains brand consistency while updating key specification differences.

Python port of dashboard/src/lib/regeneration/core.ts (adaptVariantContent)
"""

import openai
from datetime import datetime, timezone
import json
import hashlib
import logging
import os

logger = logging.getLogger(__name__)


def build_variant_adaptation_prompt(
    content_type: str,
    platform: str,
    base_sku: str,
    variant_sku: str,
    base_content: str,
    base_spec: str,
    variant_spec: str,
) -> tuple[str, bool]:
    """
    Build adaptation prompt for variant content generation.

    Args:
        content_type: "title" or "description"
        platform: "google", "bing", or "shopify"
        base_sku: Base SKU name
        variant_sku: Variant SKU name
        base_content: Content from base SKU to adapt
        base_spec: Specification from base SKU (e.g., "2X")
        variant_spec: Specification for variant (e.g., "5X")

    Returns:
        Tuple of (prompt, requires_json)
    """
    is_variant_description = content_type == "description" and platform in [
        "google",
        "bing",
    ]

    if is_variant_description:
        prompt = f"""You are adapting product content for a variant specification. You MUST respond with valid JSON.

BASE PRODUCT: {base_sku}
BASE CONTENT:
{base_content}

TARGET PRODUCT: {variant_sku}
KEY DIFFERENCE: Specification changes from {base_spec} to {variant_spec}

TASK:
1. Adapt the description for the {variant_spec} specification
2. Update numeric specs and measurements ({base_spec} → {variant_spec})
3. Adjust use case emphasis based on the specification difference
4. Maintain the SAME brand voice, structure, and key selling points
5. Keep similar length and format
6. Generate finish_sentences for all 28 finishes relating to THIS variant

CRITICAL:
- This is a specification variant of the same product family
- Maintain consistency with the base content's storytelling and tone
- Focus only on meaningful differences (specs, use cases)
- Do NOT reinvent the entire description - adapt strategically

Respond with this EXACT JSON structure (no markdown, no code blocks):
{{
  "content": "The adapted description for {variant_spec}...",
  "finish_sentences": {{
    "Antique Brass": "One sentence relating Antique Brass to this {variant_spec} product...",
    "Antique Copper": "One sentence...",
    "Antique Pewter": "One sentence...",
    "Antique Silver": "One sentence...",
    "Bright Brass": "One sentence...",
    "Brushed Bronze": "One sentence...",
    "Brushed Nickel": "One sentence...",
    "Brushed Pewter": "One sentence...",
    "Chrome": "One sentence...",
    "Matte Black": "One sentence...",
    "Matte White": "One sentence...",
    "Oil Rubbed Bronze": "One sentence...",
    "Polished Brass": "One sentence...",
    "Polished Chrome": "One sentence...",
    "Polished Nickel": "One sentence...",
    "Satin Brass": "One sentence...",
    "Satin Chrome": "One sentence...",
    "Satin Nickel": "One sentence...",
    "Unlacquered Brass": "One sentence...",
    "Venetian Bronze": "One sentence...",
    "Weathered Iron": "One sentence...",
    "French Gold": "One sentence...",
    "Polished Gold": "One sentence...",
    "Satin Gold": "One sentence...",
    "Polished Copper": "One sentence...",
    "Rustic Bronze": "One sentence...",
    "Graphite Nickel": "One sentence...",
    "Matte Nickel": "One sentence..."
  }}
}}"""
        return prompt, True

    # For titles
    prompt = f"""You are adapting a product title for a variant specification.

BASE PRODUCT: {base_sku}
BASE TITLE: {base_content}

TARGET PRODUCT: {variant_sku}
KEY DIFFERENCE: Specification changes from {base_spec} to {variant_spec}

TASK:
Adapt the title for the {variant_spec} specification. Update the spec reference ({base_spec} → {variant_spec}) while maintaining the same structure and format.

CRITICAL RULES:
- For Google/Bing titles: Use {{FINISH_NAME}} placeholder at the START, update spec to {variant_spec}
- For Shopify titles: Update spec to {variant_spec}, keep same structure as base
- Maintain the SAME collection name, product name, and format
- ONLY change the specification number/identifier

Respond with ONLY the adapted title text."""
    return prompt, False


async def adapt_variant_content(
    supabase,
    base_sku: str,
    variant_sku: str,
    platform: str,
    content_type: str,
    base_spec: str,
    variant_spec: str,
) -> dict:
    """
    Adapt content from base SKU for variant SKU.

    Args:
        supabase: Supabase client instance
        base_sku: Base SKU to adapt from
        variant_sku: Variant SKU to generate for
        platform: "google", "bing", or "shopify"
        content_type: "title" or "description"
        base_spec: Base specification (e.g., "2X")
        variant_spec: Variant specification (e.g., "5X")

    Returns:
        Dict with success status and content/error
    """
    try:
        # Get base content
        base_result = (
            supabase.table("generated_content")
            .select("candidate_content, approved_content")
            .eq("master_sku", base_sku)
            .eq("platform", platform)
            .eq("content_type", content_type)
            .maybeSingle()
            .execute()
        )

        if not base_result.data:
            return {
                "success": False,
                "error": f"No base content found for {base_sku}/{platform}/{content_type}",
            }

        base_content = base_result.data.get("approved_content") or base_result.data.get(
            "candidate_content"
        )
        if not base_content:
            return {
                "success": False,
                "error": f"Base content is empty for {base_sku}/{platform}/{content_type}",
            }

        # Get current content for version tracking
        current_result = (
            supabase.table("generated_content")
            .select("*")
            .eq("master_sku", variant_sku)
            .eq("platform", platform)
            .eq("content_type", content_type)
            .maybeSingle()
            .execute()
        )

        # Build prompt
        system_prompt = "You are a product content specialist adapting content for product specification variants. Your goal is to maintain brand consistency while updating key specification differences."

        user_prompt, requires_json = build_variant_adaptation_prompt(
            content_type,
            platform,
            base_sku,
            variant_sku,
            base_content,
            base_spec,
            variant_spec,
        )

        prompt_hash = hashlib.sha256(
            f"{system_prompt}\n\n{user_prompt}".encode()
        ).hexdigest()

        # Call OpenAI
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_MODEL", "gpt-4o")

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,  # Lower than full generation (0.7)
            max_completion_tokens=(
                4000
                if requires_json
                else (200 if content_type == "title" else 1000)
            ),
            **({"response_format": {"type": "json_object"}} if requires_json else {}),
        )

        raw_response = completion.choices[0].message.content.strip()

        # Parse response
        finish_sentences = None
        if requires_json:
            try:
                parsed = json.loads(raw_response)
                new_content = parsed.get("content", "").strip()
                finish_sentences = parsed.get("finish_sentences")

                if not new_content:
                    return {
                        "success": False,
                        "error": "Invalid JSON response: missing content field",
                    }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                new_content = raw_response
        else:
            new_content = raw_response

        # Save to database
        current_version = current_result.data["version"] if current_result.data else 0
        next_version = current_version + 1

        if current_result.data:
            supabase.table("generated_content").update(
                {
                    "candidate_content": new_content,
                    "version": next_version,
                    "is_current": True,
                    "generation_model": f"{model}-variant-adaptation",
                    "generation_prompt_hash": prompt_hash,
                    "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", current_result.data["id"]).execute()
        else:
            supabase.table("generated_content").insert(
                {
                    "master_sku": variant_sku,
                    "platform": platform,
                    "content_type": content_type,
                    "candidate_content": new_content,
                    "version": 1,
                    "is_current": True,
                    "generation_model": f"{model}-variant-adaptation",
                    "generation_prompt_hash": prompt_hash,
                    "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()

        # Save to regeneration_history
        content_id_result = (
            supabase.table("generated_content")
            .select("id")
            .eq("master_sku", variant_sku)
            .eq("platform", platform)
            .eq("content_type", content_type)
            .single()
            .execute()
        )

        supabase.table("regeneration_history").insert(
            {
                "generated_content_id": content_id_result.data["id"],
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "model_version": model,
                "prompt_hash": prompt_hash,
                "mode": "variant-adaptation",
            }
        ).execute()

        # Save finish_sentences if present (for descriptions)
        if finish_sentences and platform in ["google", "bing"]:
            for finish_name, sentence in finish_sentences.items():
                supabase.table("variant_finish_sentences").upsert(
                    {
                        "master_sku": variant_sku,
                        "finish_name": finish_name,
                        "platform": platform,
                        "finish_sentence": sentence,
                    },
                    on_conflict="master_sku,finish_name,platform",
                ).execute()

        return {"success": True, "content": new_content}

    except Exception as e:
        logger.error(f"Variant adaptation failed for {variant_sku}: {e}")
        return {"success": False, "error": str(e)}
