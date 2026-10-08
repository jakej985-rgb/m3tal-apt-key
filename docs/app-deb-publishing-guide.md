# M3tal Application Deb Packaging & Publishing Guide

This guide describes how to configure any application in the M3tal developer ecosystem to build Debian packages and push them to the central `m3tal-apt-key` repository.

---

## 1. Quick Checklist for App Developers

To ensure your application is recognized, signed, and installable via `apt`:

- [x] Package name follows standard convention: `monster-lab`, `m3tal-core`, `m3tal-<appname>`.
- [x] Application control file declared in `DEBIAN/control` conforms to Debian Policy.
- [x] Binary placed in `/usr/bin/` and desktop entry placed in `/usr/share/applications/`.
- [x] Keyring reference uses the canonical `m3tal-archive-keyring.gpg` (never generate an independent GPG key).
- [x] GitHub Actions workflow dispatches release events to `jakej985-rgb/m3tal-apt-key`.

---

## 2. Registering Your Application

Ensure your app is listed in `registry/packages.yml` in `m3tal-apt-key`:

```yaml
- id: "your-app-id"
  name: "your-app-name"
  source_repo: "jakej985-rgb/your-app-repo"
  type: "desktop"  # or cli / service
  status: "active"
  supported_architectures:
    - "amd64"
  publication:
    component: "main"
    distribution: "stable"
    pool_path: "pool/main/your-app-name"
    retention_count: 5
    auto_publish: true
  metadata:
    latest_version: "1.0.0"
    section: "utils"
    priority: "optional"
    maintainer: "M3tal-Creates <jakej985@gmail.com>"
    homepage: "https://jakej985-rgb.github.io/M3tal-Hub/"
    description: |
      Your application description here.
  dependencies:
    runtime:
      - "libc6 (>= 2.31)"
```

---

## 3. Bundling the Central Keyring (Optional Standalone Updates)

If your package installer provides repository configuration for users installing via standalone `.deb` (`dpkg -i`), configure the central M3tal repository:

```text
/etc/apt/keyrings/m3tal-archive-keyring.gpg
/etc/apt/sources.list.d/m3tal.list
```

Contents of `/etc/apt/sources.list.d/m3tal.list`:
```text
# M3tal Official Debian APT Repository
deb [signed-by=/etc/apt/keyrings/m3tal-archive-keyring.gpg] https://jakej985-rgb.github.io/m3tal-apt-key stable main
```

Do NOT create custom `.list` files or unique `.gpg` keyrings for individual applications.

---

## 4. Automatic Publishing via GitHub Actions

Copy [`templates/dispatch-apt.yml`](../templates/dispatch-apt.yml) into your repository at `.github/workflows/dispatch-apt.yml`.

### Step 1: Add Repository Secret
In your application repository on GitHub:
- Go to **Settings** -> **Secrets and variables** -> **Actions**.
- Add secret `M3TAL_APT_DISPATCH_TOKEN` with a GitHub Personal Access Token (PAT) that has write access to trigger repository dispatch events on `jakej985-rgb/m3tal-apt-key`.

### Step 2: Trigger Release
When you publish a new release tag (e.g. `v0.1.5`):
1. Your build workflow builds the Linux `.deb` asset and attaches it to the GitHub Release.
2. `dispatch-apt.yml` detects the release, resolves the `.deb` asset URL, and sends a `publish-deb` event to `m3tal-apt-key`.
3. `m3tal-apt-key` downloads, validates, signs, and publishes the package to GitHub Pages.

---

## 5. Local Workstation Publishing

To push a `.deb` directly from your local machine:

```bash
# Navigate to central repository
cd /home/m3tal/apps/m3tal-apt-key

# Ingest package
python3 scripts/ingest_deb.py --from-repo /home/m3tal/apps/Your-App-Repo
```
