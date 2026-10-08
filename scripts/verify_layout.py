#!/usr/bin/env python3
"""
M3tal Repository Layout Verification Suite (Phase 04)
Validates compliance with Debian repository layout standards:
  - dists/ hierarchy (dists/stable/main/binary-amd64)
  - pool/ structure and backward compatibility preservation
  - keys/ trust material and fingerprint validation
  - scripts/ tooling separation
  - docs/ specifications
  - registry/ metadata directory
  - Permissions and clean separation of concerns
"""

import os
import sys
import hashlib
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTED_FINGERPRINT = "5F84FE50A40111C981410E11775AD1473BF25102"

def check(condition, message):
    if not condition:
        print(f"    [FAIL] {message}")
        sys.exit(1)
    print(f"    [OK] {message}")

def verify_directory_tree():
    print("--> 1. Verifying target directory layout...")
    required_dirs = [
        "dists/stable",
        "dists/stable/main",
        "dists/stable/main/binary-amd64",
        "pool/main",
        "keys",
        "scripts",
        "docs",
        "registry",
    ]
    for d in required_dirs:
        p = os.path.join(REPO_ROOT, d)
        check(os.path.isdir(p), f"Directory exists: {d}")

def verify_metadata_files():
    print("--> 2. Verifying APT distribution metadata...")
    required_meta = [
        "dists/stable/Release",
        "dists/stable/Release.gpg",
        "dists/stable/InRelease",
        "dists/stable/main/binary-amd64/Packages",
        "dists/stable/main/binary-amd64/Packages.gz",
    ]
    for m in required_meta:
        p = os.path.join(REPO_ROOT, m)
        check(os.path.isfile(p) and os.path.getsize(p) > 0, f"Metadata file exists: {m}")

def verify_keys_layout():
    print("--> 3. Verifying key storage and fingerprint...")
    keyring_bin = os.path.join(REPO_ROOT, "keys", "m3tal-archive-keyring.gpg")
    keyring_asc = os.path.join(REPO_ROOT, "keys", "m3tal-archive-keyring.asc")
    keys_readme = os.path.join(REPO_ROOT, "keys", "README.md")

    check(os.path.isfile(keyring_bin), "Binary keyring keys/m3tal-archive-keyring.gpg exists")
    check(os.path.isfile(keyring_asc), "Armored key keys/m3tal-archive-keyring.asc exists")
    check(os.path.isfile(keys_readme), "Documentation keys/README.md exists")

    # Verify fingerprint of key in keys/
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_gnupg:
        res = subprocess.run(
            f"GNUPGHOME='{tmp_gnupg}' gpg --show-keys '{keyring_bin}'",
            shell=True,
            capture_output=True,
            text=True
        )
    check(EXPECTED_FINGERPRINT in res.stdout, f"Keyring has expected fingerprint {EXPECTED_FINGERPRINT}")

    # Verify root backward compatibility files
    check(os.path.isfile(os.path.join(REPO_ROOT, "public.key")), "Root public.key preserved for legacy tooling")
    check(os.path.isfile(os.path.join(REPO_ROOT, "KEY.gpg")), "Root KEY.gpg preserved for legacy tooling")

def verify_tooling_and_docs_separation():
    print("--> 4. Verifying separation of tooling, docs, and pool...")
    pool_main = os.path.join(REPO_ROOT, "pool", "main")
    for fname in os.listdir(pool_main):
        if not fname.endswith(".deb"):
            continue
        p = os.path.join(pool_main, fname)
        check(not os.path.islink(p) or os.path.exists(p), f"Package archive accessible: {fname}")

    # Ensure no binary packages are stored in scripts/ or docs/
    for sub in ["scripts", "docs", "registry"]:
        p = os.path.join(REPO_ROOT, sub)
        for root, dirs, files in os.walk(p):
            for f in files:
                check(not f.endswith(".deb"), f"No package binaries stored in {sub}: {f}")

    # Check that documentation is present
    check(os.path.isfile(os.path.join(REPO_ROOT, "docs", "universal-bootstrap.md")), "docs/universal-bootstrap.md exists")

def main():
    print("==================================================")
    print(" M3tal Repository Layout Verification Suite       ")
    print("==================================================")
    verify_directory_tree()
    verify_metadata_files()
    verify_keys_layout()
    verify_tooling_and_docs_separation()
    print("==================================================")
    print(" ✅ Repository Layout verification PASSED!")
    print("==================================================")

if __name__ == "__main__":
    main()
