#!/usr/bin/env python3
"""
Unit and Integration Test Suite for M3tal Package Retention Engine
Tests version parsing, ordering, policy rules, safety guards,
snapshot generation, and metadata regeneration in an isolated sandbox.
"""

import gzip
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import manage_retention

from manage_retention import (
    VersionKey,
    build_inventory,
    compare_debian_versions,
    create_snapshot,
    execute_prune,
    extract_series,
    load_policy,
    parse_debian_version,
    regenerate_repository_indexes,
)


class TestDebianVersionParsing(unittest.TestCase):
    def test_basic_version_parsing(self):
        epoch, upstream, revision = parse_debian_version("1.1.62")
        self.assertEqual(epoch, 0)
        self.assertEqual(upstream, "1.1.62")
        self.assertEqual(revision, "0")

    def test_epoch_and_revision(self):
        epoch, upstream, revision = parse_debian_version("2:1.0.4-1ubuntu2")
        self.assertEqual(epoch, 2)
        self.assertEqual(upstream, "1.0.4")
        self.assertEqual(revision, "1ubuntu2")

    def test_debian_version_comparison(self):
        self.assertTrue(compare_debian_versions("1.0.1", "1.0.2") < 0)
        self.assertTrue(compare_debian_versions("1.1.0", "1.0.60") > 0)
        self.assertTrue(compare_debian_versions("1.1.9", "1.1.10") < 0)
        self.assertTrue(compare_debian_versions("1.1.62", "1.1.62") == 0)
        self.assertTrue(compare_debian_versions("1.0.0~beta1", "1.0.0") < 0)

    def test_extract_series(self):
        self.assertEqual(extract_series("1.0.0"), "1.0")
        self.assertEqual(extract_series("1.1.62"), "1.1")
        self.assertEqual(extract_series("2.0.0-beta"), "2.0")


class TestRetentionPolicyLogic(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "keep_recent_per_series": 3,
            "min_retained_packages": 4,
            "protected_series": ["1.1", "1.0"],
            "pinned_versions": ["1.0.0", "1.1.0"],
            "snapshot": {"enabled": True},
            "deprecation": {"archive_obsolete": False}
        }

    def test_load_policy_defaults(self):
        pol = load_policy("/nonexistent/path/policy.json")
        self.assertIn("keep_recent_per_series", pol)
        self.assertIn("pinned_versions", pol)


class TestMockRepositoryPruning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_gnupghome = os.environ.get("GNUPGHOME")
        cls.original_key_id = os.environ.get("APT_GPG_KEY_ID")
        cls.gnupghome = tempfile.mkdtemp(prefix="m3tal-retention-gpg-")
        subprocess.run(
            ["gpg", "--homedir", cls.gnupghome, "--batch", "--passphrase", "", "--quick-generate-key",
             "M3tal Retention Test <retention-test@m3tal.invalid>", "rsa2048", "sign", "0"],
            check=True,
            capture_output=True,
        )
        keys = subprocess.run(
            ["gpg", "--homedir", cls.gnupghome, "--with-colons", "--list-secret-keys"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        cls.test_fingerprint = next(line.split(":")[9] for line in keys.splitlines() if line.startswith("fpr:"))
        os.environ["GNUPGHOME"] = cls.gnupghome
        os.environ["APT_GPG_KEY_ID"] = cls.test_fingerprint

    @classmethod
    def tearDownClass(cls):
        if cls.original_gnupghome is None:
            os.environ.pop("GNUPGHOME", None)
        else:
            os.environ["GNUPGHOME"] = cls.original_gnupghome
        if cls.original_key_id is None:
            os.environ.pop("APT_GPG_KEY_ID", None)
        else:
            os.environ["APT_GPG_KEY_ID"] = cls.original_key_id
        shutil.rmtree(cls.gnupghome, ignore_errors=True)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="m3tal_retention_test_")
        self.dist_dir = os.path.join(self.test_dir, "dists", "stable")
        self.bin_dir = os.path.join(self.dist_dir, "main", "binary-amd64")
        self.pool_dir = os.path.join(self.test_dir, "pool", "main")
        os.makedirs(self.bin_dir, exist_ok=True)
        os.makedirs(self.pool_dir, exist_ok=True)

        # Create valid tiny deb files so the authoritative publisher can rebuild
        # Packages from the pool rather than trusting stale index records.
        self.versions = [
            "1.0.0", "1.0.1", "1.0.2", "1.0.3",  # Series 1.0 (1.0.0 pinned, top 2 are 1.0.3, 1.0.2)
            "1.1.0", "1.1.1", "1.1.2", "1.1.3", "1.1.4"  # Series 1.1 (top 2 are 1.1.4, 1.1.3; 1.1.0 pinned)
        ]

        entries = []
        for ver in self.versions:
            deb_name = f"m3tal_v{ver}_amd64.deb"
            deb_path = os.path.join(self.pool_dir, deb_name)
            build_dir = tempfile.mkdtemp(prefix="deb-build-", dir=self.test_dir)
            os.makedirs(os.path.join(build_dir, "DEBIAN"))
            os.makedirs(os.path.join(build_dir, "usr", "share", "m3tal"))
            control = (
                "Package: m3tal\n"
                f"Version: {ver}\n"
                "Architecture: amd64\n"
                "Maintainer: Test <test@m3tal.io>\n"
                "Description: Test package\n"
            )
            with open(os.path.join(build_dir, "DEBIAN", "control"), "w", encoding="utf-8") as f:
                f.write(control)
            with open(os.path.join(build_dir, "usr", "share", "m3tal", "version"), "w", encoding="utf-8") as f:
                f.write(ver + "\n")
            subprocess.run(["dpkg-deb", "--build", build_dir, deb_path], check=True, capture_output=True)
            shutil.rmtree(build_dir)
            with open(deb_path, "rb") as f:
                deb_bytes = f.read()
            sz = os.path.getsize(deb_path)
            md5_h = hashlib.md5(deb_bytes).hexdigest()
            sha256_h = hashlib.sha256(deb_bytes).hexdigest()

            entry = (
                f"Package: m3tal\n"
                f"Version: {ver}\n"
                f"Architecture: amd64\n"
                f"Maintainer: Test <test@m3tal.io>\n"
                f"Filename: pool/main/{deb_name}\n"
                f"Size: {sz}\n"
                f"MD5sum: {md5_h}\n"
                f"SHA256: {sha256_h}\n"
                f"Description: Test package\n"
            )
            entries.append(entry)

        packages_content = "\n\n".join(entries) + "\n"
        pkg_file = os.path.join(self.bin_dir, "Packages")
        with open(pkg_file, "w", encoding="utf-8") as f:
            f.write(packages_content)

        pkg_gz_file = os.path.join(self.bin_dir, "Packages.gz")
        with gzip.open(pkg_gz_file, "wb") as f:
            f.write(packages_content.encode("utf-8"))

        # Release file
        release_content = (
            "Origin: M3TAL\n"
            "Label: M3TAL\n"
            "Suite: stable\n"
            "Codename: stable\n"
            "Architectures: amd64\n"
            "Components: main\n"
            "Description: Test\n"
            "Date: Mon, 29 Jun 2026 00:00:00 +0000\n"
            "MD5Sum:\n"
            " eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee 100 main/binary-amd64/Packages\n"
            " eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee 100 main/binary-amd64/Packages.gz\n"
            "SHA256:\n"
            " eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee 100 main/binary-amd64/Packages\n"
            " eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee 100 main/binary-amd64/Packages.gz\n"
        )
        with open(os.path.join(self.dist_dir, "Release"), "w", encoding="utf-8") as f:
            f.write(release_content)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_inventory_classification(self):
        policy = {
            "keep_recent_per_series": 2,
            "min_retained_packages": 2,
            "protected_series": ["1.1", "1.0"],
            "pinned_versions": ["1.0.0", "1.1.0"],
        }
        inv = build_inventory(self.test_dir, policy)
        status_map = {item["version"]: item["status"] for item in inv}

        self.assertEqual(status_map["1.1.4"], "RETAIN_CURRENT")
        self.assertEqual(status_map["1.1.3"], "RETAIN_RECENT")
        self.assertEqual(status_map["1.1.0"], "RETAIN_PINNED")
        self.assertEqual(status_map["1.1.2"], "PRUNE_CANDIDATE")
        self.assertEqual(status_map["1.1.1"], "PRUNE_CANDIDATE")

        self.assertEqual(status_map["1.0.3"], "RETAIN_RECENT")
        self.assertEqual(status_map["1.0.2"], "RETAIN_RECENT")
        self.assertEqual(status_map["1.0.0"], "RETAIN_PINNED")
        self.assertEqual(status_map["1.0.1"], "PRUNE_CANDIDATE")

    def test_safety_guard_prevents_pruning_below_floor(self):
        policy = {
            "keep_recent_per_series": 1,
            "min_retained_packages": 20,  # Floor higher than total
            "pinned_versions": [],
        }
        rc = execute_prune(self.test_dir, policy, dry_run=False)
        self.assertEqual(rc, 1, "Should abort when retained count < min_floor")

    def test_execute_prune_and_metadata_regeneration(self):
        policy = {
            "keep_recent_per_series": 2,
            "min_retained_packages": 2,
            "pinned_versions": ["1.0.0", "1.1.0"],
            "deprecation": {"archive_obsolete": False},
        }
        snap_dir = os.path.join(self.test_dir, "snapshots")
        create_snapshot(self.test_dir, snapshot_dir=snap_dir)
        self.assertTrue(len(os.listdir(snap_dir)) > 0)

        rc = execute_prune(self.test_dir, policy, dry_run=False)
        self.assertEqual(rc, 0)

        # Check pruned files deleted
        self.assertFalse(os.path.exists(os.path.join(self.pool_dir, "m3tal_v1.0.1_amd64.deb")))
        self.assertFalse(os.path.exists(os.path.join(self.pool_dir, "m3tal_v1.1.1_amd64.deb")))

        # Check retained files exist
        self.assertTrue(os.path.exists(os.path.join(self.pool_dir, "m3tal_v1.0.0_amd64.deb")))
        self.assertTrue(os.path.exists(os.path.join(self.pool_dir, "m3tal_v1.1.4_amd64.deb")))

        # Check Packages index only contains retained packages
        with open(os.path.join(self.bin_dir, "Packages"), "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("Version: 1.0.1", content)
        self.assertIn("Version: 1.0.0", content)
        self.assertIn("Version: 1.1.4", content)

        # Check Release file checksums match newly generated Packages and Packages.gz
        with open(os.path.join(self.bin_dir, "Packages"), "rb") as f:
            real_sha256 = hashlib.sha256(f.read()).hexdigest()
        with open(os.path.join(self.dist_dir, "Release"), "r", encoding="utf-8") as f:
            rel_content = f.read()

        inrelease = os.path.join(self.dist_dir, "InRelease")
        release_gpg = os.path.join(self.dist_dir, "Release.gpg")
        self.assertTrue(os.path.isfile(inrelease))
        self.assertTrue(os.path.isfile(release_gpg))
        subprocess.run(["gpg", "--homedir", self.gnupghome, "--verify", inrelease], check=True, capture_output=True)
        subprocess.run(["gpg", "--homedir", self.gnupghome, "--verify", release_gpg, os.path.join(self.dist_dir, "Release")], check=True, capture_output=True)
        self.assertIn(real_sha256, rel_content)

    def test_signing_failure_restores_removed_packages_and_old_indexes(self):
        policy = {
            "keep_recent_per_series": 2,
            "min_retained_packages": 2,
            "pinned_versions": ["1.0.0", "1.1.0"],
            "deprecation": {"archive_obsolete": False},
        }
        packages_path = os.path.join(self.bin_dir, "Packages")
        with open(packages_path, "rb") as f:
            original_packages = f.read()
        pruned_path = os.path.join(self.pool_dir, "m3tal_v1.0.1_amd64.deb")

        with patch.object(manage_retention, "regenerate_repository_indexes", side_effect=RuntimeError("sign failed")):
            with self.assertRaisesRegex(RuntimeError, "sign failed"):
                execute_prune(self.test_dir, policy, dry_run=False)

        self.assertTrue(os.path.isfile(pruned_path))
        with open(packages_path, "rb") as f:
            self.assertEqual(f.read(), original_packages)
        self.assertFalse(any(name.startswith(".retention-quarantine-") for name in os.listdir(self.test_dir)))


if __name__ == "__main__":
    unittest.main()
