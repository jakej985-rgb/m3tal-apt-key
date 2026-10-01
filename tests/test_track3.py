#!/usr/bin/env python3
"""
Comprehensive Test Suite for Track 3: Package Publishing, Metadata & Versioning
(Phases 06, 07, 08)
"""

import os
import sys
import shutil
import tempfile
import subprocess
import gzip
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from deb_version import (
    parse_debian_version,
    compare_debian_versions,
    semver_to_debian,
    debian_to_semver,
    check_upgrade_path,
    is_valid_debian_version,
)
from validate_package import (
    validate_control_fields,
    validate_debian_package,
    parse_dependency_field,
    parse_rfc822_fields,
)
from publish_package import AptPublisher, compute_file_digests


class TestDebianVersioning(unittest.TestCase):
    """Phase 08 Versioning Tests"""

    def test_version_parsing(self):
        v = parse_debian_version("2:1.4.2~rc1-3ubuntu1")
        self.assertEqual(v.epoch, 2)
        self.assertEqual(v.upstream_version, "1.4.2~rc1")
        self.assertEqual(v.debian_revision, "3ubuntu1")
        self.assertEqual(str(v), "2:1.4.2~rc1-3ubuntu1")

        v_no_epoch = parse_debian_version("1.0.0-1")
        self.assertEqual(v_no_epoch.epoch, 0)
        self.assertEqual(v_no_epoch.upstream_version, "1.0.0")
        self.assertEqual(v_no_epoch.debian_revision, "1")

        v_native = parse_debian_version("1.1.62")
        self.assertEqual(v_native.epoch, 0)
        self.assertEqual(v_native.upstream_version, "1.1.62")
        self.assertEqual(v_native.debian_revision, "")

    def test_dpkg_parity(self):
        """Test against dpkg --compare-versions directly for 100% equivalence."""
        test_cases = [
            ("1.0", "1.0", 0),
            ("1.0", "1.1", -1),
            ("1.1", "1.0", 1),
            ("1.0-1", "1.0-2", -1),
            ("1.0.0~beta1", "1.0.0", -1),
            ("1.0.0~alpha", "1.0.0~beta", -1),
            ("1.0.0~rc1-1", "1.0.0-1", -1),
            ("1.0.0-1", "1.0.0~rc1-1", 1),
            ("1.0.0+git1", "1.0.0", 1),
            ("1:1.0.0", "2.0.0", 1),
            ("2.0.0", "1:1.0.0", -1),
            ("1:1.0.0", "1:1.0.1", -1),
            ("0.9.9", "1.0.0", -1),
            ("1.1.62", "1.1.62", 0),
            ("1.1.62", "1.1.63", -1),
            ("2.0~alpha", "2.0~~alpha", 1),
        ]
        for v1, v2, expected in test_cases:
            py_res = compare_debian_versions(v1, v2)
            self.assertEqual(py_res, expected, f"Failed comparing {v1} and {v2}")

            # Verify with dpkg if installed
            r_lt = subprocess.run(["dpkg", "--compare-versions", v1, "lt", v2]).returncode == 0
            r_eq = subprocess.run(["dpkg", "--compare-versions", v1, "eq", v2]).returncode == 0
            r_gt = subprocess.run(["dpkg", "--compare-versions", v1, "gt", v2]).returncode == 0
            dpkg_expected = -1 if r_lt else (0 if r_eq else (1 if r_gt else None))
            self.assertEqual(py_res, dpkg_expected, f"dpkg mismatch for {v1} and {v2}")

    def test_semver_to_debian(self):
        # Normal
        self.assertEqual(semver_to_debian("1.2.3"), "1.2.3-1")
        # Native
        self.assertEqual(semver_to_debian("1.2.3", native=True), "1.2.3")
        # Prerelease must use ~
        self.assertEqual(semver_to_debian("1.2.3-rc.1"), "1.2.3~rc.1-1")
        self.assertEqual(semver_to_debian("2.0.0-beta.2", epoch=1), "1:2.0.0~beta.2-1")
        # Build metadata
        self.assertEqual(semver_to_debian("1.0.0+sha.abcd"), "1.0.0+sha.abcd-1")

        # Crucial sorting guarantee: 1.2.3-rc.1 < 1.2.3
        deb_rc = semver_to_debian("1.2.3-rc.1")
        deb_rel = semver_to_debian("1.2.3")
        self.assertEqual(compare_debian_versions(deb_rc, deb_rel), -1)

    def test_upgrade_path_evaluation(self):
        upg = check_upgrade_path("1.0.0", "1.1.0")
        self.assertEqual(upg["status"], "upgrade")
        self.assertTrue(upg["allowed"])

        dup = check_upgrade_path("1.1.0", "1.1.0")
        self.assertEqual(dup["status"], "identical")
        self.assertFalse(dup["allowed"])

        down = check_upgrade_path("1.1.0", "1.0.0")
        self.assertEqual(down["status"], "downgrade")
        self.assertFalse(down["allowed"])
        self.assertEqual(down["suggested_epoch_version"], "1:1.0.0")

    def test_strict_debian_version_validation(self):
        """Debian Policy §5.6.12 strict syntax checks"""
        # Leading 'v' rejected in strict mode
        self.assertFalse(is_valid_debian_version("v1.0.0"))
        self.assertFalse(is_valid_debian_version("v2.1.0-1"))
        self.assertTrue(is_valid_debian_version("1.0.0"))
        self.assertTrue(is_valid_debian_version("2.1.0-1"))

        # Colons in upstream forbidden unless epoch is present
        self.assertFalse(is_valid_debian_version("1.0:1"))
        self.assertTrue(is_valid_debian_version("1:1.0:1"))

        # Trailing hyphen / empty revision forbidden
        self.assertFalse(is_valid_debian_version("1.0.0-"))

        # Lenient parsing allows git tag stripping when explicitly requested
        parsed = parse_debian_version("v1.2.3", allow_v_prefix=True)
        self.assertEqual(parsed.upstream_version, "1.2.3")


class TestPackageMetadata(unittest.TestCase):
    """Phase 07 Package Metadata Tests"""

    def test_valid_control(self):
        ctrl = """Package: m3tal-tools
Version: 2.0.1-1
Section: utils
Priority: optional
Architecture: amd64
Maintainer: M3tal Team <ops@m3tal.io>
Depends: libc6 (>= 2.34), python3 (>= 3.10) | python3.11
Description: M3tal command line utility collection.
 A set of administration tools for managing local services.
"""
        fields = parse_rfc822_fields(ctrl)
        res = validate_control_fields(fields)
        self.assertTrue(res.is_valid, f"Validation errors: {res.errors}")
        self.assertEqual(len(res.errors), 0)

    def test_invalid_control(self):
        bad_ctrl = """Package: Invalid_Name_UpperCase
Version: v1.0.0
Section: badsection
Priority: unknownprio
Architecture: unknownarch
Maintainer: bademailformat
Depends: broken (>= bad..ver)
Description: Short description
"""
        fields = parse_rfc822_fields(bad_ctrl)
        res = validate_control_fields(fields)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Package" in e for e in res.errors))
        self.assertTrue(any("Architecture" in e for e in res.errors))
        self.assertTrue(any("Priority" in e for e in res.errors))

    def test_dependency_parsing(self):
        deps = "curl (>= 7.68.0), libssl3, docker-ce | docker.io"
        parsed = parse_dependency_field(deps)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0][0]["package"], "curl")
        self.assertEqual(parsed[0][0]["operator"], ">=")
        self.assertEqual(parsed[0][0]["version"], "7.68.0")
        # Alternative
        self.assertEqual(len(parsed[2]), 2)
        self.assertEqual(parsed[2][0]["package"], "docker-ce")
        self.assertEqual(parsed[2][1]["package"], "docker.io")


class TestPackagePublishingPipeline(unittest.TestCase):
    """Phase 06 Package Publishing & GPG Signing Tests"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_m3tal_pub_")
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_mock_deb(self, pkg_name: str, version: str, arch: str, extra_control: str = "") -> str:
        """Create a real minimal Debian binary package using dpkg-deb."""
        deb_build_dir = os.path.join(self.test_dir, f"build_{pkg_name}_{version}_{arch}")
        debian_dir = os.path.join(deb_build_dir, "DEBIAN")
        bin_dir = os.path.join(deb_build_dir, "usr", "bin")
        os.makedirs(debian_dir, exist_ok=True)
        os.chmod(debian_dir, 0o755)
        os.makedirs(bin_dir, exist_ok=True)

        control_content = f"""Package: {pkg_name}
Version: {version}
Section: utils
Priority: optional
Architecture: {arch}
Maintainer: Test Maintainer <test@m3tal.io>
Description: Test package for publication pipeline
 Automated test package.
{extra_control}
"""
        with open(os.path.join(debian_dir, "control"), "w", encoding="utf-8") as f:
            f.write(control_content)
        os.chmod(os.path.join(debian_dir, "control"), 0o644)

        test_bin = os.path.join(bin_dir, pkg_name)
        with open(test_bin, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho 'hello from test package'\n")
        os.chmod(test_bin, 0o755)

        out_deb = os.path.join(self.test_dir, f"{pkg_name}_{version}_{arch}.deb")
        res = subprocess.run(["dpkg-deb", "-b", deb_build_dir, out_deb], capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"dpkg-deb failed: {res.stderr}")
        return out_deb

    def test_publishing_flow_and_indexes(self):
        publisher = AptPublisher(
            repo_dir=self.repo_dir,
            suite="stable",
            component="main",
            pool_style="structured",
        )

        deb1 = self._create_mock_deb("m3tal-test", "1.0.0", "amd64")
        staged = publisher.publish_deb(deb1)
        self.assertTrue(os.path.isfile(staged))
        self.assertTrue("pool/main/m3tal-test/m3tal-test_1.0.0_amd64.deb" in staged)

        # Generate indexes
        info = publisher.generate_indexes(sign=False)
        self.assertEqual(info["package_count"], "1")

        # Verify Packages and Packages.gz
        pkgs_path = os.path.join(self.repo_dir, "dists", "stable", "main", "binary-amd64", "Packages")
        pkgs_gz_path = os.path.join(self.repo_dir, "dists", "stable", "main", "binary-amd64", "Packages.gz")
        self.assertTrue(os.path.isfile(pkgs_path))
        self.assertTrue(os.path.isfile(pkgs_gz_path))

        with open(pkgs_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Package: m3tal-test", content)
            self.assertIn("Version: 1.0.0", content)
            self.assertIn("Filename: pool/main/m3tal-test/m3tal-test_1.0.0_amd64.deb", content)

        # Verify Release file
        rel_path = os.path.join(self.repo_dir, "dists", "stable", "Release")
        self.assertTrue(os.path.isfile(rel_path))
        with open(rel_path, "r", encoding="utf-8") as f:
            rel_content = f.read()
            self.assertIn("Origin: M3TAL", rel_content)
            self.assertIn("Suite: stable", rel_content)
            self.assertIn("main/binary-amd64/Packages", rel_content)

        # Duplicate publication rejection test
        with self.assertRaises(ValueError) as ctx:
            publisher.publish_deb(deb1, allow_replace=False)
        self.assertIn("already exists", str(ctx.exception))

        # Downgrade rejection test
        deb_old = self._create_mock_deb("m3tal-test", "0.9.0", "amd64")
        with self.assertRaises(ValueError) as ctx:
            publisher.publish_deb(deb_old, allow_downgrade=False)
        self.assertIn("is older than latest", str(ctx.exception))

        # Multi-arch package test: Architecture 'all' appears in both amd64 and arm64
        deb_all = self._create_mock_deb("m3tal-common", "1.0.0", "all")
        publisher.publish_deb(deb_all)
        info2 = publisher.generate_indexes(architectures=["amd64", "arm64"], sign=False)

        pkgs_arm64 = os.path.join(self.repo_dir, "dists", "stable", "main", "binary-arm64", "Packages")
        self.assertTrue(os.path.isfile(pkgs_arm64))
        with open(pkgs_arm64, "r", encoding="utf-8") as f:
            arm64_content = f.read()
            # m3tal-common (all) should be present
            self.assertIn("Package: m3tal-common", arm64_content)
            # m3tal-test (amd64) should NOT be present in arm64 index
            self.assertNotIn("Package: m3tal-test", arm64_content)

    def test_custom_fields_and_valid_until(self):
        """Verify preservation of non-standard control fields and Valid-Until Release generation."""
        publisher = AptPublisher(
            repo_dir=self.repo_dir,
            suite="stable",
            component="main",
            pool_style="auto",
        )
        deb = self._create_mock_deb(
            "m3tal-addon",
            "1.5.0",
            "amd64",
            extra_control="Multi-Arch: foreign\nX-Custom-Tag: m3tal-ecosystem",
        )
        staged = publisher.publish_deb(deb)
        # Default auto pool_style should place in structured pool/main/<package>/
        self.assertIn("pool/main/m3tal-addon/m3tal-addon_1.5.0_amd64.deb", staged)

        publisher.generate_indexes(valid_until_days=7, sign=False)

        pkgs_path = os.path.join(self.repo_dir, "dists", "stable", "main", "binary-amd64", "Packages")
        with open(pkgs_path, "r", encoding="utf-8") as f:
            pkgs_data = f.read()
            self.assertIn("Multi-Arch: foreign", pkgs_data)
            self.assertIn("X-Custom-Tag: m3tal-ecosystem", pkgs_data)

        rel_path = os.path.join(self.repo_dir, "dists", "stable", "Release")
        with open(rel_path, "r", encoding="utf-8") as f:
            rel_data = f.read()
            self.assertIn("Valid-Until:", rel_data)

    def test_gpg_signing_end_to_end(self):
        """Test InRelease and Release.gpg signing and verification with temporary GPG key."""
        gpg_dir = os.path.join(self.test_dir, "gnupg")
        os.makedirs(gpg_dir, mode=0o700, exist_ok=True)

        key_params = """Key-Type: RSA
Key-Length: 2048
Name-Real: Test Signer
Name-Email: signer@m3tal.test
Expire-Date: 0
%no-protection
%commit
"""
        key_batch_file = os.path.join(self.test_dir, "genkey.batch")
        with open(key_batch_file, "w") as f:
            f.write(key_params)

        res = subprocess.run(
            ["gpg", "--homedir", gpg_dir, "--batch", "--generate-key", key_batch_file],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"GPG key generation failed: {res.stderr}")

        publisher = AptPublisher(repo_dir=self.repo_dir)
        deb = self._create_mock_deb("m3tal-sec", "1.0.0", "amd64")
        publisher.publish_deb(deb)

        # Generate and sign indexes
        publisher.generate_indexes(gnupghome=gpg_dir, sign=True)

        inrelease = os.path.join(self.repo_dir, "dists", "stable", "InRelease")
        release_gpg = os.path.join(self.repo_dir, "dists", "stable", "Release.gpg")
        release = os.path.join(self.repo_dir, "dists", "stable", "Release")

        self.assertTrue(os.path.isfile(inrelease))
        self.assertTrue(os.path.isfile(release_gpg))

        # Cryptographically verify InRelease
        verify_in = subprocess.run(
            ["gpg", "--homedir", gpg_dir, "--verify", inrelease],
            capture_output=True,
            text=True
        )
        self.assertEqual(verify_in.returncode, 0, f"InRelease signature verification failed: {verify_in.stderr}")

        # Cryptographically verify Release.gpg against Release
        verify_rel = subprocess.run(
            ["gpg", "--homedir", gpg_dir, "--verify", release_gpg, release],
            capture_output=True,
            text=True
        )
        self.assertEqual(verify_rel.returncode, 0, f"Release.gpg signature verification failed: {verify_rel.stderr}")


if __name__ == "__main__":
    unittest.main()
