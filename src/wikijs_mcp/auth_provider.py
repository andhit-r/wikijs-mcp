"""Auth provider pintu depan MCP: Authentik OAuth + API key statis.

  AuthentikProvider     — subclass OAuthProxy yang memakai Authentik sebagai IdP
      (OAuth 2.0 Authorization Code + PKCE). Token diverifikasi via JWKS Authentik.
      Dipakai oleh klien berbasis browser (Claude.ai). Opsional: batasi akses ke
      username tertentu via AUTHENTIK_ALLOWED_USERNAMES.

  BearerApiKeyVerifier  — TokenVerifier sederhana untuk static Bearer token.
      Dipakai klien non-OAuth (VS Code/CLI).

Pemakaian (lihat auth.py): keduanya bisa digabung via MultiAuth.

Pitfall #3 (dari IMPLEMENTATION_PLAN.md): ``TokenError`` hanya pakai ``error_code``
valid OAuth/MCP: ``invalid_request``, ``invalid_client``, ``invalid_grant``,
``unauthorized_client``, ``unsupported_grant_type``, ``invalid_scope``. Kode lain
(mis. ``access_denied``) memicu Pydantic ValidationError dan crash token exchange.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.auth.oauth_proxy.proxy import OAuthProxy
from fastmcp.server.auth.providers.jwt import JWTVerifier
from mcp.server.auth.provider import TokenError

logger = logging.getLogger(__name__)


class AuthentikProvider(OAuthProxy):
    """OAuthProxy yang memakai Authentik sebagai identity provider.

    URL endpoint Authentik dibangun otomatis dari ``authentik_base_url`` dan
    ``application_slug`` (Authentik 2024+: authorize & token memakai endpoint
    generik tanpa slug; JWKS/issuer/end-session memakai slug).

    Args:
        authentik_base_url: URL dasar Authentik (tanpa trailing slash).
        application_slug: Slug OAuth2/OIDC Provider di Authentik.
        client_id: Client ID dari Authentik OAuth2 Provider.
        client_secret: Client Secret dari Authentik OAuth2 Provider.
        base_url: URL publik MCP server (untuk redirect OAuth).
        allowed_usernames: Daftar ``preferred_username`` yang diizinkan
            (case-insensitive). Kosong/None = semua user yang login diizinkan.
        **kwargs: Diteruskan ke ``OAuthProxy.__init__``.
    """

    def __init__(
        self,
        *,
        authentik_base_url: str,
        application_slug: str,
        client_id: str,
        client_secret: str,
        base_url: str,
        allowed_usernames: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        base = authentik_base_url.rstrip("/")
        slug = application_slug.strip("/")

        authorize_url = f"{base}/application/o/authorize/"
        token_url = f"{base}/application/o/token/"
        jwks_url = f"{base}/application/o/{slug}/jwks/"
        revoke_url = f"{base}/application/o/{slug}/end-session/"
        issuer_url = f"{base}/application/o/{slug}/"
        self._userinfo_url = f"{base}/application/o/userinfo/"

        token_verifier = JWTVerifier(jwks_uri=jwks_url, issuer=issuer_url)

        super().__init__(
            upstream_authorization_endpoint=authorize_url,
            upstream_token_endpoint=token_url,
            upstream_client_id=client_id,
            upstream_client_secret=client_secret,
            upstream_revocation_endpoint=revoke_url,
            token_verifier=token_verifier,
            base_url=base_url,
            valid_scopes=["openid", "profile", "email"],
            **kwargs,
        )

        self._allowed_usernames: frozenset[str] = frozenset(
            u.lower().strip() for u in (allowed_usernames or []) if u.strip()
        )
        logger.debug(
            "AuthentikProvider siap — issuer: %s | allowed: %s",
            issuer_url,
            list(self._allowed_usernames) or "(semua diizinkan)",
        )

    async def _extract_upstream_claims(self, idp_tokens: dict[str, Any]) -> dict[str, Any] | None:
        """Ambil klaim user dari Authentik userinfo dan validasi akses.

        Dipanggil sekali saat pertukaran authorization code. Bila
        ``allowed_usernames`` diisi dan username tidak termasuk, raise TokenError
        sehingga FastMCP JWT tidak diterbitkan.

        Args:
            idp_tokens: Response token dari Authentik (berisi ``access_token``).

        Returns:
            Dict klaim untuk disematkan di JWT FastMCP.

        Raises:
            TokenError: access_token kosong, userinfo tak terjangkau/invalid,
                atau username tidak diizinkan. ``error_code`` (argumen pertama)
                HARUS salah satu nilai yang valid di token endpoint MCP/OAuth:
                ``invalid_request``, ``invalid_client``, ``invalid_grant``,
                ``unauthorized_client``, ``unsupported_grant_type``,
                ``invalid_scope``.
        """
        access_token = idp_tokens.get("access_token", "")
        if not access_token:
            raise TokenError("invalid_grant", "Upstream access token tidak tersedia")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self._userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except httpx.RequestError as exc:
            logger.warning("Gagal menghubungi Authentik userinfo: %s", exc)
            raise TokenError(
                "invalid_request", "Tidak dapat memverifikasi identitas dari Authentik"
            ) from exc

        if response.status_code != 200:
            logger.warning("Authentik userinfo menolak token (status=%d)", response.status_code)
            raise TokenError("invalid_grant", "Token Authentik tidak valid atau kedaluwarsa")

        userinfo = response.json()
        username: str = (
            (userinfo.get("preferred_username") or userinfo.get("sub", "")).lower().strip()
        )
        if not username:
            raise TokenError("invalid_grant", "Tidak dapat mengambil username dari Authentik")

        if self._allowed_usernames and username not in self._allowed_usernames:
            logger.warning("Akses ditolak untuk user Authentik '%s'", username)
            raise TokenError("unauthorized_client", f"User '{username}' tidak diizinkan")

        logger.info("User Authentik '%s' berhasil diautentikasi", username)
        return {
            "username": username,
            "email": userinfo.get("email"),
            "name": userinfo.get("name"),
            "sub": userinfo.get("sub"),
            "groups": userinfo.get("groups", []),
        }


class BearerApiKeyVerifier(TokenVerifier):
    """TokenVerifier yang memvalidasi static Bearer token (API key).

    Untuk klien tanpa OAuth (VS Code/CLI/otomasi). Token valid = nilai persis
    ``MCP_API_KEY``.

    Args:
        api_key: API key statis (wajib non-kosong).

    Raises:
        ValueError: Bila ``api_key`` kosong/spasi.
    """

    def __init__(self, *, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("api_key tidak boleh kosong")
        self._api_key = api_key

    async def verify_token(self, token: str) -> AccessToken | None:
        """Kembalikan AccessToken bila token cocok dengan API key, else None.

        Args:
            token: Bearer token dari header Authorization request.

        Returns:
            ``AccessToken`` bila cocok, ``None`` bila tidak cocok.
        """
        if token == self._api_key:
            return AccessToken(token=token, client_id="api-key-client", scopes=[])
        return None
