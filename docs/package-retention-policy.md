# M3tal APT Repository: Package Retention & Pruning Architecture

> **Phase**: Phase 10 — Package Retention  
> **Status**: Active / Production Standard  
> **Target Repository**: `m3tal-apt-key` (`https://github.com/jakej985-rgb/m3tal-apt-key`)  
> **Policy Configuration**: `config/retention-policy.json`  
> **Management Engine**: `scripts/manage_retention.py`  
> **Test Suite**: `scripts/test_retention.py`

---

## 1. Executive Summary & Problem Statement

The M3tal APT repository serves as the central Debian package distribution host for the M3tal orchestration ecosystem. The `m3tal` package is currently versioned on the `0.x` line; the current candidate is `0.24.6`. An earlier `1.x` line (`1.0.x` through `1.1.62`) was published historically and has been **retired** — those versions are no longer part of the active index and must not be referenced as current.

### 1.1 Empirical Baseline Metrics
- **Current Pool**: 65 `.deb` packages across six published packages (`m3tal` plus five `m3tal-plugin-*` packages), all `amd64`.
- **Active Series**: `0.x` releases (`0.1.x` through `0.24.x` for `m3tal`; `0.2.x`–`0.8.x` for plugins).
- **Historical Note**: the retired `1.x` line previously contributed ~124 builds (~2.85 GB working tree, ~5.8 GB total footprint) before pruning; the lessons below remain the governing rationale.

### 1.2 The Indefinite Growth Hazard
Debian packages contain compiled binaries (e.g. `/usr/bin/m3tal-api` ~20 MB for the core `m3tal` package). Each release adds tens of MB of binary data to Git history. Without a rigorous package retention and pruning policy:
1. **Repository Bloat**: Pushing 50 more releases would add ~1.25 GB of working tree data and another ~1.25 GB of packfiles, exceeding GitHub's recommended repository size limit (5 GB) and causing cloning timeouts.
2. **Bandwidth Costs**: APT index files (`Packages` / `Packages.gz`) and metadata transfers scale with total packages, increasing latency for end-user installations.
3. **Operational Overhead**: Auditing, indexing, and validating thousands of legacy point-release binaries degrades CI pipeline execution times.

---

## 2. Retention Architecture & Policy Specification

The M3tal retention engine enforces a deterministic, multi-tiered lifecycle model defined in `config/retention-policy.json`.

### 2.1 Retention Tiers

| Tier | Classification | Criteria | Action |
| :--- | :--- | :--- | :--- |
| **Tier 0** | **Current Candidate** | Highest semantic Debian version across the entire repository (currently `0.24.6` for `m3tal`). | **Mandatory Retain**. Cannot be pruned under any circumstances. |
| **Tier 1** | **Pinned Milestones** | Explicitly designated landmark or LTS releases (`0.24.0`, `0.24.5`, `0.24.6`, or custom pins). | **Mandatory Retain**. Preserves foundational history and long-term compatibility. |
| **Tier 2** | **Recent Active Window** | Top $N$ most recent releases within each active or supported series (default $N=5$). | **Retain Active**. Accommodates rollback requirements for existing deployments. |
| **Tier 3** | **Obsolete / Deprecated** | Releases older than the recent window not covered by milestone pins. | **Prune Candidate**. Transitioned to archive/snapshot manifest and removed from active pool. |

```text
[All Packages in pool/main/]
       │
       ├── Is version the highest candidate? ───> YES ───> [RETAIN_CURRENT]
       │
       ├── Is version in pinned_versions? ─────> YES ───> [RETAIN_PINNED]
       │
       ├── Is rank <= keep_recent_per_series? ──> YES ───> [RETAIN_RECENT]
       │
       └── Otherwise ──────────────────────────────────> [PRUNE_CANDIDATE]
                                                               │
                                                               ▼
                                               [Create Snapshot Manifest]
                                                               │
                                                               ▼
                                               [Move to Archive / Remove]
                                                               │
                                                               ▼
                                               [Regenerate Packages & Release]
```

### 2.2 Safety Guardrails (Non-Negotiable Invariants)

1. **Zero Silent Deletions**: Pruning operations default to `--dry-run`. Deletions require the explicit `--execute` flag.
2. **Active Candidate Invariant**: The repository candidate version must never be pruned. If any policy rule or bug attempts to prune the candidate, the engine immediately aborts with exit code 1.
3. **Safety Floor**: Pruning will abort if the number of retained packages falls below `min_retained_packages` (default: `10`).
4. **Snapshot Guarantee**: Before any file is modified or unlinked on disk, an immutable snapshot manifest (`snapshots/snapshot-manifest-<timestamp>.json`) recording all file hashes, metadata, and raw indexes is persisted.
5. **Atomic Index Recalculation**: Pruning immediately regenerates `Packages`, compresses `Packages.gz`, recalculates all checksum blocks (MD5, SHA1, SHA256, SHA512) in `dists/stable/Release`, and verifies integrity.

---

## 3. Deprecation Lifecycle & Grace Periods

To prevent breaking existing automated environments or configuration management playbooks, releases follow a staged deprecation lifecycle:

1. **Active**: Fully supported, indexed in `Packages`, hosted in `pool/main/`.
2. **Deprecated (90-day grace period)**: Marked in release notes and metadata. Packages remain available in the repository index.
3. **Archived / Snapshot**: Package artifact is removed from the active GitHub Pages APT distribution but preserved in snapshot manifests and cold archive storage (`archive/pool/main/`).
4. **Purged**: Permanent removal after archive retention threshold.

---

## 4. Snapshot Manifest Schema & Historical Preservation

Every snapshot captured by `scripts/manage_retention.py snapshot` generates a structured JSON manifest containing:

```json
{
  "timestamp": "20261001T180251Z",
  "repo_root": "/home/m3tal/apps/m3tal-apt-key",
  "total_packages": 65,
  "pool_files": {
    "m3tal_0.24.6_amd64.deb": {
      "md5": "490c1156dafb12e2dfc16593fb72dddc",
      "sha1": "232d7abbd4c487adcc7fde8e2a8a27abcd16b825",
      "sha256": "0f74d46d3ff1b3385e3a69a05628f976cbfab59e9a42421927a5597d004f2cf1",
      "sha512": "479e5b382ebbc6efdd924080d68a86914da41b90f382f17cca17939698aa68e9a498ab9618abf047f7a6713d6840a265c2334e877f9cc04be0787dfa82be63d1",
      "size": 14114870
    }
  },
  "packages_content": "Package: m3tal\n...",
  "release_content": "Origin: M3TAL\n..."
}
```

This manifest provides complete cryptographic auditability and reproducibility, allowing full reconstruction of repository index state at any point in history.

---

## 5. Tooling & Automation Guide

### 5.1 CLI Commands

```bash
# 1. Audit inventory and retention status
python3 scripts/manage_retention.py inventory

# 2. Output structured JSON inventory
python3 scripts/manage_retention.py inventory --json /tmp/inventory.json

# 3. Create an immutable repository snapshot
python3 scripts/manage_retention.py snapshot --dir snapshots

# 4. Preview pruning without making disk changes (Dry-Run)
python3 scripts/manage_retention.py prune --dry-run

# 5. Execute policy pruning and metadata index regeneration
python3 scripts/manage_retention.py prune --execute

# 6. Verify repository adherence to retention bounds
python3 scripts/manage_retention.py verify
```

### 5.2 Verification Suite

The retention engine is backed by an automated unit and integration test suite:

```bash
python3 scripts/test_retention.py
```

Tests cover:
- Debian version ordering (epochs, revisions, alphanumeric comparison)
- Multi-series package classification
- Safety guardrail activation when thresholds are breached
- Mock repository pruning, file archiving, and bit-level Release checksum verification.

---

## 6. Storage Savings Assessment

Applying the standard retention profile (`keep_recent_per_series: 5`, `pinned_versions: ["0.24.0", "0.24.5", "0.24.6"]`) bounds the active pool to a small set of recent, rollback-capable builds per package series. Historically, applying the equivalent profile to the retired `1.x` line reclaimed ~2.57 GB (**~90%** footprint reduction) by pruning 112 obsolete builds while retaining 12 critical versions — the same mechanics now keep the `0.x` pool lean.
