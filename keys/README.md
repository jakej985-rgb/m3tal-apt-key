# M3tal APT Repository Trust & Key Material

This directory contains the public cryptographic signing key material for the official M3tal Debian/APT repository.

## Canonical Key Information

- **Key ID / Fingerprint**: `B95A45C647577DEBCC877C49AF6190B0C01346DD`
- **Key Algorithm**: RSA 4096-bit (`[SC]` signing and cert, `[E]` encrypt subkey)
- **User ID**: `M3tal-Creates <jakej985@gmail.com>`
- **Creation Date**: 2026-05-15

## Formats Available

1. **`m3tal-archive-keyring.gpg`**:
   - Format: Binary OpenPGP Keyring format.
   - Standard Installation Target: `/etc/apt/keyrings/m3tal-archive-keyring.gpg`
   - Permissions: `0644` (readable by `_apt` and all system users).

2. **`m3tal-archive-keyring.asc`**:
   - Format: ASCII-armored OpenPGP Public Key Block.
   - For manual inspection, key distribution, or systems requiring ASCII armored keys (`gpg --dearmor`).
   - Identical to root `public.key` and `KEY.gpg` (retained for backward compatibility).

## Security Policy

- **Private Key Isolation**: Private signing keys are NEVER committed to this repository or hosted publicly. Signing operations are strictly decoupled from public repository storage.
- **Dedicated Keyring**: The repository configuration mandates `signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg` in `/etc/apt/sources.list.d/m3tal.list` to prevent cross-repository signature spoofing or trust contamination.
