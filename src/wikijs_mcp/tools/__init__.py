"""Paket berisi seluruh tool MCP, dikelompokkan per domain Wiki.js.

Setiap submodul mengekspos fungsi ``register(mcp, client)`` yang mendaftarkan
tool-tool domainnya ke instance FastMCP. Fungsi :func:`register_all` di sini
memanggil seluruh ``register`` tersebut.
"""

from __future__ import annotations

from fastmcp import FastMCP

from ..client import WikiJSGraphQLClient
from . import groups, mail, pages, search, storage, system, tags, users

# Urutan modul menentukan urutan registrasi (dan urutan tampil di dokumentasi).
_MODULES = [
    pages,
    search,
    tags,
    groups,
    users,
    system,
    mail,
    storage,
]


def register_all(mcp: FastMCP, client: WikiJSGraphQLClient) -> None:
    """Daftarkan seluruh tool dari setiap domain ke server MCP.

    Args:
        mcp: Instance FastMCP tempat tool didaftarkan.
        client: Klien Wiki.js bersama yang dipakai semua tool.
    """
    for module in _MODULES:
        module.register(mcp, client)
