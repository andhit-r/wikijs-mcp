"""Tool MCP untuk mengelola group (grup permission) Wiki.js (domain ``groups``).

Mendaftarkan tool: group_list, group_get, group_create, group_update,
group_delete, group_assign_user, group_unassign_user.

Semua query/mutation menggunakan GraphQL Wiki.js 2.x. Mutation mengembalikan
``responseResult { succeeded errorCode message }`` — HTTP 200 + ``succeeded=false``
bukan sukses; divalidasi via :func:`_check_response_result`.

Otorisasi sepenuhnya bergantung pada hak API key Wiki.js (``manage:groups``/grup
Administrators) — tidak ada pengecekan tambahan di level tool ini, identik pola
``mail.py``. HTTP 403 dari Wiki.js diteruskan apa adanya lewat ``WikiJSAPIError``.

# verifikasi terhadap versi Wiki.js target sebelum mengubah field GraphQL
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..client import WikiJSGraphQLClient, _check_response_result


def register(mcp: FastMCP, client: WikiJSGraphQLClient) -> None:
    """Daftarkan seluruh tool domain groups ke server MCP.

    Args:
        mcp: Instance FastMCP.
        client: Klien Wiki.js bersama.
    """

    @mcp.tool(tags={"groups"})
    async def wikijs_group_list() -> list[dict[str, Any]]:
        """Ambil daftar semua group (grup permission) Wiki.js.

        Returns:
            Daftar dict group, tiap item berisi ``id``, ``name``, ``isSystem``,
            ``userCount``, ``createdAt``, ``updatedAt``.

        Raises:
            WikiJSAPIError: Bila request GraphQL gagal (mis. HTTP 403 karena API
                key tanpa hak ``manage:groups``).
        """
        query = """
        query {
          groups {
            list {
              id
              name
              isSystem
              userCount
              createdAt
              updatedAt
            }
          }
        }
        """
        data = await client.execute(query, operation="group_list")
        return data.get("groups", {}).get("list", [])

    @mcp.tool(tags={"groups"})
    async def wikijs_group_get(group_id: int) -> dict[str, Any] | None:
        """Ambil detail satu group berdasarkan ID numerik.

        Args:
            group_id: ID numerik group Wiki.js. Wajib bilangan bulat positif.

        Returns:
            Dict detail group berisi ``id``, ``name``, ``isSystem``,
            ``redirectOnLogin``, ``permissions``, ``pageRules``, ``userCount``,
            ``createdAt``, ``updatedAt``. Mengembalikan ``None`` bila group
            dengan ``group_id`` tersebut tidak ditemukan.

        Raises:
            ValueError: Bila ``group_id`` bukan bilangan bulat positif (``<= 0``).
                Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila request GraphQL gagal (mis. HTTP 403).
        """
        if group_id <= 0:
            raise ValueError(f"group_id harus positif, diterima: {group_id}")

        query = """
        query($id: Int!) {
          groups {
            single(id: $id) {
              id
              name
              isSystem
              redirectOnLogin
              permissions
              pageRules
              userCount
              createdAt
              updatedAt
            }
          }
        }
        """
        data = await client.execute(query, {"id": group_id}, operation="group_get")
        return data.get("groups", {}).get("single")

    @mcp.tool(tags={"groups"})
    async def wikijs_group_create(name: str) -> dict[str, Any]:
        """Buat group baru di Wiki.js.

        Args:
            name: Nama group baru. Wajib diisi (tidak boleh kosong/whitespace).

        Returns:
            Dict berisi ``id`` dan ``name`` group yang baru dibuat.

        Raises:
            ValueError: Bila ``name`` kosong/whitespace. Dilempar sebelum ada
                request HTTP terkirim.
            WikiJSAPIError: Bila mutation gagal (mis. nama sudah dipakai, izin
                kurang) atau HTTP 403.
        """
        if not name or not name.strip():
            raise ValueError("name tidak boleh kosong")

        mutation = """
        mutation($name: String!) {
          groups {
            create(name: $name) {
              responseResult { succeeded errorCode message }
              group { id name }
            }
          }
        }
        """
        data = await client.execute(mutation, {"name": name}, operation="group_create")
        result = data.get("groups", {}).get("create", {})
        _check_response_result(result.get("responseResult", {}), "group_create")
        return result.get("group") or {}

    @mcp.tool(tags={"groups"})
    async def wikijs_group_update(
        group_id: int,
        name: str | None = None,
        redirect_on_login: str | None = None,
        permissions: list[str] | None = None,
        page_rules: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Perbarui sebagian field sebuah group Wiki.js yang sudah ada.

        BEDA DENGAN ``wikijs_mail_update_config`` (REPLACE-ALL): mutation
        ``groups.update`` di Wiki.js bersifat **patch-per-field**. Parameter
        opsional yang tidak diisi (``None``) **tidak dikirim** sama sekali
        sebagai variabel GraphQL — bukan dikirim sebagai ``null`` — sehingga
        nilai lama pada field tersebut tetap dipertahankan Wiki.js. Untuk
        menghapus/mengosongkan sebuah field, kirim nilai eksplisit yang sesuai
        (mis. ``permissions=[]``), bukan biarkan default ``None``.

        Args:
            group_id: ID numerik group yang akan diperbarui. Wajib bilangan
                bulat positif.
            redirect_on_login: Path redirect setelah login untuk anggota group
                ini. ``None`` (default) berarti tidak diubah.
            name: Nama baru group. ``None`` (default) berarti tidak diubah.
            permissions: Daftar string kode permission baru. ``None`` (default)
                berarti tidak diubah. Diteruskan apa adanya ke Wiki.js.
            page_rules: Daftar dict aturan halaman (``PageRuleInput``) baru.
                ``None`` (default) berarti tidak diubah. Diteruskan apa adanya
                ke Wiki.js — penyusunan page rule bukan tanggung jawab tool ini.

        Returns:
            Dict ``{"status": "updated"}``.

        Raises:
            ValueError: Bila ``group_id`` bukan bilangan bulat positif
                (``<= 0``). Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila mutation gagal atau group tidak ditemukan.
        """
        if group_id <= 0:
            raise ValueError(f"group_id harus positif, diterima: {group_id}")

        mutation = """
        mutation(
          $id: Int!
          $name: String
          $redirectOnLogin: String
          $permissions: [String]
          $pageRules: [PageRuleInput]
        ) {
          groups {
            update(
              id: $id
              name: $name
              redirectOnLogin: $redirectOnLogin
              permissions: $permissions
              pageRules: $pageRules
            ) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        variables: dict[str, Any] = {"id": group_id}
        if name is not None:
            variables["name"] = name
        if redirect_on_login is not None:
            variables["redirectOnLogin"] = redirect_on_login
        if permissions is not None:
            variables["permissions"] = permissions
        if page_rules is not None:
            variables["pageRules"] = page_rules

        data = await client.execute(mutation, variables, operation="group_update")
        result = data.get("groups", {}).get("update", {})
        _check_response_result(result.get("responseResult", {}), "group_update")
        return {"status": "updated"}

    @mcp.tool(tags={"groups"})
    async def wikijs_group_delete(group_id: int) -> dict[str, Any]:
        """Hapus group Wiki.js secara permanen. Operasi ini tidak dapat dibatalkan.

        Args:
            group_id: ID numerik group yang akan dihapus. Wajib bilangan bulat
                positif.

        Returns:
            Dict ``{"status": "deleted", "group_id": group_id}``.

        Raises:
            ValueError: Bila ``group_id`` bukan bilangan bulat positif
                (``<= 0``). Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila mutation gagal (mis. group sistem yang tidak
                boleh dihapus) atau group tidak ditemukan.
        """
        if group_id <= 0:
            raise ValueError(f"group_id harus positif, diterima: {group_id}")

        mutation = """
        mutation($id: Int!) {
          groups {
            delete(id: $id) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        data = await client.execute(mutation, {"id": group_id}, operation="group_delete")
        result = data.get("groups", {}).get("delete", {})
        _check_response_result(result.get("responseResult", {}), "group_delete")
        return {"status": "deleted", "group_id": group_id}

    @mcp.tool(tags={"groups"})
    async def wikijs_group_assign_user(group_id: int, user_id: int) -> dict[str, Any]:
        """Tambahkan seorang user sebagai anggota sebuah group Wiki.js.

        Args:
            group_id: ID numerik group tujuan. Wajib bilangan bulat positif.
            user_id: ID numerik user yang akan ditambahkan. Wajib bilangan
                bulat positif.

        Returns:
            Dict ``{"status": "assigned", "group_id": group_id, "user_id": user_id}``.

        Raises:
            ValueError: Bila ``group_id`` atau ``user_id`` bukan bilangan bulat
                positif (``<= 0``). Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila mutation gagal atau group/user tidak ditemukan.
        """
        if group_id <= 0:
            raise ValueError(f"group_id harus positif, diterima: {group_id}")
        if user_id <= 0:
            raise ValueError(f"user_id harus positif, diterima: {user_id}")

        mutation = """
        mutation($groupId: Int!, $userId: Int!) {
          groups {
            assignUser(groupId: $groupId, userId: $userId) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        variables = {"groupId": group_id, "userId": user_id}
        data = await client.execute(mutation, variables, operation="group_assign_user")
        result = data.get("groups", {}).get("assignUser", {})
        _check_response_result(result.get("responseResult", {}), "group_assign_user")
        return {"status": "assigned", "group_id": group_id, "user_id": user_id}

    @mcp.tool(tags={"groups"})
    async def wikijs_group_unassign_user(group_id: int, user_id: int) -> dict[str, Any]:
        """Cabut keanggotaan seorang user dari sebuah group Wiki.js.

        Args:
            group_id: ID numerik group asal. Wajib bilangan bulat positif.
            user_id: ID numerik user yang akan dicabut keanggotaannya. Wajib
                bilangan bulat positif.

        Returns:
            Dict ``{"status": "unassigned", "group_id": group_id, "user_id": user_id}``.

        Raises:
            ValueError: Bila ``group_id`` atau ``user_id`` bukan bilangan bulat
                positif (``<= 0``). Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila mutation gagal atau group/user tidak ditemukan.
        """
        if group_id <= 0:
            raise ValueError(f"group_id harus positif, diterima: {group_id}")
        if user_id <= 0:
            raise ValueError(f"user_id harus positif, diterima: {user_id}")

        mutation = """
        mutation($groupId: Int!, $userId: Int!) {
          groups {
            unassignUser(groupId: $groupId, userId: $userId) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        variables = {"groupId": group_id, "userId": user_id}
        data = await client.execute(mutation, variables, operation="group_unassign_user")
        result = data.get("groups", {}).get("unassignUser", {})
        _check_response_result(result.get("responseResult", {}), "group_unassign_user")
        return {"status": "unassigned", "group_id": group_id, "user_id": user_id}
