"""Test untuk modul konfigurasi (:mod:`wikijs_mcp.config`)."""

from __future__ import annotations

import pytest

from tests.conftest import make_settings
from wikijs_mcp.config import Settings


def test_graphql_endpoint_strips_trailing_slash() -> None:
    s = make_settings(wikijs_url="https://wiki.example.com/")
    assert s.wikijs_url == "https://wiki.example.com"
    assert s.graphql_endpoint == "https://wiki.example.com/graphql"


def test_graphql_endpoint_correct() -> None:
    s = make_settings(wikijs_url="https://wiki.example.com")
    assert s.graphql_endpoint == "https://wiki.example.com/graphql"


def test_authentik_active_false_when_incomplete() -> None:
    s = make_settings()
    assert s.authentik_active is False


def test_authentik_active_true_when_complete() -> None:
    s = make_settings(
        authentik_base_url="https://auth.example.com",
        authentik_app_slug="wikijs-mcp",
        authentik_client_id="cid",
        authentik_client_secret="secret",
        mcp_base_url="https://mcp.example.com",
    )
    assert s.authentik_active is True


def test_require_api_config_raises_when_missing() -> None:
    s = make_settings(wikijs_url="", wikijs_api_key="")
    with pytest.raises(ValueError) as exc:
        s.require_api_config()
    assert "WIKIJS_URL" in str(exc.value)
    assert "WIKIJS_API_KEY" in str(exc.value)


def test_require_api_config_raises_when_url_missing() -> None:
    s = make_settings(wikijs_url="")
    with pytest.raises(ValueError) as exc:
        s.require_api_config()
    assert "WIKIJS_URL" in str(exc.value)


def test_require_api_config_ok_when_complete() -> None:
    s = make_settings()
    s.require_api_config()  # tidak raise


def test_invalid_transport_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, wikijs_url="x", wikijs_api_key="y", mcp_transport="grpc")


def test_authentik_allowed_usernames_comma_separated(monkeypatch) -> None:
    """settings_customise_sources harus menerima format comma-separated dari env."""
    monkeypatch.setenv("AUTHENTIK_ALLOWED_USERNAMES", "alice,bob")
    s = Settings(_env_file=None, wikijs_url="x", wikijs_api_key="y")
    assert s.authentik_allowed_usernames == ["alice", "bob"]


def test_authentik_allowed_usernames_single(monkeypatch) -> None:
    """settings_customise_sources harus menerima nilai tunggal dari env."""
    monkeypatch.setenv("AUTHENTIK_ALLOWED_USERNAMES", "alice")
    s = Settings(_env_file=None, wikijs_url="x", wikijs_api_key="y")
    assert s.authentik_allowed_usernames == ["alice"]


def test_authentik_allowed_usernames_json_array(monkeypatch) -> None:
    """settings_customise_sources harus menerima JSON array dari env."""
    monkeypatch.setenv("AUTHENTIK_ALLOWED_USERNAMES", '["alice", "bob"]')
    s = Settings(_env_file=None, wikijs_url="x", wikijs_api_key="y")
    assert s.authentik_allowed_usernames == ["alice", "bob"]


def test_authentik_allowed_usernames_empty(monkeypatch) -> None:
    """settings_customise_sources harus kembalikan list kosong bila env kosong."""
    monkeypatch.setenv("AUTHENTIK_ALLOWED_USERNAMES", "")
    s = Settings(_env_file=None, wikijs_url="x", wikijs_api_key="y")
    assert s.authentik_allowed_usernames == []
