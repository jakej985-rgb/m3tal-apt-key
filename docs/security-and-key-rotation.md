# M3tal APT Repository: Security Guidelines & Key Rotation Policy

> **Phase**: Phase 15 — Security & Key Rotation  
> **Target Audience**: Security Engineers, Repository Maintainers, Infrastructure Operators  
> **Repository Target**: `m3tal-apt-key`  
> **Last Updated**: 2026-10-01  
> **Classification**: Public Cryptographic & Security Standard  

---

## 1. Security Architecture & Threat Model

The integrity and authenticity of all Debian packages distributed through the M3tal ecosystem are guaranteed through OpenPGP public-key cryptography.

```text
[ Developer / CI Build Engine ]
               │
               ▼ (Protected Secrets)
[ GPG Signing Engine (RSA 4096) ]
               │
      Signs Release File
               │
               ▼
[ InRelease (Inline) & Release.gpg (Detached) ]
               │
               ▼ (HTTPS CDN via GitHub Pages)
[ Client Machine / APT Package Manager ]
               │
      Validates Against
               │
               ▼
[ /etc/apt/keyrings/m3tal-archive-keyring.gpg ]
```

### Threat Vectors & Mitigations
| Threat Vector | Severity | Mitigation Strategy |
| :--- | :--- | :--- |
| **Man-in-the-Middle (MITM) Tampering** | Critical | Repository metadata (`InRelease` / `Release`) is signed with RSA 4096. Packages are validated against SHA256 checksums recorded in the signed `Release` file. |
| **Malicious Package Injection** | Critical | APT refuses installation if package checksum does not match signed `Packages` index. |
| **Repository Metadata Replay Attack** | Medium | `Release` index includes an authoritative `Date` header. APT flags repositories whose Release date is stale or in the future. |
| **Supply-Chain Compromise of CI** | High | Signing keys are isolated in protected GitHub Actions Environment Secrets requiring approval and audit logs. |
| **Private Key Compromise** | Critical | Documented emergency revocation certificate deployment, dual-key migration, and client remediation protocol. |

---

## 2. Official Public Key Specification

### Key Parameters
- **Key Type**: RSA 4096-bit (signing and certification `[SC]`)
- **Subkey**: RSA 4096-bit (encryption `[E]`, Key ID `E07849D2B52D9739`)
- **Creation Date**: `2026-05-15`
- **Expiration Date**: None (`never`) — *recommended for routine rotation in 2028*
- **Key ID (Short/Long)**: `775AD1473BF25102`
- **Primary Fingerprint**:
  ```text
  5F84 FE50 A401 11C9 8141  0E11 775A D147 3BF2 5102
  ```
- **Normalized Fingerprint**: `5F84FE50A40111C981410E11775AD1473BF25102`
- **User ID**: `M3tal-Creates <jakej985@gmail.com>`

### Public Key Distribution Points
1. **Canonical ASCII Key**: `https://jakej985-rgb.github.io/m3tal-apt-key/public.key`
2. **Legacy Compatible Key**: `https://jakej985-rgb.github.io/m3tal-apt-key/KEY.gpg`
3. **Integrity Invariant**: `public.key` and `KEY.gpg` must always remain bit-for-bit identical.

---

## 3. Private Key Protection Standards

### Storage Rules
1. **Never Commit Private Keys**: Under NO circumstances may private keys (`.sec`, `.key`, `secring.gpg`, or ASCII blocks starting with `-----BEGIN PGP PRIVATE KEY BLOCK-----`) be committed to this or any public git repository.
2. **Offline Master Key**: The master certification key should be stored in cold offline storage (e.g. encrypted air-gapped USB storage or HSM hardware key).
3. **CI Signing Subkey**: For automated publishing, a dedicated signing subkey with signing capability only `[S]` must be used, rather than the master certification key `[C]`.

### Protected CI Environment Secrets
Signing keys in CI pipelines must follow these controls:
- Stored as encrypted secrets in GitHub Actions (`GPG_SIGNING_KEY` and `GPG_PASSPHRASE`).
- Scoped to a restricted `production-deployment` environment.
- Requiring repository maintainer approval before deployment workflows execute.
- Workflows must scrub GPG keyrings and temporary directories immediately upon completion.

---

## 4. Scheduled Key Rotation Procedure

To maintain cryptographic resilience, repository signing keys should be rotated on a **24-month lifecycle** with a **6-month dual-trust transition window**.

```text
[ Month 0 - 18: Primary Key A Active ]
                        │
                        ▼ (Month 18: Generate Key B)
[ Month 18 - 24: Dual-Trust Transition Window (Both Key A and B in Keyring) ]
                        │
                        ▼ (Month 24: Key A Retired)
[ Month 24+: Primary Key B Active ]
```

### Rotation Execution Steps

#### Step 1: Generate Replacement Keypair
Generate a new RSA 4096-bit or Ed25519 signing keypair with a 2-year expiration date:
```bash
gpg --quick-generate-key "M3tal-Creates (2028-2030) <jakej985@gmail.com>" rsa4096 sign 2y
```

#### Step 2: Create Dual-Key Transitional Keyring
Combine the existing active public key and the new public key into an amalgamated keyring:
```bash
# Export both keys into one binary keyring
gpg --export 775AD1473BF25102 <NEW_KEY_ID> > m3tal-archive-keyring.gpg

# Export ASCII armored bundle
gpg --armor --export 775AD1473BF25102 <NEW_KEY_ID> > public.key
cp public.key KEY.gpg
```

#### Step 3: Transition Period (Dual-Signing)
During the 6-month grace period:
- Existing clients with the updated keyring will trust releases signed with either key.
- The `Release` metadata can be signed by both keys or transitioned seamlessly to the new key.
- Update `install.sh` to install the amalgamated keyring.

#### Step 4: Retirement of Obsolete Key
At the end of the transition period, generate a formal expiration/retirement record and transition all signing pipelines exclusively to `<NEW_KEY_ID>`.

---

## 5. Emergency Key Revocation & Compromise Response

If the private key is suspected of being compromised or inadvertently exposed:

```text
       [ COMPROMISE DETECTED ]
                  │
                  ▼
  [ 1. Trigger Revocation Certificate ]
                  │
                  ▼
  [ 2. Publish Revocation to Key Endpoints ]
                  │
                  ▼
  [ 3. Generate Emergency Replacement Key ]
                  │
                  ▼
  [ 4. Deploy Emergency Installer & Out-of-Band Advisory ]
                  │
                  ▼
  [ 5. Post-Mortem & Forensic Audit ]
```

### Action Checklist

### Phase A: Immediate Containment (T + 0 to 1 Hour)
1. **Revoke CI Secrets**: Instantly revoke `GPG_SIGNING_KEY` and `GPG_PASSPHRASE` from GitHub Actions Secrets to prevent further signatures.
2. **Generate Revocation Certificate**:
   ```bash
   gpg --output revocation-775AD1473BF25102.crt --gen-revoke 775AD1473BF25102
   ```
3. **Apply Revocation to Public Key**:
   ```bash
   gpg --import revocation-775AD1473BF25102.crt
   gpg --armor --export 775AD1473BF25102 > public.key
   cp public.key KEY.gpg
   ```
4. **Publish Revocation Notice**: Commit and push the revoked public key to the repository immediately.

### Phase B: Emergency Replacement Key (T + 1 to 3 Hours)
1. Generate new emergency signing keypair:
   ```bash
   gpg --quick-generate-key "M3tal Emergency Replacement <jakej985@gmail.com>" rsa4096 sign 1y
   ```
2. Resign current repository metadata (`dists/stable/Release`) with the new key.
3. Update `install.sh` to download and install the new emergency key.

### Phase C: Client Remediation Command
Publish an out-of-band advisory across GitHub, M3tal-Hub, and community channels instructing users to update their keyring:
```bash
curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/install.sh | sudo bash
```

---

## 6. Secret Exposure Audit & CI Integrity Controls

### 6.1 Git History Audit Verification
A comprehensive audit of repository Git history was performed to guarantee that no private key material was ever checked into source control:

```bash
# Verify no PGP private key blocks exist anywhere in git commits:
git log -p -S "BEGIN PGP PRIVATE KEY"
# Returns 0 results across entire commit history.
```

### 6.2 Pre-Publication CI Gates
To prevent unsigned or malformed repository metadata from reaching production, CI pipelines must enforce:
1. `Release` checksum verification against all files in `dists/`.
2. Valid detached GPG signature (`Release.gpg`).
3. Valid inline cleartext signature (`InRelease`).
4. Strict key fingerprint matching (`5F84FE50A40111C981410E11775AD1473BF25102`).

---

## 7. Supply-Chain Risk Review of `install.sh`

Piping scripts from `curl` to `bash` carries supply-chain considerations:
1. **Transport Security**: `install.sh` is served strictly over HTTPS with TLS 1.3 encryption.
2. **De-Armoring Validation**: Piping raw keys to `gpg --dearmor` ensures that only syntactically valid OpenPGP key blocks are written to the system keyring.
3. **Hardened Fingerprint Checking**: The bootstrap script should inspect the fingerprint of the downloaded key prior to copying to `/etc/apt/keyrings/`.
