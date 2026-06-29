"""Titik masuk CLI wikijs-mcp.

Jalankan dengan::

    python -m wikijs_mcp

atau melalui console script::

    wikijs-mcp
"""

from __future__ import annotations

import sys

from .logging import configure_logging, get_logger
from .server import run

logger = get_logger(__name__)


def main() -> int:
    """Jalankan server MCP. Mengembalikan exit code proses.

    Returns:
        ``0`` bila keluar normal, ``1`` bila terjadi error konfigurasi/fatal.
    """
    try:
        run()
        return 0
    except ValueError as exc:
        configure_logging()
        logger.error("Konfigurasi tidak valid: %s", exc)
        return 1
    except KeyboardInterrupt:
        logger.info("Dihentikan oleh pengguna.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
