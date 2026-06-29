"""Tool MCP untuk informasi sistem Wiki.js (domain ``system``).

Mendaftarkan tool: system_info.

# verifikasi terhadap versi Wiki.js target sebelum mengubah field GraphQL
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..client import WikiJSGraphQLClient


def register(mcp: FastMCP, client: WikiJSGraphQLClient) -> None:
    """Daftarkan seluruh tool domain system ke server MCP.

    Args:
        mcp: Instance FastMCP.
        client: Klien Wiki.js bersama.
    """

    @mcp.tool(tags={"system"})
    async def wikijs_system_info() -> dict[str, Any]:
        """Ambil informasi sistem Wiki.js (versi, platform, database).

        Berguna untuk uji koneksi dan diagnosis masalah. Mengembalikan informasi
        tentang versi Wiki.js yang berjalan, platform, tipe database, dan runtime.

        Returns:
            Dict berisi ``currentVersion``, ``latestVersion``, ``platform``,
            ``dbType``, ``operatingSystem``, ``nodeVersion``.

        Raises:
            WikiJSAPIError: Bila request GraphQL gagal atau API key tidak valid.
        """
        query = """
        query {
          system {
            info {
              currentVersion
              latestVersion
              platform
              dbType
              operatingSystem
              nodeVersion
            }
          }
        }
        """
        data = await client.execute(query, operation="system_info")
        return data.get("system", {}).get("info") or {}
