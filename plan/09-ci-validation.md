# Phase 9 - CI Validation

## Goal
Automatically verify repository integrity before and after publication.

## Checks
- Repository structure.
- APT metadata.
- Package indexes.
- Checksums.
- Release signatures.
- InRelease signature.
- Package metadata.
- Supported architecture.
- Duplicate versions.
- Broken dependencies.
- Clean installation.

## Tasks
- Create repository validation scripts.
- Add GitHub Actions.
- Test against supported Debian/Ubuntu environments.
- Fail publication on validation errors.
- Produce useful CI diagnostics.

## Completion Criteria
- Broken repository metadata cannot be published silently.
