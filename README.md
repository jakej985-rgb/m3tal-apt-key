# M3tal APT Repository Workspace (`m3tal-apt-key`)

This workspace coordinates execution tracks for the unified M3tal Debian/Ubuntu APT package repository.

---

## Tracks & Deliverables Index

### Track 3: Package Publishing, Metadata & Versioning (Phases 06, 07, 08)
- `scripts/deb_version.py`: Debian version parsing, comparison, and semantic version validation.
- `scripts/validate_package.py`: Automated Debian package metadata and dependency validation.
- `templates/control.template`: Canonical `DEBIAN/control` metadata template.

### Track 6: Documentation, Security & End-to-End Validation (Phases 14, 15, 16)
- **Phase 14 (Documentation)**:
  - [`docs/README-repository.md`](docs/README-repository.md): Complete repository README and user introduction.
  - [`docs/user-setup-guide.md`](docs/user-setup-guide.md): In-depth workstation, server, and IaC installation guide.
  - [`docs/maintenance-guide.md`](docs/maintenance-guide.md): Repository operations, package ingestion, and signing workflows.
  - [`docs/developer-guide.md`](docs/developer-guide.md): Packaging standards for M3tal application developers.
- **Phase 15 (Security & Key Rotation)**:
  - [`docs/security-and-key-rotation.md`](docs/security-and-key-rotation.md): Security architecture, private key protection, routine rotation schedules, and emergency revocation procedures.
- **Phase 16 (End-to-End Validation)**:
  - [`scripts/test_e2e_validation.py`](scripts/test_e2e_validation.py): Automated 13-step lifecycle test suite (bootstrap, GPG verification, apt update, install, upgrade, remove, idempotency).
  - [`docs/e2e-validation-report.md`](docs/e2e-validation-report.md): Execution records and multi-distribution audit report.
