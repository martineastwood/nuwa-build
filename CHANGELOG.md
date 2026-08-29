# Changelog

All notable changes to nuwa-build are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-08-29

This release lines the published package up with the tested support matrix.
Python 3.9 is no longer supported. Watch mode and Jupyter magics are optional extras.

### Breaking

- Require CPython 3.10 or newer (`requires-python = ">=3.10"`).
- Move `watchdog` and `ipython` out of the default install. Use `pip install "nuwa-build[watch]"` and `pip install "nuwa-build[notebook]"`.

### Added

- Optional extras: `watch` and `notebook`.
- Generated publish workflows smoke-test the installed wheel with `CIBW_TEST_COMMAND`.
- PyPI project URLs (homepage, docs, repository, issues, changelog).
- New projects pin `nimpy@0.2.1` and `nuwa_sdk@0.4.3`.

### Changed

- Wheel packaging and metadata handling for more reliable sdist/wheel contents.
- Stub generation prefers JSON files written via `-d:nuwaStubDir=`, with stdout `NUWA_STUB:` as fallback.
- Nimble dependency validation and safer path handling.
- Windows console encoding and build-artifact cleanup.

### Documentation

- Document the tested matrix: CPython 3.10–3.14 on Linux/macOS/Windows native architectures.
- State that free-threaded CPython, PyPy, musllinux, and Linux aarch64 are not tested yet.

## [0.4.3] - 2026-02-14

Published on PyPI. No matching GitHub release tag was cut at the time.
