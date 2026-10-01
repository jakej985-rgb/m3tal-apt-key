# Phase 10 - Package Retention

## Goal
Prevent the unified repository from growing indefinitely while preserving useful package history.

## Status: Completed (2026-10-01)

## Tasks Executed
- [x] Inventory existing package versions:
  - Audited all 124 Debian packages in `pool/main/` (~2.85 GB total storage).
  - Categorized packages across series `v1.0.x` (61 releases) and `v1.1.x` (63 releases).
- [x] Define retention policy:
  - Codified in `config/retention-policy.json`.
  - Full architectural specification documented in `docs/package-retention-policy.md`.
- [x] Keep current releases:
  - Engine automatically classifies active candidate (`1.1.62`) as `RETAIN_CURRENT`.
- [x] Keep a defined number of previous releases:
  - Configurable sliding window per series (`keep_recent_per_series: 5`).
- [x] Preserve explicitly supported versions:
  - Pinned milestones (`1.0.0`, `1.0.60`, `1.1.0`, `1.1.62`) protected indefinitely from deletion.
- [x] Remove obsolete artifacts safely:
  - Tooling `scripts/manage_retention.py` implements safe pruning with safety floor safeguards and mandatory snapshot creation.
  - Safe mode defaults to dry-run (`--dry-run`).
- [x] Regenerate metadata after cleanup:
  - Engine recalculates RFC 822 `Packages`, gzips `Packages.gz`, and updates Release checksums (MD5, SHA1, SHA256, SHA512).
- [x] Document retention rules:
  - Comprehensive guide published to `docs/package-retention-policy.md`.
- [x] Automation & Verification:
  - Automated weekly audit and on-demand pruning workflow in `.github/workflows/package-retention.yml`.
  - Comprehensive test suite in `scripts/test_retention.py` (8 test cases passing).

## Deliverables
- `config/retention-policy.json`: Declarative policy configuration.
- `docs/package-retention-policy.md`: Architectural specification and guide.
- `scripts/manage_retention.py`: CLI inventory, snapshot, and pruning engine.
- `scripts/test_retention.py`: Automated unit and integration test suite.
- `.github/workflows/package-retention.yml`: Scheduled and dispatchable GitHub Actions workflow.

## Completion Criteria Verification
- Old packages can be removed without breaking current APT clients: Verified via sandbox integration tests simulating package removal and metadata regeneration.
- Repository storage remains manageable: Pruning obsolete builds yields an estimated 2,570 MB (90.3%) reduction in active storage.
