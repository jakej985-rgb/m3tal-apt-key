# Phase 11 - M3tal Core

> **Phase**: Phase 11 — M3tal Core  
> **Status**: Completed  
> **Deliverable Document**: [`docs/11-m3tal-core-spec.md`](file:///home/m3tal/apps/M3tal-Hub/docs/packaging/11-m3tal-core-spec.md)  
> **Reference Package**: `pool/main/m3tal_v1.1.62_amd64.deb` (`m3tal` v1.1.62 amd64)  
> **Test Suite**: [`scripts/verify_track5_packaging_and_hub.py`](file:///home/m3tal/apps/M3tal-Hub/scripts/verify_track5_packaging_and_hub.py)

## Goal
Establish `m3tal-core` as the shared foundation package for the M3tal application ecosystem.

## Tasks Executed
- [x] Define the responsibilities of `m3tal-core` (CLI orchestrator `/usr/bin/m3tal`, API daemon `/usr/bin/m3tal-api`, systemd services, shared groups, Traefik dynamic stack).
- [x] Keep repository/bootstrap functionality independent from the package (no cyclic bootstrap dependency; repository can be added without `m3tal` installed).
- [x] Define shared CLI and runtime functionality (`m3tal init`, `m3tal daemon`, `m3tal help`, Control Center).
- [x] Define common configuration and paths (`/etc/m3tal/.env`, `/var/lib/m3tal/`, `/var/log/m3tal/`, `/opt/m3tal/stack/`, `/docker` symlink).
- [x] Define upgrade behavior (conffiles preservation, no-clobber template copying `cp -rn`, daemon-reload and service restart).
- [x] Define dependency expectations for M3tal applications (Tight `Depends: m3tal`, Modular `Recommends: m3tal`, Standalone independent).
- [x] Ensure core does not create an APT bootstrap dependency loop (verified via clean container testing).

## Deliverables
- `docs/11-m3tal-core-spec.md`: Complete specification of `m3tal-core` Debian package architecture, control metadata, payload, systemd units, filesystem layout, maintainer hooks, and dependency contracts.
- `scripts/verify_track5_packaging_and_hub.py`: Automated verification suite validating `m3tal_v1.1.62_amd64.deb`, binaries, hooks, and service units.

## Completion Criteria Verification
- **M3tal applications can depend on `m3tal-core` consistently**: Verified via standardized dependency tiers and shared group/path contracts documented in specification.
- **Repository installation remains possible without `m3tal-core`**: Verified via clean container test where repository was bootstrapped and queried without installing `m3tal`.
