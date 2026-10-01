# Phase 9 - CI Validation

## Goal
Automatically verify repository integrity before and after publication.

## Status: Completed (2026-10-01)

## Checks
- Repository structure (`Release`, `Release.gpg`, `InRelease`, `Packages`, `Packages.gz`, `public.key`, `KEY.gpg`, `.nojekyll`, `install.sh`).
- APT metadata (`Origin`, `Label`, `Suite`, `Codename`, `Architectures`, `Components`, `Description`, `Date`).
- Package indexes (`Packages` and `Packages.gz` consistency and decompression parity).
- Checksums (MD5, SHA1, SHA256, SHA512 across Release descriptor and package archives).
- Release signatures (`Release.gpg` detached signature verification against `public.key`).
- InRelease signature (`InRelease` inline cleartext signature verification against `public.key`).
- Package metadata (RFC 822 format, mandatory fields, disk existence, byte-for-byte size matching).
- Supported architecture (strictly `amd64`; flags unsupported architectures).
- Duplicate versions (prevents duplicate `(Package, Version, Architecture)` collisions).
- Broken dependencies (syntax validation for `Depends`, `Pre-Depends`, `Recommends`, `Suggests`, `Conflicts`, `Breaks`).
- Clean installation (isolated Docker container execution across Debian and Ubuntu distributions).

## Tasks Executed
- [x] Create repository validation engine: `scripts/validate_repository.py`
  - Comprehensive structure, metadata, cryptographic, index, and dependency validation.
  - JSON diagnostic report generation (`--json`) and GitHub Actions annotations (`--github-actions`).
  - Supports `--strict` mode to reject warnings.
- [x] Add GitHub Actions CI workflow: `.github/workflows/ci-validation.yml`
  - Automated jobs for repository validation, Lintian packaging analysis, and multi-distribution matrix tests.
  - Hard gate: Fails publication on any metadata or structural corruption.
- [x] Test against supported Debian/Ubuntu environments:
  - Clean container tests executed against `debian:bookworm-slim` (Debian 12) and `ubuntu:noble` (Ubuntu 24.04).
  - APT source configuration, key de-armoring, candidate resolution, and package download verified.
- [x] Fail publication on validation errors:
  - Enforced in CI pipeline; non-zero exit codes block publication jobs.
- [x] Produce useful CI diagnostics:
  - Formatted terminal tables, GITHUB_STEP_SUMMARY Markdown tables, and structured JSON diagnostics.

## Deliverables
- `scripts/validate_repository.py`: Core CLI validation engine and test runner.
- `.github/workflows/ci-validation.yml`: Automated GitHub Actions validation pipeline.

## Completion Criteria Verification
- Broken repository metadata cannot be published silently: Verified via strict exit-code assertions and automated PR/push CI gates.
