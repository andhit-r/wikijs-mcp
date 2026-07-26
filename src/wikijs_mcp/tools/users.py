"""Tool MCP untuk mengelola user Wiki.js (domain ``users``).

Mendaftarkan tool: user_list, user_get, user_create, user_update, user_delete,
user_activate, user_deactivate, user_enable_tfa, user_disable_tfa.

Semua query/mutation menggunakan GraphQL Wiki.js 2.x. Mutation mengembalikan
``responseResult { succeeded errorCode message }`` — HTTP 200 + ``succeeded=false``
bukan sukses; divalidasi via :func:`_check_response_result`.

Kredensial (``password_raw`` pada ``wikijs_user_create``, ``new_password`` pada
``wikijs_user_update``) **tidak pernah** di-echo di return value tool — identik
pola ``wikijs_mail_update_config`` yang menyembunyikan kredensial dari response.

Pengelolaan group (``wikijs_group_*``) berada di modul terpisah (:mod:`.groups`).
Tool ``wikijs_user_create``/``wikijs_user_update`` menerima ``group_ids: list[int]``
mentah (asumsi id sudah diketahui pemanggil) — tidak memvalidasi keberadaannya
lewat pemanggilan tool group.

Otorisasi sepenuhnya bergantung pada hak API key Wiki.js (``manage:users``/grup
Administrators) — tidak ada pengecekan tambahan di level tool ini, identik pola
``mail.py``/``groups.py``. HTTP 403 dari Wiki.js diteruskan apa adanya lewat
``WikiJSAPIError``.

# verifikasi terhadap versi Wiki.js target sebelum mengubah field GraphQL
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..client import WikiJSGraphQLClient, _check_response_result


def _validate_positive_id(value: int, field: str) -> None:
    """Validasi bahwa sebuah ID Wiki.js adalah bilangan bulat positif.

    Args:
        value: Nilai ID yang akan divalidasi.
        field: Nama field untuk konteks pesan error.

    Raises:
        ValueError: Bila ``value`` <= 0.
    """
    if value <= 0:
        raise ValueError(f"{field} harus positif, diterima: {value}")


def _validate_email(email: str, field: str = "email") -> None:
    """Validasi minimal alamat email: tidak kosong dan mengandung ``@``.

    Ini validasi minimal saja — sisanya (format lengkap, domain, dsb.)
    diserahkan ke ``responseResult`` Wiki.js, identik pola
    ``wikijs_mail_send_test`` yang tidak meregex email.

    Args:
        email: Alamat email yang akan divalidasi.
        field: Nama field untuk konteks pesan error.

    Raises:
        ValueError: Bila ``email`` kosong/whitespace atau tidak mengandung ``@``.
    """
    if not email or not email.strip():
        raise ValueError(f"{field} tidak boleh kosong")
    if "@" not in email:
        raise ValueError(f"{field} harus mengandung '@', diterima: {email}")


def register(mcp: FastMCP, client: WikiJSGraphQLClient) -> None:
    """Daftarkan seluruh tool domain users ke server MCP.

    Args:
        mcp: Instance FastMCP.
        client: Klien Wiki.js bersama.
    """

    @mcp.tool(tags={"users"})
    async def wikijs_user_list() -> list[dict[str, Any]]:
        """Ambil daftar semua user Wiki.js.

        Returns:
            Daftar dict user, tiap item berisi ``id``, ``name``, ``email``,
            ``providerKey``, ``isSystem``, ``isActive``, ``createdAt``,
            ``lastLoginAt``.

        Raises:
            WikiJSAPIError: Bila request GraphQL gagal (mis. HTTP 403 karena API
                key tanpa hak ``manage:users``).
        """
        query = """
        query {
          users {
            list {
              id
              name
              email
              providerKey
              isSystem
              isActive
              createdAt
              lastLoginAt
            }
          }
        }
        """
        data = await client.execute(query, operation="user_list")
        return data.get("users", {}).get("list", [])

    @mcp.tool(tags={"users"})
    async def wikijs_user_get(user_id: int) -> dict[str, Any] | None:
        """Ambil detail satu user berdasarkan ID numerik, termasuk keanggotaan group.

        Args:
            user_id: ID numerik user Wiki.js. Wajib bilangan bulat positif.

        Returns:
            Dict detail user berisi ``id``, ``name``, ``email``, ``providerKey``,
            ``isSystem``, ``isActive``, ``isVerified``, ``location``,
            ``jobTitle``, ``timezone``, ``createdAt``, ``updatedAt``,
            ``lastLoginAt``, dan ``groups`` (list dict ``{id, name}``).
            Mengembalikan ``None`` bila user dengan ``user_id`` tersebut tidak
            ditemukan.

        Raises:
            ValueError: Bila ``user_id`` bukan bilangan bulat positif (``<= 0``).
                Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila request GraphQL gagal (mis. HTTP 403).
        """
        _validate_positive_id(user_id, "user_id")

        query = """
        query($id: Int!) {
          users {
            single(id: $id) {
              id
              name
              email
              providerKey
              isSystem
              isActive
              isVerified
              location
              jobTitle
              timezone
              createdAt
              updatedAt
              lastLoginAt
              groups { id name }
            }
          }
        }
        """
        data = await client.execute(query, {"id": user_id}, operation="user_get")
        return data.get("users", {}).get("single")

    @mcp.tool(tags={"users"})
    async def wikijs_user_create(
        email: str,
        name: str,
        group_ids: list[int],
        password_raw: str | None = None,
        provider_key: str = "local",
        must_change_password: bool | None = None,
        send_welcome_email: bool | None = None,
    ) -> dict[str, Any]:
        """Buat user baru di Wiki.js.

        Args:
            email: Alamat email user baru. Wajib diisi (tidak boleh
                kosong/whitespace) dan mengandung ``@`` (validasi minimal —
                sisanya diserahkan ke ``responseResult`` Wiki.js).
            name: Nama lengkap user baru. Wajib diisi (tidak boleh
                kosong/whitespace).
            group_ids: Daftar ID group (mentah, id diasumsikan sudah diketahui
                pemanggil — tidak divalidasi lewat tool group) yang akan
                dijadikan keanggotaan awal user. Tidak boleh kosong untuk
                ``provider_key="local"``.
            password_raw: Password awal user (plain text, dikirim ke Wiki.js
                lewat variabel GraphQL ``passwordRaw``). ``None`` (default)
                berarti tidak diset (relevan untuk provider non-local).
                **Tidak pernah** di-echo di return value tool.
            provider_key: Kunci provider autentikasi Wiki.js. Default
                ``"local"``.
            must_change_password: Wajibkan user mengganti password saat login
                pertama. ``None`` (default) berarti tidak dikirim (memakai
                default Wiki.js).
            send_welcome_email: Kirim email selamat datang ke user baru.
                ``None`` (default) berarti tidak dikirim (memakai default
                Wiki.js).

        Returns:
            Dict ``{"id": ..., "name": ..., "email": ...}`` dari user yang baru
            dibuat. **Tidak** memuat ``password_raw`` — mutation Wiki.js hanya
            mengembalikan ``user { id name email }``, kredensial tidak pernah
            ikut ter-echo di response.

        Raises:
            ValueError: Bila ``email``/``name`` kosong/whitespace, ``email``
                tidak mengandung ``@``, atau ``group_ids`` kosong untuk
                ``provider_key="local"``. Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila mutation gagal (mis. email sudah dipakai,
                izin kurang) atau HTTP 403.
        """
        _validate_email(email)
        if not name or not name.strip():
            raise ValueError("name tidak boleh kosong")
        if not group_ids and provider_key == "local":
            raise ValueError("group_ids tidak boleh kosong untuk provider_key='local'")

        mutation = """
        mutation(
          $email: String!
          $name: String!
          $passwordRaw: String
          $providerKey: String!
          $groups: [Int]!
          $mustChangePassword: Boolean
          $sendWelcomeEmail: Boolean
        ) {
          users {
            create(
              email: $email
              name: $name
              passwordRaw: $passwordRaw
              providerKey: $providerKey
              groups: $groups
              mustChangePassword: $mustChangePassword
              sendWelcomeEmail: $sendWelcomeEmail
            ) {
              responseResult { succeeded errorCode message }
              user { id name email }
            }
          }
        }
        """
        variables: dict[str, Any] = {
            "email": email,
            "name": name,
            "providerKey": provider_key,
            "groups": group_ids,
        }
        if password_raw is not None:
            variables["passwordRaw"] = password_raw
        if must_change_password is not None:
            variables["mustChangePassword"] = must_change_password
        if send_welcome_email is not None:
            variables["sendWelcomeEmail"] = send_welcome_email

        data = await client.execute(mutation, variables, operation="user_create")
        result = data.get("users", {}).get("create", {})
        _check_response_result(result.get("responseResult", {}), "user_create")
        return result.get("user") or {}

    @mcp.tool(tags={"users"})
    async def wikijs_user_update(
        user_id: int,
        email: str | None = None,
        name: str | None = None,
        new_password: str | None = None,
        is_active: bool | None = None,
        timezone: str | None = None,
        group_ids: list[int] | None = None,
        job_title: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        """Perbarui sebagian field sebuah user Wiki.js yang sudah ada.

        Mutation ``users.update`` di Wiki.js bersifat **patch-per-field**.
        Parameter opsional yang tidak diisi (``None``) **tidak dikirim** sama
        sekali sebagai variabel GraphQL — bukan dikirim sebagai ``null`` —
        sehingga nilai lama pada field tersebut tetap dipertahankan Wiki.js.

        Args:
            user_id: ID numerik user yang akan diperbarui. Wajib bilangan
                bulat positif.
            email: Alamat email baru. ``None`` (default) berarti tidak
                diubah. Bila diisi, wajib mengandung ``@`` (validasi minimal).
            name: Nama baru user. ``None`` (default) berarti tidak diubah.
            new_password: Password baru (plain text, dikirim lewat variabel
                GraphQL ``newPassword``). ``None`` (default) berarti tidak
                diubah. **Tidak pernah** di-echo di return value tool.
            is_active: Status aktif user. ``None`` (default) berarti tidak
                diubah.
            timezone: Zona waktu user (mis. ``"Asia/Jakarta"``). ``None``
                (default) berarti tidak diubah.
            group_ids: Daftar ID group (mentah) baru untuk keanggotaan user —
                menggantikan seluruh keanggotaan lama. ``None`` (default)
                berarti tidak diubah.
            job_title: Jabatan user. ``None`` (default) berarti tidak diubah.
            location: Lokasi user. ``None`` (default) berarti tidak diubah.

        Returns:
            Dict ``{"status": "updated"}``.

        Raises:
            ValueError: Bila ``user_id`` bukan bilangan bulat positif
                (``<= 0``), atau ``email`` diisi tapi kosong/whitespace/tidak
                mengandung ``@``. Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila mutation gagal atau user tidak ditemukan.
        """
        _validate_positive_id(user_id, "user_id")
        if email is not None:
            _validate_email(email)

        mutation = """
        mutation(
          $id: Int!
          $email: String
          $name: String
          $newPassword: String
          $isActive: Boolean
          $timezone: String
          $groups: [Int]
          $jobTitle: String
          $location: String
        ) {
          users {
            update(
              id: $id
              email: $email
              name: $name
              newPassword: $newPassword
              isActive: $isActive
              timezone: $timezone
              groups: $groups
              jobTitle: $jobTitle
              location: $location
            ) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        variables: dict[str, Any] = {"id": user_id}
        if email is not None:
            variables["email"] = email
        if name is not None:
            variables["name"] = name
        if new_password is not None:
            variables["newPassword"] = new_password
        if is_active is not None:
            variables["isActive"] = is_active
        if timezone is not None:
            variables["timezone"] = timezone
        if group_ids is not None:
            variables["groups"] = group_ids
        if job_title is not None:
            variables["jobTitle"] = job_title
        if location is not None:
            variables["location"] = location

        data = await client.execute(mutation, variables, operation="user_update")
        result = data.get("users", {}).get("update", {})
        _check_response_result(result.get("responseResult", {}), "user_update")
        return {"status": "updated"}

    @mcp.tool(tags={"users"})
    async def wikijs_user_delete(user_id: int, replace_id: int | None = None) -> dict[str, Any]:
        """Hapus user Wiki.js secara permanen. Operasi ini tidak dapat dibatalkan.

        Args:
            user_id: ID numerik user yang akan dihapus. Wajib bilangan bulat
                positif.
            replace_id: ID numerik user pengganti untuk mewarisi kepemilikan
                konten (halaman, dsb.) milik user yang dihapus. ``None``
                (default) berarti tidak ada penggantian. Bila diisi, wajib
                bilangan bulat positif.

        Returns:
            Dict ``{"status": "deleted", "user_id": user_id}``.

        Raises:
            ValueError: Bila ``user_id`` bukan bilangan bulat positif
                (``<= 0``), atau ``replace_id`` diisi tapi bukan bilangan
                bulat positif. Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila mutation gagal (mis. user sistem yang tidak
                boleh dihapus) atau user tidak ditemukan.
        """
        _validate_positive_id(user_id, "user_id")
        if replace_id is not None:
            _validate_positive_id(replace_id, "replace_id")

        mutation = """
        mutation($id: Int!, $replaceId: Int) {
          users {
            delete(id: $id, replaceId: $replaceId) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        variables: dict[str, Any] = {"id": user_id}
        if replace_id is not None:
            variables["replaceId"] = replace_id

        data = await client.execute(mutation, variables, operation="user_delete")
        result = data.get("users", {}).get("delete", {})
        _check_response_result(result.get("responseResult", {}), "user_delete")
        return {"status": "deleted", "user_id": user_id}

    @mcp.tool(tags={"users"})
    async def wikijs_user_activate(user_id: int) -> dict[str, Any]:
        """Aktifkan kembali akun user Wiki.js yang sebelumnya dinonaktifkan.

        Args:
            user_id: ID numerik user yang akan diaktifkan. Wajib bilangan
                bulat positif.

        Returns:
            Dict ``{"status": "activated", "user_id": user_id}``.

        Raises:
            ValueError: Bila ``user_id`` bukan bilangan bulat positif
                (``<= 0``). Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila mutation gagal atau user tidak ditemukan.
        """
        _validate_positive_id(user_id, "user_id")

        mutation = """
        mutation($id: Int!) {
          users {
            activate(id: $id) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        data = await client.execute(mutation, {"id": user_id}, operation="user_activate")
        result = data.get("users", {}).get("activate", {})
        _check_response_result(result.get("responseResult", {}), "user_activate")
        return {"status": "activated", "user_id": user_id}

    @mcp.tool(tags={"users"})
    async def wikijs_user_deactivate(user_id: int) -> dict[str, Any]:
        """Nonaktifkan akun user Wiki.js (mencegah login tanpa menghapus data).

        Args:
            user_id: ID numerik user yang akan dinonaktifkan. Wajib bilangan
                bulat positif.

        Returns:
            Dict ``{"status": "deactivated", "user_id": user_id}``.

        Raises:
            ValueError: Bila ``user_id`` bukan bilangan bulat positif
                (``<= 0``). Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila mutation gagal atau user tidak ditemukan.
        """
        _validate_positive_id(user_id, "user_id")

        mutation = """
        mutation($id: Int!) {
          users {
            deactivate(id: $id) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        data = await client.execute(mutation, {"id": user_id}, operation="user_deactivate")
        result = data.get("users", {}).get("deactivate", {})
        _check_response_result(result.get("responseResult", {}), "user_deactivate")
        return {"status": "deactivated", "user_id": user_id}

    @mcp.tool(tags={"users"})
    async def wikijs_user_enable_tfa(user_id: int) -> dict[str, Any]:
        """Aktifkan two-factor authentication (TFA) untuk sebuah user Wiki.js.

        Args:
            user_id: ID numerik user. Wajib bilangan bulat positif.

        Returns:
            Dict ``{"status": "tfa_enabled", "user_id": user_id}``.

        Raises:
            ValueError: Bila ``user_id`` bukan bilangan bulat positif
                (``<= 0``). Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila mutation gagal atau user tidak ditemukan.
        """
        _validate_positive_id(user_id, "user_id")

        mutation = """
        mutation($id: Int!) {
          users {
            enableTFA(id: $id) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        data = await client.execute(mutation, {"id": user_id}, operation="user_enable_tfa")
        result = data.get("users", {}).get("enableTFA", {})
        _check_response_result(result.get("responseResult", {}), "user_enable_tfa")
        return {"status": "tfa_enabled", "user_id": user_id}

    @mcp.tool(tags={"users"})
    async def wikijs_user_disable_tfa(user_id: int) -> dict[str, Any]:
        """Nonaktifkan two-factor authentication (TFA) untuk sebuah user Wiki.js.

        Args:
            user_id: ID numerik user. Wajib bilangan bulat positif.

        Returns:
            Dict ``{"status": "tfa_disabled", "user_id": user_id}``.

        Raises:
            ValueError: Bila ``user_id`` bukan bilangan bulat positif
                (``<= 0``). Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila mutation gagal atau user tidak ditemukan.
        """
        _validate_positive_id(user_id, "user_id")

        mutation = """
        mutation($id: Int!) {
          users {
            disableTFA(id: $id) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        data = await client.execute(mutation, {"id": user_id}, operation="user_disable_tfa")
        result = data.get("users", {}).get("disableTFA", {})
        _check_response_result(result.get("responseResult", {}), "user_disable_tfa")
        return {"status": "tfa_disabled", "user_id": user_id}
