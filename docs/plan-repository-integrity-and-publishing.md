# Plan: Fix APT Repository Integrity and Publishing

## Status

- **Priority:** Critical — APT clients currently reject the published repository index.
- **Scope:** `m3tal-apt-key` repository generation, signing, CI validation, GitHub Pages deployment, and post-deployment verification.
- **Observed on:** 2026-10-26.
- **Affected endpoint:** `https://jakej985-rgb.github.io/m3tal-apt-key/dists/stable`

## 1. Problem Summary

The server downloaded package indexes that do not match the hashes and sizes in the signed `InRelease` metadata:

| Artifact | Advertised by `InRelease` | Downloaded |
|---|---:|---:|
| `main/binary-amd64/Packages` | 43,649 bytes | 45,216 bytes |
| `main/binary-amd64/Packages.gz` | 12,071 bytes | 12,449 bytes |

The downloaded `Packages.gz` SHA-256 was `5240340a03b678ae84889306265c72d1152bbdf018de7920db882222f124625f`; the signed `InRelease` advertises `f90a50bd877b83d37ac77fb06122acef6ae2c6c26840a90ebc28626aee9f1543`.

The CI run [40405475372](https://github.com/jakej985-rgb/m3tal-apt-key/actions/runs/40405475372) on commit `f2691468ccc57a96119297c0f4c34ccd5c2e3f66` failed repository integrity validation. Its log reports that index checksums and gzip integrity pass **against the checked-out `Packages` files**, `InRelease` verifies, but `Release.gpg` fails with `BAD signature`. The Pages deployment job nevertheless succeeded.

This is evidence of stale/inconsistent release metadata and signatures in the committed repository, with a separate gap between validation and deployment. GitHub Pages caching or overlapping deployments may contribute to what clients receive, but must be tested rather than assumed to be the sole cause.

## 2. Goals and Non-Goals

### Goals

- Ensure `Packages`, `Packages.gz`, `Release`, `InRelease`, and `Release.gpg` always describe and authenticate the same repository state.
- Fail publication before deployment if any index, checksum, signature, package-pool, or registry validation fails.
- Prevent concurrent ingestion/retention operations from overwriting one another's generated metadata.
- Verify the files actually served by GitHub Pages after deployment.
- Keep client-side APT signature and checksum verification enabled.

### Non-goals

- Do not disable APT hash/signature checks.
- Do not replace or rotate the trusted signing key as a workaround.
- Do not manually edit checksum values in `Release` without regenerating and signing all dependent metadata.

## 3. Phase 1 — Establish a Reproducible Baseline

1. Preserve the failing commit and CI artifact/logs for comparison.
2. On a clean checkout of `main`, record sizes and SHA-256 hashes for:
   - `dists/stable/main/binary-amd64/Packages`
   - `dists/stable/main/binary-amd64/Packages.gz`
   - `dists/stable/Release`
   - `dists/stable/InRelease`
   - `dists/stable/Release.gpg`
3. Re-run `scripts/validate_repository.py --strict --github-actions --skip-container-test` and preserve the full output.
4. Verify `Release.gpg` against `Release` and `InRelease` independently with the repository public key.
5. Download each published file directly from GitHub Pages using cache-busting query parameters and compare it with the same file from the commit. Repeat a few times to distinguish committed mismatch from stale CDN/deployment responses.

**Acceptance criteria:** the failure is reproducible and the investigation identifies whether the first inconsistency exists in Git, the workflow workspace, or the deployed HTTP response.

## 4. Phase 2 — Make Index Generation and Signing One Transaction

Audit `scripts/publish_package.py`, `scripts/ingest_deb.py`, `scripts/generate_indices.py`, and `scripts/manage_retention.py`.

1. Establish a single authoritative index-generation path for normal ingestion, index-only regeneration, and retention/pruning. Avoid alternate code paths that write index files differently.
2. Generate `Packages` first, then generate `Packages.gz` from those exact bytes using deterministic gzip settings.
3. Generate `Release` only after all indexes are final; compute every advertised size and digest from the staged files.
4. Generate both `InRelease` and `Release.gpg` from that exact staged `Release` file. Treat either signing failure as fatal.
5. Verify both signatures immediately using the expected public key/fingerprint before the staged files can replace the repository files.
6. Publish the complete staged set together. Do not copy individual files into the live tree one at a time while a web server/deployment can observe a mixed state. For GitHub Pages, commit the complete generated set as one commit and deploy that commit as one unit.
7. Remove or update any legacy generator path that can change `Packages`/ `Release` without re-signing. In particular, audit retention regeneration because it currently updates index files and `Release` checksum sections separately from signing.
8. Ensure each workflow checks out the latest branch state before writing and handles non-fast-forward/conflict outcomes by failing and retrying from a fresh checkout rather than force-pushing stale state.

**Acceptance criteria:** every generation path creates the same coherent set of artifacts; no path can update indexes or `Release` while leaving signatures stale.

## 5. Phase 3 — Serialize Writers and Fix Workflow Ordering

Audit `.github/workflows/ingest-deb.yml`, `.github/workflows/package-retention.yml`, and `.github/workflows/ci-validation.yml`, plus the GitHub Pages build/deploy configuration.

1. Add a shared GitHub Actions concurrency group for all workflows that mutate the repository's package pool, indexes, signatures, or deployment source. Choose a policy that queues repository writes rather than cancelling a running publication halfway through.
2. Ensure ingestion and retention cannot run concurrently against the same `main` tree.
3. Make publication ordering explicit:
   - checkout latest base;
   - ingest or prune package files;
   - regenerate indexes and release metadata;
   - sign;
   - validate all repository contents and signatures;
   - commit the complete set;
   - deploy only the validated commit;
   - verify the live endpoint.
4. Configure Pages deployment to depend on successful validation of the exact commit being deployed. A failed integrity job must block deployment.
5. Avoid a second workflow deploying the same commit independently of the validation gate. If Pages deployment is automatically triggered on every push, restructure the source branch/workflow so unvalidated commits cannot be published.
6. Make the publishing workflow fail closed if validation, signing, commit, or deployment verification fails.

**Acceptance criteria:** there is one serialized write/deploy path and no Pages deployment can succeed for a commit whose integrity validation failed.

## 6. Phase 4 — Strengthen Repository Integrity Tests

Extend `scripts/validate_repository.py` and CI tests to check:

- The SHA-256, SHA-512, and byte sizes in `Release` match both index files.
- Decompressing `Packages.gz` produces byte-for-byte identical contents to `Packages`.
- `InRelease` signature validates against the expected public key.
- `Release.gpg` validates against the same exact `Release` bytes.
- All required files exist and are included in the same generated commit.
- Every package index entry corresponds to a real package in the pool, and no unintended pool packages are omitted.
- The generated release metadata is internally consistent after normal ingestion, index-only regeneration, and retention/pruning.
- Negative tests deliberately corrupt one index, one checksum, and each signature in turn; validation must fail every time.
- A clean-container bootstrap/install test runs only after repository integrity checks pass, and a failed prerequisite is reported as blocked rather than silently skipped.

**Acceptance criteria:** CI fails for the exact class of size/hash mismatch and detached-signature failure observed here, and tests cover every supported metadata-generation path.

## 7. Phase 5 — Add Post-Deployment Verification

After the validated commit is deployed to GitHub Pages:

1. Fetch `InRelease`, `Release`, `Release.gpg`, `Packages`, and `Packages.gz` from the public endpoint with retries and a bounded timeout.
2. Verify the signature on the fetched `InRelease` and `Release.gpg` using the public key.
3. Parse the fetched `InRelease` checksum tables and compare downloaded index sizes and hashes to the advertised values.
4. Decompress fetched `Packages.gz` and compare it byte-for-byte with fetched `Packages`.
5. Compare the deployed file hashes with the validated commit's expected hashes. Report cache/deployment mismatch distinctly from a bad committed repository.
6. If any check fails, mark the workflow failed, block subsequent releases where possible, and provide the mismatched path, expected hash/size, actual hash/size, commit SHA, and URL in the log.
7. Use a few bounded retries for propagation delay; retries must never turn a persistent integrity mismatch into success.

**Acceptance criteria:** a deployment is considered complete only after the public repository passes cryptographic and index-integrity checks.

## 8. Phase 6 — Repair the Currently Published Repository

Once the workflow changes are implemented and tested:

1. Use the current package pool as the source of truth; do not trust the currently committed indexes.
2. Regenerate all package indexes and release metadata from the pool using the authoritative generator.
3. Sign the regenerated `Release` with the existing verified key and verify both signature formats before committing.
4. Run the complete strict validator locally and in CI.
5. Deploy only the validated commit.
6. Run post-deployment checks against the public GitHub Pages endpoint.
7. On the Linux Mint server, run:
   ```bash
   sudo apt clean
   sudo rm -rf /var/lib/apt/lists/partial/*
   sudo apt update
   ```
8. Confirm that APT fetches the expected index without `File has unexpected size` and that the repository is listed without signature or hash warnings.

**Acceptance criteria:** clean APT update succeeds on the affected server and a fresh client, with all signature and hash checks enabled.

## 9. Recommended Implementation Order

1. Reproduce and record the current failure.
2. Fix the index/signature generation path and remove unsafe alternate writers.
3. Add negative and full-path validation tests.
4. Serialize mutating workflows and make deployment depend on validation.
5. Add public-endpoint post-deployment verification.
6. Regenerate, validate, and deploy a clean repository state.
7. Verify from the affected server and document the recovery.

## 10. Definition of Done

- [ ] The five repository metadata artifacts are generated from one consistent staged state.
- [ ] Both signature types verify against the exact same `Release` content.
- [ ] All package index hashes and sizes match the signed metadata.
- [ ] Ingestion, retention, and manual regeneration use the same safe generation path.
- [ ] Repository writers are serialized.
- [ ] Pages cannot deploy an unvalidated commit.
- [ ] CI includes corruption/negative tests for hashes and signatures.
- [ ] Post-deployment validation checks the actual public endpoint.
- [ ] The current repository is regenerated and published successfully.
- [ ] `sudo apt update` succeeds on the affected Linux Mint server with security checks enabled.
