"""Tests for Merchant Center snapshot handling."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest


def test_write_merchant_center_snapshot_jsonl(monkeypatch, tmp_path):
    from feedops.integrations import merchant_center

    output_path = tmp_path / "mc.jsonl"
    products = [
        {
            "offerId": "shopify_US_1_2",
            "productAttributes": {
                "customLabel0": "label0",
                "customLabel1": "label1",
                "customLabel2": None,
                "customLabel3": "",
                "customLabel4": "label4",
                "googleProductCategory": "Home & Garden",
                "productTypes": ["Bath", "Accessories"],
            },
            "productStatus": {
                "destinationStatuses": [
                    {"destination": "Shopping", "status": "approved"}
                ],
                "itemLevelIssues": [
                    {"code": "title_too_long", "severity": "disapproved"}
                ],
            },
        }
    ]

    monkeypatch.setattr(
        merchant_center,
        "fetch_merchant_center_products",
        lambda *_args, **_kwargs: products,
    )

    merchant_center.write_merchant_center_snapshot(output_path, limit=1)

    lines = output_path.read_text().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["offerId"] == "shopify_US_1_2"
    assert payload["customLabel0"] == "label0"
    assert payload["customLabel1"] == "label1"
    assert payload["customLabel4"] == "label4"
    assert payload["googleProductCategory"] == "Home & Garden"
    assert payload["productTypes"] == ["Bath", "Accessories"]
    assert payload["destinationStatuses"][0]["status"] == "approved"
    assert payload["itemLevelIssues"][0]["code"] == "title_too_long"
    assert "fetched_at" in payload


def test_fetch_merchant_center_items_normalizes(monkeypatch):
    from feedops.integrations import merchant_center

    products = [
        {
            "offerId": "shopify_US_1_2",
            "attributes": {
                "customLabel1": "label1",
                "googleProductCategory": "Home & Garden",
                "productTypes": ["Bath"],
            },
            "customAttributes": [
                {"name": "custom_label_0", "value": "label0"},
                {"attributeName": "customLabel2", "attributeValue": "label2"},
            ],
            "productStatus": {
                "destinationStatuses": [
                    {"destination": "Shopping", "status": "approved"}
                ],
                "itemLevelIssues": [
                    {"code": "title_too_long", "severity": "disapproved"}
                ],
            },
        }
    ]

    monkeypatch.setattr(
        merchant_center,
        "fetch_merchant_center_products",
        lambda *_args, **_kwargs: products,
    )

    normalized = merchant_center.fetch_merchant_center_items(limit=1)
    assert len(normalized) == 1
    assert normalized[0]["offerId"] == "shopify_US_1_2"
    assert normalized[0]["customLabel0"] == "label0"
    assert normalized[0]["customLabel2"] == "label2"
    assert normalized[0]["destinationStatuses"][0]["status"] == "approved"


def test_load_merchant_center_snapshot(monkeypatch, tmp_path):
    from feedops.integrations import merchant_center

    output_path = tmp_path / "mc.jsonl"
    output_path.write_text(
        json.dumps(
            {
                "offerId": "shopify_US_9_10",
                "customLabel0": "label0",
                "googleProductCategory": "Home",
                "productTypes": ["Bath"],
                "destinationStatuses": [],
                "itemLevelIssues": [],
                "fetched_at": "2026-01-01T00:00:00Z",
            }
        )
        + "\n"
    )

    data = merchant_center.load_merchant_center_snapshot(output_path)
    assert data["shopify_US_9_10"]["googleProductCategory"] == "Home"


def test_get_access_token_uses_gmc_api_key_path(monkeypatch, tmp_path):
    from feedops.integrations import merchant_center

    cred_path = tmp_path / "service-account.json"
    cred_path.write_text("{}")

    class DummyCred:
        def __init__(self) -> None:
            self.token = "token"

        def refresh(self, _request) -> None:
            pass

    def fake_from_file(path, scopes=None):
        assert path == str(cred_path)
        assert scopes == [merchant_center.MAPI_SCOPE]
        return DummyCred()

    monkeypatch.setattr(
        merchant_center.service_account.Credentials,
        "from_service_account_file",
        fake_from_file,
    )

    token = merchant_center._get_access_token({"GMC_API_KEY": str(cred_path)})
    assert token == "token"


def test_load_credentials_falls_back_to_creds_dir(monkeypatch, tmp_path):
    from feedops.integrations import merchant_center

    creds_dir = tmp_path / "creds"
    creds_dir.mkdir()
    (creds_dir / "client_secret_abc.json").write_text("{}")
    service_path = creds_dir / "service-account.json"
    service_path.write_text("{}")

    class DummyCred:
        def __init__(self) -> None:
            self.token = "token"

        def refresh(self, _request) -> None:
            pass

    captured = {"path": None}

    def fake_from_file(path, scopes=None):
        captured["path"] = path
        assert scopes == [merchant_center.MAPI_SCOPE]
        return DummyCred()

    monkeypatch.setattr(
        merchant_center.service_account.Credentials,
        "from_service_account_file",
        fake_from_file,
    )

    creds, source = merchant_center._load_credentials(
        {"GMC_API_KEY": "AIzaDummy", "FEEDOPS_CREDS_DIR": str(creds_dir)}
    )
    assert isinstance(creds, DummyCred)
    assert source == "creds_dir_fallback"
    assert captured["path"] == str(service_path)


def test_load_credentials_uses_google_ads_config(tmp_path):
    from feedops.integrations import merchant_center

    config_path = tmp_path / "google-ads.yaml"
    config_path.write_text(
        "\n".join(
            [
                "client_id: test-client-id",
                "client_secret: test-client-secret",
                "refresh_token: test-refresh-token",
            ]
        )
    )

    creds, source = merchant_center._load_credentials(
        {
            "GOOGLE_ADS_CONFIGURATION_FILE_PATH": str(config_path),
            "FEEDOPS_CREDS_DIR": str(tmp_path / "empty-creds"),
        }
    )

    assert source == "google_ads_config"
    assert hasattr(creds, "refresh")


def test_load_credentials_invalid_service_account_fails_fast_without_adc_fallback(monkeypatch, tmp_path):
    from feedops.integrations import merchant_center

    def fail_from_info(_info, scopes=None):
        raise ValueError("Invalid private key")

    def fail_adc(*_args, **_kwargs):
        raise AssertionError("ADC fallback should not be used")

    monkeypatch.setattr(
        merchant_center.service_account.Credentials,
        "from_service_account_info",
        fail_from_info,
    )
    monkeypatch.setattr(merchant_center.google.auth, "default", fail_adc)
    missing_ads_config = tmp_path / "missing-google-ads.yaml"
    missing_creds_dir = tmp_path / "missing-creds"

    with pytest.raises(ValueError, match="Merchant credential loading failed"):
        merchant_center._load_credentials(
            {
                "GOOGLE_SERVICE_ACCOUNT_KEY": '{"type":"service_account","private_key":"bad","client_email":"x@example.com"}',
                "GOOGLE_ADS_CONFIGURATION_FILE_PATH": str(missing_ads_config),
                "FEEDOPS_CREDS_DIR": str(missing_creds_dir),
            }
        )


def test_load_credentials_can_use_adc_fallback_when_opted_in(monkeypatch, tmp_path):
    from feedops.integrations import merchant_center

    class DummyCred:
        token = None

        def refresh(self, _request) -> None:
            return None

    def fail_from_info(_info, scopes=None):
        raise ValueError("Invalid private key")

    def fake_adc(*_args, **_kwargs):
        return DummyCred(), "project-id"

    monkeypatch.setattr(
        merchant_center.service_account.Credentials,
        "from_service_account_info",
        fail_from_info,
    )
    monkeypatch.setattr(merchant_center.google.auth, "default", fake_adc)
    missing_ads_config = tmp_path / "missing-google-ads.yaml"
    missing_creds_dir = tmp_path / "missing-creds"

    creds, source = merchant_center._load_credentials(
        {
            "GOOGLE_SERVICE_ACCOUNT_KEY": '{"type":"service_account","private_key":"bad","client_email":"x@example.com"}',
            "FEEDOPS_ALLOW_ADC_FALLBACK": "1",
            "GOOGLE_ADS_CONFIGURATION_FILE_PATH": str(missing_ads_config),
            "FEEDOPS_CREDS_DIR": str(missing_creds_dir),
        }
    )

    assert isinstance(creds, DummyCred)
    assert source == "adc_default"


def test_request_page_with_retries_timeout_then_success(monkeypatch):
    from feedops.integrations import merchant_center

    request = httpx.Request("GET", "https://example.test/products")
    attempts = {"count": 0}

    class FakeClient:
        def get(self, _endpoint, headers=None, params=None):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise httpx.ReadTimeout("timed out", request=request)
            return httpx.Response(200, json={"products": []}, request=request)

    monkeypatch.setattr(merchant_center.time, "sleep", lambda _seconds: None)

    response = merchant_center._request_page_with_retries(
        FakeClient(),
        "https://example.test/products",
        {"Authorization": "Bearer token"},
        {"pageSize": 1000},
        max_attempts=3,
        backoff_seconds=0.01,
    )

    assert response.status_code == 200
    assert attempts["count"] == 2


def test_request_page_with_retries_retries_on_503_then_succeeds(monkeypatch):
    from feedops.integrations import merchant_center

    request = httpx.Request("GET", "https://example.test/products")
    attempts = {"count": 0}

    class FakeClient:
        def get(self, _endpoint, headers=None, params=None):
            attempts["count"] += 1
            if attempts["count"] == 1:
                return httpx.Response(503, json={"error": "temporary"}, request=request)
            return httpx.Response(200, json={"products": [{"offerId": "x"}]}, request=request)

    monkeypatch.setattr(merchant_center.time, "sleep", lambda _seconds: None)

    response = merchant_center._request_page_with_retries(
        FakeClient(),
        "https://example.test/products",
        {"Authorization": "Bearer token"},
        {"pageSize": 1000},
        max_attempts=3,
        backoff_seconds=0.01,
    )

    assert response.status_code == 200
    assert attempts["count"] == 2
