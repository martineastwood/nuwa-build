# Changelog

All notable changes to nuwa-build will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Multi-file Nim project support
- Enhanced error messages with code context and suggestions
- Comprehensive test suite (69 tests)
- GitHub Actions CI/CD workflows
- Type hints throughout the codebase
- Watch mode for auto-recompilation on file changes
- PyPI trusted publishing setup

### Changed
- Fixed wheel tag generation for proper platform compatibility
- Changed from src/ to flat project layout
- Updated project templates with explicit imports (no star imports)

### Fixed
- Fixed `__init__.py` template to use explicit imports instead of star imports
- Fixed wheel building to include Python package files
- Fixed regex pattern to handle spaces in Nim error messages
- Fixed various type checking errors

## [0.1.0] - 2025-01-XX

### Added
- Initial release
- PEP 517/660 build backend support
- `nuwa new` command for project scaffolding
- `nuwa develop` command for in-place compilation
- `nuwa watch` command for auto-recompilation
- Configuration via `pyproject.toml`
- Entry point auto-discovery
- Multi-file Nim project support with `include`
- Nimble dependency auto-installation
- Platform-specific extension handling (.so/.pyd)
- Enhanced error parsing and formatting
- Wheel and source distribution building
- Editable install support

[Unreleased]: https://github.com/martineastwood/nuwa-build/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/martineastwood/nuwa-build/releases/tag/v0.1.0
