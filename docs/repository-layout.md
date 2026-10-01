# M3tal Debian Repository Layout & Filesystem Standard

> **Phase**: Phase 04 — Repository Layout  
> **Target Repository**: `m3tal-apt-key` (`https://github.com/jakej985-rgb/m3tal-apt-key`)  
> **Hosting Root**: `https://jakej985-rgb.github.io/m3tal-apt-key/`  
> **Standard**: Debian Repository Format (RFC 822 / Debian Policy Manual Chapter 2)

---

## 1. Overview & Directory Topology

The M3tal APT repository implements a clean physical filesystem layout adhering to Debian repository standards while serving as an immutable static distribution endpoint on GitHub Pages.

```text
/home/m3tal/apps/m3tal-apt-key/
├── .nojekyll                            # Disables Jekyll processing on GitHub Pages
├── KEY.gpg                              # Root public key (ASCII armored backward compatibility)
├── public.key                           # Root public key (ASCII armored backward compatibility)
├── index.html                           # Landing page & web setup wizard
├── install.sh                           # Hardened universal bootstrap installer
├── README.md                            # Repository readme & overview
│
├── dists/                               # APT distribution indices & release manifests
│   └── stable/                          # Primary distribution suite
│       ├── InRelease                    # Inline signed Release manifest (clearsign)
│       ├── Release                      # Plaintext Release index with cryptographic checksums
│       ├── Release.gpg                  # Detached OpenPGP signature for Release
│       └── main/                        # Component: main (freely redistributable software)
│           └── binary-amd64/            # Architecture: amd64
│               ├── Packages             # RFC 822 binary package catalog
│               └── Packages.gz          # Gzip-compressed binary package catalog
│
├── pool/                                # Binary package storage
│   └── main/                            # Component storage
│       ├── m3tal_v1.0.0_amd64.deb       # Legacy flat pool (124 historical builds v1.0.0 - v1.1.62)
│       ├── ...                          # (Preserved for zero-downtime client compatibility)
│       ├── m3tal_v1.1.62_amd64.deb
│       └── <package>/                   # Target hierarchical layout: pool/main/<package>/
│           └── <package>_<version>_<arch>.deb
│
├── keys/                                # Public trust material & keyrings
│   ├── m3tal-archive-keyring.gpg        # Binary OpenPGP keyring (for /etc/apt/keyrings/)
│   ├── m3tal-archive-keyring.asc        # ASCII-armored OpenPGP public key
│   └── README.md                        # Keyring trust specifications and fingerprint audit
│
├── registry/                            # Ecosystem package registry & metadata
│   ├── packages.yml                     # Machine-readable registry of published & tracked packages
│   └── schema.json                      # JSON schema for registry validation
│
├── scripts/                             # Repository management, indexing & verification tooling
│   ├── verify_baseline.py               # Phase 00 baseline audit suite
│   ├── test_bootstrap.py                # Phase 03 universal bootstrap test suite
│   ├── verify_layout.py                 # Phase 04 repository layout verification suite
│   ├── validate_registry.py             # Phase 05 package registry validator
│   └── generate_indices.py              # Repository indexing & Release generator
│
├── docs/                                # Architecture & operational documentation
│   ├── current-state.md                 # Phase 00 baseline state audit
│   ├── universal-bootstrap.md           # Phase 03 bootstrap installation guide
│   ├── repository-layout.md             # Phase 04 physical layout standard
│   └── package-registry.md              # Phase 05 package registry specification
│
├── plan/                                # Phased modernization roadmap (Phases 00 - 16)
│   ├── 00-repository-audit.md
│   ├── ...
│   └── 16-end-to-end-validation.md
│
└── projects/                            # Web redirect shims for ecosystem projects
    └── m3tal-core/
        └── index.html
```

---

## 2. Directory Responsibilities

### 2.1 Distribution Trees (`dists/`)
- Contains all distribution metadata required by Debian APT (`apt-get`, `apt`, `synaptic`, `aptitude`).
- **Suite**: `stable` (codename: `stable`).
- **Components**: `main`.
- **Architectures**: `amd64` (default), extensible to `arm64` and `all`.
- Contains uncompressed `Packages` and gzip-compressed `Packages.gz`.
- Hashes (`MD5Sum`, `SHA1`, `SHA256`, `SHA512`) of all index files are listed inside `Release`, which is authenticated by `InRelease` and `Release.gpg`.

### 2.2 Binary Storage (`pool/`)
- The `pool/` directory stores Debian package files (`.deb`).
- **Debian Convention**: Debian mirrors structure packages under `pool/<component>/<source-prefix>/<source-package>/`.
- **M3tal Standard**: `pool/main/<package>/<package>_<version>_<arch>.deb`.
- **Backward Compatibility Policy**:
  - The repository contains 124 historical packages at `pool/main/m3tal_v*.deb`.
  - These existing files MUST NOT be moved or removed without corresponding metadata resigning, because active installations and existing signed `Packages` files directly reference `pool/main/m3tal_v*.deb`.
  - As established in Phase 04, the package indexer supports both the historical flat files and modern `pool/main/<package>/` subdirectories seamlessly.

### 2.3 Cryptographic Trust Material (`keys/`)
- Public keys are organized cleanly in `keys/`.
- `keys/m3tal-archive-keyring.gpg`: Standard binary de-armored format suitable for direct installation into `/etc/apt/keyrings/m3tal-archive-keyring.gpg`.
- `keys/m3tal-archive-keyring.asc`: Human-readable ASCII-armored format.
- Fingerprint: `B95A45C647577DEBCC877C49AF6190B0C01346DD`.
- Root `public.key` and `KEY.gpg` are kept for backward compatibility with existing external deployment scripts.

### 2.4 Ecosystem Registry (`registry/`)
- Contains `registry/packages.yml`, the single authoritative machine-readable manifest linking source GitHub repositories to published Debian packages.
- Defines package categories, build targets, dependencies, architectures, and retention policies.

### 2.5 Tooling & Verification (`scripts/`)
- Repository maintenance tooling is decoupled from the published artifact trees.
- No binary packages or temporary build artifacts are ever placed in `scripts/`.
- All scripts are self-contained, modular, and provide explicit exit codes (0 = success).

---

## 3. GitHub Pages Hosting & Caching Considerations

1. **`.nojekyll`**:
   The `.nojekyll` file at repository root prevents GitHub Pages from processing filenames with underscores (such as `m3tal_v1.1.62_amd64.deb`) or ignoring directories starting with dots.
2. **MIME Types**:
   - `.deb`: `application/vnd.debian.binary-package` (or `application/octet-stream`)
   - `Release`, `InRelease`: `text/plain`
   - `Packages.gz`: `application/gzip`
   - `Packages`: `text/plain`
3. **Atomic Publication**:
   Repository indexes and Release files must be generated and committed together in a single Git commit to prevent window conditions where `Packages.gz` and `Release` checksums fall out of sync during web fetching.
