# M3tal Key Rotation and Revocation Procedures (Phase 2 & 15)

> **Document**: M3tal Cryptographic Maintenance and Key Lifecycle Standard  
> **Target Repository**: `m3tal-apt-key` (`https://github.com/jakej985-rgb/m3tal-apt-key`)  
> **Phases**: Phase 02 — Trust and Keyring, Phase 15 — Security and Key Rotation  
> **Status**: Active / Canonical Specification  

---

## 1. Overview and Key Lifecycle Policy

Cryptographic keys must have a defined lifecycle to maintain long-term repository security. This policy defines:
- Key ownership and responsibility.
- Scheduled key rotation cadence.
- Dual-key transition period to prevent client disruption.
- Emergency revocation protocol for key compromise.
- CI/CD secret rotation procedures.

---

## 2. Key Ownership & Operational Responsibilities

- **Trust Owner**: Jake Johnson (`jake@m3tal.io`)
- **Key Identity**: `M3tal-Creates <jakej985@gmail.com>`
- **Current Primary Key ID**: `AF6190B0C01346DD`
- **Current Primary Fingerprint**: `B95A45C647577DEBCC877C49AF6190B0C01346DD`
- **Creation Date**: May 15, 2026
- **Scheduled Expiration Review**: May 2028 (2-year rotation review cycle)

The primary secret key and revocation certificate must be preserved in encrypted, offline cold storage. Daily CI release signing operations must use an isolated signing subkey stored as a protected GitHub Action secret with restricted branch policies.

---

## 3. Scheduled Key Rotation Procedure

To rotate a signing key without breaking existing client installations, a **60-day dual-signing transition window** is employed.

```text
Time Line:
[Day 0]                     [Day 30]                     [Day 60]
  │                            │                            │
  ├── Generate New Key K2      ├── Update Bootstrap to K2   ├── Sunset K1
  ├── Add K2 to Keyring        ├── Dual-Sign Release with   └── Sign Release
  │   (Keyring contains K1+K2) │   both K1 and K2               with K2 only
  └── Clients acquire K2       └── Legacy clients still ok
```

### Step 1: Generate New Keypair (T - 60 Days)

Generate a new RSA 4096-bit (or Ed25519) keypair in a secure offline environment:

```bash
gpg --quick-generate-key "M3tal-Creates <jake@m3tal.io>" rsa4096 sign,cert 2y
```

Extract the new public key and generate a designated revocation certificate immediately:

```bash
NEW_KEY_ID="<new_key_id>"
gpg --armor --export "$NEW_KEY_ID" > new_public.key
gpg --output "revocation-${NEW_KEY_ID}.asc" --gen-revoke "$NEW_KEY_ID"
```

### Step 2: Assemble Multi-Key Combined Keyring (T - 60 Days)

APT supports multiple public keys within a single keyring file (`.gpg`).

Combine the existing key ($K_1$) and the new key ($K_2$):

```bash
gpg --dearmor < current_public.key > k1.gpg
gpg --dearmor < new_public.key > k2.gpg

# Concatenate binary keyrings
cat k1.gpg k2.gpg > m3tal-archive-keyring.gpg
cp m3tal-archive-keyring.gpg keyrings/m3tal-archive-keyring.gpg

# Concatenate ASCII-armored keys
cat current_public.key new_public.key > keyrings/m3tal-archive-keyring.asc
```

Commit and push the combined keyring to `m3tal-apt-key`.

### Step 3: Transition Client Keyrings (T - 30 Days)

1. Clients executing `apt upgrade` or running system updates receive packages that update the local keyring file `/etc/apt/keyrings/m3tal-archive-keyring.gpg` with the multi-key bundle.
2. Update the repository bootstrap script (`install.sh`) to install the new key by default.
3. Update upstream CI build secrets (`GPG_SIGNING_KEY`) on `jakej985-rgb/m3tal-core` with Key $K_2$.

### Step 4: Decommission Legacy Key $K_1$ (T + 0 Days)

1. Remove $K_1$ from the active repository signing pipeline.
2. Sign subsequent `Release` files exclusively using $K_2$.
3. Keep $K_1$ in the public keyring for an additional 90 days to allow inactive or offline machines to upgrade gracefully upon returning to service.

---

## 4. Emergency Key Compromise Procedure

If the private signing key is compromised or suspected compromised, immediate action is mandatory to prevent unauthorized package distribution.

### Phase A: Repository Lockdown (Hour 0)

1. **Halt Automated Publishing**:
   Immediately revoke or disable the GitHub Actions token and secret `GPG_SIGNING_KEY` on `jakej985-rgb/m3tal-core`.
2. **Audit Recent Commits**:
   Inspect recent commits to `m3tal-apt-key` to confirm whether any unauthorized packages or metadata modifications were pushed.

### Phase B: Publish Revocation Certificate (Hour 1 - 2)

Import and publish the pre-generated revocation certificate for key `B95A45C647577DEBCC877C49AF6190B0C01346DD`:

```bash
gpg --homedir /tmp/secure_gpg --import revocation-B95A45C647577DEBCC877C49AF6190B0C01346DD.asc
gpg --homedir /tmp/secure_gpg --armor --export-clean > revoked-key.asc
```

Upload the revocation notice to the repository root:
- `https://jakej985-rgb.github.io/m3tal-apt-key/revocation.txt`

### Phase C: Generate Emergency Replacement Key $K_{\text{emergency}}$

1. Generate a new RSA 4096-bit key on an uncontaminated host.
2. Generate fresh `m3tal-archive-keyring.gpg` and `keyrings/m3tal-archive-keyring.asc`.
3. Sign the new `dists/stable/Release` using $K_{\text{emergency}}$.
4. Publish an updated `install.sh` bootstrap script with the new fingerprint hardcoded.

### Phase D: Client Recovery Notice & Automation

Publish a remediation advisory across all M3tal documentation and community channels:

```bash
# Emergency Keyring Repair Command for existing clients:
curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/install.sh | sudo bash
```

The script will detect the mismatched fingerprint, replace the compromised keyring in `/etc/apt/keyrings/m3tal-archive-keyring.gpg`, verify the new fingerprint, and run `apt-get update`.

---

## 5. Continuous Secret Audit & Exposure Prevention

To maintain compliance with repository standards:
1. **Repository Secret Scans**:
   All commits in `m3tal-apt-key` and upstream packages are scanned using automated verification scripts (`scripts/verify_trust.py`).
2. **Environment Variable Hygiene**:
   CI build environments must mask signing keys and never echo private key blocks to build logs or artifacts.
3. **No Key Extraction**:
   No tool or script in `m3tal-apt-key` contains private key decoding logic.
