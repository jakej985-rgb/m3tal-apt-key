# M3tal Ecosystem Distribution Guide

> **Status**: Authoritative distribution reference
> **Repository**: `m3tal-apt-key` — `https://jakej985-rgb.github.io/m3tal-apt-key`
> **Suite**: `stable` · **Component**: `main` · **Architectures**: `amd64` only
> **Signing Key**: RSA 4096, fingerprint `5F84FE50A40111C981410E11775AD1473BF25102` (key ID `775AD1473BF25102`)

This document is the single authoritative description of how M3tal ecosystem software is distributed to end users via APT. If any other document conflicts with this one, this one wins.

---

## 1. Trust Model

All repository metadata is cryptographically signed with the central M3tal GPG key:

- `dists/stable/InRelease` — clearsigned `Release` file (preferred by modern APT).
- `dists/stable/Release.gpg` — detached signature over `Release`.
- `dists/stable/Release` — plaintext index of checksums (MD5/SHA1/SHA256/SHA512) and sizes for `Packages` and `Packages.gz`.
- `dists/stable/main/binary-amd64/Packages(.gz)` — RFC 822 package index.

APT clients verify the signature against the keyring installed at `/etc/apt/keyrings/m3tal-archive-keyring.gpg`, then verify every downloaded `.deb` against the checksums in the signed index. A package that is not signed by key `775AD1473BF25102` is rejected.

### Bootstrap (one-time client setup)

```bash
curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/install.sh | sudo bash
```

`install.sh` fetches `public.key`, verifies the fingerprint before trusting it, dearmors it to `/etc/apt/keyrings/m3tal-archive-keyring.gpg` (mode `0644`), writes `/etc/apt/sources.list.d/m3tal.list`, and runs `apt-get update`.

Equivalent manual source line:

```text
deb [signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg] https://jakej985-rgb.github.io/m3tal-apt-key stable main
```

---

## 2. Repository Layout

```text
m3tal-apt-key/
├── pool/main/<package>/           # .deb binaries, one dir per package
│   └── <package>_<version>_amd64.deb
├── dists/stable/
│   ├── InRelease                  # signed Release (inline)
│   ├── Release                    # plaintext metadata
│   ├── Release.gpg                # detached signature
│   └── main/binary-amd64/
│       ├── Packages               # uncompressed index
│       └── Packages.gz            # compressed index
├── registry/packages.yml          # authoritative package registry
├── scripts/ingest_deb.py          # ingestion engine
└── install.sh                     # client bootstrap
```

Package filenames use underscores: `<name>_<version>_amd64.deb` (e.g. `m3tal_0.24.6_amd64.deb`) — **not** `v`-prefixed names.

---

## 3. Publishing Pipeline (publish-deb dispatch)

Package publication is automated; maintainers do **not** hand-run `dpkg-scanpackages` or sign releases locally.

1. An app repository tags a release and its `dispatch-apt.yml` workflow (template: `templates/dispatch-apt.yml`) sends a `repository_dispatch` event of type **`publish-deb`** to `jakej985-rgb/m3tal-apt-key`.
2. `.github/workflows/ingest-deb.yml` receives the payload:

   ```json
   {
     "package_id": "m3tal",
     "version": "0.24.6",
     "deb_url": "https://github.com/<owner>/<repo>/releases/download/v0.24.6/<package>_0.24.6_amd64.deb",
     "sha256": "<64-char hex digest of the .deb asset>"
   }
   ```

3. `scripts/ingest_deb.py` downloads the `.deb`, verifies `sha256` when supplied, validates architecture (`amd64`), control metadata, and dependencies, then places it in `pool/main/<package>/`.
4. Validation gates run (`validate_package.py`, `validate_registry.py`, `validate_repository.py`); any failure aborts the publish.
5. Indices are regenerated (`scripts/generate_indices.py` → `Packages`, `Packages.gz`, `Release`), and `Release` is signed to produce `InRelease` and `Release.gpg`.
6. The complete set is committed atomically to `main`.
7. `.github/workflows/deploy-latest-validated.yml` deploys to GitHub Pages only after validation passes, and `verify_deployed_repository.py` checks the live endpoint.

Local ingestion (`python3 scripts/ingest_deb.py <deb>`) exists for development and verification only — it is not the production publish path.

---

## 4. Package Naming Policy

| Package family | Meaning | Source |
| :--- | :--- | :--- |
| `m3tal` | **Core platform package.** Installs `/usr/bin/m3tal-api` and `m3tal-api.service` (port 5050; web GUI at `/gui/`, REST API at `/api/v2`; config in `/etc/m3tal/.env`, state in `state.db`). There is no `/usr/bin/m3tal` CLI and no `m3tal.service` orchestrator. | `jakej985-rgb/m3tal-apt-key` |
| `m3tal-plugin-*` | Plugins for the m3tal core platform, versioned and released from the `m3tal-plugins` repository. | `jakej985-rgb/m3tal-plugins` |
| `<app-name>` | Standalone non-core ecosystem applications may use their own Debian package names (e.g. `monster-lab`, `shop-manager`). | Each app's own repository |

All packages currently target `amd64` only.

---

## 5. Registry Semantics (`registry/packages.yml`)

The registry is the machine-readable source of truth consumed by `scripts/validate_registry.py`, `scripts/generate_indices.py`, and M3tal-Hub.

| Status | Meaning |
| :--- | :--- |
| `planned` | Specified in the registry; no published artifacts yet. No `pool/main/<pkg>/` directory is required. |
| `active` | Build/CI pipeline implemented; artifacts not yet indexed. |
| `published` | `.deb` artifacts exist in `pool/main/<pkg>/`, are indexed in `Packages.gz`, and are installable via `apt install`. **The validator requires a matching non-empty pool directory for every `published` entry.** |
| `deprecated` | Retired/superseded; retained per policy for backward compatibility. |

Other fields: `supported_architectures` (currently `amd64` only), `publication.pool_path` (`pool/main/<pkg>`), `publication.retention_count`, `publication.auto_publish`, and `metadata.latest_version`.

---

## 6. Retention & Rollback

- `config/retention-policy.json` defines `keep_recent_per_series: 5`, `min_retained_packages: 10`, `protected_series`, and explicit `pinned_versions`.
- `scripts/manage_retention.py` enforces tiers: current candidate (never pruned) → pinned milestones → recent window → prune candidates.
- Pruning writes an immutable snapshot manifest (`snapshots/snapshot-manifest-<ts>.json`) before removing anything, then regenerates all indices and signatures through the pipeline.
- Users pin/rollback with `apt-get install <pkg>=<version>` plus `apt-mark hold` — see `docs/user-setup-guide.md`.

---

## 7. Key Rotation

Key rotation, dual-trust transitions, and emergency revocation are governed by `docs/security-and-key-rotation.md`. The fingerprint `5F84FE50A40111C981410E11775AD1473BF25102` is canonical; `public.key` and `KEY.gpg` must remain byte-identical.

---

## 8. Responsibility Boundaries

| Repository / System | Owns |
| :--- | :--- |
| **`m3tal-apt-key`** (this repo) | Debian trust + distribution: GPG keyring, signed `Release`/`InRelease`, package pool, APT indices, registry, ingest/dispatch pipeline, GitHub Pages hosting. |
| **M3tal-Hub** | Web discovery: app catalog, install snippets, version/arch badges derived from `registry/packages.yml`. |
| **App repositories** | Source code, builds, release tagging, and the `publish-deb` dispatch that submits `.deb` artifacts here. |
| **M3tal-core** | Runtime and plugin supervision: the `m3tal` platform runtime that loads and supervises `m3tal-plugin-*` packages on the host. |

This repo does not build application binaries and does not supervise installed software; it only distributes signed `.deb` artifacts.

---

## 9. Current Package Matrix

| Package | Latest | Status | Source Repo | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `m3tal` | `0.24.6` | published | `jakej985-rgb/m3tal-apt-key` | Core platform: `m3tal-api` binary + service |
| `m3tal-plugin-compose` | `0.6.0` | published | `jakej985-rgb/m3tal-plugins` | Compose orchestration plugin |
| `m3tal-plugin-docker-monitor` | `0.8.1` | published | `jakej985-rgb/m3tal-plugins` | Docker monitoring plugin |
| `m3tal-plugin-mesh` | `0.5.0` | published | `jakej985-rgb/m3tal-plugins` | Mesh networking base plugin |
| `m3tal-plugin-mesh-cluster` | `0.4.1` | published | `jakej985-rgb/m3tal-plugins` | Cluster mesh coordination |
| `m3tal-plugin-mesh-node` | `0.4.1` | published | `jakej985-rgb/m3tal-plugins` | Per-node mesh agent |
| `m3tal-core` | `1.0.0` | planned | `jakej985-rgb/m3tal-core` | Ecosystem runtime/topology |
| `m3tal-api` | `0.1.0` | planned | `jakej985-rgb/m3tal-api` | Standalone API daemon |
| `m3tal-godash` | `0.1.0` | planned | `jakej985-rgb/m3tal-godash` | Telemetry dashboard service |
| `m3tal-stack` | `0.1.0` | planned | `jakej985-rgb/m3tal-stack` | Stack lifecycle CLI |
| `monster-lab` | `0.1.4` | planned | `jakej985-rgb/Monster-Lab` | STEM robotics studio |
| `red-music-locker` | `1.0.0` | planned | `jakej985-rgb/red-music-locker` | Audio locker daemon |
| `shop-manager` | `0.0.1` | planned | `jakej985-rgb/shop-manager` | POS/inventory client |
| `specs-n-parts` | `0.0.1` | planned | `jakej985-rgb/specs-n-parts` | Parts/spec tracker |
| `comicinfo-generator` | `0.0.1` | planned | `jakej985-rgb/comicinfo-generator` | Comic metadata CLI |
