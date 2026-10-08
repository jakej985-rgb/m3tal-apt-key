# M3tal Debian Repository Specification (Phase 1)

> **Standard**: M3tal Repository Specification Standard v1.0  
> **Target Repository**: `m3tal-apt-key` (`https://github.com/jakej985-rgb/m3tal-apt-key`)  
> **Hosting Endpoint**: `https://jakej985-rgb.github.io/m3tal-apt-key/`  
> **Phase**: Phase 01 — Repository Standard  
> **Status**: Active / Canonical Specification  

---

## 1. Scope and Objective

This specification establishes the permanent, uniform packaging and distribution standard for the M3tal Debian repository.

The repository serves as the official package source for all core and ecosystem applications produced under the M3tal banner, including:
- `m3tal` (M3tal Core Orchestrator and CLI)
- `m3tal-api` (M3tal System Daemon & Management API)
- Future ecosystem packages (`m3tal-godash`, `m3tal-plugin-page`, `m3tal-hub-cli`, etc.)

All projects targeting distribution via the M3tal Debian repository **must** comply with the structure, metadata rules, versioning standards, signing requirements, and client configuration directives defined in this document.

---

## 2. Repository Infrastructure & Hosting Architecture

### 2.1 Endpoint URIs

| Identifier | URL / Path | Purpose |
| :--- | :--- | :--- |
| **Primary Repository URL** | `https://jakej985-rgb.github.io/m3tal-apt-key/` | Primary HTTPS APT archive root |
| **Bootstrap Installer** | `https://jakej985-rgb.github.io/m3tal-apt-key/install.sh` | One-command system setup script |
| **Canonical Binary Keyring**| `https://jakej985-rgb.github.io/m3tal-apt-key/m3tal-archive-keyring.gpg` | De-armored OpenPGP keyring |
| **Canonical Armored Key** | `https://jakej985-rgb.github.io/m3tal-apt-key/keyrings/m3tal-archive-keyring.asc` | ASCII-armored OpenPGP public key |
| **Legacy Armored Key** | `https://jakej985-rgb.github.io/m3tal-apt-key/public.key` | Backwards-compatible public key |
| **Legacy Key Alias** | `https://jakej985-rgb.github.io/m3tal-apt-key/KEY.gpg` | Backwards-compatible alias |

### 2.2 Distribution Suite & Codename

- **Distribution Suite**: `stable`
- **Distribution Codename**: `stable`
- **Future Suites (Planned)**:
  - `testing`: Pre-release candidates and integration builds.
  - `experimental`: Bleeding-edge staging releases.

Clients configure the `stable` suite. To prevent APT suite-codename mismatch warnings, both `Suite: stable` and `Codename: stable` are specified in repository `Release` metadata.

### 2.3 Repository Components

- **`main`**: Officially supported, free, self-contained packages maintained by M3tal. All binaries and scripts in `main` must depend only on packages present in `main` or the base distribution repositories (Debian/Ubuntu main).
- **Future Components (Reserved)**:
  - `contrib`: Packages requiring third-party non-free external software.
  - `non-free`: Proprietary third-party dependencies or drivers.

### 2.4 Target Architectures

| Architecture | Debian Identifier | Support Status | Notes |
| :--- | :--- | :--- | :--- |
| **x86_64** | `amd64` | **Tier 1 (Active)** | Fully tested, automated release builds |
| **ARM64** | `arm64` | **Tier 2 (Roadmap)** | Raspberry Pi 4/5, Oracle Ampere, AWS Graviton |
| **Architecture-Independent**| `all` | **Tier 2 (Roadmap)** | Data sets, web assets, documentation |

---

## 3. Debian Repository Physical & Logical Layout

The repository conforms strictly to the standard Debian archive layout defined in Debian Policy and Debian Repository Format specification:

```text
m3tal-apt-key/
├── .nojekyll                               # Bypasses Jekyll on GitHub Pages
├── m3tal-archive-keyring.gpg               # Canonical binary keyring for APT
├── public.key                              # ASCII-armored public key (legacy)
├── KEY.gpg                                 # ASCII-armored public key alias (legacy)
├── install.sh                              # Universal bootstrap script
├── keyrings/
│   ├── m3tal-archive-keyring.gpg           # Canonical binary keyring
│   └── m3tal-archive-keyring.asc           # Canonical ASCII-armored keyring
├── dists/
│   └── stable/
│       ├── InRelease                       # Signed inline release index
│       ├── Release                         # Unsigned release index
│       ├── Release.gpg                     # Detached GPG signature for Release
│       └── main/
│           ├── binary-amd64/
│           │   ├── Packages                # RFC 822 package stanza index
│           │   └── Packages.gz             # Gzip-compressed package index
│           └── binary-arm64/               # Planned
│               ├── Packages
│               └── Packages.gz
└── pool/
    └── main/
        ├── m/
        │   └── m3tal/                      # Standard hierarchical pool layout
        │       ├── m3tal_1.1.62_amd64.deb
        │       └── ...
        └── <legacy flat pool files>        # Maintained for backwards compatibility
```

### 3.1 `Release` / `InRelease` Metadata Contract

The `dists/stable/Release` file **must** declare:

```ini
Origin: M3TAL
Label: M3TAL
Suite: stable
Codename: stable
Architectures: amd64
Components: main
Description: M3TAL Core Repository
Date: <RFC 2822 Timestamp>
Valid-Until: <RFC 2822 Timestamp (optional, recommended for production)>
MD5Sum:
 <hash> <size> <relative-path>
SHA1:
 <hash> <size> <relative-path>
SHA256:
 <hash> <size> <relative-path>
SHA512:
 <hash> <size> <relative-path>
```

- Hashes must be generated for `main/binary-amd64/Packages` and `main/binary-amd64/Packages.gz`.
- `InRelease` must be signed with cryptographic cleartext signature using the active M3tal repository key.
- `Release.gpg` must be a valid detached OpenPGP signature of `Release`.

---

## 4. Package Naming Conventions

### 4.1 Canonical Package Filename Standard

Debian packaging standards (Debian Policy Manual §5.6.1) mandate the following filename structure:

$$\mathbf{\langle package\rangle\_\langle version\rangle\text{-}\langle revision\rangle\_\langle architecture\rangle.deb}$$

For M3tal ecosystem packages:
- **Package Name (`<package>`)**: All lowercase alphanumeric characters and hyphens (`[a-z0-9+-]`). Must NOT start with a number. Must NOT contain uppercase letters or underscores.
- **Version (`<version>`)**: Standard SemVer format without leading `v` (e.g. `1.1.62`, NOT `v1.1.62`).
- **Revision (`<revision>`)**: Debian packaging revision number (e.g. `1` or omitted if upstream and packaging are identical).
- **Architecture (`<architecture>`)**: `amd64`, `arm64`, or `all`.

#### Valid Examples:
- `m3tal_1.1.62_amd64.deb`
- `m3tal-api_1.0.4-1_amd64.deb`
- `m3tal-theme_0.2.0_all.deb`

#### Invalid Examples:
- `m3tal_v1.1.62_amd64.deb` *(leading 'v' in version violates Debian filename conventions)*
- `M3tal_1.1.62_amd64.deb` *(capital letters forbidden)*
- `m3tal_1.1.62.deb` *(missing architecture)*

### 4.2 Legacy Compatibility

Historical packages in `pool/main/` were named `m3tal_v1.X.Y_amd64.deb`. To preserve zero-downtime compatibility with existing client caches and static links:
1. Historical files (`m3tal_v*.deb`) remain accessible in `pool/main/`.
2. New packages published starting with Phase 6 **must** adopt canonical naming `m3tal_<version>_<arch>.deb`.
3. Symlinks or duplicate pointers may be provided where needed.

---

## 5. Versioning Rules & Debian Policy Semantics

### 5.1 Semantic Versioning Mapping

M3tal software adheres to [Semantic Versioning 2.0.0](https://semver.org/): `MAJOR.MINOR.PATCH`.

When mapped into Debian versioning (`dpkg --compare-versions`):
- Normal release: `1.2.0` $\rightarrow$ Debian `1.2.0`
- Packaging revision: `1.2.0-1` $\rightarrow$ Debian `1.2.0-1`

### 5.2 Pre-Release Versions: The Tilde (`~`) Rule

In Semantic Versioning, `1.2.0-rc1` is *earlier* than `1.2.0`.  
However, standard Debian version sorting treats `-` as greater than empty. In Debian:
$$\text{"1.2.0-rc1"} > \text{"1.2.0"} \quad \text{(INCORRECT)}$$

In Debian version comparison, the tilde character `~` sorts before everything, including end-of-string:
$$\text{"1.2.0~rc1"} < \text{"1.2.0"} \quad \text{(CORRECT)}$$

**Rule**: All alpha, beta, and release-candidate packages **must** use `~` instead of `-` for pre-release identifiers:
- Correct: `1.2.0~alpha.1`, `1.2.0~beta.2`, `1.2.0~rc1`
- Prohibited: `1.2.0-alpha.1`, `1.2.0-beta.2`

### 5.3 Epoch Policy

An epoch (e.g. `1:1.0.0`) overrides all version comparison. Epochs can never be removed once introduced.  
**Rule**: Epochs are **strictly forbidden** unless an accidental version regression has rendered a package un-upgradable and explicitly approved by architecture review.

---

## 6. Package Metadata & Debian Control Field Requirements

Every Debian package (`.deb`) must contain a control archive (`control.tar.gz` or `control.tar.xz`) satisfying RFC 822 format:

### 6.1 Required Fields

```deb822
Package: m3tal
Version: 1.1.62
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Jake Johnson <jake@m3tal.io>
Installed-Size: 75420
Depends: libc6 (>= 2.31), systemd
Recommends: xdotool
Homepage: https://github.com/jakej985-rgb/m3tal-core
Description: M3tal Core System Management Daemon and CLI
 M3tal is the central automation and orchestration agent for M3tal OS.
 It delivers automated container stack orchestration, unified API control,
 and desktop environment integration.
```

### 6.2 Conffiles Protection

Every package installing files under `/etc/` **must** list them in `debian/conffiles`:
```text
/etc/m3tal/.env.example
/lib/systemd/system/m3tal.service
/lib/systemd/system/m3tal-api.service
```
This guarantees that local user edits to configurations are never silently overwritten during `apt upgrade`.

### 6.3 Systemd Integration Standard

Packages providing system services must:
1. Place unit files in `/lib/systemd/system/` (or `/usr/lib/systemd/system/`).
2. Implement idempotent `postinst` hooks:
   ```bash
   if [ "$1" = "configure" ]; then
       systemctl --system daemon-reload >/dev/null 2>&1 || true
       systemctl enable --now m3tal.service >/dev/null 2>&1 || true
   fi
   ```
3. Implement clean `prerm` / `postrm` hooks:
   - On upgrade/remove: stop service before file removal.
   - On purge: disable service, remove state and log directories.

---

## 7. Dependency Conventions & Binary Packaging

1. **System Libraries**: Packages must express dependencies against standard distribution packages (`libc6`, `systemd`, `ca-certificates`, `curl`) rather than embedding private copies of vulnerable system libraries.
2. **Go & Rust Binaries**: Statically linked or dynamically linked Go/Rust binaries must specify `Depends: libc6 (>= 2.31)` to ensure compatibility with all supported releases.
3. **No Out-of-Archive Vendor Lock**: Packages must not hardcode proprietary external repository dependencies that cannot be satisfied by standard Debian/Ubuntu upstream archives.

---

## 8. Supported Operating Systems & Releases

The M3tal repository targets modern Debian-family distributions with Long Term Support:

| Operating System | Release Codename | Version | glibc Version | Support Tier |
| :--- | :--- | :--- | :--- | :--- |
| **Debian** | `bookworm` | Debian 12 | 2.36 | **Tier 1 (Current Stable)** |
| **Debian** | `trixie` | Debian 13 | 2.40 | **Tier 1 (Testing/Next Stable)** |
| **Debian** | `bullseye` | Debian 11 | 2.31 | **Tier 2 (Oldstable/Maintenance)** |
| **Ubuntu** | `noble` | 24.04 LTS | 2.39 | **Tier 1 (Current LTS)** |
| **Ubuntu** | `jammy` | 22.04 LTS | 2.35 | **Tier 1 (Active LTS)** |
| **Ubuntu** | `focal` | 20.04 LTS | 2.31 | **Tier 2 (Maintenance LTS)** |
| **Linux Mint** | `wilma` / `xia` | 22.x / 21.x | 2.39 / 2.35 | **Tier 1 (Desktop Standard)** |

**Minimum Supported GLIBC Baseline**: `2.31` (ensures binary execution across all listed distributions without symbol lookup errors).

---

## 9. Client Configuration & Standard `signed-by` Directives

Under modern Debian Policy (Debian 12+, Ubuntu 22.04+), placing repository signing keys in `/etc/apt/trusted.gpg` or `/etc/apt/trusted.gpg.d/` is deprecated and insecure because it grants those keys authority over *all* repositories on the machine.

### 9.1 Modern DEB822 Standard Format (Recommended for Debian 12+ / Ubuntu 24.04+)

Target file: `/etc/apt/sources.list.d/m3tal.sources`

```deb822
Types: deb
URIs: https://jakej985-rgb.github.io/m3tal-apt-key
Suites: stable
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/m3tal-archive-keyring.gpg
```

### 9.2 Traditional One-Line Format (Universal Compatibility)

Target file: `/etc/apt/sources.list.d/m3tal.list`

```text
deb [arch=amd64 signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg] https://jakej985-rgb.github.io/m3tal-apt-key stable main
```

### 9.3 Keyring Placement Directives

- **Directory**: `/etc/apt/keyrings/` (mode `0755`)
- **Keyring File**: `/etc/apt/keyrings/m3tal-archive-keyring.gpg` (mode `0644`, owner `root:root`)
- **Format**: Binary OpenPGP Keyring (de-armored)
- **Prohibited Locations**:
  - `/usr/share/keyrings/` (reserved exclusively for base OS distribution packages managed by `dpkg`)
  - `/etc/apt/trusted.gpg` (deprecated global trust)
  - `/etc/apt/trusted.gpg.d/` (deprecated global trust directory)

---

## 10. Multi-Project Onboarding Checklist

When a new M3tal project (e.g. `m3tal-godash`, `m3tal-plugin-page`) prepares to publish Debian packages into this repository, the project maintainer must execute the following checklist:

- [ ] **Package Name**: Validated lower-case hyphenated name (`[a-z0-9+-]`).
- [ ] **Debian Control**: RFC 822 control file contains all required fields (`Package`, `Version`, `Architecture`, `Maintainer`, `Description`, `Section`, `Priority`).
- [ ] **Dependencies**: All runtime dependencies exist in Debian/Ubuntu main or M3tal main.
- [ ] **Filesystem Paths**: Installs only into standard FHS locations (`/usr/bin`, `/usr/share/<package>`, `/etc/<package>`, `/var/lib/<package>`).
- [ ] **Conffiles**: Any user-editable files under `/etc/` are declared in `debian/conffiles`.
- [ ] **System Services**: Any systemd units follow idempotent reload/enable rules.
- [ ] **GLIBC Baseline**: Binaries compiled against GLIBC $\le$ 2.31 for universal compatibility.
- [ ] **Release Signing**: Release metadata signed using the canonical M3tal GPG key (`9DFED0A19DF5351298FE812AED1DAE1980AD1550`).
- [ ] **Automated CI**: Build and publishing integrated into repository automation.
