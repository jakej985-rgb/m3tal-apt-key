# M3tal Central Debian Package Repository & Keyring (`m3tal-apt-key`)

Official URL: [https://jakej985-rgb.github.io/m3tal-apt-key](https://jakej985-rgb.github.io/m3tal-apt-key)  
Keyring Fingerprint: `9DFED0A19DF5351298FE812AED1DAE1980AD1550`

This repository serves as the **authoritative, central Debian package keyring and repository** for the entire M3tal developer ecosystem. All applications built with Debian packages (such as Monster Lab, M3tal Core, GoDash, Specs-n-Parts, and Shop Manager) publish and distribute their `.deb` packages here.

---

## 🚀 Quick Start for End Users

### Universal One-Line Bootstrap
```bash
curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/install.sh | sudo bash
```

### Install Ecosystem Applications
```bash
# Install core platform daemon
sudo apt install m3tal

# Install Monster Lab learning studio
sudo apt install monster-lab
```

---

## 📦 For Application Developers: Pushing Packages

All M3tal ecosystem apps push their Debian packages directly into this repository:

### 1. Automated CI/CD Push (GitHub Actions)
Add `.github/workflows/dispatch-apt.yml` (from [`templates/dispatch-apt.yml`](templates/dispatch-apt.yml)) to your app repo. On each release, it dispatches an authenticated `publish-deb` event to this repository.

### 2. Local Workstation Ingestion CLI
Developers can also publish packages directly from their workstation:
```bash
# Ingest deb package file
python3 scripts/ingest_deb.py /path/to/app.deb

# Ingest directly from local application repository
python3 scripts/ingest_deb.py --from-repo /home/m3tal/apps/Monster-Lab

# Ingest from remote URL
python3 scripts/ingest_deb.py --url https://github.com/jakej985-rgb/Monster-Lab/releases/download/v0.1.4/monster-lab-linux.deb
```

---

## 📚 Architecture & Documentation Index

- **Central Keyring Architecture**: [`docs/central-keyring-architecture.md`](docs/central-keyring-architecture.md)
- **App Deb Publishing Guide**: [`docs/app-deb-publishing-guide.md`](docs/app-deb-publishing-guide.md)
- **Application Installation Standard**: [`docs/12-app-installation-standard.md`](docs/12-app-installation-standard.md)
- **Package Registry Manifest**: [`registry/packages.yml`](registry/packages.yml)
- **Repository Operations & Maintenance Guide**: [`docs/maintenance-guide.md`](docs/maintenance-guide.md)
- **Security & Key Rotation Protocols**: [`docs/security-and-key-rotation.md`](docs/security-and-key-rotation.md)
- **End-to-End Validation Report**: [`docs/e2e-validation-report.md`](docs/e2e-validation-report.md)
