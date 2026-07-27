# Changelog

Semua perubahan penting pada proyek ini didokumentasikan di sini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
dan proyek ini mengikuti [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- `wikijs_group_get` dan `wikijs_group_update` (domain `groups`) selalu gagal HTTP 400
  `GRAPHQL_VALIDATION_FAILED` terhadap Wiki.js 2.x sungguhan: `groups.single` menyeleksi
  `userCount` (field itu hanya ada di `GroupMinimal`, bukan `Group`) dan `pageRules` tanpa
  subfield, sementara `groups.update` mengirim kelima argumen sebagai variabel opsional
  padahal skema Wiki.js 2.x mewajibkannya non-null (**REPLACE-ALL**, bukan patch-per-field
  seperti diklaim sebelumnya di `[0.2.0]`). `wikijs_group_update` kini melakukan
  read-modify-write: bila ada argumen opsional yang tidak diisi, tool membaca state group
  saat ini lebih dulu lalu menggabungkannya sebelum mengirim mutation — signature publik
  tool tidak berubah. `page_rules` kini divalidasi lokal (`ValueError` sebelum request HTTP)
  dan otomatis diberi `id` (UUID) bila belum ada. Seluruh dokumen GraphQL `tools/groups.py`
  kini divalidasi otomatis di `make test` terhadap SDL Wiki.js 2.x yang di-commit
  (`tests/schema/wikijs-2.x.graphql`) agar ketidakcocokan skema serupa gagal di test, bukan
  di produksi. Lihat `andhit-r/wikijs-mcp#4`.
- `wikijs_page_list_by_tags` (domain `tags`) selalu gagal `AttributeError` terhadap Wiki.js
  2.x sungguhan: query `pages.list` menyeleksi `tags { tag }` padahal field `tags` pada
  `PageListItem` bertipe `[String]` (daftar string polos, tanpa subfield) — bukan `[PageTag]`
  seperti pada `Page.tags`. Query kini menyeleksi `tags` langsung dan pemfilteran lokal
  memperlakukan tiap entrinya sebagai string. Lihat `andhit-r/wikijs-mcp#5`.

### Changed
- Gate validasi skema GraphQL offline (`andhit-r/wikijs-mcp#4`) diperluas dari domain
  `groups` saja ke **seluruh** modul `src/wikijs_mcp/tools/` (`pages`, `users`, `mail`,
  `tags`, `search`, `system`, `groups`). SDL `tests/schema/wikijs-2.x.graphql` kini juga
  mencakup domain `pages`/`users`/`mail`/`system` (skema resmi Wiki.js 2.5.x, tag
  upstream `v2.5.314`), dan validatornya (`tests/test_tools_schema.py`, menggantikan
  `tests/test_groups_schema.py`) diparametrisasi per modul — daftar modul dibaca dari isi
  direktori `src/wikijs_mcp/tools/`, bukan hardcoded, sehingga modul tool baru otomatis
  ikut tervalidasi. `src/wikijs_mcp/tools/search.py` sedikit direstrukturisasi (nama
  variabel dokumen GraphQL, tanpa mengubah perilaku) agar bisa diekstrak gate ini.
  Modul `users` untuk sementara dikecualikan dari gate positif (`wikijs_user_update`
  mengirim argumen `isActive` yang tidak ada pada skema Wiki.js, dan `wikijs_user_delete`
  menganggap `replace_id` opsional padahal Wiki.js mewajibkannya) — kedua temuan menuntut
  perubahan semantik kontrak tool, dilacak di `andhit-r/wikijs-mcp#7`.

## [0.2.0] - 2026-07-27

### Added
- Tool domain `groups`: `wikijs_group_list`, `wikijs_group_get`, `wikijs_group_create`,
  `wikijs_group_update`, `wikijs_group_delete`, `wikijs_group_assign_user`,
  `wikijs_group_unassign_user` — mengelola group (grup permission) Wiki.js dan
  keanggotaan user di dalamnya. `wikijs_group_update` bersifat patch-per-field (field
  yang tidak diisi tidak dikirim, beda dari `wikijs_mail_update_config`).
- Tool domain `mail`: `wikijs_mail_update_config` (mutation `mail.updateConfig`, semantik
  REPLACE-ALL) dan `wikijs_mail_send_test` (mutation `mail.sendTest`) — mengatur dan
  memverifikasi konfigurasi SMTP instance Wiki.js. Menuntut API key dengan hak
  `manage:system`.
- Tool domain `users`: `wikijs_user_list`, `wikijs_user_get`, `wikijs_user_create`,
  `wikijs_user_update`, `wikijs_user_delete`, `wikijs_user_activate`,
  `wikijs_user_deactivate`, `wikijs_user_enable_tfa`, `wikijs_user_disable_tfa` —
  mengelola akun user Wiki.js (buat, baca, patch-per-field, hapus, aktif/nonaktif, TFA).
  Kredensial (`password_raw`/`new_password`) tidak pernah di-echo di return value.

## [0.1.0] - 2026-06-29

### Added
- MCP server awal untuk Wiki.js via GraphQL API
- Tool domain `pages`: list, get, get_by_path, create, update, delete, move, render, tree
- Tool domain `search`: page_search
- Tool domain `tags`: tag_list, page_list_by_tags
- Tool domain `system`: system_info
- Autentikasi: Authentik OAuth (Claude Web) + API Key statis (CLI/VS Code)
- Transport: stdio dan Streamable HTTP
- Docker image runtime dan Dockerfile.test untuk gate test
- Workflow CI (GitHub Actions) dan rilis (GitHub Release + GHCR)
