"""Tool MCP untuk mengelola group (grup permission) Wiki.js (domain ``groups``).

Mendaftarkan tool: group_list, group_get, group_create, group_update,
group_delete, group_assign_user, group_unassign_user.

Semua query/mutation menggunakan GraphQL Wiki.js 2.x. Mutation mengembalikan
``responseResult { succeeded errorCode message }`` — HTTP 200 + ``succeeded=false``
bukan sukses; divalidasi via :func:`_check_response_result`.

Otorisasi sepenuhnya bergantung pada hak API key Wiki.js (``manage:groups``/grup
Administrators) — tidak ada pengecekan tambahan di level tool ini, identik pola
``mail.py``. HTTP 403 dari Wiki.js diteruskan apa adanya lewat ``WikiJSAPIError``.

Seluruh literal ``query``/``mutation`` di modul ini divalidasi otomatis di
``make test`` terhadap SDL Wiki.js 2.x yang di-commit
(``tests/schema/wikijs-2.x.graphql``, lihat ``tests/test_groups_schema.py``) —
lihat ``andhit-r/wikijs-mcp#4``. Field pada ``Group`` **berbeda** dari
``GroupMinimal`` (dipakai ``groups.list``): ``Group`` **tidak** punya
``userCount``, dan ``pageRules``-nya bertipe ``[PageRule]`` yang **wajib**
diseleksi dengan subfield.

# verifikasi terhadap versi Wiki.js target sebelum mengubah field GraphQL
"""

from __future__ import annotations

import uuid
from typing import Any

from fastmcp import FastMCP

from ..client import WikiJSAPIError, WikiJSGraphQLClient, _check_response_result

_VALID_PAGE_RULE_MATCH = {"START", "EXACT", "END", "REGEX", "TAG"}


def _validate_page_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """Validasi & normalisasi satu entri ``page_rules`` sebelum dikirim ke Wiki.js.

    Wiki.js mewajibkan tiap ``PageRuleInput`` memiliki ``id`` (string) meski
    pemanggil MCP tidak perlu tahu detail itu — bila ``id`` absen atau kosong,
    fungsi ini membangkitkannya otomatis dengan :func:`uuid.uuid4`.

    Args:
        rule: Satu entri page rule mentah dari pemanggil. Wajib memuat
            ``deny`` (bool), ``match`` (salah satu dari
            ``START``/``EXACT``/``END``/``REGEX``/``TAG``), ``roles`` (list),
            dan ``path`` (str). ``id`` dan ``locales`` opsional.

    Returns:
        Dict page rule yang sudah lengkap (termasuk ``id`` dan ``locales``)
        dan siap dipakai sebagai variabel GraphQL ``PageRuleInput``.

    Raises:
        ValueError: Bila salah satu field wajib hilang/bertipe salah, atau
            ``match`` bukan salah satu nilai enum yang valid.
    """
    if not isinstance(rule.get("deny"), bool):
        raise ValueError(f"page_rules: 'deny' wajib bool, diterima: {rule.get('deny')!r}")
    match = rule.get("match")
    if match not in _VALID_PAGE_RULE_MATCH:
        raise ValueError(
            "page_rules: 'match' harus salah satu dari "
            f"{sorted(_VALID_PAGE_RULE_MATCH)}, diterima: {match!r}"
        )
    roles = rule.get("roles")
    if not isinstance(roles, list):
        raise ValueError(f"page_rules: 'roles' wajib list, diterima: {roles!r}")
    path = rule.get("path")
    if not isinstance(path, str):
        raise ValueError(f"page_rules: 'path' wajib str, diterima: {path!r}")

    return {
        "id": rule.get("id") or str(uuid.uuid4()),
        "deny": rule["deny"],
        "match": match,
        "roles": roles,
        "path": path,
        "locales": rule.get("locales") or [],
    }


def register(mcp: FastMCP, client: WikiJSGraphQLClient) -> None:
    """Daftarkan seluruh tool domain groups ke server MCP.

    Args:
        mcp: Instance FastMCP.
        client: Klien Wiki.js bersama.
    """

    async def _fetch_current_for_update(group_id: int) -> dict[str, Any]:
        """Baca state group saat ini untuk read-modify-write ``groups.update``.

        Dipanggil dari :func:`wikijs_group_update` hanya ketika ada argumen
        opsional yang bernilai ``None`` — mutation ``groups.update`` Wiki.js
        bersifat REPLACE-ALL (kelima argumen non-null), sehingga nilai yang
        tidak diisi pemanggil perlu dibaca dulu agar tidak tertimpa kosong.

        Args:
            group_id: ID numerik group yang sedang diperbarui.

        Returns:
            Dict berisi ``name``, ``redirectOnLogin``, ``permissions``, dan
            ``pageRules`` (masing-masing dengan subfield
            ``id deny match roles path locales``) milik group saat ini.

        Raises:
            WikiJSAPIError: Bila group dengan ``group_id`` tersebut tidak
                ditemukan (``groups.single`` mengembalikan ``null``) —
                dilempar sebelum mutation ``groups.update`` dikirim — atau
                bila request GraphQL itu sendiri gagal (mis. HTTP 403).
        """
        query = """
        query($id: Int!) {
          groups {
            single(id: $id) {
              name
              redirectOnLogin
              permissions
              pageRules { id deny match roles path locales }
            }
          }
        }
        """
        data = await client.execute(query, {"id": group_id}, operation="group_update")
        current = data.get("groups", {}).get("single")
        if current is None:
            raise WikiJSAPIError(
                f"Group dengan id={group_id} tidak ditemukan (operasi: group_update)",
                operation="group_update",
            )
        return current

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
            ``redirectOnLogin``, ``permissions``, ``pageRules`` (list dict
            dengan ``id deny match roles path locales``), ``createdAt``,
            ``updatedAt``. **Tidak** memuat ``userCount`` — field itu hanya
            ada pada ``GroupMinimal`` (dipakai ``wikijs_group_list``), bukan
            pada tipe ``Group``. Mengembalikan ``None`` bila group dengan
            ``group_id`` tersebut tidak ditemukan.

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
              pageRules { id deny match roles path locales }
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
        """Perbarui sebuah group Wiki.js yang sudah ada.

        PENTING — mutation ``groups.update`` di Wiki.js 2.x bersifat
        **REPLACE-ALL**, bukan patch-per-field: kelima argumennya (``id``,
        ``name``, ``redirectOnLogin``, ``permissions``, ``pageRules``) wajib
        non-null di level GraphQL (``String!``/``[String]!``/``[PageRuleInput]!``).
        Signature tool ini **tetap** menerima keempat argumen selain
        ``group_id`` sebagai opsional — semantik "ubah sebagian" dipertahankan
        di sisi tool lewat **read-modify-write**: bila ada argumen bernilai
        ``None``, tool membaca state group saat ini lewat ``groups.single``
        lebih dulu (nilai eksplisit dari pemanggil selalu menang saat
        digabung), baru mengirim satu mutation dengan kelima nilai lengkap.
        Bila keempat argumen opsional sudah terisi, pembacaan itu
        **dilewati** — hanya satu request HTTP yang dikirim.

        Args:
            group_id: ID numerik group yang akan diperbarui. Wajib bilangan
                bulat positif.
            name: Nama baru group. ``None`` (default) berarti dipertahankan
                dari state saat ini (dibaca lewat ``groups.single``).
            redirect_on_login: Path redirect setelah login untuk anggota group
                ini. ``None`` (default) berarti dipertahankan dari state saat
                ini; bila state saat ini kosong/``null``, jatuh ke ``"/"``.
            permissions: Daftar string kode permission baru. ``None``
                (default) berarti dipertahankan dari state saat ini; bila
                state saat ini kosong/``null``, jatuh ke ``[]``.
            page_rules: Daftar dict aturan halaman (``PageRuleInput``) baru.
                Tiap entri wajib memuat ``deny`` (bool), ``match`` (salah
                satu dari ``START``/``EXACT``/``END``/``REGEX``/``TAG``),
                ``roles`` (list), dan ``path`` (str); ``locales`` opsional.
                Bila ``id`` absen/kosong pada suatu entri, tool
                membangkitkannya otomatis (UUID) — pemanggil tidak perlu tahu
                Wiki.js mewajibkan ``id`` per-rule. ``None`` (default) berarti
                dipertahankan dari state saat ini; bila state saat ini
                kosong/``null``, jatuh ke ``[]``.

        Returns:
            Dict ``{"status": "updated"}``.

        Raises:
            ValueError: Bila ``group_id`` bukan bilangan bulat positif
                (``<= 0``), atau salah satu entri ``page_rules`` tidak valid
                (lihat :func:`_validate_page_rule`). Dilempar sebelum ada
                request HTTP.
            WikiJSAPIError: Bila group dengan ``group_id`` tersebut tidak
                ditemukan saat pembacaan state saat ini (dilempar sebelum
                mutation dikirim), atau mutation ``groups.update`` itu sendiri
                gagal (``responseResult.succeeded=false`` atau HTTP error).
        """
        if group_id <= 0:
            raise ValueError(f"group_id harus positif, diterima: {group_id}")

        if page_rules is not None:
            page_rules = [_validate_page_rule(rule) for rule in page_rules]

        if name is None or redirect_on_login is None or permissions is None or page_rules is None:
            current = await _fetch_current_for_update(group_id)
            if name is None:
                name = current.get("name")
            if redirect_on_login is None:
                redirect_on_login = current.get("redirectOnLogin") or "/"
            if permissions is None:
                permissions = current.get("permissions") or []
            if page_rules is None:
                page_rules = current.get("pageRules") or []

        mutation = """
        mutation(
          $id: Int!
          $name: String!
          $redirectOnLogin: String!
          $permissions: [String]!
          $pageRules: [PageRuleInput]!
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
        variables: dict[str, Any] = {
            "id": group_id,
            "name": name,
            "redirectOnLogin": redirect_on_login,
            "permissions": permissions,
            "pageRules": page_rules,
        }

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
