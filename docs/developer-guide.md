# M3tal Package Developer & Contributor Guide

> **Phase**: Phase 14 — Documentation  
> **Target Audience**: Application developers, software engineers packaging software for M3tal  
> **Repository Target**: `m3tal-apt-key`  
> **Last Updated**: 2026-10-01  

---

## 1. Debian Packaging Standards for M3tal Applications

All applications integrated into the M3tal ecosystem MUST adhere to standard Debian package formats. Consistent packaging ensures reliable installation, seamless upgrades via `apt-get`, clean removal, and desktop integration.

### Package Naming Rules
- Platform Core Package: `m3tal` (or future `m3tal-core`)
- Application Packages: `m3tal-<appname>` (e.g. `m3tal-hub`, `m3tal-scanner`, `m3tal-gps`)
- Lowercase alphanumeric characters, hyphens, and periods only.
- Filename convention in pool: `<package>_<version>_<arch>.deb` (e.g., `m3tal_1.1.62_amd64.deb`). Note: avoid historical `v` prefix in new deb filenames.

### Target Architecture
- `Architecture: amd64` for compiled Go, Rust, C/C++, or Dart native binaries.
- `Architecture: all` for architecture-independent packages (Python scripts, shell scripts, static web apps).

---

## 2. Standard Filesystem Layout

Applications must install files into the standard Linux Filesystem Hierarchy Standard (FHS) locations:

| Directory | Purpose | Example |
| :--- | :--- | :--- |
| `/usr/bin/` | Primary executables and CLI binaries | `/usr/bin/m3tal`, `/usr/bin/m3tal-api` |
| `/usr/share/m3tal/<app>/` | Static application assets, templates, web UI | `/usr/share/m3tal/gui/`, `/usr/share/m3tal/stack/` |
| `/usr/share/applications/` | Desktop menu entries (`.desktop` files) | `/usr/share/applications/m3tal.desktop` |
| `/usr/share/icons/hicolor/` | Application icons (SVG or PNG: 48x48, 128x128, etc.) | `/usr/share/icons/hicolor/scalable/apps/m3tal.svg` |
| `/lib/systemd/system/` | Systemd service unit files | `/lib/systemd/system/m3tal.service` |
| `/etc/m3tal/` | Global configuration files and templates | `/etc/m3tal/.env.example` |
| `/var/lib/m3tal/` | Persistent state, SQLite databases, runtime data | `/var/lib/m3tal/data/` |
| `/var/log/m3tal/` | Application log output | `/var/log/m3tal/orchestrator.log` |

---

## 3. Package Control File (`DEBIAN/control`)

The `control` file is the heart of the Debian package.

### Canonical Specification
```control
Package: m3tal-app
Version: 1.0.0
Section: utils
Priority: optional
Architecture: amd64
Maintainer: M3tal Packaging Team <packaging@m3tal.io>
Depends: libc6 (>= 2.34), ca-certificates, systemd
Recommends: xdotool, curl
Suggests: docker-ce
Homepage: https://github.com/jakej985-rgb/m3tal-app
Description: M3tal Application Module
 High-performance microservice and user interface for the M3tal platform.
 This package provides the CLI tool, systemd service, and desktop integration.
```

### Dependency Rules
- Always declare minimum library versions where known (`libc6 (>= 2.31)`).
- Never depend on packages outside standard Debian/Ubuntu base repositories without packaging them first.
- Put optional desktop utilities in `Recommends` or `Suggests`.

---

## 4. Maintainer Lifecycle Scripts

Lifecycle scripts reside inside the `DEBIAN/` directory of the package root. All scripts must be executable (`chmod 0755`), strictly idempotent, and handle failures gracefully.

### 4.1 Post-Installation (`DEBIAN/postinst`)
Executed immediately after package files are extracted:
```bash
#!/bin/sh
set -e

case "$1" in
    configure)
        # 1. Create system group and user if needed
        if ! getent group m3tal >/dev/null 2>&1; then
            groupadd --system m3tal
        fi

        # 2. Set directory permissions
        install -d -m 0750 -o root -g m3tal /etc/m3tal
        install -d -m 0770 -o root -g m3tal /var/lib/m3tal
        install -d -m 0755 -o root -g m3tal /var/log/m3tal

        # 3. Seed initial config if not present
        if [ ! -f /etc/m3tal/.env ] && [ -f /etc/m3tal/.env.example ]; then
            cp /etc/m3tal/.env.example /etc/m3tal/.env
            chmod 0640 /etc/m3tal/.env
            chown root:m3tal /etc/m3tal/.env
        fi

        # 4. Reload systemd and enable service
        if [ -d /run/systemd/system ]; then
            systemctl --system daemon-reload >/dev/null 2>&1 || true
            systemctl enable m3tal.service >/dev/null 2>&1 || true
            systemctl restart m3tal.service >/dev/null 2>&1 || true
        fi

        # 5. Update desktop caches if GUI assets installed
        if which update-desktop-database >/dev/null 2>&1; then
            update-desktop-database -q /usr/share/applications || true
        fi
        ;;
esac

exit 0
```

### 4.2 Pre-Removal (`DEBIAN/prerm`)
Executed before package files are removed:
```bash
#!/bin/sh
set -e

case "$1" in
    remove|deconfigure)
        if [ -d /run/systemd/system ]; then
            systemctl stop m3tal.service >/dev/null 2>&1 || true
            systemctl disable m3tal.service >/dev/null 2>&1 || true
        fi
        ;;
esac

exit 0
```

### 4.3 Post-Removal (`DEBIAN/postrm`)
Executed after package files are removed or during purge:
```bash
#!/bin/sh
set -e

case "$1" in
    purge)
        rm -rf /var/lib/m3tal
        rm -rf /var/log/m3tal
        rm -rf /etc/m3tal
        ;;
    remove)
        if [ -d /run/systemd/system ]; then
            systemctl --system daemon-reload >/dev/null 2>&1 || true
        fi
        ;;
esac

exit 0
```

---

## 5. Building & Verifying Packages Locally

### Building a `.deb`
Create the target directory tree and compile with `dpkg-deb`:
```bash
# Set permissions
chmod 0755 build_root/DEBIAN/*
chmod -R u=rwX,go=rX build_root/usr/

# Build package
dpkg-deb --build --root-owner-group build_root m3tal_1.2.0_amd64.deb
```

### Inspecting Package Metadata
```bash
dpkg-deb -I m3tal_1.2.0_amd64.deb
dpkg-deb -c m3tal_1.2.0_amd64.deb
```

### Testing Package Installation Locally in Docker
Always test package installation inside a clean Debian container before publishing:
```bash
docker run --rm -v $(pwd):/workspace:ro debian:bookworm-slim bash -c "
  apt-get update &&
  apt-get install -y /workspace/m3tal_1.2.0_amd64.deb &&
  m3tal --version
"
```
