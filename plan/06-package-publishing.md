# Phase 6 - Package Publishing

> **Phase**: Phase 06 — Package Publishing  
> **Status**: Completed  
> **Deliverable Document**: [`docs/publishing-spec.md`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/docs/publishing-spec.md)  
> **Publishing Tool**: [`scripts/publish_package.py`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/scripts/publish_package.py)  
> **Test Suite**: [`tests/test_track3.py`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/tests/test_track3.py)

## Goal
Automate publication of packages from individual M3tal projects into the unified repository.

## Tasks Executed
- [x] Define the package publication workflow (`docs/publishing-spec.md`).
- [x] Build automated publication and pool management engine (`scripts/publish_package.py`).
- [x] Validate package metadata before accepting packages (`validate_package.py`).
- [x] Publish approved artifacts into canonical pool paths (`pool/main/<package>/` with fallback to flat pool).
- [x] Place artifacts with normalized Debian naming (`<package>_<version>_<arch>.deb`).
- [x] Regenerate APT indexes (`Packages`, `Packages.gz` with deterministic `mtime=0`).
- [x] Regenerate Release metadata with byte sizes and full checksum blocks (`MD5Sum`, `SHA1`, `SHA256`, `SHA512`).
- [x] Sign repository metadata (`InRelease` via clearsign, `Release.gpg` via detached armor).
- [x] Publish changes atomically using temporary staging directories.
- [x] Prevent duplicate or invalid package versions with pre-publish guardrails (`--allow-replace`, `--allow-downgrade`).

## Deliverables
- `docs/publishing-spec.md`: Complete architectural and operational specification for automated debian package publication.
- `scripts/publish_package.py`: Automated CLI publishing tool supporting single/batch deb ingestion, pool organization, index creation, Release descriptors, GPG signing, and atomic staging.
- `tests/test_track3.py`: Full end-to-end integration test suite verifying deb building, publishing, index generation, duplicate rejections, and cryptographic GPG signing/verification.

## Completion Criteria Verification
- **A project can publish a valid package without manual file copying**: Verified via automated `publish_deb` invocation which places files, generates all indexes, and creates release descriptors.
- **A published package becomes available through APT after repository synchronization**: Verified via test repository synthesis and clean Debian APT container policy resolution.
