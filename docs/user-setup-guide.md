# M3tal APT Repository: End-User & Administrator Setup Guide

> **Phase**: Phase 14 — Documentation  
> **Target Audience**: End users, system administrators, DevOps engineers, and CI/CD maintainers  
> **Repository Target**: `m3tal-apt-key`  
> **Official Endpoint**: `https://jakej985-rgb.github.io/m3tal-apt-key`  
> **Last Updated**: 2026-10-01  

---

## 1. Overview & System Requirements

The official M3tal APT repository distributes cryptographically signed Debian packages (`.deb`) for the M3tal orchestration platform and associated tools. Packages are served via static HTTPS CDN and authenticate against an official RSA 4096-bit GPG signing key.

### Supported Operating Systems
| Distribution | Versions Tested | Status | Recommended Keyring Location |
| :--- | :--- | :--- | :--- |
| **Debian** | 11 (Bullseye), 12 (Bookworm), 13 (Trixie) | Tier 1 (Supported) | `/etc/apt/keyrings/m3tal-archive-keyring.gpg` |
| **Ubuntu** | 20.04 LTS (Focal), 22.04 LTS (Jammy), 24.04 LTS (Noble) | Tier 1 (Supported) | `/etc/apt/keyrings/m3tal-archive-keyring.gpg` |
| **Linux Mint** | 20.x (Ulyana), 21.x (Vanessa/Vera), 22.x (Wilma/Zena) | Tier 1 (Supported) | `/etc/apt/keyrings/m3tal-archive-keyring.gpg` |
| **Pop!_OS** | 22.04 LTS | Tier 1 (Supported) | `/etc/apt/keyrings/m3tal-archive-keyring.gpg` |

### Architecture Requirements
- **Architecture**: `amd64` (x86_64) exclusively.
- *Notice for ARM64 (aarch64) users*: If your host is ARM-based (e.g. Raspberry Pi, AWS Graviton, Apple Silicon VMs), standard APT updates will skip or warn about missing architecture metadata. Always specify `[arch=amd64]` in source declarations to avoid unnecessary sync warnings.

---

## 2. Fast Setup (Automated One-Liner)

For workstations and quick installations, run the canonical bootstrap script:

```bash
curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/install.sh | sudo bash
```

### What this script performs:
1. Validates that the system has `curl`, `gpg`, and `apt-get` available.
2. Creates the target keyring directory (`/etc/apt/keyrings` or `/usr/share/keyrings`).
3. Fetches the armored public key from `https://jakej985-rgb.github.io/m3tal-apt-key/public.key`.
4. Converts the ASCII key to a binary OpenPGP keyring via `gpg --dearmor`.
5. Sets secure permissions (`0644`) on the keyring.
6. Writes `/etc/apt/sources.list.d/m3tal.list` configured with the cryptographic `signed-by=` attribute.
7. Executes `apt-get update` to synchronize package lists.

---

## 3. Manual Setup (Debian / Ubuntu Modern Standards)

Production workstations and servers should follow Debian Policy 4.6+ guidelines using dedicated keyrings under `/etc/apt/keyrings/` without polluting global `/etc/apt/trusted.gpg`.

### Step 1: Install System Prerequisites
```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends curl gnupg ca-certificates
```

### Step 2: Create Secure Keyring Storage
```bash
sudo install -m 0755 -d /etc/apt/keyrings
```

### Step 3: Fetch and De-Armor the Public Key
```bash
curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/public.key | sudo gpg --dearmor -o /etc/apt/keyrings/m3tal-archive-keyring.gpg
sudo chmod 0644 /etc/apt/keyrings/m3tal-archive-keyring.gpg
```

### Step 4: Verify Key Fingerprint (Mandatory for High-Security Systems)
Run GPG inspection on the stored keyring:
```bash
gpg --dry-run --show-keys /etc/apt/keyrings/m3tal-archive-keyring.gpg
```

Verify that the output matches the authoritative fingerprint:
```text
pub   rsa4096 2026-05-15 [SC]
      B95A 45C6 4757 7DEB CC87  7C49 AF61 90B0 C013 46DD
uid           M3tal-Creates <jakej985@gmail.com>
sub   rsa4096 2026-05-15 [E]
```

### Step 5: Declare Repository Source
Write the repository specification:
```bash
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg] https://jakej985-rgb.github.io/m3tal-apt-key stable main" | sudo tee /etc/apt/sources.list.d/m3tal.list > /dev/null
```

### Step 6: Synchronize APT Index
```bash
sudo apt-get update
```

---

## 4. Headless & Infrastructure-As-Code Provisioning

### 4.1 Dockerfile Integration
```dockerfile
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
 && install -m 0755 -d /etc/apt/keyrings \
 && curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/public.key | gpg --dearmor -o /etc/apt/keyrings/m3tal-archive-keyring.gpg \
 && chmod 0644 /etc/apt/keyrings/m3tal-archive-keyring.gpg \
 && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg] https://jakej985-rgb.github.io/m3tal-apt-key stable main" > /etc/apt/sources.list.d/m3tal.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends m3tal \
 && rm -rf /var/lib/apt/lists/*
```

### 4.2 Ansible Playbook Task
```yaml
- name: Configure M3tal APT Repository
  hosts: all
  become: true
  tasks:
    - name: Ensure apt-transport-https and gnupg are present
      ansible.builtin.apt:
        name:
          - curl
          - gnupg
          - ca-certificates
        state: present
        update_cache: yes

    - name: Ensure /etc/apt/keyrings exists
      ansible.builtin.file:
        path: /etc/apt/keyrings
        state: directory
        mode: '0755'

    - name: Download M3tal GPG key
      ansible.builtin.get_url:
        url: https://jakej985-rgb.github.io/m3tal-apt-key/public.key
        dest: /tmp/m3tal.key
        mode: '0644'

    - name: De-armor M3tal GPG key into keyring
      ansible.builtin.command:
        cmd: gpg --dearmor --batch --yes -o /etc/apt/keyrings/m3tal-archive-keyring.gpg /tmp/m3tal.key
      args:
        creates: /etc/apt/keyrings/m3tal-archive-keyring.gpg

    - name: Set permissions on M3tal keyring
      ansible.builtin.file:
        path: /etc/apt/keyrings/m3tal-archive-keyring.gpg
        mode: '0644'

    - name: Add M3tal repository entry
      ansible.builtin.apt_repository:
        repo: "deb [arch=amd64 signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg] https://jakej985-rgb.github.io/m3tal-apt-key stable main"
        filename: m3tal
        state: present
        update_cache: yes

    - name: Install m3tal package
      ansible.builtin.apt:
        name: m3tal
        state: latest
```

### 4.3 Cloud-Init (user-data.yaml)
```yaml
#cloud-config
apt:
  sources:
    m3tal:
      source: "deb [arch=amd64 signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg] https://jakej985-rgb.github.io/m3tal-apt-key stable main"
      key: |
        -----BEGIN PGP PUBLIC KEY BLOCK-----
        mQINBGY+cxsBEACyD3D6i... (insert contents of public.key)
        -----END PGP PUBLIC KEY BLOCK-----
packages:
  - m3tal
```

---

## 5. Daily Package Operations

### Installing Packages
```bash
sudo apt-get install -y m3tal
```

### Inspecting Installed and Candidate Versions
```bash
apt-cache policy m3tal
```
Example Output:
```text
m3tal:
  Installed: 1.1.62
  Candidate: 1.1.62
  Version table:
 *** 1.1.62 500
        500 https://jakej985-rgb.github.io/m3tal-apt-key stable/main amd64 Packages
        100 /var/lib/dpkg/status
     1.1.61 500
        500 https://jakej985-rgb.github.io/m3tal-apt-key stable/main amd64 Packages
```

### Upgrading Packages
```bash
sudo apt-get update
sudo apt-get install --only-upgrade -y m3tal
```

### Pinning a Specific Package Version
To install a specific version and prevent automatic upgrades:
```bash
# Install targeted release
sudo apt-get install -y m3tal=1.1.60

# Prevent automatic upgrade
sudo apt-mark hold m3tal

# Check held packages
apt-mark showhold

# Release hold when ready to upgrade
sudo apt-mark unhold m3tal
```

Or via APT Preferences (`/etc/apt/preferences.d/m3tal`):
```text
Package: m3tal
Pin: version 1.1.60*
Pin-Priority: 1001
```

### Inspecting Package Contents Before Execution
```bash
dpkg -L m3tal
```
Main installed assets include:
- `/usr/bin/m3tal`: Core orchestrator CLI
- `/usr/bin/m3tal-api`: Background control daemon
- `/lib/systemd/system/m3tal.service`: Systemd orchestrator unit
- `/lib/systemd/system/m3tal-api.service`: Systemd API unit
- `/etc/m3tal/.env.example`: Configuration baseline

---

## 6. Complete Uninstallation & Repository Removal

If you need to completely remove M3tal and revert your system:

### Step 1: Remove or Purge the Installed Packages
```bash
# Remove binaries and services, keep /etc/m3tal config files:
sudo apt-get remove m3tal

# OR completely purge all binaries, services, logs, and configs:
sudo apt-get purge m3tal
```

### Step 2: Remove Repository Source Definition
```bash
sudo rm -f /etc/apt/sources.list.d/m3tal.list
```

### Step 3: Remove Keyring
```bash
sudo rm -f /etc/apt/keyrings/m3tal-archive-keyring.gpg
# Also clean legacy location if used:
sudo rm -f /usr/share/keyrings/m3tal-archive-keyring.gpg
```

### Step 4: Refresh Package Index
```bash
sudo apt-get update
```

---

## 7. Troubleshooting & FAQ

### Q1: `GPG error: ... NO_PUBKEY AF6190B0C01346DD`
- **Cause**: The signing key has not been imported into the path configured in `signed-by=`, or the path has a typo.
- **Resolution**:
  ```bash
  sudo curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/public.key | sudo gpg --dearmor -o /etc/apt/keyrings/m3tal-archive-keyring.gpg
  sudo chmod 0644 /etc/apt/keyrings/m3tal-archive-keyring.gpg
  ```

### Q2: `Certificate verification failed: The certificate is not yet valid / expired`
- **Cause**: The system clock on the client machine is out of synchronization.
- **Resolution**:
  ```bash
  sudo timedatectl set-ntp on
  date
  ```

### Q3: `W: Target Packages ... is configured multiple times`
- **Cause**: The repository is declared in multiple configuration files (e.g. both `/etc/apt/sources.list` and `/etc/apt/sources.list.d/m3tal.list`).
- **Resolution**:
  ```bash
  grep -rn "m3tal-apt-key" /etc/apt/sources.list /etc/apt/sources.list.d/
  # Remove duplicate definitions, preserving only /etc/apt/sources.list.d/m3tal.list
  ```

### Q4: `E: Unable to locate package m3tal`
- **Cause**: `apt update` has not been run after adding the repository, or the client CPU architecture is not `amd64`.
- **Resolution**: Check system architecture with `dpkg --print-architecture`. If `amd64`, run `sudo apt-get update` and check output for `Hit:... m3tal-apt-key stable InRelease`.
