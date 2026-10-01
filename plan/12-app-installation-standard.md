# Phase 12 - App Installation Standard

> **Phase**: Phase 12 — App Installation Standard  
> **Status**: Completed  
> **Deliverable Document**: [`docs/12-app-installation-standard.md`](file:///home/m3tal/apps/M3tal-Hub/docs/packaging/12-app-installation-standard.md)  
> **Reference Standard**: Universal APT Package Architecture (`sudo apt install m3tal-<app>`)  
> **Test Suite**: [`scripts/verify_track5_packaging_and_hub.py`](file:///home/m3tal/apps/M3tal-Hub/scripts/verify_track5_packaging_and_hub.py)

## Goal
Give every M3tal Linux application one consistent installation experience.

## Standard
Install the repository once, then use APT:

`sudo apt install m3tal-<app>`

## Tasks Executed
- [x] Define package naming (`m3tal-<app-name>` in lowercase alphanumeric with hyphens; `m3tal` virtual `m3tal-core`).
- [x] Define application dependencies (3 architectural tiers: Standalone CLI, Ecosystem Services `Depends: m3tal`, Desktop GUI `Recommends: m3tal`).
- [x] Define desktop integration where applicable (`.desktop` spec under `/usr/share/applications/`, hicolor icons, update cache hooks).
- [x] Define configuration locations (`/etc/m3tal/<app>/`, `~/.config/m3tal/<app>/`, `/var/lib/m3tal/<app>/`).
- [x] Define upgrade behavior (conffiles preservation, idempotent scripts, systemd service reloads).
- [x] Define uninstall behavior (remove leaves config and state intact; purge cleans `/etc/m3tal/<app>` and `/var/lib/m3tal/<app>`).
- [x] Define application documentation requirements (copyright format 1.0, changelog.Debian.gz, man pages in `/usr/share/man/man1/`).
- [x] Remove project-specific installation workarounds where possible (standardize on APT packages instead of curl-piping or manual builds).

## Deliverables
- `docs/12-app-installation-standard.md`: Comprehensive Debian packaging specification defining package naming, dependency taxonomy, FHS filesystem layout, desktop integration, service unit templates, and lifecycle scripts.

## Completion Criteria Verification
- **Every supported M3tal Linux application follows the same installation model**: Standard codified in documentation, catalog mapping table defined across all ecosystem components, and verification suite validated.
