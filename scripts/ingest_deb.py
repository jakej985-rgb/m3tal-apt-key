#!/usr/bin/env python3
"""
M3tal Central Deb Package Ingestion & Publishing CLI
Enables any M3tal ecosystem application (like Monster Lab) to publish and synchronize
its Debian packages into the central m3tal-apt-key repository.

Supports:
  1. Local .deb file ingestion:      ingest_deb.py /path/to/app.deb
  2. Local repo ingestion:           ingest_deb.py --from-repo /path/to/app-repo
  3. Remote URL ingestion:           ingest_deb.py --url https://github.com/.../app.deb
"""

import os
import sys
import shutil
import urllib.request
import tempfile
import argparse
import subprocess
import yaml
from typing import Optional, Dict, Any

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

SCRIPT_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from publish_package import AptPublisher
from validate_package import validate_debian_package, extract_control_from_deb
from deb_version import compare_debian_versions

DEFAULT_KEY_FINGERPRINT = "5F84FE50A40111C981410E11775AD1473BF25102"
REGISTRY_PATH = os.path.join(REPO_ROOT, "registry", "packages.yml")


def find_default_signing_key() -> Optional[str]:
    """Check if default signing key exists in gpg keyring."""
    gpg_bin = shutil.which("gpg")
    if not gpg_bin:
        return None
    res = subprocess.run([gpg_bin, "--list-secret-keys", "--with-colons"], capture_output=True, text=True)
    if res.returncode == 0:
        if DEFAULT_KEY_FINGERPRINT in res.stdout:
            return DEFAULT_KEY_FINGERPRINT
        # Check any secret key
        for line in res.stdout.splitlines():
            if line.startswith("fpr:"):
                parts = line.split(":")
                if len(parts) > 9 and parts[9]:
                    return parts[9]
    return None


def update_registry_manifest(package_name: str, new_version: str, pool_path: str):
    """Update registry/packages.yml with newly published package version and status."""
    if not os.path.exists(REGISTRY_PATH):
        return

    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry = yaml.safe_load(f) or {}

    updated = False
    packages = registry.get("packages", [])
    for pkg in packages:
        # Match by id or package name
        if pkg.get("id") == package_name or pkg.get("name") == package_name:
            metadata = pkg.setdefault("metadata", {})
            curr_ver = metadata.get("latest_version")
            if not curr_ver or compare_debian_versions(new_version, curr_ver) > 0:
                metadata["latest_version"] = new_version
                pkg["status"] = "published"
                publication = pkg.setdefault("publication", {})
                publication["pool_path"] = os.path.dirname(pool_path)
                updated = True
                print(f"--> [REGISTRY] Updated registry entry for '{package_name}' to v{new_version}")
            break

    if updated:
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            yaml.dump(registry, f, sort_keys=False, default_flow_style=False)


def ingest_deb_file(
    deb_path: str,
    repo_dir: str = REPO_ROOT,
    allow_replace: bool = False,
    allow_downgrade: bool = False,
    skip_validation: bool = False,
    sign: bool = True,
    key_id: Optional[str] = None,
    passphrase: Optional[str] = None,
    update_registry: bool = True,
) -> Dict[str, Any]:
    """Ingest a single Debian package into the central repository."""
    if not os.path.isfile(deb_path):
        raise FileNotFoundError(f"Package file not found: {deb_path}")

    print(f"==================================================")
    print(f" Ingesting Debian Package: {os.path.basename(deb_path)}")
    print(f"==================================================")

    # 1. Validation
    if not skip_validation:
        print("--> 1. Validating Debian package structure and metadata...")
        val_res = validate_debian_package(deb_path)
        if not val_res.is_valid:
            errors_str = "\n  - ".join(val_res.errors)
            raise ValueError(f"Debian package validation failed:\n  - {errors_str}")
        print("    [OK] Package control and archive structure passed validation.")

    fields, _ = extract_control_from_deb(deb_path)
    pkg_name = fields.get("Package", "unknown")
    pkg_ver = fields.get("Version", "unknown")
    pkg_arch = fields.get("Architecture", "unknown")

    print(f"--> Package Details: {pkg_name} {pkg_ver} ({pkg_arch})")

    # 2. Stage into pool
    publisher = AptPublisher(
        repo_dir=repo_dir,
        suite="stable",
        component="main",
        origin="M3TAL",
        label="M3TAL",
        description="M3TAL Central Ecosystem APT Repository",
        pool_style="structured",
    )

    print(f"--> 2. Publishing to repository pool...")
    staged_path = publisher.publish_deb(
        deb_path=deb_path,
        allow_replace=allow_replace,
        allow_downgrade=allow_downgrade,
        skip_validation=True,  # already validated above
    )
    rel_staged = os.path.relpath(staged_path, repo_dir)
    print(f"    [OK] Staged to: {rel_staged}")

    # 3. Update registry manifest
    if update_registry:
        update_registry_manifest(pkg_name, pkg_ver, rel_staged)

    # 4. Determine signing key
    signing_key = key_id or find_default_signing_key()
    should_sign = sign and bool(signing_key)
    if sign and not signing_key:
        print("--> Warning: No GPG signing key found in keyring. Proceeding with unsigned index.")

    # 5. Regenerate APT indices
    print("--> 3. Regenerating Packages, Packages.gz, and Release indices...")
    try:
        index_info = publisher.generate_indexes(
            gpg_key_id=signing_key if should_sign else None,
            gpg_passphrase=passphrase,
            sign=should_sign,
        )
        print(f"    [OK] Indices updated ({index_info['package_count']} packages for {index_info['architectures']}).")
        if should_sign:
            print(f"    [OK] Cryptographically signed InRelease and Release.gpg with key {signing_key}.")
    except Exception as e:
        if should_sign:
            print(f"--> Warning: GPG signing failed ({e}).", file=sys.stderr)
            print("--> Regenerating repository indices without GPG signature...", file=sys.stderr)
            index_info = publisher.generate_indexes(sign=False)
            print(f"    [OK] Indices updated successfully without signature ({index_info['package_count']} packages for {index_info['architectures']}).")
            should_sign = False
        else:
            raise

    print("==================================================")
    print(f" ✅ Successfully Published {pkg_name} ({pkg_ver}) to Central Repository!")
    print(f" Install via: sudo apt install {pkg_name}")
    print("==================================================")

    return {
        "package": pkg_name,
        "version": pkg_ver,
        "architecture": pkg_arch,
        "staged_path": staged_path,
        "signed": should_sign,
    }


def ingest_from_repo(repo_path: str, **kwargs) -> Dict[str, Any]:
    """Locate or build .deb from an application repo and ingest it."""
    repo_path = os.path.abspath(repo_path)
    if not os.path.isdir(repo_path):
        raise NotADirectoryError(f"Application directory not found: {repo_path}")

    # Find existing .deb files in repo
    deb_candidates = []
    for root, _, files in os.walk(repo_path):
        if "/.git" in root or "/build/deb_staging" in root:
            continue
        for f in files:
            if f.endswith(".deb"):
                deb_candidates.append(os.path.join(root, f))

    if deb_candidates:
        # Sort by modification time, most recent first
        deb_candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        selected_deb = deb_candidates[0]
        print(f"Found existing .deb in application repo: {selected_deb}")
        return ingest_deb_file(selected_deb, **kwargs)

    # If no deb found, check for package script
    pkg_script = os.path.join(repo_path, "scripts", "package_linux_deb.py")
    if os.path.exists(pkg_script):
        print(f"No .deb found. Packaging via {pkg_script}...")
        bundle_dir = os.path.join(repo_path, "build", "linux", "x64", "release", "bundle")
        output_deb = os.path.join(repo_path, "build", "app-release.deb")
        os.makedirs(os.path.dirname(output_deb), exist_ok=True)

        res = subprocess.run([sys.executable, pkg_script, "--bundle-dir", bundle_dir, "--output", output_deb])
        if res.returncode == 0 and os.path.exists(output_deb):
            return ingest_deb_file(output_deb, **kwargs)
        else:
            raise RuntimeError(f"Packaging failed in {repo_path}. Ensure release bundle is built.")

    raise FileNotFoundError(f"No .deb archive or package_linux_deb.py found in {repo_path}")


def ingest_from_url(url: str, **kwargs) -> Dict[str, Any]:
    """Download .deb from URL to temp directory and ingest."""
    print(f"Downloading package from: {url} ...")
    with tempfile.TemporaryDirectory(prefix="m3tal_deb_dl_") as tmp_dir:
        filename = url.split("?")[0].split("/")[-1]
        if not filename.endswith(".deb"):
            filename = "downloaded_package.deb"
        dest = os.path.join(tmp_dir, filename)

        req = urllib.request.Request(url, headers={"User-Agent": "M3tal-Deb-Ingest/1.0"})
        with urllib.request.urlopen(req) as resp, open(dest, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)

        print(f"Downloaded {os.path.getsize(dest)} bytes -> {dest}")
        return ingest_deb_file(dest, **kwargs)


def main():
    parser = argparse.ArgumentParser(
        description="M3tal Central Deb Package Ingestion Tool"
    )
    parser.add_argument("deb", nargs="?", help="Path to local .deb file to ingest")
    parser.add_argument("--url", help="HTTP(S) URL of .deb file to download and ingest")
    parser.add_argument("--from-repo", help="Path to local app repository directory to ingest from")
    parser.add_argument("--repo-dir", default=REPO_ROOT, help="Path to central apt repository root")
    parser.add_argument("--allow-replace", action="store_true", help="Allow replacing identical existing package version")
    parser.add_argument("--allow-downgrade", action="store_true", help="Allow publishing older version than latest")
    parser.add_argument("--skip-validation", action="store_true", help="Skip deb validation checks")
    parser.add_argument("--no-sign", action="store_true", help="Do not GPG sign repository indices")
    parser.add_argument("--key-id", help="GPG key ID/fingerprint to sign with")
    parser.add_argument("--passphrase", help="GPG key passphrase")
    parser.add_argument("--no-registry-update", action="store_true", help="Do not update registry/packages.yml")

    args = parser.parse_args()

    sign_flag = not args.no_sign
    update_reg = not args.no_registry_update

    passphrase = args.passphrase or os.environ.get("APT_GPG_PASSPHRASE") or os.environ.get("GPG_PASSPHRASE")
    if not passphrase and os.path.exists(os.path.expanduser("~/.config/m3tal/apt_gpg_passphrase")):
        try:
            with open(os.path.expanduser("~/.config/m3tal/apt_gpg_passphrase"), "r") as pf:
                passphrase = pf.read().strip()
        except Exception:
            pass

    common_kwargs = {
        "repo_dir": args.repo_dir,
        "allow_replace": args.allow_replace,
        "allow_downgrade": args.allow_downgrade,
        "skip_validation": args.skip_validation,
        "sign": sign_flag,
        "key_id": args.key_id,
        "passphrase": passphrase,
        "update_registry": update_reg,
    }

    try:
        if args.url:
            ingest_from_url(args.url, **common_kwargs)
        elif args.from_repo:
            ingest_from_repo(args.from_repo, **common_kwargs)
        elif args.deb:
            ingest_deb_file(args.deb, **common_kwargs)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ [ERROR] Ingestion failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
