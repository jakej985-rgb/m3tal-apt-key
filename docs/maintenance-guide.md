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
│   └── main/                           # Structured binary package pool (.deb archives)
│       └── <package>/                  # One directory per Debian package name
│           └── <package>_<version>_amd64.deb
│               # e.g. m3tal/m3tal_0.24.6_amd64.deb
├── docs/                               # Engineering specifications & manuals
│   ├── user-setup-guide.md             # End-user installation manual
│   ├── maintenance-guide.md            # This operations manual
│   ├── ecosystem-distribution.md       # Authoritative distribution & trust guide
│   ├── central-keyring-architecture.md # Keyring & ingestion architecture
│   ├── app-deb-publishing-guide.md     # Publisher guide for app repositories
│   ├── package-registry.md             # Registry schema & lifecycle spec
│   ├── package-retention-policy.md     # Retention & pruning policy
│   ├── security-and-key-rotation.md    # Cryptographic policies & emergency protocols
│   ├── universal-bootstrap.md          # install.sh technical specification
│   └── plan-repository-integrity-and-publishing.md  # Integrity remediation plan
├── scripts/                            # Validation, ingestion & release automation
│   ├── ingest_deb.py                   # Package ingestion (dispatch handler core)
│   ├── generate_indices.py             # RFC 822 Packages/Release index generator
│   ├── validate_repository.py          # Repository integrity & crypto audit
│   ├── validate_registry.py            # Registry manifest validator
│   ├── manage_retention.py             # Retention inventory/prune engine
│   ├── verify_baseline.py              # Baseline structural validation
│   ├── verify_deployed_repository.py   # Post-deploy public endpoint check
│   └── verify_trust.py                 # Client-side trust verification
├── registry/
│   ├── packages.yml                    # Authoritative package registry manifest
│   └── schema.json                     # Registry JSON Schema
├── templates/
│   └── dispatch-apt.yml                # App-side repository_dispatch template
├── KEY.gpg                             # ASCII-armored OpenPGP public key (backward compat)
├── public.key                          # Canonical ASCII-armored OpenPGP public key
├── install.sh                          # Universal curl-to-bash repository installer
├── index.html                          # Landing page & clipboard bootstrap helper
└── .nojekyll                           # Prevents GitHub Pages from ignoring leading underscores
```

---

## 2. Ingestion & Release Generation Workflow

Package publication is **not** a manual maintainer workflow. The supported pipeline is triggered by app repositories and executed by GitHub Actions:

```text
App repo release tag
   │  .github/workflows/dispatch-apt.yml (templates/dispatch-apt.yml)
   ▼
repository_dispatch event: publish-deb  ──►  .github/workflows/ingest-deb.yml
   │                                            │
   │   payload: { package_id, version,          ▼
   │              deb_url, sha256 }      scripts/ingest_deb.py
   │                                            │  download .deb, verify sha256,
   │                                            │  validate arch/control/deps
   │                                            ▼
   │                                     pool/main/<package>/<package>_<version>_amd64.deb
   │                                            │
   │                                            ▼
   │                                     validate (validate_package.py /
   │                                     validate_registry.py / validate_repository.py)
   │                                            │
   │                                            ▼
   │                                     sign Release → InRelease + Release.gpg
   │                                     (key 775AD1473BF25102)
   │                                            │
   │                                            ▼
   │                                     generate indices → Packages, Packages.gz,
   │                                     Release (scripts/generate_indices.py)
   │                                            │
   │                                            ▼
   │                                     atomic commit to main
   │                                            │
   │                                            ▼
   │                                     gated GitHub Pages deploy
   │                                     (deploy-latest-validated.yml)
   ▼
Live at https://jakej985-rgb.github.io/m3tal-apt-key
```

### Key operational rules

1. **Never hand-edit `dists/` or run `dpkg-scanpackages` in production.** The signing key is only available inside the protected ingest workflow; locally generated unsigned or wrongly-signed metadata will break clients. Local copies of the generation scripts (`generate_indices.py`, `ingest_deb.py`) exist for verification, dry-runs, and testing — not for publishing.
2. **Pool layout is structured**: each package lives in `pool/main/<package-name>/` with filenames `<package>_<version>_amd64.deb` (underscore separator, e.g. `pool/main/m3tal/m3tal_0.24.6_amd64.deb`). Do not place flat `.deb` files at `pool/main/`.
3. **Atomic commits**: the `.deb`, regenerated `Packages`/`Packages.gz`, `Release`, `InRelease`, `Release.gpg`, and any `registry/packages.yml` update must land in a single commit produced by the ingest workflow.

### Release metadata format (reference)

The `Release` file lists checksums (MD5, SHA1, SHA256, SHA512) and file sizes for all index files under `dists/stable/`:

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

### Signing the Release (reference — performed by the ingest workflow)
The ingest workflow signs `dists/stable/Release` with the official M3tal GPG signing key (`775AD1473BF25102`) to produce both signature formats:

1. Detached signature → `dists/stable/Release.gpg`
   ```bash
   gpg --default-key 775AD1473BF25102 --armor --detach-sign --output dists/stable/Release.gpg dists/stable/Release
   ```
2. Inline clearsigned signature → `dists/stable/InRelease`
   ```bash
   gpg --default-key 775AD1473BF25102 --clearsign --output dists/stable/InRelease dists/stable/Release
   ```

---

## 3. Package Retention Policy & Repository Pruning

### Retention Invariants
As audited in Phase 0, storing every historical build inside git creates repository bloat (~5.8 GB footprint across 124 builds).

To maintain long-term scalability without breaking existing users:
1. **Active Stable Version**: The current candidate (e.g. `0.24.6` for `m3tal`) MUST always be preserved.
2. **Previous Versions Window**: Preserve the **5 most recent minor/patch releases** for rollback purposes.
3. **Explicitly Pinned Releases**: Any version flagged in production manifests must be pinned and retained.
4. **Obsolete Package Cleanup**:
   - Move obsolete `.deb` packages out of `pool/main/<package>/` to an external cold storage / archive bucket.
   - Regenerate `Packages`, `Packages.gz`, `Release`, `InRelease`, and `Release.gpg` through the ingest/retention pipeline (never by hand).
   - Run `scripts/validate_registry.py`, `scripts/validate_repository.py`, and `scripts/verify_deployed_repository.py` to ensure no broken references remain.

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
# 1. Registry manifest validation:
python3 scripts/validate_registry.py

# 2. Repository integrity & cryptographic validation:
python3 scripts/validate_repository.py --skip-container-test

# 3. Post-deployment public endpoint verification:
python3 scripts/verify_deployed_repository.py
```

All validation commands must exit with return code `0` before any release is deployed. The canonical publish path (`ingest-deb.yml`) enforces these checks automatically and gates the GitHub Pages deployment on them.
