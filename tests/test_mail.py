"""Test untuk tool domain mail (:mod:`wikijs_mcp.tools.mail`).

Semua request ke Wiki.js GraphQL di-mock dengan respx_mock fixture. Nilai
kredensial di test ini adalah dummy yang jelas bukan kredensial sungguhan.
"""

from __future__ import annotations

import json

import httpx
import pytest
from fastmcp import FastMCP

from tests.conftest import GRAPHQL_URL, call_tool

_DUMMY_PASSWORD = "dummy-pass"
_DUMMY_DKIM_KEY = "dummy-dkim-private-key"

_UPDATE_CONFIG_ARGS: dict[str, object] = {
    "sender_name": "Wiki.js",
    "sender_email": "noreply@example.com",
    "host": "smtp.example.com",
    "port": 587,
    "name": "wiki.example.com",
    "secure": True,
    "verify_ssl": True,
    "user": "smtp-user",
    "password": _DUMMY_PASSWORD,
    "use_dkim": True,
    "dkim_domain_name": "example.com",
    "dkim_key_selector": "default",
    "dkim_private_key": _DUMMY_DKIM_KEY,
}

_SUCCESS_RESPONSE = {
    "data": {
        "mail": {
            "updateConfig": {
                "responseResult": {"succeeded": True, "errorCode": 0, "message": ""},
            }
        }
    }
}

_SEND_TEST_SUCCESS_RESPONSE = {
    "data": {
        "mail": {
            "sendTest": {
                "responseResult": {"succeeded": True, "errorCode": 0, "message": ""},
            }
        }
    }
}


async def test_mail_update_config_success(mcp: FastMCP, respx_mock) -> None:
    """Payload SMTP lengkap → sukses, seluruh 13 variabel terkirim dengan nama benar."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_SUCCESS_RESPONSE)
    )

    data = await call_tool(mcp, "wikijs_mail_update_config", _UPDATE_CONFIG_ARGS)

    assert data == {"status": "updated"}
    assert route.called
    body = json.loads(route.calls.last.request.content)
    variables = body["variables"]
    assert set(variables.keys()) == {
        "senderName",
        "senderEmail",
        "host",
        "port",
        "name",
        "secure",
        "verifySSL",
        "user",
        "pass",
        "useDKIM",
        "dkimDomainName",
        "dkimKeySelector",
        "dkimPrivateKey",
    }
    assert variables["pass"] == _DUMMY_PASSWORD
    assert "password" not in variables
    assert variables["verifySSL"] is True
    assert "verifySSLCertificate" not in variables


async def test_mail_update_config_empty_user_password_still_sent(mcp: FastMCP, respx_mock) -> None:
    """user='' dan password='' (relay tanpa auth) tetap terkirim, bukan di-omit."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_SUCCESS_RESPONSE)
    )

    args = {
        **_UPDATE_CONFIG_ARGS,
        "user": "",
        "password": "",
        "use_dkim": False,
        "dkim_domain_name": "",
        "dkim_key_selector": "",
        "dkim_private_key": "",
    }
    data = await call_tool(mcp, "wikijs_mail_update_config", args)

    assert data == {"status": "updated"}
    body = json.loads(route.calls.last.request.content)
    variables = body["variables"]
    assert variables["user"] == ""
    assert variables["pass"] == ""
    assert variables["dkimPrivateKey"] == ""
    assert "user" in variables
    assert "pass" in variables
    assert "dkimPrivateKey" in variables


async def test_mail_update_config_response_excludes_credentials(mcp: FastMCP, respx_mock) -> None:
    """Response tool tidak memuat password/dkim_private_key saat diserialisasi."""
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=_SUCCESS_RESPONSE))

    data = await call_tool(mcp, "wikijs_mail_update_config", _UPDATE_CONFIG_ARGS)

    serialized = json.dumps(data)
    assert _DUMMY_PASSWORD not in serialized
    assert _DUMMY_DKIM_KEY not in serialized


async def test_mail_send_test_response_excludes_credentials(mcp: FastMCP, respx_mock) -> None:
    """Response wikijs_mail_send_test juga tidak pernah memuat kredensial dummy."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_SEND_TEST_SUCCESS_RESPONSE)
    )

    data = await call_tool(mcp, "wikijs_mail_send_test", {"recipient_email": "ops@example.com"})

    serialized = json.dumps(data)
    assert _DUMMY_PASSWORD not in serialized
    assert _DUMMY_DKIM_KEY not in serialized


async def test_mail_update_config_failed(mcp: FastMCP, respx_mock) -> None:
    """responseResult.succeeded=false → WikiJSAPIError dengan pesan dari field message."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "mail": {
                        "updateConfig": {
                            "responseResult": {
                                "succeeded": False,
                                "errorCode": 4001,
                                "message": "SMTP auth failed",
                            }
                        }
                    }
                }
            },
        )
    )
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_mail_update_config", _UPDATE_CONFIG_ARGS)
    assert "SMTP auth failed" in str(exc.value)


async def test_mail_update_config_forbidden(mcp: FastMCP, respx_mock) -> None:
    """HTTP 403 (API key tanpa hak manage:system) → WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_mail_update_config", _UPDATE_CONFIG_ARGS)
    assert "403" in str(exc.value) or "ditolak" in str(exc.value).lower()


@pytest.mark.parametrize(
    "field, value, expected_message",
    [
        ("sender_email", "", "sender_email"),
        ("host", "   ", "host"),
        ("port", 0, "port"),
        ("port", 70000, "port"),
    ],
)
async def test_mail_update_config_validation_errors(
    mcp: FastMCP, respx_mock, field: str, value: object, expected_message: str
) -> None:
    """Validasi lokal melempar ValueError tanpa request HTTP terkirim."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_SUCCESS_RESPONSE)
    )

    args = {**_UPDATE_CONFIG_ARGS, field: value}
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_mail_update_config", args)
    assert expected_message in str(exc.value)
    assert not route.called


async def test_mail_update_config_dkim_validation_error(mcp: FastMCP, respx_mock) -> None:
    """use_dkim=True dengan dkim_private_key kosong → ValueError, tanpa request HTTP."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_SUCCESS_RESPONSE)
    )

    args = {
        **_UPDATE_CONFIG_ARGS,
        "use_dkim": True,
        "dkim_domain_name": "example.com",
        "dkim_key_selector": "default",
        "dkim_private_key": "",
    }
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_mail_update_config", args)
    assert "dkim" in str(exc.value).lower()
    assert not route.called


async def test_mail_send_test_success(mcp: FastMCP, respx_mock) -> None:
    """wikijs_mail_send_test('ops@example.com') → sukses, return status+recipient_email."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_SEND_TEST_SUCCESS_RESPONSE)
    )

    data = await call_tool(mcp, "wikijs_mail_send_test", {"recipient_email": "ops@example.com"})

    assert data == {"status": "test_sent", "recipient_email": "ops@example.com"}


async def test_mail_send_test_failed(mcp: FastMCP, respx_mock) -> None:
    """responseResult.succeeded=false → WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "mail": {
                        "sendTest": {
                            "responseResult": {
                                "succeeded": False,
                                "errorCode": 5001,
                                "message": "Mail server not configured",
                            }
                        }
                    }
                }
            },
        )
    )
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_mail_send_test", {"recipient_email": "ops@example.com"})
    assert "Mail server not configured" in str(exc.value)


@pytest.mark.parametrize("recipient_email", ["", "   "])
async def test_mail_send_test_empty_recipient_raises(
    mcp: FastMCP, respx_mock, recipient_email: str
) -> None:
    """recipient_email kosong/whitespace → ValueError, tanpa request HTTP terkirim."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_SEND_TEST_SUCCESS_RESPONSE)
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_mail_send_test", {"recipient_email": recipient_email})
    assert "kosong" in str(exc.value).lower()
    assert not route.called
