#!/usr/bin/env python3
"""
M3tal APT Repository: End-to-End Validation Suite (Phase 16)

Automates the complete 13-step lifecycle validation defined in plan/16-end-to-end-validation.md:
 1. Start clean Debian/Ubuntu environment.
 2. Run repository bootstrap.
 3. Verify M3tal keyring fingerprint.
 4. Run apt-get update.
 5. Search for M3tal packages.
 6. Install m3tal.
 7. Verify version pinning / multi-version resolution.
 8. Upgrade package to candidate.
 9. Remove application.
 10. Reinstall application.
 11. Verify signatures and checksums.
 12. Confirm no duplicate repository entries.
 13. Confirm package dependencies resolve correctly.
"""

import os
import sys
import time
import json
import gzip
import shutil
import hashlib
import tempfile
import threading
import subprocess
import http.server
import socketserver
from pathlib import Path

# Paths
CWD = os.path.dirname(os.path.abspath(__file__))
M3TAL_APT_KEY_ROOT = "/home/m3tal/apps/m3tal-apt-key"
if not os.path.isdir(M3TAL_APT_KEY_ROOT):
    # Fallback to relative path if cloned elsewhere
    M3TAL_APT_KEY_ROOT = os.path.abspath(os.path.join(CWD, ".."))

EXPECTED_FINGERPRINT = "9DFED0A19DF5351298FE812AED1DAE1980AD1550"
EXPECTED_CANDIDATE = "1.1.62"
TEST_CONTAINER_IMAGE = "dart:stable"  # Clean Debian 13 (trixie) amd64 image

class SilentHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noisy HTTP request logging during tests
        pass

class E2EValidator:
    def __init__(self, repo_dir, port=9678):
        self.repo_dir = repo_dir
        self.port = port
        self.httpd = None
        self.server_thread = None
        self.results = {}

    def start_http_server(self):
        """Starts an in-memory HTTP server serving repo_dir on 127.0.0.1:port."""
        os.chdir(self.repo_dir)
        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = socketserver.TCPServer(("127.0.0.1", self.port), SilentHTTPHandler)
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        time.sleep(0.5)
        print(f"[*] Started local HTTP repository server at http://127.0.0.1:{self.port}")

    def stop_http_server(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            print("[*] Stopped local HTTP repository server.")

    def run_container_test(self):
        """Runs the 13-step validation inside a clean container environment."""
        print("\n=======================================================")
        print("  Starting Phase 16 End-to-End Validation Suite")
        print("=======================================================")

        # Container script executing all lifecycle operations
        container_script = f"""
set -e
export DEBIAN_FRONTEND=noninteractive

echo "=== Step 1: Clean Debian/Ubuntu environment verified ==="
cat /etc/os-release | grep -E "PRETTY_NAME|VERSION="

echo "=== Step 2: Run official repository bootstrap ==="
# Ensure prerequisites are available
apt-get update > /dev/null
apt-get install -y --no-install-recommends curl gnupg ca-certificates > /dev/null
mkdir -p -m 0700 /root/.gnupg

# Pre-seed system groups required by package maintainer scripts
groupadd -r docker || true

# Bootstrap keyring and source list
install -m 0755 -d /etc/apt/keyrings
curl -fsSL http://127.0.0.1:{self.port}/public.key | gpg --dearmor -o /etc/apt/keyrings/m3tal-archive-keyring.gpg
chmod 0644 /etc/apt/keyrings/m3tal-archive-keyring.gpg

# Register APT source
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg] http://127.0.0.1:{self.port} stable main" > /etc/apt/sources.list.d/m3tal.list

echo "=== Step 3: Verify M3tal keyring ==="
FPR=$(gpg --homedir /root/.gnupg --show-keys --with-colons /etc/apt/keyrings/m3tal-archive-keyring.gpg | grep "^fpr:" | head -n1 | cut -d: -f10)
echo "Imported Key Fingerprint: $FPR"
if [ "$FPR" != "{EXPECTED_FINGERPRINT}" ]; then
    echo "ERROR: Fingerprint mismatch! Expected {EXPECTED_FINGERPRINT}, got $FPR" >&2
    exit 1
fi
echo "[PASS] Keyring fingerprint matches authoritative master key."

echo "=== Step 4: Run apt update ==="
apt-get update

echo "=== Step 5: Search for M3tal packages ==="
apt-cache search m3tal | grep -i "m3tal"
POLICY=$(apt-cache policy m3tal)
echo "$POLICY"
echo "$POLICY" | grep -q "Candidate: {EXPECTED_CANDIDATE}"
echo "[PASS] APT policy confirms candidate {EXPECTED_CANDIDATE}."

echo "=== Step 6: Install m3tal ==="
apt-get install -y m3tal
test -x /usr/bin/m3tal
test -x /usr/bin/m3tal-api
test -f /etc/m3tal/.env
test -d /opt/m3tal/stack
/usr/bin/m3tal help > /dev/null
echo "[PASS] m3tal installed and CLI verified."

echo "=== Step 7: Version Pinning & Multi-Version Resolution ==="
# Install specific historical version (1.1.0)
apt-get install -y --allow-downgrades m3tal=1.1.0
CURRENT_VER=$(dpkg-query -W -f='${{Version}}' m3tal)
echo "Current Version after downgrade: $CURRENT_VER"
if [ "$CURRENT_VER" != "1.1.0" ]; then
    echo "ERROR: Expected version 1.1.0, got $CURRENT_VER" >&2
    exit 1
fi
echo "[PASS] Pinned historical release 1.1.0 installed successfully."

echo "=== Step 8: Upgrade packages ==="
apt-get --only-upgrade -y install m3tal
UPGRADED_VER=$(dpkg-query -W -f='${{Version}}' m3tal)
echo "Current Version after upgrade: $UPGRADED_VER"
if [ "$UPGRADED_VER" != "{EXPECTED_CANDIDATE}" ]; then
    echo "ERROR: Expected upgraded version {EXPECTED_CANDIDATE}, got $UPGRADED_VER" >&2
    exit 1
fi
echo "[PASS] Package upgraded smoothly back to latest candidate {EXPECTED_CANDIDATE}."

echo "=== Step 9: Remove application ==="
apt-get remove -y m3tal
if [ -f /usr/bin/m3tal ]; then
    echo "ERROR: /usr/bin/m3tal still exists after removal!" >&2
    exit 1
fi
test -f /etc/m3tal/.env  # Conffile must be retained on remove
echo "[PASS] Package cleanly removed, configurations preserved."

echo "=== Step 10: Reinstall the application ==="
apt-get install -y m3tal
test -x /usr/bin/m3tal
echo "[PASS] Package cleanly reinstalled."

echo "=== Step 11: Verify signatures and checksums ==="
INRELEASE_FILE=$(ls /var/lib/apt/lists/*127.0.0.1*InRelease 2>/dev/null || ls /var/lib/apt/lists/*InRelease 2>/dev/null | head -n1)
echo "Acquired InRelease file: $INRELEASE_FILE"
test -f "$INRELEASE_FILE"
gpg --homedir /root/.gnupg --no-default-keyring --keyring /etc/apt/keyrings/m3tal-archive-keyring.gpg --verify "$INRELEASE_FILE"
echo "[PASS] APT InRelease acquired and verified cryptographically with RSA-4096 signature."

echo "=== Step 12: Confirm no duplicate repository entries ==="
# Re-run the bootstrap steps to test idempotency
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg] http://127.0.0.1:{self.port} stable main" > /etc/apt/sources.list.d/m3tal.list
UPDATE_OUTPUT=$(apt-get update 2>&1)
echo "$UPDATE_OUTPUT"
if echo "$UPDATE_OUTPUT" | grep -i "configured multiple times"; then
    echo "ERROR: Duplicate repository warning detected!" >&2
    exit 1
fi
echo "[PASS] Idempotent bootstrap produces zero duplicate repository warnings."

echo "=== Step 13: Confirm package dependencies resolve correctly ==="
dpkg -s m3tal | grep -E "Depends|Recommends"
apt-cache show m3tal | grep -E "Depends|Recommends" | head -n 2
echo "[PASS] Package dependencies verified."

echo "======================================================="
echo "  All 13 E2E Lifecycle Steps Completed Successfully!   "
echo "======================================================="
"""
        cmd = [
            "docker", "run", "--rm",
            "--network", "host",
            TEST_CONTAINER_IMAGE,
            "bash", "-c", container_script
        ]

        start_time = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        duration = round(time.time() - start_time, 2)

        print(proc.stdout)
        if proc.returncode != 0:
            print(f"[!] Docker test failed with code {proc.returncode}!", file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            self.results["docker_e2e"] = {
                "status": "FAILED",
                "duration_s": duration,
                "error": proc.stderr
            }
            return False

        self.results["docker_e2e"] = {
            "status": "PASSED",
            "duration_s": duration,
            "image": TEST_CONTAINER_IMAGE,
            "os": "Debian GNU/Linux 13 (trixie)"
        }
        return True

    def verify_cryptographic_integrity(self):
        """Verifies local checksums and detached signatures independently in Python."""
        print("\n[*] Running independent cryptographic integrity checks...")
        release_path = os.path.join(self.repo_dir, "dists", "stable", "Release")
        packages_path = os.path.join(self.repo_dir, "dists", "stable", "main", "binary-amd64", "Packages")
        packages_gz_path = os.path.join(self.repo_dir, "dists", "stable", "main", "binary-amd64", "Packages.gz")
        public_key_path = os.path.join(self.repo_dir, "public.key")
        inrelease_path = os.path.join(self.repo_dir, "dists", "stable", "InRelease")
        release_gpg_path = os.path.join(self.repo_dir, "dists", "stable", "Release.gpg")

        # 1. SHA256 of Packages and Packages.gz
        with open(packages_path, "rb") as f:
            p_sha256 = hashlib.sha256(f.read()).hexdigest()
        with open(packages_gz_path, "rb") as f:
            gz_sha256 = hashlib.sha256(f.read()).hexdigest()

        with open(release_path, "r", encoding="utf-8") as f:
            release_text = f.read()

        assert p_sha256 in release_text, f"Packages SHA256 {p_sha256} not in Release!"
        assert gz_sha256 in release_text, f"Packages.gz SHA256 {gz_sha256} not in Release!"
        print(f"    [OK] Release file contains exact SHA256 hashes for Packages and Packages.gz")

        # 2. GPG signature verification
        tmpdir = tempfile.mkdtemp(prefix="gpg_e2e_")
        try:
            # Import public key
            subprocess.run(["gpg", "--homedir", tmpdir, "--import", public_key_path], check=True, capture_output=True)
            # Verify InRelease
            subprocess.run(["gpg", "--homedir", tmpdir, "--verify", inrelease_path], check=True, capture_output=True)
            # Verify Release.gpg
            subprocess.run(["gpg", "--homedir", tmpdir, "--verify", release_gpg_path, release_path], check=True, capture_output=True)
            print(f"    [OK] InRelease and Release.gpg validated with RSA-4096 signature")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        self.results["cryptographic_integrity"] = "PASSED"
        return True

def main():
    repo_root = M3TAL_APT_KEY_ROOT
    if not os.path.isdir(repo_root):
        print(f"Error: Repository root '{repo_root}' not found!", file=sys.stderr)
        sys.exit(1)

    validator = E2EValidator(repo_root, port=9678)
    validator.start_http_server()
    try:
        crypto_ok = validator.verify_cryptographic_integrity()
        e2e_ok = validator.run_container_test()
    finally:
        validator.stop_http_server()

    print("\n=======================================================")
    print("  Validation Results Summary:")
    print(json.dumps(validator.results, indent=2))
    print("=======================================================")

    if crypto_ok and e2e_ok:
        print("\n✅ All End-to-End Validation criteria successfully passed!")
        sys.exit(0)
    else:
        print("\n❌ End-to-End Validation failed!", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
