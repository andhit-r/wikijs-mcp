"""Test untuk tool domain tags (:mod:`wikijs_mcp.tools.tags`)."""

from __future__ import annotations

import httpx
import pytest
from fastmcp import FastMCP

from tests.conftest import GRAPHQL_URL, call_tool

_TAGS = [
    {"id": 1, "tag": "wiki", "title": "Wiki", "createdAt": "2024-01-01", "updatedAt": "2024-01-01"},
    {"id": 2, "tag": "home", "title": "Home", "createdAt": "2024-01-01", "updatedAt": "2024-01-01"},
]

_PAGES_WITH_TAGS = [
    {
        "id": 1,
        "path": "home",
        "title": "Home",
        "locale": "en",
        "contentType": "markdown",
        "updatedAt": "2024-01-01",
        "tags": ["wiki", "home"],
    },
    {
        "id": 2,
        "path": "about",
        "title": "About",
        "locale": "en",
        "contentType": "markdown",
        "updatedAt": "2024-01-01",
        "tags": ["wiki"],
    },
]


async def test_tag_list(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"pages": {"tags": _TAGS}}})
    )
    data = await call_tool(mcp, "wikijs_tag_list")
    assert len(data) == 2
    assert data[0]["tag"] == "wiki"


async def test_tag_list_empty(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"pages": {"tags": []}}})
    )
    data = await call_tool(mcp, "wikijs_tag_list")
    assert data == []


async def test_page_list_by_tags_single_tag(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"pages": {"list": _PAGES_WITH_TAGS}}})
    )
    data = await call_tool(mcp, "wikijs_page_list_by_tags", {"tags": ["wiki"]})
    assert len(data) == 2


async def test_page_list_by_tags_multiple_tags(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"pages": {"list": _PAGES_WITH_TAGS}}})
    )
    data = await call_tool(mcp, "wikijs_page_list_by_tags", {"tags": ["wiki", "home"]})
    assert len(data) == 1
    assert data[0]["title"] == "Home"


async def test_page_list_by_tags_no_match(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"pages": {"list": _PAGES_WITH_TAGS}}})
    )
    data = await call_tool(mcp, "wikijs_page_list_by_tags", {"tags": ["nonexistent"]})
    assert data == []


async def test_page_list_by_tags_empty_raises(mcp: FastMCP) -> None:
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_page_list_by_tags", {"tags": []})
    assert "kosong" in str(exc.value)


async def test_page_list_by_tags_graphql_error(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "DB error"}]})
    )
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_page_list_by_tags", {"tags": ["wiki"]})
    assert "GraphQL error" in str(exc.value)
