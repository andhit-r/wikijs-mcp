# wikijs-mcp

MCP server untuk mengakses **Wiki.js** melalui GraphQL API, dibangun dengan FastMCP (Python).

## Tool yang Diekspos

| Domain | Tool |
|--------|------|
| pages | `wikijs_page_list`, `wikijs_page_get`, `wikijs_page_get_by_path`, `wikijs_page_create`, `wikijs_page_update`, `wikijs_page_delete`, `wikijs_page_move`, `wikijs_page_render`, `wikijs_page_tree` |
| search | `wikijs_page_search` |
| tags | `wikijs_tag_list`, `wikijs_page_list_by_tags` |
| groups | `wikijs_group_list`, `wikijs_group_get`, `wikijs_group_create`, `wikijs_group_update`, `wikijs_group_delete`, `wikijs_group_assign_user`, `wikijs_group_unassign_user` |
| users | `wikijs_user_list`, `wikijs_user_get`, `wikijs_user_create`, `wikijs_user_update`, `wikijs_user_delete`, `wikijs_user_activate`, `wikijs_user_deactivate`, `wikijs_user_enable_tfa`, `wikijs_user_disable_tfa` |
| system | `wikijs_system_info` |
| mail | `wikijs_mail_update_config`, `wikijs_mail_send_test` |
| storage | `wikijs_storage_target_list`, `wikijs_storage_status`, `wikijs_storage_action_execute`, `wikijs_storage_target_update` |

> **Domain `mail` menuntut hak `manage:system`.** Berbeda dari domain lain, kedua tool
> `mail` hanya bisa dipakai dengan API key Wiki.js milik grup Administrators (hak
> `manage:system`). `wikijs_mail_update_config` juga bersifat REPLACE-ALL — satu
> panggilan menimpa seluruh konfigurasi mail instance, bukan hanya field yang disebut.

> **Domain `storage` juga menuntut hak `manage:system`.** Keempat tool `storage` hanya
> bisa dipakai dengan API key milik grup Administrators. **Force Sync** (tombol di
> *Admin → Storage*) dijalankan dengan
> `wikijs_storage_action_execute(target_key="git", handler="sync")`.
> `wikijs_storage_target_list` menyensor nilai konfigurasi yang bersifat kredensial
> (`basicPassword`, `sshPrivateKeyContent`) menjadi `***` — nilai aslinya tidak bisa
> dibaca lewat MCP. Handler tidak di-daftar-putih: pakai `actions` dari
> `wikijs_storage_target_list` untuk menemukan handler yang tersedia, dan perhatikan
> bahwa sebagian di antaranya destruktif (`purge` menghapus repo Git lokal, `importAll`
> menimpa konten wiki dari repo lokal).
>
> `wikijs_storage_target_update(target_key, is_enabled, mode, sync_interval, config)`
> mengubah konfigurasi **satu** target dengan semantik **partial update**: argumen yang
> tidak diisi berarti "jangan ubah", dan `config` di-merge per key. Mutation Wiki.js di
> baliknya (`storage.updateTargets`) sebenarnya REPLACE-ALL, jadi tool melakukan
> read-modify-write sendiri agar field yang tak disebut tidak terhapus. Key `config` yang
> belum ada pada target ditolak (`ValueError`), begitu pula nilai `"***"` — itu sentinel
> redaksi `wikijs_storage_target_list`, bukan kredensial asli.

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
