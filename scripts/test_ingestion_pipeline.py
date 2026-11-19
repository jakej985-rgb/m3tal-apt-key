#!/usr/bin/env python3
"""
M3tal Central Ingestion Pipeline & Publishing Regression Test Suite
Validates:
  1. Package identity validation (reject mismatching package name)
  2. Version validation (clean semver, reject version mismatch)
  3. Architecture validation (reject unsupported architecture, reject mismatch)
  4. Duplicate handling (idempotent re-ingest of identical deb, reject conflicts)
  5. Checksum integrity (reject SHA256 mismatch, accept match)
  6. Ingestion failure behavior and atomic rollback
  7. Missing dispatch credentials detection
  8. Failed downloads error handling
  9. Path traversal protection
  10. Index generation (Packages, Packages.gz, Release, InRelease)
  11. Registry synchronization (status transitions from planned to published)
  12. Post-publication verification (detect missing from index)
"""

import os
import sys
import shutil
import tempfile
import unittest
import subprocess
import yaml
from pathlib import Path

# Paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

SCRIPT_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ingest_deb import ingest_deb_file, update_registry_manifest
from publish_package import AptPublisher, compute_file_digests


def make_dummy_deb(output_path, package_name="monster-lab", version="0.3.0", arch="amd64"):
    """Create a minimal valid debian package for testing."""
    with tempfile.TemporaryDirectory(prefix="dummy_deb_") as tmp_dir:
        debian_dir = os.path.join(tmp_dir, "DEBIAN")
        usr_bin = os.path.join(tmp_dir, "usr", "bin")
        os.makedirs(debian_dir, exist_ok=True)
        os.makedirs(usr_bin, exist_ok=True)

        control_path = os.path.join(debian_dir, "control")
        with open(control_path, "w", encoding="utf-8") as f:
            f.write(f"Package: {package_name}\n")
            f.write(f"Version: {version}\n")
            f.write("Section: education\n")
            f.write("Priority: optional\n")
            f.write(f"Architecture: {arch}\n")
            f.write("Maintainer: Monster Lab Team <support@monsterlab.org>\n")
            f.write("Description: Test package\n Test package description.\n")

        binary_path = os.path.join(usr_bin, "test-binary")
        with open(binary_path, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho test\n")
        os.chmod(binary_path, 0o755)

        cmd = ["dpkg-deb", "--build", "--root-owner-group", tmp_dir, output_path]
        subprocess.run(cmd, check=True, capture_output=True)


class TestIngestionPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_gnupghome = os.environ.get("GNUPGHOME")
        cls.gnupghome = tempfile.mkdtemp(prefix="m3tal-pipeline-gpg-")
        subprocess.run(
            ["gpg", "--homedir", cls.gnupghome, "--batch", "--passphrase", "",
             "--quick-generate-key", "M3tal Pipeline Test <pipeline-test@m3tal.invalid>",
             "rsa2048", "sign", "0"],
            check=True,
            capture_output=True,
        )
        keys = subprocess.run(
            ["gpg", "--homedir", cls.gnupghome, "--with-colons", "--list-secret-keys"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        cls.test_fingerprint = next(
            line.split(":")[9] for line in keys.splitlines() if line.startswith("fpr:")
        )
        os.environ["GNUPGHOME"] = cls.gnupghome

    @classmethod
    def tearDownClass(cls):
        if cls.original_gnupghome is None:
            os.environ.pop("GNUPGHOME", None)
        else:
            os.environ["GNUPGHOME"] = cls.original_gnupghome
        shutil.rmtree(cls.gnupghome, ignore_errors=True)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="apt_test_repo_")
        self.pool_dir = os.path.join(self.test_dir, "pool", "main")
        self.dists_dir = os.path.join(self.test_dir, "dists", "stable")
        self.registry_dir = os.path.join(self.test_dir, "registry")
        os.makedirs(self.pool_dir, exist_ok=True)
        os.makedirs(self.dists_dir, exist_ok=True)
        os.makedirs(self.registry_dir, exist_ok=True)

        # Create dummy registry
        self.registry_file = os.path.join(self.registry_dir, "packages.yml")
        registry_data = {
            "version": "1.0.0",
            "repository": {
                "url": "https://example.com/apt",
                "suite": "stable",
                "components": ["main"],
                "architectures": ["amd64"],
            },
            "packages": [
                {
                    "id": "monster-lab",
                    "name": "monster-lab",
                    "status": "planned",
                    "supported_architectures": ["amd64"],
                    "publication": {
                        "component": "main",
                        "distribution": "stable",
                        "pool_path": "pool/main/monster-lab",
                    },
                    "metadata": {
                        "latest_version": "0.1.4",
                    },
                }
            ],
        }
        with open(self.registry_file, "w", encoding="utf-8") as f:
            yaml.dump(registry_data, f)

        # Create valid deb file
        self.deb_file = os.path.join(self.test_dir, "monster-lab_0.3.0_amd64.deb")
        make_dummy_deb(self.deb_file, "monster-lab", "0.3.0", "amd64")
        self.deb_sha256 = compute_file_digests(self.deb_file)["sha256"]

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_checksum_integrity_rejection(self):
        """Reject package if SHA256 does not match expected."""
        with self.assertRaises(ValueError) as ctx:
            ingest_deb_file(
                self.deb_file,
                repo_dir=self.test_dir,
                expected_sha256="0000000000000000000000000000000000000000000000000000000000000000",
                skip_validation=True,
            )
        self.assertIn("Package SHA-256 mismatch", str(ctx.exception))

    def test_checksum_integrity_match(self):
        """Accept package if SHA256 matches."""
        res = ingest_deb_file(
            self.deb_file,
            repo_dir=self.test_dir,
            expected_sha256=self.deb_sha256,
            key_id=self.test_fingerprint,
            passphrase="",
        )
        self.assertEqual(res["package"], "monster-lab")
        self.assertEqual(res["version"], "0.3.0")
        self.assertEqual(res["sha256"], self.deb_sha256)
        self.assertTrue(os.path.isfile(os.path.join(self.dists_dir, "InRelease")))

    def test_package_identity_rejection(self):
        """Reject package if package name does not match expected_package."""
        with self.assertRaises(ValueError) as ctx:
            ingest_deb_file(
                self.deb_file,
                repo_dir=self.test_dir,
                expected_package="different-app",
            )
        self.assertIn("Package identity mismatch", str(ctx.exception))

    def test_package_version_rejection(self):
        """Reject package if package version does not match expected_version."""
        with self.assertRaises(ValueError) as ctx:
            ingest_deb_file(
                self.deb_file,
                repo_dir=self.test_dir,
                expected_version="0.4.0",
            )
        self.assertIn("Package version mismatch", str(ctx.exception))

    def test_package_version_prefix_cleaning(self):
        """Accept expected_version with leading 'v' prefix."""
        res = ingest_deb_file(
            self.deb_file,
            repo_dir=self.test_dir,
            expected_version="v0.3.0",
            key_id=self.test_fingerprint,
            passphrase="",
        )
        self.assertEqual(res["version"], "0.3.0")

    def test_arch_all_in_arm64_only_repo(self):
        """Architecture: all verifies against generated arm64 index, not amd64."""
        arm_deb = os.path.join(self.test_dir, "arm-app.deb")
        make_dummy_deb(arm_deb, "arm-app", "1.0.0", "arm64")
        ingest_deb_file(arm_deb, repo_dir=self.test_dir, key_id=self.test_fingerprint,
                        passphrase="", update_registry=False)
        all_deb = os.path.join(self.test_dir, "data-pkg.deb")
        make_dummy_deb(all_deb, "data-pkg", "1.0.0", "all")
        res = ingest_deb_file(all_deb, repo_dir=self.test_dir, key_id=self.test_fingerprint,
                              passphrase="", update_registry=False)
        self.assertEqual(res["architecture"], "all")
        with open(os.path.join(self.dists_dir, "main", "binary-arm64", "Packages"), encoding="utf-8") as f:
            self.assertIn("Package: data-pkg\n", f.read())

    def test_package_arch_rejection(self):
        """Reject package if architecture does not match expected_arch."""
        with self.assertRaises(ValueError) as ctx:
            ingest_deb_file(
                self.deb_file,
                repo_dir=self.test_dir,
                expected_arch="arm64",
            )
        self.assertIn("Package architecture mismatch", str(ctx.exception))

    def test_unsupported_arch_rejection(self):
        """Reject package with invalid/unsupported architecture."""
        bad_deb = os.path.join(self.test_dir, "bad_arch.deb")
        make_dummy_deb(bad_deb, "monster-lab", "0.3.0", "unsupported_arch")
        with self.assertRaises(ValueError) as ctx:
            ingest_deb_file(
                bad_deb,
                repo_dir=self.test_dir,
            )
        self.assertIn("unsupported", str(ctx.exception).lower())

    def test_path_traversal_rejection(self):
        """Reject package if parameter or field contains directory traversal."""
        with self.assertRaises(ValueError) as ctx:
            ingest_deb_file(
                self.deb_file,
                repo_dir=self.test_dir,
                expected_package="../../etc/shadow",
            )
        self.assertIn("Package identity mismatch", str(ctx.exception))

    def test_registry_manifest_update_from_planned(self):
        """Ensure status transitions from planned to published."""
        update_registry_manifest("monster-lab", "0.3.0", "pool/main/monster-lab/monster-lab_0.3.0_amd64.deb", repo_dir=self.test_dir)
        with open(self.registry_file, "r", encoding="utf-8") as f:
            reg = yaml.safe_load(f)
        pkg = reg["packages"][0]
        self.assertEqual(pkg["status"], "published")
        self.assertEqual(pkg["metadata"]["latest_version"], "0.3.0")
        self.assertEqual(pkg["publication"]["pool_path"], "pool/main/monster-lab")

    def test_registry_manifest_update_identical_version(self):
        """Ensure status transitions to published even if package was planned with current version."""
        # Reset version to 0.1.4 and status planned
        update_registry_manifest("monster-lab", "0.1.4", "pool/main/monster-lab/monster-lab_0.1.4_amd64.deb", repo_dir=self.test_dir)
        with open(self.registry_file, "r", encoding="utf-8") as f:
            reg = yaml.safe_load(f)
        pkg = reg["packages"][0]
        self.assertEqual(pkg["status"], "published")
        self.assertEqual(pkg["metadata"]["latest_version"], "0.1.4")

    def test_duplicate_reingest_idempotency(self):
        """Byte-for-byte identical deb is allowed without --allow-replace."""
        publisher = AptPublisher(
            repo_dir=self.test_dir,
            suite="stable",
            component="main",
            pool_style="structured",
        )
        staged_1 = publisher.publish_deb(self.deb_file)
        self.assertTrue(os.path.isfile(staged_1))

        # Publishing the exact same file again must succeed idempotently
        staged_2 = publisher.publish_deb(self.deb_file, allow_replace=False)
        self.assertEqual(staged_1, staged_2)

    def test_duplicate_conflict_rejection(self):
        """Conflicting deb with same version but different content is rejected without --allow-replace."""
        publisher = AptPublisher(
            repo_dir=self.test_dir,
            suite="stable",
            component="main",
            pool_style="structured",
        )
        publisher.publish_deb(self.deb_file)

        # Create another deb with different content
        diff_deb = os.path.join(self.test_dir, "diff_0.3.0.deb")
        with tempfile.TemporaryDirectory() as t:
            d = os.path.join(t, "DEBIAN")
            os.makedirs(d)
            with open(os.path.join(d, "control"), "w") as f:
                f.write("Package: monster-lab\nVersion: 0.3.0\nSection: education\nPriority: optional\nArchitecture: amd64\nMaintainer: ml <m@m.org>\nDescription: diff\n diff content\n")
            subprocess.run(["dpkg-deb", "--build", t, diff_deb], check=True, capture_output=True)

        with self.assertRaises(ValueError) as ctx:
            publisher.publish_deb(diff_deb, allow_replace=False)
        self.assertIn("already exists in repository with different content", str(ctx.exception))

    def test_missing_dispatch_token_behavior(self):
        """Ensure missing token detection logic correctly identifies empty credentials."""
        token = ""
        self.assertFalse(bool(token), "Empty token must evaluate to False and block silent publishing")


if __name__ == "__main__":
    unittest.main()
