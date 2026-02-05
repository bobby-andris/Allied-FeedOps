-- Migration: 020_prompt_templates
-- Description: Store gold standard examples and prompt templates for unified content generation
-- Created: 2026-02-04

-- Create the prompt_templates table for versioned prompt management
CREATE TABLE IF NOT EXISTS prompt_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Template identification
  name TEXT NOT NULL UNIQUE,
  version INTEGER NOT NULL DEFAULT 1,
  is_active BOOLEAN DEFAULT false,

  -- Core prompt content
  system_prompt TEXT NOT NULL,

  -- Gold standard examples (JSON array of examples)
  -- Each example: {index, category, master_sku, title, collection, style, material,
  --                source_data, gold_standard_content: {google_title, bing_title, shopify_title,
  --                google_description, bing_description, shopify_description, finish_sentences, why_it_works}}
  gold_standard_examples JSONB NOT NULL,

  -- Category-specific guidance (JSON object keyed by category)
  -- E.g., {"Towel Bars": "Focus on...", "Grab Bars": "Safety first..."}
  category_guidance JSONB,

  -- Platform rules (JSON object)
  -- E.g., {"google": {"brand_suffix": "Allied Brass"}, "shopify": {"brand_suffix": null}}
  platform_rules JSONB,

  -- Metadata
  description TEXT,
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Index for active prompt lookup (only one should be active at a time)
CREATE INDEX idx_prompt_templates_active ON prompt_templates(is_active) WHERE is_active = true;

-- Index for version history queries
CREATE INDEX idx_prompt_templates_name_version ON prompt_templates(name, version);

-- Trigger to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_prompt_templates_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prompt_templates_updated_at
  BEFORE UPDATE ON prompt_templates
  FOR EACH ROW
  EXECUTE FUNCTION update_prompt_templates_updated_at();

-- Ensure only one active template at a time per name
CREATE OR REPLACE FUNCTION ensure_single_active_template()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.is_active = true THEN
    -- Deactivate other templates with the same name
    UPDATE prompt_templates
    SET is_active = false
    WHERE name = NEW.name AND id != NEW.id AND is_active = true;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ensure_single_active_template_trigger
  BEFORE INSERT OR UPDATE ON prompt_templates
  FOR EACH ROW
  EXECUTE FUNCTION ensure_single_active_template();

-- Add comments for documentation
COMMENT ON TABLE prompt_templates IS 'Stores versioned prompt templates and gold standard examples for content generation';
COMMENT ON COLUMN prompt_templates.name IS 'Template identifier (e.g., "content-generation-v1")';
COMMENT ON COLUMN prompt_templates.version IS 'Version number for the template';
COMMENT ON COLUMN prompt_templates.is_active IS 'Whether this template is currently active for content generation';
COMMENT ON COLUMN prompt_templates.system_prompt IS 'The system prompt text for the LLM';
COMMENT ON COLUMN prompt_templates.gold_standard_examples IS 'JSON array of 10 gold standard examples for few-shot learning';
COMMENT ON COLUMN prompt_templates.category_guidance IS 'Category-specific instructions (keyed by category name)';
COMMENT ON COLUMN prompt_templates.platform_rules IS 'Platform-specific rules (keyed by platform: google, bing, shopify)';
