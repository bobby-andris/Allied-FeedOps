# Task: Implement Content Regeneration from Dashboard

## Objective

Add the ability to regenerate titles, descriptions, or images directly from the dashboard review page with two modes:

1. **Simple Regeneration** - Re-run generation with same prompts (for testing model updates)
2. **Feedback-Based Regeneration** - Include specific feedback to guide improvements

## Current State

- Content is generated via Python CLI (`feedops optimize`)
- Dashboard can view and approve content
- No way to request regeneration from the dashboard UI

## Files to Create

1. `dashboard/src/app/api/regenerate/route.ts` - Regeneration API
2. `dashboard/src/components/review/RegenerateButton.tsx` - NEW component
3. `dashboard/src/components/review/RegenerateModal.tsx` - NEW modal with options
4. `dashboard/src/components/review/FeedbackInput.tsx` - NEW feedback UI component

## Requirements

### 1. Regenerate API (`/api/regenerate`)

```typescript
POST /api/regenerate
{
  master_sku: string,
  content_type: 'title' | 'description' | 'image' | 'all',
  platform: 'google' | 'bing' | 'shopify' | 'all',

  // Regeneration mode
  mode: 'simple' | 'with_feedback',

  // For 'with_feedback' mode
  feedback?: {
    current_content: string,      // The content being improved
    user_feedback: string,        // What to change (free text)
    feedback_type?: 'shorter' | 'longer' | 'more_specific' | 'different_angle' | 'custom'
  },

  options?: {
    num_candidates?: number,      // How many variations to generate
    preserve_baseline?: boolean   // Keep original baseline for comparison
  }
}

Response:
{
  job_id: string,
  status: 'queued' | 'processing' | 'completed' | 'failed',
  estimated_time: number, // seconds
  mode: 'simple' | 'with_feedback'
}
```

### 2. Regeneration Modes Explained

**Simple Regeneration (`mode: 'simple'`)**

- Re-runs the exact same generation process with the same prompts
- Useful when: Backend model has been updated and user wants to test new output
- No feedback is sent - just product data + standard prompt templates
- UI: Single "Regenerate" button click

**Feedback-Based Regeneration (`mode: 'with_feedback'`)**

- Sends the current content + user feedback to the LLM
- LLM is instructed to improve the content based on feedback
- Useful when: User sees specific issues they want fixed
- UI: Feedback textarea + "Regenerate with Feedback" button

### 3. Implementation Options

**Option A: Direct LLM Calls (Recommended for MVP)**

- Call OpenAI/Gemini APIs directly from Next.js
- Generate content and save to Supabase
- Synchronous for titles/descriptions, async for images

**Option B: Job Queue (Production-Ready)**

- Create `generation_jobs` table in Supabase
- Poll for job status
- Background worker processes jobs

### 4. Implementation Logic

```typescript
// /api/regenerate/route.ts

export async function POST(request: Request) {
  const { master_sku, content_type, platform, mode, feedback, options } =
    await request.json();

  // Get product data from Supabase or catalog
  const productData = await getProductData(master_sku);

  // Get current content (needed for feedback mode)
  const currentContent = await getCurrentContent(
    master_sku,
    content_type,
    platform
  );

  let prompt: string;

  if (mode === "simple") {
    // Use standard generation prompt (same as initial generation)
    prompt = buildStandardPrompt(content_type, productData);
  } else if (mode === "with_feedback") {
    // Use improvement prompt with current content + feedback
    prompt = buildFeedbackPrompt(
      content_type,
      productData,
      currentContent,
      feedback
    );
  }

  // Call LLM
  const newContent = await generateWithOpenAI(
    prompt,
    options?.num_candidates || 1
  );

  // Save new content (mark as current, demote previous version)
  await saveNewContent(
    master_sku,
    content_type,
    platform,
    newContent,
    currentContent
  );

  // Log regeneration history
  await logRegeneration({
    master_sku,
    content_type,
    platform,
    mode,
    feedback_text: feedback?.user_feedback,
    feedback_preset: feedback?.feedback_type,
    previous_content: currentContent,
    new_content: newContent,
    model_version: "gpt-5.2",
  });

  return Response.json({ success: true, content: newContent });
}
```

### 5. LLM Integration

Use environment variables:

```
OPENAI_API_KEY - For GPT-5.2 (titles/descriptions)
GEMINI_API_KEY - For image generation
```

#### Simple Regeneration Prompts

**Title Generation Prompt** (from AGENTS.md):

```
Generate an optimized product title for Google Shopping.
- Max 150 characters
- Front-load critical info in first 70 characters
- Include: Product Type, Key Dimension, Variant Differentiator
- Brand at end (Allied Brass)
- No promotional text or ALL CAPS

Product: [product_name]
Category: [category]
Dimensions: [dimensions]
Material: [material]
Finish: [finish]
```

**Description Generation Prompt**:

```
Generate an optimized product description for Google Shopping.
- Start with benefit-focused hook (first 150 chars critical)
- Include 3-5 bullet points
- Minimum 500 characters recommended
- Specific, verifiable claims only
- Address: fit, durability, installation, decor matching

Product: [product_name]
Features: [features]
Material: [material]
Dimensions: [dimensions]
```

#### Feedback-Based Regeneration Prompts

**Title Improvement Prompt**:

```
You are improving a product title for Google Shopping based on reviewer feedback.

CURRENT TITLE:
[current_title]

REVIEWER FEEDBACK:
[user_feedback]

PRODUCT DATA:
- Product: [product_name]
- Category: [category]
- Dimensions: [dimensions]
- Material: [material]
- Finish: [finish]

REQUIREMENTS:
- Max 150 characters
- Front-load critical info in first 70 characters
- Include: Product Type, Key Dimension, Variant Differentiator
- Brand at end (Allied Brass)
- No promotional text or ALL CAPS

Generate an improved title that addresses the feedback while following all requirements.
```

**Description Improvement Prompt**:

```
You are improving a product description for Google Shopping based on reviewer feedback.

CURRENT DESCRIPTION:
[current_description]

REVIEWER FEEDBACK:
[user_feedback]

PRODUCT DATA:
- Product: [product_name]
- Features: [features]
- Material: [material]
- Dimensions: [dimensions]

REQUIREMENTS:
- Start with benefit-focused hook (first 150 chars critical)
- Include 3-5 bullet points
- Minimum 500 characters recommended
- Specific, verifiable claims only
- Address: fit, durability, installation, decor matching

Generate an improved description that addresses the feedback while following all requirements.
```

#### Feedback Type Presets

Provide quick-select feedback options:

```typescript
const FEEDBACK_PRESETS = {
  shorter: "Make this shorter and more concise while keeping key information",
  longer: "Expand this with more detail and product benefits",
  more_specific: "Replace vague claims with specific, verifiable details",
  different_angle:
    "Take a different approach - emphasize different benefits or features",
  more_keywords: "Include more relevant search keywords naturally",
  less_promotional: "Remove promotional language, make it more factual",
  better_hook: "Improve the opening to be more compelling",
};
```

### 6. UI Components

**RegenerateButton** - Dropdown button next to content with two options:

```tsx
<RegenerateDropdown
  sku="1051"
  contentType="title"
  platform="google"
  currentContent={title.candidate_content}
>
  <DropdownMenuItem onClick={handleSimpleRegenerate}>
    <RefreshCw className="h-4 w-4 mr-2" />
    Regenerate
    <span className="text-xs text-muted-foreground ml-2">Same prompt</span>
  </DropdownMenuItem>
  <DropdownMenuItem onClick={openFeedbackModal}>
    <MessageSquare className="h-4 w-4 mr-2" />
    Regenerate with Feedback
  </DropdownMenuItem>
</RegenerateDropdown>
```

**RegenerateModal** - Options dialog for simple regeneration:

- Content type selector (title, description, image, all)
- Platform selector (if regenerating for specific platform)
- Number of candidates (1-5)
- "Regenerate" button

**FeedbackModal** - Dialog for feedback-based regeneration:

```tsx
<Dialog>
  <DialogHeader>
    <DialogTitle>Improve {contentType}</DialogTitle>
    <DialogDescription>Provide feedback on what to change</DialogDescription>
  </DialogHeader>

  <DialogContent>
    {/* Show current content for reference */}
    <div className="bg-muted p-4 rounded-lg mb-4">
      <Label className="text-sm text-muted-foreground">
        Current {contentType}:
      </Label>
      <p className="mt-1">{currentContent}</p>
    </div>

    {/* Quick feedback presets */}
    <div className="flex flex-wrap gap-2 mb-4">
      <Button
        variant="outline"
        size="sm"
        onClick={() => setFeedback(PRESETS.shorter)}
      >
        Make Shorter
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setFeedback(PRESETS.longer)}
      >
        Add More Detail
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setFeedback(PRESETS.more_specific)}
      >
        More Specific
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setFeedback(PRESETS.different_angle)}
      >
        Different Angle
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setFeedback(PRESETS.better_hook)}
      >
        Better Hook
      </Button>
    </div>

    {/* Custom feedback textarea */}
    <div>
      <Label>Your feedback</Label>
      <Textarea
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        placeholder="E.g., 'Emphasize the solid brass construction more' or 'Make the opening more compelling for homeowners'"
        rows={4}
      />
      <p className="text-xs text-muted-foreground mt-1">
        Be specific about what you want changed
      </p>
    </div>
  </DialogContent>

  <DialogFooter>
    <Button variant="outline" onClick={onClose}>
      Cancel
    </Button>
    <Button onClick={handleRegenerateWithFeedback} disabled={!feedback.trim()}>
      <Sparkles className="h-4 w-4 mr-2" />
      Regenerate with Feedback
    </Button>
  </DialogFooter>
</Dialog>
```

**FeedbackInput** - Inline feedback for quick iterations:

```tsx
// For when user wants to quickly iterate without full modal
<div className="mt-2 flex gap-2">
  <Input
    placeholder="What should change?"
    value={quickFeedback}
    onChange={(e) => setQuickFeedback(e.target.value)}
    onKeyDown={(e) => e.key === "Enter" && handleQuickRegenerate()}
  />
  <Button size="sm" onClick={handleQuickRegenerate}>
    <RefreshCw className="h-4 w-4" />
  </Button>
</div>
```

### 7. Generation Flows

#### Flow A: Simple Regeneration (Model Update Testing)

1. User clicks dropdown arrow on "Regenerate" button
2. User selects "Regenerate" (same prompt)
3. Confirmation toast: "Regenerating with latest model..."
4. API called with `mode: 'simple'`
5. Loading spinner shows on content card
6. New content saved to `generated_content`
7. Page refreshes to show new content
8. Toast: "Title regenerated successfully"

#### Flow B: Feedback-Based Regeneration

1. User clicks dropdown arrow on "Regenerate" button
2. User selects "Regenerate with Feedback"
3. Modal opens showing:
   - Current content (for reference)
   - Quick preset buttons
   - Custom feedback textarea
4. User enters feedback (required)
5. User clicks "Regenerate with Feedback"
6. API called with `mode: 'with_feedback'` + feedback payload
7. Loading spinner shows
8. New content saved with feedback logged
9. Page refreshes to show new content
10. Previous content still visible for comparison

### 8. Image Regeneration (If Applicable)

For lifestyle images:

- Use Gemini Imagen API
- Store in Supabase Storage or keep using GitHub
- Generate multiple variations (3-5)
- Save to `generated_images` table

### 9. Preserve History & Track Feedback

Keep previous generations and log all feedback:

```sql
-- Add versioning to generated_content
ALTER TABLE generated_content ADD COLUMN version integer DEFAULT 1;
ALTER TABLE generated_content ADD COLUMN is_current boolean DEFAULT true;

-- New table to track regeneration history with feedback
CREATE TABLE regeneration_history (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku text NOT NULL,
  content_type text NOT NULL, -- 'title', 'description', 'image'
  platform text NOT NULL,

  -- Regeneration details
  mode text NOT NULL, -- 'simple', 'with_feedback'
  feedback_text text, -- User's feedback (null for simple mode)
  feedback_preset text, -- Which preset was used, if any

  -- Content snapshots
  previous_content text,
  new_content text,

  -- Metadata
  model_version text, -- Track which model was used
  created_at timestamptz DEFAULT now(),
  created_by text
);
```

**UI for viewing history:**

```tsx
// Collapsible section on SKU detail page
<Collapsible>
  <CollapsibleTrigger>
    <History className="h-4 w-4 mr-2" />
    Regeneration History ({historyCount})
  </CollapsibleTrigger>
  <CollapsibleContent>
    {history.map((entry) => (
      <div key={entry.id} className="border-l-2 pl-4 py-2">
        <div className="flex justify-between text-sm">
          <span className="font-medium">
            {entry.mode === "simple" ? "Simple regeneration" : "With feedback"}
          </span>
          <span className="text-muted-foreground">
            {formatDate(entry.created_at)}
          </span>
        </div>
        {entry.feedback_text && (
          <p className="text-sm text-muted-foreground mt-1">
            Feedback: "{entry.feedback_text}"
          </p>
        )}
      </div>
    ))}
  </CollapsibleContent>
</Collapsible>
```

### 10. Revert to Previous Version

Allow users to revert if new generation is worse:

```tsx
<Button
  variant="outline"
  size="sm"
  onClick={() => revertToVersion(previousVersion)}
>
  <Undo className="h-4 w-4 mr-2" />
  Revert to Previous
</Button>
```

## Reference Files

- `src/feedops/pipeline/content_generator.py` - Python generation logic
- `src/feedops/pipeline/prompt_builder.py` - Prompt templates
- `src/feedops/pipeline/lifestyle_images.py` - Image generation
- `AGENTS.md` - Title/description rules and guidelines

## Success Criteria

1. **Simple Regeneration**:
   - Can regenerate title/description with one click
   - Uses same prompts as original generation
   - Useful for testing model updates
2. **Feedback-Based Regeneration**:
   - Can provide specific feedback on what to change
   - Preset buttons for common feedback types
   - Custom feedback textarea for detailed instructions
   - Feedback is sent to LLM along with current content
3. **History & Comparison**:

   - All regenerations are logged with feedback
   - Can view regeneration history per SKU
   - Can compare current vs previous versions
   - Can revert to previous version if needed

4. **General**:
   - New content appears in review page after regeneration
   - Loading states show during generation
   - Error handling for API failures
   - Works on Vercel deployment

## Notes

- OpenAI calls are relatively fast (2-5 seconds for text)
- Image generation is slower (30-60 seconds)
- Consider rate limiting to prevent abuse
- May need to increase Vercel function timeout for images
- Track model version used for each generation (helps debug quality changes)
- Feedback history is valuable for improving prompts over time
