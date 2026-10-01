#!/usr/bin/env python3
"""
M3tal Debian Package Metadata Validator
Phase 07 Deliverable: Enforces Debian Policy standards for package control fields,
architecture tags (amd64, arm64, all), dependency syntax, and .deb archive integrity.
"""

import sys
import os
import re
import io
import json
import tarfile
import argparse
import subprocess
from typing import Dict, List, Tuple, Optional

# Import deb_version from same directory or relative path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    from deb_version import is_valid_debian_version, parse_debian_version
except ImportError:
    # Fallback if imported from parent dir
    sys.path.insert(0, os.path.join(SCRIPT_DIR, "scripts"))
    from deb_version import is_valid_debian_version, parse_debian_version

# Debian Policy Standards
VALID_ARCHITECTURES = {
    "amd64", "arm64", "all",
    # Additional standard Debian architectures supported if needed
    "armhf", "armel", "i386", "riscv64", "ppc64el", "s390x"
}

VALID_SECTIONS = {
    "admin", "cli-mono", "comm", "database", "debug", "devel", "doc",
    "editors", "education", "electronics", "embedded", "fonts", "games",
    "gnome", "gnu-r", "gnustep", "graphics", "hamradio", "haskell",
    "httpd", "interpreters", "introspection", "java", "javascript",
    "kde", "kernel", "libdevel", "libs", "lisp", "localization",
    "mail", "math", "metapackages", "misc", "net", "news", "ocaml",
    "oldlibs", "otherosfs", "perl", "php", "python", "ruby", "rust",
    "science", "shells", "sound", "tasks", "tex", "text", "utils",
    "vcs", "video", "web", "x11", "zope"
}

VALID_PRIORITIES = {"required", "important", "standard", "optional", "extra"}

# Package name: lowercase alphanumerics, plus, minus, period; at least 2 chars; starts with alphanumeric
PACKAGE_NAME_REGEX = re.compile(r"^[a-z0-9][a-z0-9+.-]+$")

# Maintainer: Name <email@domain>
MAINTAINER_REGEX = re.compile(r"^.+?<[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}>$")

# Dependency element: package-name [ ( <<|<=|=|>=|>> version ) ] [ [arch1 !arch2] ]
RELATION_OPERATORS = {"<<", "<=", "=", ">=", ">>"}
DEP_ITEM_REGEX = re.compile(
    r"^(?P<pkg>[a-z0-9][a-z0-9+.-]+)"
    r"(?::(?P<archqual>[a-z0-9-]+))?"
    r"(?:\s*\(\s*(?P<op><=|<<|>=|>>|=)\s*(?P<ver>[^\)]+)\s*\))?"
    r"(?:\s*\[(?P<archlist>[^\]]+)\])?"
    r"(?:\s*<(?P<buildprofiles>[^>]+)>)?$"
)


def parse_rfc822_fields(text: str) -> Dict[str, str]:
    """Parse RFC 822 formatted key-value block into a dictionary."""
    fields: Dict[str, str] = {}
    current_key: Optional[str] = None
    current_val: List[str] = []

    for line in text.splitlines():
        if not line:
            continue
        if line.startswith(" ") or line.startswith("\t"):
            if current_key:
                current_val.append(line.rstrip())
        elif ":" in line:
            if current_key:
                fields[current_key] = "\n".join(current_val)
            key, val = line.split(":", 1)
            current_key = key.strip()
            current_val = [val.strip()]
        else:
            continue

    if current_key:
        fields[current_key] = "\n".join(current_val)

    return fields


def parse_dependency_field(field_value: str) -> List[List[Dict[str, str]]]:
    """
    Parse a dependency field (Depends, Recommends, etc.)
    Debian dependencies are comma-separated conjunctions of pipe-separated alternatives:
    e.g. "python3 (>= 3.10), docker-ce | docker.io, curl"
    Returns a list of lists (AND of ORs).
    """
    conjunctions = []
    for item in field_value.split(","):
        item = item.strip()
        if not item:
            continue
        alternatives = []
        for alt in item.split("|"):
            alt = alt.strip()
            match = DEP_ITEM_REGEX.match(alt)
            if not match:
                raise ValueError(f"Malformed dependency specification: '{alt}'")
            entry = {
                "package": match.group("pkg"),
                "operator": match.group("op"),
                "version": match.group("ver"),
                "archqual": match.group("archqual"),
                "raw": alt,
            }
            if entry["version"] and not is_valid_debian_version(entry["version"]):
                raise ValueError(
                    f"Invalid Debian version in dependency '{alt}': '{entry['version']}'"
                )
            alternatives.append(entry)
        conjunctions.append(alternatives)
    return conjunctions


def extract_control_from_deb(deb_path: str) -> Tuple[Dict[str, str], Dict[str, bytes]]:
    """
    Extract control fields and maintainer scripts from a .deb archive.
    Uses pure Python ar/tar extraction with fallback to dpkg-deb.
    Returns (control_fields_dict, control_tar_files_dict).
    """
    if not os.path.isfile(deb_path):
        raise FileNotFoundError(f"DEB archive not found: {deb_path}")

    # Pure Python AR parser
    control_text = None
    extra_files = {}

    try:
        with open(deb_path, "rb") as f:
            magic = f.read(8)
            if magic != b"!<arch>\n":
                raise ValueError("Not a valid AR archive (missing !<arch> signature)")

            while True:
                header = f.read(60)
                if len(header) < 60:
                    break
                name = header[:16].decode("ascii", errors="ignore").strip().rstrip("/")
                size_str = header[48:58].decode("ascii", errors="ignore").strip()
                size = int(size_str)

                data = f.read(size)
                # AR members are 2-byte aligned
                if size % 2 == 1:
                    f.read(1)

                if name == "debian-binary":
                    ver = data.decode("ascii", errors="ignore").strip()
                    if ver != "2.0":
                        raise ValueError(f"Unsupported debian-binary version: {ver}")

                elif name.startswith("control.tar"):
                    tar_bytes = io.BytesIO(data)
                    with tarfile.open(fileobj=tar_bytes, mode="r:*") as tar:
                        for member in tar.getmembers():
                            member_name = os.path.basename(member.name)
                            if member.isfile():
                                extracted = tar.extractfile(member)
                                if extracted:
                                    extra_files[member_name] = extracted.read()

                    if "control" in extra_files:
                        control_text = extra_files["control"].decode("utf-8", errors="replace")

        if control_text:
            return parse_rfc822_fields(control_text), extra_files

    except Exception:
        # Fallback to dpkg-deb if Python ar parsing fails or non-standard compression
        pass

    # Fallback to dpkg-deb
    res = subprocess.run(["dpkg-deb", "-f", deb_path], capture_output=True, text=True)
    if res.returncode != 0:
        raise ValueError(f"Failed to inspect deb via dpkg-deb: {res.stderr}")
    fields = parse_rfc822_fields(res.stdout)

    # Also extract control files via dpkg-deb -e for script inspection
    try:
        import tempfile
        with tempfile.TemporaryDirectory(prefix="dpkg_deb_ctrl_") as tmp_dir:
            res_e = subprocess.run(["dpkg-deb", "-e", deb_path, tmp_dir], capture_output=True, text=True)
            if res_e.returncode == 0:
                for item in os.listdir(tmp_dir):
                    item_path = os.path.join(tmp_dir, item)
                    if os.path.isfile(item_path):
                        try:
                            with open(item_path, "rb") as f_item:
                                extra_files[item] = f_item.read()
                        except Exception:
                            pass
    except Exception:
        pass

    return fields, extra_files


class ValidationResult:
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str):
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)


def validate_control_fields(
    fields: Dict[str, str],
    check_installed_size: bool = False
) -> ValidationResult:
    """Validate RFC 822 control metadata against Debian standards."""
    result = ValidationResult()

    # 1. Package Name
    pkg = fields.get("Package")
    if not pkg:
        result.add_error("Missing required field: 'Package'")
    else:
        if not PACKAGE_NAME_REGEX.match(pkg):
            result.add_error(
                f"Invalid 'Package' name '{pkg}'. Must consist only of lower-case letters (a-z), "
                f"digits (0-9), plus (+) and minus (-) signs, and dots (.), must be >= 2 chars, "
                f"and must start with an alphanumeric character."
            )

    # 2. Version
    ver = fields.get("Version")
    if not ver:
        result.add_error("Missing required field: 'Version'")
    else:
        if not is_valid_debian_version(ver):
            result.add_error(
                f"Invalid 'Version' format '{ver}'. Must conform to Debian Policy §5.6.12 [epoch:]upstream[-revision]."
            )
        else:
            # Check for accidental 'v' prefix
            if ver.startswith("v") or ver.startswith("V"):
                result.add_error(
                    f"Version string '{ver}' contains leading 'v'. Debian versions must not prefix upstream with 'v'."
                )

    # 3. Architecture
    arch = fields.get("Architecture")
    if not arch:
        result.add_error("Missing required field: 'Architecture'")
    else:
        if arch not in VALID_ARCHITECTURES:
            result.add_error(
                f"Invalid or unsupported 'Architecture' '{arch}'. Supported architectures: {sorted(list(VALID_ARCHITECTURES))}"
            )

    # 4. Maintainer
    maintainer = fields.get("Maintainer")
    if not maintainer:
        result.add_error("Missing required field: 'Maintainer'")
    else:
        if not MAINTAINER_REGEX.match(maintainer):
            result.add_warning(
                f"Maintainer '{maintainer}' does not match standard RFC 822 format: 'Full Name <user@domain.tld>'."
            )

    # 5. Section
    section = fields.get("Section")
    if not section:
        result.add_error("Missing required field: 'Section'")
    else:
        # Some packages use component/section like main/utils
        sec_base = section.split("/")[-1]
        if sec_base not in VALID_SECTIONS:
            result.add_warning(
                f"Non-standard 'Section' '{section}'. Standard sections include: {sorted(list(VALID_SECTIONS))[:10]}..."
            )

    # 6. Priority
    prio = fields.get("Priority")
    if not prio:
        result.add_error("Missing required field: 'Priority'")
    else:
        if prio.lower() not in VALID_PRIORITIES:
            result.add_error(
                f"Invalid 'Priority' '{prio}'. Must be one of: {sorted(list(VALID_PRIORITIES))}"
            )
        elif prio.lower() == "extra":
            result.add_warning("Priority 'extra' is deprecated in Debian Policy. Use 'optional' instead.")

    # 7. Description
    desc = fields.get("Description")
    if not desc:
        result.add_error("Missing required field: 'Description'")
    else:
        lines = desc.splitlines()
        synopsis = lines[0].strip()
        if len(synopsis) > 80:
            result.add_warning(f"Description synopsis exceeds 80 characters ({len(synopsis)} chars).")
        if len(lines) > 1:
            for i, line in enumerate(lines[1:], start=2):
                if line and not (line.startswith(" ") or line.startswith("\t")):
                    result.add_error(
                        f"Description line {i} is not indented with leading space/tab: '{line[:30]}...'"
                    )

    # 8. Dependency Fields Syntax
    dep_fields = [
        "Depends", "Pre-Depends", "Recommends", "Suggests",
        "Enhances", "Conflicts", "Breaks", "Replaces", "Provides"
    ]
    for df in dep_fields:
        val = fields.get(df)
        if val:
            try:
                parse_dependency_field(val)
            except ValueError as e:
                result.add_error(f"Syntax error in field '{df}': {e}")

    # 9. Homepage
    homepage = fields.get("Homepage")
    if homepage:
        if not (homepage.startswith("http://") or homepage.startswith("https://")):
            result.add_error(f"Invalid 'Homepage' '{homepage}'. Must begin with http:// or https://")

    # 10. Installed-Size (if checked)
    if check_installed_size:
        isize = fields.get("Installed-Size")
        if not isize or not isize.isdigit():
            result.add_warning(f"Field 'Installed-Size' is missing or non-integer: '{isize}'")

    return result


def validate_maintainer_scripts(extra_files: Dict[str, bytes]) -> ValidationResult:
    """Validate maintainer scripts inside control tarball."""
    result = ValidationResult()
    script_names = ["preinst", "postinst", "prerm", "postrm", "config"]

    for s_name in script_names:
        if s_name in extra_files:
            content = extra_files[s_name].decode("utf-8", errors="replace").strip()
            first_line = content.splitlines()[0] if content else ""
            if not first_line.startswith("#!"):
                result.add_error(f"Maintainer script '{s_name}' is missing shebang line (#!)")
            elif not any(sh in first_line for sh in ["/bin/sh", "/bin/bash", "/usr/bin/python"]):
                result.add_warning(
                    f"Maintainer script '{s_name}' uses uncommon interpreter: '{first_line}'"
                )

    return result


def validate_debian_package(deb_path: str) -> ValidationResult:
    """Perform complete structural and metadata validation on a .deb package file."""
    res = ValidationResult()

    if not os.path.isfile(deb_path):
        res.add_error(f"File not found: {deb_path}")
        return res

    if not deb_path.endswith(".deb"):
        res.add_warning(f"File '{deb_path}' does not end with '.deb' extension")

    try:
        fields, extra_files = extract_control_from_deb(deb_path)
    except Exception as e:
        res.add_error(f"Failed to read .deb archive structure: {e}")
        return res

    # Validate control metadata
    ctrl_res = validate_control_fields(fields, check_installed_size=False)
    res.errors.extend(ctrl_res.errors)
    res.warnings.extend(ctrl_res.warnings)

    # Validate maintainer scripts
    scripts_res = validate_maintainer_scripts(extra_files)
    res.errors.extend(scripts_res.errors)
    res.warnings.extend(scripts_res.warnings)

    # Validate filename convention: <package>_<version>_<arch>.deb
    filename = os.path.basename(deb_path)
    pkg = fields.get("Package", "")
    ver = fields.get("Version", "")
    arch = fields.get("Architecture", "")

    if pkg and ver and arch:
        expected_fn = f"{pkg}_{ver}_{arch}.deb"
        # Check if filename has legacy 'v' prefix
        if filename != expected_fn:
            if filename == f"{pkg}_v{ver}_{arch}.deb":
                res.add_warning(
                    f"Package filename '{filename}' includes legacy 'v' prefix. Standard Debian name: '{expected_fn}'"
                )
            else:
                res.add_warning(
                    f"Package filename '{filename}' diverges from standard Debian naming convention '{expected_fn}'"
                )

    return res


def main():
    parser = argparse.ArgumentParser(
        description="M3tal Debian Package Metadata Validator (Phase 07)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate-deb
    p_deb = subparsers.add_parser("validate-deb", help="Validate a .deb binary package file")
    p_deb.add_argument("deb_file", help="Path to .deb file")
    p_deb.add_argument("--json", action="store_true", help="Output results in JSON format")

    # validate-control
    p_ctrl = subparsers.add_parser("validate-control", help="Validate a debian/control file")
    p_ctrl.add_argument("control_file", help="Path to control file")
    p_ctrl.add_argument("--json", action="store_true", help="Output results in JSON format")

    # extract-control
    p_ext = subparsers.add_parser("extract-control", help="Extract and print control fields from .deb")
    p_ext.add_argument("deb_file", help="Path to .deb file")
    p_ext.add_argument("--json", action="store_true", help="Output fields as JSON")

    args = parser.parse_args()

    if args.command == "validate-deb":
        res = validate_debian_package(args.deb_file)
        if args.json:
            print(json.dumps({
                "valid": res.is_valid,
                "errors": res.errors,
                "warnings": res.warnings,
            }, indent=2))
        else:
            print(f"Validating DEB: {args.deb_file}")
            if res.is_valid:
                print("✅ Package PASSED validation!")
            else:
                print(f"❌ Package FAILED validation with {len(res.errors)} errors:")
                for e in res.errors:
                    print(f"   [ERROR] {e}")
            if res.warnings:
                print(f"⚠️  {len(res.warnings)} warnings:")
                for w in res.warnings:
                    print(f"   [WARN]  {w}")

        sys.exit(0 if res.is_valid else 1)

    elif args.command == "validate-control":
        with open(args.control_file, "r", encoding="utf-8") as f:
            fields = parse_rfc822_fields(f.read())
        res = validate_control_fields(fields)
        if args.json:
            print(json.dumps({
                "valid": res.is_valid,
                "errors": res.errors,
                "warnings": res.warnings,
            }, indent=2))
        else:
            print(f"Validating control file: {args.control_file}")
            if res.is_valid:
                print("✅ Control file PASSED validation!")
            else:
                print(f"❌ Control file FAILED validation with {len(res.errors)} errors:")
                for e in res.errors:
                    print(f"   [ERROR] {e}")
            if res.warnings:
                print(f"⚠️  {len(res.warnings)} warnings:")
                for w in res.warnings:
                    print(f"   [WARN]  {w}")

        sys.exit(0 if res.is_valid else 1)

    elif args.command == "extract-control":
        fields, _ = extract_control_from_deb(args.deb_file)
        if args.json:
            print(json.dumps(fields, indent=2))
        else:
            for k, v in fields.items():
                print(f"{k}: {v}")
        sys.exit(0)


if __name__ == "__main__":
    main()
