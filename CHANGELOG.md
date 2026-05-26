# Changelog

## v0.1.0-local-osint - 2026-05-26

Initial local-first Open-Source release candidate.

### Added

- local web UI bound to `127.0.0.1`
- use-case based discovery, source classification, rating and draft generation
- built-in `application_student` and `company_osint` use cases
- configurable local secrets/setup page
- review queue with filters, bulk decisions and undo
- dashboard for runs, provider status and review backlog
- deterministic engine eval baseline with 51 cases
- local privacy check, diagnostics and run-data export/clear flow
- GitHub Actions quality gate without provider secrets
- importable demo use-case examples and local walkthrough

### Known Limitations

- no hosted or multi-user deployment support
- no browser screenshot regression suite in CI yet
- real provider quality depends on local Brave/Ollama/OpenAI configuration
- eval baseline is deterministic and intentionally small
- UI is designed for local review workflows, not public exposure
