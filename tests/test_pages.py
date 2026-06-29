"""Test untuk tool domain pages (:mod:`wikijs_mcp.tools.pages`).

Semua request ke Wiki.js GraphQL di-mock dengan respx_mock fixture.
"""

from __future__ import annotations

import httpx
import pytest
from fastmcp import FastMCP

from tests.conftest import GRAPHQL_URL, call_tool

_PAGE_ITEM = {
    "id": 1,
    "path": "home",
    "title": "Home",
    "locale": "en",
    "contentType": "markdown",
    "updatedAt": "2024-01-01",
}
_PAGE_FULL = {
    **_PAGE_ITEM,
    "description": "",
    "content": "# Home",
    "render": "<h1>Home</h1>",
    "editor": "markdown",
    "isPublished": True,
    "isPrivate": False,
    "tags": [{"tag": "home"}],
    "authorName": "admin",
    "creatorName": "admin",
    "createdAt": "2024-01-01",
}


async def test_page_list(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"pages": {"list": [_PAGE_ITEM]}}})
    )
    data = await call_tool(mcp, "wikijs_page_list")
    assert isinstance(data, list)
    assert data[0]["title"] == "Home"


async def test_page_get(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"pages": {"single": _PAGE_FULL}}})
    )
    data = await call_tool(mcp, "wikijs_page_get", {"page_id": 1})
    assert data["id"] == 1
    assert data["title"] == "Home"


async def test_page_get_graphql_error(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "Page not found"}]})
    )
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_page_get", {"page_id": 999})
    assert "GraphQL error" in str(exc.value)


async def test_page_get_invalid_id(mcp: FastMCP) -> None:
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_page_get", {"page_id": 0})
    assert "positif" in str(exc.value)


async def test_page_get_by_path(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"pages": {"singleByPath": _PAGE_FULL}}})
    )
    data = await call_tool(mcp, "wikijs_page_get_by_path", {"path": "home"})
    assert data["path"] == "home"


async def test_page_get_by_path_empty_raises(mcp: FastMCP) -> None:
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_page_get_by_path", {"path": ""})
    assert "kosong" in str(exc.value)


async def test_page_create(mcp: FastMCP, respx_mock) -> None:
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "pages": {
                        "create": {
                            "responseResult": {"succeeded": True, "errorCode": 0, "message": ""},
                            "page": {"id": 10, "path": "new-page"},
                        }
                    }
                }
            },
        )
    )
    data = await call_tool(
        mcp, "wikijs_page_create", {"title": "New Page", "path": "new-page", "content": "# New"}
    )
    assert data["id"] == 10
    assert route.called


async def test_page_create_failed(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "pages": {
                        "create": {
                            "responseResult": {
                                "succeeded": False,
                                "errorCode": 3001,
                                "message": "Path sudah ada",
                            },
                            "page": None,
                        }
                    }
                }
            },
        )
    )
    with pytest.raises(Exception) as exc:
        await call_tool(
            mcp, "wikijs_page_create", {"title": "Dup", "path": "existing", "content": "x"}
        )
    assert "Path sudah ada" in str(exc.value)


async def test_page_create_empty_title_raises(mcp: FastMCP) -> None:
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_page_create", {"title": "", "path": "p", "content": "c"})
    assert "title" in str(exc.value).lower()


async def test_page_delete(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "pages": {
                        "delete": {
                            "responseResult": {"succeeded": True, "errorCode": 0, "message": ""},
                        }
                    }
                }
            },
        )
    )
    data = await call_tool(mcp, "wikijs_page_delete", {"page_id": 1})
    assert data["status"] == "deleted"
    assert data["page_id"] == 1


async def test_page_move(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "pages": {
                        "move": {
                            "responseResult": {"succeeded": True, "errorCode": 0, "message": ""},
                        }
                    }
                }
            },
        )
    )
    data = await call_tool(mcp, "wikijs_page_move", {"page_id": 1, "destination_path": "new/path"})
    assert data["status"] == "moved"


async def test_page_render(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "pages": {
                        "render": {
                            "responseResult": {"succeeded": True, "errorCode": 0, "message": ""},
                        }
                    }
                }
            },
        )
    )
    data = await call_tool(mcp, "wikijs_page_render", {"page_id": 1})
    assert data["status"] == "rendered"


async def test_page_tree(mcp: FastMCP, respx_mock) -> None:
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "pages": {
                        "tree": [
                            {
                                "id": 1,
                                "path": "home",
                                "title": "Home",
                                "isFolder": False,
                                "pageId": 1,
                                "locale": "en",
                            }
                        ]
                    }
                }
            },
        )
    )
    data = await call_tool(mcp, "wikijs_page_tree", {"path": "", "mode": "ALL", "locale": "en"})
    assert isinstance(data, list)
    assert data[0]["title"] == "Home"


async def test_page_tree_invalid_mode(mcp: FastMCP) -> None:
    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_page_tree", {"path": "", "mode": "INVALID"})
    assert "mode" in str(exc.value).lower()
