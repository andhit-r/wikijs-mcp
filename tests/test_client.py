"""Test untuk klien GraphQL Wiki.js (:mod:`wikijs_mcp.client`).

Mencakup happy path, penanganan error HTTP (401, 403, 404, 500), error jaringan,
timeout, GraphQL-level errors, dan helper _check_response_result.

Gunakan ``respx_mock`` fixture (bukan dekorator ``@respx.mock``) agar kompatibel
dengan pytest-asyncio asyncio_mode="auto".
"""

from __future__ import annotations

import httpx
import pytest

from tests.conftest import GRAPHQL_URL
from wikijs_mcp.client import WikiJSAPIError, WikiJSGraphQLClient, _check_response_result


async def test_execute_happy_path(wiki_client: WikiJSGraphQLClient, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"pages": {"list": [{"id": 1}]}}})
    )
    data = await wiki_client.execute("{ pages { list { id } } }")
    assert data == {"pages": {"list": [{"id": 1}]}}


async def test_authorization_header_sent(wiki_client: WikiJSGraphQLClient, respx_mock) -> None:
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json={"data": {}}))
    await wiki_client.execute("{ system { info { currentVersion } } }")
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer test-api-key"


async def test_graphql_errors_raise(wiki_client: WikiJSGraphQLClient, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200, json={"errors": [{"message": "Field tidak ditemukan", "locations": []}]}
        )
    )
    with pytest.raises(WikiJSAPIError) as exc:
        await wiki_client.execute("{ pages { nonexistent } }")
    assert "GraphQL error" in str(exc.value)
    assert exc.value.errors


async def test_401_raises(wiki_client: WikiJSGraphQLClient, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(401))
    with pytest.raises(WikiJSAPIError) as exc:
        await wiki_client.execute("{ system { info { currentVersion } } }")
    assert exc.value.status_code == 401
    assert "Tidak terautentikasi" in str(exc.value)


async def test_403_raises(wiki_client: WikiJSGraphQLClient, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(403))
    with pytest.raises(WikiJSAPIError) as exc:
        await wiki_client.execute("{ system { info { currentVersion } } }")
    assert exc.value.status_code == 403


async def test_500_raises(wiki_client: WikiJSGraphQLClient, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(WikiJSAPIError) as exc:
        await wiki_client.execute("{ system { info { currentVersion } } }")
    assert exc.value.status_code == 500


async def test_network_error_raises(wiki_client: WikiJSGraphQLClient, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(side_effect=httpx.ConnectError("connection refused"))
    with pytest.raises(WikiJSAPIError) as exc:
        await wiki_client.execute("{ pages { list { id } } }")
    assert "Gagal terhubung" in str(exc.value)


async def test_timeout_raises(wiki_client: WikiJSGraphQLClient, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(side_effect=httpx.ReadTimeout("timed out"))
    with pytest.raises(WikiJSAPIError) as exc:
        await wiki_client.execute("{ pages { list { id } } }")
    assert "Timeout" in str(exc.value)


def test_check_response_result_ok() -> None:
    _check_response_result({"succeeded": True, "message": "ok"}, "test_op")


def test_check_response_result_failed() -> None:
    with pytest.raises(WikiJSAPIError) as exc:
        _check_response_result(
            {"succeeded": False, "errorCode": 3001, "message": "Path sudah ada"},
            "page_create",
        )
    assert "Path sudah ada" in str(exc.value)
    assert exc.value.operation == "page_create"


def test_check_response_result_none_skipped() -> None:
    _check_response_result(None, "test_op")


def test_check_response_result_empty_dict_ok() -> None:
    _check_response_result({}, "test_op")
