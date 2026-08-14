"""Tool MCP untuk membaca, mengubah & menjalankan aksi Storage Wiki.js (domain ``storage``).

Mendaftarkan tool: storage_target_list, storage_status, storage_action_execute,
storage_target_update.

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

``Mutation.storage.updateTargets`` bersemantik **REPLACE-ALL**: argumennya
menerima seluruh nilai sebuah target sekaligus, sehingga panggilan yang hanya
mengirim satu-dua field akan menghapus sisa konfigurasinya. Karena itu
:func:`wikijs_storage_target_update` selalu melakukan **read-modify-write** di
dalam tool dan menolak nilai ``config`` yang berisi
:data:`_REDACTED_PLACEHOLDER`.

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

    @mcp.tool(tags={"storage"})
    async def wikijs_storage_target_update(
        target_key: str,
        is_enabled: bool | None = None,
        mode: str | None = None,
        sync_interval: str | None = None,
        config: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Ubah sebagian konfigurasi satu target storage Wiki.js (partial update).

        Contoh pemakaian: mengaktifkan target ``git``
        (``is_enabled=True``), mengganti jadwal sinkronisasi
        (``sync_interval="PT5M"``), atau memindahkan branch tujuan
        (``config={"branch": "main"}``) — hal-hal yang sebelumnya hanya bisa
        dilakukan lewat *Admin → Storage*.

        PERINGATAN — ``Mutation.storage.updateTargets`` Wiki.js bersemantik
        **REPLACE-ALL**: satu panggilan mengirim seluruh nilai target sekaligus,
        sehingga field yang tidak disertakan akan **terhapus**. Tool ini
        menutupi jebakan itu dengan **read-modify-write**: ia membaca dulu
        target yang bersangkutan lewat ``Query.storage.targets``, menerapkan
        argumen yang bukan ``None``, lalu mengirim kembali target itu **utuh**.
        Argumen bernilai ``None`` berarti "jangan ubah", bukan "kosongkan".

        DILARANG mengirim nilai ``"***"`` pada ``config``. Nilai itu adalah
        sentinel redaksi keluaran :func:`wikijs_storage_target_list`; alur wajar
        "baca → salin → ubah sedikit → tulis" akan menimpa kredensial asli
        (``basicPassword``, ``sshPrivateKeyContent``) dengan literal ``"***"``.
        Tool menolaknya dengan ``ValueError`` sebelum ada request HTTP terkirim.
        Bila kredensial memang perlu diganti, kirim nilai barunya yang
        sebenarnya.

        Args:
            target_key: Kunci target storage yang diubah, mis. ``"git"``. Wajib
                diisi (tidak boleh kosong/whitespace) dan wajib ada di antara
                target yang dikembalikan Wiki.js.
            is_enabled: Aktifkan (``True``) atau nonaktifkan (``False``) target.
                ``None`` = pertahankan nilai saat ini.
            mode: Mode sinkronisasi, mis. ``"sync"``/``"push"``/``"pull"``.
                Nilai yang sah ada di ``supportedModes`` pada
                :func:`wikijs_storage_target_list`. ``None`` = tidak diubah.
            sync_interval: Jadwal sinkronisasi berformat durasi ISO-8601, mis.
                ``"PT5M"`` (5 menit) atau ``"P1D"`` (1 hari). ``None`` = tidak
                diubah.
            config: Key konfigurasi yang ingin ditimpa, mis.
                ``{"branch": "main"}``. Di-**merge per key** ke konfigurasi saat
                ini — key yang tidak disebut dipertahankan apa adanya. Key yang
                belum ada pada target ditolak (proteksi salah ketik), bukan
                ditambahkan diam-diam. ``None`` = konfigurasi tidak disentuh.

        Returns:
            Dict ``{"status": "updated", "target_key": target_key}``. Nilai
            ``config`` sengaja **tidak** di-echo agar kredensial tidak nyangkut
            di transcript client.

        Raises:
            ValueError: Bila ``target_key`` kosong/whitespace, ada nilai
                ``config`` yang sama persis dengan ``"***"``, ``target_key``
                tidak ditemukan di antara target Wiki.js, atau ``config`` memuat
                key yang tidak ada pada konfigurasi target saat ini. Dua kasus
                pertama dilempar sebelum ada request HTTP sama sekali.
            WikiJSAPIError: Bila HTTP 403 (API key tanpa hak ``manage:system``)
                atau ``responseResult.succeeded=false``.
        """
        if not target_key or not target_key.strip():
            raise ValueError("target_key tidak boleh kosong")
        if config:
            redacted_keys = sorted(
                key for key, value in config.items() if value == _REDACTED_PLACEHOLDER
            )
            if redacted_keys:
                raise ValueError(
                    "config memuat nilai tersensor '***' pada key "
                    f"{redacted_keys} — nilai itu adalah sentinel redaksi "
                    "wikijs_storage_target_list, bukan kredensial asli. Kirim "
                    "nilai sebenarnya atau hilangkan key tersebut."
                )

        query = """
        query {
          storage {
            targets {
              isEnabled
              key
              mode
              syncInterval
              config {
                key
                value
              }
            }
          }
        }
        """
        data = await client.execute(query, operation="storage_target_update_read")
        targets = data.get("storage", {}).get("targets") or []
        current = next(
            (
                target
                for target in targets
                if isinstance(target, dict) and target.get("key") == target_key
            ),
            None,
        )
        if current is None:
            known = sorted(str(target.get("key")) for target in targets if isinstance(target, dict))
            raise ValueError(
                f"target_key '{target_key}' tidak ditemukan di Wiki.js; "
                f"target yang tersedia: {known}"
            )

        merged_config = [
            {"key": entry.get("key"), "value": entry.get("value")}
            for entry in (current.get("config") or [])
            if isinstance(entry, dict)
        ]
        if config:
            known_config_keys = {entry["key"] for entry in merged_config}
            unknown = sorted(set(config) - known_config_keys)
            if unknown:
                raise ValueError(
                    f"key config {unknown} tidak dikenal target '{target_key}'; "
                    f"key yang tersedia: {sorted(known_config_keys)}"
                )
            for entry in merged_config:
                if entry["key"] in config:
                    entry["value"] = config[entry["key"]]

        target_input = {
            "isEnabled": current.get("isEnabled") if is_enabled is None else is_enabled,
            "key": target_key,
            "mode": current.get("mode") if mode is None else mode,
            "syncInterval": (
                current.get("syncInterval") if sync_interval is None else sync_interval
            ),
            "config": merged_config,
        }

        mutation = """
        mutation($targets: [StorageTargetInput]!) {
          storage {
            updateTargets(targets: $targets) {
              responseResult { succeeded errorCode message }
            }
          }
        }
        """
        data = await client.execute(
            mutation,
            {"targets": [target_input]},
            operation="storage_target_update",
        )
        result = data.get("storage", {}).get("updateTargets", {})
        _check_response_result(result.get("responseResult", {}), "storage_target_update")
        return {"status": "updated", "target_key": target_key}
