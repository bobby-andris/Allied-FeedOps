# Task: Implement Live Batch Management

## Objective

Replace the hardcoded placeholder data in the Batches page with real Supabase data and implement full CRUD operations for batch management.

## Current State

- Batches list page: `dashboard/src/app/(dashboard)/batches/page.tsx` (hardcoded data)
- Batch detail page: `dashboard/src/app/(dashboard)/batches/[batchId]/page.tsx`
- API route exists: `dashboard/src/app/api/batches/route.ts` (partially implemented)

## Files to Modify/Create

1. `dashboard/src/app/api/batches/route.ts` - Update to fully implement CRUD
2. `dashboard/src/app/(dashboard)/batches/page.tsx` - Fetch real data, add create batch modal
3. `dashboard/src/app/(dashboard)/batches/[batchId]/page.tsx` - Implement detail view
4. `dashboard/src/components/batches/CreateBatchModal.tsx` - NEW component
5. `dashboard/src/components/batches/BatchSkuTable.tsx` - NEW component

## Supabase Tables

### `publish_batches`

```sql
CREATE TABLE publish_batches (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  name text NOT NULL,
  notes text,
  status text DEFAULT 'draft', -- draft, ready, executing, completed, failed
  created_at timestamptz DEFAULT now(),
  executed_at timestamptz,
  created_by text
);
```

### `batch_sku_assignments`

```sql
CREATE TABLE batch_sku_assignments (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  batch_id uuid REFERENCES publish_batches(id),
  master_sku text NOT NULL,
  status text DEFAULT 'pending', -- pending, success, failed
  error_message text,
  created_at timestamptz DEFAULT now()
);
```

### `publish_events`

```sql
CREATE TABLE publish_events (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  batch_id uuid REFERENCES publish_batches(id),
  master_sku text NOT NULL,
  platform text NOT NULL,
  environment text NOT NULL, -- staging, production
  action text NOT NULL, -- publish, rollback
  status text NOT NULL, -- success, failed
  details jsonb,
  created_at timestamptz DEFAULT now()
);
```

## Requirements

### 1. API Route Implementation (`/api/batches`)

**GET** - List all batches with SKU counts

```typescript
// Query publish_batches joined with batch_sku_assignments
// Return: { batches: [...], total: number }
```

**POST** - Create new batch

```typescript
// Body: { name: string, notes?: string, skus?: string[] }
// 1. Create batch in publish_batches
// 2. If skus provided, add to batch_sku_assignments
```

**PATCH** - Update batch

```typescript
// Body: { batch_id: string, status?: string, notes?: string, add_skus?: string[], remove_skus?: string[] }
```

### 2. Batches List Page

- Fetch batches from API on load
- Show stats cards (total, draft, completed, SKUs published)
- Table with all batches
- "Create Batch" button opens modal
- Status badges with colors
- Actions: View, Publish (if draft), Rollback (if completed)

### 3. Create Batch Modal

- Name input (required)
- Notes textarea (optional)
- SKU multi-select (optional) - show approved SKUs not yet in any batch
- Create button

### 4. Batch Detail Page (`/batches/[batchId]`)

- Show batch info (name, status, dates, notes)
- Table of assigned SKUs with their status
- Add SKU button (shows approved SKUs not in this batch)
- Remove SKU button (for draft batches only)
- Publish button (changes status to executing, then calls publish workflow)
- Show publish_events for this batch

### 5. Publishing Workflow (Stretch Goal)

When "Publish" is clicked:

1. Update batch status to 'executing'
2. For each SKU in batch:
   - Call existing Python publishing functions via API (or implement in TS)
   - Log to publish_events
   - Update batch_sku_assignments status
3. Update batch status to 'completed' or 'failed'

**Note**: Full publishing integration may require additional API routes that call the Python backend. For now, focus on the UI and database operations.

## Reference Files

- `src/feedops/db/supabase_client.py` - Python Supabase client patterns
- `src/feedops/db/schema.py` - SQLite schema (same structure)
- `dashboard/src/lib/supabase/server.ts` - Supabase server client

## Success Criteria

1. Batches page shows real data from Supabase
2. Can create new batches with name and optional SKUs
3. Can view batch details with assigned SKUs
4. Can add/remove SKUs from draft batches
5. Status updates work correctly
6. Works on Vercel deployment

## Notes

- Only approved SKUs should be eligible for batch assignment
- A SKU can only be in one active (non-completed) batch at a time
- Completed batches are historical records and shouldn't be modified
