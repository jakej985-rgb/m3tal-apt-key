# Phase 11 - M3tal Core

## Goal
Establish `m3tal-core` as the shared foundation package for the M3tal application ecosystem.

## Tasks
- Define the responsibilities of `m3tal-core`.
- Keep repository/bootstrap functionality independent from the package.
- Define shared CLI and runtime functionality.
- Define common configuration and paths.
- Define upgrade behavior.
- Define dependency expectations for M3tal applications.
- Ensure core does not create an APT bootstrap dependency loop.

## Completion Criteria
- M3tal applications can depend on `m3tal-core` consistently.
- Repository installation remains possible without `m3tal-core`.
