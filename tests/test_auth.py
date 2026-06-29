"""Test untuk mekanisme auth pintu depan (:mod:`wikijs_mcp.auth` dan :mod:`wikijs_mcp.auth_provider`).

- ``BearerApiKeyVerifier`` diuji langsung.
- ``AuthentikProvider._extract_upstream_claims`` diuji dengan httpx di-mock.
- Setiap penolakan auth HARUS memakai ``error_code`` valid OAuth/MCP — kode di
  luar set valid memicu Pydantic ValidationError sehingga token exchange crash.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from mcp.server.auth.provider import TokenError

from tests.conftest import make_settings
from wikijs_mcp.auth import build_token_verifier
from wikijs_mcp.auth_provider import AuthentikProvider, BearerApiKeyVerifier

VALID_OAUTH_ERROR_CODES = {
    "invalid_request",
    "invalid_client",
    "invalid_grant",
    "unauthorized_client",
    "unsupported_grant_type",
    "invalid_scope",
}


def test_returns_none_when_no_auth_configured() -> None:
    assert build_token_verifier(make_settings()) is None


def test_returns_multi_auth_when_only_api_key() -> None:
    from fastmcp.server.auth import MultiAuth

    settings = make_settings(mcp_api_key="rahasia123")
    result = build_token_verifier(settings)
    assert isinstance(result, MultiAuth)


def test_returns_authentik_provider_when_oauth_complete() -> None:
    settings = make_settings(
        authentik_base_url="https://auth.example.com",
        authentik_app_slug="wikijs-mcp",
        authentik_client_id="cid",
        authentik_client_secret="secret",
        mcp_base_url="https://mcp.example.com",
    )
    assert settings.authentik_active is True
    provider = build_token_verifier(settings)
    assert isinstance(provider, AuthentikProvider)


def test_returns_multi_auth_when_both_oauth_and_api_key() -> None:
    from fastmcp.server.auth import MultiAuth

    settings = make_settings(
        authentik_base_url="https://auth.example.com",
        authentik_app_slug="wikijs-mcp",
        authentik_client_id="cid",
        authentik_client_secret="secret",
        mcp_base_url="https://mcp.example.com",
        mcp_api_key="rahasia123",
    )
    result = build_token_verifier(settings)
    assert isinstance(result, MultiAuth)


class TestBearerApiKeyVerifier:
    def test_api_key_kosong_raise(self) -> None:
        with pytest.raises(ValueError, match="api_key"):
            BearerApiKeyVerifier(api_key="")

    def test_api_key_spasi_raise(self) -> None:
        with pytest.raises(ValueError, match="api_key"):
            BearerApiKeyVerifier(api_key="   ")

    async def test_token_cocok(self) -> None:
        verifier = BearerApiKeyVerifier(api_key="rahasia")
        result = await verifier.verify_token("rahasia")
        assert result is not None
        assert result.client_id == "api-key-client"

    async def test_token_salah(self) -> None:
        verifier = BearerApiKeyVerifier(api_key="rahasia")
        assert await verifier.verify_token("salah") is None

    async def test_token_kosong(self) -> None:
        verifier = BearerApiKeyVerifier(api_key="rahasia")
        assert await verifier.verify_token("") is None


def _provider() -> AuthentikProvider:
    return AuthentikProvider(
        authentik_base_url="https://auth.example.com",
        application_slug="wikijs-mcp",
        client_id="cid",
        client_secret="secret",
        base_url="https://mcp.example.com",
        allowed_usernames=["akadmin"],
    )


class _FakeResp:
    def __init__(self, status_code: int, data: dict) -> None:
        self.status_code = status_code
        self._data = data

    def json(self) -> dict:
        return self._data


class _FakeClient:
    def __init__(self, *, resp: _FakeResp | None = None, raise_exc: Exception | None = None):
        self._resp = resp
        self._raise = raise_exc

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def get(self, *args, **kwargs) -> _FakeResp:
        if self._raise:
            raise self._raise
        return self._resp


async def _error_code(idp_tokens: dict, **client_kw) -> str | None:
    provider = _provider()
    with patch.object(httpx, "AsyncClient", lambda *a, **k: _FakeClient(**client_kw)):
        try:
            await provider._extract_upstream_claims(idp_tokens)
            return None
        except TokenError as exc:
            return exc.error


class TestAuthentikTokenErrorCodes:
    async def test_access_token_kosong(self) -> None:
        assert await _error_code({}) in VALID_OAUTH_ERROR_CODES

    async def test_userinfo_tak_terjangkau(self) -> None:
        code = await _error_code({"access_token": "x"}, raise_exc=httpx.ConnectError("boom"))
        assert code in VALID_OAUTH_ERROR_CODES

    async def test_userinfo_non_200(self) -> None:
        code = await _error_code({"access_token": "x"}, resp=_FakeResp(403, {}))
        assert code in VALID_OAUTH_ERROR_CODES

    async def test_username_tidak_ada(self) -> None:
        code = await _error_code({"access_token": "x"}, resp=_FakeResp(200, {}))
        assert code in VALID_OAUTH_ERROR_CODES

    async def test_username_tidak_diizinkan(self) -> None:
        code = await _error_code(
            {"access_token": "x"},
            resp=_FakeResp(200, {"preferred_username": "intruder"}),
        )
        assert code == "unauthorized_client"

    async def test_username_diizinkan_lolos(self) -> None:
        provider = _provider()
        resp = _FakeResp(200, {"preferred_username": "akadmin", "email": "a@x", "sub": "1"})
        with patch.object(httpx, "AsyncClient", lambda *a, **k: _FakeClient(resp=resp)):
            claims = await provider._extract_upstream_claims({"access_token": "x"})
        assert claims is not None
        assert claims["username"] == "akadmin"
