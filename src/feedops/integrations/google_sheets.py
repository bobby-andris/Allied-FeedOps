"""Google Sheets integration for GMC supplemental feed updates.

Pushes optimized product content (title, description, lifestyle images) to a Google Sheet
that serves as a supplemental feed for Google Merchant Center.

Authentication:
- Local development: Use GOOGLE_APPLICATION_CREDENTIALS env var pointing to JSON file
- Streamlit Cloud: Use st.secrets["GCP_SERVICE_ACCOUNT_JSON"] with JSON string

Streamlit secrets.toml format:
```toml
GOOGLE_SHEETS_SPREADSHEET_ID = "your-spreadsheet-id"
GCP_SERVICE_ACCOUNT_JSON = '{"type": "service_account", "project_id": "...", ...}'
```
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

# Scopes required for Google Sheets API
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Default column mapping for GMC supplemental feed
# Column letters map to 0-indexed positions
DEFAULT_COLUMN_MAP = {
    "id": 0,  # Column A - offer ID (GMC ID)
    "title": 1,  # Column B - product title
    "description": 2,  # Column C - product description
    "short_title": 3,  # Column D - short title for Demand Gen
    "lifestyle_image_link": 4,  # Column E - lifestyle image URL
    "custom_label_4": 5,  # Column F - FeedOps tracking label
}


def _get_streamlit_secrets() -> dict | None:
    """Try to get credentials from Streamlit secrets.

    Supports two formats:
    1. GCP_SERVICE_ACCOUNT_JSON: Single JSON string (recommended)
    2. gcp_service_account: TOML dict (legacy)

    Returns:
        Service account info dict if available, None otherwise.
    """
    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            # Try JSON string format first (recommended)
            if "GCP_SERVICE_ACCOUNT_JSON" in st.secrets:
                json_str = st.secrets["GCP_SERVICE_ACCOUNT_JSON"]
                return json.loads(json_str)
            # Fall back to TOML dict format (legacy)
            if "gcp_service_account" in st.secrets:
                return dict(st.secrets["gcp_service_account"])
    except Exception:
        pass
    return None


def _get_spreadsheet_id_from_secrets() -> str | None:
    """Try to get spreadsheet ID from Streamlit secrets.

    Returns:
        Spreadsheet ID if available, None otherwise.
    """
    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            # Check for the spreadsheet ID in secrets
            if "GOOGLE_SHEETS_SPREADSHEET_ID" in st.secrets:
                return st.secrets["GOOGLE_SHEETS_SPREADSHEET_ID"]
            # Also check in gcp_service_account section
            if "gcp_service_account" in st.secrets:
                sa = st.secrets["gcp_service_account"]
                if "spreadsheet_id" in sa:
                    return sa["spreadsheet_id"]
    except Exception:
        pass
    return None


def get_credentials(credentials_path: str | Path | None = None) -> Credentials:
    """Load service account credentials.

    Tries multiple sources in order:
    1. Streamlit secrets (for Streamlit Cloud deployment)
    2. Credentials file path (explicit parameter)
    3. GOOGLE_APPLICATION_CREDENTIALS env var (local development)

    Args:
        credentials_path: Path to service account JSON file (optional).

    Returns:
        Google OAuth2 credentials object.

    Raises:
        ValueError: If no valid credentials source is found.
    """
    # Try Streamlit secrets first (for cloud deployment)
    secrets_info = _get_streamlit_secrets()
    if secrets_info:
        return Credentials.from_service_account_info(secrets_info, scopes=SCOPES)

    # Try explicit credentials path
    if credentials_path is None:
        credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    if not credentials_path:
        raise ValueError(
            "No credentials found. Options:\n"
            "1. Set st.secrets['gcp_service_account'] for Streamlit Cloud\n"
            "2. Set GOOGLE_APPLICATION_CREDENTIALS env var for local development\n"
            "3. Pass credentials_path parameter"
        )

    credentials_path = Path(credentials_path)
    if not credentials_path.exists():
        raise ValueError(f"Credentials file not found: {credentials_path}")

    return Credentials.from_service_account_file(str(credentials_path), scopes=SCOPES)


def get_sheets_client(credentials_path: str | Path | None = None) -> gspread.Client:
    """Initialize authenticated Google Sheets client.

    Args:
        credentials_path: Path to service account JSON file.

    Returns:
        Authenticated gspread client.
    """
    credentials = get_credentials(credentials_path)
    return gspread.authorize(credentials)


def get_spreadsheet(
    spreadsheet_id: str | None = None,
    credentials_path: str | Path | None = None,
) -> gspread.Spreadsheet:
    """Open a spreadsheet by ID.

    Tries multiple sources for spreadsheet ID:
    1. Explicit parameter
    2. Streamlit secrets (GOOGLE_SHEETS_SPREADSHEET_ID)
    3. Environment variable (GOOGLE_NEW_MERCHANT_CENTER_SHEETS_SPREADSHEET_ID)

    Args:
        spreadsheet_id: Google Sheets spreadsheet ID.
        credentials_path: Path to service account JSON file.

    Returns:
        gspread Spreadsheet object.

    Raises:
        ValueError: If spreadsheet ID is not provided.
    """
    if spreadsheet_id is None:
        # Try Streamlit secrets first
        spreadsheet_id = _get_spreadsheet_id_from_secrets()

    if spreadsheet_id is None:
        # Fall back to environment variable
        spreadsheet_id = os.environ.get(
            "GOOGLE_NEW_MERCHANT_CENTER_SHEETS_SPREADSHEET_ID"
        )

    if not spreadsheet_id:
        raise ValueError(
            "No spreadsheet ID provided. Options:\n"
            "1. Set st.secrets['GOOGLE_SHEETS_SPREADSHEET_ID'] for Streamlit Cloud\n"
            "2. Set GOOGLE_NEW_MERCHANT_CENTER_SHEETS_SPREADSHEET_ID env var\n"
            "3. Pass spreadsheet_id parameter"
        )

    client = get_sheets_client(credentials_path)
    return client.open_by_key(spreadsheet_id)


def get_existing_ids(
    spreadsheet_id: str | None = None,
    sheet_name: str | None = None,
    id_column: int = 0,
    credentials_path: str | Path | None = None,
) -> dict[str, int]:
    """Fetch existing IDs from column A and map them to row numbers.

    Args:
        spreadsheet_id: Google Sheets spreadsheet ID.
        sheet_name: Name of the worksheet. If None, uses first sheet.
        id_column: Column index for IDs (0 = A, 1 = B, etc.).
        credentials_path: Path to service account JSON file.

    Returns:
        Dictionary mapping offer_id -> row_number (1-indexed).
    """
    spreadsheet = get_spreadsheet(spreadsheet_id, credentials_path)

    if sheet_name:
        worksheet = spreadsheet.worksheet(sheet_name)
    else:
        worksheet = spreadsheet.sheet1

    # Get all values from the ID column
    # Column index is 1-based in gspread
    id_values = worksheet.col_values(id_column + 1)

    # Build mapping: id -> row_number (1-indexed, skip header)
    id_to_row: dict[str, int] = {}
    for row_idx, value in enumerate(id_values):
        # Row 1 is header, data starts at row 2
        if row_idx == 0:
            continue
        if value:
            # Store the actual row number (1-indexed)
            id_to_row[str(value)] = row_idx + 1

    return id_to_row


def get_column_headers(
    spreadsheet_id: str | None = None,
    sheet_name: str | None = None,
    credentials_path: str | Path | None = None,
) -> list[str]:
    """Get column headers from the first row.

    Args:
        spreadsheet_id: Google Sheets spreadsheet ID.
        sheet_name: Name of the worksheet.
        credentials_path: Path to service account JSON file.

    Returns:
        List of column header names.
    """
    spreadsheet = get_spreadsheet(spreadsheet_id, credentials_path)

    if sheet_name:
        worksheet = spreadsheet.worksheet(sheet_name)
    else:
        worksheet = spreadsheet.sheet1

    # Get first row (headers)
    headers = worksheet.row_values(1)
    return headers


def build_column_map(headers: list[str]) -> dict[str, int]:
    """Build column name to index mapping from headers.

    Args:
        headers: List of column header names.

    Returns:
        Dictionary mapping column name -> index (0-based).
    """
    column_map: dict[str, int] = {}
    for idx, header in enumerate(headers):
        # Normalize header names (lowercase, strip whitespace)
        normalized = header.strip().lower().replace(" ", "_")
        column_map[normalized] = idx
    return column_map


def row_data_to_values(
    row_data: dict[str, Any],
    column_map: dict[str, int],
    num_columns: int,
) -> list[Any]:
    """Convert row data dict to list of values in column order.

    Args:
        row_data: Dictionary of field name -> value.
        column_map: Dictionary of field name -> column index.
        num_columns: Total number of columns in the sheet.

    Returns:
        List of values in column order.
    """
    values = [""] * num_columns

    for field, value in row_data.items():
        normalized_field = field.strip().lower().replace(" ", "_")
        if normalized_field in column_map:
            col_idx = column_map[normalized_field]
            if col_idx < num_columns:
                values[col_idx] = value if value is not None else ""

    return values


def update_rows(
    spreadsheet_id: str | None,
    updates: list[tuple[int, dict[str, Any]]],
    column_map: dict[str, int],
    num_columns: int,
    sheet_name: str | None = None,
    credentials_path: str | Path | None = None,
) -> int:
    """Batch update existing rows.

    Args:
        spreadsheet_id: Google Sheets spreadsheet ID.
        updates: List of (row_number, row_data) tuples.
        column_map: Dictionary of field name -> column index.
        num_columns: Total number of columns in the sheet.
        sheet_name: Name of the worksheet.
        credentials_path: Path to service account JSON file.

    Returns:
        Number of rows updated.
    """
    if not updates:
        return 0

    spreadsheet = get_spreadsheet(spreadsheet_id, credentials_path)

    if sheet_name:
        worksheet = spreadsheet.worksheet(sheet_name)
    else:
        worksheet = spreadsheet.sheet1

    # Prepare batch update
    batch_data = []
    for row_num, row_data in updates:
        values = row_data_to_values(row_data, column_map, num_columns)
        # Update only the columns we have data for
        for col_idx, value in enumerate(values):
            if value != "":
                # gspread uses A1 notation
                cell = gspread.utils.rowcol_to_a1(row_num, col_idx + 1)
                batch_data.append({"range": cell, "values": [[value]]})

    if batch_data:
        worksheet.batch_update(batch_data)

    return len(updates)


def append_rows(
    spreadsheet_id: str | None,
    rows: list[dict[str, Any]],
    column_map: dict[str, int],
    num_columns: int,
    sheet_name: str | None = None,
    credentials_path: str | Path | None = None,
) -> int:
    """Append new rows to the sheet.

    Args:
        spreadsheet_id: Google Sheets spreadsheet ID.
        rows: List of row data dictionaries.
        column_map: Dictionary of field name -> column index.
        num_columns: Total number of columns in the sheet.
        sheet_name: Name of the worksheet.
        credentials_path: Path to service account JSON file.

    Returns:
        Number of rows appended.
    """
    if not rows:
        return 0

    spreadsheet = get_spreadsheet(spreadsheet_id, credentials_path)

    if sheet_name:
        worksheet = spreadsheet.worksheet(sheet_name)
    else:
        worksheet = spreadsheet.sheet1

    # Convert all rows to value lists
    values_list = [row_data_to_values(row, column_map, num_columns) for row in rows]

    # Append all rows at once
    worksheet.append_rows(values_list, value_input_option="RAW")

    return len(rows)


def push_patches_to_sheet(
    patches: list[dict],
    environment: str = "staging",
    spreadsheet_id: str | None = None,
    sheet_name: str | None = None,
    credentials_path: str | Path | None = None,
    dry_run: bool = False,
    include_variants: bool = True,
) -> dict[str, Any]:
    """Push patch data to Google Sheet with upsert logic.

    For each patch (and optionally its variants), this function:
    1. Checks if the offer ID already exists in the sheet
    2. Updates the existing row if found
    3. Appends a new row if not found

    Args:
        patches: List of patch dictionaries (google-patch-*.json format).
        environment: 'staging' or 'production' - used for custom_label_4.
        spreadsheet_id: Google Sheets spreadsheet ID.
        sheet_name: Name of the worksheet.
        credentials_path: Path to service account JSON file.
        dry_run: If True, calculate changes but don't write.
        include_variants: If True, expand patches to include variant rows.

    Returns:
        Dictionary with:
        - success: bool
        - updated_count: Number of rows updated
        - appended_count: Number of rows appended
        - total_variants: Total variants processed
        - errors: List of error messages
        - dry_run: Whether this was a dry run
    """
    result: dict[str, Any] = {
        "success": False,
        "updated_count": 0,
        "appended_count": 0,
        "total_variants": 0,
        "errors": [],
        "dry_run": dry_run,
    }

    if not patches:
        result["errors"].append("No patches provided")
        return result

    tracking_label = f"feedops-{environment}"

    try:
        # Get existing IDs from the sheet
        existing_ids = get_existing_ids(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            credentials_path=credentials_path,
        )

        # Get column headers and build mapping
        headers = get_column_headers(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            credentials_path=credentials_path,
        )
        column_map = build_column_map(headers)
        num_columns = len(headers)

        # Ensure lifestyle_image_link column exists
        if "lifestyle_image_link" not in column_map:
            new_col_idx = num_columns
            column_map["lifestyle_image_link"] = new_col_idx
            num_columns += 1
            if not dry_run:
                spreadsheet = get_spreadsheet(spreadsheet_id, credentials_path)
                if sheet_name:
                    worksheet = spreadsheet.worksheet(sheet_name)
                else:
                    worksheet = spreadsheet.sheet1
                worksheet.update_cell(1, new_col_idx + 1, "lifestyle_image_link")

        # Ensure we have the required columns
        required_cols = ["id"]
        for col in required_cols:
            if col not in column_map:
                result["errors"].append(
                    f"Required column '{col}' not found in sheet headers"
                )
                return result

        # Build rows from patches
        rows_to_update: list[tuple[int, dict[str, Any]]] = []
        rows_to_append: list[dict[str, Any]] = []

        for patch in patches:
            # Get lifestyle image URL from patch (same for all variants)
            lifestyle_image_link = patch.get("lifestyle_image_link", "")

            # Determine which items to process
            items_to_process = []

            if include_variants:
                # Process all variants
                variants = patch.get("variants", [])
                if variants:
                    items_to_process.extend(variants)
                else:
                    # No variants array - use the patch itself as the single item
                    items_to_process.append(patch)
            else:
                # Only process the master item
                items_to_process.append(patch)

            for item in items_to_process:
                offer_id = item.get("offerId")
                if not offer_id:
                    continue

                result["total_variants"] += 1

                # Per-variant lifestyle image filtering
                approved_finish = patch.get("_image_approved_finish")
                variant_finish = item.get("_meta", {}).get("finish", "")
                if approved_finish == "__ALL_FINISHES__" or approved_finish == variant_finish:
                    row_lifestyle_image = lifestyle_image_link
                elif not approved_finish:
                    # No finish restriction — apply to all (backward compat)
                    row_lifestyle_image = lifestyle_image_link
                else:
                    row_lifestyle_image = ""

                row_data = {
                    "id": offer_id,
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "short_title": item.get("short_title", ""),
                    "lifestyle_image_link": row_lifestyle_image,
                    "custom_label_4": tracking_label,
                }

                if offer_id in existing_ids:
                    row_num = existing_ids[offer_id]
                    rows_to_update.append((row_num, row_data))
                else:
                    rows_to_append.append(row_data)

        if dry_run:
            result["success"] = True
            result["updated_count"] = len(rows_to_update)
            result["appended_count"] = len(rows_to_append)
            result["message"] = "Dry run - no changes made"
            return result

        # Execute updates
        if rows_to_update:
            updated = update_rows(
                spreadsheet_id=spreadsheet_id,
                updates=rows_to_update,
                column_map=column_map,
                num_columns=num_columns,
                sheet_name=sheet_name,
                credentials_path=credentials_path,
            )
            result["updated_count"] = updated

        # Execute appends
        if rows_to_append:
            appended = append_rows(
                spreadsheet_id=spreadsheet_id,
                rows=rows_to_append,
                column_map=column_map,
                num_columns=num_columns,
                sheet_name=sheet_name,
                credentials_path=credentials_path,
            )
            result["appended_count"] = appended

        result["success"] = True

    except gspread.exceptions.APIError as e:
        result["errors"].append(f"Google Sheets API error: {e}")
    except gspread.exceptions.SpreadsheetNotFound:
        result["errors"].append(
            "Spreadsheet not found. Check spreadsheet ID and permissions."
        )
    except gspread.exceptions.WorksheetNotFound:
        result["errors"].append(f"Worksheet '{sheet_name}' not found.")
    except Exception as e:
        result["errors"].append(f"Unexpected error: {e}")

    return result


def load_patches_for_batch(
    patches_dir: Path,
    skus: list[str],
    platform: str = "google",
) -> list[dict]:
    """Load patch files for a list of SKUs.

    Args:
        patches_dir: Directory containing patch files.
        skus: List of master SKUs to load.
        platform: Platform prefix ('google', 'bing', 'shopify').

    Returns:
        List of loaded patch dictionaries.
    """
    patches = []

    for sku in skus:
        safe_sku = sku.replace("/", "-")
        patch_file = patches_dir / f"{platform}-patch-{safe_sku}.json"

        if not patch_file.exists():
            continue

        try:
            with open(patch_file) as f:
                patch = json.load(f)
            patch["_source_file"] = str(patch_file)
            patches.append(patch)
        except (json.JSONDecodeError, OSError):
            continue

    return patches


def publish_batch_to_sheets(
    batch_id: str,
    patches_dir: Path,
    environment: str = "staging",
    spreadsheet_id: str | None = None,
    sheet_name: str | None = None,
    credentials_path: str | Path | None = None,
    dry_run: bool = False,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Publish a batch of SKUs to Google Sheets.

    This is the main entry point for batch publishing from the CLI or dashboard.

    Args:
        batch_id: Batch ID to publish.
        patches_dir: Directory containing patch files.
        environment: 'staging' or 'production'.
        spreadsheet_id: Google Sheets spreadsheet ID.
        sheet_name: Name of the worksheet.
        credentials_path: Path to service account JSON file.
        dry_run: If True, calculate changes but don't write.
        db_path: Path to database for looking up batch SKUs.

    Returns:
        Result dictionary from push_patches_to_sheet.
    """
    from feedops.db import get_batch_skus, init_db, log_publish_event

    # Resolve database path
    if db_path is None:
        db_path = Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))
    db_path = Path(db_path)
    init_db(db_path)

    # Get SKUs in the batch
    skus = get_batch_skus(db_path, batch_id=batch_id)
    if not skus:
        return {
            "success": False,
            "errors": [f"No SKUs found in batch {batch_id}"],
            "updated_count": 0,
            "appended_count": 0,
            "total_variants": 0,
            "dry_run": dry_run,
        }

    # Load patches for batch SKUs
    patches = load_patches_for_batch(patches_dir, skus, platform="google")
    if not patches:
        return {
            "success": False,
            "errors": [f"No Google patches found for batch {batch_id}"],
            "updated_count": 0,
            "appended_count": 0,
            "total_variants": 0,
            "dry_run": dry_run,
        }

    # Push to sheets
    result = push_patches_to_sheet(
        patches=patches,
        environment=environment,
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        credentials_path=credentials_path,
        dry_run=dry_run,
        include_variants=True,
    )

    # Log publish events for each SKU (only if not dry run and successful)
    if not dry_run and result.get("success"):
        for patch in patches:
            meta = patch.get("_meta", {})
            sku = meta.get("master_sku", "")
            if not sku:
                continue

            log_publish_event(
                db_path,
                master_sku=sku,
                platform="google",
                environment=environment,
                action="publish",
                patch_file=patch.get("_source_file", ""),
                status="success",
                quality_score=meta.get("quality_score"),
                approval_status=meta.get("approval_status"),
                batch_id=batch_id,
            )

    return result
