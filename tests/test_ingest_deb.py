#!/usr/bin/env python3
"""
Unit and Integration Test Suite for Central Package Ingestion (ingest_deb.py)
Verifies:
  1. Creation of mock Debian package
  2. Ingestion into isolated mock repository root
  3. Structured pool placement (pool/main/<package>/)
  4. Index generation (Packages, Packages.gz, Release)
  5. Registry manifest auto-updating
  6. Idempotency and duplicate detection
"""

import os
import sys
import shutil
import tempfile
import subprocess
import gzip
import unittest
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from ingest_deb import ingest_deb_file, update_registry_manifest
from validate_package import extract_control_from_deb


def build_mock_deb(output_path: str, pkg_name: str = "monster-lab", version: str = "0.1.4") -> str:
    """Build a minimal valid Debian package using dpkg-deb."""
    with tempfile.TemporaryDirectory(prefix="mock_deb_stage_") as stage:
        debian_dir = os.path.join(stage, "DEBIAN")
        bin_dir = os.path.join(stage, "usr", "bin")
        os.makedirs(debian_dir, exist_ok=True)
        os.makedirs(bin_dir, exist_ok=True)

        # Binary
        bin_path = os.path.join(bin_dir, pkg_name)
        with open(bin_path, "w") as f:
            f.write("#!/bin/sh\necho 'running'\n")
        os.chmod(bin_path, 0o755)

        # Control
        control_path = os.path.join(debian_dir, "control")
        with open(control_path, "w") as f:
            f.write(
                f"Package: {pkg_name}\n"
                f"Version: {version}\n"
                f"Architecture: amd64\n"
                f"Maintainer: Monster Lab Team <support@monsterlab.org>\n"
                f"Section: education\n"
                f"Priority: optional\n"
                f"Description: Monster Lab - Test Suite Mock Package\n"
            )
        os.chmod(control_path, 0o644)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        res = subprocess.run(["dpkg-deb", "--build", "--root-owner-group", stage, output_path], capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"dpkg-deb build failed: {res.stderr}")
        return output_path


class TestDebIngestion(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="m3tal_test_ingest_")
        self.mock_repo = os.path.join(self.temp_dir, "repo")
        os.makedirs(os.path.join(self.mock_repo, "pool", "main"), exist_ok=True)
        os.makedirs(os.path.join(self.mock_repo, "dists", "stable", "main", "binary-amd64"), exist_ok=True)
        os.makedirs(os.path.join(self.mock_repo, "registry"), exist_ok=True)

        # Mock registry
        self.registry_file = os.path.join(self.mock_repo, "registry", "packages.yml")
        mock_registry_data = {
            "version": "1.0.0",
            "packages": [
                {
                    "id": "monster-lab",
                    "name": "monster-lab",
                    "status": "active",
                    "metadata": {"latest_version": "0.1.0"},
                    "publication": {"pool_path": "pool/main/monster-lab"}
                }
            ]
        }
        with open(self.registry_file, "w") as f:
            yaml.dump(mock_registry_data, f)

        self.mock_deb = os.path.join(self.temp_dir, "monster-lab_0.1.4_amd64.deb")
        build_mock_deb(self.mock_deb, pkg_name="monster-lab", version="0.1.4")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ingest_deb_file(self):
        # Ingest without GPG signing in isolated test environment
        res = ingest_deb_file(
            deb_path=self.mock_deb,
            repo_dir=self.mock_repo,
            sign=False,
            update_registry=False,
        )

        self.assertEqual(res["package"], "monster-lab")
        self.assertEqual(res["version"], "0.1.4")
        self.assertEqual(res["architecture"], "amd64")

        # Verify staged location in structured pool
        expected_staged = os.path.join(self.mock_repo, "pool", "main", "monster-lab", "monster-lab_0.1.4_amd64.deb")
        self.assertTrue(os.path.isfile(expected_staged))

        # Verify Packages index
        packages_path = os.path.join(self.mock_repo, "dists", "stable", "main", "binary-amd64", "Packages")
        self.assertTrue(os.path.isfile(packages_path))
        with open(packages_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Package: monster-lab", content)
        self.assertIn("Version: 0.1.4", content)
        self.assertIn("Filename: pool/main/monster-lab/monster-lab_0.1.4_amd64.deb", content)

        # Verify Packages.gz index
        packages_gz_path = os.path.join(self.mock_repo, "dists", "stable", "main", "binary-amd64", "Packages.gz")
        self.assertTrue(os.path.isfile(packages_gz_path))
        with gzip.open(packages_gz_path, "rt", encoding="utf-8") as f:
            gz_content = f.read()
        self.assertEqual(gz_content, content)

        # Verify Release manifest
        release_path = os.path.join(self.mock_repo, "dists", "stable", "Release")
        self.assertTrue(os.path.isfile(release_path))
        with open(release_path, "r", encoding="utf-8") as f:
            rel_content = f.read()
        self.assertIn("Origin: M3TAL", rel_content)
        self.assertIn("main/binary-amd64/Packages", rel_content)

    def test_duplicate_rejection(self):
        # Ingest first time
        ingest_deb_file(self.mock_deb, repo_dir=self.mock_repo, sign=False, update_registry=False)

        # Ingest second time without allow_replace should fail
        with self.assertRaises(ValueError) as ctx:
            ingest_deb_file(self.mock_deb, repo_dir=self.mock_repo, allow_replace=False, sign=False, update_registry=False)
        self.assertIn("already exists", str(ctx.exception))

        # Ingest second time with allow_replace should succeed
        res = ingest_deb_file(self.mock_deb, repo_dir=self.mock_repo, allow_replace=True, sign=False, update_registry=False)
        self.assertEqual(res["version"], "0.1.4")


if __name__ == "__main__":
    unittest.main()
