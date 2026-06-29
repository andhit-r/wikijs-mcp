"""Tool MCP untuk pencarian halaman Wiki.js (domain ``search``).

Mendaftarkan tool: page_search.

# verifikasi terhadap versi Wiki.js target sebelum mengubah field GraphQL
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..client import WikiJSGraphQLClient


def register(mcp: FastMCP, client: WikiJSGraphQLClient) -> None:
    """Daftarkan seluruh tool domain search ke server MCP.

    Args:
        mcp: Instance FastMCP.
        client: Klien Wiki.js bersama.
    """

    @mcp.tool(tags={"search"})
    async def wikijs_page_search(
        query: str,
        path: str | None = None,
        locale: str | None = None,
    ) -> dict[str, Any]:
        """Cari halaman Wiki.js menggunakan full-text search.

        Args:
            query: Kata kunci pencarian (wajib, non-kosong).
            path: Filter hasil pada path tertentu (opsional).
                Mis. ``folder/sub-folder`` akan membatasi hasil di bawah path itu.
            locale: Filter berdasarkan locale (opsional). Mis. ``en``, ``id``.

        Returns:
            Dict berisi:
            - ``results``: daftar dict halaman cocok (``id``, ``title``,
              ``description``, ``path``, ``locale``).
            - ``suggestions``: daftar string saran kata kunci.
            - ``totalHits``: total jumlah dokumen cocok.

        Raises:
            WikiJSAPIError: Bila request GraphQL gagal.
            ValueError: Bila ``query`` kosong.
        """
        if not query or not query.strip():
            raise ValueError("query pencarian tidak boleh kosong")

        gql_query = """
        query($query: String!, $path: String, $locale: String) {
          pages {
            search(query: $query, path: $path, locale: $locale) {
              results {
                id
                title
                description
                path
                locale
              }
              suggestions
              totalHits
            }
          }
        }
        """
        variables: dict[str, Any] = {"query": query.strip()}
        if path is not None:
            variables["path"] = path
        if locale is not None:
            variables["locale"] = locale

        data = await client.execute(gql_query, variables, operation="page_search")
        return data.get("pages", {}).get(
            "search", {"results": [], "suggestions": [], "totalHits": 0}
        )
