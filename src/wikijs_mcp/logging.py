"""Utilitas logging terpusat untuk wikijs-mcp.

Menyediakan ``get_logger`` dan ``configure_logging`` agar seluruh modul memakai
konfigurasi log yang konsisten. Level log diambil dari ``MCP_LOG_LEVEL``.
"""

from __future__ import annotations

import logging

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Konfigurasikan root logging satu kali.

    Args:
        level: Nama level log (``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``).
            Nilai tidak dikenal akan jatuh ke ``INFO``.
    """
    global _CONFIGURED
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Kembalikan logger bernama ``name``.

    Args:
        name: Nama logger (biasanya ``__name__`` modul pemanggil).

    Returns:
        Instance ``logging.Logger``.
    """
    return logging.getLogger(name)
