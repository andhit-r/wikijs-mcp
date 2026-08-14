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
    """Keempat tool storage terdaftar di server MCP dan bertag `storage`."""
    tools = {tool.name: tool for tool in await mcp.list_tools()}

    expected = {
        "wikijs_storage_target_list",
        "wikijs_storage_status",
        "wikijs_storage_action_execute",
        "wikijs_storage_target_update",
    }
    assert expected <= set(tools)
    for name in expected:
        assert "storage" in tools[name].tags


# ---------------------------------------------------------------------------
# wikijs_storage_target_update (andhit-r/wikijs-mcp#9)
#
# Alur read-modify-write memakai DUA request berurutan: query storage.targets
# lalu mutation storage.updateTargets. Karena kedua request menuju URL yang
# sama, mock-nya memakai `side_effect` berisi daftar respons berurutan.
# ---------------------------------------------------------------------------

_UPDATE_SUCCESS_RESPONSE = {
    "data": {
        "storage": {
            "updateTargets": {
                "responseResult": {"succeeded": True, "errorCode": 0, "message": ""},
            }
        }
    }
}


def _mock_read_then_write(respx_mock, write_response: dict | None = None):
    """Pasang mock dua tahap: query targets, lalu mutation updateTargets.

    Args:
        respx_mock: Fixture router respx aktif.
        write_response: Body JSON untuk request kedua (mutation). Default
            :data:`_UPDATE_SUCCESS_RESPONSE`.

    Returns:
        Route respx yang terpasang, agar test bisa memeriksa
        ``route.calls`` (jumlah request dan isi variabelnya).
    """
    return respx_mock.post(GRAPHQL_URL).mock(
        side_effect=[
            httpx.Response(200, json=_TARGETS_RESPONSE),
            httpx.Response(200, json=write_response or _UPDATE_SUCCESS_RESPONSE),
        ]
    )


def _sent_target(route) -> dict:
    """Ambil satu-satunya entri `targets` dari variabel mutation terakhir."""
    variables = json.loads(route.calls.last.request.content)["variables"]
    assert len(variables["targets"]) == 1
    return variables["targets"][0]


async def test_storage_target_update_merges_config_per_key(mcp: FastMCP, respx_mock) -> None:
    """`config={"branch": ...}` mengirim ulang SELURUH key lama, hanya `branch` berubah."""
    route = _mock_read_then_write(respx_mock)

    data = await call_tool(
        mcp,
        "wikijs_storage_target_update",
        {"target_key": "git", "config": {"branch": "main"}},
    )

    assert data == {"status": "updated", "target_key": "git"}
    assert len(route.calls) == 2
    sent = _sent_target(route)
    sent_config = {entry["key"]: entry["value"] for entry in sent["config"]}
    assert set(sent_config) == {
        "authType",
        "repoUrl",
        "branch",
        "basicPassword",
        "sshPrivateKeyContent",
    }
    assert sent_config["branch"] == "main"
    assert sent_config["repoUrl"] == "git@github.com:example/wiki-content.git"
    assert sent_config["authType"] == "ssh"


async def test_storage_target_update_sends_unredacted_credentials(mcp: FastMCP, respx_mock) -> None:
    """Kredensial dikirim ulang dengan nilai ASLI dari query, bukan sentinel '***'."""
    route = _mock_read_then_write(respx_mock)

    await call_tool(
        mcp,
        "wikijs_storage_target_update",
        {"target_key": "git", "config": {"branch": "main"}},
    )

    sent_config = {entry["key"]: entry["value"] for entry in _sent_target(route)["config"]}
    assert sent_config["basicPassword"] == _DUMMY_BASIC_PASSWORD
    assert sent_config["sshPrivateKeyContent"] == _DUMMY_SSH_PRIVATE_KEY
    assert "***" not in sent_config.values()


async def test_storage_target_update_keeps_untouched_fields(mcp: FastMCP, respx_mock) -> None:
    """Hanya `sync_interval` diisi → isEnabled/mode/config identik dengan hasil query."""
    route = _mock_read_then_write(respx_mock)

    await call_tool(
        mcp,
        "wikijs_storage_target_update",
        {"target_key": "git", "sync_interval": "PT5M"},
    )

    sent = _sent_target(route)
    assert sent["syncInterval"] == "PT5M"
    assert sent["key"] == "git"
    assert sent["isEnabled"] is True
    assert sent["mode"] == "sync"
    assert sent["config"] == _GIT_TARGET["config"]


async def test_storage_target_update_disable_only(mcp: FastMCP, respx_mock) -> None:
    """`is_enabled=False` saja → sisa field target dikirim ulang apa adanya."""
    route = _mock_read_then_write(respx_mock)

    await call_tool(
        mcp,
        "wikijs_storage_target_update",
        {"target_key": "git", "is_enabled": False},
    )

    sent = _sent_target(route)
    assert sent["isEnabled"] is False
    assert sent["mode"] == "sync"
    assert sent["syncInterval"] == "P2D"
    assert sent["config"] == _GIT_TARGET["config"]


async def test_storage_target_update_mode_override(mcp: FastMCP, respx_mock) -> None:
    """`mode` yang diisi menimpa nilai bacaan, field lain tetap."""
    route = _mock_read_then_write(respx_mock)

    await call_tool(
        mcp,
        "wikijs_storage_target_update",
        {"target_key": "git", "mode": "push"},
    )

    sent = _sent_target(route)
    assert sent["mode"] == "push"
    assert sent["isEnabled"] is True
    assert sent["syncInterval"] == "P2D"


async def test_storage_target_update_unknown_config_key(mcp: FastMCP, respx_mock) -> None:
    """Key config asing → ValueError setelah query, TANPA mutation terkirim."""
    route = _mock_read_then_write(respx_mock)

    with pytest.raises(Exception) as exc:
        await call_tool(
            mcp,
            "wikijs_storage_target_update",
            {"target_key": "git", "config": {"brunch": "main"}},
        )

    assert "brunch" in str(exc.value)
    assert len(route.calls) == 1


async def test_storage_target_update_rejects_redacted_value(mcp: FastMCP, respx_mock) -> None:
    """Nilai '***' → ValueError tanpa request apa pun (query pun tidak perlu)."""
    route = _mock_read_then_write(respx_mock)

    with pytest.raises(Exception) as exc:
        await call_tool(
            mcp,
            "wikijs_storage_target_update",
            {"target_key": "git", "config": {"basicPassword": "***"}},
        )

    assert "***" in str(exc.value)
    assert not route.called


async def test_storage_target_update_unknown_target_key(mcp: FastMCP, respx_mock) -> None:
    """`target_key` tak ada di hasil query → ValueError, mutation tidak dikirim."""
    route = _mock_read_then_write(respx_mock)

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_storage_target_update", {"target_key": "s3"})

    assert "s3" in str(exc.value)
    assert len(route.calls) == 1


@pytest.mark.parametrize("target_key", ["", "   "])
async def test_storage_target_update_empty_target_key(
    mcp: FastMCP, respx_mock, target_key: str
) -> None:
    """`target_key` kosong/whitespace → ValueError tanpa request HTTP."""
    route = _mock_read_then_write(respx_mock)

    with pytest.raises(Exception) as exc:
        await call_tool(mcp, "wikijs_storage_target_update", {"target_key": target_key})

    assert "target_key" in str(exc.value)
    assert not route.called


async def test_storage_target_update_failed_response_result(mcp: FastMCP, respx_mock) -> None:
    """responseResult.succeeded=false → WikiJSAPIError."""
    _mock_read_then_write(
        respx_mock,
        {
            "data": {
                "storage": {
                    "updateTargets": {
                        "responseResult": {
                            "succeeded": False,
                            "errorCode": 6002,
                            "message": "Invalid Storage Target",
                        }
                    }
                }
            }
        },
    )

    with pytest.raises(Exception) as exc:
        await call_tool(
            mcp,
            "wikijs_storage_target_update",
            {"target_key": "git", "is_enabled": True},
        )

    assert "Invalid Storage Target" in str(exc.value)


async def test_storage_target_update_forbidden(mcp: FastMCP, respx_mock) -> None:
    """HTTP 403 pada tahap baca (API key tanpa manage:system) → WikiJSAPIError."""
    respx_mock.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )

    with pytest.raises(Exception) as exc:
        await call_tool(
            mcp,
            "wikijs_storage_target_update",
            {"target_key": "git", "is_enabled": True},
        )
    assert "403" in str(exc.value) or "ditolak" in str(exc.value).lower()


async def test_storage_target_update_does_not_echo_config(mcp: FastMCP, respx_mock) -> None:
    """Kembalian tidak meng-echo `config` agar kredensial tak nyangkut di transcript."""
    _mock_read_then_write(respx_mock)

    data = await call_tool(
        mcp,
        "wikijs_storage_target_update",
        {"target_key": "git", "config": {"repoUrl": "git@github.com:example/lain.git"}},
    )

    assert data == {"status": "updated", "target_key": "git"}
    assert "config" not in data
    assert "lain.git" not in json.dumps(data)
