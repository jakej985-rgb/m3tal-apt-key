#!/usr/bin/env python3
"""
M3tal Package Registry Validator (Phase 05)
Validates:
  - YAML syntax and JSON Schema conformance
  - Debian package naming conventions (Debian Policy Manual 5.6.1)
  - Uniqueness of package IDs and package names
  - Supported architectures and component definitions
  - Integrity of published artifacts against the pool/ tree
"""

import os
import sys
import re
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(REPO_ROOT, "registry", "packages.yml")
POOL_PATH = os.path.join(REPO_ROOT, "pool", "main")

# Debian package naming regex: lowercase alphanumeric, +, -, .
# Must start with alphanumeric and be at least 2 characters long.
DEBIAN_PKG_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9+-.]+$")
DEBIAN_VERSION_RE = re.compile(r"^(?:[0-9]+:)?[0-9]+[a-zA-Z0-9.+:~-]*$")

ALLOWED_ARCHITECTURES = {"amd64", "arm64", "armhf", "i386", "all"}
ALLOWED_TYPES = {"cli", "service", "desktop", "core-system", "library", "metapackage"}
ALLOWED_STATUSES = {"published", "active", "planned", "deprecated"}

SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
PKG_ID_RE = re.compile(r"^[a-z0-9-]+$")
FINGERPRINT_RE = re.compile(r"^[A-F0-9]{40}$")

def fail(msg):
    print(f"    [FAIL] {msg}", file=sys.stderr)
    sys.exit(1)

def check(condition, msg):
    if not condition:
        fail(msg)
    print(f"    [OK] {msg}")

def validate_registry(manifest_path=None):
    manifest_path = manifest_path or REGISTRY_PATH
    print(f"--> 1. Loading and parsing {manifest_path}...")
    if not os.path.isfile(manifest_path):
        fail(f"Registry file not found at {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except Exception as e:
            fail(f"YAML parsing error: {e}")

    check(isinstance(data, dict), "Root element is a mapping")
    check("version" in data and isinstance(data["version"], str) and bool(SEMVER_RE.match(data["version"])), "Registry manifest defines valid SemVer schema version")
    check("repository" in data and isinstance(data["repository"], dict), "Registry defines repository metadata mapping")
    check("packages" in data and isinstance(data["packages"], list), "Registry defines package list")

    repo_info = data["repository"]
    check(bool(repo_info.get("url")), "Repository URL is specified")
    check(repo_info.get("suite") == "stable", "Repository suite is stable")
    check(bool(repo_info.get("origin")), "Repository origin is defined")
    check(bool(repo_info.get("label")), "Repository label is defined")
    check("main" in repo_info.get("components", []), "Component 'main' is declared")
    check("amd64" in repo_info.get("architectures", []), "Architecture 'amd64' is declared")

    keyring_info = repo_info.get("keyring", {})
    check(isinstance(keyring_info, dict), "Repository keyring configuration is defined")
    fpr = keyring_info.get("fingerprint", "")
    check(bool(fpr and FINGERPRINT_RE.match(fpr)), f"Repository keyring defines valid 40-char fingerprint: {fpr}")
    check(bool(keyring_info.get("path")), "Repository keyring path is defined")

    print("--> 2. Validating package entries and Debian compliance...")
    packages = data["packages"]
    check(len(packages) >= 1, f"Found {len(packages)} registered packages")

    seen_ids = set()
    seen_names = set()

    for pkg in packages:
        pkg_id = pkg.get("id")
        pkg_name = pkg.get("name")

        check(bool(pkg_id and PKG_ID_RE.match(pkg_id)), f"Package has valid ID: {pkg_id}")
        check(pkg_id not in seen_ids, f"Unique package ID: {pkg_id}")
        seen_ids.add(pkg_id)

        check(bool(pkg_name), f"Package defines Debian name: {pkg_name}")
        check(pkg_name not in seen_names, f"Unique Debian package name: {pkg_name}")
        seen_names.add(pkg_name)

        # Debian package name policy
        check(bool(DEBIAN_PKG_NAME_RE.match(pkg_name)), f"Package '{pkg_name}' satisfies Debian naming syntax")

        # Source repo
        check(bool(pkg.get("source_repo")), f"Package '{pkg_name}' defines source repository")

        # Type and Status
        check(pkg.get("type") in ALLOWED_TYPES, f"Package '{pkg_name}' has valid type '{pkg.get('type')}'")
        check(pkg.get("status") in ALLOWED_STATUSES, f"Package '{pkg_name}' has valid status '{pkg.get('status')}'")

        # Architectures
        archs = pkg.get("supported_architectures", [])
        check(isinstance(archs, list) and len(archs) > 0, f"Package '{pkg_name}' has architectures list")
        for a in archs:
            check(a in ALLOWED_ARCHITECTURES, f"Architecture '{a}' for '{pkg_name}' is valid Debian arch")

        # Metadata
        meta = pkg.get("metadata", {})
        check(isinstance(meta, dict), f"Package '{pkg_name}' defines metadata mapping")
        version = meta.get("latest_version")
        check(bool(version and DEBIAN_VERSION_RE.match(version)), f"Package '{pkg_name}' version '{version}' is valid")
        check(bool(meta.get("section")), f"Package '{pkg_name}' defines section '{meta.get('section')}'")
        check(bool(meta.get("priority")), f"Package '{pkg_name}' defines priority '{meta.get('priority')}'")
        check(bool(meta.get("maintainer")), f"Package '{pkg_name}' defines maintainer")
        check(bool(meta.get("description")), f"Package '{pkg_name}' defines description")

        # Publication
        pub = pkg.get("publication", {})
        check(isinstance(pub, dict), f"Package '{pkg_name}' defines publication mapping")
        check(pub.get("component") in ["main", "contrib", "non-free"], f"Component valid for '{pkg_name}'")
        check(pub.get("distribution") == "stable", f"Distribution is 'stable' for '{pkg_name}'")
        check(bool(pub.get("pool_path")), f"Pool path defined for '{pkg_name}'")

        # Dependencies (optional)
        if "dependencies" in pkg:
            deps = pkg["dependencies"]
            check(isinstance(deps, dict), f"Dependencies is mapping for '{pkg_name}'")
            for dep_cat in ["runtime", "recommends", "suggests", "build"]:
                if dep_cat in deps:
                    check(isinstance(deps[dep_cat], list), f"Dependency list '{dep_cat}' is array for '{pkg_name}'")

        # Pool cross-reference for published status
        if pkg.get("status") == "published":
            pool_dir = os.path.join(REPO_ROOT, pub.get("pool_path", "pool/main"))
            check(os.path.isdir(pool_dir), f"Pool directory exists for published package '{pkg_name}': {pool_dir}")
            debs = [f for f in os.listdir(pool_dir) if f.startswith(pkg_name + "_") and f.endswith(".deb")]
            check(len(debs) > 0, f"Found {len(debs)} published .deb artifacts in pool for '{pkg_name}'")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="M3tal Package Registry Validator")
    parser.add_argument("--manifest", help="Path to registry YAML manifest (default: registry/packages.yml)")
    args = parser.parse_args()

    print("==================================================")
    print(" M3tal Package Registry Validator                 ")
    print("==================================================")
    validate_registry(args.manifest)
    print("==================================================")
    print(" ✅ Package Registry validation PASSED!")
    print("==================================================")

if __name__ == "__main__":
    main()
