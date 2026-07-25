"""Tool MCP untuk mengelola konfigurasi mail (SMTP) Wiki.js (domain ``mail``).

Mendaftarkan tool: update_config, send_test.

Kedua tool memerlukan API key Wiki.js dengan hak ``manage:system`` (grup
Administrators) — beda dari domain tool lain yang cukup hak baca/tulis konten.

Semua mutation menggunakan GraphQL Wiki.js 2.x dan mengembalikan
``responseResult { succeeded errorCode message }`` — HTTP 200 + ``succeeded=false``
bukan sukses; divalidasi via :func:`_check_response_result`.

# verifikasi terhadap versi Wiki.js target sebelum mengubah field GraphQL
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..client import WikiJSGraphQLClient, _check_response_result


def register(mcp: FastMCP, client: WikiJSGraphQLClient) -> None:
    """Daftarkan seluruh tool domain mail ke server MCP.

    Args:
        mcp: Instance FastMCP.
        client: Klien Wiki.js bersama.
    """

    @mcp.tool(tags={"mail"})
    async def wikijs_mail_update_config(
        sender_name: str,
        sender_email: str,
        host: str,
        port: int,
        name: str,
        secure: bool,
        verify_ssl: bool,
        user: str,
        password: str,
        use_dkim: bool = False,
        dkim_domain_name: str = "",
        dkim_key_selector: str = "",
        dkim_private_key: str = "",
    ) -> dict[str, Any]:
        """Timpa konfigurasi mail (SMTP) instance Wiki.js.

        PERINGATAN — REPLACE-ALL, BUKAN PATCH: mutation ``mail.updateConfig`` di
        Wiki.js menimpa **seluruh** konfigurasi mail sekaligus, bukan hanya field
        yang disebut. Tidak ada tool pembaca konfigurasi saat ini (lihat README),
        jadi read-modify-write tidak mungkin dilakukan lewat MCP — pemanggil wajib
        menyertakan **seluruh** nilai yang ingin dipertahankan pada setiap
        panggilan. Secara khusus, memanggil tool ini dengan parameter DKIM default
        (string kosong) akan **menghapus** konfigurasi DKIM yang sudah terpasang
        di Wiki.js.

        Args:
            sender_name: Nama pengirim yang tampil di email (boleh kosong).
            sender_email: Alamat email pengirim. Wajib diisi (tidak boleh
                kosong/whitespace).
            host: Hostname atau IP server SMTP. Wajib diisi (tidak boleh
                kosong/whitespace).
            port: Port server SMTP. Harus di rentang 1–65535.
            name: Nama server SMTP yang dikirim saat HELO/EHLO (boleh kosong).
            secure: Apakah koneksi memakai SSL/TLS implisit. Tanpa nilai default
                agar pemanggil selalu menyatakannya secara eksplisit.
            verify_ssl: Apakah sertifikat SSL server SMTP diverifikasi. Tanpa
                nilai default agar verifikasi sertifikat tidak diam-diam
                dinonaktifkan.
            user: Username autentikasi SMTP. Boleh string kosong untuk relay
                tanpa autentikasi.
            password: Password autentikasi SMTP. Dipetakan ke variabel GraphQL
                ``$pass`` (``pass`` adalah reserved word Python). Boleh string
                kosong untuk relay tanpa autentikasi.
            use_dkim: Aktifkan penandatanganan DKIM. Default ``False``.
            dkim_domain_name: Domain DKIM. Wajib diisi bila ``use_dkim=True``.
                Default string kosong.
            dkim_key_selector: Selector kunci DKIM. Wajib diisi bila
                ``use_dkim=True``. Default string kosong.
            dkim_private_key: Kunci privat DKIM (PEM). Wajib diisi bila
                ``use_dkim=True``. Default string kosong.

        Returns:
            Dict ``{"status": "updated"}``. Tidak mengembalikan echo
            ``password``/``dkim_private_key`` agar kredensial tidak nyangkut di
            log/transcript client.

        Raises:
            ValueError: Bila ``sender_email`` atau ``host`` kosong/whitespace,
                ``port`` di luar rentang 1–65535, atau ``use_dkim=True`` dengan
                salah satu dari ``dkim_domain_name``/``dkim_key_selector``/
                ``dkim_private_key`` kosong. Dilempar sebelum ada request HTTP.
            WikiJSAPIError: Bila HTTP 403 (API key tanpa hak ``manage:system``)
                atau ``responseResult.succeeded=false``.
        """
        if not sender_email or not sender_email.strip():
            raise ValueError("sender_email tidak boleh kosong")
        if not host or not host.strip():
            raise ValueError("host tidak boleh kosong")
        if not 1 <= port <= 65535:
            raise ValueError(f"port harus di rentang 1-65535, diterima: {port}")
        if use_dkim and not (dkim_domain_name and dkim_key_selector and dkim_private_key):
            raise ValueError(
                "dkim_domain_name, dkim_key_selector, dan dkim_private_key wajib diisi "
                "saat use_dkim=True"
            )

        mutation = """
        mutation(
          $senderName: String!
          $senderEmail: String!
          $host: String!
          $port: Int!
          $name: String!
          $secure: Boolean!
          $verifySSL: Boolean!
          $user: String!
          $pass: String!
          $useDKIM: Boolean!
          $dkimDomainName: String!
          $dkimKeySelector: String!
          $dkimPrivateKey: String!
        ) {
          mail {
            updateConfig(
              senderName: $senderName
              senderEmail: $senderEmail
              host: $host
              port: $port
              name: $name
              secure: $secure
              verifySSL: $verifySSL
              user: $user
              pass: $pass
              useDKIM: $useDKIM
              dkimDomainName: $dkimDomainName
              dkimKeySelector: $dkimKeySelector
              dkimPrivateKey: $dkimPrivateKey
            ) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        variables = {
            "senderName": sender_name,
            "senderEmail": sender_email,
            "host": host,
            "port": port,
            "name": name,
            "secure": secure,
            "verifySSL": verify_ssl,
            "user": user,
            "pass": password,
            "useDKIM": use_dkim,
            "dkimDomainName": dkim_domain_name,
            "dkimKeySelector": dkim_key_selector,
            "dkimPrivateKey": dkim_private_key,
        }
        data = await client.execute(mutation, variables, operation="mail_update_config")
        result = data.get("mail", {}).get("updateConfig", {})
        _check_response_result(result.get("responseResult", {}), "mail_update_config")
        return {"status": "updated"}

    @mcp.tool(tags={"mail"})
    async def wikijs_mail_send_test(recipient_email: str) -> dict[str, Any]:
        """Kirim email uji lewat konfigurasi mail Wiki.js saat ini.

        Berguna untuk memverifikasi konfigurasi SMTP setelah dipanggil
        ``wikijs_mail_update_config``. Validasi format alamat email diserahkan
        ke Wiki.js sendiri lewat ``responseResult`` — tool ini tidak melakukan
        pengecekan regex sendiri.

        Args:
            recipient_email: Alamat email penerima email uji. Wajib diisi
                (tidak boleh kosong/whitespace).

        Returns:
            Dict ``{"status": "test_sent", "recipient_email": recipient_email}``.

        Raises:
            ValueError: Bila ``recipient_email`` kosong/whitespace. Dilempar
                sebelum ada request HTTP terkirim ke Wiki.js.
            WikiJSAPIError: Bila HTTP 403 (API key tanpa hak ``manage:system``)
                atau ``responseResult.succeeded=false``.
        """
        if not recipient_email or not recipient_email.strip():
            raise ValueError("recipient_email tidak boleh kosong")

        mutation = """
        mutation($recipientEmail: String!) {
          mail {
            sendTest(recipientEmail: $recipientEmail) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        data = await client.execute(
            mutation, {"recipientEmail": recipient_email}, operation="mail_send_test"
        )
        result = data.get("mail", {}).get("sendTest", {})
        _check_response_result(result.get("responseResult", {}), "mail_send_test")
        return {"status": "test_sent", "recipient_email": recipient_email}
