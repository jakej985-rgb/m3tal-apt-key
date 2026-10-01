#!/usr/bin/env python3
"""
M3tal Debian Versioning & SemVer Translation Engine
Phase 08 Deliverable: Implements Debian Policy §5.6.12 version specification,
pure-Python Debian version parsing & comparison, SemVer-to-Debian mapping,
prerelease (~ ordering), and epoch management.
"""

import sys
import re
import argparse
from typing import Optional, Tuple, NamedTuple


class DebianVersion(NamedTuple):
    epoch: int
    upstream_version: str
    debian_revision: str
    raw: str

    def __str__(self) -> str:
        res = ""
        if self.epoch > 0:
            res += f"{self.epoch}:"
        res += self.upstream_version
        if self.debian_revision:
            res += f"-{self.debian_revision}"
        return res


# Regex conforming to Debian Policy 5.6.12:
# [epoch:]upstream_version[-debian_revision]
# epoch: unsigned integer
# upstream_version: alphanumerics and . + - ~; must begin with a digit
# debian_revision: alphanumerics and + . ~
DEBIAN_VERSION_REGEX = re.compile(
    r"^(?:(?P<epoch>\d+):)?"
    r"(?P<upstream>[0-9][a-zA-Z0-9.+:~-]*?)"
    r"(?:-(?P<revision>[a-zA-Z0-9+.~]+))?$"
)


def parse_debian_version(version_str: str, allow_v_prefix: bool = False) -> DebianVersion:
    """
    Parse a version string into epoch, upstream_version, and debian_revision.
    Conforms strictly to Debian Policy §5.6.12.
    """
    v = version_str.strip()
    if not v:
        raise ValueError("Version string cannot be empty")

    if v.startswith("v") or v.startswith("V"):
        if allow_v_prefix and len(v) > 1 and v[1].isdigit():
            v = v[1:]
        else:
            raise ValueError(
                f"Invalid Debian version format: '{version_str}'. "
                f"Debian version must start with a digit, not 'v'."
            )

    match = DEBIAN_VERSION_REGEX.match(v)
    if not match:
        raise ValueError(f"Invalid Debian version format: '{version_str}'")

    epoch_str = match.group("epoch")
    has_epoch = epoch_str is not None
    epoch = int(epoch_str) if has_epoch else 0

    upstream = match.group("upstream")
    revision = match.group("revision") or ""

    # Debian Policy 5.6.12: If there is no epoch then colons are not allowed
    if not has_epoch and ":" in upstream:
        raise ValueError(
            f"Invalid Debian version: colons are not allowed in upstream version '{upstream}' without an epoch"
        )

    # If revision is empty and upstream has hyphens, Debian allows hyphens in upstream
    # ONLY if a debian_revision is present. The regex splits at the LAST hyphen if followed by valid revision.
    if "-" in upstream and not revision:
        parts = upstream.rsplit("-", 1)
        if re.match(r"^[a-zA-Z0-9+.~]+$", parts[1]):
            upstream = parts[0]
            revision = parts[1]
        else:
            raise ValueError(
                f"Invalid Debian version: upstream version '{upstream}' contains hyphens without valid debian_revision"
            )

    return DebianVersion(
        epoch=epoch,
        upstream_version=upstream,
        debian_revision=revision,
        raw=version_str,
    )


def is_valid_debian_version(version_str: str) -> bool:
    """Check if a version string is a valid Debian version strictly conforming to Debian Policy §5.6.12."""
    try:
        parse_debian_version(version_str, allow_v_prefix=False)
        return True
    except ValueError:
        return False


def _order_char(c: Optional[str]) -> Tuple[int, int]:
    """
    Debian Policy 5.6.12 character ordering:
    - '~' sorts earlier than anything, even the end of a part.
    - End of a part (None) sorts after '~' but earlier than any other character.
    - All letters sort earlier than all non-letters (except '~').
    - Letters sort by ASCII value.
    - Non-letters sort by ASCII value.
    """
    if c is None:
        # End of part: higher than '~', lower than letters and other chars
        return (1, 0)
    if c == "~":
        # '~': lowest priority
        return (0, 0)
    if c.isalpha():
        # Letters: higher than end-of-part, lower than non-letters
        return (2, ord(c))
    # Non-letters (and not '~'): highest group
    return (3, ord(c))


def _compare_nondigits(s1: str, s2: str) -> int:
    """Compare two non-digit strings according to Debian policy."""
    i = 0
    len1 = len(s1)
    len2 = len(s2)
    while i < len1 or i < len2:
        c1 = s1[i] if i < len1 else None
        c2 = s2[i] if i < len2 else None
        if c1 == c2:
            i += 1
            continue

        o1 = _order_char(c1)
        o2 = _order_char(c2)
        if o1 < o2:
            return -1
        elif o1 > o2:
            return 1
        else:
            i += 1
    return 0


def _compare_version_part(part1: str, part2: str) -> int:
    """
    Compare two version parts (upstream_version or debian_revision)
    according to Debian policy: alternating non-digit and digit sequences.
    """
    idx1 = 0
    idx2 = 0
    len1 = len(part1)
    len2 = len(part2)

    while idx1 < len1 or idx2 < len2:
        # 1. Grab non-digit chunk from part1 and part2
        nd1_start = idx1
        while idx1 < len1 and not part1[idx1].isdigit():
            idx1 += 1
        nd1 = part1[nd1_start:idx1]

        nd2_start = idx2
        while idx2 < len2 and not part2[idx2].isdigit():
            idx2 += 1
        nd2 = part2[nd2_start:idx2]

        cmp_nd = _compare_nondigits(nd1, nd2)
        if cmp_nd != 0:
            return cmp_nd

        # 2. Grab digit chunk from part1 and part2
        d1_start = idx1
        while idx1 < len1 and part1[idx1].isdigit():
            idx1 += 1
        d1 = part1[d1_start:idx1]

        d2_start = idx2
        while idx2 < len2 and part2[idx2].isdigit():
            idx2 += 1
        d2 = part2[d2_start:idx2]

        val1 = int(d1) if d1 else 0
        val2 = int(d2) if d2 else 0

        if val1 < val2:
            return -1
        elif val1 > val2:
            return 1

    return 0


def compare_debian_versions(v1: str, v2: str) -> int:
    """
    Compare two Debian versions.
    Returns:
      -1 if v1 < v2
       0 if v1 == v2
       1 if v1 > v2
    """
    dv1 = parse_debian_version(v1)
    dv2 = parse_debian_version(v2)

    # 1. Compare epoch
    if dv1.epoch < dv2.epoch:
        return -1
    elif dv1.epoch > dv2.epoch:
        return 1

    # 2. Compare upstream_version
    cmp_upstream = _compare_version_part(dv1.upstream_version, dv2.upstream_version)
    if cmp_upstream != 0:
        return cmp_upstream

    # 3. Compare debian_revision
    cmp_rev = _compare_version_part(dv1.debian_revision, dv2.debian_revision)
    return cmp_rev


# SemVer 2.0.0 Regex:
# MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
SEMVER_REGEX = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


def semver_to_debian(
    semver_str: str,
    debian_revision: Optional[str] = "1",
    epoch: int = 0,
    native: bool = False,
) -> str:
    """
    Convert a Semantic Version (SemVer 2.0.0) string to a valid Debian package version.

    Key rule for prereleases:
    In SemVer: 1.0.0-alpha.1 < 1.0.0
    In Debian: 1.0.0~alpha.1 < 1.0.0
    Therefore, SemVer prerelease '-' MUST map to '~'.
    """
    match = SEMVER_REGEX.match(semver_str.strip())
    if not match:
        raise ValueError(f"Invalid SemVer string: '{semver_str}'")

    major = match.group("major")
    minor = match.group("minor")
    patch = match.group("patch")
    prerelease = match.group("prerelease")
    build = match.group("build")

    upstream = f"{major}.{minor}.{patch}"

    if prerelease:
        # Replace hyphens with dots inside prerelease to keep it clean, prefix with '~'
        clean_prerelease = prerelease.replace("-", ".")
        upstream += f"~{clean_prerelease}"

    if build:
        # Build metadata in Debian can be appended with '+'
        clean_build = build.replace("-", ".")
        upstream += f"+{clean_build}"

    result = ""
    if epoch > 0:
        result += f"{epoch}:"
    result += upstream

    if not native and debian_revision:
        result += f"-{debian_revision}"

    return result


def debian_to_semver(debian_version_str: str) -> str:
    """
    Convert a Debian package version string back to SemVer representation where possible.
    e.g. 1.2.3~rc.1-1 -> 1.2.3-rc.1
    """
    parsed = parse_debian_version(debian_version_str)
    upstream = parsed.upstream_version

    # Split build metadata if present (+)
    build = None
    if "+" in upstream:
        upstream, build = upstream.split("+", 1)

    # Split prerelease if present (~)
    prerelease = None
    if "~" in upstream:
        upstream, prerelease = upstream.split("~", 1)

    # Ensure major.minor.patch
    parts = upstream.split(".")
    while len(parts) < 3:
        parts.append("0")
    semver = ".".join(parts[:3])

    if prerelease:
        semver += f"-{prerelease}"
    if build:
        semver += f"+{build}"

    return semver


def check_upgrade_path(current_ver: str, candidate_ver: str) -> dict:
    """
    Evaluate upgrade validity from current_ver to candidate_ver.
    Returns status: 'upgrade', 'downgrade', 'identical', or 'epoch_needed'.
    """
    parsed_curr = parse_debian_version(current_ver)
    parsed_cand = parse_debian_version(candidate_ver)

    cmp = compare_debian_versions(candidate_ver, current_ver)

    if cmp > 0:
        return {
            "status": "upgrade",
            "message": f"Valid upgrade: {candidate_ver} > {current_ver}",
            "allowed": True,
        }
    elif cmp == 0:
        return {
            "status": "identical",
            "message": f"Duplicate version: {candidate_ver} == {current_ver}",
            "allowed": False,
        }
    else:
        # Candidate is lower than current. Check if epoch bump would resolve it.
        needed_epoch = parsed_curr.epoch + 1
        cand_with_epoch = f"{needed_epoch}:{parsed_cand.upstream_version}"
        if parsed_cand.debian_revision:
            cand_with_epoch += f"-{parsed_cand.debian_revision}"

        return {
            "status": "downgrade",
            "message": f"Downgrade rejected: {candidate_ver} < {current_ver}",
            "allowed": False,
            "suggested_epoch_version": cand_with_epoch,
            "epoch_explanation": (
                f"Candidate version '{candidate_ver}' sorts lower than installed '{current_ver}'. "
                f"If upstream versioning scheme reset, bump epoch to '{needed_epoch}' (e.g. '{cand_with_epoch}')."
            ),
        }


def main():
    parser = argparse.ArgumentParser(
        description="M3tal Debian Versioning & SemVer Translation Engine (Phase 08)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # parse
    p_parse = subparsers.add_parser("parse", help="Parse Debian version into components")
    p_parse.add_argument("version", help="Version string to parse")
    p_parse.add_argument("--strip-v", action="store_true", help="Allow and strip leading 'v' prefix (for git tags)")

    # compare
    p_cmp = subparsers.add_parser("compare", help="Compare two Debian versions")
    p_cmp.add_argument("v1", help="First version")
    p_cmp.add_argument("v2", help="Second version")

    # from-semver
    p_from = subparsers.add_parser("from-semver", help="Convert SemVer to Debian version")
    p_from.add_argument("semver", help="SemVer string (e.g., 1.2.3-beta.1)")
    p_from.add_argument("--revision", default="1", help="Debian revision (default: 1)")
    p_from.add_argument("--epoch", type=int, default=0, help="Epoch (default: 0)")
    p_from.add_argument("--native", action="store_true", help="Native package (omit revision)")

    # to-semver
    p_to = subparsers.add_parser("to-semver", help="Convert Debian version to SemVer")
    p_to.add_argument("version", help="Debian version string")

    # validate
    p_val = subparsers.add_parser("validate", help="Validate Debian version syntax")
    p_val.add_argument("version", help="Version string to validate")

    # check-upgrade
    p_upg = subparsers.add_parser("check-upgrade", help="Check upgrade validity between versions")
    p_upg.add_argument("current", help="Current version in repository")
    p_upg.add_argument("candidate", help="Candidate version to publish")

    args = parser.parse_args()

    if args.command == "parse":
        try:
            parsed = parse_debian_version(args.version, allow_v_prefix=args.strip_v)
            print(f"Epoch:    {parsed.epoch}")
            print(f"Upstream: {parsed.upstream_version}")
            print(f"Revision: {parsed.debian_revision}")
            print(f"Canon:    {str(parsed)}")
            sys.exit(0)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "compare":
        try:
            res = compare_debian_versions(args.v1, args.v2)
            if res < 0:
                print(f"{args.v1} < {args.v2}")
                sys.exit(1)
            elif res > 0:
                print(f"{args.v1} > {args.v2}")
                sys.exit(2)
            else:
                print(f"{args.v1} == {args.v2}")
                sys.exit(0)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(3)

    elif args.command == "from-semver":
        try:
            deb_v = semver_to_debian(
                args.semver,
                debian_revision=args.revision,
                epoch=args.epoch,
                native=args.native,
            )
            print(deb_v)
            sys.exit(0)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "to-semver":
        try:
            sem_v = debian_to_semver(args.version)
            print(sem_v)
            sys.exit(0)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "validate":
        if is_valid_debian_version(args.version):
            print(f"VALID: {args.version}")
            sys.exit(0)
        else:
            print(f"INVALID: {args.version}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "check-upgrade":
        try:
            res = check_upgrade_path(args.current, args.candidate)
            print(f"Status:  {res['status']}")
            print(f"Message: {res['message']}")
            if not res["allowed"] and "epoch_explanation" in res:
                print(f"Note:    {res['epoch_explanation']}")
            sys.exit(0 if res["allowed"] else 1)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)


if __name__ == "__main__":
    main()
