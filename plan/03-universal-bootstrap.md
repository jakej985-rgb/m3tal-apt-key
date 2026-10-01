# Phase 3 - Universal Bootstrap

## Goal
Create one safe installer that configures the M3tal APT repository.

## Tasks
- Detect Debian/Ubuntu compatibility.
- Detect CPU architecture.
- Verify required commands.
- Create `/etc/apt/keyrings`.
- Download the public key.
- Verify the expected fingerprint.
- Install the keyring.
- Install the M3tal APT source definition.
- Run `apt update`.
- Provide clear errors and rollback behavior.
- Make the script idempotent.

## Deliverables
- Hardened `install.sh`.
- Bootstrap documentation.

## Completion Criteria
- A clean supported system can configure the repository with one command.
- Re-running the installer does not create duplicate sources or break configuration.
