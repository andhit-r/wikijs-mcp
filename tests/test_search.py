"""Test untuk tool domain search (:mod:`wikijs_mcp.tools.search`)."""

from __future__ import annotations

import httpx
import pytest
from fastmcp import FastMCP

from tests.conftest import GRAPHQL_URL, call_tool

_SEARCH_RESULT = {
    "results": [{"id": 1, "title": "Home", "description": "", "path": "home", "locale": "en"}],
    "suggestions": ["homepage"],
    "totalHits": 1,
}


async def test_page_search_happy_path(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"pages": {"search": _SEARCH_RESULT}}})
    )
    data = await call_tool(mcp, "wikijs_page_search", {"query": "home"})
    assert data["totalHits"] == 1
    assert data["results"][0]["title"] == "Home"
    assert data["suggestions"] == ["homepage"]


async def test_page_search_with_path_and_locale(mcp: FastMCP, respx_mock) -> None:
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"pages": {"search": _SEARCH_RESULT}}})
    )
    await call_tool(mcp, "wikijs_page_search", {"query": "test", "path": "folder", "locale": "en"})
    body = route.calls.last.request.content.decode()
    assert "folder" in body
    assert "en" in body


async def test_page_search_empty_query_raises(mcp: FastMCP) -> None:
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_page_search", {"query": ""})
    assert "kosong" in str(exc.value)


async def test_page_search_graphql_error(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "Search engine error"}]})
    )
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_page_search", {"query": "test"})
    assert "GraphQL error" in str(exc.value)
