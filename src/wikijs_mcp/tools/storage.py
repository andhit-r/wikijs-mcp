"""Tool MCP untuk membaca & menjalankan aksi Storage Wiki.js (domain ``storage``).

Mendaftarkan tool: storage_target_list, storage_status, storage_action_execute.

Storage adalah mekanisme Wiki.js untuk mencerminkan konten wiki ke penyimpanan
eksternal (Git, S3, disk, dsb). Aksi paling sering dipakai adalah **Force Sync**
pada target ``git`` (``target_key="git"``, ``handler="sync"``) — tombol yang di
Admin UI berada di *Admin → Storage*, dipakai agar konten segera mendarat di repo
tanpa menunggu jadwal ``syncInterval``.

Ketiga tool memerlukan API key Wiki.js dengan hak ``manage:system`` (grup
Administrators), sama seperti domain ``mail``.

``StorageTarget.config`` memuat kredensial target (mis. ``basicPassword`` dan
``sshPrivateKeyContent`` pada target ``git``). Nilai untuk key yang terdaftar di
:data:`_REDACTED_CONFIG_KEYS` selalu disensor menjadi ``"***"`` — tidak ada opsi
untuk membuka nilai aslinya lewat MCP.

Mutation Wiki.js mengembalikan ``responseResult { succeeded errorCode message }``
— HTTP 200 + ``succeeded=false`` bukan sukses; divalidasi via
:func:`_check_response_result`.

# verifikasi terhadap versi Wiki.js target sebelum mengubah field GraphQL
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..client import WikiJSGraphQLClient, _check_response_result

# Key konfigurasi target storage yang nilainya WAJIB disensor sebelum keluar dari
# server MCP. Sensor berdasarkan NAMA KEY (bukan isi nilai) agar kredensial tetap
# tertutup apa pun bentuk nilainya. Target `git` Wiki.js 2.x memakai kedua key ini
# untuk autentikasi HTTP basic dan SSH.
_REDACTED_CONFIG_KEYS = frozenset({"basicPassword", "sshPrivateKeyContent"})

# Nilai pengganti yang ditampilkan sebagai ganti kredensial asli.
_REDACTED_PLACEHOLDER = "***"


def _redact_config(config: list[Any] | None) -> list[Any]:
    """Sensor nilai kredensial pada daftar ``config`` sebuah target storage.

    Setiap entri ``{"key": ..., "value": ...}`` yang ``key``-nya ada di
    :data:`_REDACTED_CONFIG_KEYS` dikembalikan dengan ``value`` diganti
    :data:`_REDACTED_PLACEHOLDER`. Entri lain diteruskan apa adanya. Daftar
    masukan tidak dimutasi — entri yang disensor disalin dangkal lebih dulu.

    Args:
        config: Daftar pasangan key-value dari ``StorageTarget.config``. Boleh
            ``None`` (target tanpa konfigurasi).

    Returns:
        Daftar konfigurasi baru dengan kredensial tersensor. Daftar kosong bila
        ``config`` bernilai ``None``.
    """
    if not config:
        return []
    redacted: list[Any] = []
    for entry in config:
        if isinstance(entry, dict) and entry.get("key") in _REDACTED_CONFIG_KEYS:
            redacted.append({**entry, "value": _REDACTED_PLACEHOLDER})
        else:
            redacted.append(entry)
    return redacted


def register(mcp: FastMCP, client: WikiJSGraphQLClient) -> None:
    """Daftarkan seluruh tool domain storage ke server MCP.

    Args:
        mcp: Instance FastMCP.
        client: Klien Wiki.js bersama.
    """

    @mcp.tool(tags={"storage"})
    async def wikijs_storage_target_list() -> dict[str, Any]:
        """Daftar seluruh target storage Wiki.js beserta aksi yang tersedia.

        Mengembalikan **semua** target yang dikenal instance (``git``, ``disk``,
        ``s3``, dsb) — bukan hanya yang aktif — sehingga handler aksi yang sah
        untuk :func:`wikijs_storage_action_execute` bisa ditemukan dari data
        (``actions``), tanpa menebak atau bergantung pada daftar hardcode.

        Nilai konfigurasi yang bersifat kredensial (``basicPassword``,
        ``sshPrivateKeyContent``) selalu dikembalikan sebagai ``"***"``. Tidak
        ada opsi untuk membuka nilai aslinya lewat MCP — sensor dilakukan
        berdasarkan nama key, bukan isi nilainya.

        Returns:
            Dict ``{"targets": [...]}``. Tiap target memuat ``isAvailable``,
            ``isEnabled``, ``key``, ``title``, ``description``, ``logo``,
            ``website``, ``supportedModes``, ``mode``, ``hasSchedule``,
            ``syncInterval``, ``syncIntervalDefault``, ``config`` (daftar
            ``{key, value}``, tersensor), dan ``actions`` (daftar
            ``{handler, label, hint}``).

        Raises:
            WikiJSAPIError: Bila request GraphQL gagal, atau HTTP 403 karena API
                key tidak berhak ``manage:system``.
        """
        query = """
        query {
          storage {
            targets {
              isAvailable
              isEnabled
              key
              title
              description
              logo
              website
              supportedModes
              mode
              hasSchedule
              syncInterval
              syncIntervalDefault
              config {
                key
                value
              }
              actions {
                handler
                label
                hint
              }
            }
          }
        }
        """
        data = await client.execute(query, operation="storage_target_list")
        targets = data.get("storage", {}).get("targets") or []
        sanitized: list[Any] = []
        for target in targets:
            if isinstance(target, dict):
                sanitized.append({**target, "config": _redact_config(target.get("config"))})
            else:
                sanitized.append(target)
        return {"targets": sanitized}

    @mcp.tool(tags={"storage"})
    async def wikijs_storage_status() -> dict[str, Any]:
        """Status sinkronisasi terakhir tiap target storage Wiki.js.

        Dipakai untuk memastikan sebuah aksi (mis. Force Sync lewat
        :func:`wikijs_storage_action_execute`) benar-benar berhasil: periksa
        ``status`` dan ``lastAttempt`` target yang bersangkutan sesudahnya.

        Returns:
            Dict ``{"status": [...]}``. Tiap entri memuat ``key``, ``title``,
            ``status`` (mis. ``"operational"``, ``"error"``, ``"pending"``),
            ``message``, dan ``lastAttempt``.

        Raises:
            WikiJSAPIError: Bila request GraphQL gagal, atau HTTP 403 karena API
                key tidak berhak ``manage:system``.
        """
        query = """
        query {
          storage {
            status {
              key
              title
              status
              message
              lastAttempt
            }
          }
        }
        """
        data = await client.execute(query, operation="storage_status")
        return {"status": data.get("storage", {}).get("status") or []}

    @mcp.tool(tags={"storage"})
    async def wikijs_storage_action_execute(target_key: str, handler: str) -> dict[str, Any]:
        """Jalankan sebuah aksi (handler) pada target storage Wiki.js.

        **Force Sync** = ``target_key="git"``, ``handler="sync"`` — mendorong
        konten wiki ke repo Git sekarang juga, tanpa menunggu ``syncInterval``.

        PERINGATAN — SEBAGIAN HANDLER DESTRUKTIF. Target ``git`` Wiki.js 2.x
        mengekspos empat handler dan dua di antaranya mengubah/menghapus data
        tanpa konfirmasi lanjutan:

        - ``sync`` — Force Sync dua arah. Aman, ini yang biasanya dimaksud.
        - ``syncUntracked`` — mendorong halaman yang belum terlacak ke repo.
        - ``importAll`` — **menimpa konten wiki** dengan isi repo Git lokal.
        - ``purge`` — **menghapus salinan repo Git lokal** milik Wiki.js.

        Handler tidak di-daftar-putih di sisi MCP: daftar handler yang sah adalah
        **data** (``actions`` pada :func:`wikijs_storage_target_list`) yang berbeda
        per target dan per versi Wiki.js. Nilai ``handler`` diteruskan apa adanya;
        handler yang tidak dikenal ditolak Wiki.js lewat ``responseResult`` dan
        diangkat menjadi ``WikiJSAPIError``. Panggil
        :func:`wikijs_storage_target_list` lebih dulu bila handler yang tersedia
        belum diketahui.

        Args:
            target_key: Kunci target storage, mis. ``"git"``. Wajib diisi (tidak
                boleh kosong/whitespace).
            handler: Nama handler aksi, mis. ``"sync"``. Wajib diisi (tidak boleh
                kosong/whitespace).

        Returns:
            Dict ``{"status": "executed", "target_key": target_key,
            "handler": handler}``.

        Raises:
            ValueError: Bila ``target_key`` atau ``handler`` kosong/whitespace.
                Dilempar sebelum ada request HTTP terkirim ke Wiki.js.
            WikiJSAPIError: Bila HTTP 403 (API key tanpa hak ``manage:system``)
                atau ``responseResult.succeeded=false`` (mis. handler tidak
                dikenal, atau aksi gagal di sisi Wiki.js).
        """
        if not target_key or not target_key.strip():
            raise ValueError("target_key tidak boleh kosong")
        if not handler or not handler.strip():
            raise ValueError("handler tidak boleh kosong")

        mutation = """
        mutation($targetKey: String!, $handler: String!) {
          storage {
            executeAction(targetKey: $targetKey, handler: $handler) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        data = await client.execute(
            mutation,
            {"targetKey": target_key, "handler": handler},
            operation="storage_action_execute",
        )
        result = data.get("storage", {}).get("executeAction", {})
        _check_response_result(result.get("responseResult", {}), "storage_action_execute")
        return {"status": "executed", "target_key": target_key, "handler": handler}
