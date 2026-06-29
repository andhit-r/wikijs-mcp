"""Pemilihan auth provider MCP berdasarkan konfigurasi.

Auth pintu depan dipilih otomatis berdasarkan env vars yang tersedia:

1. **Authentik OAuth + API Key (MultiAuth)**: bila keduanya aktif.
2. **Authentik OAuth saja** (``AuthentikProvider``): OAuth Proxy + DCR untuk Claude.ai.
   Pengguna login via Authentik; ``AUTHENTIK_ALLOWED_USERNAMES`` membatasi akses.
3. **API Key saja** (``BearerApiKeyVerifier``): static Bearer token untuk CLI/VS Code.
4. **None**: tanpa autentikasi (stdio lokal — jangan pakai di produksi).
"""

from __future__ import annotations

from .config import Settings
from .logging import get_logger

logger = get_logger(__name__)


def build_token_verifier(settings: Settings):
    """Bangun auth provider dari konfigurasi (lihat docstring modul untuk urutan).

    Args:
        settings: Konfigurasi aplikasi.

    Returns:
        AuthentikProvider, MultiAuth, BearerApiKeyVerifier dalam MultiAuth, atau None.
    """
    authentik_aktif = settings.authentik_active
    api_key_aktif = bool(settings.mcp_api_key)

    if authentik_aktif and api_key_aktif:
        return _build_multi_auth(settings)

    if authentik_aktif:
        return _build_authentik_provider(settings)

    if api_key_aktif:
        return _build_api_key_only(settings)

    logger.warning(
        "Konfigurasi auth tidak lengkap — MCP server berjalan TANPA autentikasi. "
        "Jangan gunakan mode ini di produksi."
    )
    return None


def _build_authentik_provider(settings: Settings):
    """Bangun AuthentikProvider (OAuth Proxy + DCR) untuk login Authentik."""
    from .auth_provider import AuthentikProvider

    allowed = settings.authentik_allowed_usernames

    logger.info(
        "Autentikasi MCP aktif: AuthentikProvider — slug: %s | base_url: %s | allowed: %s.",
        settings.authentik_app_slug,
        settings.mcp_base_url,
        allowed or "(semua diizinkan)",
    )

    return AuthentikProvider(
        authentik_base_url=settings.authentik_base_url,
        application_slug=settings.authentik_app_slug,
        client_id=settings.authentik_client_id,
        client_secret=settings.authentik_client_secret.get_secret_value(),
        base_url=settings.mcp_base_url,
        allowed_usernames=allowed or None,
        require_authorization_consent="external",
    )


def _build_api_key_only(settings: Settings):
    """Bangun MultiAuth dengan BearerApiKeyVerifier saja (tanpa OAuth)."""
    from fastmcp.server.auth import MultiAuth

    from .auth_provider import BearerApiKeyVerifier

    logger.info("Autentikasi MCP aktif: API Key saja (tanpa OAuth).")
    return MultiAuth(verifiers=[BearerApiKeyVerifier(api_key=settings.mcp_api_key)])


def _build_multi_auth(settings: Settings):
    """Bangun MultiAuth: Authentik OAuth + BearerApiKeyVerifier."""
    from fastmcp.server.auth import MultiAuth

    from .auth_provider import AuthentikProvider, BearerApiKeyVerifier

    allowed = settings.authentik_allowed_usernames

    logger.info(
        "Autentikasi MCP aktif: MultiAuth (Authentik OAuth + API Key) — slug: %s.",
        settings.authentik_app_slug,
    )

    provider = AuthentikProvider(
        authentik_base_url=settings.authentik_base_url,
        application_slug=settings.authentik_app_slug,
        client_id=settings.authentik_client_id,
        client_secret=settings.authentik_client_secret.get_secret_value(),
        base_url=settings.mcp_base_url,
        allowed_usernames=allowed or None,
        require_authorization_consent="external",
    )
    return MultiAuth(
        server=provider,
        verifiers=[BearerApiKeyVerifier(api_key=settings.mcp_api_key)],
    )
