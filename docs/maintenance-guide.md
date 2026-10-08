# M3tal APT Repository: Repository Maintenance & Operations Guide

> **Phase**: Phase 14 — Documentation  
> **Target Audience**: Repository Maintainers, Release Engineers, Sysadmins  
> **Repository Target**: `m3tal-apt-key`  
> **Hosting Platform**: GitHub Pages (`https://jakej985-rgb.github.io/m3tal-apt-key`)  
> **Last Updated**: 2026-10-01  

---

## 1. Architectural Overview & Physical Structure

The M3tal APT repository operates as a static Debian repository hosted directly on GitHub Pages. It requires zero server-side database infrastructure; APT clients interact with static HTTP resources (`InRelease`, `Release`, `Release.gpg`, `Packages.gz`, and `.deb` pool files).

### Repository Directory Hierarchy

```text
/home/m3tal/apps/m3tal-apt-key/
├── dists/
│   └── stable/
│       ├── InRelease                   # Clearsigned PGP Release file (read by modern APT)
│       ├── Release                     # Plaintext index hashes & metadata descriptor
│       ├── Release.gpg                 # Detached OpenPGP signature for Release
│       └── main/
│           └── binary-amd64/
│               ├── Packages            # Full RFC 822 package metadata block
│               └── Packages.gz         # Gzip-compressed binary index
├── pool/
│   └── main/                           # Binary package pool (.deb archives)
│       ├── m3tal_v1.0.0_amd64.deb
│       ├── ...
│       └── m3tal_v1.1.62_amd64.deb
├── docs/                               # Engineering specifications & manuals
│   ├── current-state.md                # Phase 0 Baseline Audit
│   ├── user-setup-guide.md             # End-user installation manual
│   ├── maintenance-guide.md            # This operations manual
│   ├── developer-guide.md              # Packaging standard for contributors
│   ├── security-and-key-rotation.md   # Cryptographic policies and emergency protocols
│   └── e2e-validation-report.md       # Phase 16 Validation Suite Record
├── scripts/                            # Validation & release automation tools
│   ├── verify_baseline.py              # Repository integrity & crypto audit script
│   └── test_e2e_validation.py         # Full lifecycle end-to-end testing suite
├── projects/                           # Project redirect shims
│   └── m3tal-core/
│       └── index.html                  # Legacy URL redirect shim
├── KEY.gpg                             # ASCII-armored OpenPGP public key (backward compat)
├── public.key                          # Canonical ASCII-armored OpenPGP public key
├── install.sh                          # Universal curl-to-bash repository installer
├── index.html                          # Landing page & clipboard bootstrap helper
└── .nojekyll                           # Prevents GitHub Pages from ignoring leading underscores
```

---

## 2. Ingestion & Release Generation Workflow

Whenever a new package build (e.g. `m3tal_1.1.63_amd64.deb`) is ready to publish, follow this standard release lifecycle:

### Step 1: Place Package into the Pool
Move the freshly built `.deb` into `pool/main/`:
```bash
cp /path/to/build/m3tal_1.1.63_amd64.deb pool/main/
```

### Step 2: Regenerate the Binary Package Index
Run `dpkg-scanpackages` from the repository root to produce the uncompressed `Packages` index:
```bash
dpkg-scanpackages --multiversion pool/main > dists/stable/main/binary-amd64/Packages
```

Compress the index using `gzip -9` while preserving the uncompressed version:
```bash
gzip -9c dists/stable/main/binary-amd64/Packages > dists/stable/main/binary-amd64/Packages.gz
```

### Step 3: Regenerate the `Release` Descriptor
The `Release` file lists checksums (MD5, SHA1, SHA256, SHA512) and file sizes for all index files under `dists/stable/`.

Template for `dists/stable/Release`:
```text
Origin: M3TAL
Label: M3TAL
Suite: stable
Codename: stable
Architectures: amd64
Components: main
Description: M3TAL Core Repository
Date: <CURRENT_RFC2822_UTC_TIMESTAMP>
MD5Sum:
 <MD5> <SIZE> main/binary-amd64/Packages
 <MD5> <SIZE> main/binary-amd64/Packages.gz
SHA1:
 <SHA1> <SIZE> main/binary-amd64/Packages
 <SHA1> <SIZE> main/binary-amd64/Packages.gz
SHA256:
 <SHA256> <SIZE> main/binary-amd64/Packages
 <SHA256> <SIZE> main/binary-amd64/Packages.gz
SHA512:
 <SHA512> <SIZE> main/binary-amd64/Packages
 <SHA512> <SIZE> main/binary-amd64/Packages.gz
```

### Step 4: Cryptographically Sign the Release
Using the official M3tal GPG signing key (`ED1DAE1980AD1550`):

1. Generate detached signature:
   ```bash
   gpg --default-key ED1DAE1980AD1550 --armor --detach-sign --output dists/stable/Release.gpg dists/stable/Release
   ```
2. Generate inline clearsigned signature (`InRelease`):
   ```bash
   gpg --default-key ED1DAE1980AD1550 --clearsign --output dists/stable/InRelease dists/stable/Release
   ```

---

## 3. Package Retention Policy & Repository Pruning

### Retention Invariants
As audited in Phase 0, storing every historical build inside git creates repository bloat (~5.8 GB footprint across 124 builds).

To maintain long-term scalability without breaking existing users:
1. **Active Stable Version**: The current candidate (e.g. `1.1.62`) MUST always be preserved.
2. **Previous Versions Window**: Preserve the **5 most recent minor/patch releases** for rollback purposes.
3. **Explicitly Pinned LTS Releases**: Any version flagged in production manifests (e.g. `1.0.60`) must be pinned and retained.
4. **Obsolete Package Cleanup**:
   - Move obsolete `.deb` packages out of `pool/main/` to an external cold storage / archive bucket.
   - Regenerate `Packages`, `Packages.gz`, `Release`, `InRelease`, and `Release.gpg`.
   - Run `scripts/verify_baseline.py` and `scripts/test_e2e_validation.py` to ensure no broken references remain.

---

## 4. Key Management & Public Key Updates

When updating public key files:
1. Both `public.key` and `KEY.gpg` at the repository root MUST remain byte-for-byte identical:
   ```bash
   cmp public.key KEY.gpg
   ```
2. Any newly generated keyrings must be verified using:
   ```bash
   gpg --show-keys public.key
   ```
3. Never commit private keys (`*.key`, `*.sec`, `secring.gpg`) to this or any public repository.

---

## 5. GitHub Pages Deployment Constraints

1. **`.nojekyll` Flag**:
   - The `.nojekyll` file at the repository root prevents Jekyll from ignoring files beginning with underscores (e.g., `_amd64.deb`).
   - Never delete or rename `.nojekyll`.
2. **Atomic Commits**:
   - Index files (`Packages`, `Packages.gz`, `Release`, `InRelease`, `Release.gpg`) and the corresponding `.deb` files in `pool/` MUST be committed together in a single atomic Git commit.
   - Pushing deb packages before regenerating Release metadata will cause client-side APT 404 or hash mismatch errors during active updates.
3. **Root Domain & HTTPS**:
   - All assets are served over HTTPS. Always use absolute or scheme-relative paths in documentation.

---

## 6. Automated Health Checks & Pre-Deployment Audits

Before merging or pushing any changes to branch `main`, run the repository audit suites:

```bash
# 1. Baseline structural & cryptographic validation:
python3 scripts/verify_baseline.py

# 2. End-to-end containerized client lifecycle test:
python3 scripts/test_e2e_validation.py
```

Both test suites must exit with return code `0` before any release is deployed.
