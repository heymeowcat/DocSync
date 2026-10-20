# Changelog

## [0.1.0] - 2026-10-20

### Added
- FastAPI web application for scanning projects and generating LLD documents.
- GitHub and GitLab repository integration.
- Prompt library with 60+ analysis prompts.
- Markdown/DOCX/HTML/JSON export.
- Test suite, CI workflow, Dockerfile, and documentation.

### Changed
- Refactored configuration to pydantic-settings.
- Replaced debug prints with structured logging.

### Fixed
- File path resolution for selected files.
- Prompt loading from the correct directory.
- Path traversal in file downloads.
