# M3tal Core Specification & Debian Packaging Standard (Phase 11)

> **Phase**: Phase 11 — M3tal Core  
> **Package Name**: `m3tal` (Virtual: `m3tal-core`)  
> **Reference Architecture**: `amd64`  
> **Target Distribution**: `stable main` (`Debian 12/13`, `Ubuntu 22.04/24.04`, `Linux Mint 21/22`)  
> **Current Version**: `1.1.62` (`pool/main/m3tal_v1.1.62_amd64.deb`)  
> **Maintainer**: `Jake Johnson <jake@m3tal.io>`  
> **Status**: Completed & Validated

---

## 1. Executive Summary & Core Responsibilities

`m3tal-core` (binary package `m3tal`) is the foundational system orchestration package for the M3tal Linux application ecosystem. It provides:
1. **Core Orchestration CLI (`/usr/bin/m3tal`)**: Command dispatcher, environment initialization, interactive terminal Control Center, and runtime supervision.
2. **Control-Plane API Daemon (`/usr/bin/m3tal-api`)**: Local REST API backend facilitating inter-process communication, metrics, and homelab routing integration.
3. **Systemd Services**: Native background service units (`m3tal.service` and `m3tal-api.service`) with automated lifecycle management.
4. **Shared Environment & Group Primitives**: Common system group `m3tal`, directory layout (`/etc/m3tal`, `/var/lib/m3tal`, `/var/log/m3tal`, `/opt/m3tal`), and permissions allowing secure sudo-less operation.
5. **Docker Infrastructure Topology**: Standard compose stacks and Traefik reverse-proxy templates deployed to `/opt/m3tal/stack` (with convenience symlink `/docker`).

---

## 2. Bootstrap & Repository Isolation (Loop Prevention)

A critical requirement of the M3tal packaging architecture is **strict isolation between repository bootstrapping and `m3tal-core` runtime**:

```
+-------------------------------------------------------------+
|              Repository Bootstrap Layer                     |
|  (m3tal-apt-key / install.sh / KEY.gpg / sources.list)      |
|                                                             |
|  Prerequisites: POSIX sh, curl, gpg, coreutils              |
|  Dependencies on m3tal-core: NONE                           |
+-------------------------------------------------------------+
                              |
                              v (APT index resolution)
+-------------------------------------------------------------+
|                  APT Package Layer                          |
|         sudo apt update && sudo apt install m3tal           |
+-------------------------------------------------------------+
                              |
                              v (Unpacks binaries & services)
+-------------------------------------------------------------+
|                 m3tal-core Runtime Layer                    |
|  /usr/bin/m3tal, /usr/bin/m3tal-api, systemd services       |
|                                                             |
|  Downstream apps: Depends / Recommends: m3tal               |
+-------------------------------------------------------------+
```

### Isolation Guarantees:
- **Zero Circular Dependencies**: The repository bootstrap script (`install.sh`), keyrings (`KEY.gpg`), and APT repository configuration (`dists/stable/...`) do **not** depend on `m3tal-core` or any custom binaries.
- **Bootstrap Tooling**: Repository bootstrapping relies exclusively on standard base utilities available on any minimal Debian/Ubuntu system (`curl`, `gpg`, `tee`, `install`).
- **Independent Upgrades**: Updating repository keys or adding additional repositories can occur independently of `m3tal-core` package version changes.
- **Clean Container Proof**: Validated via clean Debian 13 (trixie) container where the repository was bootstrapped and queried with zero prior `m3tal` components installed.

---

## 3. Package Architecture & Payload Manifest

The reference Debian binary package `m3tal_v1.1.62_amd64.deb` contains:

### 3.1 Control Metadata (`DEBIAN/control`)
```ini
Package: m3tal
Version: 1.1.62
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Jake Johnson <jake@m3tal.io>
Installed-Size: 47987
Recommends: xdotool
Description: M3TAL Core — DEB-first infrastructure orchestration platform.
 Includes the m3tal CLI and control-plane API.
 Optimized for Traefik ecosystems and home lab automation.
```

### 3.2 Executable Binaries
- `/usr/bin/m3tal` (27.8 MB ELF 64-bit LSB executable, x86-64, dynamically linked)
- `/usr/bin/m3tal-api` (20.5 MB ELF 64-bit LSB executable, x86-64, dynamically linked)

### 3.3 System Configuration & Templates
- `/etc/m3tal/.env.example`: Default environment variable configuration template.
- `/usr/share/m3tal/stack/`: Base compose topology templates:
  - `ai-compose.yml`, `cloudflared-config.yml`, `m3tal-compose.local.yml`
  - `m3tal-compose.traefik.yml`, `m3tal-compose.yml`, `routing-compose.yml`
  - `traefik.yml`, `users.example.json`, `dynamic/api.yml`
- `/usr/share/m3tal/gui/`: Built-in web dashboard assets (`index.html`, JavaScript, CSS).

### 3.4 Desktop & Theme Integration
- `/usr/share/applications/m3tal.desktop`: Freedesktop desktop menu shortcut.
- `/usr/share/pixmaps/m3tal.svg`: High-resolution vector icon.
- `/usr/share/icons/hicolor/{16x16,24x24,32x32,48x48,64x64,128x128,256x256}/apps/m3tal.png`: Multi-resolution raster icons.
- `/usr/share/icons/hicolor/scalable/apps/m3tal.svg`: Scalable vector icon.

### 3.5 Systemd Unit Files
- `/lib/systemd/system/m3tal.service`
- `/lib/systemd/system/m3tal-api.service`

---

## 4. Systemd Service Units Specification

### 4.1 Orchestrator Daemon (`m3tal.service`)
```ini
[Unit]
Description=M3TAL Orchestrator CLI
Documentation=https://github.com/jakej985-rgb/m3tal-core
After=network-online.target docker.service
Wants=network-online.target docker.service

[Service]
Type=simple
ExecStart=/usr/bin/m3tal daemon
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
EnvironmentFile=-/etc/m3tal/.env
StateDirectory=m3tal
RuntimeDirectory=m3tal
LogsDirectory=m3tal

[Install]
WantedBy=multi-user.target
```

### 4.2 Control Plane API (`m3tal-api.service`)
```ini
[Unit]
Description=M3TAL API Backend
Documentation=https://github.com/jakej985-rgb/m3tal-core
After=network-online.target docker.service
Wants=network-online.target docker.service m3tal.service

[Service]
Type=simple
ExecStart=/usr/bin/m3tal-api
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
EnvironmentFile=-/etc/m3tal/.env
StateDirectory=m3tal
RuntimeDirectory=m3tal
LogsDirectory=m3tal

[Install]
WantedBy=multi-user.target
```

### Unit Design Principles:
1. **Dependency Ordering**: `After=network-online.target docker.service` guarantees container networking is ready before stack orchestration starts.
2. **Auto-Recovery**: `Restart=on-failure` with `RestartSec=5` provides crash resilience.
3. **Environment Injection**: `EnvironmentFile=-/etc/m3tal/.env` passes site credentials and paths if present (the `-` prefix ensures silence if absent).
4. **Sandboxed Directories**: `StateDirectory=m3tal`, `RuntimeDirectory=m3tal`, and `LogsDirectory=m3tal` automatically bind `/var/lib/m3tal`, `/run/m3tal`, and `/var/log/m3tal`.

---

## 5. Standard Filesystem Layout & Common Paths

| Path | Purpose | Permissions | Ownership | Managed By |
| :--- | :--- | :--- | :--- | :--- |
| `/usr/bin/m3tal` | Orchestrator CLI binary | `0755` | `root:root` | Package payload |
| `/usr/bin/m3tal-api` | API backend binary | `0755` | `root:root` | Package payload |
| `/etc/m3tal/` | System configuration directory | `2775` (setgid) | `root:m3tal` | `postinst` hook |
| `/etc/m3tal/.env.example` | Default template config | `0644` | `root:root` | Debian conffile |
| `/etc/m3tal/.env` | Live system configuration | `0600` | `root:root` | Initialized in `postinst` (never overwritten) |
| `/var/lib/m3tal/` | Persistent state, databases, cache | `2775` (setgid) | `root:m3tal` | Systemd `StateDirectory` / `postinst` |
| `/var/log/m3tal/` | Daemon logs | `2775` (setgid) | `root:m3tal` | Systemd `LogsDirectory` / `postinst` |
| `/opt/m3tal/stack/` | Active compose stack files & dynamic routing | `2775` (setgid) | `root:docker` | Initialized from `/usr/share/m3tal/stack` |
| `/docker` | Convenience UX symlink to `/opt/m3tal/stack` | `0777` symlink | `root:root` | `postinst` hook |

---

## 6. Lifecycle Scripts & Hook Behaviors

### 6.1 Post-Installation (`postinst`) Contract
1. **Directory Creation**: Ensures `/etc/m3tal`, `/var/lib/m3tal`, `/opt/m3tal/stack`, and `/var/log/m3tal` exist.
2. **Permission Hardening & Group Setup**:
   - Creates system group `m3tal` if it does not already exist (`groupadd -r m3tal`).
   - Ensures `root:m3tal` ownership with group read-write-execute (`chmod -R g+rwX`).
   - Sets group ownership of `/opt/m3tal/stack` to `docker` to facilitate container control.
3. **Configuration Safeguard**:
   - Checks if `/etc/m3tal/.env` exists. If not, copies `/etc/m3tal/.env.example` to `/etc/m3tal/.env` with `0600` permissions.
   - **Never overwrites** an existing `/etc/m3tal/.env` during package upgrades.
4. **Stack Template Synchronization**:
   - Copies `/usr/share/m3tal/stack/.` into `/opt/m3tal/stack/` using `cp -rn` (no-clobber), preventing deletion or regression of customized user Compose files.
5. **UX Symlink Management**:
   - Creates symlink `/docker -> /opt/m3tal/stack` if `/docker` does not already exist. If `/docker` is an existing physical folder, skips symlink creation with a warning.
6. **Systemd Daemon Integration**:
   - Calls `systemctl daemon-reload`.
   - Enables and restarts `m3tal-api.service` and `m3tal.service` so updated binaries take effect immediately.
7. **Desktop Cache Update**:
   - Triggers `update-desktop-database -q` and `gtk-update-icon-cache -f -t /usr/share/icons/hicolor`.

### 6.2 Post-Removal (`postrm`) Contract
1. **Service Teardown**:
   - Stops and disables `m3tal-api.service` and `m3tal.service`.
   - Reloads systemd daemon.
2. **Symlink Cleanup**:
   - Removes `/docker` if it is a symlink.
3. **Purge Handling (`postrm purge`)**:
   - Selectively cleans default stack templates from `/opt/m3tal/stack/`.
   - If `/opt/m3tal/stack/` or `/opt/m3tal/` contains custom user files, preserves the directory and logs a notice; otherwise removes the folder.
   - Removes `/etc/m3tal` and `/var/lib/m3tal`.
4. **Standard Removal (`postrm remove`)**:
   - Preserves user configuration in `/etc/m3tal` and state data in `/var/lib/m3tal` in accordance with Debian Policy Manual section 6.8.

---

## 7. Downstream Dependency Contract for M3tal Apps

Applications in the M3tal ecosystem depend on `m3tal-core` according to three standard tiers:

1. **Tight Orchestration Tier** (`m3tal-godash`, `m3tal-api`):
   ```ini
   Depends: m3tal (>= 1.1.0), docker.io | docker-ce
   ```
   Requires the core CLI, `/docker` stack tree, and systemd units for service discovery and Traefik reverse-proxy routing.

2. **Modular Service Tier** (e.g. `infernal-web`, `jellyfin-ui`):
   ```ini
   Recommends: m3tal (>= 1.1.0)
   ```
   Can run standalone in containers or web servers, but leverages `m3tal` when installed on the host for automated network routing and SSL termination.

3. **Standalone Desktop & Utility Tier** (`comicinfo-generator`, `gps-speedometer`):
   ```ini
   Depends: libc6 (>= 2.34)
   ```
   Operates completely independently without requiring `m3tal-core`.

---

## 8. Verification & Validation Record

| Test Assertion | Method | Result | Notes |
| :--- | :--- | :--- | :--- |
| Package Archive Integrity | `dpkg-deb -I m3tal_v1.1.62_amd64.deb` | PASSED | Control archive checksums, md5sums, and conffiles valid |
| File Payload Structure | `dpkg-deb -c m3tal_v1.1.62_amd64.deb` | PASSED | Correct directories under `/usr/bin`, `/lib/systemd`, `/etc/m3tal`, `/usr/share` |
| Idempotent Installation | Clean Debian 13 container test | PASSED | `apt-get install -y m3tal` successfully resolves and unpacks |
| Non-Destructive Upgrades | `postinst` check on `.env` | PASSED | Pre-existing `.env` is preserved |
| Symlink Safety | `postinst` check on `/docker` | PASSED | Existing non-symlink directories are never overwritten |
| Service Unit Syntax | `systemd-analyze verify` | PASSED | Units parse validly with standard systemd targets |
