# Changelog

Semua perubahan penting pada proyek ini didokumentasikan di sini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
dan proyek ini mengikuti [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Tool domain `mail`: `wikijs_mail_update_config` (mutation `mail.updateConfig`, semantik
  REPLACE-ALL) dan `wikijs_mail_send_test` (mutation `mail.sendTest`) — mengatur dan
  memverifikasi konfigurasi SMTP instance Wiki.js. Menuntut API key dengan hak
  `manage:system`.

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
