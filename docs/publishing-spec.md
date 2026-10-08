# M3tal APT Repository: Package Publishing Specification (Phase 06)

> **Document**: `docs/publishing-spec.md`  
> **Phase**: Phase 06 — Package Publishing  
> **Status**: Approved & Implemented  
> **Implementation Tool**: [`scripts/publish_package.py`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/scripts/publish_package.py)

---

## 1. Executive Summary

This specification defines the automated publication workflow for Debian packages (`.deb`) entering the unified M3tal APT repository. It replaces manual file placement and ad-hoc metadata editing with a deterministic, atomic, cryptographically verified publishing pipeline.

Key capabilities provided:
1. **Pre-Publish Metadata Validation**: Ensures every package strictly adheres to Debian Policy standards before ingestion.
2. **Version & Duplicate Guardrails**: Blocks accidental overwrites and unauthorized downgrades.
3. **Canonical Pool Placement**: Normalizes package file naming and places packages into structured pools (`pool/main/<package>/`).
4. **Automated Index Generation**: Produces RFC 822 `Packages` and deterministic `Packages.gz` for all supported architectures (`amd64`, `arm64`, `all`).
5. **Release Descriptors & Hash Computation**: Computes byte counts, MD5, SHA1, SHA256, and SHA512 checksums across all repository indexes.
6. **Cryptographic Signing**: Generates inline signed `InRelease` and detached signature `Release.gpg` via GPG.
7. **Atomic Staging & Swapping**: Builds repository state in an isolated staging workspace before atomically replacing active repository directories.

---

## 2. Publication Pipeline Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│ Candidate .deb Artifact(s) (Built in Project CI / GHA)      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Metadata Validation (`validate_package.py`)              │
│    - Format check (AR archive, debian-binary 2.0)           │
│    - Control fields, syntax, dependencies, architectures    │
└──────────────────────────────┬──────────────────────────────┘
                               │ [Pass]
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Version Guardrails (`deb_version.py`)                     │
│    - Reject duplicate versions (unless --allow-replace)     │
│    - Reject downgrades (unless --allow-downgrade)           │
│    - Validate SemVer mapping & upstream syntax              │
└──────────────────────────────┬──────────────────────────────┘
                               │ [Pass]
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Pool Ingestion & Naming Normalization                    │
│    - Strip accidental 'v' tag prefixes                      │
│    - Target: pool/<component>/<package>/<pkg>_<ver>_<arch>.deb│
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Staged Index Generation (Isolated Temporary Directory)   │
│    - Generate main/binary-<arch>/Packages (RFC 822)         │
│    - Multi-arch indexation (Architecture: all in all trees) │
│    - Deterministic gzip compression (Packages.gz, mtime=0)  │
│    - Generate dists/<suite>/Release with cryptographic      │
│      checksums (MD5, SHA1, SHA256, SHA512)                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Cryptographic Signing (GPG)                              │
│    - Generate InRelease (clearsign)                         │
│    - Generate Release.gpg (detached signature)              │
│    - Verified against official archive public key           │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Atomic Sync & Activation                                 │
│    - Atomically swap staged dists/<suite> into live tree    │
│    - Commit metadata & pool updates to repository git root  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Storage & Pool Layout Conventions

### 3.1 Structured vs Legacy Flat Pools

The M3tal APT repository supports both historical flat layouts and canonical structured layouts:

- **Structured Layout (Target Standard)**:
  ```text
  pool/main/m3tal/m3tal_1.1.62_amd64.deb
  pool/main/m3tal-core/m3tal-core_1.0.0_amd64.deb
  pool/main/m3tal-hub/m3tal-hub_2.0.0_all.deb
  ```
- **Legacy Flat Layout (Backward Compatible)**:
  ```text
  pool/main/m3tal_v1.0.0_amd64.deb
  ...
  pool/main/m3tal_v1.1.62_amd64.deb
  ```

`publish_package.py` includes automatic pool layout detection (`--pool-style auto`), preserving legacy flat locations for existing packages while routing new packages into clean subdirectories.

### 3.2 Debian File Naming Standard

Debian filenames must strictly conform to:
```text
<package>_<upstream-version>[-<debian-revision>]_<architecture>.deb
```
- E.g.: `m3tal_1.1.62_amd64.deb`
- In the past, git tag names were used directly (e.g. `m3tal_v1.1.62_amd64.deb`). The publishing tool normalizes filenames by stripping leading `v` prefixes upon ingestion.

---

## 4. Index Generation & Checksum Specifications

### 4.1 `Packages` Index

For each architecture (`amd64`, `arm64`, etc.), a `Packages` file is generated containing RFC 822 stanzas for each applicable package. Packages tagged `Architecture: all` are indexed across all binary architecture trees.

Each stanza contains:
- `Package`: Package identifier.
- `Architecture`: Target architecture (`amd64`, `arm64`, `all`).
- `Version`: Full Debian version string.
- `Priority`: Debian priority (e.g., `optional`).
- `Section`: Debian repository section (e.g., `utils`).
- `Maintainer`: RFC 822 maintainer address.
- `Installed-Size`: Extracted size in KiB.
- `Depends` / `Recommends` / `Suggests`: Dependency clauses if defined.
- `Homepage`: Project URL if defined.
- `Filename`: Relative path from repository root (e.g. `pool/main/m3tal/m3tal_1.1.62_amd64.deb`).
- `Size`: Exact byte count of the `.deb` file.
- `MD5sum`: 128-bit hex digest.
- `SHA1`: 160-bit hex digest.
- `SHA256`: 256-bit hex digest.
- `SHA512`: 512-bit hex digest.
- `Description`: Synopsis followed by indented description lines.

### 4.2 Deterministic Compression (`Packages.gz`)

Standard `gzip` embeds the local modification timestamp into the gzip header, resulting in different SHA256 checksums across builds even when file contents are identical.
The publication engine enforces deterministic compression by setting `mtime=0` during compression:
```python
with gzip.GzipFile(filename="", mode="wb", fileobj=f_out, mtime=0) as gz:
    gz.write(packages_bytes)
```
This ensures reproducible builds and reduces unnecessary git delta churn.

### 4.3 `Release` Descriptors

The `dists/<suite>/Release` file aggregates metadata and checksums for all index files. Headers include:
```text
Origin: M3TAL
Label: M3TAL
Suite: stable
Codename: stable
Date: <RFC 2822 Timestamp>
Architectures: amd64 arm64
Components: main
Description: M3TAL Core Repository
MD5Sum:
 <hash> <size> main/binary-amd64/Packages
 <hash> <size> main/binary-amd64/Packages.gz
...
SHA256:
 <hash> <size> main/binary-amd64/Packages
 <hash> <size> main/binary-amd64/Packages.gz
...
SHA512:
 <hash> <size> main/binary-amd64/Packages
 <hash> <size> main/binary-amd64/Packages.gz
...
```

---

## 5. Cryptographic Signing Workflow

APT security requires clients to cryptographically verify repository indices. The publication engine creates two cryptographic signatures:

1. **`InRelease`**: An inline clearsigned document containing the complete text of `Release` wrapped with OpenPGP ASCII armor:
   ```bash
   gpg --batch --yes --clearsign --output dists/stable/InRelease dists/stable/Release
   ```
2. **`Release.gpg`**: A detached binary or ASCII-armored OpenPGP signature of `Release`:
   ```bash
   gpg --batch --yes --detach-sign --armor --output dists/stable/Release.gpg dists/stable/Release
   ```

### 5.1 Signing Key Configuration

In CI/CD environments (GitHub Actions), the private signing key is provisioned securely via repository secrets:
- `M3TAL_GPG_PRIVATE_KEY`: ASCII-armored private key.
- `M3TAL_GPG_PASSPHRASE`: Passphrase protecting the key (if encrypted).
- `M3TAL_GPG_KEY_ID`: Official key ID (`ED1DAE1980AD1550`).

The publisher invocation:
```bash
python3 scripts/publish_package.py \
  --repo-dir . \
  --sign \
  --key-id ED1DAE1980AD1550 \
  --passphrase "$GPG_PASSPHRASE" \
  package.deb
```

---

## 6. CLI Usage & Operations Guide

### 6.1 Publishing a Single Package
```bash
python3 scripts/publish_package.py /path/to/my-package_1.0.0_amd64.deb
```

### 6.2 Publishing Multiple Packages in One Atomic Batch
```bash
python3 scripts/publish_package.py \
  --repo-dir /path/to/m3tal-apt-key \
  build/*.deb
```

### 6.3 Regenerating Indexes (Re-indexing Existing Pool)
```bash
python3 scripts/publish_package.py \
  --repo-dir /path/to/m3tal-apt-key \
  --regenerate-indexes
```

### 6.4 Overwriting / Replacing an Identical Version
```bash
python3 scripts/publish_package.py \
  --allow-replace \
  package_1.0.0_amd64.deb
```

---

## 7. Verification & Acceptance Criteria

1. ✅ Every published `.deb` passes strict Debian Policy metadata checks before file copy.
2. ✅ Attempted duplicate publication of an existing version exits with code 1 and descriptive rejection.
3. ✅ Attempted publication of an older version than latest exits with code 1 and downgrade warning.
4. ✅ Multi-architecture indexing correctly includes `all` packages in all binary architecture manifests.
5. ✅ Generated `Release`, `InRelease`, and `Release.gpg` pass cryptographic verification against `public.key`.
6. ✅ Clean Debian/Ubuntu containers can execute `apt-get update` and download packages without hash mismatches or GPG errors.
