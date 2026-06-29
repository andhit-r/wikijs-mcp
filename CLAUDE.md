# CLAUDE.md

Panduan untuk Claude Code saat bekerja dengan repo ini.

## Ringkasan Proyek

`wikijs-mcp` adalah **MCP server** (Model Context Protocol) yang mengakses
**Wiki.js** melalui **GraphQL API** (`/graphql`), dibangun di atas **FastMCP**
(Python). Server mengekspos tool per domain dengan prefix `wikijs_` dan dapat
dilindungi dengan OAuth (Authentik) maupun API key statis.

## Aturan Wajib

1. **Inspeksi versi package sebelum menulis kode.** Jangan berasumsi tentang
   API pihak ketiga. Versi acuan: **fastmcp 3.3+**, **httpx 0.28.x**, **pydantic 2.x**.
2. **Jangan hardcode credential atau URL.** Semua konfigurasi lewat environment
   variable melalui `src/wikijs_mcp/config.py` (pydantic-settings).
3. **Selalu tulis/perbarui docstring** setiap menambah atau mengubah kode.
   Gaya: Google style (Args/Returns/Raises), Bahasa Indonesia.
4. **Selalu gunakan `make` untuk test/lint.** Jangan jalankan `pytest`/`ruff`/`black`/
   `isort` langsung. Gunakan `make test` / `make lint` / `make build`.

## Perbedaan Utama dari authentik-mcp

- Authentik-mcp memakai **REST** (`/api/v3`). Wiki.js memakai **GraphQL** tunggal di
  `/graphql`. Satu metode inti: `client.execute(query, variables)`.
- Prefix tool: `wikijs_` (bukan `authentik_`).
- Mutation Wiki.js mengembalikan `responseResult { succeeded errorCode message }`.
  HTTP 200 + `succeeded=false` **bukan** sukses — cek dengan `_check_response_result`.

## Struktur Direktori

```
src/wikijs_mcp/
  config.py          -> Settings (pydantic-settings) + get_settings()
  client.py          -> WikiJSGraphQLClient + WikiJSAPIError
  auth.py            -> build_token_verifier() — pemilihan auth otomatis
  auth_provider.py   -> AuthentikProvider + BearerApiKeyVerifier
  docs.py            -> rute /health, /docs, /openapi.json
  asgi.py            -> ASGI app (Starlette wrap + /health + lifespan)
  logging.py         -> configure_logging(), get_logger()
  server.py          -> create_server(), run()
  __main__.py        -> entrypoint: pilih transport
  tools/             -> satu modul per domain; tiap modul punya register(mcp, client)
    __init__.py      -> register_all(); _MODULES (urutan registrasi)
    pages.py         -> tool domain "pages"
    search.py        -> tool domain "search"
    tags.py          -> tool domain "tags"
    system.py        -> tool domain "system"
tests/               -> pytest + respx (mock HTTP GraphQL)
```

## Arsitektur Auth

`build_token_verifier()` di `auth.py` memilih otomatis:

1. **Authentik OAuth + API Key (MultiAuth)**: bila keduanya aktif.
2. **Authentik OAuth saja**: `AuthentikProvider` — OAuth Proxy + DCR untuk Claude.ai.
3. **API Key saja**: `BearerApiKeyVerifier` — static Bearer token untuk CLI/VS Code.
4. **None**: tanpa auth (stdio lokal).

## Konvensi Kode

- **Penamaan tool**: `wikijs_<domain>_<aksi>`, mis. `wikijs_page_get`, `wikijs_page_create`.
- **Registrasi tool**: setiap modul di `tools/` mengekspos
  `def register(mcp: FastMCP, client: WikiJSGraphQLClient) -> None`.
- **Akses GraphQL**: selalu via `client.execute(query, variables)`. Jangan httpx langsung.
- **Mutation check**: setiap mutation harus memanggil `_check_response_result(rr, op)`.
- **Error HTTP Wiki.js**: dikelola di `client.py`; validasi input → `ValueError`.

## Menambah Tool Baru

1. Verifikasi query/mutation GraphQL pada instance Wiki.js target.
2. Tambah fungsi di modul domain terkait (atau buat modul baru + daftar di `_MODULES`).
3. Beri nama `wikijs_<domain>_<aksi>`, tambahkan docstring Args/Returns/Raises.
4. Untuk mutation: panggil `_check_response_result(data["domain"]["op"]["responseResult"], "op")`.
5. Tulis unit test mock (respx) untuk happy path + ≥1 jalur error.
6. Jalankan `make test`. Pastikan hijau.

## Test

```bash
make build    # bangun image test
make lint     # ruff check + isort check + black check
make unit     # pytest
make test     # lint + unit (gate lengkap)
make clean    # hapus image test
```

## Git & Rilis

- Branch utama: **master**. Commit message dalam **Bahasa Indonesia**.
- **Jangan `git commit`** kecuali diminta eksplisit.
- Tag `vX.Y.Z` memicu workflow Release (GitHub Release + image GHCR).

## Yang TIDAK Boleh

- Hardcode URL, secret, atau API key di kode.
- Memanggil instance Wiki.js sungguhan dari unit test (selalu mock respx).
- Menebak nama field GraphQL — verifikasi via introspeksi dulu.
- Menjalankan pytest/ruff/black/isort langsung (selalu via `make`).
