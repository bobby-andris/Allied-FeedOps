# Structured Title/Description Columns Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add GMC AI content disclosure compliance by implementing structured_title and structured_description columns in Google Sheets supplemental feed with compound format `trained_algorithmic_media:"content text"`.

**Architecture:** Create an `ensureStructuredColumns()` function that adds both columns at the end of the sheet if they don't exist, then modify `rowDataToValues()` to build the compound format string when writing structured fields. The `digital_source_type` is embedded in the compound format, not a separate column.

**Tech Stack:** TypeScript, googleapis (Google Sheets API v4), Node.js

---

## Task 1: Update Type Definitions

**Files:**
- Modify: `dashboard/src/lib/publishing/types.ts:72-82`

**Step 1: Remove digital_source_type from GoogleSheetsRow interface**

Update the `GoogleSheetsRow` interface to remove `digital_source_type` since it's embedded in the compound format:

```typescript
export interface GoogleSheetsRow {
  id: string // offer_id (GMC ID)
  title?: string // Standard title (omit if structured-only mode)
  description?: string // Standard description (omit if structured-only mode)
  structured_title?: string // For AI-generated content (compound format: trained_algorithmic_media:"content")
  structured_description?: string // For AI-generated content (compound format: trained_algorithmic_media:"content")
  short_title?: string
  lifestyle_image_link?: string
  custom_label_4: string // tracking label: feedops-staging or feedops-production
}
```

**Step 2: Update SheetColumnMap interface**

Remove `digital_source_type` from the `SheetColumnMap` interface:

```typescript
export interface SheetColumnMap {
  id: number
  title?: number
  description?: number
  structured_title?: number
  structured_description?: number
  short_title?: number
  lifestyle_image_link?: number
  custom_label_4?: number
  [key: string]: number | undefined
}
```

**Step 3: Update JSDoc comments**

Update the comment block for `GoogleSheetsRow` (lines 65-71):

```typescript
/**
 * Row data for Google Sheets supplemental feed
 *
 * GMC Policy for AI-Generated Content:
 * - If content is AI-generated, use structured_title/structured_description
 *   with compound format: trained_algorithmic_media:"content text"
 * - If both structured and standard fields are present, GMC ignores structured
 * - Set FEEDOPS_GMC_STRUCTURED_ONLY=1 to omit title/description and use only structured fields
 */
```

**Step 4: Commit type changes**

```bash
git add dashboard/src/lib/publishing/types.ts
git commit -m "refactor: Remove digital_source_type from GoogleSheetsRow (embedded in compound format)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Create Compound Format Builder Function

**Files:**
- Modify: `dashboard/src/lib/publishing/google-sheets.ts` (add new function after line 188)

**Step 1: Add buildCompoundFormat helper function**

Add this function after `getExistingIds()` and before `rowDataToValues()`:

```typescript
/**
 * Build GMC compound format for structured content fields.
 * Format: trained_algorithmic_media:"content text"
 *
 * Properly escapes quotes in content text per GMC specification.
 */
function buildCompoundFormat(content: string): string {
  // Escape any existing quotes in the content
  const escapedContent = content.replace(/"/g, '\\"')
  return `trained_algorithmic_media:"${escapedContent}"`
}
```

**Step 2: Commit helper function**

```bash
git add dashboard/src/lib/publishing/google-sheets.ts
git commit -m "feat: Add buildCompoundFormat helper for GMC structured fields

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Update rowDataToValues to Build Compound Format

**Files:**
- Modify: `dashboard/src/lib/publishing/google-sheets.ts:190-219`

**Step 1: Update rowDataToValues function**

Replace the `rowDataToValues` function with this updated version:

```typescript
/**
 * Convert row data dict to an array of values in column order.
 *
 * For structured fields, builds compound format: trained_algorithmic_media:"content"
 */
function rowDataToValues(
  rowData: GoogleSheetsRow,
  columnMap: SheetColumnMap,
  numColumns: number
): (string | undefined)[] {
  const values: (string | undefined)[] = new Array(numColumns).fill(undefined)

  // Build compound format for structured fields if present
  const structuredTitle = rowData.structured_title
    ? buildCompoundFormat(rowData.structured_title)
    : undefined

  const structuredDescription = rowData.structured_description
    ? buildCompoundFormat(rowData.structured_description)
    : undefined

  const entries: [keyof GoogleSheetsRow, string | undefined][] = [
    ['id', rowData.id],
    ['title', rowData.title],
    ['description', rowData.description],
    ['structured_title', structuredTitle],
    ['structured_description', structuredDescription],
    ['short_title', rowData.short_title],
    ['lifestyle_image_link', rowData.lifestyle_image_link],
    ['custom_label_4', rowData.custom_label_4],
  ]

  for (const [field, value] of entries) {
    const colIdx = columnMap[field]
    if (colIdx !== undefined && colIdx < numColumns && value !== undefined) {
      values[colIdx] = value
    }
  }

  return values
}
```

**Step 2: Commit compound format building**

```bash
git add dashboard/src/lib/publishing/google-sheets.ts
git commit -m "feat: Build compound format for structured title/description in rowDataToValues

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Create ensureStructuredColumns Function

**Files:**
- Modify: `dashboard/src/lib/publishing/google-sheets.ts` (add after `ensureLifestyleImageColumn`, before line 337)

**Step 1: Add ensureStructuredColumns function**

Add this function after `ensureLifestyleImageColumn()`:

```typescript
/**
 * Ensure structured_title and structured_description columns exist in the sheet.
 * These columns are required for GMC AI content disclosure compliance.
 *
 * Adds both columns at the end of the sheet if they don't exist.
 */
async function ensureStructuredColumns(
  sheets: sheets_v4.Sheets,
  spreadsheetId: string,
  columnMap: SheetColumnMap,
  numColumns: number,
  sheetName?: string
): Promise<{ columnMap: SheetColumnMap; numColumns: number }> {
  const needsStructuredTitle = columnMap.structured_title === undefined
  const needsStructuredDescription = columnMap.structured_description === undefined

  // If both columns exist, return unchanged
  if (!needsStructuredTitle && !needsStructuredDescription) {
    return { columnMap, numColumns }
  }

  // Build batch update for missing columns
  const updates: { column: string; index: number }[] = []
  let currentColIdx = numColumns

  if (needsStructuredTitle) {
    updates.push({ column: 'structured_title', index: currentColIdx })
    currentColIdx++
  }

  if (needsStructuredDescription) {
    updates.push({ column: 'structured_description', index: currentColIdx })
    currentColIdx++
  }

  // Add column headers in batch
  const data: sheets_v4.Schema$ValueRange[] = updates.map(({ column, index }) => {
    const columnLetter = columnIndexToLetter(index)
    const range = sheetName ? `${sheetName}!${columnLetter}1` : `${columnLetter}1`
    return {
      range,
      values: [[column]],
    }
  })

  await sheets.spreadsheets.values.batchUpdate({
    spreadsheetId,
    requestBody: {
      valueInputOption: 'RAW',
      data,
    },
  })

  // Update column map with new indices
  const updatedColumnMap = { ...columnMap }
  for (const { column, index } of updates) {
    updatedColumnMap[column] = index
  }

  return {
    columnMap: updatedColumnMap,
    numColumns: currentColIdx,
  }
}
```

**Step 2: Commit ensureStructuredColumns function**

```bash
git add dashboard/src/lib/publishing/google-sheets.ts
git commit -m "feat: Add ensureStructuredColumns to create structured title/description columns

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Update publishToGoogleSheets Function

**Files:**
- Modify: `dashboard/src/lib/publishing/google-sheets.ts:365-498`

**Step 1: Add ensureStructuredColumns call after ensureLifestyleImageColumn**

In the `publishToGoogleSheets` function, add the call to ensure structured columns exist. Find the block around lines 401-410 and update it:

```typescript
    // Ensure lifestyle_image_link column exists
    const ensured = await ensureLifestyleImageColumn(
      sheets,
      spreadsheetId,
      columnMap,
      numColumns,
      sheetName
    )
    columnMap = ensured.columnMap
    numColumns = ensured.numColumns

    // Ensure structured columns exist
    const ensuredStructured = await ensureStructuredColumns(
      sheets,
      spreadsheetId,
      columnMap,
      numColumns,
      sheetName
    )
    columnMap = ensuredStructured.columnMap
    numColumns = ensuredStructured.numColumns
```

**Step 2: Update logging to include structured columns**

Find the console.log statement around line 419 and add structured columns:

```typescript
    console.log('[publishToGoogleSheets] Column mapping from sheet headers:', {
      id: columnMap.id,
      title: columnMap.title,
      description: columnMap.description,
      structured_title: columnMap.structured_title,
      structured_description: columnMap.structured_description,
      lifestyle_image_link: columnMap.lifestyle_image_link,
      custom_label_4: columnMap.custom_label_4,
      numColumns,
    })
```

**Step 3: Update row data building (remove digital_source_type)**

Find the block around lines 443-455 where `rowData` is built. Remove the `digital_source_type` line since it's now embedded in the compound format:

```typescript
      const rowData: GoogleSheetsRow = {
        id: offerId,
        // Standard fields - omit if structured-only mode
        title: USE_STRUCTURED_ONLY ? undefined : title,
        description: USE_STRUCTURED_ONLY ? undefined : description,
        // Structured fields - always set for AI-generated content
        // Note: compound format is built in rowDataToValues()
        structured_title: title,
        structured_description: description,
        // Other fields
        custom_label_4: trackingLabel,
        lifestyle_image_link: imageUrl,
      }
```

**Step 4: Commit publishToGoogleSheets updates**

```bash
git add dashboard/src/lib/publishing/google-sheets.ts
git commit -m "feat: Integrate ensureStructuredColumns into publishToGoogleSheets

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Update publishExpandedVariantsToGoogleSheets Function

**Files:**
- Modify: `dashboard/src/lib/publishing/google-sheets.ts:509-636`

**Step 1: Add ensureStructuredColumns call**

In the `publishExpandedVariantsToGoogleSheets` function, add the call to ensure structured columns exist. Find the block around lines 542-551 and update it:

```typescript
    // Ensure lifestyle_image_link column exists
    const ensured = await ensureLifestyleImageColumn(
      sheets,
      spreadsheetId,
      columnMap,
      numColumns,
      sheetName
    )
    columnMap = ensured.columnMap
    numColumns = ensured.numColumns

    // Ensure structured columns exist
    const ensuredStructured = await ensureStructuredColumns(
      sheets,
      spreadsheetId,
      columnMap,
      numColumns,
      sheetName
    )
    columnMap = ensuredStructured.columnMap
    numColumns = ensuredStructured.numColumns
```

**Step 2: Update logging**

Find the console.log statement around line 560 and add structured columns:

```typescript
    console.log('[publishExpandedVariants] Column mapping from sheet headers:', {
      id: columnMap.id,
      title: columnMap.title,
      description: columnMap.description,
      structured_title: columnMap.structured_title,
      structured_description: columnMap.structured_description,
      lifestyle_image_link: columnMap.lifestyle_image_link,
      custom_label_4: columnMap.custom_label_4,
      numColumns,
      totalVariants: variants.length,
    })
```

**Step 3: Update row data building**

Find the block around lines 580-593 where `rowData` is built. Remove the `digital_source_type` line:

```typescript
      const rowData: GoogleSheetsRow = {
        id: variant.gmc_offer_id,
        // Standard fields - omit if structured-only mode
        title: USE_STRUCTURED_ONLY ? undefined : variant.title,
        description: USE_STRUCTURED_ONLY ? undefined : variant.description,
        // Structured fields - always set for AI-generated content
        // Note: compound format is built in rowDataToValues()
        structured_title: variant.title,
        structured_description: variant.description,
        // Other fields
        custom_label_4: trackingLabel,
        lifestyle_image_link: variant.image_url,
      }
```

**Step 4: Commit publishExpandedVariantsToGoogleSheets updates**

```bash
git add dashboard/src/lib/publishing/google-sheets.ts
git commit -m "feat: Integrate ensureStructuredColumns into publishExpandedVariantsToGoogleSheets

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Build Verification

**Files:**
- Test: `dashboard/` (build process)

**Step 1: Run TypeScript build**

```bash
cd dashboard
npm run build
```

Expected: Build succeeds with no TypeScript errors

**Step 2: Run linter**

```bash
npm run lint
```

Expected: No linting errors

**Step 3: Commit if fixes needed**

If any auto-fixable lint issues were found:

```bash
git add dashboard/src/lib/publishing/google-sheets.ts dashboard/src/lib/publishing/types.ts
git commit -m "style: Fix linting issues in structured columns implementation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Manual Testing Plan

**Testing Instructions:**

1. **Verify column creation (staging environment)**:
   - Set `FEEDOPS_GMC_STRUCTURED_ONLY=0` (or unset)
   - Publish a test SKU to staging
   - Check Google Sheet: columns `structured_title` and `structured_description` should appear at END
   - Verify format: `trained_algorithmic_media:"Your Title Here"`

2. **Verify structured-only mode**:
   - Set `FEEDOPS_GMC_STRUCTURED_ONLY=1`
   - Publish a test SKU to staging
   - Check Google Sheet: `title` and `description` columns should be empty/unchanged
   - Structured columns should have values

3. **Verify compound format quote escaping**:
   - Publish SKU with quotes in title (e.g., `12" Towel Bar`)
   - Check sheet: should show `trained_algorithmic_media:"12\" Towel Bar"` (escaped quotes)

4. **Verify existing columns unchanged**:
   - Compare columns A-K before and after publish
   - Verify no data corruption in existing columns

**Note:** These tests should be run manually in the staging environment before production deployment.

---

## Verification Checklist

- [ ] Type definitions updated (digital_source_type removed)
- [ ] buildCompoundFormat function created
- [ ] rowDataToValues builds compound format correctly
- [ ] ensureStructuredColumns function created
- [ ] Both publish functions call ensureStructuredColumns
- [ ] TypeScript build passes
- [ ] Linter passes
- [ ] Manual testing completed (staging)
- [ ] Columns added at END of sheet (after column K)
- [ ] Quote escaping works correctly
- [ ] Structured-only mode works (FEEDOPS_GMC_STRUCTURED_ONLY=1)
- [ ] Existing columns A-K unchanged

---

## Notes

- The `digital_source_type` value is now embedded in the compound format string, not a separate column
- Columns are added dynamically at runtime if they don't exist
- The compound format properly escapes quotes in content text
- When `FEEDOPS_GMC_STRUCTURED_ONLY=1`, standard title/description are omitted (GMC ignores structured fields when standard fields are present)
