"""Fixture dan helper bersama untuk unit test wikijs-mcp.

Seluruh test memakai mock HTTP (``respx``) sehingga TIDAK pernah memanggil
instance Wiki.js sungguhan. Base URL Wiki.js di-set ke domain contoh tetap
``https://wiki.example.com``.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client, FastMCP

from wikijs_mcp.client import WikiJSGraphQLClient
from wikijs_mcp.config import Settings
from wikijs_mcp.server import create_server

BASE_URL = "https://wiki.example.com"
GRAPHQL_URL = f"{BASE_URL}/graphql"


def make_settings(**overrides: Any) -> Settings:
    """Bangun objek ``Settings`` untuk test dengan nilai default yang aman.

    Args:
        **overrides: Field yang ingin di-override dari default test.

    Returns:
        Instance ``Settings`` siap pakai (tidak membaca ``.env``).
    """
    defaults: dict[str, Any] = {
        "wikijs_url": BASE_URL,
        "wikijs_api_key": "test-api-key",
        "authentik_base_url": "",
        "authentik_app_slug": "",
        "authentik_client_id": "",
        "authentik_client_secret": "",
        "mcp_api_key": "",
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


@pytest.fixture
def settings() -> Settings:
    """Fixture ``Settings`` standar untuk test."""
    return make_settings()


@pytest.fixture
async def wiki_client(settings: Settings) -> WikiJSGraphQLClient:
    """Fixture ``WikiJSGraphQLClient`` yang siap dimock dengan respx."""
    c = WikiJSGraphQLClient(settings)
    try:
        yield c
    finally:
        await c.aclose()


@pytest.fixture
def mcp(settings: Settings) -> FastMCP:
    """Fixture instance FastMCP yang sudah terkonfigurasi penuh untuk test."""
    return create_server(settings)


async def call_tool(mcp_server: FastMCP, name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Panggil sebuah tool MCP melalui transport in-memory dan kembalikan datanya.

    Args:
        mcp_server: Instance FastMCP.
        name: Nama tool yang dipanggil.
        arguments: Argumen tool.

    Returns:
        Data hasil tool (``CallToolResult.data``).

    Raises:
        Exception: Bila tool gagal (mis. ``WikiJSAPIError`` dibungkus ToolError).
    """
    async with Client(mcp_server) as c:
        result = await c.call_tool(name, arguments or {})
        return result.data
