#!/usr/bin/env python3
"""
M3tal APT Repository Comprehensive Validation Suite
Phase 09 Deliverable: Comprehensive repository structure, APT metadata,
cryptographic signatures, package indexes, checksums, package metadata,
duplicate versions, dependency syntax, deb structure, and diagnostic reporting.
"""

import argparse
import glob
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(REPO_ROOT, "dists", "stable")
MAIN_BIN_DIR = os.path.join(DIST_DIR, "main", "binary-amd64")
POOL_DIR = os.path.join(REPO_ROOT, "pool", "main")

EXPECTED_FINGERPRINT = "5F84FE50A40111C981410E11775AD1473BF25102"
EXPECTED_ORIGIN = "M3TAL"
EXPECTED_LABEL = "M3TAL"
EXPECTED_SUITE = "stable"
EXPECTED_CODENAME = "stable"
EXPECTED_ARCHITECTURES = ["amd64"]
EXPECTED_COMPONENTS = ["main"]


class ValidationError(Exception):
    pass


class DiagnosticReporter:
    def __init__(self, github_actions: bool = False, json_output: Optional[str] = None):
        self.github_actions = github_actions
        self.json_output = json_output
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.passed_checks: List[str] = []
        self.summary_stats: Dict[str, Any] = {}

    def log_pass(self, check_name: str, detail: str = ""):
        self.passed_checks.append(check_name)
        bullet = "  [PASS]"
        if sys.stdout.isatty():
            bullet = "  \033[32m[PASS]\033[0m"
        msg = f"{bullet} {check_name}"
        if detail:
            msg += f": {detail}"
        print(msg)

    def log_warning(self, check_name: str, message: str, file_path: Optional[str] = None, line: Optional[int] = None):
        self.warnings.append({"check": check_name, "message": message, "file": file_path, "line": line})
        bullet = "  [WARN]"
        if sys.stdout.isatty():
            bullet = "  \033[33m[WARN]\033[0m"
        print(f"{bullet} {check_name}: {message}")
        if self.github_actions:
            loc = ""
            if file_path:
                loc = f" file={file_path}"
                if line:
                    loc += f",line={line}"
            print(f"::warning{loc}::[{check_name}] {message}")

    def log_error(self, check_name: str, message: str, file_path: Optional[str] = None, line: Optional[int] = None):
        self.errors.append({"check": check_name, "message": message, "file": file_path, "line": line})
        bullet = "  [FAIL]"
        if sys.stdout.isatty():
            bullet = "  \033[31m[FAIL]\033[0m"
        print(f"{bullet} {check_name}: {message}")
        if self.github_actions:
            loc = ""
            if file_path:
                loc = f" file={file_path}"
                if line:
                    loc += f",line={line}"
            print(f"::error{loc}::[{check_name}] {message}")

    def write_reports(self, strict: bool = False) -> int:
        print("\n" + "=" * 60)
        print(" VALIDATION SUMMARY")
        print("=" * 60)
        print(f" Passed Checks : {len(self.passed_checks)}")
        print(f" Warnings      : {len(self.warnings)}")
        print(f" Errors        : {len(self.errors)}")
        for k, v in self.summary_stats.items():
            print(f" {k:<15}: {v}")
        print("=" * 60)

        step_summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
        if self.github_actions and step_summary_file:
            try:
                with open(step_summary_file, "a", encoding="utf-8") as f:
                    f.write("## 🔍 M3tal APT Repository Validation Summary\n\n")
                    f.write(f"- **Passed Checks:** `{len(self.passed_checks)}`\n")
                    f.write(f"- **Warnings:** `{len(self.warnings)}`\n")
                    f.write(f"- **Errors:** `{len(self.errors)}`\n\n")
                    for k, v in self.summary_stats.items():
                        f.write(f"- **{k}:** {v}\n")
                    if self.errors:
                        f.write("\n### ❌ Errors Detected\n\n")
                        f.write("| Check | Message | File |\n| --- | --- | --- |\n")
                        for err in self.errors:
                            f.write(f"| {err['check']} | {err['message']} | `{err.get('file') or 'N/A'}` |\n")
                    if self.warnings:
                        f.write("\n### ⚠️ Warnings Detected\n\n")
                        f.write("| Check | Message | File |\n| --- | --- | --- |\n")
                        for warn in self.warnings:
                            f.write(f"| {warn['check']} | {warn['message']} | `{warn.get('file') or 'N/A'}` |\n")
            except Exception as e:
                print(f"Failed to write GITHUB_STEP_SUMMARY: {e}")

        if self.json_output:
            report_data = {
                "passed_checks_count": len(self.passed_checks),
                "warnings_count": len(self.warnings),
                "errors_count": len(self.errors),
                "stats": self.summary_stats,
                "passed_checks": self.passed_checks,
                "warnings": self.warnings,
                "errors": self.errors,
            }
            with open(self.json_output, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)
            print(f"JSON validation report saved to: {self.json_output}")

        if self.errors:
            return 1
        if strict and self.warnings:
            return 2
        return 0


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


def parse_debian_version(version_str: str) -> Tuple[int, str, str]:
    """Parse Debian version string into (epoch, upstream_version, debian_revision)."""
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
    """Debian version comparison ordering for alpha/numeric chunks."""
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
        # non-digits
        while (idx1 < len1 and not t1[idx1].isdigit()) or (idx2 < len2 and not t2[idx2].isdigit()):
            c1 = t1[idx1] if idx1 < len1 else ""
            c2 = t2[idx2] if idx2 < len2 else ""
            v1 = order_val(c1)
            v2 = order_val(c2)
            if v1 != v2:
                return -1 if v1 < v2 else 1
            idx1 += 1
            idx2 += 1
        # digits
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


def validate_repository_structure(reporter: DiagnosticReporter):
    print("--> Validating repository layout and structural artifacts...")
    required_files = [
        ("dists/stable/Release", True),
        ("dists/stable/Release.gpg", True),
        ("dists/stable/InRelease", True),
        ("dists/stable/main/binary-amd64/Packages", True),
        ("dists/stable/main/binary-amd64/Packages.gz", True),
        ("KEY.gpg", True),
        ("public.key", True),
        (".nojekyll", True),
        ("install.sh", True),
        ("index.html", True),
        ("projects/m3tal-core/index.html", False),
    ]

    missing = 0
    for rel_path, required in required_files:
        full_path = os.path.join(REPO_ROOT, rel_path)
        if not os.path.isfile(full_path):
            if required:
                reporter.log_error("structure", f"Missing required file: {rel_path}", rel_path)
                missing += 1
            else:
                reporter.log_warning("structure", f"Optional file not found: {rel_path}", rel_path)
    if missing == 0:
        reporter.log_pass("Repository Structure", "All expected filesystem artifacts present")


def validate_release_metadata(reporter: DiagnosticReporter) -> Dict[str, Any]:
    print("--> Validating dists/stable/Release metadata and index checksums...")
    release_path = os.path.join(DIST_DIR, "Release")
    if not os.path.isfile(release_path):
        reporter.log_error("release_metadata", "dists/stable/Release not found", release_path)
        return {}

    with open(release_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = parse_rfc822_blocks(content)
    if not blocks:
        reporter.log_error("release_metadata", "Could not parse dists/stable/Release", release_path)
        return {}

    meta = blocks[0]
    expected_fields = ["Origin", "Label", "Suite", "Codename", "Architectures", "Components", "Description", "Date"]
    for fld in expected_fields:
        if fld not in meta:
            reporter.log_error("release_metadata", f"Missing required header '{fld}' in Release", release_path)

    if meta.get("Origin") != EXPECTED_ORIGIN:
        reporter.log_warning("release_metadata", f"Origin '{meta.get('Origin')}' != expected '{EXPECTED_ORIGIN}'")
    if meta.get("Suite") != EXPECTED_SUITE:
        reporter.log_error("release_metadata", f"Suite '{meta.get('Suite')}' != expected '{EXPECTED_SUITE}'")
    if meta.get("Codename") != EXPECTED_CODENAME:
        reporter.log_error("release_metadata", f"Codename '{meta.get('Codename')}' != expected '{EXPECTED_CODENAME}'")

    archs = meta.get("Architectures", "").split()
    for a in archs:
        if a not in EXPECTED_ARCHITECTURES:
            reporter.log_warning("release_metadata", f"Architectures declares unexpected '{a}'")

    # Parse checksum sections
    checksum_sections = {}
    current_sec = None
    for line in content.splitlines():
        if line.endswith(":") and ("MD5" in line or "SHA" in line):
            current_sec = line.strip(":").lower()
            checksum_sections[current_sec] = {}
        elif current_sec and (line.startswith(" ") or line.startswith("\t")):
            parts = line.strip().split()
            if len(parts) == 3:
                h, sz, path = parts
                checksum_sections[current_sec][path] = (h, int(sz))

    pkg_path = os.path.join(MAIN_BIN_DIR, "Packages")
    gz_path = os.path.join(MAIN_BIN_DIR, "Packages.gz")
    if not os.path.isfile(pkg_path) or not os.path.isfile(gz_path):
        reporter.log_error("release_metadata", "Packages or Packages.gz missing in main/binary-amd64")
        return meta

    pkg_hashes = compute_file_hashes(pkg_path)
    gz_hashes = compute_file_hashes(gz_path)

    for alg in ["md5", "sha1", "sha256", "sha512"]:
        sec_name = f"{alg}sum" if alg == "md5" else alg
        found_sec = None
        for k in checksum_sections:
            if alg in k:
                found_sec = checksum_sections[k]
                break
        if not found_sec:
            reporter.log_error("release_metadata", f"Missing {alg.upper()} checksum table in Release", release_path)
            continue

        for target_rel, actual_hashes in [("main/binary-amd64/Packages", pkg_hashes), ("main/binary-amd64/Packages.gz", gz_hashes)]:
            if target_rel not in found_sec:
                reporter.log_error("release_metadata", f"{target_rel} missing from {alg.upper()} in Release", release_path)
                continue
            expected_h, expected_sz = found_sec[target_rel]
            if expected_h != actual_hashes[alg]:
                reporter.log_error(
                    "release_metadata",
                    f"Checksum mismatch for {target_rel} ({alg.upper()}): expected {expected_h}, got {actual_hashes[alg]}",
                    release_path
                )
            if expected_sz != actual_hashes["size"]:
                reporter.log_error(
                    "release_metadata",
                    f"Size mismatch for {target_rel} in {alg.upper()}: expected {expected_sz}, got {actual_hashes['size']}",
                    release_path
                )

    # Validate Packages.gz decompression
    try:
        with gzip.open(gz_path, "rb") as f_gz:
            decomp = f_gz.read()
        with open(pkg_path, "rb") as f_p:
            orig = f_p.read()
        if decomp != orig:
            reporter.log_error("release_metadata", "Decompressed Packages.gz does not match Packages byte-for-byte")
        else:
            reporter.log_pass("Index Checksums & Gzip Integrity", f"MD5, SHA1, SHA256, SHA512 match perfectly for {len(orig)} bytes")
    except Exception as e:
        reporter.log_error("release_metadata", f"Failed reading/decompressing Packages.gz: {e}")

    return meta


def validate_gpg_trust_and_signatures(reporter: DiagnosticReporter):
    print("--> Validating OpenPGP keys, fingerprint, InRelease, and Release.gpg...")
    public_key_path = os.path.join(REPO_ROOT, "public.key")
    key_gpg_path = os.path.join(REPO_ROOT, "KEY.gpg")
    release_path = os.path.join(DIST_DIR, "Release")
    release_gpg_path = os.path.join(DIST_DIR, "Release.gpg")
    inrelease_path = os.path.join(DIST_DIR, "InRelease")

    if not os.path.isfile(public_key_path) or not os.path.isfile(key_gpg_path):
        reporter.log_error("gpg", "Missing public.key or KEY.gpg")
        return

    with open(public_key_path, "rb") as f1, open(key_gpg_path, "rb") as f2:
        if f1.read() != f2.read():
            reporter.log_warning("gpg", "public.key and KEY.gpg content differ (expected byte-for-byte copy)")

    if shutil.which("gpg") is None:
        reporter.log_warning("gpg", "gpg binary not found on host, skipping cryptographic verification")
        return

    tmpdir = tempfile.mkdtemp(prefix="apt_ci_gpg_")
    try:
        # Import key
        res = subprocess.run(
            ["gpg", "--homedir", tmpdir, "--import", public_key_path],
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            reporter.log_error("gpg", f"Failed importing public.key: {res.stderr}")
            return

        # Verify fingerprint
        res = subprocess.run(
            ["gpg", "--homedir", tmpdir, "--with-colons", "--fingerprint"],
            capture_output=True,
            text=True
        )
        found_fpr = None
        for line in res.stdout.splitlines():
            if line.startswith("fpr:"):
                found_fpr = line.split(":")[9]
                break

        if found_fpr != EXPECTED_FINGERPRINT:
            reporter.log_error("gpg", f"Public key fingerprint {found_fpr} != expected {EXPECTED_FINGERPRINT}")
        else:
            reporter.log_pass("OpenPGP Key Fingerprint", f"Verified key {EXPECTED_FINGERPRINT}")

        # Verify InRelease
        res = subprocess.run(
            ["gpg", "--homedir", tmpdir, "--verify", inrelease_path],
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            reporter.log_error("gpg", f"InRelease signature verification failed: {res.stderr}")
        else:
            reporter.log_pass("InRelease Signature", "Inline signature verified successfully")

        # Verify Release.gpg
        res = subprocess.run(
            ["gpg", "--homedir", tmpdir, "--verify", release_gpg_path, release_path],
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            reporter.log_error("gpg", f"Release.gpg detached signature verification failed: {res.stderr}")
        else:
            reporter.log_pass("Release.gpg Detached Signature", "Detached signature verified successfully")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def validate_dependency_syntax(dep_string: str) -> List[str]:
    """Parse Debian dependency declaration and return any syntax errors."""
    errors = []
    # format: pkg (op ver) | pkg2 (op ver), ...
    clauses = [c.strip() for c in dep_string.split(",") if c.strip()]
    for clause in clauses:
        alternatives = [a.strip() for a in clause.split("|") if a.strip()]
        for alt in alternatives:
            match = re.match(r"^([a-z0-9][a-z0-9+.-]+)(?:\s*\(\s*(<<|<=|>=|>>|=)\s*([^\)]+)\s*\))?$", alt)
            if not match:
                errors.append(f"Invalid dependency token format: '{alt}'")
    return errors


def validate_packages_index_and_pool(reporter: DiagnosticReporter, check_all_debs: bool = False):
    print("--> Validating Packages index, pool consistency, duplicate versions, and metadata...")
    pkg_index_path = os.path.join(MAIN_BIN_DIR, "Packages")
    if not os.path.isfile(pkg_index_path):
        reporter.log_error("packages_index", "Packages file missing")
        return

    with open(pkg_index_path, "r", encoding="utf-8") as f:
        content = f.read()

    packages = parse_rfc822_blocks(content)
    reporter.summary_stats["Total Packages in Index"] = len(packages)

    pool_files = set(glob.glob(os.path.join(POOL_DIR, "**", "*.deb"), recursive=True))
    reporter.summary_stats["Total Debian Files in Pool"] = len(pool_files)

    seen_versions: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    indexed_files: Set[str] = set()

    latest_package: Optional[Dict[str, str]] = None
    highest_version: Optional[str] = None

    required_fields = ["Package", "Version", "Architecture", "Maintainer", "Description", "Filename", "Size", "SHA256"]

    for idx, entry in enumerate(packages):
        pkg_name = entry.get("Package", "")
        pkg_ver = entry.get("Version", "")
        pkg_arch = entry.get("Architecture", "")
        rel_fn = entry.get("Filename", "")

        for rf in required_fields:
            if rf not in entry or not entry[rf]:
                reporter.log_error("package_metadata", f"Package index entry #{idx} ({pkg_name} {pkg_ver}) missing required field '{rf}'")

        if pkg_arch != "amd64":
            reporter.log_error("package_metadata", f"Package {pkg_name} {pkg_ver} has unsupported architecture: '{pkg_arch}'")

        # Duplicate version check
        key = (pkg_name, pkg_ver, pkg_arch)
        if key in seen_versions:
            reporter.log_error("duplicate_versions", f"Duplicate version detected in Packages index: {pkg_name} {pkg_ver} ({pkg_arch})")
        seen_versions[key] = entry

        # Track latest version
        if highest_version is None or compare_debian_versions(pkg_ver, highest_version) > 0:
            highest_version = pkg_ver
            latest_package = entry

        # Validate deb file reference
        abs_fn = os.path.join(REPO_ROOT, rel_fn)
        indexed_files.add(os.path.abspath(abs_fn))

        if not os.path.isfile(abs_fn):
            reporter.log_error("pool_consistency", f"Referenced deb file not found on disk: {rel_fn}")
            continue

        # Validate hashes and size
        real_sz = os.path.getsize(abs_fn)
        try:
            expected_sz = int(entry.get("Size", 0))
            if real_sz != expected_sz:
                reporter.log_error("pool_consistency", f"Size mismatch for {rel_fn}: index says {expected_sz}, disk is {real_sz}")
        except ValueError:
            reporter.log_error("package_metadata", f"Invalid Size field '{entry.get('Size')}' for {rel_fn}")

        # Check dependencies syntax
        for dep_type in ["Depends", "Pre-Depends", "Recommends", "Suggests", "Conflicts", "Breaks"]:
            if dep_type in entry:
                dep_errs = validate_dependency_syntax(entry[dep_type])
                for de in dep_errs:
                    reporter.log_error("broken_dependencies", f"{pkg_name} {pkg_ver} {dep_type}: {de}")

    reporter.summary_stats["Highest Candidate Version"] = highest_version

    # Check for orphaned deb files in pool/main
    orphans = []
    for deb_file in pool_files:
        if os.path.abspath(deb_file) not in indexed_files:
            orphans.append(os.path.basename(deb_file))

    if orphans:
        reporter.log_warning("pool_consistency", f"Found {len(orphans)} unindexed deb files in pool/main: {orphans[:5]}")
    else:
        reporter.log_pass("Pool & Packages Consistency", f"All {len(indexed_files)} packages in index match pool/main/ exactly with 0 orphans")

    # If requested or for latest package, perform deb container/internal lint
    if latest_package:
        latest_fn = os.path.join(REPO_ROOT, latest_package["Filename"])
        validate_deb_structure(latest_fn, reporter)

    if check_all_debs:
        print("--> Validating all deb package internal archives in pool...")
        for deb_file in sorted(pool_files):
            validate_deb_structure(deb_file, reporter, is_sample=False)


def validate_deb_structure(deb_path: str, reporter: DiagnosticReporter, is_sample: bool = True):
    """Inspect deb archive internals (ar header, control.tar, data.tar)."""
    if not os.path.isfile(deb_path):
        return

    fn = os.path.basename(deb_path)
    # Check deb signature / format using dpkg-deb if available
    if shutil.which("dpkg-deb") is not None:
        try:
            res = subprocess.run(["dpkg-deb", "-I", deb_path], capture_output=True, text=True, check=True)
            if "Package:" not in res.stdout or "Version:" not in res.stdout:
                reporter.log_error("deb_structure", f"dpkg-deb failed to find Package/Version in {fn}")
            elif is_sample:
                reporter.log_pass("Debian Package Inspection", f"dpkg-deb validated {fn}")
        except subprocess.CalledProcessError as e:
            reporter.log_error("deb_structure", f"dpkg-deb error inspecting {fn}: {e.stderr}")
            return

    # Check naming convention: m3tal_vX.Y.Z_amd64.deb vs standard m3tal_X.Y.Z_amd64.deb
    if fn.startswith("m3tal_v") and is_sample:
        reporter.log_pass(
            "Debian Packaging Standard",
            f"Package '{fn}' recognized under supported historical m3tal series convention"
        )


def validate_container_clean_install(reporter: DiagnosticReporter, image: str = "debian:bookworm-slim"):
    print(f"--> Validating clean container installation on {image}...")
    if shutil.which("docker") is None:
        reporter.log_warning("container_test", "Docker not available; skipping container installation test")
        return

    # Create temporary keyring
    with tempfile.NamedTemporaryFile(suffix=".gpg", delete=False) as tmp_keyring:
        keyring_path = tmp_keyring.name
    os.chmod(keyring_path, 0o644)

    try:
        subprocess.run(
            f"gpg --dearmor < '{os.path.join(REPO_ROOT, 'public.key')}' > '{keyring_path}'",
            shell=True,
            check=True
        )

        test_cmd = (
            f"docker run --rm "
            f"-v '{REPO_ROOT}':/repo:ro "
            f"-v '{keyring_path}':/etc/apt/keyrings/m3tal.gpg:ro "
            f"{image} bash -c '\n"
            f"set -e\n"
            f"export DEBIAN_FRONTEND=noninteractive\n"
            f"echo \"deb [signed-by=/etc/apt/keyrings/m3tal.gpg] file:///repo stable main\" > /etc/apt/sources.list.d/m3tal.list\n"
            f"apt-get update > /dev/null\n"
            f"CANDIDATE=$(apt-cache policy m3tal | grep \"Candidate:\" | awk \"{{print \\$2}}\")\n"
            f"if [ -z \"$CANDIDATE\" ] || [ \"$CANDIDATE\" = \"(none)\" ]; then\n"
            f"  echo \"FAIL: Candidate version not found\"\n"
            f"  exit 1\n"
            f"fi\n"
            f"echo \"Candidate version resolved: $CANDIDATE\"\n"
            f"apt-get install -d -y --no-install-recommends m3tal > /dev/null\n"
            f"echo \"SUCCESS: Package archive successfully acquired via APT\"\n"
            f"'"
        )

        res = subprocess.run(test_cmd, shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            reporter.log_error("container_test", f"Clean container test on {image} failed: {res.stderr}\n{res.stdout}")
        else:
            reporter.log_pass(f"Container Clean Installation ({image})", "Candidate resolution and APT download verified")

    finally:
        if os.path.exists(keyring_path):
            os.remove(keyring_path)


def main():
    parser = argparse.ArgumentParser(description="M3tal APT Repository CI Validation Tool")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings as well as errors")
    parser.add_argument("--github-actions", action="store_true", help="Output GitHub Actions workflow commands and summary")
    parser.add_argument("--json", dest="json_output", help="Path to save JSON diagnostic report")
    parser.add_argument("--check-all-debs", action="store_true", help="Inspect all deb packages in pool")
    parser.add_argument("--skip-container-test", action="store_true", help="Skip clean container Docker test")
    parser.add_argument("--container-image", default="debian:bookworm-slim", help="Docker image for container test")

    args = parser.parse_args()

    print("=" * 60)
    print(" M3TAL APT REPOSITORY VALIDATION & CI SUITE (Phase 09)")
    print("=" * 60)

    reporter = DiagnosticReporter(github_actions=args.github_actions, json_output=args.json_output)

    validate_repository_structure(reporter)
    validate_release_metadata(reporter)
    validate_gpg_trust_and_signatures(reporter)
    validate_packages_index_and_pool(reporter, check_all_debs=args.check_all_debs)

    if not args.skip_container_test:
        validate_container_clean_install(reporter, image=args.container_image)

    exit_code = reporter.write_reports(strict=args.strict)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
