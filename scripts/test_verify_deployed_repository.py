#!/usr/bin/env python3
"""Unit tests for the bounded post-deployment integrity verifier."""
import gzip
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import verify_deployed_repository as verifier


class TestDeployedRepositoryVerifier(unittest.TestCase):
    def run_verifier(self, packages_gz):
        contents = {
            "dists/stable/Release": b"release bytes",
            "dists/stable/InRelease": b"inline signature",
            "dists/stable/Release.gpg": b"detached signature",
            verifier.PACKAGES: b"Package: test\n\n",
            verifier.PACKAGES_GZ: packages_gz,
        }
        with tempfile.TemporaryDirectory(prefix="verify-pages-test-") as directory:
            old_cwd = os.getcwd()
            try:
                os.chdir(directory)
                for path, content in contents.items():
                    target = Path(path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                Path("public.key").write_text("test key", encoding="utf-8")
                fetched = {path: content for path, content in contents.items()}

                def fake_fetch(url):
                    path = url.split("?", 1)[0].removeprefix("https://example.test/")
                    return fetched[path]

                gpg_results = [
                    SimpleNamespace(returncode=0, stdout="", stderr=""),
                    SimpleNamespace(
                        returncode=0,
                        stdout=f"fpr:::::::::{verifier.EXPECTED_FINGERPRINT}:\n",
                        stderr="",
                    ),
                ]
                with patch("sys.argv", ["verify_deployed_repository.py", "--base-url", "https://example.test", "--attempts", "1"]), \
                     patch.object(verifier, "fetch", side_effect=fake_fetch), \
                     patch.object(verifier, "verify_signature", return_value=SimpleNamespace(returncode=0, stderr="")), \
                     patch.object(verifier.subprocess, "run", side_effect=gpg_results):
                    verifier.main()
            finally:
                os.chdir(old_cwd)

    def test_accepts_matching_signed_repository_and_index_bytes(self):
        self.run_verifier(gzip.compress(b"Package: test\n\n", mtime=0))

    def test_rejects_matching_but_invalid_gzip_index(self):
        with self.assertRaises(SystemExit):
            self.run_verifier(b"not gzip")


if __name__ == "__main__":
    unittest.main()
