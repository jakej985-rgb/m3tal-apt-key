# M3tal Ecosystem Application Installation Standard (Phase 12)

> **Phase**: Phase 12 — App Installation Standard  
> **Standard Model**: Uniform Debian / APT Package Architecture  
> **Target OS**: Debian 12 (bookworm), Debian 13 (trixie), Ubuntu 22.04 LTS (jammy), Ubuntu 24.04 LTS (noble), Linux Mint 21/22  
> **Target Architecture**: `amd64`  
> **Status**: Completed & Validated

---

## 1. The Universal Installation Contract

Every supported Linux application in the M3tal ecosystem must provide a single, consistent, repeatable installation workflow:

### Step 1: Install Repository Once
```bash
curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/install.sh | sudo bash
```

### Step 2: Install Any Ecosystem App via Standard APT
```bash
sudo apt install m3tal-<app-name>
```

No git cloning, manual pip installs into global python paths, unverified wget binary drops, or ad-hoc systemd unit copying is permitted for end-user installations.

---

## 2. Package Naming Standards

All Debian binary packages in the M3tal ecosystem must adhere to standard naming conventions:

1. **Prefix**: Every application package name must be prefixed with `m3tal-`.
2. **Casing**: Strictly lowercase alphanumeric characters and hyphens (`[a-z0-9-]+`).
3. **Core Exception**: The foundational orchestration package is named `m3tal` and provides the virtual package `m3tal-core` via `Provides: m3tal-core`.
4. **Archive Filename**: `<package>_<version>_<arch>.deb` (e.g., `m3tal-godash_0.2.0_amd64.deb`). Note: Historical builds with leading `v` (e.g. `m3tal_v1.1.62_amd64.deb`) are supported by index mapping, but future builds must omit the `v` prefix in the Debian control version field.

### Ecosystem Package Registry Mapping

| Hub App ID | Ecosystem Category | Debian Package Name | Service / Binary | Dependency Tier |
| :--- | :--- | :--- | :--- | :--- |
| `m3tal-core` | Infrastructure | `m3tal` | `/usr/bin/m3tal`, `/usr/bin/m3tal-api` | Foundation |
| `m3tal-godash` | Infrastructure | `m3tal-godash` | `/usr/bin/m3tal-godash` | Tight (`Depends: m3tal`) |
| `m3tal-api` | Infrastructure | `m3tal-api` | `/usr/bin/m3tal-api` | Tight (`Depends: m3tal`) |
| `comicinfo-generator`| Tooling / CLI | `m3tal-comicinfo` | `/usr/bin/comicinfo` | Standalone |
| `gps-speedometer` | Utilities | `m3tal-gps-speedometer` | `/usr/bin/gps-speedometer` | Standalone |
| `monster-lab` | Applications | `m3tal-monster-lab` | `/usr/bin/monster-lab` | Desktop (`Recommends: m3tal`) |
| `shop-manager` | Applications | `m3tal-shop-manager` | `/usr/bin/shop-manager` | Desktop (`Recommends: m3tal`) |
| `infernal-ink-steel-suite`| Applications | `m3tal-infernal-suite` | `/usr/bin/infernal-suite` | Desktop (`Recommends: m3tal`) |

---

## 3. Dependency Classification & Architecture Tiers

Applications must declare dependencies explicitly in `DEBIAN/control` using Debian Policy Manual syntax:

### Tier 1: Standalone CLI Tools & Daemons
- **Profile**: Self-contained binaries or tools requiring no local orchestrator.
- **Dependencies**: `Depends: libc6 (>= 2.34), ca-certificates`
- **Isolation**: Must function fully without `m3tal-core` installed.

### Tier 2: Ecosystem-Integrated Services
- **Profile**: Services designed to attach to local M3tal orchestration, dynamic Traefik routing, or shared daemon coordination.
- **Dependencies**: `Depends: m3tal (>= 1.1.0), adduser`
- **Integration**: Shares `/etc/m3tal/`, runs under group `m3tal`, and registers dynamic routing configs under `/opt/m3tal/stack/dynamic/`.

### Tier 3: Desktop Graphical Applications
- **Profile**: Flutter desktop, Qt C++, or native GUI applications.
- **Dependencies**: `Depends: libgtk-3-0 | libqt6core6, xdg-utils`
- **Recommends**: `Recommends: m3tal (>= 1.1.0)`
- **Integration**: Freedesktop desktop entries, application icons, and mime-type associations.

---

## 4. Standard Filesystem Hierarchy (FHS Compliance)

Every M3tal application package must place files according to the Linux Filesystem Hierarchy Standard:

```text
/
├── usr/
│   ├── bin/
│   │   └── m3tal-<app>                    # Standard binary executable
│   ├── share/
│   │   ├── applications/
│   │   │   └── m3tal-<app>.desktop        # Desktop entry shortcut
│   │   ├── icons/hicolor/
│   │   │   ├── <size>x<size>/apps/
│   │   │   │   └── m3tal-<app>.png        # Raster application icon
│   │   │   └── scalable/apps/
│   │   │       └── m3tal-<app>.svg        # Vector application icon
│   │   ├── pixmaps/
│   │   │   └── m3tal-<app>.png            # Fallback legacy icon
│   │   ├── doc/
│   │   │   └── m3tal-<app>/
│   │   │       ├── copyright              # Machine-readable Debian copyright
│   │   │       ├── changelog.Debian.gz    # Debian changelog
│   │   │       └── README.md              # Application documentation
│   │   └── man/man1/
│   │       └── m3tal-<app>.1.gz           # Manual page (for CLI tools)
├── etc/
│   └── m3tal/
│       └── <app>/                         # System configuration directory
│           └── config.yaml.example        # Configuration template
├── var/
│   ├── lib/
│   │   └── m3tal/
│   │       └── <app>/                     # Persistent database & state
│   └── log/
│       └── m3tal/
│           └── <app>/                     # Application log directory
└── lib/systemd/system/
    └── m3tal-<app>.service                # Systemd service unit (if service daemon)
```

---

## 5. Desktop Integration Specification

For graphical and interactive desktop applications:

### 5.1 Desktop Entry (`/usr/share/applications/m3tal-<app>.desktop`)
```ini
[Desktop Entry]
Version=1.5
Type=Application
Name=M3tal <AppName>
Comment=<Brief description of application>
Exec=/usr/bin/m3tal-<app> %U
Icon=m3tal-<app>
Terminal=false
Categories=Utility;Development;
StartupNotify=true
StartupWMClass=m3tal-<app>
Keywords=m3tal;<app>;<keywords>;
```

### 5.2 Desktop Hooks in `postinst` & `postrm`
```bash
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi
```

---

## 6. Systemd Service Specification

For background daemon applications:

```ini
[Unit]
Description=M3tal <AppName> Service
Documentation=https://github.com/jakej985-rgb/m3tal-<app>
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=m3tal
Group=m3tal
ExecStart=/usr/bin/m3tal-<app> daemon
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
EnvironmentFile=-/etc/m3tal/<app>/env
StateDirectory=m3tal/<app>
RuntimeDirectory=m3tal/<app>
LogsDirectory=m3tal/<app>

# Security hardening
ProtectSystem=strict
ProtectHome=read-only
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

---

## 7. Lifecycle Scripts Standard (`postinst`, `prerm`, `postrm`)

### 7.1 Idempotency Guarantee
All maintainer scripts must be completely idempotent. Re-running `dpkg --configure -a` or reinstalling the same version must succeed without errors or duplicate entries.

### 7.2 Configuration & State Preservation on Upgrades
- Active user configuration (`/etc/m3tal/<app>/config.yaml`) must **never** be replaced during an upgrade.
- Template files (`config.yaml.example`) must be listed in `DEBIAN/conffiles` to trigger standard Debian interactive 3-way merge prompts only when the template itself changes.
- Persistent databases and user data in `/var/lib/m3tal/<app>/` must remain untouched across package upgrades and standard `apt remove`.

### 7.3 Clean Purge Guarantee (`postrm purge`)
- Standard removal (`apt remove m3tal-<app>`):
  - Services are stopped and disabled.
  - Binaries, man pages, desktop shortcuts, and icons are removed.
  - Configuration files and state databases are **preserved**.
- Complete purge (`apt purge m3tal-<app>`):
  - Configuration files (`/etc/m3tal/<app>/`) and application state directories (`/var/lib/m3tal/<app>/`) are purged cleanly.
  - The shared parent directory `/etc/m3tal` is only removed if completely empty.

---

## 8. Anti-Patterns & Prohibited Practices

| Prohibited Practice | Architectural Risk | Required Standard |
| :--- | :--- | :--- |
| `curl ... \| bash` per individual app | Security risk, no signature verification, unmanageable uninstalls | Use unified `m3tal-apt-key` once, then `apt install` |
| Writing binaries to `/usr/local/bin` via package | Violates Debian FHS policy for package-managed files | All packaged binaries belong in `/usr/bin` |
| Writing state to `/tmp` | State loss on reboot, race conditions, security vulnerabilities | Use `/var/lib/m3tal/<app>` or `StateDirectory` |
| Overwriting `/etc/...` files in `postinst` | Silently destroys user custom configuration | Use `conffiles` or `[ -f config ] || cp example config` |
| Running daemons as root | Privilege escalation vulnerability | Use dedicated unprivileged system user or `User=m3tal` |
