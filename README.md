# wikijs-mcp

MCP server untuk mengakses **Wiki.js** melalui GraphQL API, dibangun dengan FastMCP (Python).

## Tool yang Diekspos

| Domain | Tool |
|--------|------|
| pages | `wikijs_page_list`, `wikijs_page_get`, `wikijs_page_get_by_path`, `wikijs_page_create`, `wikijs_page_update`, `wikijs_page_delete`, `wikijs_page_move`, `wikijs_page_render`, `wikijs_page_tree` |
| search | `wikijs_page_search` |
| tags | `wikijs_tag_list`, `wikijs_page_list_by_tags` |
| system | `wikijs_system_info` |
| mail | `wikijs_mail_update_config`, `wikijs_mail_send_test` |

> **Domain `mail` menuntut hak `manage:system`.** Berbeda dari domain lain, kedua tool
> `mail` hanya bisa dipakai dengan API key Wiki.js milik grup Administrators (hak
> `manage:system`). `wikijs_mail_update_config` juga bersifat REPLACE-ALL — satu
> panggilan menimpa seluruh konfigurasi mail instance, bukan hanya field yang disebut.

## Konfigurasi

Salin `.env.example` menjadi `.env` dan isi nilai yang sesuai:

```bash
cp .env.example .env
```

### Variabel Wajib

| Variabel | Keterangan |
|----------|-----------|
| `WIKIJS_URL` | URL dasar instance Wiki.js, mis. `https://wiki.example.com` |
| `WIKIJS_API_KEY` | API key Wiki.js (Admin → API Access) |

## Cara Pakai

### stdio (Claude Desktop / VS Code)

```json
{
  "mcpServers": {
    "wikijs": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/andhit-r/wikijs-mcp", "wikijs-mcp"],
      "env": {
        "WIKIJS_URL": "https://wiki.example.com",
        "WIKIJS_API_KEY": "your-api-key"
      }
    }
  }
}
```

### HTTP + API Key (Claude Code / VS Code remote)

```bash
docker run -p 8000:8000 \
  -e WIKIJS_URL=https://wiki.example.com \
  -e WIKIJS_API_KEY=your-wikijs-api-key \
  -e MCP_API_KEY=your-mcp-api-key \
  ghcr.io/andhit-r/wikijs-mcp:latest
```

### HTTP + Authentik OAuth (Claude Web)

Isi semua variabel `AUTHENTIK_*` dan `MCP_BASE_URL` di `.env`, lalu:

```bash
docker run -p 8000:8000 --env-file .env ghcr.io/andhit-r/wikijs-mcp:latest
```

## Lisensi

MIT
