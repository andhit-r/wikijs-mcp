"""Tool MCP untuk mengelola tag Wiki.js (domain ``tags``).

Mendaftarkan tool: tag_list, page_list_by_tags.

Catatan: ``pages.byTags`` mungkin tidak tersedia di semua versi Wiki.js 2.x.
Bila tidak tersedia, ``wikijs_page_list_by_tags`` menggunakan fallback berupa
mengambil semua halaman lalu memfilter berdasarkan tag secara lokal.

# verifikasi terhadap versi Wiki.js target sebelum mengubah field GraphQL
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..client import WikiJSGraphQLClient


def register(mcp: FastMCP, client: WikiJSGraphQLClient) -> None:
    """Daftarkan seluruh tool domain tags ke server MCP.

    Args:
        mcp: Instance FastMCP.
        client: Klien Wiki.js bersama.
    """

    @mcp.tool(tags={"tags"})
    async def wikijs_tag_list() -> list[dict[str, Any]]:
        """Ambil daftar semua tag yang ada di Wiki.js.

        Returns:
            Daftar dict tag, tiap item berisi ``id``, ``tag``, ``title``,
            ``createdAt``, ``updatedAt``.

        Raises:
            WikiJSAPIError: Bila request GraphQL gagal.
        """
        query = """
        query {
          pages {
            tags {
              id
              tag
              title
              createdAt
              updatedAt
            }
          }
        }
        """
        data = await client.execute(query, operation="tag_list")
        return data.get("pages", {}).get("tags", [])

    @mcp.tool(tags={"tags"})
    async def wikijs_page_list_by_tags(
        tags: list[str],
        locale: str | None = None,
    ) -> list[dict[str, Any]]:
        """Daftar halaman Wiki.js yang memiliki semua tag yang ditentukan.

        Menggunakan query ``pages.list`` lalu memfilter berdasarkan tag secara lokal,
        karena ketersediaan ``pages.byTags`` bervariasi antar versi Wiki.js 2.x.

        Args:
            tags: Daftar string tag yang harus dimiliki halaman (AND semantics).
                Wajib non-kosong.
            locale: Filter berdasarkan locale (opsional). Bila diisi, hanya
                halaman dengan locale tersebut yang dikembalikan.

        Returns:
            Daftar dict halaman yang memiliki semua tag yang diminta, berisi
            ``id``, ``path``, ``title``, ``locale``, ``contentType``, ``updatedAt``.

        Raises:
            WikiJSAPIError: Bila request GraphQL gagal.
            ValueError: Bila ``tags`` kosong.
        """
        if not tags:
            raise ValueError("Daftar tags tidak boleh kosong")

        query = """
        query {
          pages {
            list(orderBy: TITLE) {
              id
              path
              title
              locale
              contentType
              updatedAt
              tags { tag }
            }
          }
        }
        """
        data = await client.execute(query, operation="page_list_by_tags")
        all_pages = data.get("pages", {}).get("list", [])

        target_tags = {t.lower().strip() for t in tags if t.strip()}

        result = []
        for page in all_pages:
            if locale and page.get("locale") != locale:
                continue
            page_tags = {t.get("tag", "").lower().strip() for t in (page.get("tags") or [])}
            if target_tags.issubset(page_tags):
                page_out = {k: v for k, v in page.items() if k != "tags"}
                result.append(page_out)

        return result
