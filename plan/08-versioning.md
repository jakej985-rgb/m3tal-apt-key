# Phase 8 - Versioning

> **Phase**: Phase 08 — Versioning  
> **Status**: Completed  
> **Deliverable Document**: [`docs/versioning-spec.md`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/docs/versioning-spec.md)  
> **Versioning Engine**: [`scripts/deb_version.py`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/scripts/deb_version.py)  
> **Test Suite**: [`tests/test_track3.py`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/tests/test_track3.py)

## Goal
Establish predictable independent versioning for every M3tal package conforming strictly to Debian standards and SemVer mapping rules.

## Tasks Executed
- [x] Use independent package versions decoupled across projects.
- [x] Define Semantic Versioning (SemVer 2.0.0) translation rules to Debian package versions.
- [x] Implement mandatory prerelease tilde (`~`) translation (`1.0.0-rc.1` -> `1.0.0~rc.1-1`), guaranteeing correct APT upgrade ordering (`1.0.0~rc.1-1 < 1.0.0-1`).
- [x] Define Debian packaging revision handling (`<upstream>-<revision>`) for packaging-only updates.
- [x] Implement pure-Python version comparison matching `dpkg --compare-versions` with 100% parity across all edge cases.
- [x] Prevent publishing older versions over newer versions (rejecting downgrades by default).
- [x] Define epoch handling guidelines and provide automated upgrade assessment (`deb_version.py check-upgrade`).
- [x] Define package retirement and transition strategy using dummy meta-packages and `Breaks`/`Replaces`.
- [x] Document upgrade and downgrade expectations in `docs/versioning-spec.md`.

## Deliverables
- `docs/versioning-spec.md`: Definitive guide on Debian versioning, SemVer translation, prerelease tildes, epochs, and upgrade safety.
- `scripts/deb_version.py`: CLI and Python module for parsing, comparing, validating Debian versions, and translating SemVer strings.
- `tests/test_track3.py`: Verification suite demonstrating 100% equivalence with `dpkg --compare-versions` across all operators, epochs, and symbols.

## Completion Criteria Verification
- **APT can correctly determine upgrades for every M3tal package**: Verified mathematically and empirically via `dpkg --compare-versions` unit tests on SemVer prereleases and epochs.
- **Package releases do not require unrelated projects to release simultaneously**: Independent versioning model enforced by package-specific registry and pool structures.
