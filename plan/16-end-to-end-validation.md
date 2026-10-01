# Phase 16 - End To End Validation

## Goal
Prove the unified M3tal repository works from a clean supported system.

## Test
1. Start with a clean Debian/Ubuntu environment.
2. Run the official repository bootstrap.
3. Verify the M3tal keyring.
4. Run `apt update`.
5. Search for M3tal packages.
6. Install `m3tal-core`.
7. Install a second M3tal application.
8. Upgrade packages.
9. Remove an application.
10. Reinstall the application.
11. Verify signatures and checksums.
12. Confirm no duplicate repository entries are created.
13. Confirm package dependencies resolve correctly.

## Completion Criteria
- Clean installation succeeds.
- Package installation succeeds.
- Package upgrades succeed.
- Package removal succeeds.
- Repository signatures validate.
- CI validation passes.
- The unified repository is ready for M3tal-Hub integration.
