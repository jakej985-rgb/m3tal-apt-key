# M3tal Trust and Keyring Specification (Phase 2)

> **Standard**: M3tal Cryptographic Trust and Keyring Specification  
> **Target Repository**: `m3tal-apt-key` (`https://github.com/jakej985-rgb/m3tal-apt-key`)  
> **Phase**: Phase 02 — Trust and Keyring  
> **Status**: Active / Canonical Specification  

---

## 1. Security Architecture & Trust Model

The M3tal APT repository uses an asymmetric OpenPGP cryptographic trust chain to guarantee package integrity and provenance. 

Every client running Debian, Ubuntu, or derivative distributions verifies repository authenticity before installing or upgrading any package. This prevents:
- Man-in-the-Middle (MitM) package injection or tampering.
- Malicious repository spoofing or domain hijacking.
- Cross-repository package signature abuse (via dedicated `signed-by` scoping).

---

## 2. Official Signing Key Cryptographic Identity

The repository is certified and signed with the official M3tal master repository signing key.

### 2.1 Cryptographic Parameters

| Parameter | Specification Value |
| :--- | :--- |
| **User ID (UID)** | `M3tal-Creates <jakej985@gmail.com>` |
| **Primary Key ID** | `775AD1473BF25102` |
| **Full Primary Fingerprint** | `5F84 FE50 A401 11C9 8141  0E11 775A D147 3BF2 5102` |
| **Normalized Fingerprint** | `5F84FE50A40111C981410E11775AD1473BF25102` |
| **Key Type & Size** | RSA 4096-bit |
| **Usage Capabilities** | `[SC]` (Sign, Certify) |
| **Creation Date** | `2026-05-15` |
| **Expiration Date** | `never` |
| **Encryption Subkey ID** | `CF2E20713078A579` |
| **Subkey Capabilities** | `[E]` (Encrypt) |
| **Signature Digest** | SHA-512 |

### 2.2 Fingerprint Verification Command

Administrators and automated bootstrap scripts can verify the key fingerprint locally:

```bash
gpg --show-keys --with-colons /etc/apt/keyrings/m3tal-archive-keyring.gpg | grep '^fpr:' | head -n1 | cut -d: -f10
```
Expected output:
```text
5F84FE50A40111C981410E11775AD1473BF25102
```

---

## 3. Canonical Keyring Artifacts & Endpoints

To provide seamless compatibility across modern APT versions, legacy distribution tools, and third-party consumers, the repository publishes public trust material in both binary and ASCII-armored formats.

| File Path in Repository | Public HTTP Endpoint | Format | Primary Target Audience |
| :--- | :--- | :--- | :--- |
| `m3tal-archive-keyring.gpg` | `https://jakej985-rgb.github.io/m3tal-apt-key/m3tal-archive-keyring.gpg` | **Binary OpenPGP Keyring** | Direct download to `/etc/apt/keyrings/` |
| `keyrings/m3tal-archive-keyring.gpg` | `https://jakej985-rgb.github.io/m3tal-apt-key/keyrings/m3tal-archive-keyring.gpg` | **Binary OpenPGP Keyring** | Standard keyrings directory |
| `keyrings/m3tal-archive-keyring.asc` | `https://jakej985-rgb.github.io/m3tal-apt-key/keyrings/m3tal-archive-keyring.asc` | **ASCII-Armored OpenPGP** | Debian 12+ deb822 ascii key source |
| `public.key` | `https://jakej985-rgb.github.io/m3tal-apt-key/public.key` | ASCII-Armored OpenPGP | Legacy curl pipe (`gpg --dearmor`) |
| `KEY.gpg` | `https://jakej985-rgb.github.io/m3tal-apt-key/KEY.gpg` | ASCII-Armored OpenPGP | Historical legacy alias |

---

## 4. Keyring Installation Standards

### 4.1 Client Keyring Placement

- **Canonical Path**: `/etc/apt/keyrings/m3tal-archive-keyring.gpg`
- **Owner**: `root:root`
- **File Permissions**: `0644` (`-rw-r--r--`)
- **Directory Permissions**: `/etc/apt/keyrings` must be `0755` (`drwxr-xr-x`)

### 4.2 Why `/etc/apt/keyrings/` is Mandatory

In older Debian releases (Debian 10 and earlier), keys were added globally to `/etc/apt/trusted.gpg` or `/etc/apt/trusted.gpg.d/`. This was identified as a critical security issue: a key added to `trusted.gpg.d` could authenticate packages from *any* configured repository on the system, creating a vulnerability where a compromise of one third-party key compromised the entire system.

Debian 12 (`bookworm`), Ubuntu 22.04 LTS (`jammy`), and all subsequent versions deprecate `trusted.gpg.d` and require dedicated keyrings in `/etc/apt/keyrings/` paired with `signed-by=` directives.

Furthermore, `/usr/share/keyrings/` is strictly reserved for keys installed by base distribution packages (via `dpkg`). Third-party repositories must never install keys directly into `/usr/share/keyrings/` without package management.

---

## 5. Verified Client Installation Recipe

### 5.1 Hardened Fingerprint-Verifying Bootstrap Flow

The following sequence safely downloads the key into a temporary buffer, cryptographically checks the fingerprint against the expected master key fingerprint, and only installs it if the fingerprint matches exactly:

```bash
set -e

KEYRING_DIR="/etc/apt/keyrings"
KEYRING_FILE="${KEYRING_DIR}/m3tal-archive-keyring.gpg"
EXPECTED_FPR="5F84FE50A40111C981410E11775AD1473BF25102"

# 1. Ensure prerequisites and keyrings directory exist
sudo mkdir -p -m 0755 "$KEYRING_DIR"

# 2. Download and de-armor key into temporary file
TMP_KEY=$(mktemp)
curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/public.key | gpg --dearmor > "$TMP_KEY"

# 3. Cryptographically verify fingerprint
ACTUAL_FPR=$(gpg --show-keys --with-colons "$TMP_KEY" 2>/dev/null | grep '^fpr:' | head -n1 | cut -d: -f10)
if [ "$ACTUAL_FPR" != "$EXPECTED_FPR" ]; then
    echo "ERROR: GPG Fingerprint mismatch! Expected $EXPECTED_FPR, got $ACTUAL_FPR" >&2
    rm -f "$TMP_KEY"
    exit 1
fi

# 4. Install verified keyring
sudo install -m 0644 -o root -g root "$TMP_KEY" "$KEYRING_FILE"
rm -f "$TMP_KEY"

# 5. Configure APT repository source
sudo tee /etc/apt/sources.list.d/m3tal.sources > /dev/null <<EOF
Types: deb
URIs: https://jakej985-rgb.github.io/m3tal-apt-key
Suites: stable
Components: main
Architectures: amd64
Signed-By: ${KEYRING_FILE}
EOF

# 6. Update package indices
sudo apt-get update
```

---

## 6. Private Signing Key Boundary & Protection

The security of the repository relies on strictly maintaining the secret boundary:

1. **Zero Secret Exposure in Public Git**:
   - The private signing key (`secring`, `.key`, or ASCII private key block) **must never** be committed to Git, staged in working trees, or deployed to GitHub Pages.
   - Automated git pre-commit hooks and CI audit scans enforce zero matches for `BEGIN PGP PRIVATE KEY BLOCK` or `BEGIN ENCRYPTED PRIVATE KEY`.
2. **Upstream Release Signing**:
   - Repository metadata (`Release`, `InRelease`) is signed in automated CI using protected repository secrets (`GPG_SIGNING_KEY`, `GPG_PASSPHRASE`) on the upstream builder (`jakej985-rgb/m3tal-core`).
3. **Offline Master Key Security**:
   - The primary certification key is maintained offline with isolated subkeys used for automated deployment signing.

---

## 7. Compliance and Verification Criteria

A repository deployment satisfies Phase 2 trust criteria when:
- [x] Canonical binary keyring `m3tal-archive-keyring.gpg` is deployed and readable at root.
- [x] Keyring contains exactly the public key with fingerprint `5F84FE50A40111C981410E11775AD1473BF25102`.
- [x] Both `dists/stable/InRelease` and `dists/stable/Release.gpg` verify cleanly against the keyring.
- [x] Clean systems installing via `/etc/apt/keyrings/m3tal-archive-keyring.gpg` experience zero APT warnings or errors.
- [x] Zero private key material exists in the repository.
