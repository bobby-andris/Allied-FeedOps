# FeedOps Dashboard Enhancement Prompts

These prompts are designed for separate Cursor chat sessions, each focused on a single task. Copy the entire contents of a prompt file into a new Cursor chat to implement that feature.

## Priority Order

### P0 - Critical Path (Needed for Basic Workflow)

| #   | Task                      | File                          | Description                                             |
| --- | ------------------------- | ----------------------------- | ------------------------------------------------------- |
| 1   | **Performance Dashboard** | `01-performance-dashboard.md` | Connect Google Ads API to show real performance metrics |
| 2   | **Batch Management**      | `02-batch-management.md`      | Enable creating/managing publish batches from dashboard |

### P1 - Core Functionality

| #   | Task                           | File                              | Description                                              |
| --- | ------------------------------ | --------------------------------- | -------------------------------------------------------- |
| 3   | **Publishing Integration**     | `03-publishing-integration.md`    | Publish approved content to GMC, Shopify, Bing           |
| 4   | **Variant Review**             | `04-variant-review-support.md`    | Per-finish approval and content display                  |
| 5   | **SKU Selection & Generation** | `08-sku-selection-generation.md`  | Strategic SKU selection + content generation wizard      |

### P2 - Quality of Life

| #   | Task                       | File                         | Description                                   |
| --- | -------------------------- | ---------------------------- | --------------------------------------------- |
| 6   | **Settings Health Checks** | `05-settings-api-health.md`  | Real API connectivity status on Settings page |
| 7   | **Content Regeneration**   | `06-content-regeneration.md` | Regenerate titles/descriptions from dashboard |
| 8   | **Dashboard Overview**     | `07-dashboard-overview.md`   | Charts, insights, and enhanced stats          |

## How to Use These Prompts

1. **Start a new Cursor chat** (Cmd+L or Ctrl+L)
2. **Copy the entire contents** of the prompt file
3. **Paste into the chat** and send
4. The agent will have all context needed to implement the feature
5. **Test the implementation** before moving to the next prompt
6. **Commit changes** between prompts for clean git history

## Common Context (All Prompts Need This)

The prompts reference these key files and concepts:

### Project Structure

```
/dashboard/                 # Next.js 14 App Router project
  /src/app/                # Pages and API routes
    /(dashboard)/          # Protected routes (require auth)
    /api/                  # API routes
  /src/components/         # React components
  /src/lib/               # Utilities, Supabase client
```

### Key Files

- `CLAUDE.md` - Project overview, database schema, API keys
- `.env.vercel` - All environment variables for Vercel
- `dashboard/src/lib/supabase/server.ts` - Server-side Supabase client
- `dashboard/src/lib/supabase/client.ts` - Client-side Supabase client

### Supabase Tables

- `generated_content` - Titles and descriptions
- `generated_images` - Lifestyle images
- `sku_approvals` - Master SKU approval status
- `variant_approvals` - Per-finish approval status
- `variant_index` - GMC offer ID to SKU mapping
- `publish_batches` - Batch management
- `batch_sku_assignments` - SKU to batch mapping
- `publish_events` - Audit log
- `performance_baselines` - Pre-optimization metrics
- `performance_snapshots` - Post-publish metrics

### Environment Variables (All in Vercel)

- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GOOGLE_ADS_*` (6 variables)
- `GOOGLE_SERVICE_ACCOUNT_KEY` (base64)
- `SHOPIFY_*` (4 variables)
- `GMC_*` and `GOOGLE_SHEETS_SPREADSHEET_ID`
- `OPENAI_API_KEY`, `GEMINI_API_KEY`

## Deployment

The dashboard auto-deploys to Vercel from the `master` branch:

- **Production**: https://allied-feedops-nqhv5z5vpypgcikbr8hhzy.streamlit.app/ (Streamlit - old)
- **New Dashboard**: Check Vercel for latest deployment URL

## After Implementation

After completing each prompt:

1. Test locally: `cd dashboard && npm run dev`
2. Test on Vercel preview deployment
3. Commit with descriptive message
4. Push to GitHub
5. Verify Vercel production deployment

## Notes

- Each prompt is self-contained with all necessary context
- Prompts reference existing code patterns from the repo
- Always test API routes with real data before marking complete
- Check Vercel logs if deployments fail
