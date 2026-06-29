"""Smoke test ASGI app (Streamable HTTP + /health).

Menjaga dua regresi yang pernah membuat deployment gagal:

1. ``/health`` HARUS ada — kalau hilang, health check Docker/Compose selalu
   ``unhealthy`` (``mcp.http_app()`` tidak menyediakan endpoint ini).
2. ``lifespan`` MCP HARUS dioper ke Starlette — kalau tidak, request MCP pertama
   crash ``RuntimeError: Task group is not initialized``.

``TestClient`` dipakai sebagai context manager agar lifespan (startup/shutdown)
ikut dijalankan — itulah yang menginisialisasi ``StreamableHTTPSessionManager``.

Catatan: test ini mengasumsikan variabel env WIKIJS_URL dan WIKIJS_API_KEY diisi
dari conftest (via environment WIKIJS_URL=https://wiki.example.com, dll.).
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def set_wikijs_env(monkeypatch):
    """Set env vars minimum agar asgi.py dapat diinisialisasi."""
    monkeypatch.setenv("WIKIJS_URL", "https://wiki.example.com")
    monkeypatch.setenv("WIKIJS_API_KEY", "test-api-key")


def test_health_ok():
    from wikijs_mcp.asgi import app

    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_mcp_initialize_tidak_crash_task_group():
    from wikijs_mcp.asgi import app

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "0"},
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    with TestClient(app) as client:
        resp = client.post("/mcp", json=payload, headers=headers, follow_redirects=True)
    assert resp.status_code == 200, resp.text
