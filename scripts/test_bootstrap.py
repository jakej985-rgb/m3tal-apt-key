#!/usr/bin/env python3
"""
Test Suite for M3tal Universal Bootstrap Installer (Phase 03)
Tests:
  - Command line arguments (--help, --dry-run)
  - Fingerprint verification and tamper rejection
  - Keyring and sources.list creation
  - Idempotency on repeated execution
  - Clean uninstallation
  - Docker container execution on clean Debian image
"""

import os
import sys
import shutil
import tempfile
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL_SCRIPT = os.path.join(REPO_ROOT, "install.sh")
PUBLIC_KEY = os.path.join(REPO_ROOT, "public.key")
EXPECTED_FINGERPRINT = "9DFED0A19DF5351298FE812AED1DAE1980AD1550"

def run(cmd, check=True, capture=True):
    return subprocess.run(
        cmd,
        shell=True,
        check=check,
        capture_output=capture,
        text=True
    )

def test_help_and_dry_run():
    print("--> Testing --help and --dry-run...")
    res = run(f"'{INSTALL_SCRIPT}' --help")
    assert "M3tal Core APT Repository Installer" in res.stdout, "Help output missing title"
    assert "--dry-run" in res.stdout, "Help output missing --dry-run"

    res = run(f"'{INSTALL_SCRIPT}' --dry-run")
    assert "[DRY-RUN]" in res.stdout, "Dry run output missing [DRY-RUN]"
    assert EXPECTED_FINGERPRINT in res.stdout, "Dry run missing expected fingerprint"
    print("    [OK] --help and --dry-run work as expected.")

def test_fingerprint_tamper_detection():
    print("--> Testing fingerprint verification & tamper rejection...")
    tmpdir = tempfile.mkdtemp(prefix="m3tal_test_tamper_")
    try:
        # Generate dummy untrusted RSA key
        dummy_key = os.path.join(tmpdir, "fake.key")
        gnupg_home = os.path.join(tmpdir, "gnupg")
        os.makedirs(gnupg_home, mode=0o700)
        
        keygen_script = (
            "Key-Type: RSA\n"
            "Key-Length: 2048\n"
            "Subkey-Type: RSA\n"
            "Subkey-Length: 2048\n"
            "Name-Real: Rogue Actor\n"
            "Name-Email: rogue@example.com\n"
            "Expire-Date: 0\n"
            "%no-protection\n"
            "%commit\n"
        )
        run(f"GNUPGHOME='{gnupg_home}' gpg --batch --generate-key << 'EOF'\n{keygen_script}EOF")
        run(f"GNUPGHOME='{gnupg_home}' gpg --armor --export 'rogue@example.com' > '{dummy_key}'")

        fake_keyring = os.path.join(tmpdir, "keyring.gpg")
        fake_list = os.path.join(tmpdir, "m3tal.list")

        # Run install.sh with fake key
        res = run(
            f"'{INSTALL_SCRIPT}' --key-url '{dummy_key}' --keyring '{fake_keyring}' --sources-list '{fake_list}' --no-update",
            check=False
        )
        assert res.returncode != 0, "Installer did NOT reject forged key!"
        assert "SECURITY ALERT: GPG fingerprint mismatch" in res.stderr or "SECURITY ALERT" in res.stdout, "Missing security alert on fingerprint mismatch"
        assert not os.path.exists(fake_keyring), "Keyring was installed despite fingerprint mismatch!"
        assert not os.path.exists(fake_list), "Sources list was written despite fingerprint mismatch!"
        print("    [OK] Forged key correctly rejected and halted execution.")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_isolated_installation_and_idempotence():
    print("--> Testing isolated installation, idempotency, and uninstallation...")
    tmpdir = tempfile.mkdtemp(prefix="m3tal_test_install_")
    try:
        target_keyring = os.path.join(tmpdir, "etc", "apt", "keyrings", "m3tal-archive-keyring.gpg")
        target_list = os.path.join(tmpdir, "etc", "apt", "sources.list.d", "m3tal.list")

        # First run: install
        cmd = f"'{INSTALL_SCRIPT}' --key-url '{PUBLIC_KEY}' --keyring '{target_keyring}' --sources-list '{target_list}' --no-update"
        res = run(cmd)
        assert os.path.isfile(target_keyring), f"Keyring not created at {target_keyring}"
        assert os.path.isfile(target_list), f"Sources list not created at {target_list}"

        with open(target_list, "r") as f:
            list_content = f.read()
        assert f"signed-by={target_keyring}" in list_content, "Source list missing signed-by keyring directive"

        # Verify installed keyring fingerprint matches official
        gnupg_tmp = os.path.join(tmpdir, "gpg_check")
        os.makedirs(gnupg_tmp, mode=0o700)
        check_res = run(f"GNUPGHOME='{gnupg_tmp}' gpg --show-keys '{target_keyring}'")
        assert EXPECTED_FINGERPRINT in check_res.stdout, "Installed keyring fingerprint mismatch"

        # Second run: test idempotency
        res2 = run(cmd)
        assert "already up-to-date" in res2.stdout, "Second run did not detect existing keyring"
        assert "already configured correctly" in res2.stdout, "Second run did not detect existing source definition"

        # Test uninstall
        uninst_cmd = f"'{INSTALL_SCRIPT}' --keyring '{target_keyring}' --sources-list '{target_list}' --no-update --uninstall"
        run(uninst_cmd)
        assert not os.path.exists(target_keyring), "Keyring still exists after --uninstall"
        assert not os.path.exists(target_list), "Sources list still exists after --uninstall"
        print("    [OK] Installation, idempotence, and uninstallation verified.")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_debian_container_bootstrap():
    print("--> Testing automated bootstrap in clean Debian container...")
    if shutil.which("docker") is None:
        print("    [SKIP] Docker not available.")
        return

    test_cmd = (
        f"docker run --rm "
        f"-v '{REPO_ROOT}':/repo:ro "
        f"dart:stable bash -c '"
        f"set -e\n"
        f"/repo/install.sh --key-url /repo/public.key --repo-url file:///repo\n"
        f"apt-cache policy m3tal | grep -q \"Candidate: 1.1.62\"\n"
        f"apt-get install -d -y m3tal > /dev/null\n"
        f"echo \"Container bootstrap and package fetch succeeded.\"\n"
        f"'"
    )
    res = run(test_cmd)
    assert "Candidate: 1.1.62" in res.stdout or "succeeded" in res.stdout, "Docker bootstrap verification failed"
    print("    [OK] Clean Debian container completed bootstrap and downloaded package.")

def test_piped_execution_and_repo_url():
    print("--> Testing piped stdin execution, --repo-url key tracking, and isolated uninstall...")
    # Piped execution test
    res = run(f"cat '{INSTALL_SCRIPT}' | bash -s -- --dry-run")
    assert res.returncode == 0, f"Piped execution failed: {res.stderr}"
    assert "SUCCESS" in res.stdout, "Piped execution missing success banner"
    assert "unbound variable" not in res.stderr, "Piped execution triggered unbound variable error"

    # --repo-url key tracking test
    res2 = run(f"'{INSTALL_SCRIPT}' --repo-url http://custom-mirror.example.com/apt --dry-run")
    assert "http://custom-mirror.example.com/apt/public.key" in res2.stdout, "--repo-url did not update GPG_KEY_URL"

    # Isolated uninstall dry-run test
    res3 = run(f"'{INSTALL_SCRIPT}' --keyring /tmp/isolated_test_keyring.gpg --uninstall --dry-run")
    assert res3.returncode == 0, f"Isolated uninstall dry-run failed: {res3.stderr}"
    assert "Removing legacy keyring" not in res3.stdout, "Isolated uninstall targeted host legacy keyring"
    print("    [OK] Piped execution, key tracking, and isolated uninstall verified.")

def main():
    print("==================================================")
    print(" M3tal Universal Bootstrap Installer Test Suite   ")
    print("==================================================")
    test_help_and_dry_run()
    test_piped_execution_and_repo_url()
    test_fingerprint_tamper_detection()
    test_isolated_installation_and_idempotence()
    test_debian_container_bootstrap()
    print("==================================================")
    print(" ✅ All Phase 03 bootstrap tests PASSED!")
    print("==================================================")

if __name__ == "__main__":
    main()
