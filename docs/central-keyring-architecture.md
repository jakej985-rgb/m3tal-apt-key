# M3tal Central Debian Package Keyring & Distribution Architecture

> **Architecture Role**: Authoritative Central Debian Repository & Package Keyring for the M3tal Ecosystem  
> **Repository Base URL**: `https://jakej985-rgb.github.io/m3tal-apt-key`  
> **Keyring Identifier**: `m3tal-archive-keyring.gpg`  
> **GPG Key ID / Fingerprint**: `5F84FE50A40111C981410E11775AD1473BF25102`  
> **UID**: `M3tal-Creates <jakej985@gmail.com>`  

---

## 1. Executive Summary & Architectural Motivation

Previously, applications within the M3tal developer ecosystem (such as Monster Lab) attempted to build independent, isolated GPG keyrings and point users directly to raw GitHub release URLs. This created severe drawbacks:

1. **Fragmented Trust**: Every individual app required users to manually download and trust separate PGP keys, creating key sprawl in `/etc/apt/keyrings/`.
2. **Missing Package Discovery**: Users could not perform `sudo apt update && sudo apt install <app>` from a unified package registry.
3. **No Automatic Upgrades**: Releases distributed via disparate GitHub asset links do not receive automatic package updates via standard `apt upgrade`.
4. **Maintenance Overhead**: Each project had to implement its own ad-hoc signing, checksum, and distribution scripts.

### The Unified Central Solution

Under the Central Keyring Architecture:
- **`m3tal-apt-key` is the single source of truth** for all Debian package distribution across the M3tal ecosystem.
- A user or workstation runs the universal bootstrap installer **once**:
  ```bash
  curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/install.sh | sudo bash
  ```
- All ecosystem applications (e.g. `monster-lab`, `m3tal-core`, `m3tal-godash`, `specs-n-parts`, `shop-manager`, etc.) **push their `.deb` packages directly to `m3tal-apt-key`**.
- The central repository validates incoming packages, stages them into the structured pool, regenerates package indexes (`Packages`, `Packages.gz`, `Release`), and signs the repository with the central M3tal GPG key.

```
+-------------------------------------------------------------------------+
|                          Application Repositories                       |
|   (Monster-Lab, m3tal-core, m3tal-godash, specs-n-parts, shop-manager)  |
+-------------------------------------------------------------------------+
       |                                                    |
       | Local Push:                                        | CI/CD Push:
       | scripts/ingest_deb.py --from-repo                  | repository_dispatch (publish-deb)
       v                                                    v
+-------------------------------------------------------------------------+
|                  m3tal-apt-key (Central Package Authority)              |
|                                                                         |
|  - Ingestion Engine (scripts/ingest_deb.py, .github/workflows/ingest-deb)|
|  - Central Keyring: m3tal-archive-keyring.gpg                           |
|  - Structured Pool: pool/main/<package-id>/                             |
|  - Signed Indices: dists/stable/ (Release, InRelease, Release.gpg)      |
|  - Registry Manifest: registry/packages.yml                             |
+-------------------------------------------------------------------------+
                                   |
                                   | Served via GitHub Pages
                                   v
+-------------------------------------------------------------------------+
|                          End-User Workstations                          |
|                                                                         |
|  - /etc/apt/keyrings/m3tal-archive-keyring.gpg                          |
|  - /etc/apt/sources.list.d/m3tal.list                                   |
|  - Single Command Install: sudo apt install <any-m3tal-app>             |
+-------------------------------------------------------------------------+
```

---

## 2. Central Keyring Standards

All ecosystem applications must adhere to the central keyring specification:

| Parameter | Value | Location / Reference |
| :--- | :--- | :--- |
| **Keyring Name** | `m3tal-archive-keyring.gpg` | `/etc/apt/keyrings/m3tal-archive-keyring.gpg` |
| **Legacy Fallback**| `m3tal-archive-keyring.gpg` | `/usr/share/keyrings/m3tal-archive-keyring.gpg` |
| **Armored Key** | `public.key`, `KEY.gpg` | `https://jakej985-rgb.github.io/m3tal-apt-key/public.key` |
| **Primary Fingerprint** | `5F84FE50A40111C981410E11775AD1473BF25102` | RSA 4096-bit |
| **APT Source Entry** | `m3tal.list` | `/etc/apt/sources.list.d/m3tal.list` |
| **APT Line Syntax** | `deb [signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg] https://jakej985-rgb.github.io/m3tal-apt-key stable main` | Modern Deb822 / signed-by standard |

Applications MUST NOT generate their own separate GPG keyrings.

---

## 3. Package Ingestion Modalities

### Modality A: Remote CI/CD Dispatch (GitHub Actions)
When an application tags a release, its GitHub Actions workflow sends an authenticated `repository_dispatch` to `jakej985-rgb/m3tal-apt-key`:

```yaml
uses: peter-evans/repository-dispatch@v3
with:
  token: ${{ secrets.M3TAL_APT_DISPATCH_TOKEN }}
  repository: jakej985-rgb/m3tal-apt-key
  event-type: publish-deb
  client-payload: >-
    {
      "package_id": "monster-lab",
      "version": "0.1.4",
      "deb_url": "https://github.com/jakej985-rgb/Monster-Lab/releases/download/v0.1.4/monster-lab-v0.1.4-linux.deb"
    }
```

The workflow `.github/workflows/ingest-deb.yml` automatically:
1. Downloads the `.deb` asset.
2. Validates package architecture, control metadata, and dependencies.
3. Moves it to `pool/main/<package_id>/`.
4. Updates `registry/packages.yml`.
5. Recomputes RFC 822 `Packages` and `Packages.gz`.
6. Signs `InRelease` and `Release.gpg` with GPG.
7. Commits and deploys the change.

### Modality B: Local CLI Ingestion (`scripts/ingest_deb.py`)
For local workstation builds or development tests, developers can ingest directly:

```bash
# Ingest local deb
python3 scripts/ingest_deb.py /path/to/monster-lab_0.1.4_amd64.deb

# Ingest from application directory
python3 scripts/ingest_deb.py --from-repo /home/m3tal/apps/Monster-Lab

# Ingest from remote URL
python3 scripts/ingest_deb.py --url https://github.com/jakej985-rgb/Monster-Lab/releases/download/v0.1.4/monster-lab-linux.deb
```

---

## 4. Pool Organization & Multi-Package Hierarchy

The package pool uses structured paths per package identity:
```text
pool/
└── main/
    ├── m3tal/
    │   └── m3tal_1.1.62_amd64.deb
    ├── monster-lab/
    │   └── monster-lab_0.1.4_amd64.deb
    └── <other-apps>/
        └── <app>_<version>_<arch>.deb
```

All indexed packages are unified into:
- `dists/stable/main/binary-amd64/Packages`
- `dists/stable/main/binary-amd64/Packages.gz`
- `dists/stable/Release`
- `dists/stable/InRelease`
- `dists/stable/Release.gpg`
