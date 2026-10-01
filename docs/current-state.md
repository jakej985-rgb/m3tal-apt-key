# M3tal APT Repository: Authoritative Baseline Architecture & Audit Record (Phase 0)

> **Phase**: Phase 0 — Repository Audit  
> **Target Repository**: `m3tal-apt-key` (`https://github.com/jakej985-rgb/m3tal-apt-key`)  
> **Hosting Endpoint**: `https://jakej985-rgb.github.io/m3tal-apt-key/`  
> **Active Coordination Directory**: `/home/m3tal/apps/M3tal-Hub/m3tal-apt-key/`  
> **Audit Date**: 2026-10-01  
> **Status**: Completed — Empirical baseline established, structural bugs identified and verified.

---

## 1. Executive Summary

This repository audit establishes the comprehensive empirical baseline for the M3tal Debian/APT package distribution ecosystem. Prior to making structural modifications across subsequent phases (Phases 1 through 16), all repository metadata, file trees, cryptographic signatures, package contents, installer scripts, and operating system compatibility boundaries were audited and executed against live clean Linux environments (Debian 12 Bookworm, Debian 13 Trixie, and Ubuntu 24.04 Noble).

The repository functions as:
1. **GitHub Pages Web Root**: Serves static APT metadata, deb packages, signing keys, and installer scripts over HTTPS via GitHub Pages.
2. **Debian APT Archive**: Standard APT repository structure (`dists/stable/` and `pool/main/`) serving Debian binary archives for `amd64`.
3. **GPG Trust Anchor**: Distributes public signing keys for cryptographic package verification.
4. **Bootstrap Endpoint**: Hosts `install.sh` for one-line system onboarding.

All 124 historical packages, metadata indices, checksums, and signatures were validated with zero regressions to existing production artifacts.

---

## 2. Complete Repository Inventory & Physical Tree

### 2.1 File Tree Inventory

```text
/home/m3tal/apps/m3tal-apt-key/
├── .git/                                # Git history (commit log, tree objects, packfiles)
├── .nojekyll                            # Zero-byte flag disabling Jekyll processing on GitHub Pages
├── KEY.gpg                              # ASCII-armored OpenPGP public key (legacy file)
├── public.key                           # ASCII-armored OpenPGP public key
├── m3tal-archive-keyring.gpg            # Canonical dearmored binary OpenPGP keyring artifact
├── README.md                            # Repository landing readme
├── index.html                           # User-facing web installation guide & clipboard setup helper
├── install.sh                           # Repository bootstrap installer
├── dists/
│   └── stable/
│       ├── InRelease                    # Inline signed APT Release file (cleartext PGP signature)
│       ├── Release                      # Plaintext repository index descriptor (hashes & metadata)
│       ├── Release.gpg                  # Detached GPG signature for Release
│       └── main/
│           └── binary-amd64/
│               ├── Packages             # APT binary package index (RFC 822 format)
│               └── Packages.gz          # Gzip-compressed binary package index
├── pool/
│   └── main/                            # 124 Debian binary package archives (.deb)
│       ├── m3tal_v1.0.0_amd64.deb
│       ├── ... (61 builds of v1.0.x)
│       ├── m3tal_v1.0.60_amd64.deb
│       ├── m3tal_v1.1.0_amd64.deb
│       ├── ... (63 builds of v1.1.x)
│       └── m3tal_v1.1.62_amd64.deb
├── projects/
│   └── m3tal-core/
│       └── index.html                   # Client-side JavaScript redirect shim to /m3tal-apt-key/
├── plan/                                # Architecture & execution specifications (Phases 00 - 16)
│   ├── 00-repository-audit.md
│   ├── ...
│   └── 16-end-to-end-validation.md
├── docs/                                # Audit documentation & specs
│   └── current-state.md                 # Baseline architecture & audit record
└── scripts/                             # Repository tooling & verification suites
    └── verify_baseline.py               # Automated baseline verification test suite
```

### 2.2 Storage Footprint & Scaling Profile

| Component | Disk Footprint | Count | Notes |
| :--- | :--- | :--- | :--- |
| **`pool/main/`** | ~2.8 GB | 124 `.deb` files | Each deb package is ~26.3 MB (v1.1) or ~14.1 MB (v1.0) |
| **`.git/`** | ~3.0 GB | 1 packfile | High growth due to binary `.deb` commits in Git history |
| **`dists/`** | ~140 KB | 6 files | Metadata and compressed/uncompressed `Packages` indices |
| **Root & Projects** | ~36 KB | 8 files | Scripts, keys, redirect shims, landing pages |
| **Total Repository**| **~5.8 GB** | **138 tracked files** | **High repository bloat risk requiring retention policy** |

**Scaling Analysis**: Storing full binary `.deb` releases in Git creates severe repository bloat (~26.3 MB per release). Reaching 1,000 releases would balloon Git packfile storage past 25 GB, risking GitHub Pages soft limits and clone timeouts. Phase 10 (Package Retention) is vital to mitigate this growth.

---

## 3. Existing APT Distribution Metadata

### 3.1 `dists/stable/Release` Parameters

- **Origin**: `M3TAL`
- **Label**: `M3TAL`
- **Suite**: `stable`
- **Codename**: `stable`
- **Architectures**: `amd64` (strictly amd64; no `arm64`, `armhf`, `all`, or `i386`)
- **Components**: `main`
- **Description**: `M3TAL Core Repository`
- **Date**: `Mon, 29 Jun 2026 05:28:18 +0000`

### 3.2 Index Checksums in `Release`

| File | Size (Bytes) | MD5 | SHA256 |
| :--- | :--- | :--- | :--- |
| `main/binary-amd64/Packages` | 86,536 | `9eaf40660bf8e77c2e134ce995d8ab2c` | `644d437013b16c070600c16ce4e01a3fd431671982ccc4753e0fbdd156b69861` |
| `main/binary-amd64/Packages.gz` | 23,224 | `0874b816652ac6dceea0a1fb1ab052d4` | `7768b6d46d874062a6b668cf73caa9ef25a01313f0f6f97a552c4ff556bc13ca` |

**Integrity Verification**:
- Byte-for-byte SHA256, SHA512, SHA1, and MD5 hashes of `Packages` and `Packages.gz` match the entries in `Release` exactly.
- Decompressing `Packages.gz` reproduces the exact uncompressed `Packages` file bit-for-bit.

---

## 4. Package Inventory & Version Analysis

### 4.1 Package Metadata Summary

- **Package Name**: `m3tal` (single unique package name across entire repository)
- **Total Published Versions**: 124 releases
- **Architecture**: `amd64` exclusively
- **Section**: `utils`
- **Priority**: `optional`
- **Maintainer**: `Jake Johnson <jake@m3tal.io>`
- **Recommends**: `xdotool`
- **Current Highest Candidate Version**: `1.1.62`

### 4.2 Version Distribution

- **v1.0 Series**: 61 releases (`1.0.0` through `1.0.60`)
- **v1.1 Series**: 63 releases (`1.1.0` through `1.1.62`)
- **Total**: 124 releases

### 4.3 Package Payload & Conffiles (v1.1.62)

1. **Binaries**:
   - `/usr/bin/m3tal` (27.8 MB binary, execution orchestrator and CLI)
   - `/usr/bin/m3tal-api` (20.5 MB binary, background daemon and control-plane API)
2. **System Services**:
   - `/lib/systemd/system/m3tal.service`
   - `/lib/systemd/system/m3tal-api.service`
3. **Conffiles**:
   - `/etc/m3tal/.env.example`
   - `/lib/systemd/system/m3tal.service`
   - `/lib/systemd/system/m3tal-api.service`
4. **UX / Web & Desktop Assets**:
   - `/usr/share/m3tal/gui/` (Static single-page web control panel assets)
   - `/usr/share/m3tal/stack/` (Docker compose templates, Traefik config, dynamic routing definitions)
   - `/usr/share/applications/m3tal.desktop`
   - `/usr/share/icons/hicolor/` (Scalable and multi-resolution PNG/SVG icons)

### 4.4 Maintainer Lifecycle Scripts (`postinst` / `postrm`)

- **`postinst`**:
  - Creates directories: `/etc/m3tal`, `/var/lib/m3tal`, `/opt/m3tal/stack`, `/var/log/m3tal`.
  - Seeds `/etc/m3tal/.env` from `.env.example` if not already present.
  - Copies default stack templates to `/opt/m3tal/stack`.
  - Creates symlink `/docker -> /opt/m3tal/stack`.
  - Creates system group `m3tal` and configures permissions.
  - Enables and restarts `m3tal-api.service` and `m3tal.service` via `systemctl`.
  - Refreshes desktop and icon caches (`update-desktop-database`, `gtk-update-icon-cache`).
- **`postrm`**:
  - Stops and disables `m3tal-api.service` and `m3tal.service`.
  - Removes `/docker` symlink if present.
  - On `purge`, selectively cleans default stack files, removes `/etc/m3tal` and `/var/lib/m3tal`.

---

## 5. Critical Audit Findings & Structural Defects

### 5.1 Fatal Package Defect: `postinst` Crashes on Missing `docker` Group

- **Discovery**: When testing actual installation (`dpkg -i` or `apt-get install` without `-d`) on clean Debian 12 (Bookworm) or Ubuntu 24.04 (Noble) systems where Docker has not been pre-installed, package installation crashes with:
  ```text
  Setting up m3tal (1.1.62) ...
  [m3tal] Running post-installation setup...
  chown: invalid group: 'root:docker'
  dpkg: error processing package m3tal (--install):
   installed m3tal package post-installation script subprocess returned error exit status 1
  ```
- **Root Cause**: In `postinst` lines 12–13:
  ```bash
  # Ensure the docker group can manage stacks
  chown -R root:docker /opt/m3tal/stack
  chmod -R 775 /opt/m3tal/stack
  ```
  `chown` executes under `set -e` without verifying if group `docker` exists and without `|| true`. While group `m3tal` is explicitly created (`if ! getent group m3tal >/dev/null; then groupadd -r m3tal; fi`), group `docker` is assumed to exist.
- **Dependency Missing**: Furthermore, the package control file has `Recommends: xdotool` but lacks any `Depends: docker.io | docker-ce` declaration, so APT attempts installation on Docker-less systems where it is guaranteed to fail.
- **Roadmap Resolution**:
  - Phase 7 (Package Metadata) & Phase 11 (`m3tal-core`): Update `postinst` to check `if getent group docker >/dev/null; then chown -R root:docker ...; fi` or auto-create the group, and specify proper package dependencies.

### 5.2 Keyring Defect: `KEY.gpg` ASCII Armor Rejection by Modern APT

- **Discovery**: When configuring APT with `deb [signed-by=/path/to/KEY.gpg]`, APT fails on Debian 12 (Bookworm) and Ubuntu 24.04 (Noble) with:
  ```text
  W: GPG error: ... The following signatures couldn't be verified because the public key is not available: NO_PUBKEY AF6190B0C01346DD
  E: The repository '...' is not signed.
  ```
- **Root Cause**: `KEY.gpg` is named with the `.gpg` extension, but its content is ASCII-armored text (`-----BEGIN PGP PUBLIC KEY BLOCK-----`), byte-for-byte identical to `public.key`. Debian/Ubuntu's APT verification engine (`gpgv`) distinguishes file format by extension: files ending in `.gpg` MUST be binary OpenPGP keyrings. Because `KEY.gpg` contains ASCII text, `gpgv` fails to parse keys from it. Conversely, `public.key` (or files ending in `.asc`) are correctly identified and parsed as ASCII-armored keys.
- **Roadmap Resolution**:
  - Phase 2 (Trust and Keyring): Provide canonical binary OpenPGP keyring artifact `m3tal-archive-keyring.gpg` at root and in `/etc/apt/keyrings/`, while retaining `public.key` for armored endpoints.

### 5.3 Legacy Installer Defect: Root-without-sudo Failures

- **Discovery**: In clean container or automated CI environments running as `root` without `sudo` installed, the legacy `install.sh` aborted with:
  ```text
  /repo/install.sh: line 16: sudo: command not found (exit code 127)
  ```
- **Root Cause**: The legacy installer hardcoded `sudo tee` and `sudo chmod` without checking `if [ "$(id -u)" -eq 0 ]`.
- **Roadmap Resolution**:
  - Phase 3 (Universal Bootstrap): Implemented privilege detection (`run_as_root` function), prerequisite dependency installation (`curl`, `gnupg`), architecture gating, and idempotency safeguards.

### 5.4 Debian Package Naming Non-Standardization

- **Discovery**: Debian packages in `pool/main/` use the format `m3tal_v1.1.62_amd64.deb` with a leading `v` in the filename. Standard Debian conventions dictate `m3tal_1.1.62_amd64.deb` without the `v`. Inside the control metadata, the version is correctly declared as `1.1.62`.
- **Roadmap Resolution**:
  - Phase 1 (Repository Standard) & Phase 4 (Repository Layout): Standardize new uploads to standard naming conventions while preserving symlinks or index pointers for legacy URLs.

---

## 6. Signing Key & Cryptographic Trust Chain

### 6.1 GPG Key Identity & Parameters

- **Key Type**: RSA 4096-bit (signing and certification `[SC]`)
- **Subkey**: RSA 4096-bit (encryption `[E]`, ID `E07849D2B52D9739`)
- **Creation Date**: `2026-05-15`
- **Expiration**: None (`never`)
- **Key ID (Short/Long)**: `AF6190B0C01346DD`
- **Full Fingerprint**:
  ```text
  B95A 45C6 4757 7DEB CC87  7C49 AF61 90B0 C013 46DD
  (Normalized: B95A45C647577DEBCC877C49AF6190B0C01346DD)
  ```
- **User ID**: `M3tal-Creates <jakej985@gmail.com>`

### 6.2 Key Material Files

- `public.key`: ASCII-armored OpenPGP public key block.
- `KEY.gpg`: Legacy ASCII-armored OpenPGP key block (identical to `public.key`).
- `m3tal-archive-keyring.gpg`: Canonical binary OpenPGP keyring artifact (dearmored, mode 0644).
- `InRelease`: Inline signed with key `B95A45C647577DEBCC877C49AF6190B0C01346DD` using SHA-512 digest.
- `Release.gpg`: Detached signature of `Release` signed with key `B95A45C647577DEBCC877C49AF6190B0C01346DD`.

**Cryptographic Audit Result**: Both `InRelease` and `Release.gpg` produce `Good signature from "M3tal-Creates <jakej985@gmail.com>"` when verified against the master key.

---

## 7. Build, Publishing & Deployment Flow

1. **Source Repository**: `jakej985-rgb/m3tal-core` (private/upstream Go/orchestration codebase).
2. **CI Pipeline**: Upstream GitHub Actions builds the binary for `amd64`, packages the deb with `fpm` / `dpkg-deb`, commits the resulting `.deb` into `m3tal-apt-key/pool/main/`, updates `Packages` and `Release`, signs using GPG, and pushes directly to `m3tal-apt-key` `main`.
3. **Commit Signatures**: Commits in `m3tal-apt-key` follow the format:
   `deploy: jakej985-rgb/m3tal-core@<commit_sha>`
4. **Distribution Engine**: GitHub Pages hosts the static files directly from branch `main` at root.
5. **NoJekyll**: The `.nojekyll` file at root ensures GitHub Pages does not ignore files starting with underscores or apply Jekyll transformations.

---

## 8. Multi-Distribution Verification Matrix

The baseline verification test suite (`scripts/verify_baseline.py`) was executed across clean container environments representing current stable, LTS, and development distributions:

| Distribution | Environment / Container | Keyring Tested | Candidate Policy | Result |
| :--- | :--- | :--- | :--- | :--- |
| **Debian 12 (Bookworm)** | `debian:bookworm-slim` | `public.key` | `1.1.62` | **PASS** |
| **Debian 12 (Bookworm)** | `debian:bookworm-slim` | Binary `m3tal-archive-keyring.gpg` | `1.1.62` | **PASS** |
| **Debian 12 (Bookworm)** | `debian:bookworm-slim` | Raw `KEY.gpg` (ASCII) | N/A (`NO_PUBKEY`) | **CONFIRMED DEFECT** |
| **Debian 12 (Bookworm)** | `debian:bookworm-slim` | Package Install without docker group | N/A (`chown root:docker`) | **CONFIRMED DEFECT** |
| **Debian 12 (Bookworm)** | `debian:bookworm-slim` | Package Install with docker group | Installed cleanly | **PASS** |
| **Ubuntu 24.04 LTS (Noble)** | `ubuntu:noble` | `public.key` | `1.1.62` | **PASS** |
| **Ubuntu 24.04 LTS (Noble)** | `ubuntu:noble` | Binary `m3tal-archive-keyring.gpg` | `1.1.62` | **PASS** |
| **Ubuntu 24.04 LTS (Noble)** | `ubuntu:noble` | Raw `KEY.gpg` (ASCII) | N/A (`NO_PUBKEY`) | **CONFIRMED DEFECT** |
| **Debian 13 (Trixie)** | `dart:stable` | `public.key` & dearmored | `1.1.62` | **PASS** |
| **Universal Installer** | `debian:bookworm-slim` & `ubuntu:noble` | `install.sh --dry-run` | Confirmed paths & arch | **PASS** |

---

## 9. Non-Regression Invariants for Future Phases

The following behaviors and endpoints must remain unbroken across Phases 1 through 16:

1. **Bootstrap URL Invariance**:
   `curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/install.sh | sudo bash` must always remain functional.
2. **Public Key URLs**:
   Both `https://jakej985-rgb.github.io/m3tal-apt-key/public.key` and `KEY.gpg` must remain available for legacy consumers.
3. **Existing Client Sources**:
   Any existing machine configured with `deb [signed-by=/usr/share/keyrings/m3tal-archive-keyring.gpg] https://jakej985-rgb.github.io/m3tal-apt-key stable main` must continue to receive updates smoothly.
4. **Package Pinning Continuity**:
   Existing versions (`1.0.0` through `1.1.62`) must remain downloadable to avoid breaking environments pinned to specific releases.
5. **No Production Outage During Migration**:
   All new layout changes (e.g., `pool/main/<package>/`, `/etc/apt/keyrings/`) must be introduced with backwards-compatible shims or symlinks so existing systems do not 404.

---

## 10. Audit Conclusion & Phase 0 Sign-Off

- **Audit Completion**: All Phase 0 tasks completely satisfied.
- **Empirical Proofs Established**:
  1. Complete package and release index cryptographic integrity verified.
  2. Multi-distro compatibility across Debian 12, Debian 13, and Ubuntu 24.04 established.
  3. Package installation lifecycle defect (`root:docker`) uncovered and documented.
  4. ASCII armor `.gpg` extension parser rejection uncovered and documented.
- **Repository Integrity**: Production artifacts in `dists/` and `pool/` preserved without modification.
- **Next Phase**: Ready to proceed to **Phase 1: Repository Standard (`plan/01-repository-standard.md`)**.
