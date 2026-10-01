# Phase 0 - Repository Audit

## Goal
Document the current M3tal APT repository before making structural or behavioral changes.

## Tasks
- Inventory the current repository tree.
- Document the existing APT distribution metadata.
- Document existing packages and versions.
- Inspect the current signing key and fingerprint.
- Document how packages are currently built and published.
- Document the current `install.sh` behavior.
- Verify the current repository works from a clean Debian/Ubuntu system.
- Record current behavior that must not regress.

## Deliverables
- `docs/current-state.md`
- Baseline repository validation results.

## Completion Criteria
- Current repository behavior is documented.
- Current signing and package flow is understood.
- No production behavior is changed during this phase.
