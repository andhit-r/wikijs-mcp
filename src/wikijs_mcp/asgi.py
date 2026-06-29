"""ASGI entrypoint untuk deployment HTTP (dipakai uvicorn / Docker).

Auth sudah menempel pada objek ``mcp`` (lihat server.py). Modul ini membungkus
MCP app dengan transport Streamable HTTP lalu menambah endpoint ``/health`` untuk
health check container.

Jalankan::

    uvicorn wikijs_mcp.asgi:app --host 0.0.0.0 --port 8000

PENTING — dua hal yang WAJIB benar saat membungkus MCP app dalam Starlette:

1. ``lifespan=_mcp_app.lifespan`` HARUS dioper ke Starlette. Tanpa itu,
   ``StreamableHTTPSessionManager`` milik MCP tidak pernah diinisialisasi, sehingga
   setiap request MCP crash dengan ``RuntimeError: Task group is not initialized``.
2. Endpoint ``/health`` perlu ditambah sendiri — ``mcp.http_app()`` tidak
   menyediakannya. Tanpa ini, health check Docker/Compose selalu ``unhealthy``.
"""

from __future__ import annotations

import logging

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .server import create_server

logger = logging.getLogger(__name__)

_mcp = create_server()
_mcp_app = _mcp.http_app()


async def health(request: Request) -> JSONResponse:
    """Health check ringan untuk Docker/Compose — tidak menyentuh MCP/auth."""
    return JSONResponse({"status": "ok"})


# lifespan WAJIB dioper agar StreamableHTTPSessionManager terinisialisasi.
app = Starlette(
    lifespan=_mcp_app.lifespan,
    routes=[
        Route("/health", health),
        Mount("/", app=_mcp_app),
    ],
)
logger.info("ASGI app siap (wikijs-mcp, Streamable HTTP + /health)")
