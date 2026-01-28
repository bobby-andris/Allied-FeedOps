"""FeedOps database package."""

from feedops.db.schema import (
    cache_shopify_product,
    get_cached_merchant_center_items,
    get_cached_shopify_product,
    get_connection,
    get_last_publish_event,
    get_publish_history,
    init_db,
    log_keyword_intent_snapshot,
    log_optimization,
    log_publish_event,
)

__all__ = [
    "init_db",
    "get_connection",
    "log_optimization",
    "log_keyword_intent_snapshot",
    "cache_shopify_product",
    "get_cached_shopify_product",
    "get_cached_merchant_center_items",
    "log_publish_event",
    "get_publish_history",
    "get_last_publish_event",
]
