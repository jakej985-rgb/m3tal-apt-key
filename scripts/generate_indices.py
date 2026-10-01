#!/usr/bin/env python3
"""
M3tal Package Indexing & Metadata Generation Engine (Phase 05)
Scans package pools, extracts Debian control records, calculates hashes,
and generates RFC 822 Packages, Packages.gz, and Release manifests.

Usage:
  ./generate_indices.py [--dry-run] [--verify] [--output-dir DIR]
"""

import os
import sys
import gzip
import hashlib
import argparse
import subprocess
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(REPO_ROOT, "registry", "packages.yml")
POOL_DIR = os.path.join(REPO_ROOT, "pool", "main")
DIST_DIR = os.path.join(REPO_ROOT, "dists", "stable")
AMD64_DIR = os.path.join(DIST_DIR, "main", "binary-amd64")

def compute_hashes(file_path):
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

def get_deb_control(deb_path):
    """Extract control stanza using dpkg-deb."""
    res = subprocess.run(
        ["dpkg-deb", "-f", deb_path],
        capture_output=True,
        text=True,
        check=True
    )
    return res.stdout.strip()

def scan_pool(pool_dir, repo_root):
    """Scans pool for .deb files, returning relative paths and metadata."""
    deb_files = []
    for root, _, files in os.walk(pool_dir):
        for f in sorted(files):
            if f.endswith(".deb"):
                abs_path = os.path.join(root, f)
                rel_path = os.path.relpath(abs_path, repo_root)
                deb_files.append((abs_path, rel_path))
    return deb_files

def generate_packages_content(deb_entries):
    """Generates the text for the Packages RFC 822 file."""
    paragraphs = []
    for abs_path, rel_path in deb_entries:
        control_text = get_deb_control(abs_path)
        hashes = compute_hashes(abs_path)
        
        # Build paragraph: standard Debian convention places checksums before Description
        lines = control_text.splitlines()
        desc_idx = -1
        for i, line in enumerate(lines):
            if line.startswith("Description:"):
                desc_idx = i
                break

        extra = [
            f"Filename: {rel_path}",
            f"Size: {hashes['size']}",
            f"MD5sum: {hashes['md5']}",
            f"SHA1: {hashes['sha1']}",
            f"SHA256: {hashes['sha256']}",
            f"SHA512: {hashes['sha512']}",
        ]

        if desc_idx != -1:
            pkg_lines = lines[:desc_idx] + extra + lines[desc_idx:]
        else:
            pkg_lines = lines + extra

        paragraphs.append("\n".join(pkg_lines))
    
    return "\n\n".join(paragraphs) + "\n\n"

def generate_release_manifest(suite="stable", origin="M3TAL", label="M3TAL", codename="stable",
                              architectures="amd64", components="main", description="M3TAL Core Repository",
                              date_str=None, file_hash_records=None):
    """Constructs a standard Debian Release file."""
    import datetime
    if date_str is None:
        now = datetime.datetime.now(datetime.timezone.utc)
        date_str = now.strftime("%a, %d %b %Y %H:%M:%S +0000")

    lines = [
        f"Architectures: {architectures}",
        f"Codename: {codename}",
        f"Components: {components}",
        f"Date: {date_str}",
        f"Description: {description}",
        f"Label: {label}",
        f"Origin: {origin}",
        f"Suite: {suite}",
    ]
    header_text = "\n".join(lines) + "\n"
    header_bytes = header_text.encode("utf-8")

    header_hashes = {
        "size": len(header_bytes),
        "md5": hashlib.md5(header_bytes).hexdigest(),
        "sha1": hashlib.sha1(header_bytes).hexdigest(),
        "sha256": hashlib.sha256(header_bytes).hexdigest(),
        "sha512": hashlib.sha512(header_bytes).hexdigest(),
    }

    all_records = {"Release": header_hashes}
    if file_hash_records:
        all_records.update(file_hash_records)

    for hash_name, header in [("md5", "MD5Sum:"), ("sha1", "SHA1:"), ("sha256", "SHA256:"), ("sha512", "SHA512:")]:
        lines.append(header)
        for rel_name, hashes in all_records.items():
            lines.append(f" {hashes[hash_name]} {hashes['size']:>16} {rel_name}")

    return "\n".join(lines) + "\n"

def main():
    parser = argparse.ArgumentParser(description="M3tal Repository Indexer")
    parser.add_argument("--dry-run", action="store_true", help="Index pool without modifying files")
    parser.add_argument("--verify", action="store_true", help="Verify existing Packages index against pool scan")
    parser.add_argument("--output-dir", help="Directory to write Packages and Packages.gz")
    parser.add_argument("--update-release", action="store_true", help="Also generate/update dists/stable/Release")
    args = parser.parse_args()

    print("==================================================")
    print(" M3tal Package Indexing & Metadata Engine         ")
    print("==================================================")

    # 1. Load registry
    print("--> 1. Loading registry...")
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry = yaml.safe_load(f)
    print(f"    Loaded {len(registry.get('packages', []))} package definitions.")

    # 2. Scan pool
    print("--> 2. Scanning pool for Debian packages...")
    deb_entries = scan_pool(POOL_DIR, REPO_ROOT)
    print(f"    Found {len(deb_entries)} .deb package archives in pool.")

    # 3. Generate Packages index
    print("--> 3. Parsing package control metadata & calculating hashes...")
    packages_content = generate_packages_content(deb_entries)
    compressed_content = gzip.compress(packages_content.encode("utf-8"), mtime=0)
    print(f"    Generated Packages index ({len(packages_content.encode('utf-8'))} bytes uncompressed, {len(compressed_content)} bytes gzipped).")

    if args.verify:
        print("--> 4. Verifying against existing repository index...")
        existing_packages_path = os.path.join(AMD64_DIR, "Packages")
        with open(existing_packages_path, "r", encoding="utf-8") as f:
            existing_text = f.read()

        # Parse existing packages to compare records
        def parse_paragraphs(text):
            pkgs = {}
            for block in text.strip().split("\n\n"):
                fields = {}
                for line in block.splitlines():
                    if ":" in line and not line.startswith(" "):
                        k, v = line.split(":", 1)
                        fields[k.strip()] = v.strip()
                if "Package" in fields and "Version" in fields:
                    pkgs[(fields["Package"], fields["Version"])] = fields
            return pkgs

        existing_map = parse_paragraphs(existing_text)
        new_map = parse_paragraphs(packages_content)

        print(f"    Existing index contains {len(existing_map)} package versions.")
        print(f"    Generated index contains {len(new_map)} package versions.")
        assert len(existing_map) == len(new_map), f"Count mismatch: {len(existing_map)} vs {len(new_map)}"

        check_fields = ["Package", "Version", "Architecture", "Size", "MD5sum", "SHA1", "SHA256", "SHA512", "Filename"]
        for key, orig in existing_map.items():
            assert key in new_map, f"Missing package version {key} in generated index"
            gen = new_map[key]
            for check_field in check_fields:
                assert orig.get(check_field) == gen.get(check_field), f"Mismatch in {check_field} for {key}: orig={orig.get(check_field)} gen={gen.get(check_field)}"
        print(f"    [OK] All package records, versions, sizes, and {', '.join(check_fields[4:8])} checksums match perfectly!")

    if args.dry_run:
        print("    [DRY-RUN] Index generated successfully; skipping disk write.")
    elif not args.verify:
        target_dir = args.output_dir or AMD64_DIR
        print(f"--> Writing index to {target_dir}...")
        os.makedirs(target_dir, exist_ok=True)
        pkg_file = os.path.join(target_dir, "Packages")
        pkg_gz_file = os.path.join(target_dir, "Packages.gz")
        with open(pkg_file, "w", encoding="utf-8") as f:
            f.write(packages_content)
        with open(pkg_gz_file, "wb") as f:
            f.write(compressed_content)
        print("    [OK] Packages and Packages.gz updated.")

        if args.update_release:
            print(f"--> Updating Release manifest in {DIST_DIR}...")
            # Compute hashes of generated index files
            file_records = {
                "main/binary-amd64/Packages": compute_hashes(pkg_file),
                "main/binary-amd64/Packages.gz": compute_hashes(pkg_gz_file),
            }
            rel_content = generate_release_manifest(file_hash_records=file_records)
            rel_file = os.path.join(DIST_DIR, "Release")
            with open(rel_file, "w", encoding="utf-8") as f:
                f.write(rel_content)
            print(f"    [OK] Release manifest updated at {rel_file}.")

    print("==================================================")
    print(" ✅ Package indexing operation completed successfully!")
    print("==================================================")

if __name__ == "__main__":
    main()
