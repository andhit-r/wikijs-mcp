"""Tool MCP untuk mengelola halaman Wiki.js (domain ``pages``).

Mendaftarkan tool: list, get, get_by_path, create, update, delete, move, render, tree.

Semua query/mutation menggunakan GraphQL Wiki.js 2.x. Mutation mengembalikan
``responseResult { succeeded errorCode message }`` — HTTP 200 + ``succeeded=false``
bukan sukses; divalidasi via :func:`_check_response_result`.

# verifikasi terhadap versi Wiki.js target sebelum mengubah field GraphQL
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..client import WikiJSGraphQLClient, _check_response_result

_SINGLE_FIELDS = (
    "id path title description content render contentType editor locale "
    "isPublished isPrivate tags { tag } authorName creatorName createdAt updatedAt"
)


def register(mcp: FastMCP, client: WikiJSGraphQLClient) -> None:
    """Daftarkan seluruh tool domain pages ke server MCP.

    Args:
        mcp: Instance FastMCP.
        client: Klien Wiki.js bersama.
    """

    @mcp.tool(tags={"pages"})
    async def wikijs_page_list(
        order_by: str = "TITLE",
    ) -> list[dict[str, Any]]:
        """Daftar semua halaman Wiki.js.

        Args:
            order_by: Urutan halaman. Nilai valid: ``TITLE``, ``PATH``,
                ``CREATED``, ``UPDATED``. Default ``TITLE``.

        Returns:
            Daftar dict halaman, tiap item berisi ``id``, ``path``, ``title``,
            ``locale``, ``contentType``, ``updatedAt``.

        Raises:
            WikiJSAPIError: Bila request GraphQL gagal.
            ValueError: Bila ``order_by`` tidak valid.
        """
        valid_orders = {"TITLE", "PATH", "CREATED", "UPDATED"}
        if order_by.upper() not in valid_orders:
            raise ValueError(f"order_by tidak valid: {order_by!r}. Pilih dari {valid_orders}.")

        query = """
        query($orderBy: PageOrderBy) {
          pages {
            list(orderBy: $orderBy) {
              id
              path
              title
              locale
              contentType
              updatedAt
            }
          }
        }
        """
        data = await client.execute(query, {"orderBy": order_by.upper()}, operation="page_list")
        return data.get("pages", {}).get("list", [])

    @mcp.tool(tags={"pages"})
    async def wikijs_page_get(page_id: int) -> dict[str, Any]:
        """Ambil detail satu halaman berdasarkan ID numerik.

        Args:
            page_id: ID numerik halaman Wiki.js.

        Returns:
            Objek halaman lengkap dengan konten, metadata, dan tags.

        Raises:
            WikiJSAPIError: 401/403 bila akses ditolak, atau GraphQL error.
            ValueError: Bila ``page_id`` tidak valid (≤ 0).
        """
        if page_id <= 0:
            raise ValueError(f"page_id harus positif, diterima: {page_id}")

        query = f"""
        query($id: Int!) {{
          pages {{
            single(id: $id) {{
              {_SINGLE_FIELDS}
            }}
          }}
        }}
        """
        data = await client.execute(query, {"id": page_id}, operation="page_get")
        return data.get("pages", {}).get("single") or {}

    @mcp.tool(tags={"pages"})
    async def wikijs_page_get_by_path(
        path: str,
        locale: str = "en",
    ) -> dict[str, Any]:
        """Ambil detail satu halaman berdasarkan path dan locale.

        Args:
            path: Path halaman Wiki.js (mis. ``folder/sub-folder/halaman``).
                Tanpa leading slash.
            locale: Kode locale halaman (mis. ``en``, ``id``). Default ``en``.

        Returns:
            Objek halaman lengkap dengan konten, metadata, dan tags.

        Raises:
            WikiJSAPIError: Bila halaman tidak ditemukan atau akses ditolak.
            ValueError: Bila ``path`` kosong.
        """
        if not path or not path.strip():
            raise ValueError("path tidak boleh kosong")

        query = f"""
        query($path: String!, $locale: String!) {{
          pages {{
            singleByPath(path: $path, locale: $locale) {{
              {_SINGLE_FIELDS}
            }}
          }}
        }}
        """
        data = await client.execute(
            query, {"path": path.strip("/"), "locale": locale}, operation="page_get_by_path"
        )
        return data.get("pages", {}).get("singleByPath") or {}

    @mcp.tool(tags={"pages"})
    async def wikijs_page_create(
        title: str,
        path: str,
        content: str,
        description: str = "",
        editor: str = "markdown",
        locale: str = "en",
        is_published: bool = True,
        is_private: bool = False,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Buat halaman baru di Wiki.js. Operasi ini bersifat permanen.

        Args:
            title: Judul halaman (wajib, non-kosong).
            path: Path halaman baru (mis. ``folder/nama-halaman``). Tanpa leading slash.
            content: Konten halaman dalam format sesuai ``editor`` (default markdown).
            description: Deskripsi singkat halaman. Default kosong.
            editor: Editor yang digunakan: ``markdown``, ``wysiwyg``, ``asciidoc``.
                Default ``markdown``.
            locale: Kode locale (mis. ``en``, ``id``). Default ``en``.
            is_published: Apakah halaman langsung dipublikasikan. Default ``True``.
            is_private: Apakah halaman bersifat privat. Default ``False``.
            tags: Daftar tag string. Default daftar kosong.

        Returns:
            Dict berisi ``id`` dan ``path`` halaman yang baru dibuat.

        Raises:
            WikiJSAPIError: Bila mutation gagal (mis. path sudah ada, izin kurang).
            ValueError: Bila ``title`` atau ``path`` kosong.
        """
        if not title or not title.strip():
            raise ValueError("title tidak boleh kosong")
        if not path or not path.strip():
            raise ValueError("path tidak boleh kosong")

        mutation = """
        mutation(
          $content: String!
          $description: String!
          $editor: String!
          $isPublished: Boolean!
          $isPrivate: Boolean!
          $locale: String!
          $path: String!
          $tags: [String]!
          $title: String!
        ) {
          pages {
            create(
              content: $content
              description: $description
              editor: $editor
              isPublished: $isPublished
              isPrivate: $isPrivate
              locale: $locale
              path: $path
              tags: $tags
              title: $title
            ) {
              responseResult { succeeded errorCode message }
              page { id path }
            }
          }
        }
        """
        variables = {
            "content": content,
            "description": description,
            "editor": editor,
            "isPublished": is_published,
            "isPrivate": is_private,
            "locale": locale,
            "path": path.strip("/"),
            "tags": tags or [],
            "title": title.strip(),
        }
        data = await client.execute(mutation, variables, operation="page_create")
        result = data.get("pages", {}).get("create", {})
        _check_response_result(result.get("responseResult", {}), "page_create")
        return result.get("page") or {}

    @mcp.tool(tags={"pages"})
    async def wikijs_page_update(
        page_id: int,
        content: str,
        title: str | None = None,
        description: str | None = None,
        editor: str | None = None,
        locale: str | None = None,
        is_published: bool | None = None,
        is_private: bool | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Perbarui halaman Wiki.js yang sudah ada. Operasi ini bersifat permanen.

        Wiki.js update mutation mengharuskan ``content`` selalu dikirim. Field lain
        bersifat opsional — bila tidak diisi, nilai lama dipertahankan Wiki.js.

        Args:
            page_id: ID numerik halaman yang akan diperbarui.
            content: Konten halaman baru (wajib selalu dikirim ke Wiki.js).
            title: Judul baru (opsional).
            description: Deskripsi baru (opsional).
            editor: Editor baru (opsional).
            locale: Locale baru (opsional).
            is_published: Status publikasi baru (opsional).
            is_private: Status privat baru (opsional).
            tags: Daftar tag baru — menggantikan semua tag lama (opsional).

        Returns:
            Dict berisi ``id`` dan ``path`` halaman setelah diperbarui.

        Raises:
            WikiJSAPIError: Bila mutation gagal atau halaman tidak ditemukan.
            ValueError: Bila ``page_id`` tidak valid.
        """
        if page_id <= 0:
            raise ValueError(f"page_id harus positif, diterima: {page_id}")

        mutation = """
        mutation(
          $id: Int!
          $content: String!
          $description: String
          $editor: String
          $isPublished: Boolean
          $isPrivate: Boolean
          $locale: String
          $tags: [String]
          $title: String
        ) {
          pages {
            update(
              id: $id
              content: $content
              description: $description
              editor: $editor
              isPublished: $isPublished
              isPrivate: $isPrivate
              locale: $locale
              tags: $tags
              title: $title
            ) {
              responseResult { succeeded errorCode message }
              page { id path }
            }
          }
        }
        """
        variables: dict[str, Any] = {"id": page_id, "content": content}
        if title is not None:
            variables["title"] = title
        if description is not None:
            variables["description"] = description
        if editor is not None:
            variables["editor"] = editor
        if locale is not None:
            variables["locale"] = locale
        if is_published is not None:
            variables["isPublished"] = is_published
        if is_private is not None:
            variables["isPrivate"] = is_private
        if tags is not None:
            variables["tags"] = tags

        data = await client.execute(mutation, variables, operation="page_update")
        result = data.get("pages", {}).get("update", {})
        _check_response_result(result.get("responseResult", {}), "page_update")
        return result.get("page") or {}

    @mcp.tool(tags={"pages"})
    async def wikijs_page_delete(page_id: int) -> dict[str, Any]:
        """Hapus halaman Wiki.js secara permanen. Operasi ini tidak dapat dibatalkan.

        Args:
            page_id: ID numerik halaman yang akan dihapus.

        Returns:
            Dict berisi ``status`` konfirmasi penghapusan.

        Raises:
            WikiJSAPIError: Bila mutation gagal atau halaman tidak ditemukan.
            ValueError: Bila ``page_id`` tidak valid.
        """
        if page_id <= 0:
            raise ValueError(f"page_id harus positif, diterima: {page_id}")

        mutation = """
        mutation($id: Int!) {
          pages {
            delete(id: $id) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        data = await client.execute(mutation, {"id": page_id}, operation="page_delete")
        result = data.get("pages", {}).get("delete", {})
        _check_response_result(result.get("responseResult", {}), "page_delete")
        return {"status": "deleted", "page_id": page_id}

    @mcp.tool(tags={"pages"})
    async def wikijs_page_move(
        page_id: int,
        destination_path: str,
        destination_locale: str = "en",
    ) -> dict[str, Any]:
        """Pindahkan halaman Wiki.js ke path/locale tujuan. Operasi ini permanen.

        Args:
            page_id: ID numerik halaman yang akan dipindahkan.
            destination_path: Path tujuan baru (mis. ``new-folder/page-name``).
                Tanpa leading slash.
            destination_locale: Locale tujuan. Default ``en``.

        Returns:
            Dict berisi ``status`` konfirmasi pemindahan.

        Raises:
            WikiJSAPIError: Bila mutation gagal atau path tujuan sudah ada.
            ValueError: Bila ``page_id`` atau ``destination_path`` tidak valid.
        """
        if page_id <= 0:
            raise ValueError(f"page_id harus positif, diterima: {page_id}")
        if not destination_path or not destination_path.strip():
            raise ValueError("destination_path tidak boleh kosong")

        mutation = """
        mutation($id: Int!, $destinationPath: String!, $destinationLocale: String!) {
          pages {
            move(
              id: $id
              destinationPath: $destinationPath
              destinationLocale: $destinationLocale
            ) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        variables = {
            "id": page_id,
            "destinationPath": destination_path.strip("/"),
            "destinationLocale": destination_locale,
        }
        data = await client.execute(mutation, variables, operation="page_move")
        result = data.get("pages", {}).get("move", {})
        _check_response_result(result.get("responseResult", {}), "page_move")
        return {"status": "moved", "page_id": page_id, "destination_path": destination_path}

    @mcp.tool(tags={"pages"})
    async def wikijs_page_render(page_id: int) -> dict[str, Any]:
        """Render ulang HTML halaman Wiki.js dari konten sumbernya.

        Berguna setelah memperbarui konten secara manual atau setelah perubahan
        template/konfigurasi renderer.

        Args:
            page_id: ID numerik halaman yang akan di-render ulang.

        Returns:
            Dict berisi ``status`` konfirmasi render.

        Raises:
            WikiJSAPIError: Bila mutation gagal.
            ValueError: Bila ``page_id`` tidak valid.
        """
        if page_id <= 0:
            raise ValueError(f"page_id harus positif, diterima: {page_id}")

        mutation = """
        mutation($id: Int!) {
          pages {
            render(id: $id) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        data = await client.execute(mutation, {"id": page_id}, operation="page_render")
        result = data.get("pages", {}).get("render", {})
        _check_response_result(result.get("responseResult", {}), "page_render")
        return {"status": "rendered", "page_id": page_id}

    @mcp.tool(tags={"pages"})
    async def wikijs_page_tree(
        path: str = "",
        mode: str = "ALL",
        locale: str = "en",
        parent: int | None = None,
    ) -> list[dict[str, Any]]:
        """Ambil pohon halaman Wiki.js untuk navigasi hierarki.

        Args:
            path: Path root pohon (string kosong = root). Default ``""``.
            mode: Mode tampilan pohon: ``ALL`` (halaman + folder), ``PAGES``
                (halaman saja), ``FOLDERS`` (folder saja). Default ``ALL``.
            locale: Kode locale. Default ``en``.
            parent: ID halaman parent (opsional) untuk pembatasan sub-pohon.

        Returns:
            Daftar dict node pohon, tiap item berisi ``id``, ``path``, ``title``,
            ``isFolder``, ``pageId``, ``locale``.

        Raises:
            WikiJSAPIError: Bila request GraphQL gagal.
            ValueError: Bila ``mode`` tidak valid.
        """
        valid_modes = {"ALL", "PAGES", "FOLDERS"}
        if mode.upper() not in valid_modes:
            raise ValueError(f"mode tidak valid: {mode!r}. Pilih dari {valid_modes}.")

        query = """
        query($path: String!, $mode: PageTreeMode!, $locale: String!, $parent: Int) {
          pages {
            tree(path: $path, mode: $mode, locale: $locale, parent: $parent) {
              id
              path
              title
              isFolder
              pageId
              locale
            }
          }
        }
        """
        variables: dict[str, Any] = {
            "path": path,
            "mode": mode.upper(),
            "locale": locale,
        }
        if parent is not None:
            variables["parent"] = parent

        data = await client.execute(query, variables, operation="page_tree")
        return data.get("pages", {}).get("tree", [])
