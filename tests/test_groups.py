"""Test untuk tool domain groups (:mod:`wikijs_mcp.tools.groups`).

Semua request ke Wiki.js GraphQL di-mock dengan respx_mock fixture — tidak
pernah memanggil instance Wiki.js sungguhan.
"""

from __future__ import annotations

import json

import httpx
import pytest
from fastmcp import FastMCP

from tests.conftest import GRAPHQL_URL, call_tool

_LIST_RESPONSE = {
    "data": {
        "groups": {
            "list": [
                {
                    "id": 1,
                    "name": "Administrators",
                    "isSystem": True,
                    "userCount": 1,
                    "createdAt": "2024-01-01T00:00:00.000Z",
                    "updatedAt": "2024-01-01T00:00:00.000Z",
                },
                {
                    "id": 2,
                    "name": "Editors",
                    "isSystem": False,
                    "userCount": 3,
                    "createdAt": "2024-02-01T00:00:00.000Z",
                    "updatedAt": "2024-02-02T00:00:00.000Z",
                },
            ]
        }
    }
}

_SINGLE_RESPONSE = {
    "data": {
        "groups": {
            "single": {
                "id": 3,
                "name": "Editors",
                "isSystem": False,
                "redirectOnLogin": "/",
                "permissions": ["read:pages", "write:pages"],
                "pageRules": [],
                "userCount": 2,
                "createdAt": "2024-02-01T00:00:00.000Z",
                "updatedAt": "2024-02-02T00:00:00.000Z",
            }
        }
    }
}

_SINGLE_NOT_FOUND_RESPONSE = {"data": {"groups": {"single": None}}}


def _success_result() -> dict[str, object]:
    return {"succeeded": True, "errorCode": 0, "message": ""}


def _failure_result(message: str) -> dict[str, object]:
    return {"succeeded": False, "errorCode": 6001, "message": message}


# --- wikijs_group_list --------------------------------------------------


async def test_group_list_success(mcp: FastMCP, respx_mock) -> None:
    """Respons mock berisi 2 group → list 2 dict dengan field lengkap."""
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=_LIST_RESPONSE))

    data = await call_tool(mcp, "wikijs_group_list")

    assert len(data) == 2
    assert data[0]["id"] == 1
    assert data[0]["name"] == "Administrators"
    assert data[1]["name"] == "Editors"
    assert data[1]["userCount"] == 3


# --- wikijs_group_get -----------------------------------------------------


async def test_group_get_success(mcp: FastMCP, respx_mock) -> None:
    """group_id valid → dict tunggal sesuai field groups.single."""
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=_SINGLE_RESPONSE))

    data = await call_tool(mcp, "wikijs_group_get", {"group_id": 3})

    assert data["id"] == 3
    assert data["name"] == "Editors"
    assert data["permissions"] == ["read:pages", "write:pages"]


async def test_group_get_not_found_returns_none(mcp: FastMCP, respx_mock) -> None:
    """groups.single bernilai null → tool mengembalikan None."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_SINGLE_NOT_FOUND_RESPONSE)
    )

    data = await call_tool(mcp, "wikijs_group_get", {"group_id": 999})

    assert data is None


@pytest.mark.parametrize("group_id", [0, -1])
async def test_group_get_invalid_id_raises(mcp: FastMCP, respx_mock, group_id: int) -> None:
    """group_id <= 0 → ValueError, tanpa request HTTP terkirim."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_SINGLE_RESPONSE)
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_group_get", {"group_id": group_id})
    assert "group_id" in str(exc.value)
    assert not route.called


# --- wikijs_group_create ----------------------------------------------------


async def test_group_create_success(mcp: FastMCP, respx_mock) -> None:
    """name valid → sukses, return {id, name}; body request memuat variabel name."""
    response = {
        "data": {
            "groups": {
                "create": {
                    "responseResult": _success_result(),
                    "group": {"id": 4, "name": "Editors"},
                }
            }
        }
    }
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    data = await call_tool(mcp, "wikijs_group_create", {"name": "Editors"})

    assert data == {"id": 4, "name": "Editors"}
    body = json.loads(route.calls.last.request.content)
    assert body["variables"]["name"] == "Editors"


@pytest.mark.parametrize("name", ["", "   "])
async def test_group_create_empty_name_raises(mcp: FastMCP, respx_mock, name: str) -> None:
    """name kosong/whitespace → ValueError sebelum ada request HTTP."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "groups": {
                        "create": {
                            "responseResult": _success_result(),
                            "group": {"id": 4, "name": name},
                        }
                    }
                }
            },
        )
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_group_create", {"name": name})
    assert "name" in str(exc.value).lower()
    assert not route.called


async def test_group_create_failed(mcp: FastMCP, respx_mock) -> None:
    """responseResult.succeeded=false → WikiJSAPIError dengan pesan dari message."""
    response = {
        "data": {
            "groups": {
                "create": {
                    "responseResult": _failure_result("Group name already exists"),
                    "group": None,
                }
            }
        }
    }
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_group_create", {"name": "Editors"})
    assert "Group name already exists" in str(exc.value)


async def test_group_create_forbidden(mcp: FastMCP, respx_mock) -> None:
    """HTTP 403 (API key tanpa hak manage:groups) → WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_group_create", {"name": "Editors"})
    assert "403" in str(exc.value) or "ditolak" in str(exc.value).lower()


# --- wikijs_group_update ----------------------------------------------------


async def test_group_update_partial_fields_only_sends_filled_variables(
    mcp: FastMCP, respx_mock
) -> None:
    """Hanya name diisi → variabel GraphQL terkirim hanya untuk id+name."""
    response = {"data": {"groups": {"update": {"responseResult": _success_result()}}}}
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    data = await call_tool(mcp, "wikijs_group_update", {"group_id": 3, "name": "Editors 2"})

    assert data == {"status": "updated"}
    body = json.loads(route.calls.last.request.content)
    variables = body["variables"]
    assert variables == {"id": 3, "name": "Editors 2"}
    assert "redirectOnLogin" not in variables
    assert "permissions" not in variables
    assert "pageRules" not in variables


async def test_group_update_all_fields_sent(mcp: FastMCP, respx_mock) -> None:
    """Seluruh field diisi → seluruh variabel GraphQL ikut terkirim."""
    response = {"data": {"groups": {"update": {"responseResult": _success_result()}}}}
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    args = {
        "group_id": 3,
        "name": "Editors 2",
        "redirect_on_login": "/dashboard",
        "permissions": ["read:pages"],
        "page_rules": [],
    }
    data = await call_tool(mcp, "wikijs_group_update", args)

    assert data == {"status": "updated"}
    body = json.loads(route.calls.last.request.content)
    variables = body["variables"]
    assert variables == {
        "id": 3,
        "name": "Editors 2",
        "redirectOnLogin": "/dashboard",
        "permissions": ["read:pages"],
        "pageRules": [],
    }


@pytest.mark.parametrize("group_id", [0, -5])
async def test_group_update_invalid_id_raises(mcp: FastMCP, respx_mock, group_id: int) -> None:
    """group_id <= 0 → ValueError, tanpa request HTTP terkirim."""
    response = {"data": {"groups": {"update": {"responseResult": _success_result()}}}}
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_group_update", {"group_id": group_id, "name": "X"})
    assert "group_id" in str(exc.value)
    assert not route.called


async def test_group_update_failed(mcp: FastMCP, respx_mock) -> None:
    """responseResult.succeeded=false → WikiJSAPIError."""
    response = {
        "data": {"groups": {"update": {"responseResult": _failure_result("Group not found")}}}
    }
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_group_update", {"group_id": 999, "name": "X"})
    assert "Group not found" in str(exc.value)


# --- wikijs_group_delete ----------------------------------------------------


async def test_group_delete_success(mcp: FastMCP, respx_mock) -> None:
    """group_id valid → sukses, {"status": "deleted", "group_id": 3}."""
    response = {"data": {"groups": {"delete": {"responseResult": _success_result()}}}}
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    data = await call_tool(mcp, "wikijs_group_delete", {"group_id": 3})

    assert data == {"status": "deleted", "group_id": 3}


@pytest.mark.parametrize("group_id", [0, -1])
async def test_group_delete_invalid_id_raises(mcp: FastMCP, respx_mock, group_id: int) -> None:
    """group_id <= 0 → ValueError, tanpa request HTTP terkirim."""
    response = {"data": {"groups": {"delete": {"responseResult": _success_result()}}}}
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_group_delete", {"group_id": group_id})
    assert "group_id" in str(exc.value)
    assert not route.called


async def test_group_delete_failed(mcp: FastMCP, respx_mock) -> None:
    """responseResult.succeeded=false → WikiJSAPIError."""
    response = {
        "data": {
            "groups": {"delete": {"responseResult": _failure_result("Cannot delete system group")}}
        }
    }
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_group_delete", {"group_id": 1})
    assert "Cannot delete system group" in str(exc.value)


async def test_group_delete_forbidden(mcp: FastMCP, respx_mock) -> None:
    """HTTP 403 → WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_group_delete", {"group_id": 3})
    assert "403" in str(exc.value) or "ditolak" in str(exc.value).lower()


# --- wikijs_group_assign_user / wikijs_group_unassign_user ------------------


async def test_group_assign_user_success(mcp: FastMCP, respx_mock) -> None:
    """group_id+user_id valid → sukses, bentuk return sesuai kontrak."""
    response = {"data": {"groups": {"assignUser": {"responseResult": _success_result()}}}}
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    data = await call_tool(mcp, "wikijs_group_assign_user", {"group_id": 3, "user_id": 7})

    assert data == {"status": "assigned", "group_id": 3, "user_id": 7}
    body = json.loads(route.calls.last.request.content)
    assert body["variables"] == {"groupId": 3, "userId": 7}


async def test_group_unassign_user_success(mcp: FastMCP, respx_mock) -> None:
    """group_id+user_id valid → sukses, bentuk return sesuai kontrak."""
    response = {"data": {"groups": {"unassignUser": {"responseResult": _success_result()}}}}
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    data = await call_tool(mcp, "wikijs_group_unassign_user", {"group_id": 3, "user_id": 7})

    assert data == {"status": "unassigned", "group_id": 3, "user_id": 7}
    body = json.loads(route.calls.last.request.content)
    assert body["variables"] == {"groupId": 3, "userId": 7}


@pytest.mark.parametrize(
    "tool_name",
    ["wikijs_group_assign_user", "wikijs_group_unassign_user"],
)
@pytest.mark.parametrize("group_id, user_id", [(0, 7), (3, 0), (-1, 7), (3, -1)])
async def test_group_assign_unassign_invalid_id_raises(
    mcp: FastMCP, respx_mock, tool_name: str, group_id: int, user_id: int
) -> None:
    """group_id atau user_id <= 0 → ValueError, tanpa request HTTP terkirim."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "groups": {
                        "assignUser": {"responseResult": _success_result()},
                        "unassignUser": {"responseResult": _success_result()},
                    }
                }
            },
        )
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, tool_name, {"group_id": group_id, "user_id": user_id})
    message = str(exc.value)
    assert "group_id" in message or "user_id" in message
    assert not route.called


async def test_group_assign_user_failed(mcp: FastMCP, respx_mock) -> None:
    """responseResult.succeeded=false → WikiJSAPIError."""
    response = {
        "data": {
            "groups": {"assignUser": {"responseResult": _failure_result("User already in group")}}
        }
    }
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_group_assign_user", {"group_id": 3, "user_id": 7})
    assert "User already in group" in str(exc.value)


async def test_group_unassign_user_failed(mcp: FastMCP, respx_mock) -> None:
    """responseResult.succeeded=false → WikiJSAPIError."""
    response = {
        "data": {
            "groups": {"unassignUser": {"responseResult": _failure_result("User not in group")}}
        }
    }
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_group_unassign_user", {"group_id": 3, "user_id": 7})
    assert "User not in group" in str(exc.value)


async def test_group_assign_user_forbidden(mcp: FastMCP, respx_mock) -> None:
    """HTTP 403 → WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_group_assign_user", {"group_id": 3, "user_id": 7})
    assert "403" in str(exc.value) or "ditolak" in str(exc.value).lower()
