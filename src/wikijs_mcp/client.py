"""Klien GraphQL async untuk Wiki.js API.

Modul ini membungkus ``httpx.AsyncClient`` dan menyediakan:

* Satu metode inti :meth:`WikiJSGraphQLClient.execute` — selalu POST ke ``/graphql``
  dengan body ``{query, variables}``.
* Penanganan eksplisit untuk error jaringan, timeout, HTTP error (401, 403, 404, 500),
  dan GraphQL-level errors (field ``errors`` dalam respons).
* Helper :func:`_check_response_result` untuk mutation Wiki.js yang mengembalikan
  ``responseResult { succeeded errorCode message }`` — HTTP 200 + ``succeeded=false``
  bukan sukses.

Klien ini dipakai bersama oleh seluruh tool MCP.
"""

from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class WikiJSAPIError(Exception):
    """Error yang dilempar ketika request ke Wiki.js API gagal.

    Attributes:
        status_code: HTTP status code (``None`` bila error jaringan/timeout).
        errors: Daftar dict error dari body GraphQL (bila ada).
        operation: Nama operasi GraphQL yang gagal (opsional).
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        errors: list[dict[str, Any]] | None = None,
        operation: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.errors = errors or []
        self.operation = operation
        super().__init__(message)


_STATUS_HINTS: dict[int, str] = {
    400: "Permintaan tidak valid (400). Periksa query/variabel GraphQL yang dikirim.",
    401: "Tidak terautentikasi (401). WIKIJS_API_KEY salah, kedaluwarsa, atau tidak dikirim.",
    403: "Akses ditolak (403). API key tidak memiliki izin yang cukup.",
    404: "Endpoint tidak ditemukan (404). Periksa WIKIJS_URL.",
    500: "Kesalahan internal server Wiki.js (500). Coba lagi atau cek log Wiki.js.",
}


def _check_response_result(rr: dict[str, Any], operation: str) -> None:
    """Validasi responseResult dari mutation Wiki.js.

    Wiki.js mengembalikan HTTP 200 bahkan saat mutation gagal; sukses hanya
    bila ``succeeded=true``. Fungsi ini mengangkat kegagalan tersebut menjadi
    ``WikiJSAPIError`` agar tool tidak melaporkan sukses palsu.

    Args:
        rr: Dict ``responseResult`` dari mutation Wiki.js.
        operation: Nama operasi untuk konteks pesan error.

    Raises:
        WikiJSAPIError: Bila ``succeeded`` adalah ``false``.
    """
    if rr and not rr.get("succeeded", True):
        msg = rr.get("message") or f"Operasi Wiki.js '{operation}' gagal"
        raise WikiJSAPIError(msg, errors=[rr], operation=operation)


class WikiJSGraphQLClient:
    """Klien async untuk berinteraksi dengan Wiki.js melalui GraphQL API.

    Gunakan sebagai async context manager atau panggil :meth:`aclose` saat
    selesai untuk menutup koneksi.

    Example:
        >>> settings = get_settings()
        >>> async with WikiJSGraphQLClient(settings) as client:
        ...     data = await client.execute("{ system { info { currentVersion } } }")
    """

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Inisialisasi klien.

        Args:
            settings: Konfigurasi aplikasi (URL & API key Wiki.js).
            http_client: ``httpx.AsyncClient`` opsional untuk injeksi (berguna
                pada unit test). Bila ``None``, klien internal dibuat otomatis.
        """
        self._settings = settings
        self._owns_client = http_client is None
        token = settings.wikijs_api_key.get_secret_value()
        self._client = http_client or httpx.AsyncClient(
            timeout=settings.wikijs_timeout,
            verify=settings.wikijs_verify_ssl,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    async def __aenter__(self) -> WikiJSGraphQLClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Tutup koneksi HTTP bila klien ini yang membuatnya."""
        if self._owns_client:
            await self._client.aclose()

    async def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        operation: str | None = None,
    ) -> dict[str, Any]:
        """Eksekusi satu operasi GraphQL ke Wiki.js.

        Args:
            query: String query/mutation GraphQL.
            variables: Variabel GraphQL opsional (dict).
            operation: Nama operasi untuk konteks pesan error.

        Returns:
            Dict ``data`` dari body respons GraphQL.

        Raises:
            WikiJSAPIError: Bila terjadi error jaringan/timeout, HTTP error,
                atau respons GraphQL mengandung field ``errors``.
        """
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        endpoint = self._settings.graphql_endpoint

        try:
            response = await self._client.post(endpoint, json=payload)
        except httpx.TimeoutException as exc:
            raise WikiJSAPIError(
                f"Timeout saat memanggil Wiki.js GraphQL API (operasi: {operation or 'unknown'}).",
                operation=operation,
            ) from exc
        except httpx.RequestError as exc:
            raise WikiJSAPIError(
                f"Gagal terhubung ke Wiki.js GraphQL API: {exc}",
                operation=operation,
            ) from exc

        if response.is_error:
            self._raise_for_status(response, operation)

        try:
            body = response.json()
        except ValueError as exc:
            raise WikiJSAPIError(
                f"Respons Wiki.js bukan JSON yang valid: {response.text[:200]}",
                status_code=response.status_code,
                operation=operation,
            ) from exc

        gql_errors = body.get("errors")
        if gql_errors:
            first = gql_errors[0] if gql_errors else {}
            msg = first.get("message", "GraphQL error dari Wiki.js")
            raise WikiJSAPIError(
                f"Wiki.js GraphQL error: {msg}",
                status_code=response.status_code,
                errors=gql_errors,
                operation=operation,
            )

        return body.get("data", {})

    def _raise_for_status(self, response: httpx.Response, operation: str | None) -> None:
        """Terjemahkan respons error HTTP menjadi :class:`WikiJSAPIError`.

        Args:
            response: Respons httpx dengan status >= 400.
            operation: Nama operasi GraphQL untuk konteks.

        Raises:
            WikiJSAPIError: Selalu dilempar dengan pesan sesuai status code.
        """
        status = response.status_code
        hint = _STATUS_HINTS.get(status, f"Wiki.js API mengembalikan status {status}.")
        detail: Any = None
        try:
            detail = response.json()
        except ValueError:
            detail = response.text or None

        message = hint
        if operation:
            message = f"{hint} (operasi: {operation})"
        if detail:
            message = f"{message} Detail: {detail}"
        raise WikiJSAPIError(message, status_code=status, operation=operation)
