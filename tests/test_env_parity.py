"""Regression tests for local runtime env parity with Vercel production vars."""

from __future__ import annotations

import base64
import json
import sys
import types


def _import_merchant_center_with_google_stubs(monkeypatch):
    """Import merchant_center with minimal google.* stubs for unit testing."""
    google = types.ModuleType("google")
    google_auth = types.ModuleType("google.auth")
    google_auth_transport = types.ModuleType("google.auth.transport")
    google_auth_transport_requests = types.ModuleType("google.auth.transport.requests")
    google_oauth2 = types.ModuleType("google.oauth2")
    google_oauth2_service_account = types.ModuleType("google.oauth2.service_account")
    google_oauth2_credentials = types.ModuleType("google.oauth2.credentials")

    class _DummyCred:
        token = None

        def refresh(self, _request) -> None:
            return None

    class _ServiceAccountCreds:
        @staticmethod
        def from_service_account_file(_path, scopes=None):  # pragma: no cover - patched in test
            return _DummyCred()

        @staticmethod
        def from_service_account_info(_info, scopes=None):  # pragma: no cover - patched in test
            return _DummyCred()

    class _OAuthCreds:
        def __init__(self, **_kwargs) -> None:
            self.token = None

        def refresh(self, _request) -> None:
            return None

    def _default(*_args, **_kwargs):
        return _DummyCred(), "adc_default"

    google.auth = google_auth
    google_auth.default = _default
    google_auth.transport = google_auth_transport
    google_auth_transport.requests = google_auth_transport_requests
    google_auth_transport_requests.Request = object

    google.oauth2 = google_oauth2
    google_oauth2.service_account = google_oauth2_service_account
    google_oauth2.service_account.Credentials = _ServiceAccountCreds
    google_oauth2.credentials = google_oauth2_credentials
    google_oauth2.credentials.Credentials = _OAuthCreds

    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.auth", google_auth)
    monkeypatch.setitem(sys.modules, "google.auth.transport", google_auth_transport)
    monkeypatch.setitem(
        sys.modules, "google.auth.transport.requests", google_auth_transport_requests
    )
    monkeypatch.setitem(sys.modules, "google.oauth2", google_oauth2)
    monkeypatch.setitem(
        sys.modules, "google.oauth2.service_account", google_oauth2_service_account
    )
    monkeypatch.setitem(
        sys.modules, "google.oauth2.credentials", google_oauth2_credentials
    )

    import importlib

    sys.modules.pop("feedops.integrations.merchant_center", None)
    merchant_center = importlib.import_module("feedops.integrations.merchant_center")
    return merchant_center


def test_supabase_config_accepts_vercel_env_names(monkeypatch):
    from feedops.db import supabase_client

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")

    config = supabase_client._get_supabase_config()
    assert config == ("https://example.supabase.co", "service-role-key")


def test_load_credentials_prefers_base64_service_account_key(monkeypatch):
    merchant_center = _import_merchant_center_with_google_stubs(monkeypatch)

    payload = {
        "type": "service_account",
        "project_id": "example-project",
        "private_key": "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----\\n",
        "client_email": "svc@example.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

    captured: dict[str, object] = {}

    class DummyCred:
        token = "token"

        def refresh(self, _request) -> None:
            return None

    def fake_from_info(info, scopes=None):
        captured["info"] = info
        captured["scopes"] = scopes
        return DummyCred()

    def fail_default(*_args, **_kwargs):
        raise AssertionError("google.auth.default should not be used")

    monkeypatch.setattr(
        merchant_center.service_account.Credentials,
        "from_service_account_info",
        fake_from_info,
    )
    monkeypatch.setattr(merchant_center.google.auth, "default", fail_default)

    creds, source = merchant_center._load_credentials(
        {
            "GOOGLE_SERVICE_ACCOUNT_KEY": encoded,
        }
    )

    assert isinstance(creds, DummyCred)
    assert source == "google_service_account_key_base64"
    assert captured["scopes"] == [merchant_center.MAPI_SCOPE]
    assert captured["info"]["client_email"] == payload["client_email"]
