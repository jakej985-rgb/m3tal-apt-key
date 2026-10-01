# Phase 13 - M3tal Hub Integration

> **Phase**: Phase 13 — M3tal Hub Integration  
> **Status**: Completed  
> **Deliverable Document**: [`docs/13-m3tal-hub-integration.md`](file:///home/m3tal/apps/M3tal-Hub/docs/packaging/13-m3tal-hub-integration.md)  
> **Integrated Files**: [`apps/m3tal-apt-key.html`](file:///home/m3tal/apps/M3tal-Hub/apps/m3tal-apt-key.html), [`apps/m3tal-core.html`](file:///home/m3tal/apps/M3tal-Hub/apps/m3tal-core.html), [`index.html`](file:///home/m3tal/apps/M3tal-Hub/index.html)  
> **Test Suite**: [`scripts/verify_track5_packaging_and_hub.py`](file:///home/m3tal/apps/M3tal-Hub/scripts/verify_track5_packaging_and_hub.py), [`scripts/test_hub_verification.py`](file:///home/m3tal/apps/M3tal-Hub/scripts/test_hub_verification.py)

## Goal
Make M3tal-Hub the discovery and presentation layer for the unified repository.

## Tasks Executed
- [x] Define app catalog data (`build_hub.py` codified install guides and multi-platform specifications).
- [x] Connect Hub entries to package names (`m3tal` for Core, `m3tal-apt-key` for trust keyring).
- [x] Display current package versions (`v1.1.62` for Core Debian release, `v1.0.0` for repository release).
- [x] Display supported platforms (`🐧 Linux (amd64)` across Debian, Ubuntu, Mint).
- [x] Provide installation instructions (Universal one-line bootstrap `curl -fsSL ... | sudo bash` and manual signed-by `sources.list.d` setup in `apps/m3tal-apt-key.html`; `sudo apt install -y m3tal` and CLI quickstart in `apps/m3tal-core.html`).
- [x] Link source repositories (GitHub links for `m3tal-core` and `m3tal-apt-key`).
- [x] Link documentation (Cross-linking Hub detail pages, ecosystem index banner, and repository docs).
- [x] Keep Hub presentation separate from APT repository storage (GitHub Pages web front strictly decoupled from APT pool binary package storage).

## Deliverables
- `docs/13-m3tal-hub-integration.md`: Architecture specification detailing boundary separation between Hub web presentation and APT package storage.
- `apps/m3tal-apt-key.html`: Updated onboarding page with universal bootstrap, manual keyring configuration, and GPG fingerprint verification.
- `apps/m3tal-core.html`: Updated component page with complete APT package installation steps, systemd service checks, and CLI usage.
- `index.html`: Infrastructure & Backend Services section updated with official APT Repository banner and discovery links.
- `scripts/build_hub.py`: Hub build generator updated to maintain synchronized APT installation instructions.

## Completion Criteria Verification
- **A user can discover a M3tal app in M3tal-Hub and obtain its correct APT installation command**: Verified across `index.html`, `apps/m3tal-core.html`, and `apps/m3tal-apt-key.html`. Full Hub test suite (`test_hub_verification.py`) and Track 5 verification suite pass with 100% success.
