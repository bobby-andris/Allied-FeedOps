"""FeedOps data loaders.

Use lazy imports to avoid circular dependencies when lower-level modules import
loader helpers (e.g., db indexing that reads the catalog CSV).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "load_catalog",
    "get_parent_sku",
    "list_master_skus",
    "load_parent_sku_unified",
    "load_parent_sku_unified_with_status",
    "get_cached_shopify_age_hours",
    "unified_loader",
]


_LAZY_ATTRS: dict[str, tuple[str, str | None]] = {
    "load_catalog": ("feedops.loaders.catalog", "load_catalog"),
    "get_parent_sku": ("feedops.loaders.catalog", "get_parent_sku"),
    "list_master_skus": ("feedops.loaders.catalog", "list_master_skus"),
    "load_parent_sku_unified": ("feedops.loaders.unified_loader", "load_parent_sku_unified"),
    "load_parent_sku_unified_with_status": ("feedops.loaders.unified_loader", "load_parent_sku_unified_with_status"),
    "get_cached_shopify_age_hours": ("feedops.loaders.unified_loader", "get_cached_shopify_age_hours"),
    "unified_loader": ("feedops.loaders.unified_loader", None),
}


def __getattr__(name: str) -> Any:  # pragma: no cover
    target = _LAZY_ATTRS.get(name)
    if not target:
        raise AttributeError(name)
    module_name, attr_name = target
    module = import_module(module_name)
    if attr_name is None:
        return module
    return getattr(module, attr_name)


def __dir__() -> list[str]:  # pragma: no cover
    return sorted(set(__all__) | set(globals().keys()))
