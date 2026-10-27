#!/usr/bin/env python3
"""Verify GitHub Pages serves the exact signed repository metadata in this checkout."""
import argparse
import hashlib
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


FILES = (
    "dists/stable/Release",
    "dists/stable/InRelease",
    "dists/stable/Release.gpg",
    "dists/stable/main/binary-amd64/Packages",
    "dists/stable/main/binary-amd64/Packages.gz",
)


def fetch(url):
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--delay", type=int, default=10)
    args = parser.parse_args()
    base = args.base_url.rstrip("/") + "/"
    expected = {path: open(path, "rb").read() for path in FILES}
    errors = []

    with tempfile.TemporaryDirectory(prefix="apt-pages-check-") as temp:
        keyring = os.path.join(temp, "keyring")
        imported = subprocess.run(["gpg", "--batch", "--homedir", temp, "--import", "public.key"], capture_output=True)
        if imported.returncode:
            raise SystemExit(f"Cannot import repository public key: {imported.stderr.decode(errors='replace')}")
        for attempt in range(1, args.attempts + 1):
            errors = []
            actual = {}
            for path in FILES:
                try:
                    actual[path] = fetch(base + path + "?verify=" + str(attempt))
                    if actual[path] != expected[path]:
                        errors.append(f"{path}: deployed SHA256 {hashlib.sha256(actual[path]).hexdigest()} differs from commit SHA256 {hashlib.sha256(expected[path]).hexdigest()}")
                except (OSError, urllib.error.URLError) as exc:
                    errors.append(f"{path}: fetch failed: {exc}")
            if not errors:
                for path in ("InRelease",):
                    p = os.path.join(temp, path)
                    open(p, "wb").write(actual["dists/stable/" + path])
                    check = subprocess.run(["gpg", "--batch", "--homedir", temp, "--verify", p], capture_output=True)
                    if check.returncode:
                        errors.append(f"{path}: signature verification failed: {check.stderr.decode(errors='replace')}")
                rel = os.path.join(temp, "Release")
                sig = os.path.join(temp, "Release.gpg")
                open(rel, "wb").write(actual["dists/stable/Release"])
                open(sig, "wb").write(actual["dists/stable/Release.gpg"])
                check = subprocess.run(["gpg", "--batch", "--homedir", temp, "--verify", sig, rel], capture_output=True)
                if check.returncode:
                    errors.append("Release.gpg: detached signature verification failed")
                if actual["dists/stable/main/binary-amd64/Packages.gz"]:
                    import gzip
                    if gzip.decompress(actual["dists/stable/main/binary-amd64/Packages.gz"]) != actual["dists/stable/main/binary-amd64/Packages"]:
                        errors.append("Packages.gz does not decompress to Packages byte-for-byte")
            if not errors:
                print(f"Public repository matches validated commit ({os.environ.get('GITHUB_SHA', 'unknown')}).")
                return
            print(f"Attempt {attempt}/{args.attempts} failed: " + "; ".join(errors))
            if attempt < args.attempts:
                time.sleep(args.delay)
    raise SystemExit("Public repository verification failed after bounded retries")


if __name__ == "__main__":
    main()
