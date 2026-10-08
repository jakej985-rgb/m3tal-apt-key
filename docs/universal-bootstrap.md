# M3tal Universal APT Repository Bootstrap Guide

> **Phase**: Phase 03 — Universal Bootstrap  
> **Target Repository**: `m3tal-apt-key` (`https://github.com/jakej985-rgb/m3tal-apt-key`)  
> **Hosting Endpoint**: `https://jakej985-rgb.github.io/m3tal-apt-key/`  
> **Target Architecture**: `amd64` (`x86_64`)  
> **Keyring Location**: `/etc/apt/keyrings/m3tal-archive-keyring.gpg`  
> **Source Definition**: `/etc/apt/sources.list.d/m3tal.list`  
> **Official Key Fingerprint**: `9DFED0A19DF5351298FE812AED1DAE1980AD1550`

---

## 1. Quickstart

To securely configure the official M3tal Debian repository and install public signing keyrings in one command:

```bash
curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/install.sh | sudo bash
```

Once completed, install the `m3tal` agent and ecosystem applications using standard `apt`:

```bash
sudo apt update
sudo apt install m3tal
```

---

## 2. What `install.sh` Does

The bootstrap installer script (`install.sh`) implements a hardened, idempotent workflow following modern Debian and Ubuntu repository security standards:

```text
[Client System]
       │
       ▼
 1. Compatibility Check ──► Validates Debian/Ubuntu derivative (/etc/os-release)
       │
       ▼
 2. Architecture Check  ──► Validates CPU architecture (amd64 / x86_64)
       │
       ▼
 3. Prerequisites Check ──► Verifies curl/wget, gpg, apt-get (auto-resolves if missing)
       │
       ▼
 4. Secure Key Fetch    ──► Retrieves ASCII armored public key to private temporary directory
       │
       ▼
 5. Cryptographic Check ──► Verifies key fingerprint against 9DFED0A19DF5351298FE812AED1DAE1980AD1550
       │                    (Aborts immediately on any mismatch)
       ▼
 6. Dearmor & Keyring   ──► Dearmors OpenPGP key and installs to /etc/apt/keyrings/m3tal-archive-keyring.gpg
       │                    (Permissions 0644, atomic temp-file replace)
       ▼
 7. Source Configuration──► Writes /etc/apt/sources.list.d/m3tal.list with [signed-by=...] isolation
       │
       ▼
 8. Repository Sync     ──► Runs targeted 'apt-get update' for m3tal source
```

---

## 3. Command-Line Options

`install.sh` supports standard flags for automated environments, dry-runs, and customization:

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| **Dry Run** | `-d`, `--dry-run` | Simulates actions without altering system state | `false` |
| **Skip Update** | `-n`, `--no-update` | Installs keys and sources but skips `apt update` | `false` |
| **Force Arch** | `-f`, `--force-arch` | Bypasses architecture warning on non-amd64 systems | `false` |
| **Uninstall** | `-u`, `--uninstall` | Removes repository list and keyring | `false` |
| **Repo URL** | `--repo-url <URL>` | Overrides base repository URL | `https://jakej985-rgb.github.io/m3tal-apt-key` |
| **Key URL** | `--key-url <URL>` | Overrides public key download URL | `${REPO_URL}/public.key` |
| **Keyring** | `--keyring <PATH>` | Custom keyring file path | `/etc/apt/keyrings/m3tal-archive-keyring.gpg` |
| **Source List** | `--sources-list <PATH>` | Custom sources list file path | `/etc/apt/sources.list.d/m3tal.list` |
| **Help** | `-h`, `--help` | Displays command reference | — |

### Examples

```bash
# Dry-run inspection
./install.sh --dry-run

# Offline / Local file bootstrap
./install.sh --key-url /path/to/public.key --repo-url file:///path/to/repo

# Complete repository removal
sudo ./install.sh --uninstall
```

---

## 4. Cryptographic Trust Architecture

### 4.1 Canonical Signing Fingerprint

```text
pub   rsa4096 2026-05-15 [SC]
      9DFED0A19DF5351298FE812AED1DAE1980AD1550
uid   M3tal-Creates <jakej985@gmail.com>
sub   rsa4096 2026-05-15 [E]
```

### 4.2 Security Guarantees

1. **Fingerprint Verification Prior to Trust**: The script parses and validates the primary GPG key fingerprint before placing any file in `/etc/apt/keyrings`. Forged or corrupted keys are halted with a security alert.
2. **`signed-by` Isolation**: In accordance with Debian Security Advisory recommendations, keys are NEVER placed in `/etc/apt/trusted.gpg` or `/etc/apt/trusted.gpg.d/`. Dedicated keyrings prevent a compromised third-party repository from signing packages for other repositories.
3. **Atomic Operations**: Files are written to temporary staging files with restricted permissions (`0600`) and atomically moved to `/etc/apt/keyrings/` and `/etc/apt/sources.list.d/` with `0644` permissions.
4. **Automatic Trap Cleanup**: Temporary directories created under `/tmp/m3tal_bootstrap_*` are securely deleted upon exit, interruption, or termination.

---

## 5. Manual Setup Guide (Air-gapped / Manual Inspection)

For operators who prefer manual system configuration:

### Step 1: Install prerequisite tools
```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends ca-certificates curl gnupg
```

### Step 2: Download and verify public key
```bash
# Create keyrings directory
sudo install -d -m 0755 /etc/apt/keyrings

# Download public key
curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/public.key -o /tmp/m3tal.key

# Verify fingerprint
gpg --show-keys /tmp/m3tal.key | grep -q "9DFED0A19DF5351298FE812AED1DAE1980AD1550" || {
    echo "ERROR: Untrusted key fingerprint!" >&2
    exit 1
}

# Dearmor and install to keyring directory
gpg --dearmor < /tmp/m3tal.key | sudo tee /etc/apt/keyrings/m3tal-archive-keyring.gpg > /dev/null
sudo chmod 0644 /etc/apt/keyrings/m3tal-archive-keyring.gpg
rm -f /tmp/m3tal.key
```

### Step 3: Configure repository source list
```bash
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg] https://jakej985-rgb.github.io/m3tal-apt-key stable main" | sudo tee /etc/apt/sources.list.d/m3tal.list > /dev/null
sudo chmod 0644 /etc/apt/sources.list.d/m3tal.list
```

### Step 4: Refresh indices and install
```bash
sudo apt-get update
sudo apt-get install -y m3tal
```

---

## 6. Verification and Troubleshooting

### Verifying Candidate Release
```bash
apt-cache policy m3tal
```
Expected output:
```text
m3tal:
  Installed: (none)
  Candidate: 1.1.62
  Version table:
     1.1.62 500
        500 https://jakej985-rgb.github.io/m3tal-apt-key stable/main amd64 Packages
```

### Common Issues
- **`GPG error: ... NO_PUBKEY`**: The keyring file `/etc/apt/keyrings/m3tal-archive-keyring.gpg` was not found or lacks read permissions (`chmod 0644 /etc/apt/keyrings/m3tal-archive-keyring.gpg`).
- **`Architecture 'arm64' is not supported`**: The core package `m3tal` is built for `amd64`. Run on `x86_64`/`amd64` or wait for multi-architecture builds.
