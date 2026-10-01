# M3tal APT Repository: Versioning, SemVer Mapping & Epoch Standard (Phase 08)

> **Document**: `docs/versioning-spec.md`  
> **Phase**: Phase 08 — Versioning  
> **Status**: Approved & Implemented  
> **Translation Tool**: [`scripts/deb_version.py`](file:///home/m3tal/apps/M3tal-Hub/m3tal-apt-key/scripts/deb_version.py)

---

## 1. Executive Summary

This standard defines the versioning contract for all packages distributed by the M3tal APT repository. It specifies:
1. Strict adherence to **Debian Policy §5.6.12** version specifications.
2. Canonical translation rules between **Semantic Versioning 2.0.0 (SemVer)** and Debian package versions.
3. The vital role of the tilde (`~`) character in managing prereleases (release candidates, betas, alphas).
4. Guidelines for Debian package revisions (`-1`, `-2`).
5. Epoch handling (`1:2.0.0`) for breaking version scheme transitions.
6. Guardrails preventing accidental downgrades and version collisions.

---

## 2. Debian Version Format Specification

Per Debian Policy §5.6.12, every package version string follows this structure:

```text
[epoch:]upstream_version[-debian_revision]
```

### 2.1 Component Breakdown

1. **`epoch`** (Optional):
   - Single unsigned integer followed by a colon (`:`).
   - If omitted, defaults to `0`.
   - Used only when the upstream project changes versioning schemes such that a newer release would sort lexicographically or numerically lower than an older release.
   - Example: `1:1.0.0`
2. **`upstream_version`** (Mandatory):
   - Alphanumeric characters (`a-z`, `A-Z`, `0-9`) and symbols (`.`, `+`, `-`, `~`).
   - Must begin with a digit (`0-9`).
   - May contain a hyphen (`-`) only if a `debian_revision` is present.
   - Example: `1.1.62`, `2.0.0~rc.1`
3. **`debian_revision`** (Optional for native packages, recommended for non-native):
   - Alphanumeric characters and symbols (`+`, `.`, `~`).
   - Separated from upstream by a hyphen (`-`).
   - Indicates packaging-only updates without changes to upstream source code.
   - Example: `1.1.62-1`, `1.1.62-2`

---

## 3. SemVer 2.0.0 to Debian Version Translation

Upstream projects across the M3tal ecosystem utilize Semantic Versioning 2.0.0:
```text
MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
```

Directly using SemVer strings as Debian versions causes severe upgrade bugs unless translated according to the following rules:

### 3.1 The Prerelease Tilde (`~`) Rule

In SemVer:
$$\text{1.0.0-rc.1} < \text{1.0.0}$$

In standard Debian version comparison:
$$\text{1.0.0-rc.1} > \text{1.0.0} \quad \text{(FATAL UPGRADE BUG: hyphen/revision sorts AFTER release)}$$

Debian reserves the tilde (`~`) character to sort **earlier than anything, even the empty string**:
$$\text{1.0.0\~rc.1-1} < \text{1.0.0-1} \quad \text{(CORRECT APT UPGRADE BEHAVIOR)}$$

**Mandatory Translation Rule**:  
All SemVer prerelease identifiers preceded by a hyphen (`-`) MUST be translated into a tilde (`~`) in the Debian version:

| Upstream SemVer | Debian Package Version | `apt` Comparison |
| :--- | :--- | :--- |
| `1.2.0-alpha.1` | `1.2.0~alpha.1-1` | `< 1.2.0-1` |
| `1.2.0-beta.2` | `1.2.0~beta.2-1` | `< 1.2.0-1` |
| `1.2.0-rc.1` | `1.2.0~rc.1-1` | `< 1.2.0-1` |
| `1.2.0` | `1.2.0-1` | `> 1.2.0~rc.1-1` |

### 3.2 Build Metadata Handling (`+`)

SemVer allows build metadata following a plus (`+`):
```text
1.0.0+20261001.git.abcdef
```
In Debian versioning, `+` is a valid character. It sorts higher than letters and numbers.  
Debian mapping:
```text
1.0.0+20261001.git.abcdef-1
```

### 3.3 Translation CLI Tool

The `scripts/deb_version.py` utility automates SemVer translation:
```bash
python3 scripts/deb_version.py from-semver 2.0.0-rc.3
# Output: 2.0.0~rc.3-1

python3 scripts/deb_version.py from-semver 2.0.0-rc.3 --native
# Output: 2.0.0~rc.3
```

---

## 4. Epoch Handling & Migration Guidelines

### 4.1 When is an Epoch Required?

An epoch is required **strictly** when upstream changes its version format such that the new version sorts lower than the older published version.

**Real-world scenario**:
- Older version: `2026.05-1` (CalVer)
- Upstream transitions to SemVer: `1.0.0-1`
- Without epoch: `1.0.0-1 < 2026.05-1` $\implies$ APT will refuse to upgrade.
- With epoch: `1:1.0.0-1 > 2026.05-1` $\implies$ APT successfully upgrades.

### 4.2 Permanent Impact of Epochs

Once an epoch is added to a package, **all future versions of that package must have an epoch of at least that value**, because `1:anything` is always greater than `0:anything`.
Therefore, epochs must never be introduced lightly.

The publishing tool checks for candidate version downgrades:
```bash
python3 scripts/deb_version.py check-upgrade 2026.05-1 1.0.0-1
# Output:
# Status:  downgrade
# Message: Downgrade rejected: 1.0.0-1 < 2026.05-1
# Note:    Candidate version '1.0.0-1' sorts lower than installed '2026.05-1'.
#          If upstream versioning scheme reset, bump epoch to '1' (e.g. '1:1.0.0-1').
```

---

## 5. Debian Revision Lifecycle

- **Upstream Release**: Whenever upstream code changes, bump the upstream version and reset the Debian revision to `1` (e.g. `1.1.62-1` $\to$ `1.2.0-1`).
- **Packaging Fix**: If a packaging defect is fixed (e.g., incorrect systemd unit file, missing file dependency) without changing upstream binaries, increment the Debian revision (e.g. `1.1.62-1` $\to$ `1.1.62-2`).
- **Native Packages**: Native packages (where upstream code and Debian packaging originate in the exact same repository) may omit the Debian revision entirely (e.g. `1.1.62`).

---

## 6. Upgrade & Downgrade Prevention Rules

1. **Exact Duplicate Prevention**:
   - Publishing an exact duplicate version (e.g. `1.1.62` when `1.1.62` is already in the repository) is blocked by default.
   - If a build must be republished with the same version (e.g. CI rebuild), `--allow-replace` must be explicitly specified.
2. **Downgrade Guardrails**:
   - Publishing a version that sorts lower than the highest candidate currently published for that architecture is rejected with exit code 1.
   - Overriding requires `--allow-downgrade`.

---

## 7. Package Retirement & Deprecation

When a package is retired or renamed:
1. **Transitional Meta-package**: Publish an empty package with `Architecture: all` using the old package name.
2. Set `Depends: <new-package-name>`
3. Set `Section: oldlibs`
4. Set description indicating the package has been deprecated and replaced.
5. In the new package, set:
   ```text
   Breaks: <old-package-name> (<< <current-version>)
   Replaces: <old-package-name> (<< <current-version>)
   ```
This guarantees smooth automated transitions for all client systems during `apt upgrade`.
