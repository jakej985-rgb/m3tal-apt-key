#!/usr/bin/env python3
"""Verify that Pages serves this commit's signed APT metadata."""
import argparse
import gzip
import hashlib
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from validate_repository import EXPECTED_FINGERPRINT


FILES = (
    "dists/stable/Release",
    "dists/stable/InRelease",
    "dists/stable/Release.gpg",
    "dists/stable/main/binary-amd64/Packages",
    "dists/stable/main/binary-amd64/Packages.gz",
)
PACKAGES = "dists/stable/main/binary-amd64/Packages"
PACKAGES_GZ = PACKAGES + ".gz"


def fetch(url):
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def verify_signature(gpg_home, *paths):
    return subprocess.run(
        ["gpg", "--batch", "--homedir", gpg_home, "--verify", *paths],
        capture_output=True,
        text=True,
        timeout=20,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--delay", type=int, default=10)
    args = parser.parse_args()
    base = args.base_url.rstrip("/") + "/"
    expected = {path: Path(path).read_bytes() for path in FILES}
    errors = []

    with tempfile.TemporaryDirectory(prefix="apt-pages-check-") as gpg_home:
        imported = subprocess.run(
            ["gpg", "--batch", "--homedir", gpg_home, "--import", "public.key"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if imported.returncode:
            raise SystemExit(f"Cannot import repository public key: {imported.stderr}")
        listed = subprocess.run(
            ["gpg", "--batch", "--homedir", gpg_home, "--with-colons", "--fingerprint", "--list-keys"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        fingerprints = [line.split(":")[9] for line in listed.stdout.splitlines() if line.startswith("fpr:")]
        if EXPECTED_FINGERPRINT not in fingerprints:
            raise SystemExit(
                f"public.key fingerprint mismatch: expected {EXPECTED_FINGERPRINT}, found {fingerprints}"
            )

        for attempt in range(1, args.attempts + 1):
            errors = []
            actual = {}
            for path in FILES:
                try:
                    actual[path] = fetch(base + path + "?verify=" + str(attempt))
                    if actual[path] != expected[path]:
                        errors.append(
                            f"{path}: expected {len(expected[path])} bytes / "
                            f"{hashlib.sha256(expected[path]).hexdigest()}, got {len(actual[path])} bytes / "
                            f"{hashlib.sha256(actual[path]).hexdigest()}"
                        )
                except (OSError, urllib.error.URLError, TimeoutError) as exc:
                    errors.append(f"{path}: fetch failed: {exc}")

            if not errors:
                with tempfile.TemporaryDirectory(prefix="apt-pages-data-") as data_dir:
                    inrelease = os.path.join(data_dir, "InRelease")
                    release = os.path.join(data_dir, "Release")
                    detached = os.path.join(data_dir, "Release.gpg")
                    Path(inrelease).write_bytes(actual["dists/stable/InRelease"])
                    Path(release).write_bytes(actual["dists/stable/Release"])
                    Path(detached).write_bytes(actual["dists/stable/Release.gpg"])
                    for label, result in (
                        ("InRelease", verify_signature(gpg_home, inrelease)),
                        ("Release.gpg", verify_signature(gpg_home, detached, release)),
                    ):
                        if result.returncode:
                            errors.append(f"{label}: signature verification failed: {result.stderr.strip()}")
                try:
                    if gzip.decompress(actual[PACKAGES_GZ]) != actual[PACKAGES]:
                        errors.append("Packages.gz does not decompress to Packages byte-for-byte")
                except (OSError, EOFError, gzip.BadGzipFile) as exc:
                    errors.append(f"Packages.gz decompression failed: {exc}")

            if not errors:
                print(f"Public repository matches validated commit ({os.environ.get('GITHUB_SHA', 'unknown')}).")
                return
            print(f"Attempt {attempt}/{args.attempts} failed: " + "; ".join(errors))
            if attempt < args.attempts:
                time.sleep(args.delay)
    raise SystemExit("Public repository verification failed after bounded retries")


if __name__ == "__main__":
    main()
