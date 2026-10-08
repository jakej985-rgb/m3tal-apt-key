#!/usr/bin/env python3
"""
Test Suite for Track 6: Documentation, Security & End-to-End Validation
(Phases 14, 15, 16)
"""

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from test_e2e_validation import E2EValidator, EXPECTED_FINGERPRINT, EXPECTED_CANDIDATE

class TestTrack6Documentation(unittest.TestCase):
    """Phase 14 Documentation Verification"""

    def test_deliverable_documents_exist(self):
        required_docs = [
            "user-setup-guide.md",
            "maintenance-guide.md",
            "security-and-key-rotation.md",
            "central-keyring-architecture.md",
            "app-deb-publishing-guide.md",
            "package-registry.md",
            "package-retention-policy.md",
            "universal-bootstrap.md"
        ]
        for doc in required_docs:
            p = os.path.join(DOCS_DIR, doc)
            self.assertTrue(os.path.isfile(p), f"Missing required document: {doc}")
            self.assertGreater(os.path.getsize(p), 1000, f"Document {doc} appears too small/empty")

    def test_fingerprint_in_docs(self):
        for doc in ["user-setup-guide.md", "security-and-key-rotation.md", "central-keyring-architecture.md", "universal-bootstrap.md"]:
            p = os.path.join(DOCS_DIR, doc)
            with open(p, "r", encoding="utf-8") as f:
                content = f.read().replace(" ", "")
            self.assertIn(EXPECTED_FINGERPRINT, content, f"Fingerprint missing in {doc}")

class TestTrack6Security(unittest.TestCase):
    """Phase 15 Security & Key Rotation Policy Verification"""

    def test_security_policy_content(self):
        sec_path = os.path.join(DOCS_DIR, "security-and-key-rotation.md")
        with open(sec_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(EXPECTED_FINGERPRINT, content.replace(" ", ""))
        self.assertIn("Emergency Key Revocation", content)
        self.assertIn("Scheduled Key Rotation", content)
        self.assertIn("Supply-Chain Risk Review", content)

class TestTrack6E2EValidation(unittest.TestCase):
    """Phase 16 End-to-End Cryptographic Verification"""

    def setUp(self):
        self.repo_dir = "/home/m3tal/apps/m3tal-apt-key"
        self.validator = E2EValidator(self.repo_dir, port=9789)

    def test_cryptographic_integrity(self):
        self.assertTrue(self.validator.verify_cryptographic_integrity())

if __name__ == "__main__":
    unittest.main()
