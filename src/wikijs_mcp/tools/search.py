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

        search_term = query.strip()

        # Nama variabel dokumen GraphQL sengaja bernama `query` (bukan mis.
        # `gql_query`) meski parameter tool juga bernama `query` (kata kunci
        # pencarian, sudah disimpan di `search_term` di atas) -- gate validasi
        # skema offline (tests/test_tools_schema.py, andhit-r/wikijs-mcp#5)
        # mengekstrak dokumen lewat AST dari assignment bernama persis
        # `query`/`mutation`; nama lain membuatnya tidak terekstrak sama sekali.
        query = """
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
        variables: dict[str, Any] = {"query": search_term}
        if path is not None:
            variables["path"] = path
        if locale is not None:
            variables["locale"] = locale

        data = await client.execute(query, variables, operation="page_search")
        return data.get("pages", {}).get(
            "search", {"results": [], "suggestions": [], "totalHits": 0}
        )
