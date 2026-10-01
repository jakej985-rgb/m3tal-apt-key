# Phase 6 - Package Publishing

## Goal
Automate publication of packages from individual M3tal projects into the unified repository.

## Tasks
- Define the package publication workflow.
- Build Debian packages in CI.
- Validate package metadata.
- Publish approved artifacts.
- Place artifacts in the correct pool path.
- Regenerate APT indexes.
- Regenerate Release metadata.
- Sign repository metadata.
- Publish changes atomically.
- Prevent duplicate or invalid package versions.

## Completion Criteria
- A project can publish a valid package without manual file copying.
- A published package becomes available through APT after repository synchronization.
