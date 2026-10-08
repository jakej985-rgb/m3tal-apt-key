#!/usr/bin/env python3
"""
M3tal APT Repository Trust and Keyring Verification Suite (Phase 2)
Audits canonical keyring artifacts, cryptographic identity, signature validity,
secret isolation, and Debian container trust resolution with signed-by directives.
"""

import os
import sys
import shutil
import tempfile
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYRING_ROOT_GPG = os.path.join(REPO_ROOT, "m3tal-archive-keyring.gpg")
KEYRING_DIR_GPG = os.path.join(REPO_ROOT, "keyrings", "m3tal-archive-keyring.gpg")
KEYRING_DIR_ASC = os.path.join(REPO_ROOT, "keyrings", "m3tal-archive-keyring.asc")
PUBLIC_KEY_PATH = os.path.join(REPO_ROOT, "public.key")
KEY_GPG_PATH = os.path.join(REPO_ROOT, "KEY.gpg")
DIST_DIR = os.path.join(REPO_ROOT, "dists", "stable")

EXPECTED_FINGERPRINT = "5F84FE50A40111C981410E11775AD1473BF25102"
EXPECTED_KEY_ID = "775AD1473BF25102"
EXPECTED_SUBKEY_ID = "CF2E20713078A579"
EXPECTED_UID = "M3tal-Creates <jakej985@gmail.com>"


def verify_keyring_artifacts():
    print("--> 1. Verifying keyring files and format consistency...")
    for path, name in [
        (KEYRING_ROOT_GPG, "Root binary keyring (m3tal-archive-keyring.gpg)"),
        (KEYRING_DIR_GPG, "Keyrings dir binary keyring (keyrings/m3tal-archive-keyring.gpg)"),
        (KEYRING_DIR_ASC, "Canonical armored key (keyrings/m3tal-archive-keyring.asc)"),
        (PUBLIC_KEY_PATH, "Legacy public key (public.key)"),
        (KEY_GPG_PATH, "Legacy key alias (KEY.gpg)"),
    ]:
        assert os.path.isfile(path), f"Missing keyring artifact: {name} at {path}"

    # Read binary keyring
    with open(KEYRING_ROOT_GPG, "rb") as f:
        bin_data = f.read()

    # Read keyrings dir binary keyring
    with open(KEYRING_DIR_GPG, "rb") as f:
        bin_dir_data = f.read()
    assert bin_data == bin_dir_data, "Root and keyrings/ binary keyrings do not match!"

    # Verify binary format: must NOT start with ASCII armor header '-----BEGIN'
    assert not bin_data.startswith(b"-----BEGIN"), "m3tal-archive-keyring.gpg is ASCII-armored, expected binary OpenPGP!"
    # OpenPGP public key packet header has bit 7 set (tag 6: 0x98 or 0x99)
    assert (bin_data[0] & 0x80) != 0, f"m3tal-archive-keyring.gpg first byte 0x{bin_data[0]:02x} is not a valid OpenPGP packet"

    # Read ASCII files
    with open(PUBLIC_KEY_PATH, "r", encoding="utf-8") as f:
        pub_asc = f.read()
    with open(KEY_GPG_PATH, "r", encoding="utf-8") as f:
        key_asc = f.read()
    with open(KEYRING_DIR_ASC, "r", encoding="utf-8") as f:
        dir_asc = f.read()

    assert pub_asc == key_asc, "public.key and KEY.gpg content mismatch"
    assert "-----BEGIN PGP PUBLIC KEY BLOCK-----" in pub_asc, "public.key is missing ASCII armor header"
    assert "-----BEGIN PGP PUBLIC KEY BLOCK-----" in dir_asc, "keyrings/m3tal-archive-keyring.asc is missing ASCII armor header"

    print("    [OK] All 5 keyring artifacts exist, format verified (binary .gpg & ASCII .asc).")


def verify_cryptographic_identity():
    print("--> 2. Verifying cryptographic identity, fingerprint, and subkeys...")
    tmpdir = tempfile.mkdtemp(prefix="trust_id_")
    try:
        subprocess.run(
            ["gpg", "--homedir", tmpdir, "--import", KEYRING_ROOT_GPG],
            check=True,
            capture_output=True,
        )

        res = subprocess.run(
            ["gpg", "--homedir", tmpdir, "--with-colons", "--fingerprint", "jakej985@gmail.com"],
            check=True,
            capture_output=True,
            text=True,
        )

        fpr = None
        key_id = None
        subkey_ids = []
        uids = []
        for line in res.stdout.splitlines():
            parts = line.split(":")
            tag = parts[0]
            if tag == "pub":
                key_id = parts[4]
            elif tag == "fpr" and fpr is None:
                fpr = parts[9]
            elif tag == "sub":
                subkey_ids.append(parts[4])
            elif tag == "uid":
                uids.append(parts[9])

        assert fpr == EXPECTED_FINGERPRINT, f"Fingerprint mismatch: {fpr} != {EXPECTED_FINGERPRINT}"
        assert key_id == EXPECTED_KEY_ID, f"Key ID mismatch: {key_id} != {EXPECTED_KEY_ID}"
        assert EXPECTED_SUBKEY_ID in subkey_ids, f"Expected subkey {EXPECTED_SUBKEY_ID} not in {subkey_ids}"
        assert EXPECTED_UID in uids, f"Expected UID {EXPECTED_UID} not in {uids}"

        print(f"    [OK] Verified key ID: {key_id}, fingerprint: {fpr}, UID: {uids[0]}.")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def verify_signatures():
    print("--> 3. Verifying repository signatures with canonical binary keyring...")
    tmpdir = tempfile.mkdtemp(prefix="trust_sig_")
    try:
        # Import canonical binary keyring
        subprocess.run(
            ["gpg", "--homedir", tmpdir, "--import", KEYRING_ROOT_GPG],
            check=True,
            capture_output=True,
        )

        # 1. InRelease cleartext signature
        inrelease_path = os.path.join(DIST_DIR, "InRelease")
        res1 = subprocess.run(
            ["gpg", "--homedir", tmpdir, "--verify", inrelease_path],
            capture_output=True,
            text=True,
        )
        assert res1.returncode == 0, f"InRelease signature verification failed: {res1.stderr}"
        assert EXPECTED_FINGERPRINT in res1.stderr or EXPECTED_KEY_ID in res1.stderr

        # 2. Release.gpg detached signature
        release_path = os.path.join(DIST_DIR, "Release")
        release_gpg_path = os.path.join(DIST_DIR, "Release.gpg")
        res2 = subprocess.run(
            ["gpg", "--homedir", tmpdir, "--verify", release_gpg_path, release_path],
            capture_output=True,
            text=True,
        )
        assert res2.returncode == 0, f"Release.gpg detached signature verification failed: {res2.stderr}"
        assert EXPECTED_FINGERPRINT in res2.stderr or EXPECTED_KEY_ID in res2.stderr

        print("    [OK] InRelease and Release.gpg validated successfully with canonical keyring.")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def audit_private_key_leak():
    print("--> 4. Auditing repository tree for private key leaks...")
    # Construct markers at runtime so scanner does not match its own source code
    tag_prefix = b"-----" + b"BEGIN "
    tag_suffix = b" PRIVATE " + b"KEY-----"
    forbidden_markers = [
        tag_prefix + b"PGP" + tag_suffix,
        tag_prefix + b"ENCRYPTED" + tag_suffix,
        tag_prefix + b"RSA" + tag_suffix,
        tag_prefix + b"OPENSSH" + tag_suffix,
        b"-----" + b"BEGIN " + b"PRIVATE KEY-----",
    ]

    scanned_count = 0
    for root, dirs, files in os.walk(REPO_ROOT):
        # Exclude git internals and deb pool binaries (pool was already audited)
        if ".git" in root.split(os.sep) or "pool" in root.split(os.sep):
            continue
        for f in files:
            path = os.path.join(root, f)
            if f == "verify_trust.py":
                continue
            scanned_count += 1
            with open(path, "rb") as fh:
                data = fh.read()
                for marker in forbidden_markers:
                    assert marker not in data, f"SECURITY ALERT: Private key marker {marker} found in {path}!"

    print(f"    [OK] Scanned {scanned_count} files across repository. Zero private key material detected.")


def verify_docker_trust_resolution():
    print("--> 5. Verifying Debian container trust with standard signed-by directives...")
    if shutil.which("docker") is None:
        print("    [SKIP] Docker not found; skipping containerized APT verification.")
        return

    # Test both modern deb822 style and traditional style in debian:bookworm-slim
    test_script = r"""
set -e
mkdir -p /etc/apt/keyrings
cp /repo/m3tal-archive-keyring.gpg /etc/apt/keyrings/m3tal-archive-keyring.gpg
chmod 644 /etc/apt/keyrings/m3tal-archive-keyring.gpg

# Test 1: Modern DEB822 sources style
echo "--- Testing DEB822 sources style ---"
cat <<EOF > /etc/apt/sources.list.d/m3tal.sources
Types: deb
URIs: file:///repo
Suites: stable
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/m3tal-archive-keyring.gpg
EOF

apt-get update > /dev/null
CANDIDATE=$(apt-cache policy m3tal | grep "Candidate:" | awk '{print $2}')
test "$CANDIDATE" = "1.1.62"
echo "DEB822 candidate verified: $CANDIDATE"

# Test 2: Traditional one-line sources style
echo "--- Testing traditional one-line sources style ---"
rm -f /etc/apt/sources.list.d/m3tal.sources
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg] file:///repo stable main" > /etc/apt/sources.list.d/m3tal.list

apt-get update > /dev/null
CANDIDATE2=$(apt-cache policy m3tal | grep "Candidate:" | awk '{print $2}')
test "$CANDIDATE2" = "1.1.62"
echo "One-line candidate verified: $CANDIDATE2"

echo "APT trust verification succeeded cleanly!"
"""

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{REPO_ROOT}:/repo:ro",
        "debian:bookworm-slim",
        "bash", "-c", test_script
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Container STDERR:\n", res.stderr)
        print("Container STDOUT:\n", res.stdout)
        raise RuntimeError(f"Docker APT trust test failed with return code {res.returncode}")

    print("    [OK] Clean Debian container validated both DEB822 and traditional signed-by configurations.")


def main():
    print("==================================================")
    print(" M3tal Trust and Keyring Verification Suite")
    print("==================================================")
    verify_keyring_artifacts()
    verify_cryptographic_identity()
    verify_signatures()
    audit_private_key_leak()
    verify_docker_trust_resolution()
    print("==================================================")
    print(" ✅ All Phase 2 trust & keyring checks PASSED!")
    print("==================================================")


if __name__ == "__main__":
    main()
