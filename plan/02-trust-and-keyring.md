# Phase 2 - Trust And Keyring

## Goal
Establish one official M3tal repository signing trust chain.

## Tasks
- Identify the current signing key and fingerprint.
- Create the canonical public keyring artifact.
- Standardize installation at `/etc/apt/keyrings/m3tal-archive-keyring.gpg`.
- Keep the private signing key outside the public repository.
- Add fingerprint verification to the bootstrap process.
- Document key ownership and rotation.
- Ensure repository entries use `signed-by=`.
- Document recovery and key rotation procedures.

## Deliverables
- Canonical M3tal keyring.
- Fingerprint documentation.
- Trust and key-rotation documentation.

## Completion Criteria
- Every M3tal APT package source uses the same controlled trust chain.
- Private signing material is never committed.
