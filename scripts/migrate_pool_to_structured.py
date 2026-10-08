#!/usr/bin/env python3
"""
M3tal APT Pool Migration Tool: Flat to Structured Hierarchy
Scans pool/main/ for any top-level .deb packages and organizes them
into dedicated per-application subdirectories: pool/main/<package-name>/
"""

import os
import sys
import shutil
import argparse
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

SCRIPT_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from validate_package import extract_control_from_deb
from publish_package import AptPublisher

POOL_DIR = os.path.join(REPO_ROOT, "pool", "main")


def migrate_pool(dry_run: bool = False, sign: bool = False, passphrase: str = None) -> int:
    if not os.path.isdir(POOL_DIR):
        print(f"Pool directory not found: {POOL_DIR}")
        return 1

    # Find flat .deb files in pool/main/
    flat_debs = []
    for item in sorted(os.listdir(POOL_DIR)):
        full_path = os.path.join(POOL_DIR, item)
        if os.path.isfile(full_path) and item.endswith(".deb"):
            flat_debs.append(full_path)

    if not flat_debs:
        print("--> Pool is already fully structured! Zero flat deb files found.")
        return 0

    print(f"--> Found {len(flat_debs)} packages in flat pool/main/ to organize.")

    moved_count = 0
    for deb_path in flat_debs:
        try:
            fields, _ = extract_control_from_deb(deb_path)
            pkg_name = fields.get("Package", "m3tal")
        except Exception:
            pkg_name = "m3tal"

        target_dir = os.path.join(POOL_DIR, pkg_name)
        target_path = os.path.join(target_dir, os.path.basename(deb_path))

        if dry_run:
            print(f"  [DRY-RUN] Would move {os.path.basename(deb_path)} -> pool/main/{pkg_name}/")
        else:
            os.makedirs(target_dir, exist_ok=True)
            shutil.move(deb_path, target_path)
            moved_count += 1

    if dry_run:
        print(f"--> [DRY-RUN] Evaluation complete. {len(flat_debs)} packages would be organized.")
        return 0

    print(f"--> Successfully moved {moved_count} packages into structured directories.")

    # Regenerate indexes
    print("--> Regenerating Packages, Packages.gz, and Release indices...")
    publisher = AptPublisher(
        repo_dir=REPO_ROOT,
        suite="stable",
        component="main",
        origin="M3TAL",
        label="M3TAL",
        description="M3TAL Central Ecosystem APT Repository",
        pool_style="structured",
    )

    try:
        info = publisher.generate_indexes(
            gpg_passphrase=passphrase,
            sign=sign,
        )
        print(f"--> Indices regenerated successfully! ({info['package_count']} packages indexed).")
        if sign:
            print("--> Cryptographically signed Release indices with GPG.")
    except Exception as e:
        print(f"--> Note: Index regeneration with signing: {e}")
        info = publisher.generate_indexes(sign=False)
        print(f"--> Indices regenerated without signature ({info['package_count']} packages indexed).")

    return 0


def main():
    parser = argparse.ArgumentParser(description="Migrate flat pool packages into structured per-app folders")
    parser.add_argument("--dry-run", action="store_true", help="Simulate moves without changing disk")
    parser.add_argument("--execute", action="store_true", help="Execute the migration")
    parser.add_argument("--sign", action="store_true", help="Sign the Release manifest with GPG")
    parser.add_argument("--passphrase", help="GPG signing key passphrase")
    args = parser.parse_args()

    if not args.execute and not args.dry_run:
        print("Please specify either --dry-run or --execute.")
        sys.exit(1)

    passphrase = args.passphrase or os.environ.get("APT_GPG_PASSPHRASE") or os.environ.get("GPG_PASSPHRASE")
    sys.exit(migrate_pool(dry_run=args.dry_run, sign=args.sign, passphrase=passphrase))


if __name__ == "__main__":
    main()
