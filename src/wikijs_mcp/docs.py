"""Dokumentasi API berbasis Swagger/OpenAPI untuk endpoint HTTP MCP server.

Menambahkan rute dokumentasi:

* ``GET /openapi.json`` — dokumen OpenAPI 3.1 dari tool MCP yang terdaftar.
* ``GET /docs``         — halaman Swagger UI.
* ``GET /health``       — health check sederhana (juga ada di asgi.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

if TYPE_CHECKING:
    from fastmcp import FastMCP

_MCP_PATH = "/mcp/"

_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>wikijs-mcp — API Docs</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = () => {
      window.ui = SwaggerUIBundle({
        url: "/openapi.json",
        dom_id: "#swagger-ui",
        deepLinking: true,
      });
    };
  </script>
</body>
</html>
"""


async def build_openapi_spec(mcp: FastMCP, version: str) -> dict[str, Any]:
    """Bangun dokumen OpenAPI 3.1 dari tool MCP yang terdaftar.

    Args:
        mcp: Instance FastMCP yang sudah memiliki tool terdaftar.
        version: Versi aplikasi untuk field ``info.version``.

    Returns:
        Dict dokumen OpenAPI 3.1 siap di-serialisasi ke JSON.
    """
    tools = await mcp.list_tools()
    paths: dict[str, Any] = {}

    for tool in sorted(tools, key=lambda t: t.name):
        tags = sorted(tool.tags) if getattr(tool, "tags", None) else ["tools"]
        request_schema = tool.parameters or {"type": "object", "properties": {}}
        paths[f"/tools/{tool.name}"] = {
            "post": {
                "summary": (tool.description or tool.name).strip().splitlines()[0],
                "description": tool.description or "",
                "operationId": tool.name,
                "tags": tags,
                "requestBody": {
                    "required": bool(request_schema.get("required")),
                    "content": {"application/json": {"schema": request_schema}},
                },
                "responses": {
                    "200": {
                        "description": "Hasil eksekusi tool (struktur tergantung tool).",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        }

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "wikijs-mcp",
            "version": version,
            "description": (
                "MCP server untuk mengakses Wiki.js. Endpoint protokol MCP "
                f"tersedia di `{_MCP_PATH}`. Path `/tools/{{nama}}` di bawah ini "
                "adalah representasi dokumentatif tiap tool MCP beserta skema "
                "parameternya — tool dipanggil melalui protokol MCP, bukan REST."
            ),
        },
        "paths": paths,
    }


def register_docs_routes(mcp: FastMCP, version: str) -> None:
    """Daftarkan rute dokumentasi (``/docs``, ``/openapi.json``, ``/health``).

    Args:
        mcp: Instance FastMCP tempat rute kustom ditambahkan.
        version: Versi aplikasi yang ditampilkan di dokumen OpenAPI.
    """

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> JSONResponse:
        """Health check sederhana untuk liveness/readiness probe."""
        return JSONResponse({"status": "ok", "service": "wikijs-mcp", "version": version})

    @mcp.custom_route("/openapi.json", methods=["GET"])
    async def openapi(_request: Request) -> JSONResponse:
        """Kembalikan dokumen OpenAPI 3.1 yang dihasilkan dari tool MCP."""
        return JSONResponse(await build_openapi_spec(mcp, version))

    @mcp.custom_route("/docs", methods=["GET"])
    async def docs(_request: Request) -> HTMLResponse:
        """Sajikan halaman Swagger UI."""
        return HTMLResponse(_SWAGGER_HTML)
