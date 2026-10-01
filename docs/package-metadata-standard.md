# M3tal APT Repository: Package Metadata Standards (Phase 07)

> **Document**: `docs/package-metadata-standard.md`  
> **Phase**: Phase 07 — Package Metadata  
> **Status**: Approved & Implemented  
> **Validation Tool**: [`scripts/validate_package.py`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/scripts/validate_package.py)  
> **Canonical Template**: [`templates/control.template`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/templates/control.template)

---

## 1. Executive Summary

This standard defines the mandatory fields, formatting rules, dependency structures, architecture definitions, and lifecycle script policies for all packages published in the M3tal Debian/APT repository ecosystem.

Adherence ensures:
- 100% compatibility with standard Debian/Ubuntu package managers (`apt`, `apt-get`, `dpkg`, `synaptic`).
- Safe automated dependency resolution across upstream and ecosystem packages.
- Seamless multi-architecture support (`amd64`, `arm64`, and architecture-independent `all`).
- Predictable lifecycle hooks (`postinst`, `postrm`) that prevent broken package installs.

---

## 2. Mandatory & Recommended Control Fields

Every package's `control` file inside `control.tar.*` must adhere to RFC 822 key-value formatting:

| Field | Requirement | Description & Allowed Format | Example |
| :--- | :--- | :--- | :--- |
| **`Package`** | **Mandatory** | Package identifier. Lowercase letters (`a-z`), digits (`0-9`), plus (`+`), hyphen (`-`), and dot (`.`). Must be at least 2 characters long and begin with an alphanumeric character. | `m3tal-core`, `comicinfo-gen` |
| **`Version`** | **Mandatory** | Conforms to Debian Policy §5.6.12 `[epoch:]upstream[-revision]`. Must never start with `v`. | `1.1.62`, `1.2.0~rc.1-1` |
| **`Architecture`** | **Mandatory** | Target machine architecture. Must be one of `amd64`, `arm64`, or `all`. | `amd64`, `all` |
| **`Maintainer`** | **Mandatory** | RFC 822 contact string formatted as `Full Name <email@domain>`. | `Jake Johnson <jake@m3tal.io>` |
| **`Description`** | **Mandatory** | Synopsis line (≤ 80 characters) followed by optional extended description with indented continuation lines (leading whitespace). Empty lines represented by ` .`. | See Section 3.2 |
| **`Section`** | **Mandatory** | Debian package classification. Standard sections: `utils`, `admin`, `net`, `devel`, `misc`, `web`. | `utils` |
| **`Priority`** | **Mandatory** | Package priority. Default: `optional`. (Note: `extra` is deprecated in Debian Policy). | `optional` |
| **`Installed-Size`** | Optional | Total disk space consumed by unpacked package in KiB (1024 bytes). Automatically computed during packaging. | `47987` |
| **`Homepage`** | Recommended | Canonical URL of upstream repository or landing page. Must start with `http://` or `https://`. | `https://m3tal.io` |
| **`Depends`** | Optional | Packages required for proper operation. | `libc6 (>= 2.34), python3` |
| **`Recommends`** | Optional | Strong packages that are not strictly necessary, installed by default by APT. | `xdotool, docker-ce` |
| **`Suggests`** | Optional | Optional companion software. | `ufw` |
| **`Conflicts` / `Breaks`** | Optional | Incompatible packages that cannot co-exist. | `m3tal-legacy` |
| **`Replaces`** | Optional | Files owned by another package now taken over by this package. | `m3tal-legacy` |

---

## 3. Formatting & Syntax Rules

### 3.1 Package Naming Rules
- Lowercase only: `m3tal-core` (VALID), `M3tal-Core` (INVALID).
- Do not begin with hyphen or dot: `-m3tal` (INVALID).
- Use clear component naming for sub-packages:
  - `m3tal` (meta or core orchestrator)
  - `m3tal-api` (daemon / service)
  - `m3tal-cli` (command-line client)
  - `m3tal-common` (shared architecture-independent assets, `all`)

### 3.2 Description Formatting Rules
The `Description` field has two components:
1. **Synopsis**: The first line immediately following `Description: `. It must be concise and ideally less than 80 characters.
2. **Extended Description**: Every subsequent line must begin with a single ASCII space or tab. To represent an empty paragraph break, use a line with a space followed by a single dot: ` .`.

Example:
```text
Description: DEB-first infrastructure orchestration platform.
 M3TAL provides automated container management, Traefik integration,
 and dynamic service mesh routing for home lab environments.
 .
 This package includes the CLI orchestrator and background daemon.
```

### 3.3 Architecture Guidelines

- **`amd64`**: Compiled 64-bit x86 binaries (Go binaries, Rust binaries, C/C++ libraries).
- **`arm64`**: Compiled 64-bit ARM binaries (Raspberry Pi 4/5, Oracle Cloud Ampere, Apple Silicon Linux).
- **`all`**: Architecture-independent packages. Use for:
  - Pure Python scripts without compiled extensions.
  - Shell script suites.
  - Web UI static assets (HTML/CSS/JS).
  - Documentation and man pages.
  - Meta-packages (transitional packages, bundles).

*Crucial APT rule*: Packages with `Architecture: all` are automatically cross-indexed into `binary-amd64`, `binary-arm64`, and all other active repository architectures by `publish_package.py`.

---

## 4. Dependency Syntax & Relation Operators

Debian supports rich dependency constraints using comma-separated conjunctions (`AND`) and pipe-separated disjunctions (`OR`).

### 4.1 Comparison Operators
- `<<` : Strictly less than
- `<=` : Less than or equal to
- `=`  : Exactly equal to
- `>=` : Greater than or equal to (most common)
- `>>` : Strictly greater than

*Note*: Bare `<` and `>` are deprecated in Debian Policy; always use `<<` and `>>`.

### 4.2 Valid Dependency Examples
```text
# Simple package requirement:
Depends: curl, tar

# Version-constrained requirement:
Depends: python3 (>= 3.10), libc6 (>= 2.34)

# Alternative packages (OR):
Depends: docker-ce | docker.io, iptables | nftables

# Architecture-qualified dependency:
Depends: libssl3:amd64 (>= 3.0.0)
```

---

## 5. Maintainer Scripts Standards (`control.tar.*`)

Debian packages may contain lifecycle scripts inside the control archive:
- `preinst`: Executed before package files are unpacked.
- `postinst`: Executed after package files are unpacked (configuration, services, symlinks).
- `prerm`: Executed before package removal.
- `postrm`: Executed after package removal (cleanup, purging).

### 5.1 Standards for M3tal Scripts
1. **Shebang**: Must explicitly specify interpreter (`#!/bin/sh` or `#!/bin/bash`).
2. **Strict Error Handling**: Must include `set -e` so errors stop execution immediately.
3. **Idempotence**: Scripts must be safely repeatable without errors if run multiple times.
4. **Action Handling**: Maintainer scripts receive arguments like `$1 = configure`, `remove`, `upgrade`, `purge`. Scripts must check `$1` before executing action-specific logic.
5. **Systemd Services**: Use `deb-systemd-invoke` or standard `systemctl` checks:
   ```bash
   if [ "$1" = "configure" ]; then
       systemctl daemon-reload || true
       systemctl enable --now m3tal.service || true
   fi
   ```
6. **Executable Bit**: Scripts must have permissions `0755` in the control tarball.

---

## 6. Pre-Publication CI Validation Gate

All pull requests and build artifacts must pass automated validation using `scripts/validate_package.py`:

```bash
# Validate Debian binary package
python3 scripts/validate_package.py validate-deb path/to/package.deb

# Validate debian/control file during build
python3 scripts/validate_package.py validate-control debian/control
```

Exit code `0` indicates success; exit code `1` indicates fatal policy violations that block repository ingestion.
