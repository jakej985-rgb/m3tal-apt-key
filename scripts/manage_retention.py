#!/usr/bin/env python3
"""
M3tal APT Repository Package Retention & Pruning Engine
Phase 10 Deliverable: Implements inventory auditing, policy-driven retention,
snapshot creation, safe pruning, and metadata index regeneration.
"""

import argparse
import datetime
import glob
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(REPO_ROOT, "dists", "stable")
MAIN_BIN_DIR = os.path.join(DIST_DIR, "main", "binary-amd64")
POOL_DIR = os.path.join(REPO_ROOT, "pool", "main")
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "retention-policy.json")
DEFAULT_SNAPSHOT_DIR = os.path.join(REPO_ROOT, "snapshots")


def compute_file_hashes(file_path: str) -> Dict[str, Any]:
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
            sha512.update(chunk)
    return {
        "md5": md5.hexdigest(),
        "sha1": sha1.hexdigest(),
        "sha256": sha256.hexdigest(),
        "sha512": sha512.hexdigest(),
        "size": os.path.getsize(file_path),
    }


def parse_debian_version(version_str: str) -> Tuple[int, str, str]:
    epoch = 0
    rem = version_str
    if ":" in rem:
        ep_part, rem = rem.split(":", 1)
        try:
            epoch = int(ep_part)
        except ValueError:
            epoch = 0
    if "-" in rem:
        parts = rem.rsplit("-", 1)
        upstream = parts[0]
        revision = parts[1]
    else:
        upstream = rem
        revision = "0"
    return (epoch, upstream, revision)


def compare_debian_order_token(t1: str, t2: str) -> int:
    def order_val(ch: str) -> int:
        if ch == "~":
            return -1
        if ch.isalpha():
            return ord(ch)
        if ch:
            return ord(ch) + 256
        return 0

    idx1, idx2 = 0, 0
    len1, len2 = len(t1), len(t2)
    while idx1 < len1 or idx2 < len2:
        while (idx1 < len1 and not t1[idx1].isdigit()) or (idx2 < len2 and not t2[idx2].isdigit()):
            c1 = t1[idx1] if idx1 < len1 else ""
            c2 = t2[idx2] if idx2 < len2 else ""
            v1 = order_val(c1)
            v2 = order_val(c2)
            if v1 != v2:
                return -1 if v1 < v2 else 1
            idx1 += 1
            idx2 += 1
        d1, d2 = 0, 0
        while idx1 < len1 and t1[idx1].isdigit():
            d1 = d1 * 10 + int(t1[idx1])
            idx1 += 1
        while idx2 < len2 and t2[idx2].isdigit():
            d2 = d2 * 10 + int(t2[idx2])
            idx2 += 1
        if d1 != d2:
            return -1 if d1 < d2 else 1
    return 0


def compare_debian_versions(v1: str, v2: str) -> int:
    if v1 == v2:
        return 0
    e1, u1, r1 = parse_debian_version(v1)
    e2, u2, r2 = parse_debian_version(v2)
    if e1 != e2:
        return -1 if e1 < e2 else 1
    up_cmp = compare_debian_order_token(u1, u2)
    if up_cmp != 0:
        return up_cmp
    return compare_debian_order_token(r1, r2)


class VersionKey:
    def __init__(self, ver: str):
        self.ver = ver

    def __lt__(self, other: "VersionKey") -> bool:
        return compare_debian_versions(self.ver, other.ver) < 0

    def __gt__(self, other: "VersionKey") -> bool:
        return compare_debian_versions(self.ver, other.ver) > 0

    def __eq__(self, other: "VersionKey") -> bool:
        return compare_debian_versions(self.ver, other.ver) == 0


def parse_rfc822_blocks(content: str) -> List[Dict[str, str]]:
    blocks: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    last_key: Optional[str] = None
    for line in content.splitlines():
        if not line.strip():
            if current:
                blocks.append(current)
                current = {}
                last_key = None
            continue
        if line.startswith(" ") or line.startswith("\t"):
            if last_key and last_key in current:
                current[last_key] += "\n" + line.strip()
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            current[k] = v
            last_key = k
    if current:
        blocks.append(current)
    return blocks


def load_policy(config_path: str = CONFIG_PATH) -> Dict[str, Any]:
    default_policy = {
        "keep_recent_per_series": 5,
        "keep_recent_overall": 10,
        "min_retained_packages": 10,
        "protected_series": ["1.1", "1.0"],
        "pinned_versions": ["1.0.0", "1.0.60", "1.1.0", "1.1.62"],
        "snapshot": {"enabled": True, "directory": "snapshots", "max_snapshots_retained": 50},
        "deprecation": {"grace_period_days": 90, "archive_obsolete": True, "archive_directory": "archive/pool/main"}
    }
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("policy", default_policy)
        except Exception as e:
            print(f"Warning: Failed loading {config_path}: {e}. Using defaults.")
    return default_policy


def extract_series(version_str: str) -> str:
    """Extract major.minor series from version (e.g. '1.1.62' -> '1.1')."""
    _, upstream, _ = parse_debian_version(version_str)
    parts = upstream.split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return parts[0] if parts else "misc"


def build_inventory(repo_root: str = REPO_ROOT, policy: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    if policy is None:
        policy = load_policy()

    pkg_index_path = os.path.join(repo_root, "dists", "stable", "main", "binary-amd64", "Packages")
    if not os.path.isfile(pkg_index_path):
        raise FileNotFoundError(f"Packages index not found: {pkg_index_path}")

    with open(pkg_index_path, "r", encoding="utf-8") as f:
        content = f.read()

    entries = parse_rfc822_blocks(content)
    packages_by_series: Dict[str, List[Dict[str, Any]]] = {}

    all_items = []
    for entry in entries:
        pkg_name = entry.get("Package", "")
        pkg_ver = entry.get("Version", "")
        rel_fn = entry.get("Filename", "")
        abs_fn = os.path.join(repo_root, rel_fn)
        sz = int(entry.get("Size", 0)) if entry.get("Size") else os.path.getsize(abs_fn) if os.path.isfile(abs_fn) else 0
        series = extract_series(pkg_ver)

        item = {
            "package": pkg_name,
            "version": pkg_ver,
            "series": series,
            "filename": rel_fn,
            "abs_path": abs_fn,
            "size": sz,
            "raw_entry": entry,
            "status": "UNKNOWN",
            "reason": "",
        }
        all_items.append(item)
        packages_by_series.setdefault(series, []).append(item)

    # Sort items within each series descending by version
    for series, items in packages_by_series.items():
        items.sort(key=lambda x: VersionKey(x["version"]), reverse=True)

    # Find highest overall candidate version
    all_sorted = sorted(all_items, key=lambda x: VersionKey(x["version"]), reverse=True)
    highest_candidate = all_sorted[0]["version"] if all_sorted else None

    pinned_versions = set(policy.get("pinned_versions", []))
    keep_per_series = policy.get("keep_recent_per_series", 5)

    for item in all_items:
        ver = item["version"]
        series = item["series"]

        if ver == highest_candidate:
            item["status"] = "RETAIN_CURRENT"
            item["reason"] = "Latest active candidate version in repository"
        elif ver in pinned_versions:
            item["status"] = "RETAIN_PINNED"
            item["reason"] = "Explicitly pinned milestone or protected version"
        else:
            # Check rank within series
            series_items = packages_by_series[series]
            rank = series_items.index(item)
            if rank < keep_per_series:
                item["status"] = "RETAIN_RECENT"
                item["reason"] = f"Within top {keep_per_series} recent releases of series {series} (rank {rank + 1})"
            else:
                item["status"] = "PRUNE_CANDIDATE"
                item["reason"] = f"Exceeds retention window of {keep_per_series} releases in series {series}"

    return all_sorted


def print_inventory(inventory: List[Dict[str, Any]], policy: Dict[str, Any]):
    print("=" * 80)
    print(" M3TAL APT REPOSITORY PACKAGE INVENTORY & RETENTION STATUS")
    print("=" * 80)
    print(f"{'Package':<8} {'Version':<10} {'Series':<7} {'Size (MB)':<10} {'Status':<16} {'Reason'}")
    print("-" * 80)

    total_size = sum(item["size"] for item in inventory)
    prune_items = [item for item in inventory if item["status"] == "PRUNE_CANDIDATE"]
    retained_items = [item for item in inventory if item["status"] != "PRUNE_CANDIDATE"]
    prune_size = sum(item["size"] for item in prune_items)
    retain_size = sum(item["size"] for item in retained_items)

    for item in inventory:
        sz_mb = f"{item['size'] / (1024 * 1024):.2f}"
        print(f"{item['package']:<8} {item['version']:<10} {item['series']:<7} {sz_mb:<10} {item['status']:<16} {item['reason']}")

    print("=" * 80)
    print(" RETENTION PROFILE SUMMARY")
    print("=" * 80)
    print(f" Total Packages in Pool     : {len(inventory)} ({total_size / (1024*1024):.2f} MB)")
    print(f" Packages to Retain         : {len(retained_items)} ({retain_size / (1024*1024):.2f} MB)")
    print(f" Packages Eligible to Prune : {len(prune_items)} ({prune_size / (1024*1024):.2f} MB)")
    print(f" Potential Storage Savings  : {prune_size / (1024*1024):.2f} MB ({(prune_size / total_size * 100) if total_size else 0:.1f}%)")
    print("=" * 80)


def create_snapshot(repo_root: str = REPO_ROOT, snapshot_dir: Optional[str] = None) -> str:
    """Create timestamped repository metadata snapshot manifest."""
    if snapshot_dir is None:
        snapshot_dir = os.path.join(repo_root, "snapshots")
    os.makedirs(snapshot_dir, exist_ok=True)

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest_name = f"snapshot-manifest-{timestamp}.json"
    manifest_path = os.path.join(snapshot_dir, manifest_name)

    pkg_index_path = os.path.join(repo_root, "dists", "stable", "main", "binary-amd64", "Packages")
    release_path = os.path.join(repo_root, "dists", "stable", "Release")

    with open(pkg_index_path, "r", encoding="utf-8") as f:
        packages_raw = f.read()

    with open(release_path, "r", encoding="utf-8") as f:
        release_raw = f.read()

    pool_dir = os.path.join(repo_root, "pool", "main")
    pool_files = {}
    for deb in sorted(glob.glob(os.path.join(pool_dir, "*.deb"))):
        fn = os.path.basename(deb)
        h = compute_file_hashes(deb)
        pool_files[fn] = h

    manifest_data = {
        "timestamp": timestamp,
        "repo_root": repo_root,
        "total_packages": len(pool_files),
        "pool_files": pool_files,
        "packages_content": packages_raw,
        "release_content": release_raw,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    print(f"--> [SNAPSHOT] Created repository state snapshot: {manifest_path} ({len(pool_files)} packages recorded)")
    return manifest_path


def regenerate_repository_indexes(repo_root: str = REPO_ROOT, retained_items: List[Dict[str, Any]] = None):
    """Regenerate Packages, Packages.gz, and dists/stable/Release checksums."""
    print("--> [INDEX] Regenerating APT Packages and Packages.gz indexes...")
    pkg_index_path = os.path.join(repo_root, "dists", "stable", "main", "binary-amd64", "Packages")
    gz_index_path = os.path.join(repo_root, "dists", "stable", "main", "binary-amd64", "Packages.gz")
    release_path = os.path.join(repo_root, "dists", "stable", "Release")

    if retained_items is None:
        inventory = build_inventory(repo_root)
        retained_items = [i for i in inventory if i["status"] != "PRUNE_CANDIDATE"]

    # Rebuild Packages content
    blocks = []
    for item in retained_items:
        raw = item["raw_entry"]
        # Format RFC 822 block
        lines = []
        for k, v in raw.items():
            lines.append(f"{k}: {v}")
        blocks.append("\n".join(lines))

    new_packages_content = "\n\n".join(blocks) + "\n"

    # Write Packages
    with open(pkg_index_path, "w", encoding="utf-8") as f:
        f.write(new_packages_content)

    # Write Packages.gz
    with gzip.open(gz_index_path, "wb") as f_gz:
        f_gz.write(new_packages_content.encode("utf-8"))

    # Compute new hashes
    pkg_hashes = compute_file_hashes(pkg_index_path)
    gz_hashes = compute_file_hashes(gz_index_path)

    # Read existing Release
    with open(release_path, "r", encoding="utf-8") as f:
        rel_content = f.read()

    # Update checksum tables in Release
    lines = rel_content.splitlines()
    new_lines = []
    current_sec = None
    table_files_seen = set()

    for line in lines:
        if line.endswith(":") and ("MD5" in line or "SHA" in line):
            current_sec = line.strip(":").lower()
            new_lines.append(line)
            table_files_seen.clear()
            continue

        if current_sec and (line.startswith(" ") or line.startswith("\t")):
            parts = line.strip().split()
            if len(parts) == 3:
                _, _, path = parts
                alg = "md5" if "md5" in current_sec else current_sec.replace("sum", "")
                if path == "main/binary-amd64/Packages":
                    h = pkg_hashes[alg]
                    sz = pkg_hashes["size"]
                    new_lines.append(f" {h} {sz:>16} {path}")
                    table_files_seen.add(path)
                    continue
                elif path == "main/binary-amd64/Packages.gz":
                    h = gz_hashes[alg]
                    sz = gz_hashes["size"]
                    new_lines.append(f" {h} {sz:>16} {path}")
                    table_files_seen.add(path)
                    continue
            new_lines.append(line)
        else:
            current_sec = None
            new_lines.append(line)

    with open(release_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines) + "\n")

    print(f"--> [INDEX] Updated Packages ({pkg_hashes['size']} bytes) and Release checksums successfully.")


def execute_prune(repo_root: str = REPO_ROOT, policy: Optional[Dict[str, Any]] = None, dry_run: bool = True) -> int:
    if policy is None:
        policy = load_policy()

    inventory = build_inventory(repo_root, policy)
    to_prune = [i for i in inventory if i["status"] == "PRUNE_CANDIDATE"]
    to_retain = [i for i in inventory if i["status"] != "PRUNE_CANDIDATE"]

    min_floor = policy.get("min_retained_packages", 10)
    if len(to_retain) < min_floor:
        print(f"ERROR: Safety guard triggered! Retained packages count ({len(to_retain)}) is below safety floor ({min_floor}). Aborting.")
        return 1

    # Check candidate is in to_retain
    candidate = max(inventory, key=lambda x: VersionKey(x["version"]))["version"]
    if not any(i["version"] == candidate for i in to_retain):
        print(f"ERROR: Safety guard triggered! Highest candidate {candidate} is missing from retained set! Aborting.")
        return 1

    if dry_run:
        print("--> [DRY-RUN] Prune evaluation completed. Zero disk changes made.")
        print(f"--> [DRY-RUN] Would remove {len(to_prune)} deb files and retain {len(to_retain)} packages.")
        return 0

    # 1. Snapshot first
    create_snapshot(repo_root)

    # 2. Archive or delete obsolete debs
    archive_enabled = policy.get("deprecation", {}).get("archive_obsolete", True)
    archive_dir = os.path.join(repo_root, policy.get("deprecation", {}).get("archive_directory", "archive/pool/main"))
    if archive_enabled:
        os.makedirs(archive_dir, exist_ok=True)

    print(f"--> [EXECUTE] Removing {len(to_prune)} obsolete deb files from pool/main...")
    for item in to_prune:
        src = item["abs_path"]
        if os.path.isfile(src):
            if archive_enabled:
                dst = os.path.join(archive_dir, os.path.basename(src))
                shutil.move(src, dst)
            else:
                os.remove(src)

    # 3. Regenerate indexes
    regenerate_repository_indexes(repo_root, retained_items=to_retain)
    print("--> [EXECUTE] Package pruning and metadata regeneration finished.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="M3tal APT Repository Package Retention & Pruning Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Inventory
    p_inv = subparsers.add_parser("inventory", help="List all package versions and retention status")
    p_inv.add_argument("--json", dest="json_out", help="Save inventory to JSON file")

    # Snapshot
    p_snap = subparsers.add_parser("snapshot", help="Create an immutable repository state snapshot")
    p_snap.add_argument("--dir", default=DEFAULT_SNAPSHOT_DIR, help="Destination directory for snapshots")

    # Prune
    p_prune = subparsers.add_parser("prune", help="Evaluate or execute package pruning based on policy")
    p_prune.add_argument("--dry-run", action="store_true", default=True, help="Evaluate without modifying files (default)")
    p_prune.add_argument("--execute", action="store_true", help="Execute removal and metadata regeneration")

    # Verify
    p_ver = subparsers.add_parser("verify", help="Verify current repository against retention policy")

    args = parser.parse_args()
    policy = load_policy()

    if args.command == "inventory":
        inv = build_inventory(REPO_ROOT, policy)
        print_inventory(inv, policy)
        if args.json_out:
            clean_inv = [{k: v for k, v in item.items() if k != "raw_entry"} for item in inv]
            with open(args.json_out, "w", encoding="utf-8") as f:
                json.dump({"policy": policy, "inventory": clean_inv}, f, indent=2)
            print(f"Saved inventory to: {args.json_out}")

    elif args.command == "snapshot":
        create_snapshot(REPO_ROOT, snapshot_dir=args.dir)

    elif args.command == "prune":
        dry_run = not args.execute
        sys.exit(execute_prune(REPO_ROOT, policy, dry_run=dry_run))

    elif args.command == "verify":
        inv = build_inventory(REPO_ROOT, policy)
        prune_items = [i for i in inv if i["status"] == "PRUNE_CANDIDATE"]
        print(f"Policy evaluation: {len(inv)} total packages, {len(prune_items)} candidate(s) for pruning.")
        if prune_items:
            print("Notice: Repository contains packages eligible for pruning according to retention policy.")
        else:
            print("OK: Repository adheres strictly to retention bounds.")


if __name__ == "__main__":
    main()
