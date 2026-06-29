"""Konfigurasi aplikasi dari environment variable.

Seluruh konfigurasi wikijs-mcp dibaca dari environment variable (atau file
``.env``) menggunakan ``pydantic-settings``. Tidak ada credential atau URL yang
di-hardcode di dalam kode.

Penggunaan::

    from wikijs_mcp.config import get_settings

    settings = get_settings()
    print(settings.wikijs_url)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Kumpulan konfigurasi wikijs-mcp.

    Atribut dipetakan dari environment variable dengan nama uppercase yang sama
    (case-insensitive). Nilai sensitif disimpan sebagai ``SecretStr`` agar tidak
    tercetak saat objek di-repr/di-log.

    Attributes:
        wikijs_url: URL dasar instance Wiki.js, mis. ``https://wiki.example.com``.
            Trailing slash akan dihapus otomatis.
        wikijs_api_key: API key Wiki.js (Admin → System → API Access).
        wikijs_timeout: Timeout (detik) tiap request ke Wiki.js GraphQL.
        wikijs_verify_ssl: Apakah memverifikasi sertifikat TLS Wiki.js.
        authentik_base_url: URL dasar Authentik untuk OAuth Proxy.
        authentik_app_slug: Slug OAuth2/OIDC Provider di Authentik.
        authentik_client_id: Client ID dari Authentik OAuth2 Provider.
        authentik_client_secret: Client Secret dari Authentik OAuth2 Provider.
        authentik_allowed_usernames: Daftar ``preferred_username`` yang diizinkan
            (kosong = semua user yang login diizinkan). Diterima dalam tiga format:
            JSON array (``["alice","bob"]``), comma-separated (``alice,bob``),
            atau nilai tunggal (``alice``).
        mcp_api_key: API key statis untuk klien non-OAuth (VS Code/CLI).
        mcp_transport: Transport FastMCP: ``http`` atau ``stdio``.
        mcp_host: Host bind saat transport http.
        mcp_port: Port bind saat transport http.
        mcp_log_level: Level logging.
        mcp_base_url: URL publik MCP server (untuk OAuth metadata & callback).
    """

    model_config = SettingsConfigDict(
        env_ignore_empty=True,
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Koneksi Wiki.js GraphQL API ---
    wikijs_url: str = Field(default="", description="URL dasar instance Wiki.js.")
    wikijs_api_key: SecretStr = Field(default=SecretStr(""), description="API key Wiki.js.")
    wikijs_timeout: float = Field(default=30.0, ge=1.0)
    wikijs_verify_ssl: bool = Field(default=True)

    # --- OAuth Authentik (pintu depan — untuk Claude Web) ---
    authentik_base_url: str = Field(default="")
    authentik_app_slug: str = Field(default="")
    authentik_client_id: str = Field(default="")
    authentik_client_secret: SecretStr = Field(default=SecretStr(""))
    authentik_allowed_usernames: list[str] = Field(default=[])

    # --- API key statis (untuk VS Code / CLI) ---
    mcp_api_key: str = Field(default="")

    # --- Runtime MCP ---
    mcp_transport: str = Field(default="http")
    mcp_host: str = Field(default="0.0.0.0")
    mcp_port: int = Field(default=8000, ge=1, le=65535)
    mcp_log_level: str = Field(default="INFO")
    mcp_base_url: str = Field(default="")

    @field_validator("wikijs_url", "mcp_base_url", "authentik_base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        """Hapus trailing slash agar penggabungan path konsisten."""
        return value.rstrip("/") if value else value

    @field_validator("mcp_transport")
    @classmethod
    def _validate_transport(cls, value: str) -> str:
        """Pastikan transport yang dipilih didukung."""
        allowed = {"http", "stdio"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError(
                f"MCP_TRANSPORT tidak valid: {value!r}. Pilih salah satu dari {allowed}."
            )
        return normalized

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple:
        """Terima ``authentik_allowed_usernames`` sebagai JSON / comma-separated / tunggal.

        Patch WAJIB dikenakan ke DUA source — env_settings (OS env) DAN dotenv_settings
        (file .env) — agar format plain/comma diterima dari keduanya.
        """

        def _lenient(source: Any) -> Any:
            original = source.decode_complex_value

            def decode(field_name: str, field: Any, value: Any) -> Any:
                if field_name == "authentik_allowed_usernames" and isinstance(value, str):
                    v = value.strip()
                    if not v:
                        return []
                    if not v.startswith("["):
                        return [u.strip() for u in v.split(",") if u.strip()]
                return original(field_name, field, value)

            source.decode_complex_value = decode
            return source

        return (
            init_settings,
            _lenient(env_settings),
            _lenient(dotenv_settings),
            file_secret_settings,
        )

    @property
    def graphql_endpoint(self) -> str:
        """URL endpoint GraphQL Wiki.js, mis. ``https://wiki.example.com/graphql``."""
        return f"{self.wikijs_url}/graphql"

    @property
    def authentik_active(self) -> bool:
        """True bila konfigurasi OAuth Authentik lengkap untuk OAuth Proxy."""
        return bool(
            self.authentik_base_url
            and self.authentik_app_slug
            and self.authentik_client_id
            and self.authentik_client_secret.get_secret_value()
            and self.mcp_base_url
        )

    def require_api_config(self) -> None:
        """Validasi bahwa konfigurasi minimum Wiki.js API tersedia.

        Raises:
            ValueError: Bila ``WIKIJS_URL`` atau ``WIKIJS_API_KEY`` kosong.
        """
        missing = []
        if not self.wikijs_url:
            missing.append("WIKIJS_URL")
        if not self.wikijs_api_key.get_secret_value():
            missing.append("WIKIJS_API_KEY")
        if missing:
            raise ValueError(
                "Konfigurasi wajib belum diisi: " + ", ".join(missing) + ". "
                "Set environment variable tersebut atau isi file .env."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Kembalikan instance ``Settings`` singleton (di-cache).

    Returns:
        Objek ``Settings`` yang dibaca dari environment/``.env``.
    """
    return Settings()
