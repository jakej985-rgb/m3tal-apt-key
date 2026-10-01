# Phase 7 - Package Metadata

> **Phase**: Phase 07 — Package Metadata  
> **Status**: Completed  
> **Deliverable Document**: [`docs/package-metadata-standard.md`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/docs/package-metadata-standard.md)  
> **Canonical Template**: [`templates/control.template`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/templates/control.template)  
> **Validation Tool**: [`scripts/validate_package.py`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/scripts/validate_package.py)  
> **Test Suite**: [`tests/test_track3.py`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/tests/test_track3.py)

## Goal
Make every M3tal package a properly defined Debian package conforming strictly to Debian Policy standards.

## Required Metadata Fields
- **Package**: Lowercase alphanumerics and symbols (`+`, `-`, `.`), >= 2 chars, starting with alphanumeric.
- **Version**: Conforming to Debian Policy §5.6.12 (`[epoch:]upstream[-revision]`).
- **Architecture**: `amd64`, `arm64`, or `all`.
- **Maintainer**: Standard RFC 822 format (`Full Name <email@domain>`).
- **Description**: Concise synopsis line followed by indented body lines.
- **Section**: Standard Debian category (`utils`, `admin`, `net`, `devel`, etc.).
- **Priority**: Standard package priority (`optional`).
- **Dependencies**: Validated syntax for `Depends`, `Recommends`, `Suggests`, `Conflicts`, `Breaks`, `Replaces`.
- **Homepage**: Validated HTTP/HTTPS URL where applicable.

## Tasks Executed
- [x] Define package metadata templates (`templates/control.template`).
- [x] Implement dependency parser and validator supporting conjunctions and alternatives (`parse_dependency_field`).
- [x] Implement architecture validator supporting multi-architecture ecosystems (`amd64`, `arm64`, `all`).
- [x] Implement package name validator adhering to Debian naming standards.
- [x] Implement version syntax validator adhering to Debian Policy §5.6.12.
- [x] Implement package archive inspector checking AR headers, `debian-binary` 2.0, `control.tar.*`, and maintainer script shebangs.
- [x] Reject malformed packages in CI with non-zero exit codes and clear actionable diagnostics.

## Deliverables
- `docs/package-metadata-standard.md`: Comprehensive specification for Debian control fields, formatting rules, dependency relations, and lifecycle scripts.
- `templates/control.template`: Canonical template for packaging M3tal ecosystem software.
- `scripts/validate_package.py`: CLI tool for validating Debian `.deb` packages and `control` files before publication.
- `tests/test_track3.py`: Automated tests verifying control field validation, invalid format rejection, and dependency parsing.

## Completion Criteria Verification
- **Every package passes Debian package metadata validation before publication**: Verified against real repository debian packages (`m3tal_v1.0.0_amd64.deb`, `m3tal_v1.1.62_amd64.deb`, etc.) and synthetic test packages.
