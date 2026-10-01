# Phase 4 - Repository Layout

## Goal
Standardize the physical layout of the unified APT repository.

## Target
- `dists/stable/`
- `dists/stable/main/`
- `pool/main/<package>/`
- `keys/`
- `scripts/`
- `docs/`
- `registry/`
- `plan/`

## Tasks
- Organize package artifacts by package.
- Preserve valid APT metadata.
- Separate repository tooling from published artifacts.
- Define where public key material lives.
- Define where generated metadata lives.
- Avoid unnecessary duplication of package files.

## Completion Criteria
- Repository layout follows Debian repository conventions.
- Existing working packages remain installable.
