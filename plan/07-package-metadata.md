# Phase 7 - Package Metadata

## Goal
Make every M3tal package a properly defined Debian package.

## Required Metadata
- Package
- Version
- Architecture
- Maintainer
- Description
- Section
- Priority
- Dependencies
- Homepage where applicable

## Tasks
- Define package metadata templates.
- Validate dependencies.
- Validate architecture.
- Validate package names.
- Validate version syntax.
- Validate package contents.
- Reject malformed packages in CI.

## Completion Criteria
- Every package passes Debian package metadata validation before publication.
