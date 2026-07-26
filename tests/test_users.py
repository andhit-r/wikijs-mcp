"""Test untuk tool domain users (:mod:`wikijs_mcp.tools.users`).

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
        "users": {
            "list": [
                {
                    "id": 1,
                    "name": "Administrator",
                    "email": "admin@example.com",
                    "providerKey": "local",
                    "isSystem": True,
                    "isActive": True,
                    "createdAt": "2024-01-01T00:00:00.000Z",
                    "lastLoginAt": "2024-03-01T00:00:00.000Z",
                },
                {
                    "id": 2,
                    "name": "Jane Editor",
                    "email": "jane@example.com",
                    "providerKey": "local",
                    "isSystem": False,
                    "isActive": True,
                    "createdAt": "2024-02-01T00:00:00.000Z",
                    "lastLoginAt": None,
                },
            ]
        }
    }
}

_SINGLE_RESPONSE = {
    "data": {
        "users": {
            "single": {
                "id": 5,
                "name": "Jane Editor",
                "email": "jane@example.com",
                "providerKey": "local",
                "isSystem": False,
                "isActive": True,
                "isVerified": True,
                "location": "Jakarta",
                "jobTitle": "Editor",
                "timezone": "Asia/Jakarta",
                "createdAt": "2024-02-01T00:00:00.000Z",
                "updatedAt": "2024-02-02T00:00:00.000Z",
                "lastLoginAt": "2024-03-01T00:00:00.000Z",
                "groups": [{"id": 2, "name": "Editors"}],
            }
        }
    }
}

_SINGLE_NOT_FOUND_RESPONSE = {"data": {"users": {"single": None}}}


def _success_result() -> dict[str, object]:
    return {"succeeded": True, "errorCode": 0, "message": ""}


def _failure_result(message: str) -> dict[str, object]:
    return {"succeeded": False, "errorCode": 6001, "message": message}


# --- wikijs_user_list --------------------------------------------------


async def test_user_list_success(mcp: FastMCP, respx_mock) -> None:
    """Respons mock berisi 2 user → list 2 dict sesuai kontrak."""
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=_LIST_RESPONSE))

    data = await call_tool(mcp, "wikijs_user_list")

    assert len(data) == 2
    assert data[0]["id"] == 1
    assert data[0]["email"] == "admin@example.com"
    assert data[1]["name"] == "Jane Editor"


# --- wikijs_user_get -----------------------------------------------------


async def test_user_get_success(mcp: FastMCP, respx_mock) -> None:
    """user_id valid → dict tunggal termasuk groups."""
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=_SINGLE_RESPONSE))

    data = await call_tool(mcp, "wikijs_user_get", {"user_id": 5})

    assert data["id"] == 5
    assert data["email"] == "jane@example.com"
    assert data["groups"] == [{"id": 2, "name": "Editors"}]


async def test_user_get_not_found_returns_none(mcp: FastMCP, respx_mock) -> None:
    """users.single bernilai null → tool mengembalikan None."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_SINGLE_NOT_FOUND_RESPONSE)
    )

    data = await call_tool(mcp, "wikijs_user_get", {"user_id": 999})

    assert data is None


@pytest.mark.parametrize("user_id", [0, -1])
async def test_user_get_invalid_id_raises(mcp: FastMCP, respx_mock, user_id: int) -> None:
    """user_id <= 0 → ValueError, tanpa request HTTP terkirim."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_SINGLE_RESPONSE)
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_user_get", {"user_id": user_id})
    assert "user_id" in str(exc.value)
    assert not route.called


# --- wikijs_user_create ----------------------------------------------------


async def test_user_create_success(mcp: FastMCP, respx_mock) -> None:
    """Payload valid → sukses, return {id, name, email} tanpa password_raw."""
    response = {
        "data": {
            "users": {
                "create": {
                    "responseResult": _success_result(),
                    "user": {"id": 6, "name": "New User", "email": "new@example.com"},
                }
            }
        }
    }
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    data = await call_tool(
        mcp,
        "wikijs_user_create",
        {
            "email": "new@example.com",
            "name": "New User",
            "group_ids": [2],
            "password_raw": "s3cr3t-dummy-password",
        },
    )

    assert data == {"id": 6, "name": "New User", "email": "new@example.com"}
    serialized = json.dumps(data)
    assert "s3cr3t-dummy-password" not in serialized

    body = json.loads(route.calls.last.request.content)
    assert body["variables"]["email"] == "new@example.com"
    assert body["variables"]["groups"] == [2]
    assert body["variables"]["passwordRaw"] == "s3cr3t-dummy-password"


async def test_user_create_optional_fields_only_sent_when_filled(mcp: FastMCP, respx_mock) -> None:
    """must_change_password/send_welcome_email None → tidak dikirim sebagai variabel."""
    response = {
        "data": {
            "users": {
                "create": {
                    "responseResult": _success_result(),
                    "user": {"id": 6, "name": "New User", "email": "new@example.com"},
                }
            }
        }
    }
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    await call_tool(
        mcp,
        "wikijs_user_create",
        {"email": "new@example.com", "name": "New User", "group_ids": [2]},
    )

    body = json.loads(route.calls.last.request.content)
    variables = body["variables"]
    assert "passwordRaw" not in variables
    assert "mustChangePassword" not in variables
    assert "sendWelcomeEmail" not in variables


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "", "name": "New User", "group_ids": [2]},
        {"email": "new@example.com", "name": "   ", "group_ids": [2]},
        {"email": "new@example.com", "name": "New User", "group_ids": []},
        {"email": "bukan-email", "name": "New User", "group_ids": [2]},
    ],
)
async def test_user_create_invalid_payload_raises(
    mcp: FastMCP, respx_mock, payload: dict[str, object]
) -> None:
    """email/name kosong, group_ids=[], atau email tanpa '@' → ValueError, tanpa request HTTP."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "users": {
                        "create": {
                            "responseResult": _success_result(),
                            "user": {"id": 6, "name": "x", "email": "x@example.com"},
                        }
                    }
                }
            },
        )
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_user_create", payload)
    assert exc.value is not None
    assert not route.called


async def test_user_create_failed(mcp: FastMCP, respx_mock) -> None:
    """responseResult.succeeded=false → WikiJSAPIError dengan pesan dari message."""
    response = {
        "data": {
            "users": {
                "create": {
                    "responseResult": _failure_result("Email already exists"),
                    "user": None,
                }
            }
        }
    }
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(
            mcp,
            "wikijs_user_create",
            {"email": "new@example.com", "name": "New User", "group_ids": [2]},
        )
    assert "Email already exists" in str(exc.value)


async def test_user_create_forbidden(mcp: FastMCP, respx_mock) -> None:
    """HTTP 403 (API key tanpa hak manage:users) → WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )

    with pytest.raises(Exception) as exc:
        await call_tool(
            mcp,
            "wikijs_user_create",
            {"email": "new@example.com", "name": "New User", "group_ids": [2]},
        )
    assert "403" in str(exc.value) or "ditolak" in str(exc.value).lower()


# --- wikijs_user_update ----------------------------------------------------


async def test_user_update_partial_fields_only_sends_filled_variables(
    mcp: FastMCP, respx_mock
) -> None:
    """Hanya is_active diisi → variabel GraphQL terkirim hanya untuk id+isActive."""
    response = {"data": {"users": {"update": {"responseResult": _success_result()}}}}
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    data = await call_tool(mcp, "wikijs_user_update", {"user_id": 5, "is_active": False})

    assert data == {"status": "updated"}
    body = json.loads(route.calls.last.request.content)
    variables = body["variables"]
    assert variables == {"id": 5, "isActive": False}


async def test_user_update_all_fields_sent(mcp: FastMCP, respx_mock) -> None:
    """Seluruh field diisi → seluruh variabel GraphQL ikut terkirim."""
    response = {"data": {"users": {"update": {"responseResult": _success_result()}}}}
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    args = {
        "user_id": 5,
        "email": "jane2@example.com",
        "name": "Jane Baru",
        "new_password": "dummy-new-password",
        "is_active": True,
        "timezone": "Asia/Jakarta",
        "group_ids": [2, 3],
        "job_title": "Senior Editor",
        "location": "Bandung",
    }
    data = await call_tool(mcp, "wikijs_user_update", args)

    assert data == {"status": "updated"}
    body = json.loads(route.calls.last.request.content)
    variables = body["variables"]
    assert variables == {
        "id": 5,
        "email": "jane2@example.com",
        "name": "Jane Baru",
        "newPassword": "dummy-new-password",
        "isActive": True,
        "timezone": "Asia/Jakarta",
        "groups": [2, 3],
        "jobTitle": "Senior Editor",
        "location": "Bandung",
    }
    serialized = json.dumps(data)
    assert "dummy-new-password" not in serialized


@pytest.mark.parametrize("user_id", [0, -5])
async def test_user_update_invalid_id_raises(mcp: FastMCP, respx_mock, user_id: int) -> None:
    """user_id <= 0 → ValueError, tanpa request HTTP terkirim."""
    response = {"data": {"users": {"update": {"responseResult": _success_result()}}}}
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_user_update", {"user_id": user_id, "name": "X"})
    assert "user_id" in str(exc.value)
    assert not route.called


async def test_user_update_invalid_email_raises(mcp: FastMCP, respx_mock) -> None:
    """email diisi tapi tidak mengandung '@' → ValueError, tanpa request HTTP terkirim."""
    response = {"data": {"users": {"update": {"responseResult": _success_result()}}}}
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_user_update", {"user_id": 5, "email": "bukan-email"})
    assert "email" in str(exc.value).lower()
    assert not route.called


async def test_user_update_failed(mcp: FastMCP, respx_mock) -> None:
    """responseResult.succeeded=false → WikiJSAPIError."""
    response = {
        "data": {"users": {"update": {"responseResult": _failure_result("User not found")}}}
    }
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_user_update", {"user_id": 999, "name": "X"})
    assert "User not found" in str(exc.value)


async def test_user_update_forbidden(mcp: FastMCP, respx_mock) -> None:
    """HTTP 403 → WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_user_update", {"user_id": 5, "name": "X"})
    assert "403" in str(exc.value) or "ditolak" in str(exc.value).lower()


# --- wikijs_user_delete ----------------------------------------------------


async def test_user_delete_success(mcp: FastMCP, respx_mock) -> None:
    """user_id valid → sukses, {"status": "deleted", "user_id": 5}."""
    response = {"data": {"users": {"delete": {"responseResult": _success_result()}}}}
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    data = await call_tool(mcp, "wikijs_user_delete", {"user_id": 5})

    assert data == {"status": "deleted", "user_id": 5}


async def test_user_delete_with_replace_id(mcp: FastMCP, respx_mock) -> None:
    """replace_id diisi → ikut terkirim sebagai variabel replaceId."""
    response = {"data": {"users": {"delete": {"responseResult": _success_result()}}}}
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    data = await call_tool(mcp, "wikijs_user_delete", {"user_id": 5, "replace_id": 2})

    assert data == {"status": "deleted", "user_id": 5}
    body = json.loads(route.calls.last.request.content)
    assert body["variables"] == {"id": 5, "replaceId": 2}


@pytest.mark.parametrize("user_id", [0, -1])
async def test_user_delete_invalid_id_raises(mcp: FastMCP, respx_mock, user_id: int) -> None:
    """user_id <= 0 → ValueError, tanpa request HTTP terkirim."""
    response = {"data": {"users": {"delete": {"responseResult": _success_result()}}}}
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_user_delete", {"user_id": user_id})
    assert "user_id" in str(exc.value)
    assert not route.called


async def test_user_delete_failed(mcp: FastMCP, respx_mock) -> None:
    """responseResult.succeeded=false → WikiJSAPIError."""
    response = {
        "data": {
            "users": {"delete": {"responseResult": _failure_result("Cannot delete system user")}}
        }
    }
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_user_delete", {"user_id": 1})
    assert "Cannot delete system user" in str(exc.value)


async def test_user_delete_forbidden(mcp: FastMCP, respx_mock) -> None:
    """HTTP 403 → WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_user_delete", {"user_id": 5})
    assert "403" in str(exc.value) or "ditolak" in str(exc.value).lower()


# --- wikijs_user_activate / wikijs_user_deactivate / TFA -------------------


@pytest.mark.parametrize(
    "tool_name, graphql_field, expected_status",
    [
        ("wikijs_user_activate", "activate", "activated"),
        ("wikijs_user_deactivate", "deactivate", "deactivated"),
        ("wikijs_user_enable_tfa", "enableTFA", "tfa_enabled"),
        ("wikijs_user_disable_tfa", "disableTFA", "tfa_disabled"),
    ],
)
async def test_user_id_only_mutations_success(
    mcp: FastMCP, respx_mock, tool_name: str, graphql_field: str, expected_status: str
) -> None:
    """id valid → sukses, bentuk return sesuai kontrak masing-masing tool."""
    response = {"data": {"users": {graphql_field: {"responseResult": _success_result()}}}}
    route = respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    data = await call_tool(mcp, tool_name, {"user_id": 5})

    assert data == {"status": expected_status, "user_id": 5}
    body = json.loads(route.calls.last.request.content)
    assert body["variables"] == {"id": 5}


@pytest.mark.parametrize(
    "tool_name",
    [
        "wikijs_user_activate",
        "wikijs_user_deactivate",
        "wikijs_user_enable_tfa",
        "wikijs_user_disable_tfa",
    ],
)
@pytest.mark.parametrize("user_id", [0, -1])
async def test_user_id_only_mutations_invalid_id_raises(
    mcp: FastMCP, respx_mock, tool_name: str, user_id: int
) -> None:
    """user_id <= 0 → ValueError, tanpa request HTTP terkirim."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "users": {
                        "activate": {"responseResult": _success_result()},
                        "deactivate": {"responseResult": _success_result()},
                        "enableTFA": {"responseResult": _success_result()},
                        "disableTFA": {"responseResult": _success_result()},
                    }
                }
            },
        )
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, tool_name, {"user_id": user_id})
    assert "user_id" in str(exc.value)
    assert not route.called


@pytest.mark.parametrize(
    "tool_name, graphql_field",
    [
        ("wikijs_user_activate", "activate"),
        ("wikijs_user_deactivate", "deactivate"),
        ("wikijs_user_enable_tfa", "enableTFA"),
        ("wikijs_user_disable_tfa", "disableTFA"),
    ],
)
async def test_user_id_only_mutations_failed(
    mcp: FastMCP, respx_mock, tool_name: str, graphql_field: str
) -> None:
    """responseResult.succeeded=false → WikiJSAPIError memuat pesan message."""
    response = {
        "data": {"users": {graphql_field: {"responseResult": _failure_result("User not found")}}}
    }
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=response))

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, tool_name, {"user_id": 999})
    assert "User not found" in str(exc.value)


@pytest.mark.parametrize(
    "tool_name",
    [
        "wikijs_user_activate",
        "wikijs_user_deactivate",
        "wikijs_user_enable_tfa",
        "wikijs_user_disable_tfa",
    ],
)
async def test_user_id_only_mutations_forbidden(mcp: FastMCP, respx_mock, tool_name: str) -> None:
    """HTTP 403 → WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, tool_name, {"user_id": 5})
    assert "403" in str(exc.value) or "ditolak" in str(exc.value).lower()
