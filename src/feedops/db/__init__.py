"""FeedOps database package.

This package provides a unified interface for database operations.
When Supabase is configured (SUPABASE_URL and SUPABASE_KEY), it uses
Supabase for workflow state (approvals, batches, publish events).
Otherwise, it falls back to SQLite for local development.

For Streamlit Cloud deployment, configure Supabase in secrets.toml:
    SUPABASE_URL = "https://xxxxx.supabase.co"
    SUPABASE_KEY = "eyJhbGci..."
"""

from feedops.db.schema import (
    cache_shopify_product,
    get_cached_merchant_center_items,
    get_cached_shopify_product,
    get_connection,
    get_published_skus_for_review,
    init_db,
    log_keyword_intent_snapshot,
    log_optimization,
)

# Import Supabase client for availability check
from feedops.db.supabase_client import is_supabase_available

# Conditionally import workflow functions from Supabase or SQLite
if is_supabase_available():
    # Use Supabase for workflow state (cloud deployment)
    from feedops.db.supabase_client import (
        assign_skus_to_batch,
        create_batch,
        get_all_batches,
        get_all_performance_baselines,
        get_approved_for_batch,
        get_batch,
        get_batch_skus,
        get_last_publish_event,
        get_pending_approvals,
        get_performance_baseline,
        get_performance_snapshots,
        get_publish_history,
        get_published_skus,
        get_revision_queue,
        get_sku_approval,
        get_skus_needing_review,
        get_variant_approval,
        get_variant_approvals_for_sku,
        log_publish_event,
        save_performance_baseline,
        save_performance_snapshot,
        save_sku_approval,
        save_variant_approval,
        update_batch_status,
    )
else:
    # Fall back to SQLite for local development
    from feedops.db.schema import (
        assign_skus_to_batch,
        create_batch,
        get_all_batches,
        get_all_performance_baselines,
        get_approved_for_batch,
        get_batch,
        get_batch_skus,
        get_last_publish_event,
        get_pending_approvals,
        get_performance_baseline,
        get_performance_snapshots,
        get_publish_history,
        get_published_skus,
        get_revision_queue,
        get_sku_approval,
        get_skus_needing_review,
        get_variant_approval,
        get_variant_approvals_for_sku,
        log_publish_event,
        save_performance_baseline,
        save_performance_snapshot,
        save_sku_approval,
        save_variant_approval,
        update_batch_status,
    )


__all__ = [
    # Core database functions
    "init_db",
    "get_connection",
    "is_supabase_available",
    # Optimization logging
    "log_optimization",
    "log_keyword_intent_snapshot",
    # Cache functions
    "cache_shopify_product",
    "get_cached_shopify_product",
    "get_cached_merchant_center_items",
    # Publish event functions
    "log_publish_event",
    "get_publish_history",
    "get_last_publish_event",
    "get_published_skus",
    "get_skus_needing_review",
    # Performance tracking
    "save_performance_snapshot",
    "get_performance_snapshots",
    "save_performance_baseline",
    "get_performance_baseline",
    "get_all_performance_baselines",
    "get_published_skus_for_review",
    # SKU approval functions
    "save_sku_approval",
    "get_sku_approval",
    "get_pending_approvals",
    "get_revision_queue",
    "get_approved_for_batch",
    # Variant approval functions
    "save_variant_approval",
    "get_variant_approval",
    "get_variant_approvals_for_sku",
    # Batch management functions
    "create_batch",
    "get_batch",
    "get_all_batches",
    "assign_skus_to_batch",
    "get_batch_skus",
    "update_batch_status",
]
