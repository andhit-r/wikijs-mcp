# Rencana Implementasi: `wikijs-mcp`

> **Dokumen ini adalah rencana eksekusi.** Ditujukan untuk dijalankan langkah-demi-langkah
> oleh sesi Claude (Sonnet). Setiap fase punya tindakan konkret, file yang dibuat, dan
> kriteria selesai. Ikuti urutannya. Patuhi skill yang dirujuk — **jangan menduplikasi**
> logika yang sudah jadi milik skill lain.

## 0. Ringkasan

Membangun **MCP Server** untuk mengakses **Wiki.js** melalui **GraphQL API**-nya
(`{WIKIJS_URL}/graphql`), dibangun dengan **FastMCP (Python)**. Server mengekspos tool
per-domain (pages, search, tags, system) dengan prefix `wikijs_`, dapat dipakai via
**stdio, Claude Code, dan Claude Web** (OAuth Authentik), dan dirilis via **GitHub
Release + Docker image GHCR** saat tag `v*` di-push.

- **Distribusi:** `wikijs-mcp` · **Paket Python:** `wikijs_mcp` · **Repo:** `andhit-r/wikijs-mcp`
- **Author:** andhit-r `<andhitia.r@gmail.com>` · **Lisensi:** MIT · **Python:** `>=3.11`
- **Versi acuan dependency:** `fastmcp>=3.3,<4`, `httpx>=0.28,<0.29`, `pydantic>=2,<3`, `pydantic-settings>=2,<3`

### Pola yang diikuti (sumber kebenaran kode)
Tiru **`../authentik-mcp/`** (project saudara di repo yang sama). Ia adalah versi matang
dari scaffold `mcp-development-skill` dan punya struktur yang persis dibutuhkan di sini:
`config.py` (pydantic-settings) · `client.py` (httpx async + error wrapper) ·
`auth.py` + `auth_provider.py` (OAuth Authentik / API key) · `docs.py` (`/health`, `/docs`) ·
`server.py` (`create_server`/`run`) · `logging.py` · `tools/<domain>.py` dengan
`register(mcp, client)` · `tests/` (pytest + respx).

> Perbedaan inti dari authentik-mcp: Authentik memakai **REST** `/api/v3`; Wiki.js memakai
> **GraphQL** tunggal di `/graphql`. Maka `client.py` di sini adalah **GraphQLClient**
> (selalu POST ke `/graphql` dengan `{query, variables}`), bukan REST helper.

### Aturan wajib yang mengikat (dari skill)
1. **Inspeksi versi package sebelum menulis kode.** `pip show fastmcp httpx pydantic`.
   Jangan berasumsi API pihak ketiga.
2. **Tidak ada credential/URL di-hardcode** — semua lewat `config.py` (pydantic-settings).
3. **Docstring wajib** tiap tool/fungsi (Google style, Bahasa Indonesia) — FastMCP memakai
   docstring sebagai deskripsi tool yang dibaca Claude. Delegasi gaya ke skill `docstring`.
4. **Test hanya via `make`** (lihat Fase 6). Jangan jalankan `pytest`/`ruff` langsung.
5. **Verifikasi skema GraphQL Wiki.js sebelum/selama menulis tool** (lihat Fase 3.0) —
   jangan menebak nama field; gunakan introspection dari instance nyata jika tersedia.

---

## 1. Persiapan & Verifikasi Lingkungan

**Tujuan:** pastikan ini benar project baru & tooling tersedia.

- [ ] `wikijs-mcp/` saat ini kosong (selain dokumen rencana ini). Konfirmasi.
- [ ] Pastikan Docker tersedia (untuk gate test). Jika tidak, catat dan lanjutkan;
      verifikasi `make test` ditunda.
- [ ] Catat asumsi: tidak publish ke PyPI (rilis hanya GitHub + GHCR).

**Selesai bila:** lingkungan terkonfirmasi, asumsi tercatat.

---

## 2. Scaffold Struktur Project

**Tujuan:** susun kerangka project profesional & siap rilis (skill `mcp-development`,
referensi `struktur-project.md`).

Salin scaffold dari `~/.claude/skills/mcp-development-skill/assets/fastmcp-python/` **atau**
tiru langsung `../authentik-mcp/` (lebih lengkap), lalu rename:
`mcp_server` → `wikijs_mcp`, `mcp-server` → `wikijs-mcp`, placeholder `OWNER/REPO` →
`andhit-r/wikijs-mcp`.

Struktur target:

```
wikijs-mcp/
├── pyproject.toml              # metadata, deps, entrypoint wikijs-mcp, ruff, pytest
├── README.md                   # (Fase 8 — delegasi skill `readme`)
├── CHANGELOG.md                # Keep a Changelog; entri awal Unreleased
├── LICENSE                     # MIT (author andhit-r)
├── CLAUDE.md                   # panduan repo (tiru authentik-mcp/CLAUDE.md, sesuaikan)
├── .gitignore
├── .dockerignore
├── Dockerfile                  # image runtime server (non-root, uvicorn → asgi:app)
├── .env.example                # WIKIJS_* + MCP_* + AUTHENTIK_* + MCP_API_KEY
├── Makefile                    # (Fase 6 — delegasi skill `automated-test`)
├── Dockerfile.test             # (Fase 6 — delegasi skill `automated-test`)
├── requirements-test.txt       # pin tooling test
├── src/wikijs_mcp/
│   ├── __init__.py             # __version__ = "0.1.0" (sumber tunggal versi)
│   ├── config.py               # Settings (pydantic-settings) + get_settings()
│   ├── client.py               # WikiJSGraphQLClient + WikiJSAPIError
│   ├── auth.py                 # build_token_verifier() (pilih mode auth)
│   ├── auth_provider.py        # AuthentikProvider + BearerApiKeyVerifier
│   ├── docs.py                 # rute /health, /docs, /openapi.json
│   ├── asgi.py                 # ASGI app (Starlette wrap + /health + lifespan)
│   ├── logging.py              # configure_logging(), get_logger()
│   ├── server.py               # create_server(), run()
│   ├── __main__.py             # entrypoint: pilih transport via env
│   └── tools/
│       ├── __init__.py         # register_all(); daftar _MODULES (urutan registrasi)
│       ├── pages.py            # tool domain "pages"
│       ├── search.py           # tool domain "search"
│       ├── tags.py             # tool domain "tags"
│       └── system.py           # tool domain "system"
└── tests/
    ├── conftest.py
    ├── test_config.py          # parse AUTHENTIK_ALLOWED_USERNAMES (3 format)
    ├── test_asgi.py            # boot ASGI + /health + initialize di bawah lifespan
    ├── test_auth.py            # API key + error_code TokenError valid OAuth
    ├── test_client.py          # GraphQL client: sukses + GraphQL `errors` → WikiJSAPIError
    ├── test_pages.py           # tool pages (mock GraphQL via respx)
    ├── test_search.py
    └── test_tags.py
```

**Pitfalls yang WAJIB dipertahankan** (dari `mcp-development-skill/SKILL.md`):
1. **ASGI** (`asgi.py`): bungkus `mcp.http_app()` dengan Starlette, tambah `/health`,
   **oper `lifespan=_mcp_app.lifespan`**. Tanpa lifespan → request MCP crash
   `RuntimeError: Task group is not initialized`. Tanpa `/health` → container `unhealthy`.
2. **Config** `list[str]` dari env: override `settings_customise_sources` agar
   `AUTHENTIK_ALLOWED_USERNAMES` menerima JSON array / comma-separated / nilai tunggal,
   patch **EnvSettingsSource DAN DotEnvSettingsSource**. (Salin apa adanya dari scaffold.)
3. **Auth**: `TokenError` hanya pakai `error_code` valid OAuth/MCP
   (`invalid_request`, `invalid_client`, `invalid_grant`, `unauthorized_client`,
   `unsupported_grant_type`, `invalid_scope`).
4. **Import grouping** rapi (stdlib / third-party / first-party) agar `make lint`
   (ruff + isort profile black + black) hijau sejak awal.

**Selesai bila:** semua file kerangka ada, paket ter-rename, placeholder terganti.

---

## 3. Klien GraphQL Wiki.js (`config.py` + `client.py`)

### 3.0 Verifikasi skema (lakukan dulu)
Wiki.js berevolusi; **jangan menebak field**. Jika ada instance + API key:
```bash
# introspeksi singkat / sanity check
curl -s -X POST "$WIKIJS_URL/graphql" \
  -H "Authorization: Bearer $WIKIJS_API_KEY" -H "Content-Type: application/json" \
  -d '{"query":"{ system { info { currentVersion } } }"}'
```
Jika tidak ada instance, gunakan query/field di bawah (stabil untuk Wiki.js 2.x) dan beri
komentar `# verifikasi terhadap versi Wiki.js target`.

### 3.1 `config.py` — `Settings`
Field (pydantic-settings, baca dari env/`.env`, nilai sensitif `SecretStr`):

| Env | Field | Catatan |
|---|---|---|
| `WIKIJS_URL` | `wikijs_url: str` | base URL, mis. `https://wiki.example.com`; strip trailing slash |
| `WIKIJS_API_KEY` | `wikijs_api_key: SecretStr` | API key Wiki.js (Admin → API Access) |
| `WIKIJS_TIMEOUT` | `wikijs_timeout: float = 30.0` | `ge=1.0` |
| `WIKIJS_VERIFY_SSL` | `wikijs_verify_ssl: bool = True` | |
| `MCP_TRANSPORT/HOST/PORT/LOG_LEVEL/SERVER_NAME/BASE_URL` | runtime MCP | sama spt scaffold |
| `AUTHENTIK_*`, `MCP_API_KEY` | auth pintu depan | sama spt scaffold (Pola A) |

- `@property graphql_endpoint` → `f"{self.wikijs_url}/graphql"`.
- `require_api_config()` → raise `ValueError` bila `WIKIJS_URL`/`WIKIJS_API_KEY` kosong.
- `get_settings()` → `@lru_cache(maxsize=1)`.
- **Pertahankan** `settings_customise_sources` (Pitfall #2) untuk `authentik_allowed_usernames`.

### 3.2 `client.py` — `WikiJSGraphQLClient` + `WikiJSAPIError`
Bungkus `httpx.AsyncClient`. Berbeda dari REST: **satu metode inti** `execute`.

```python
class WikiJSAPIError(Exception):
    # message + opsional: status_code, errors (list dict dari GraphQL), operation
    ...

class WikiJSGraphQLClient:
    def __init__(self, settings, *, http_client=None):
        # base_url=settings.wikijs_url, timeout, verify=verify_ssl,
        # headers Authorization: Bearer <api_key>, Accept/Content-Type json
    async def execute(self, query: str, variables: dict | None = None,
                      *, operation: str | None = None) -> dict:
        # POST /graphql {query, variables}
        # 1) tangani httpx.TimeoutException / RequestError → WikiJSAPIError
        # 2) tangani HTTP >= 400 (401 auth, 403 izin, 404, 500) → pesan ramah per status
        # 3) parse body; jika body["errors"] tidak kosong → WikiJSAPIError(errors=...)
        # 4) return body["data"]
    async def aclose(self): ...
    # async context manager (__aenter__/__aexit__)
```

Catatan penting Wiki.js: **mutation mengembalikan `responseResult { succeeded, errorCode,
slug, message }`**. HTTP 200 + `succeeded=false` **bukan** sukses. Sediakan helper:
```python
def _check_response_result(rr: dict, operation: str) -> None:
    if rr and not rr.get("succeeded", True):
        raise WikiJSAPIError(rr.get("message") or "Operasi Wiki.js gagal",
                             errors=[rr], operation=operation)
```
Panggil helper ini di setiap tool mutation.

**Selesai bila:** `config.py` & `client.py` jadi, `test_config.py` & `test_client.py`
(happy path + `errors` GraphQL + `succeeded=false`) lulus.

---

## 4. Tools per Domain (`tools/`)

**Konvensi** (dari authentik-mcp/CLAUDE.md, sesuaikan prefix):
- Nama tool: `wikijs_<domain>_<aksi>` (mis. `wikijs_page_get`, `wikijs_page_create`).
- Tiap modul: `def register(mcp: FastMCP, client: WikiJSGraphQLClient) -> None`,
  tool didefinisikan dengan `@mcp.tool(tags={"<domain>"})`.
- Akses HTTP **selalu** lewat `client.execute(...)`; jangan panggil httpx langsung.
- Docstring Google style (Args/Returns/Raises), Bahasa Indonesia. Validasi input → `ValueError`.
- Daftarkan modul baru di `tools/__init__.py` (`_MODULES`, menentukan urutan).

### 4.1 `tools/pages.py` — domain `pages`
| Tool | Operasi GraphQL (acuan Wiki.js 2.x) |
|---|---|
| `wikijs_page_list` | `query { pages { list(orderBy: TITLE) { id path title locale contentType updatedAt } } }` |
| `wikijs_page_get` | `query($id:Int!){ pages { single(id:$id){ id path title description content render contentType editor locale isPublished isPrivate tags{tag} authorName creatorName createdAt updatedAt } } }` |
| `wikijs_page_get_by_path` | `query($path:String!,$locale:String!){ pages { singleByPath(path:$path, locale:$locale){ ...sama spt single } } }` (verifikasi ketersediaan field di versi target) |
| `wikijs_page_create` | `mutation($content:String!,$description:String!,$editor:String!,$isPublished:Boolean!,$isPrivate:Boolean!,$locale:String!,$path:String!,$tags:[String]!,$title:String!){ pages { create(...) { responseResult{succeeded errorCode message} page{ id path } } } }` |
| `wikijs_page_update` | `mutation($id:Int!, ...) { pages { update(id:$id, ...) { responseResult{...} page{ id path } } } }` |
| `wikijs_page_delete` | `mutation($id:Int!){ pages { delete(id:$id){ responseResult{succeeded errorCode message} } } }` |
| `wikijs_page_move` | `mutation($id:Int!,$destinationPath:String!,$destinationLocale:String!){ pages { move(...){ responseResult{...} } } }` |
| `wikijs_page_render` | `mutation($id:Int!){ pages { render(id:$id){ responseResult{...} } } }` (render ulang HTML) |
| `wikijs_page_tree` | `query($path:String!,$mode:PageTreeMode!,$locale:String!,$parent:Int){ pages { tree(path:$path, mode:$mode, locale:$locale, parent:$parent){ id path title isFolder pageId locale } } }` |

Default param yang masuk akal: `editor="markdown"`, `locale="en"`, `isPublished=true`,
`isPrivate=false`, `tags=[]`, `description=""`. Untuk `create`/`update`, jelaskan di
docstring bahwa `content` adalah markdown (sesuai `editor`).

### 4.2 `tools/search.py` — domain `search`
| Tool | Operasi |
|---|---|
| `wikijs_page_search` | `query($query:String!,$path:String,$locale:String){ pages { search(query:$query, path:$path, locale:$locale){ results{ id title description path locale } suggestions totalHits } } }` |

### 4.3 `tools/tags.py` — domain `tags`
| Tool | Operasi |
|---|---|
| `wikijs_tag_list` | `query { pages { tags { id tag title createdAt updatedAt } } }` |
| `wikijs_page_list_by_tags` | `query($tags:[String!]!){ pages { byTags? / list filtered }` — **verifikasi**: jika `byTags` tak ada di versi target, implementasikan via `pages.search`/`list` lalu filter, dan dokumentasikan keterbatasan |

### 4.4 `tools/system.py` — domain `system`
| Tool | Operasi |
|---|---|
| `wikijs_system_info` | `query { system { info { currentVersion latestVersion platform dbType operatingSystem nodeVersion } } }` — uji koneksi + diagnosa |

> Tool tulis (create/update/delete/move) bersifat **mutasi**. Pastikan docstring menegaskan
> efek samping. Setelah mutation, panggil `_check_response_result` agar `succeeded=false`
> menjadi error yang jelas, bukan sukses palsu.

**Selesai bila:** semua modul tool jadi & terdaftar di `_MODULES`; tiap tool punya docstring
lengkap; tiap modul punya unit test mock (respx) happy path + minimal satu jalur error.

---

## 5. Server, Auth, Transport (`server.py`, `auth*.py`, `asgi.py`, `__main__.py`, `docs.py`)

Tiru authentik-mcp / scaffold:
- `server.py`: `create_server(settings=None)` → `settings.require_api_config()`,
  `build_token_verifier(settings)`, `FastMCP(name="wikijs-mcp", version=__version__,
  instructions=_INSTRUCTIONS, auth=auth)`, buat `WikiJSGraphQLClient`, `register_all(mcp, client)`,
  `register_docs_routes(mcp, __version__)`. `run()` pilih transport stdio/http.
  `_INSTRUCTIONS`: "Server MCP untuk mengakses Wiki.js melalui GraphQL API. Tool tersedia
  untuk mengelola pages, search, tags, dan system. Semua tool diawali prefix `wikijs_`."
- `auth.py` + `auth_provider.py`: **Pola A** (Wiki.js bukan Authentik IdP) — pintu depan
  `AuthentikProvider` (OAuth untuk Claude Web) + `BearerApiKeyVerifier` (API key untuk
  CLI/VS Code), MultiAuth bila keduanya aktif; tanpa konfigurasi → tanpa auth (stdio lokal).
  Salin dari scaffold; jaga Pitfall #3 (error_code valid).
- `asgi.py`: Starlette wrap + `/health` + `lifespan` (Pitfall #1).
- `__main__.py`: pilih transport via `settings.mcp_transport`.
- `.env.example`: isi `WIKIJS_URL`, `WIKIJS_API_KEY`, `WIKIJS_TIMEOUT`, `WIKIJS_VERIFY_SSL`,
  blok `MCP_*` + `AUTHENTIK_*` + `MCP_API_KEY` (tiru scaffold).

**Selesai bila:** `test_asgi.py` (boot + `/health` + `initialize`) & `test_auth.py` lulus;
`python -m wikijs_mcp` jalan stdio dengan `.env` terisi.

---

## 6. Gate Test — skill `automated-test` (Python non-Odoo)

> Skill `automated-test` adalah **pemilik aturan** gate ini. Fase ini menuliskan hasil
> penerapannya secara konkret agar bisa langsung dieksekusi. **Dua penyesuaian wajib**
> dari asset default skill (jangan disalin mentah):
> 1. Project ini memakai **`pyproject.toml` (tanpa `requirements.txt`)** → `Dockerfile.test`
>    pakai varian pyproject (`pip install .`), lihat `automated-test/references/docker-guide.md`
>    bagian "Project memakai `pyproject.toml`".
> 2. Linter = **ruff + isort + black** (bukan flake8 seperti asset default) — sesuai
>    `mcp-development/references/integrasi-test.md` & konvensi `../authentik-mcp/`.

**Aturan yang tidak boleh dilanggar** (skill `automated-test`):
- Lokal == CI: keduanya menjalankan **`make test`** yang sama persis.
- Gate minimal = **lint + unit**, dijalankan **di dalam Docker**, lewat **Makefile**.
- **Tanpa artefak**: `docker run --rm` **tanpa bind-mount** (source di-COPY ke image).

### 6.1 `Makefile` (root project) — recipe WAJIB indentasi TAB

```make
IMAGE_NAME ?= $(shell basename $(CURDIR))-test
DOCKERFILE ?= Dockerfile.test
DOCKER_RUN  = docker run --rm $(IMAGE_NAME)

.DEFAULT_GOAL := test
.PHONY: build lint unit test clean help

## help: tampilkan daftar target
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed -e 's/## //'

## build: bangun image test (deps + tooling + source)
build:
	docker build -f $(DOCKERFILE) -t $(IMAGE_NAME) .

## lint: ruff + isort + black (check-only) di dalam container
lint: build
	$(DOCKER_RUN) sh -c "ruff check . && isort --check-only --diff . && black --check ."

## unit: jalankan unit test (pytest) di dalam container
unit: build
	$(DOCKER_RUN) pytest

## test: gate lengkap = lint + unit. Dipakai LOKAL dan CI (identik).
test: lint unit

## clean: hapus image test
clean:
	-docker rmi $(IMAGE_NAME)
```

### 6.2 `Dockerfile.test` — **varian pyproject** (bukan varian requirements.txt)

```dockerfile
# Image khusus automated test (lint + unit). Source di-COPY (BUKAN bind-mount):
# artefak (coverage, __pycache__, .pytest_cache) hidup di container & terhapus saat --rm.
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Deps aplikasi (dari pyproject) + tooling test lebih dulu → layer cache.
# README.md ikut karena dirujuk field readme di pyproject saat `pip install .`.
COPY pyproject.toml README.md requirements-test.txt ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && pip install --no-cache-dir -r requirements-test.txt

# Source penuh (pengecualian diatur .dockerignore) → termasuk tests/ & konfigurasi lint.
COPY . .
```

> Jika `README.md` belum dibuat saat fase ini (dibuat di Fase 8), buat placeholder minimal
> dulu agar `pip install .` tidak gagal — atau jalankan Fase 8 (README) sebelum `make build`.

### 6.3 `requirements-test.txt` — tooling test dipin (ruff, bukan flake8)

```
ruff==0.8.6
isort==5.13.2
black==24.10.0
pytest==8.3.4
pytest-asyncio==0.25.2
respx==0.21.1
httpx==0.28.1
```

### 6.4 `.dockerignore` (salin apa adanya dari asset skill `automated-test`)

```
.git
.gitignore
.github
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
.coverage.*
htmlcov/
coverage.xml
dist/
build/
.venv/
venv/
env/
.idea/
.vscode/
.DS_Store
node_modules/
```

### 6.5 `.github/workflows/test.yml` — CI hanya memanggil `make test`

```yaml
name: Automated Test
on:
  push:
    branches: [ master ]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Automated test (lint + unit) di Docker
        run: make test
```

### 6.6 Konfigurasi lint/test di `pyproject.toml` (di-COPY → aturan sama lokal & CI)

Selaras `../authentik-mcp/pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "C4", "SIM"]
ignore = ["E501"]  # line-length ditangani black/formatter

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["B011"]

[tool.isort]
profile = "black"
line_length = 100

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

> Karena ruff rule `I` (isort) **dan** isort terpisah sama-sama aktif, `profile = "black"`
> menjaga keduanya + black tidak saling bertengkar. Pastikan import dikelompokkan
> stdlib / third-party / first-party tanpa baris kosong di dalam grup (Pitfall #4 Fase 2).

### 6.7 Unit test yang harus hijau (cakupan minimal)

Semua HTTP ke Wiki.js **di-mock** (respx) — jangan pernah menghubungi instance nyata.
`tests/` (lihat Fase 2) minimal memuat:
- `test_config.py` — `AUTHENTIK_ALLOWED_USERNAMES` 3 format (OS env + file `.env`).
- `test_asgi.py` — boot ASGI app, `GET /health` 200, request `initialize` di bawah lifespan.
- `test_auth.py` — API key valid/invalid; `TokenError` pakai `error_code` valid OAuth.
- `test_client.py` — `execute` sukses; body `errors` → `WikiJSAPIError`; mutation
  `responseResult.succeeded=false` → `WikiJSAPIError` (helper `_check_response_result`).
- `test_pages.py` / `test_search.py` / `test_tags.py` — tiap tool: happy path + ≥1 jalur error,
  pakai `Client(mcp)` in-memory FastMCP + respx untuk mock `/graphql`.

Pola test in-memory:
```python
import pytest
from fastmcp import Client
from wikijs_mcp.server import create_server

@pytest.mark.asyncio
async def test_page_get(respx_mock):
    respx_mock.post("https://wiki.example.com/graphql").respond(
        json={"data": {"pages": {"single": {"id": 1, "path": "home", "title": "Home"}}}}
    )
    mcp = create_server(test_settings)  # settings dgn WIKIJS_URL/API_KEY dummy
    async with Client(mcp) as client:
        res = await client.call_tool("wikijs_page_get", {"id": 1})
        assert res.data["title"] == "Home"
```

### 6.8 Verifikasi (checklist `automated-test`)
- [ ] `Makefile` root: target `build/lint/unit/test/clean`, `.DEFAULT_GOAL := test`.
- [ ] `Dockerfile.test` varian pyproject, base image dipin (`python:3.11-slim`).
- [ ] `.dockerignore` mengecualikan artefak + `.venv/` + `node_modules/`.
- [ ] `requirements-test.txt` pin **ruff/isort/black/pytest/pytest-asyncio/respx/httpx**.
- [ ] `.github/workflows/test.yml` **hanya** `run: make test`, trigger branch `master`.
- [ ] Konfigurasi ruff/isort/black/pytest ada di `pyproject.toml`.

**Selesai bila (jika Docker ada):** `make test` **hijau** **dan** `git status --porcelain`
**kosong** sesudahnya (tidak ada artefak baru di folder project). Jika Docker tak tersedia,
catat dengan jujur dan minta verifikasi manual — jangan klaim hijau tanpa menjalankannya.

---

## 7. Workflow Rilis — skill `github-release` + `release-docker-image-ghcr`

> Dua skill memiliki aturan rilis ini; fase ini menuliskan hasil penerapannya secara konkret.
> **Prinsip yang tidak boleh dilanggar:**
> - **Reusable workflow ber-versi (M2)** — `release.yml` proyek **tipis** (`uses: ...@v1`/`@v2`),
>   jangan tempel ulang badan workflow build/push.
> - **Dipicu tag `v*`, versi = tag.** Pembuatan tag **bukan** milik fase ini → skill
>   `git-workflow` (Fase 9). Jangan membuat tag di sini.
> - GitHub Release & Docker image = **dua concern terpisah** → **dua job independen** dalam
>   satu `release.yml` (caller komposisi). MCP = **service**, jadi pakai keduanya.
> - Rilis **hanya via GitHub** (Release + image GHCR), **tidak ke PyPI**.

### 7.0 Prasyarat (verifikasi via skill `github-cli`, jangan asumsikan)
`uses:` GitHub harus literal → substitusi `__WORKFLOW_OWNER__` = **`andhit-r`** (sama dengan
owner repo proyek `andhit-r/wikijs-mcp`, jadi aman untuk model private same-owner maupun
public single-canonical). Pastikan **repo workflow infra ini ada & dapat dipanggil**:
- [ ] `andhit-r/github-release` punya `.github/workflows/release.yml` (`on: workflow_call`), tag `@v1`.
- [ ] `andhit-r/release-docker-image-ghcr` punya `.github/workflows/ghcr.yml` (`on: workflow_call`), tag `@v2`.
- [ ] Bila salah satu **privat**: access policy mengizinkan dipanggil repo `andhit-r/*`
      (privat hanya bisa dipanggil owner yang sama — di sini sama, OK). Cek lewat `github-cli`.
- [ ] Jika air-gapped / tak boleh depend repo eksternal: pakai **fallback M1** (template penuh
      self-contained dari `assets/fallback/release.yml` masing-masing skill) dan catat
      trade-off (kehilangan DRY lintas-repo).

### 7.1 `Dockerfile` runtime server (milik builder `mcp-development`)
Non-root, Streamable HTTP via uvicorn, `/health` untuk HEALTHCHECK. **Ganti paket → `wikijs_mcp`.**

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install paket dari source (pyproject sumber kebenaran). README.md ikut karena
# dirujuk field `readme` pyproject (kalau tidak, `pip install .` gagal).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install . \
    && useradd --create-home --uid 1000 appuser

USER appuser

ENV MCP_LOG_LEVEL=INFO
EXPOSE 8000

# Health check pakai endpoint /health dari asgi.py (image slim tanpa curl).
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

CMD ["uvicorn", "wikijs_mcp.asgi:app", "--host", "0.0.0.0", "--port", "8000"]
```

> `/health` disediakan `asgi.py` (Fase 5, Pitfall #1). Tanpa itu container selalu `unhealthy`.
> `.dockerignore` runtime harus mengecualikan `.git`, artefak, venv, dan `tests/`.
> (Catatan: `.dockerignore` di Fase 6.4 sudah mengecualikan `.github`, venv, artefak; pastikan
> `tests/` juga dikecualikan dari image runtime — boleh berbagi file `.dockerignore` yang sama.)

### 7.2 `.github/workflows/release.yml` — **caller komposisi** (Release + image GHCR)
Salin dari `github-release-skill/assets/callers/release.with-docker.yml`, substitusi owner:

```yaml
# release.yml — KOMPOSISI: GitHub Release + Docker image ke GHCR (proyek service).
# Dua job independen. Semver, isi catatan rilis, dan pembuatan tag = skill git-workflow.
name: Release

on:
  push:
    tags: ['v*']

permissions:
  contents: write     # untuk GitHub Release
  packages: write     # untuk push image ke GHCR

jobs:
  github-release:
    uses: andhit-r/github-release/.github/workflows/release.yml@v1
    secrets: inherit

  docker-image:
    uses: andhit-r/release-docker-image-ghcr/.github/workflows/ghcr.yml@v2
    with:
      dockerfile: Dockerfile
    secrets: inherit
```

Catatan preset **fastmcp**: `dockerfile: Dockerfile`, single-arch `linux/amd64` (default).
Untuk multi-arch tambah `platforms: linux/amd64,linux/arm64` di blok `with:` job `docker-image`.
Tidak ada `build_args` (itu khusus Next.js `NEXT_PUBLIC_*`). Tidak ada lampiran `files`
(default auto-generate notes); isi catatan kustom bila perlu via `body_path` (substansi =
`git-workflow`).

### 7.3 Hasil yang diproduksi saat tag `v*` di-push
- **GitHub Release** untuk tag tsb. (auto-generated notes, bukan draft/pre-release).
- **Docker image** di `ghcr.io/andhit-r/wikijs-mcp` dengan tag `{{version}}` (mis. `1.0.0`),
  `{{major}}.{{minor}}` (`1.0`), dan `latest`.

### 7.4 Verifikasi (tanpa membuat tag)
- [ ] `.github/workflows/release.yml` valid YAML; `__WORKFLOW_OWNER__` sudah → `andhit-r`.
- [ ] `permissions: contents: write` **dan** `packages: write` ada; `secrets: inherit` di tiap job.
- [ ] `uses: ...@v1` dan `...@v2` resolvable (repo workflow ada & dapat dipanggil — 7.0).
- [ ] `Dockerfile` runtime ada, `CMD` memakai `wikijs_mcp.asgi:app`, `EXPOSE 8000`, non-root.
- [ ] (Opsional, butuh Docker) uji lokal image runtime:
      `docker build -t wikijs-mcp:dev .` lalu `docker run --rm -p 8000:8000 -e MCP_API_KEY=devkey
      wikijs-mcp:dev` → `curl -s localhost:8000/health` mengembalikan `{"status":"ok"}`.

**Selesai bila:** `release.yml` komposisi + `Dockerfile` runtime terpasang & valid; prasyarat
7.0 terkonfirmasi. **Tag pemicu tidak dibuat di sini** — itu Fase 9 (`git-workflow`), hanya
saat user meminta rilis secara eksplisit.

---

## 8. Dokumentasi & Finalisasi

- [ ] `README.md` — **delegasi skill `readme`**: pintu depan (tool yang diekspos, cara
      daftar ke Claude Desktop/Code/Web, auth Authentik + API key, mode stdio,
      env `WIKIJS_URL`/`WIKIJS_API_KEY`).
- [ ] `CHANGELOG.md` — entri `0.1.0` (Keep a Changelog).
- [ ] `CLAUDE.md` — tiru authentik-mcp, sesuaikan: GraphQL bukan REST, prefix `wikijs_`,
      konvensi tool, aturan test via `make`.
- [ ] Audit kesiapan: `mcp-development-skill/references/checklist-publikasi.md` +
      `automated-test-skill/references/checklist.md`.

---

## 9. Commit / Tag — **delegasi ke skill `git-workflow`**

> ⚠️ **Jangan `git commit` kecuali user memintanya secara eksplisit** (aturan global user).
> Branch utama `master`, commit message Bahasa Indonesia. Tag `vX.Y.Z` (semver) memicu rilis.
> Skill `git-workflow` hanya membuat & push tag pemicu; rilis dijalankan workflow Fase 7.
> Eksekusi `gh` (PR/Actions) lewat skill `github-cli`.

---

## Daftar Tool Final (ringkas)

| Domain | Tool |
|---|---|
| pages | `wikijs_page_list`, `wikijs_page_get`, `wikijs_page_get_by_path`, `wikijs_page_create`, `wikijs_page_update`, `wikijs_page_delete`, `wikijs_page_move`, `wikijs_page_render`, `wikijs_page_tree` |
| search | `wikijs_page_search` |
| tags | `wikijs_tag_list`, `wikijs_page_list_by_tags` |
| system | `wikijs_system_info` |

## Kriteria Selesai Keseluruhan
1. Struktur project lengkap & paket ter-rename `wikijs_mcp`.
2. `WikiJSGraphQLClient` menangani timeout/HTTP error/GraphQL `errors`/`succeeded=false`.
3. Semua tool di tabel ada, ber-docstring, ter-register, ber-unit-test (mock respx).
4. 3 kanal jalan (stdio / Claude Code / Claude Web via Authentik OAuth) + API key.
5. `make test` hijau & tanpa artefak (bila Docker tersedia).
6. Workflow rilis + Dockerfile runtime terpasang via skill.
7. README/CHANGELOG/CLAUDE.md/LICENSE ada.
8. **Tidak commit** sampai user meminta eksplisit.
