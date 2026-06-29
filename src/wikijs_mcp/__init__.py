"""wikijs-mcp.

MCP (Model Context Protocol) server untuk mengakses Wiki.js melalui GraphQL API,
dibangun di atas FastMCP.

Modul-modul penting:
    - ``config``  : pemuatan konfigurasi dari environment variable.
    - ``client``  : klien GraphQL async ke Wiki.js beserta penanganan error.
    - ``auth``    : pembentukan auth provider (OAuth / API key).
    - ``server``  : perakitan instance FastMCP dan registrasi seluruh tool.
    - ``tools``   : implementasi tool per domain Wiki.js.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
