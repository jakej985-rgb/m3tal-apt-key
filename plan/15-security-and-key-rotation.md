# Phase 15 - Security And Key Rotation

## Goal
Make the repository maintainable and secure over its lifetime.

## Tasks
- Protect the private signing key.
- Use protected CI secrets for signing.
- Document the current public key fingerprint.
- Define key rotation procedure.
- Define transition period for a replacement key.
- Define emergency key replacement procedure.
- Audit repository workflows for secret exposure.
- Prevent unsigned repository metadata from being published.
- Review bootstrap script for supply-chain risks.

## Completion Criteria
- Signing secrets are never stored in the public repository.
- A compromised or expired key has a documented recovery path.
