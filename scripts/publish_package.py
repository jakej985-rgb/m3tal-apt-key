#!/usr/bin/env python3
"""
M3tal Debian Package Publishing & APT Index Generation Engine
Phase 06 Deliverable: Automates deb publication, pool placement, version guardrails,
APT index generation (Packages, Packages.gz), Release metadata computation,
and GPG signing (InRelease, Release.gpg) with atomic updates.
"""

import os
import sys
import io
import shutil
import hashlib
import gzip
import email.utils
import datetime
import tempfile
import subprocess
import argparse
from typing import Dict, List, Set, Optional, Tuple

# Import local modules
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from deb_version import (
    parse_debian_version,
    compare_debian_versions,
    is_valid_debian_version,
)
from validate_package import (
    validate_debian_package,
    extract_control_from_deb,
    parse_rfc822_fields,
)


def compute_file_digests(filepath: str) -> Dict[str, str]:
    """Compute MD5, SHA1, SHA256, SHA512, and byte size of a file."""
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()
    size = os.path.getsize(filepath)

    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
            sha512.update(chunk)

    return {
        "size": str(size),
        "md5": md5.hexdigest(),
        "sha1": sha1.hexdigest(),
        "sha256": sha256.hexdigest(),
        "sha512": sha512.hexdigest(),
    }


class AptPublisher:
    def __init__(
        self,
        repo_dir: str,
        suite: str = "stable",
        component: str = "main",
        origin: str = "M3TAL",
        label: str = "M3TAL",
        description: str = "M3TAL Core Repository",
        pool_style: str = "auto",  # 'structured' (pool/main/pkg/), 'flat' (pool/main/), or 'auto'
    ):
        self.repo_dir = os.path.abspath(repo_dir)
        self.suite = suite
        self.component = component
        self.origin = origin
        self.label = label
        self.description = description
        self.pool_style = pool_style

        self.dists_dir = os.path.join(self.repo_dir, "dists", self.suite)
        self.pool_dir = os.path.join(self.repo_dir, "pool", self.component)

    def discover_existing_packages(self) -> List[Dict[str, str]]:
        """
        Scan all .deb files in pool/<component> and parse their metadata.
        Returns a list of dictionaries with control metadata + pool-relative Filename + hashes.
        """
        packages: List[Dict[str, str]] = []
        if not os.path.exists(self.pool_dir):
            return packages

        for root, _, files in os.walk(self.pool_dir):
            for f in sorted(files):
                if f.endswith(".deb"):
                    full_path = os.path.join(root, f)
                    try:
                        fields, _ = extract_control_from_deb(full_path)
                        digests = compute_file_digests(full_path)
                        rel_filename = os.path.relpath(full_path, self.repo_dir)

                        entry = dict(fields)
                        entry["Filename"] = rel_filename
                        entry["Size"] = digests["size"]
                        entry["MD5sum"] = digests["md5"]
                        entry["SHA1"] = digests["sha1"]
                        entry["SHA256"] = digests["sha256"]
                        entry["SHA512"] = digests["sha512"]
                        entry["_full_path"] = full_path

                        packages.append(entry)
                    except Exception as e:
                        print(f"Warning: Failed to parse {full_path}: {e}", file=sys.stderr)

        return packages

    def check_duplicate_or_downgrade(
        self,
        candidate_deb: str,
        existing_packages: List[Dict[str, str]],
        allow_replace: bool = False,
        allow_downgrade: bool = False,
    ) -> Tuple[bool, str, Dict[str, str]]:
        """
        Check if candidate .deb is duplicate or older than latest published version.
        Returns (is_allowed, reason, candidate_fields).
        """
        cand_fields, _ = extract_control_from_deb(candidate_deb)
        pkg_name = cand_fields.get("Package")
        cand_ver = cand_fields.get("Version")
        cand_arch = cand_fields.get("Architecture")

        if not pkg_name or not cand_ver or not cand_arch:
            return False, "Candidate deb is missing Package, Version, or Architecture", cand_fields

        matching_pkgs = [
            p for p in existing_packages
            if p.get("Package") == pkg_name and (p.get("Architecture") == cand_arch or cand_arch == "all" or p.get("Architecture") == "all")
        ]

        if not matching_pkgs:
            return True, "Initial release of package", cand_fields

        latest_pkg = None
        for p in matching_pkgs:
            ex_ver = p.get("Version")
            cmp = compare_debian_versions(cand_ver, ex_ver)
            if cmp == 0:
                if not allow_replace:
                    return (
                        False,
                        f"Exact version '{cand_ver}' for package '{pkg_name}' ({cand_arch}) already exists in repository.",
                        cand_fields,
                    )
            if latest_pkg is None or compare_debian_versions(ex_ver, latest_pkg.get("Version")) > 0:
                latest_pkg = p

        if latest_pkg:
            latest_ver = latest_pkg.get("Version")
            if compare_debian_versions(cand_ver, latest_ver) < 0:
                if not allow_downgrade:
                    return (
                        False,
                        f"Candidate version '{cand_ver}' is older than latest repository version '{latest_ver}'. "
                        f"Use --allow-downgrade to force publication, or bump epoch/version.",
                        cand_fields,
                    )

        return True, "Version check passed", cand_fields

    def publish_deb(
        self,
        deb_path: str,
        allow_replace: bool = False,
        allow_downgrade: bool = False,
        skip_validation: bool = False,
    ) -> str:
        """
        Validate, name-standardize, and copy .deb into the pool.
        Returns destination path.
        """
        if not skip_validation:
            val_res = validate_debian_package(deb_path)
            if not val_res.is_valid:
                errors = "\n  - ".join(val_res.errors)
                raise ValueError(f"Package validation failed for {deb_path}:\n  - {errors}")

        existing = self.discover_existing_packages()
        allowed, reason, fields = self.check_duplicate_or_downgrade(
            deb_path, existing, allow_replace=allow_replace, allow_downgrade=allow_downgrade
        )
        if not allowed:
            raise ValueError(f"Publication rejected: {reason}")

        pkg_name = fields["Package"]
        ver = fields["Version"]
        arch = fields["Architecture"]

        # Standard Debian filename: <package>_<version>_<arch>.deb
        target_filename = f"{pkg_name}_{ver}_{arch}.deb"

        # Determine target pool directory
        if self.pool_style == "flat":
            target_dir = self.pool_dir
        elif self.pool_style == "structured":
            target_dir = os.path.join(self.pool_dir, pkg_name)
        else:  # auto
            # Default to structured package directory per Phase 04 / Phase 06 target
            target_dir = os.path.join(self.pool_dir, pkg_name)

        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, target_filename)

        # Atomic copy
        tmp_target = target_path + ".tmp"
        shutil.copy2(deb_path, tmp_target)
        os.replace(tmp_target, target_path)

        return target_path

    def generate_indexes(
        self,
        architectures: Optional[List[str]] = None,
        gpg_key_id: Optional[str] = None,
        gpg_passphrase: Optional[str] = None,
        gnupghome: Optional[str] = None,
        valid_until_days: Optional[int] = None,
        sign: bool = False,
    ) -> Dict[str, str]:
        """
        Regenerate Packages, Packages.gz, Release, and optionally InRelease / Release.gpg.
        Performs atomic replacement of index directory.
        """
        all_pkgs = self.discover_existing_packages()

        # Collect architectures
        found_archs = set()
        for p in all_pkgs:
            a = p.get("Architecture")
            if a and a != "all":
                found_archs.add(a)

        if architectures:
            target_archs = sorted(list(set(architectures)))
        elif found_archs:
            target_archs = sorted(list(found_archs))
        else:
            target_archs = ["amd64"]

        # Stage files in temporary directory for atomic publication
        with tempfile.TemporaryDirectory(prefix="apt_index_stage_") as stage_dir:
            stage_dists = os.path.join(stage_dir, "dists", self.suite)
            os.makedirs(stage_dists, exist_ok=True)

            index_entries = []

            for arch in target_archs:
                bin_dir = os.path.join(stage_dists, self.component, f"binary-{arch}")
                os.makedirs(bin_dir, exist_ok=True)

                # Filter packages for this architecture (include native arch + 'all')
                arch_pkgs = [
                    p for p in all_pkgs
                    if p.get("Architecture") == arch or p.get("Architecture") == "all"
                ]

                # Deterministically sort packages by name, then Debian version
                from functools import cmp_to_key

                def _cmp_pkgs(p1, p2):
                    pkg1 = p1.get("Package", "")
                    pkg2 = p2.get("Package", "")
                    if pkg1 != pkg2:
                        return -1 if pkg1 < pkg2 else 1
                    try:
                        return compare_debian_versions(p1.get("Version", "0"), p2.get("Version", "0"))
                    except Exception:
                        return -1 if p1.get("Version", "0") < p2.get("Version", "0") else 1

                arch_pkgs.sort(key=cmp_to_key(_cmp_pkgs))

                # Format Packages RFC 822 content
                packages_content = io.StringIO()
                field_order = [
                    "Package", "Architecture", "Version", "Priority", "Section",
                    "Maintainer", "Installed-Size", "Depends", "Pre-Depends",
                    "Recommends", "Suggests", "Conflicts", "Breaks", "Replaces",
                    "Provides", "Homepage", "Multi-Arch", "Essential", "Filename", "Size",
                    "MD5sum", "SHA1", "SHA256", "SHA512", "Description"
                ]

                for p in arch_pkgs:
                    # Order standard fields per Debian Packages convention
                    for field in field_order:
                        if field in p:
                            packages_content.write(f"{field}: {p[field]}\n")
                    # Preserve any extra fields from package control file not in standard field_order
                    for field, val in p.items():
                        if field not in field_order and not field.startswith("_"):
                            packages_content.write(f"{field}: {val}\n")
                    packages_content.write("\n")

                packages_str = packages_content.getvalue()
                packages_bytes = packages_str.encode("utf-8")

                pkgs_file = os.path.join(bin_dir, "Packages")
                with open(pkgs_file, "wb") as f:
                    f.write(packages_bytes)

                pkgs_gz_file = os.path.join(bin_dir, "Packages.gz")
                # Deterministic gzip: mtime=0
                with open(pkgs_gz_file, "wb") as f_out:
                    with gzip.GzipFile(filename="", mode="wb", fileobj=f_out, mtime=0) as gz:
                        gz.write(packages_bytes)

                rel_pkgs = f"{self.component}/binary-{arch}/Packages"
                rel_pkgs_gz = f"{self.component}/binary-{arch}/Packages.gz"

                index_entries.append((rel_pkgs, pkgs_file))
                index_entries.append((rel_pkgs_gz, pkgs_gz_file))

            # Generate Release file
            now = datetime.datetime.now(datetime.timezone.utc)
            date_str = email.utils.format_datetime(now)

            release_content = io.StringIO()
            release_content.write(f"Origin: {self.origin}\n")
            release_content.write(f"Label: {self.label}\n")
            release_content.write(f"Suite: {self.suite}\n")
            release_content.write(f"Codename: {self.suite}\n")
            release_content.write(f"Date: {date_str}\n")
            if valid_until_days is not None:
                valid_until = now + datetime.timedelta(days=valid_until_days)
                valid_until_str = email.utils.format_datetime(valid_until)
                release_content.write(f"Valid-Until: {valid_until_str}\n")
            release_content.write(f"Architectures: {' '.join(target_archs)}\n")
            release_content.write(f"Components: {self.component}\n")
            release_content.write(f"Description: {self.description}\n")

            # Checksums
            hashes_by_file = {}
            for rel_name, abs_f in index_entries:
                hashes_by_file[rel_name] = compute_file_digests(abs_f)

            for hash_name, label in [
                ("md5", "MD5Sum"),
                ("sha1", "SHA1"),
                ("sha256", "SHA256"),
                ("sha512", "SHA512"),
            ]:
                release_content.write(f"{label}:\n")
                for rel_name, abs_f in index_entries:
                    h = hashes_by_file[rel_name][hash_name]
                    sz = hashes_by_file[rel_name]["size"]
                    release_content.write(f" {h} {sz:>16} {rel_name}\n")

            release_str = release_content.getvalue()
            release_file = os.path.join(stage_dists, "Release")
            with open(release_file, "w", encoding="utf-8") as f:
                f.write(release_str)

            # GPG Signing
            if sign:
                self._sign_release(
                    release_file=release_file,
                    output_inrelease=os.path.join(stage_dists, "InRelease"),
                    output_release_gpg=os.path.join(stage_dists, "Release.gpg"),
                    key_id=gpg_key_id,
                    passphrase=gpg_passphrase,
                    gnupghome=gnupghome,
                )

            # Atomic copy to destination dists
            os.makedirs(self.dists_dir, exist_ok=True)
            for item in os.listdir(stage_dists):
                s_item = os.path.join(stage_dists, item)
                d_item = os.path.join(self.dists_dir, item)
                if os.path.isdir(s_item):
                    if os.path.exists(d_item):
                        shutil.rmtree(d_item)
                    shutil.copytree(s_item, d_item)
                else:
                    shutil.copy2(s_item, d_item)

        return {
            "dists_dir": self.dists_dir,
            "architectures": " ".join(target_archs),
            "package_count": str(len(all_pkgs)),
            "signed": str(sign),
        }

    def _sign_release(
        self,
        release_file: str,
        output_inrelease: str,
        output_release_gpg: str,
        key_id: Optional[str] = None,
        passphrase: Optional[str] = None,
        gnupghome: Optional[str] = None,
    ):
        """Sign Release to produce InRelease and Release.gpg."""
        base_cmd = ["gpg", "--batch", "--yes"]
        if gnupghome:
            base_cmd.extend(["--homedir", gnupghome])
        if key_id:
            base_cmd.extend(["--default-key", key_id])
        if passphrase:
            base_cmd.extend(["--pinentry-mode", "loopback", "--passphrase", passphrase])

        # 1. Inline clearsign (InRelease)
        inrel_cmd = base_cmd + ["--clearsign", "--output", output_inrelease, release_file]
        try:
            res = subprocess.run(inrel_cmd, capture_output=True, text=True, timeout=5)
            if res.returncode != 0:
                raise RuntimeError(f"GPG clearsign failed: {res.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("GPG clearsign timed out waiting for pinentry/passphrase.")

        # 2. Detached signature (Release.gpg)
        relgpg_cmd = base_cmd + ["--detach-sign", "--armor", "--output", output_release_gpg, release_file]
        try:
            res = subprocess.run(relgpg_cmd, capture_output=True, text=True, timeout=5)
            if res.returncode != 0:
                raise RuntimeError(f"GPG detached signature failed: {res.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("GPG detached signature timed out waiting for pinentry/passphrase.")


def main():
    parser = argparse.ArgumentParser(
        description="M3tal Debian Package Publishing & APT Index Generation Engine (Phase 06)"
    )
    parser.add_argument("--repo-dir", default=".", help="Root directory of APT repository")
    parser.add_argument("--suite", default="stable", help="APT distribution suite (default: stable)")
    parser.add_argument("--component", default="main", help="Repository component (default: main)")
    parser.add_argument("--pool-style", choices=["auto", "flat", "structured"], default="auto")

    # Publishing flags
    parser.add_argument("debs", nargs="*", help="Path(s) to .deb file(s) to publish")
    parser.add_argument("--regenerate-indexes", action="store_true", help="Regenerate APT indexes without publishing new deb")
    parser.add_argument("--allow-replace", action="store_true", help="Allow overwriting identical existing package version")
    parser.add_argument("--allow-downgrade", action="store_true", help="Allow publishing older version than latest")
    parser.add_argument("--skip-validation", action="store_true", help="Skip deb metadata validation checks")

    # Release metadata flags
    parser.add_argument("--valid-until-days", type=int, default=None, help="Optional Valid-Until duration in days for Release metadata")

    # GPG Signing flags
    default_pass = os.environ.get("APT_GPG_PASSPHRASE") or os.environ.get("GPG_PASSPHRASE")
    if not default_pass and os.path.exists(os.path.expanduser("~/.config/m3tal/apt_gpg_passphrase")):
        try:
            with open(os.path.expanduser("~/.config/m3tal/apt_gpg_passphrase"), "r") as pf:
                default_pass = pf.read().strip()
        except Exception:
            pass

    parser.add_argument("--sign", action="store_true", help="GPG sign Release (InRelease and Release.gpg)")
    parser.add_argument("--key-id", default=os.environ.get("APT_GPG_KEY_ID") or os.environ.get("GPG_KEY_ID") or "5F84FE50A40111C981410E11775AD1473BF25102", help="GPG key ID or fingerprint to sign with")
    parser.add_argument("--passphrase", default=default_pass, help="GPG key passphrase")
    parser.add_argument("--gnupghome", help="Custom GPG home directory")

    args = parser.parse_args()

    publisher = AptPublisher(
        repo_dir=args.repo_dir,
        suite=args.suite,
        component=args.component,
        pool_style=args.pool_style,
    )

    published_files = []
    if args.debs:
        for deb in args.debs:
            print(f"📦 Publishing {deb}...")
            try:
                dest = publisher.publish_deb(
                    deb_path=deb,
                    allow_replace=args.allow_replace,
                    allow_downgrade=args.allow_downgrade,
                    skip_validation=args.skip_validation,
                )
                print(f"   [OK] Staged to {dest}")
                published_files.append(dest)
            except Exception as e:
                print(f"   [ERROR] Failed to publish {deb}: {e}", file=sys.stderr)
                sys.exit(1)

    if args.regenerate_indexes or published_files:
        print("🔄 Regenerating APT indexes...")
        try:
            info = publisher.generate_indexes(
                gpg_key_id=args.key_id,
                gpg_passphrase=args.passphrase,
                gnupghome=args.gnupghome,
                valid_until_days=args.valid_until_days,
                sign=args.sign,
            )
            print(f"✅ APT indexes updated successfully! ({info['package_count']} packages indexed for {info['architectures']})")
        except Exception as e:
            print(f"❌ Index generation failed: {e}", file=sys.stderr)
            sys.exit(2)


if __name__ == "__main__":
    main()
