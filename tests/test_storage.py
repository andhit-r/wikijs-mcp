"""Test untuk tool domain storage (:mod:`wikijs_mcp.tools.storage`).

Semua request ke Wiki.js GraphQL di-mock dengan fixture ``respx_mock`` sehingga
tidak pernah menyentuh instance sungguhan. Nilai kredensial di berkas ini adalah
dummy yang jelas bukan kredensial nyata; keberadaannya justru dipakai untuk
membuktikan sensor ``basicPassword``/``sshPrivateKeyContent`` benar-benar bekerja.
"""

from __future__ import annotations

import json

import httpx
import pytest
from fastmcp import FastMCP

from tests.conftest import GRAPHQL_URL, call_tool

_DUMMY_BASIC_PASSWORD = "dummy-basic-password"
_DUMMY_SSH_PRIVATE_KEY = "dummy-ssh-private-key-content"

_GIT_TARGET = {
    "isAvailable": True,
    "isEnabled": True,
    "key": "git",
    "title": "Git",
    "description": "Synchronize with a Git repository.",
    "logo": "https://wiki.example.com/svg/logo-git.svg",
    "website": "https://git-scm.com/",
    "supportedModes": ["sync", "push", "pull"],
    "mode": "sync",
    "hasSchedule": True,
    "syncInterval": "P2D",
    "syncIntervalDefault": "PT5M",
    "config": [
        {"key": "authType", "value": "ssh"},
        {"key": "repoUrl", "value": "git@github.com:example/wiki-content.git"},
        {"key": "branch", "value": "master"},
        {"key": "basicPassword", "value": _DUMMY_BASIC_PASSWORD},
        {"key": "sshPrivateKeyContent", "value": _DUMMY_SSH_PRIVATE_KEY},
    ],
    "actions": [
        {"handler": "sync", "label": "Force Sync", "hint": "Force a full synchronization."},
        {"handler": "syncUntracked", "label": "Sync Untracked", "hint": "Push untracked pages."},
        {"handler": "importAll", "label": "Import Everything", "hint": "Import from local repo."},
        {"handler": "purge", "label": "Purge Local Repository", "hint": "Delete local repo."},
    ],
}

_DISK_TARGET = {
    "isAvailable": True,
    "isEnabled": False,
    "key": "disk",
    "title": "Local File System",
    "description": "Local disk storage.",
    "logo": None,
    "website": None,
    "supportedModes": ["push"],
    "mode": "push",
    "hasSchedule": False,
    "syncInterval": None,
    "syncIntervalDefault": None,
    "config": [{"key": "path", "value": "/wiki-data"}],
    "actions": [],
}

_TARGETS_RESPONSE = {"data": {"storage": {"targets": [_GIT_TARGET, _DISK_TARGET]}}}

_STATUS_ENTRIES = [
    {
        "key": "git",
        "title": "Git",
        "status": "operational",
        "message": "Successfully synchronized.",
        "lastAttempt": "2026-08-14T02:00:00.000Z",
    },
    {
        "key": "disk",
        "title": "Local File System",
        "status": "pending",
        "message": "Handler is idle.",
        "lastAttempt": "2026-08-12T02:00:00.000Z",
    },
]

_STATUS_RESPONSE = {"data": {"storage": {"status": _STATUS_ENTRIES}}}

_EXECUTE_SUCCESS_RESPONSE = {
    "data": {
        "storage": {
            "executeAction": {
                "responseResult": {"succeeded": True, "errorCode": 0, "message": ""},
            }
        }
    }
}


async def test_storage_target_list_returns_all_targets(mcp: FastMCP, respx_mock) -> None:
    """Seluruh target dikembalikan (bukan hanya `git`), lengkap dengan `actions`."""
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=_TARGETS_RESPONSE))

    data = await call_tool(mcp, "wikijs_storage_target_list", {})

    targets = data["targets"]
    assert [target["key"] for target in targets] == ["git", "disk"]
    git = targets[0]
    assert git["mode"] == "sync"
    assert git["syncInterval"] == "P2D"
    assert git["hasSchedule"] is True
    assert git["supportedModes"] == ["sync", "push", "pull"]
    assert [action["handler"] for action in git["actions"]] == [
        "sync",
        "syncUntracked",
        "importAll",
        "purge",
    ]


async def test_storage_target_list_redacts_credentials(mcp: FastMCP, respx_mock) -> None:
    """`basicPassword` & `sshPrivateKeyContent` jadi '***'; key non-rahasia tetap utuh."""
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=_TARGETS_RESPONSE))

    data = await call_tool(mcp, "wikijs_storage_target_list", {})

    config = {entry["key"]: entry["value"] for entry in data["targets"][0]["config"]}
    assert config["basicPassword"] == "***"
    assert config["sshPrivateKeyContent"] == "***"
    assert config["repoUrl"] == "git@github.com:example/wiki-content.git"
    assert config["branch"] == "master"
    assert config["authType"] == "ssh"

    serialized = json.dumps(data)
    assert _DUMMY_BASIC_PASSWORD not in serialized
    assert _DUMMY_SSH_PRIVATE_KEY not in serialized


async def test_storage_target_list_does_not_mutate_other_targets(mcp: FastMCP, respx_mock) -> None:
    """Target tanpa key rahasia diteruskan apa adanya (sensor berbasis nama key)."""
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=_TARGETS_RESPONSE))

    data = await call_tool(mcp, "wikijs_storage_target_list", {})

    assert data["targets"][1]["config"] == [{"key": "path", "value": "/wiki-data"}]
    assert data["targets"][1]["actions"] == []


async def test_storage_target_list_empty(mcp: FastMCP, respx_mock) -> None:
    """`targets` null dari Wiki.js → daftar kosong, bukan error."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"storage": {"targets": None}}})
    )

    data = await call_tool(mcp, "wikijs_storage_target_list", {})

    assert data == {"targets": []}


async def test_storage_target_list_forbidden(mcp: FastMCP, respx_mock) -> None:
    """HTTP 403 (API key tanpa hak manage:system) → WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_storage_target_list", {})
    assert "403" in str(exc.value) or "ditolak" in str(exc.value).lower()


async def test_storage_status_success(mcp: FastMCP, respx_mock) -> None:
    """Daftar status terbawa apa adanya, termasuk `lastAttempt` & `message`."""
    respx_mock.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=_STATUS_RESPONSE))

    data = await call_tool(mcp, "wikijs_storage_status", {})

    assert data == {"status": _STATUS_ENTRIES}


async def test_storage_status_empty(mcp: FastMCP, respx_mock) -> None:
    """`status` null dari Wiki.js → daftar kosong, bukan error."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"storage": {"status": None}}})
    )

    data = await call_tool(mcp, "wikijs_storage_status", {})

    assert data == {"status": []}


async def test_storage_status_forbidden(mcp: FastMCP, respx_mock) -> None:
    """HTTP 403 pada tool status juga diangkat jadi WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_storage_status", {})
    assert "403" in str(exc.value) or "ditolak" in str(exc.value).lower()


async def test_storage_action_execute_force_sync(mcp: FastMCP, respx_mock) -> None:
    """Force Sync: variabel targetKey/handler terkirim persis, hasil status 'executed'."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_EXECUTE_SUCCESS_RESPONSE)
    )

    data = await call_tool(
        mcp, "wikijs_storage_action_execute", {"target_key": "git", "handler": "sync"}
    )

    assert data == {"status": "executed", "target_key": "git", "handler": "sync"}
    assert route.called
    variables = json.loads(route.calls.last.request.content)["variables"]
    assert variables == {"targetKey": "git", "handler": "sync"}


async def test_storage_action_execute_passes_handler_verbatim(mcp: FastMCP, respx_mock) -> None:
    """Handler destruktif tidak di-daftar-putih lokal — diteruskan apa adanya ke Wiki.js."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_EXECUTE_SUCCESS_RESPONSE)
    )

    data = await call_tool(
        mcp, "wikijs_storage_action_execute", {"target_key": "git", "handler": "purge"}
    )

    assert data == {"status": "executed", "target_key": "git", "handler": "purge"}
    variables = json.loads(route.calls.last.request.content)["variables"]
    assert variables["handler"] == "purge"


async def test_storage_action_execute_failed(mcp: FastMCP, respx_mock) -> None:
    """responseResult.succeeded=false (mis. handler tak dikenal) → WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "storage": {
                        "executeAction": {
                            "responseResult": {
                                "succeeded": False,
                                "errorCode": 6001,
                                "message": "Invalid Storage Handler",
                            }
                        }
                    }
                }
            },
        )
    )

    with pytest.raises(Exception) as exc:
        await call_tool(
            mcp, "wikijs_storage_action_execute", {"target_key": "git", "handler": "bogus"}
        )
    assert "Invalid Storage Handler" in str(exc.value)


async def test_storage_action_execute_forbidden(mcp: FastMCP, respx_mock) -> None:
    """HTTP 403 (API key tanpa hak manage:system) → WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )

    with pytest.raises(Exception) as exc:
        await call_tool(
            mcp, "wikijs_storage_action_execute", {"target_key": "git", "handler": "sync"}
        )
    assert "403" in str(exc.value) or "ditolak" in str(exc.value).lower()


@pytest.mark.parametrize(
    "target_key, handler, expected_message",
    [
        ("", "sync", "target_key"),
        ("   ", "sync", "target_key"),
        ("git", "", "handler"),
        ("git", "   ", "handler"),
    ],
)
async def test_storage_action_execute_validation_errors(
    mcp: FastMCP, respx_mock, target_key: str, handler: str, expected_message: str
) -> None:
    """target_key/handler kosong atau whitespace → ValueError tanpa request HTTP."""
    route = respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_EXECUTE_SUCCESS_RESPONSE)
    )

    with pytest.raises(Exception) as exc:
        await call_tool(
            mcp,
            "wikijs_storage_action_execute",
            {"target_key": target_key, "handler": handler},
        )
    assert expected_message in str(exc.value)
    assert not route.called


async def test_storage_tools_registered_with_tag(mcp: FastMCP) -> None:
    """Ketiga tool storage terdaftar di server MCP dan bertag `storage`."""
    tools = {tool.name: tool for tool in await mcp.list_tools()}

    expected = {
        "wikijs_storage_target_list",
        "wikijs_storage_status",
        "wikijs_storage_action_execute",
    }
    assert expected <= set(tools)
    for name in expected:
        assert "storage" in tools[name].tags
