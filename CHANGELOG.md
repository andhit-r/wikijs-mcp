# Changelog

Semua perubahan penting pada proyek ini didokumentasikan di sini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
dan proyek ini mengikuti [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
