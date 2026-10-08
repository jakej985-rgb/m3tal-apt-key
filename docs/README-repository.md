# M3tal Official APT Package Repository

[![Platform: Debian / Ubuntu](https://img.shields.io/badge/platform-Debian%20%7C%20Ubuntu%20%7C%20Mint-blue.svg)](https://jakej985-rgb.github.io/m3tal-apt-key)
[![Architecture: amd64](https://img.shields.io/badge/arch-amd64-green.svg)](https://jakej985-rgb.github.io/m3tal-apt-key)
[![GPG Key: ED1DAE1980AD1550](https://img.shields.io/badge/GPG-ED1DAE1980AD1550-orange.svg)](https://jakej985-rgb.github.io/m3tal-apt-key/public.key)
[![Status: Production Stable](https://img.shields.io/badge/status-production%20stable-brightgreen.svg)](https://jakej985-rgb.github.io/m3tal-apt-key)

The official Debian and Ubuntu APT package repository for the **M3tal** platform and applications. This repository provides signed, cryptographically verified Debian packages (`.deb`) distributed via GitHub Pages and consumed by standard APT package managers (`apt`, `apt-get`, `nala`, `aptitude`).

---

## 📑 Repository Metadata

| Parameter | Specification | Notes |
| :--- | :--- | :--- |
| **Origin / Label** | `M3TAL` | Defined in repository `Release` index |
| **Suite / Codename** | `stable` | Single unified release suite |
| **Component** | `main` | Primary package distribution component |
| **Target Architecture** | `amd64` | 64-bit x86 architecture exclusively |
| **Distribution Endpoint** | `https://jakej985-rgb.github.io/m3tal-apt-key` | Static HTTPS CDN via GitHub Pages |
| **GPG Fingerprint** | `9DFE D0A1 9DF5 3512 98FE 812A ED1D AE19 80AD 1550` | RSA 4096-bit repository signing key |
| **Target Platforms** | Debian 11+, Ubuntu 20.04+, Linux Mint 20+ | Fully compatible with modern `keyrings` standards |

---

## 🚀 Quick Setup (Automatic)

For rapid configuration on any supported Debian or Ubuntu system, run the official automated installer:

```bash
curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/install.sh | sudo bash
```

### What the Automated Script Executes:
1. Verifies prerequisites (`curl`, `gpg`, `apt-get`).
2. Downloads the official OpenPGP public key from `https://jakej985-rgb.github.io/m3tal-apt-key/public.key`.
3. De-armors and installs the binary keyring into `/usr/share/keyrings/m3tal-archive-keyring.gpg` (with `/etc/apt/keyrings/` compatibility).
4. Creates a scoped repository source definition in `/etc/apt/sources.list.d/m3tal.list` with mandatory `signed-by=` attribute.
5. Synchronizes local package indices with `apt-get update`.

---

## 🛡️ Manual Setup (Modern Debian / Ubuntu Standard)

If you prefer to configure the repository manually without piping scripts to a shell:

### Step 1: Install Required Utilities
Ensure `curl`, `ca-certificates`, and `gnupg` are installed:
```bash
sudo apt-get update
sudo apt-get install -y curl ca-certificates gnupg
```

### Step 2: Import the M3tal GPG Signing Key
Create the secure keyrings directory and import the repository public key:
```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/public.key | sudo gpg --dearmor -o /etc/apt/keyrings/m3tal-archive-keyring.gpg
sudo chmod 0644 /etc/apt/keyrings/m3tal-archive-keyring.gpg
```

*(Note: For legacy compatibility with existing scripts, `/usr/share/keyrings/m3tal-archive-keyring.gpg` may also be used).*

### Step 3: Verify the GPG Key Fingerprint
Audit the downloaded keyring fingerprint before configuring APT:
```bash
gpg --dry-run --show-keys /etc/apt/keyrings/m3tal-archive-keyring.gpg
```
Expected output:
```text
pub   rsa4096 2026-05-15 [SC]
      9DFE D0A1 9DF5 3512 98FE  812A ED1D AE19 80AD 1550
uid           M3tal-Creates <jakej985@gmail.com>
sub   rsa4096 2026-05-15 [E]
```

### Step 4: Add the M3tal APT Source
Register the repository in `/etc/apt/sources.list.d/m3tal.list`:
```bash
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg] https://jakej985-rgb.github.io/m3tal-apt-key stable main" | sudo tee /etc/apt/sources.list.d/m3tal.list > /dev/null
```

### Step 5: Update Package Indexes
```bash
sudo apt-get update
```

---

## 📦 Package Management

### Install Packages
To install the flagship M3tal core system package:
```bash
sudo apt-get install -y m3tal
```

### Inspect Package Information & Candidate Versions
To view candidate versions, priority, and installed status:
```bash
apt-cache policy m3tal
```

### Upgrade Packages
Keep your M3tal installations up to date:
```bash
sudo apt-get update
sudo apt-get --only-upgrade install m3tal
```

### Pinning a Specific Historical Version
The repository maintains full historical version continuity (from `1.0.0` to `1.1.62+`). You can install or pin a specific version:
```bash
sudo apt-get install -y m3tal=1.1.62
```

### Removing Packages
To uninstall the application while retaining configuration files in `/etc/m3tal`:
```bash
sudo apt-get remove m3tal
```

To completely purge all binaries, services, and configuration directories:
```bash
sudo apt-get purge m3tal
```

---

## 📂 Repository Layout

```text
m3tal-apt-key/
├── dists/
│   └── stable/
│       ├── InRelease               # Inline cryptographically signed repository index
│       ├── Release                 # Repository index metadata (hashes, architectures, dates)
│       ├── Release.gpg             # Detached GPG signature for Release
│       └── main/
│           └── binary-amd64/
│               ├── Packages        # RFC 822 package descriptors for amd64 binaries
│               └── Packages.gz     # Gzip-compressed package index
├── pool/
│   └── main/                       # Debian binary package archives (.deb)
│       ├── m3tal_v1.0.0_amd64.deb
│       ├── ...
│       └── m3tal_v1.1.62_amd64.deb
├── docs/                           # Official Architecture & Operational Manuals
│   ├── current-state.md            # Phase 0 Baseline Audit Record
│   ├── user-setup-guide.md         # Comprehensive User & Admin Setup Guide
│   ├── maintenance-guide.md        # Repository Maintenance & Publishing Manual
│   ├── developer-guide.md          # Packaging & Development Guide
│   ├── security-and-key-rotation.md# Security Model, Audit, & Rotation Policies
│   └── e2e-validation-report.md    # Phase 16 E2E Test Suite Validation Report
├── scripts/                        # Repository Validation & Automation Suites
│   ├── verify_baseline.py          # Phase 0 Structural & Cryptographic Baseline Audit
│   └── test_e2e_validation.py      # Phase 16 Full End-to-End Lifecycle Test Suite
├── install.sh                      # Unified automated repository bootstrap script
├── public.key                      # ASCII-armored OpenPGP public key
├── KEY.gpg                         # Backward-compatible ASCII OpenPGP key duplicate
├── index.html                      # Landing page with interactive clipboard installer
└── .nojekyll                       # GitHub Pages Jekyll processing bypass flag
```

---

## 📚 Documentation Index

Detailed engineering and operational manuals are available in the [`docs/`](docs/) directory:

- [📖 User Setup & Administration Guide](docs/user-setup-guide.md): Comprehensive instructions for workstations, headless servers, Docker containers, Ansible playbooks, and air-gapped mirrors.
- [🛡️ Security & Key Rotation Policy](docs/security-and-key-rotation.md): Threat modeling, cryptographic parameters, cold storage practices, routine key rotation schedules, and emergency revocation procedures.
- [🛠️ Repository Maintenance Guide](docs/maintenance-guide.md): Package indexing, Release generation, metadata signing, pool maintenance, retention policy enforcement, and GitHub Pages deployments.
- [💻 Developer Packaging Guide](docs/developer-guide.md): Debian packaging guidelines, systemd unit integration, conffiles, maintainer scripts (`postinst`/`postrm`), and CI/CD automation.
- [🧪 End-to-End Validation Report](docs/e2e-validation-report.md): Execution logs and verification metrics across Debian and Ubuntu test environments.

---

## 🔧 Troubleshooting

### 1. `GPG error: ... The following signatures couldn't be verified because the public key is not available: NO_PUBKEY ED1DAE1980AD1550`
**Cause**: The public key was not imported into the keyring referenced by `signed-by=`, or the path in `/etc/apt/sources.list.d/m3tal.list` does not match the file on disk.  
**Fix**:
```bash
sudo curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/public.key | sudo gpg --dearmor -o /etc/apt/keyrings/m3tal-archive-keyring.gpg
sudo chmod 0644 /etc/apt/keyrings/m3tal-archive-keyring.gpg
sudo apt-get update
```

### 2. `N: Skipping acquire of configured file 'main/binary-arm64/Packages' as repository doesn't support architecture 'arm64'`
**Cause**: The client machine is running an ARM64 (aarch64) CPU (e.g. Raspberry Pi, Apple Silicon VM). The M3tal repository currently compiles packages exclusively for `amd64`.  
**Fix**: Ensure `[arch=amd64]` is specified in `/etc/apt/sources.list.d/m3tal.list` so APT does not query unsupported architectures, or build from source on ARM64 systems.

### 3. `W: Target Packages ... is configured multiple times`
**Cause**: Multiple `.list` files in `/etc/apt/sources.list.d/` declare the M3tal repository, or an entry exists in `/etc/apt/sources.list`.  
**Fix**:
```bash
# Check existing declarations:
grep -rn "jakej985-rgb.github.io/m3tal-apt-key" /etc/apt/sources.list /etc/apt/sources.list.d/
# Remove duplicates and preserve only /etc/apt/sources.list.d/m3tal.list
```

### 4. `curl: command not found` or `gpg: command not found` during bootstrap
**Cause**: Minimal Debian or Docker containers lack basic network and crypto tooling.  
**Fix**:
```bash
sudo apt-get update && sudo apt-get install -y curl gnupg ca-certificates
```

---

## 🤝 Maintenance & Support

- **Repository Maintainer**: Jake Johnson (`<jake@m3tal.io>`)
- **Key Signing Entity**: `M3tal-Creates <jakej985@gmail.com>`
- **Source Code & Issue Tracking**: [GitHub: jakej985-rgb/m3tal-apt-key](https://github.com/jakej985-rgb/m3tal-apt-key)
- **Ecosystem Hub**: [M3tal-Hub](https://github.com/jakej985-rgb/M3tal-Hub)
