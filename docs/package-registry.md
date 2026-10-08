# M3tal Package Registry Specification & Indexing Standard

> **Phase**: Phase 05 — Package Registry  
> **Target Manifest**: `registry/packages.yml`  
> **Schema Definition**: `registry/schema.json`  
> **Validator Tooling**: `scripts/validate_registry.py`  
> **Indexing Engine**: `scripts/generate_indices.py`  
> **Target Distribution**: `stable main`

---

## 1. Overview & Architectural Role

The M3tal Package Registry serves as the machine-readable, authoritative single source of truth connecting M3tal developer projects across GitHub to published Debian packages distributed through the APT repository.

Before this registry, package releases were manually published without centralized cataloging, lifecycle state tracking, or automated index reconciliation. The Phase 05 Package Registry introduces:
1. **Authoritative Package Catalog**: Declarative YAML manifest linking GitHub source repos, Debian package identities, architectures, dependencies, and retention rules.
2. **Schema & Policy Validation**: Automated CI-ready validation (`scripts/validate_registry.py`) enforcing Debian Policy naming constraints, architecture standards, and integrity cross-checks against the physical `pool/` directory.
3. **Automated Package Indexing Engine**: High-performance indexer (`scripts/generate_indices.py`) that scans `pool/`, extracts `.deb` control stanzas, calculates multi-algorithm checksums, and compiles RFC 822 `Packages` and `Release` files.

---

## 2. Registry Schema Specification (`packages.yml`)

The root structure of `registry/packages.yml` comprises two primary sections: `repository` and `packages`.

### 2.1 Top-Level Repository Configuration

```yaml
version: "1.0.0"
repository:
  url: "https://jakej985-rgb.github.io/m3tal-apt-key"
  suite: "stable"
  codename: "stable"
  origin: "M3TAL"
  label: "M3TAL"
  components:
    - "main"
  architectures:
    - "amd64"
    - "arm64"
  keyring:
    fingerprint: "5F84FE50A40111C981410E11775AD1473BF25102"
    path: "/etc/apt/keyrings/m3tal-archive-keyring.gpg"
```

### 2.2 Package Manifest Schema

Each entry under `packages:` specifies:

```yaml
- id: "m3tal"                           # Unique internal slug ([a-z0-9-]+)
  name: "m3tal"                         # Debian package name (Debian Policy 5.6.1)
  source_repo: "jakej985-rgb/m3tal-apt-key" # GitHub repository identifier
  type: "cli"                           # Package type: cli, service, desktop, core-system, library
  status: "published"                   # Status: planned, active, published, deprecated
  supported_architectures:              # Target CPU architectures
    - "amd64"
  publication:
    component: "main"                   # APT component
    distribution: "stable"              # APT distribution suite
    pool_path: "pool/main"              # Pool storage location
    retention_count: 10                 # Number of historical releases to retain
    auto_publish: true                  # Eligible for CI automated publication
  metadata:
    latest_version: "1.1.62"            # Current latest package version
    section: "admin"                    # Debian archive section
    priority: "optional"                # Debian package priority
    maintainer: "M3tal-Creates <jakej985@gmail.com>"
    homepage: "https://jakej985-rgb.github.io/m3tal-apt-key/"
    description: |
      M3tal Agent - Autonomous terminal & workflow management daemon
      M3tal is the central Linux CLI runtime and background process orchestrator.
  dependencies:
    runtime:
      - "libc6 (>= 2.31)"
      - "ca-certificates"
      - "curl"
    recommends:
      - "git"
      - "tmux"
    build:
      - "bash"
```

---

## 3. Package Types & Status Lifecycle

### 3.1 Package Types
- **`cli`**: Command-line developer utilities, diagnostic tools, and administrative CLIs.
- **`service`**: System daemons, background agents, and background network services (with systemd unit units).
- **`desktop`**: GUI applications (GTK, Flutter, Electron) with desktop launcher entries (`/usr/share/applications/*.desktop`).
- **`core-system`**: Foundational ecosystem runtime, directory topologies, and shared configs (`m3tal-core`).
- **`library`**: Shared compiled binaries, native plugins, or shared scripts.
- **`metapackage`**: Package dependency aggregators containing no files other than dependency declarations.

### 3.2 Status Lifecycle
```text
  [ planned ] ────► [ active ] ────► [ published ] ────► [ deprecated ]
 (Design/Spec)     (Building CI)   (Available in APT)    (Obsolete/Retired)
```
- **`planned`**: Spec defined in registry; implementation in progress.
- **`active`**: CI pipeline and package packaging definitions implemented; builds tested.
- **`published`**: Artifacts deployed to `pool/`, indexed in `Packages.gz`, and downloadable by `apt install <package>`.
- **`deprecated`**: Package superseded or retired; preserved for backward compatibility according to retention policy.

---

## 4. Current Ecosystem Registry Inventory

| Package ID | Debian Name | Type | Status | Supported Arch | Source Repository |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `m3tal` | `m3tal` | `cli` | `published` | `amd64` | `jakej985-rgb/m3tal-apt-key` |
| `m3tal-core` | `m3tal-core` | `core-system` | `active` | `amd64`, `arm64`, `all` | `jakej985-rgb/m3tal-core` |
| `m3tal-api` | `m3tal-api` | `service` | `planned` | `amd64`, `arm64` | `jakej985-rgb/m3tal-api` |
| `m3tal-godash` | `m3tal-godash` | `service` | `planned` | `amd64`, `arm64` | `jakej985-rgb/m3tal-godash` |
| `m3tal-stack` | `m3tal-stack` | `cli` | `planned` | `amd64`, `arm64` | `jakej985-rgb/m3tal-stack` |
| `monster-lab` | `monster-lab` | `desktop` | `active` | `amd64` | `jakej985-rgb/Monster-Lab` |
| `red-music-locker` | `red-music-locker` | `service` | `active` | `amd64` | `jakej985-rgb/red-music-locker` |
| `shop-manager` | `shop-manager` | `desktop` | `active` | `amd64` | `jakej985-rgb/shop-manager` |
| `specs-n-parts` | `specs-n-parts` | `desktop` | `active` | `amd64` | `jakej985-rgb/specs-n-parts` |
| `comicinfo-generator` | `comicinfo-generator` | `cli` | `active` | `amd64`, `all` | `jakej985-rgb/comicinfo-generator` |

---

## 5. Automated Validation & Verification

### 5.1 Validation Script (`scripts/validate_registry.py`)
Run the validation suite to ensure compliance:

```bash
python3 scripts/validate_registry.py
```

Checks enforced:
- **YAML & Schema Conformance**: Validates types, required fields, and structural constraints.
- **Debian Name Compliance**: Regex `^[a-z0-9][a-z0-9+-.]+$` (must start with alphanumeric, lowercase, at least 2 characters).
- **Identifier Uniqueness**: Ensures zero duplicate IDs or package names.
- **Debian Version Syntax**: Validates semantic / Debian epoch syntax (`[epoch:]upstream[-debian]`).
- **Pool Synchronization**: For any package marked `published`, verifies that matching `.deb` archives exist in the pool.

### 5.2 Package Indexing Engine (`scripts/generate_indices.py`)
Run the indexer to verify or regenerate the repository index:

```bash
# Verify generated index against current repository metadata
python3 scripts/generate_indices.py --verify --dry-run

# Output regenerated index to custom directory
python3 scripts/generate_indices.py --output-dir /tmp/test-dist
```

Workflow:
1. Loads `registry/packages.yml` and discovers all registered and pool packages.
2. Scans `pool/` recursively for `.deb` binaries.
3. Invokes `dpkg-deb -f` to extract canonical control fields (`Package`, `Version`, `Installed-Size`, `Depends`, etc.).
4. Calculates cryptographic hashes (`MD5sum`, `SHA1`, `SHA256`) and file byte sizes.
5. Formats standard RFC 822 `Packages` and gzip-compresses to `Packages.gz`.
6. Computes `Release` checksum entries.

---

## 6. M3tal-Hub Integration

The Package Registry directly maps to application records in `M3tal-Hub/apps/manifest.yml`. When users discover an application on the M3tal-Hub portal:
1. The Hub matches the app `id` to the corresponding package in `registry/packages.yml`.
2. If `status: published` or `status: active`, the Hub renders the native APT installation snippet:
   ```bash
   sudo apt update && sudo apt install <package-name>
   ```
3. Version and architecture compatibility badges in M3tal-Hub are derived directly from this registry.
