import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'
import OpenAI from 'openai'
import { FeedbackPreset } from '@/lib/supabase/types'

// Initialize OpenAI client
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
})

// Model to use for generation
const MODEL = process.env.FEEDOPS_OPENAI_MODEL || 'gpt-4o'

// Feedback preset descriptions
const FEEDBACK_PRESETS: Record<FeedbackPreset, string> = {
  shorter: 'Make this shorter and more concise while keeping key information',
  longer: 'Expand this with more detail and product benefits',
  more_specific: 'Replace vague claims with specific, verifiable details',
  different_angle: 'Take a different approach - emphasize different benefits or features',
  more_keywords: 'Include more relevant search keywords naturally',
  less_promotional: 'Remove promotional language, make it more factual',
  better_hook: 'Improve the opening to be more compelling',
}

interface RegenerateRequest {
  master_sku: string
  content_type: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
  mode: 'simple' | 'with_feedback'
  feedback?: {
    current_content: string
    user_feedback: string
    feedback_type?: FeedbackPreset
  }
  options?: {
    num_candidates?: number
  }
}

// Context-driven system prompt (matches Python backend philosophy)
const SYSTEM_PROMPT = `You are a product content writer for Allied Brass bathroom and kitchen hardware.
Create content that helps buyers understand why this product is worth it.

BEFORE YOU WRITE, THINK ABOUT WHO IS READING THIS:

1. WHO IS SEARCHING FOR THIS PRODUCT?
- A homeowner renovating a bathroom who wants it to look intentional, not like an afterthought
- A designer specifying fixtures for a client who expects quality
- Someone replacing a broken/ugly product who wants an upgrade, not just a replacement

2. WHAT QUESTIONS DO THEY HAVE BEFORE SPENDING $80+?
- "Will this look good in MY bathroom?" → Help them visualize it
- "Will this match my other fixtures?" → Address finish coordination
- "Is this actually better than the $20 Amazon option?" → Explain the value
- "Will this last? Is it quality?" → Provide trust signals (material, warranty)

3. WHAT MAKES ALLIED BRASS WORTH IT?
- Style without sacrifice: You don't have to choose between "looks good" and "works well"
- Personalization: 28 finishes to match any bathroom vision
- Innovation: Rollerless TP holders, retractable rods, decorative grab bars, ventilated baskets
- Durability: Solid brass outlasts plastic and die-cast that crack and corrode
- Coordination: Match everything across 42+ collections

PLATFORM CONTEXT:
- Google/Bing (variant): One specific finish. This is the customer's FIRST impression. Make them want to click.
- Shopify (master): All finishes on one page. Customer already clicked. Help them choose and buy.

CRITICAL RULES:
- Never invent specifications not in the product data
- Every factual claim must be traceable to the provided data
- "Allied Brass" should be the final segment in titles
- No ALL CAPS, no promotional language like "Premium", "Luxury", "Best"
- Write for a human who's about to spend $80 and wants to feel good about it`

function buildSimplePrompt(
  contentType: 'title' | 'description',
  platform: string,
  productData: Record<string, unknown>
): string {
  const platformContext = {
    google: {
      title: 'Google Shopping title - this is their first impression. Make them want to click. Include product type, key dimension, and "Allied Brass" at end.',
      description: 'Google Shopping description - write for a human scanning Shopping ads. Answer their questions about this product. Weave the finish naturally. Plain text only.',
    },
    bing: {
      title: 'Bing Shopping title - include natural product synonyms. Make them want to click. Include "Allied Brass" at end.',
      description: 'Bing Shopping description - write for humans, include product synonyms naturally (e.g., towel bar/rack, shower basket/caddy). Plain text only.',
    },
    shopify: {
      title: 'Shopify product title (H1) - customer already clicked. Help them feel confident about buying.',
      description: 'Shopify description - customer already clicked, now convince them to add to cart. Open with their problem or desired outcome. Mention 28 finishes as a benefit. HTML format with <p> and <ul><li> bullets.',
    },
  }

  const context = platformContext[platform as keyof typeof platformContext]?.[contentType] || ''

  return `Generate a ${contentType} for this product.

CONTEXT: ${context}

PRODUCT DATA:
${JSON.stringify(productData, null, 2)}

Remember: Write for a human who's about to spend $80 and wants to feel good about it.

Respond with ONLY the ${contentType} text, no additional explanation or formatting.`
}

function buildFeedbackPrompt(
  contentType: 'title' | 'description',
  platform: string,
  productData: Record<string, unknown>,
  currentContent: string,
  feedback: string
): string {
  const platformContext = {
    google: 'Google Shopping - first impression, make them want to click',
    bing: 'Bing Shopping - include natural product synonyms',
    shopify: 'Shopify - customer already clicked, convince them to buy',
  }

  const context = platformContext[platform as keyof typeof platformContext] || platform

  return `You are improving a product ${contentType} based on reviewer feedback.

PLATFORM: ${context}

CURRENT ${contentType.toUpperCase()}:
${currentContent}

REVIEWER FEEDBACK:
${feedback}

PRODUCT DATA:
${JSON.stringify(productData, null, 2)}

Remember the buyer questions you're answering:
- "Will this look good in MY bathroom?"
- "Will this match my other fixtures?"
- "Is this actually better than the $20 Amazon option?"
- "Will this last? Is it quality?"

Generate an improved ${contentType} that addresses the feedback while answering these buyer questions.

Respond with ONLY the improved ${contentType} text, no additional explanation or formatting.`
}

export async function POST(request: NextRequest) {
  try {
    // Validate OpenAI API key
    if (!process.env.OPENAI_API_KEY) {
      return NextResponse.json(
        { error: 'OpenAI API key not configured' },
        { status: 500 }
      )
    }

    const body: RegenerateRequest = await request.json()
    const { master_sku, content_type, platform, mode, feedback, options } = body

    // Validate required fields
    if (!master_sku || !content_type || !platform || !mode) {
      return NextResponse.json(
        { error: 'Missing required fields: master_sku, content_type, platform, mode' },
        { status: 400 }
      )
    }

    if (mode === 'with_feedback' && (!feedback?.user_feedback || !feedback?.current_content)) {
      return NextResponse.json(
        { error: 'Feedback mode requires feedback.user_feedback and feedback.current_content' },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    // Get product data from variant_index
    const { data: variantData, error: variantError } = await supabase
      .from('variant_index')
      .select('*')
      .eq('master_sku', master_sku)
      .limit(1)
      .single()

    if (variantError && variantError.code !== 'PGRST116') {
      console.error('Failed to fetch variant data:', variantError)
    }

    // Get current content for comparison (needed for history logging)
    const { data: currentContentData } = await supabase
      .from('generated_content')
      .select('*')
      .eq('master_sku', master_sku)
      .eq('platform', platform)
      .eq('content_type', content_type)
      .eq('is_current', true)
      .single()

    // Build product data object for prompt
    const productData = {
      master_sku,
      product_title: variantData?.product_title || master_sku,
      product_category: variantData?.product_category || 'Bathroom Hardware',
      finish: variantData?.finish,
      finish_code: variantData?.finish_code,
      dimensions: variantData?.dimensions,
    }

    // Build prompt based on mode
    let userPrompt: string
    if (mode === 'simple') {
      userPrompt = buildSimplePrompt(content_type, platform, productData)
    } else {
      // Combine preset + custom feedback
      const feedbackText = feedback!.feedback_type
        ? `${FEEDBACK_PRESETS[feedback!.feedback_type]}. ${feedback!.user_feedback}`
        : feedback!.user_feedback
      
      userPrompt = buildFeedbackPrompt(
        content_type,
        platform,
        productData,
        feedback!.current_content,
        feedbackText
      )
    }

    // Call OpenAI
    const completion = await openai.chat.completions.create({
      model: MODEL,
      messages: [
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content: userPrompt },
      ],
      temperature: 0.7,
      max_tokens: content_type === 'title' ? 200 : 1000,
    })

    const newContent = completion.choices[0]?.message?.content?.trim()

    if (!newContent) {
      return NextResponse.json(
        { error: 'No content generated from OpenAI' },
        { status: 500 }
      )
    }

    // Get current version number
    const currentVersion = currentContentData?.version || 0

    // Mark current content as not current
    if (currentContentData) {
      await supabase
        .from('generated_content')
        .update({ is_current: false })
        .eq('id', currentContentData.id)
    }

    // Insert or update generated content with new version
    const { data: newContentRecord, error: insertError } = await supabase
      .from('generated_content')
      .upsert({
        master_sku,
        platform,
        content_type,
        candidate_content: newContent,
        baseline_content: currentContentData?.baseline_content,
        version: currentVersion + 1,
        is_current: true,
      }, {
        onConflict: 'master_sku,platform,content_type',
      })
      .select()
      .single()

    if (insertError) {
      console.error('Failed to save generated content:', insertError)
      return NextResponse.json(
        { error: 'Failed to save generated content' },
        { status: 500 }
      )
    }

    // Log to regeneration history
    const { error: historyError } = await supabase
      .from('regeneration_history')
      .insert({
        master_sku,
        content_type,
        platform,
        mode,
        feedback_text: feedback?.user_feedback || null,
        feedback_preset: feedback?.feedback_type || null,
        previous_content: currentContentData?.candidate_content || null,
        new_content: newContent,
        model_version: MODEL,
        quality_score_before: currentContentData?.quality_score || null,
        generated_content_id: newContentRecord?.id,
      })

    if (historyError) {
      console.error('Failed to log regeneration history:', historyError)
      // Don't fail the request, just log the error
    }

    return NextResponse.json({
      success: true,
      content: newContent,
      version: currentVersion + 1,
      mode,
      model: MODEL,
      generated_content_id: newContentRecord?.id,
    })
  } catch (error) {
    console.error('Regeneration error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
