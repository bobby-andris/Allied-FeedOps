import sys
from types import ModuleType


google_module = ModuleType("google")
google_genai_module = ModuleType("google.genai")
google_genai_types_module = ModuleType("google.genai.types")
google_genai_module.types = google_genai_types_module
google_module.genai = google_genai_module

pil_module = ModuleType("PIL")
pil_image_module = ModuleType("PIL.Image")
pil_pnginfo_module = ModuleType("PIL.PngImagePlugin")

class _FakePngInfo:  # pragma: no cover - import shim only
    pass

class _FakeImage:  # pragma: no cover - import shim only
    pass

pil_pnginfo_module.PngInfo = _FakePngInfo
pil_image_module.Image = _FakeImage
pil_module.Image = pil_image_module

sys.modules.setdefault("google", google_module)
sys.modules.setdefault("google.genai", google_genai_module)
sys.modules.setdefault("google.genai.types", google_genai_types_module)
sys.modules.setdefault("PIL", pil_module)
sys.modules.setdefault("PIL.Image", pil_image_module)
sys.modules.setdefault("PIL.PngImagePlugin", pil_pnginfo_module)

from feedops.pipeline.lifestyle_images import save_lifestyle_image_to_db


class _FakeExecuteResult:
    def __init__(self, image_id: str):
        self.data = [{"id": image_id}]


class _FakeTable:
    def __init__(self, table_name: str, store: dict):
        self.table_name = table_name
        self._store = store
        self._pending_method: str | None = None
        self._pending_payload: dict | None = None
        self._pending_kwargs: dict | None = None

    def insert(self, payload: dict):
        self._pending_method = "insert"
        self._pending_payload = payload
        self._pending_kwargs = {}
        return self

    def upsert(self, payload: dict, **kwargs):
        self._pending_method = "upsert"
        self._pending_payload = payload
        self._pending_kwargs = kwargs
        return self

    def execute(self):
        call_log = self._store.setdefault(self.table_name, [])
        call_log.append(
            {
                "method": self._pending_method,
                "payload": self._pending_payload,
                "kwargs": self._pending_kwargs,
            }
        )
        image_id = f"{self.table_name}-{len(call_log)}"
        return _FakeExecuteResult(image_id)


class _FakeSupabase:
    def __init__(self):
        self.calls: dict[str, list[dict]] = {}

    def table(self, table_name: str):
        return _FakeTable(table_name, self.calls)


def test_save_lifestyle_image_to_db_uses_upsert_for_idempotent_regeneration():
    supabase = _FakeSupabase()

    save_lifestyle_image_to_db(
        master_sku="1098",
        shopify_product_id="gid://shopify/Product/123",
        finish="Polished Chrome",
        finish_code="PC",
        gmc_offer_id="offer-1098-pc",
        image_url="https://example.com/image.png",
        variation_num=1,
        ai_selected=True,
        score=92.1,
        prompt="test prompt",
        supabase_client=supabase,
    )

    product_call = supabase.calls["product_lifestyle_images"][0]
    assert product_call["method"] == "upsert"
    assert product_call["kwargs"]["on_conflict"] == "master_sku,variation_index"
    assert product_call["kwargs"]["ignore_duplicates"] is False

    variant_call = supabase.calls["variant_lifestyle_images"][0]
    assert variant_call["method"] == "upsert"
    assert variant_call["kwargs"]["on_conflict"] == "gmc_offer_id,variation_index"
    assert variant_call["kwargs"]["ignore_duplicates"] is False
