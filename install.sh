#!/usr/bin/env bash
# ==============================================================================
# M3tal Core APT Repository Universal Bootstrap Installer
# Official URL: https://jakej985-rgb.github.io/m3tal-apt-key/install.sh
# Usage:
#   curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/install.sh | sudo bash
#   or:
#   ./install.sh [OPTIONS]
# ==============================================================================

set -euo pipefail

if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd || true)"
else
    SCRIPT_DIR="$(pwd)"
fi

# --- Configuration & Defaults ---
REPO_URL="${REPO_URL:-https://jakej985-rgb.github.io/m3tal-apt-key}"
GPG_KEY_URL="${GPG_KEY_URL:-${REPO_URL}/public.key}"
CUSTOM_KEY_URL=false
EXPECTED_FINGERPRINT="5F84FE50A40111C981410E11775AD1473BF25102"

KEYRING_DIR="/etc/apt/keyrings"
KEYRING_PATH="${KEYRING_DIR}/m3tal-archive-keyring.gpg"
LEGACY_KEYRING_PATH="/usr/share/keyrings/m3tal-archive-keyring.gpg"
SOURCES_DIR="/etc/apt/sources.list.d"
SOURCES_LIST_PATH="${SOURCES_DIR}/m3tal.list"
SUITE="stable"
COMPONENTS="main"
DEFAULT_ARCH="amd64"

# CLI flag states
DRY_RUN=false
SKIP_UPDATE=false
FORCE_ARCH=false
UNINSTALL=false

# Terminal colors
BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Temporary storage management
TMP_DIR=""

cleanup() {
    local exit_code=$?
    if [[ -n "${TMP_DIR:-}" && -d "${TMP_DIR:-}" ]]; then
        rm -rf "${TMP_DIR}"
    fi
    exit "${exit_code}"
}
trap cleanup EXIT INT TERM ERR

log_info() {
    echo -e "${CYAN}==>${NC} ${BOLD}$*${NC}"
}

log_success() {
    echo -e "${GREEN}==> SUCCESS:${NC} ${BOLD}$*${NC}"
}

log_warn() {
    echo -e "${YELLOW}==> WARNING:${NC} $*" >&2
}

log_error() {
    echo -e "${RED}==> ERROR:${NC} ${BOLD}$*${NC}" >&2
}

show_help() {
    cat <<EOF
M3tal Core APT Repository Installer

Usage:
  install.sh [options]
  curl -fsSL ${REPO_URL}/install.sh | [sudo] bash [options]

Options:
  -d, --dry-run        Simulate operations without making filesystem modifications
  -n, --no-update      Configure repository and keys but skip 'apt-get update'
  -f, --force-arch     Force installation on non-amd64 architectures
  -u, --uninstall      Remove M3tal repository list and trusted keyring
  --repo-url URL       Override APT repository base URL (Default: ${REPO_URL})
  --key-url URL        Override GPG public key URL (Default: ${GPG_KEY_URL})
  --keyring PATH       Override target keyring path (Default: ${KEYRING_PATH})
  --sources-list PATH  Override sources.list file path (Default: ${SOURCES_LIST_PATH})
  -h, --help           Show this message
EOF
}

# Parse command line options
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -n|--no-update)
                SKIP_UPDATE=true
                shift
                ;;
            -f|--force-arch)
                FORCE_ARCH=true
                shift
                ;;
            -u|--uninstall)
                UNINSTALL=true
                shift
                ;;
            --repo-url)
                REPO_URL="$2"
                if [[ "${CUSTOM_KEY_URL}" != "true" ]]; then
                    GPG_KEY_URL="${REPO_URL}/public.key"
                fi
                shift 2
                ;;
            --key-url)
                GPG_KEY_URL="$2"
                CUSTOM_KEY_URL=true
                shift 2
                ;;
            --keyring)
                KEYRING_PATH="$2"
                KEYRING_DIR="$(dirname "$2")"
                shift 2
                ;;
            --sources-list)
                SOURCES_LIST_PATH="$2"
                SOURCES_DIR="$(dirname "$2")"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Elevated privilege runner helper
run_as_root() {
    if [[ "${DRY_RUN}" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} would run: $*"
        return 0
    fi

    if [[ "${EUID}" -eq 0 ]]; then
        "$@"
        return $?
    fi

    # If the target location is already writable by current user, execute directly
    if [[ "$1" == "mkdir" ]]; then
        local target_dir="${!#}"
        local p="${target_dir}"
        while [[ ! -d "${p}" && "${p}" != "/" && "${p}" != "." ]]; do
            p="$(dirname "${p}")"
        done
        if [[ -w "${p}" ]]; then
            "$@"
            return $?
        fi
    elif [[ "$1" == "cp" || "$1" == "mv" || "$1" == "rm" || "$1" == "chmod" ]]; then
        local dest="${!#}"
        local p
        p="$(dirname "${dest}")"
        if [[ -w "${p}" || ( -e "${dest}" && -w "${dest}" ) ]]; then
            "$@"
            return $?
        fi
    fi

    if command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        log_error "This script requires root privileges. Please run as root or install sudo."
        exit 1
    fi
}

# 1. Compatibility Check (Debian/Ubuntu/derivatives)
check_distribution() {
    log_info "Detecting distribution compatibility..."
    if [[ ! -f /etc/os-release && ! -f /etc/debian_version ]]; then
        log_error "Unsupported operating system: Neither /etc/os-release nor /etc/debian_version found."
        log_error "The M3tal APT repository requires a Debian or Ubuntu compatible Linux distribution."
        exit 1
    fi

    local dist_id=""
    local id_like=""
    if [[ -f /etc/os-release ]]; then
        # Safely extract ID and ID_LIKE even if file has syntax errors
        dist_id="$(grep -E '^ID=' /etc/os-release 2>/dev/null | head -n 1 | cut -d= -f2- | sed -e 's/["\x27]//g' || true)"
        id_like="$(grep -E '^ID_LIKE=' /etc/os-release 2>/dev/null | head -n 1 | cut -d= -f2- | sed -e 's/["\x27]//g' || true)"
        # Try sourcing as well if variables were empty
        if [[ -z "${dist_id}" ]]; then
            (source /etc/os-release 2>/dev/null) && {
                # shellcheck disable=SC1091
                source /etc/os-release 2>/dev/null || true
                dist_id="${ID:-}"
                id_like="${ID_LIKE:-}"
            } || true
        fi
    fi

    dist_id="$(echo "${dist_id}" | tr '[:upper:]' '[:lower:]')"
    id_like="$(echo "${id_like}" | tr '[:upper:]' '[:lower:]')"

    local compatible=false
    for match in debian ubuntu mint pop elementary raspbian kali devuan zorin neon armbian parrot pureos tails deepin tuxedo; do
        if [[ "${dist_id}" == *"${match}"* || "${id_like}" == *"${match}"* ]]; then
            compatible=true
            break
        fi
    done

    if [[ -f /etc/debian_version ]]; then
        compatible=true
    fi

    if [[ "${compatible}" != "true" ]]; then
        log_error "Unsupported distribution '${dist_id}'. Only Debian/Ubuntu compatible systems are supported."
        exit 1
    fi
    log_info "Distribution verified: ${dist_id:-Debian-family} (${id_like:-debian-derived})"
}

# 2. CPU Architecture Check
check_architecture() {
    log_info "Detecting CPU architecture..."
    local arch=""
    if command -v dpkg >/dev/null 2>&1; then
        arch="$(dpkg --print-architecture)"
    else
        local m
        m="$(uname -m)"
        case "$m" in
            x86_64) arch="amd64" ;;
            aarch64|arm64) arch="arm64" ;;
            armv7l|armhf) arch="armhf" ;;
            i386|i686) arch="i386" ;;
            *) arch="$m" ;;
        esac
    fi

    if [[ "${arch}" != "${DEFAULT_ARCH}" ]]; then
        log_warn "Current architecture is '${arch}', but official M3tal binary packages are currently provided for '${DEFAULT_ARCH}'."
        if [[ "${FORCE_ARCH}" != "true" ]]; then
            log_warn "To proceed anyway, run with --force-arch or set FORCE_ARCH=true."
            exit 1
        else
            log_info "Forcing setup on architecture '${arch}' due to --force-arch."
        fi
    else
        log_info "Architecture verified: ${arch}"
    fi
}

# 3. Prerequisites check & auto-installation
check_prerequisites() {
    log_info "Checking required utilities (curl/wget, gpg, apt)..."
    local missing=()

    if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
        missing+=("curl")
    fi
    if ! command -v gpg >/dev/null 2>&1; then
        missing+=("gnupg")
    fi
    if ! command -v apt-get >/dev/null 2>&1; then
        log_error "'apt-get' not found. This bootstrap installer is intended for Debian/Ubuntu systems."
        exit 1
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_warn "Missing required packages: ${missing[*]}"
        if [[ "${DRY_RUN}" == "true" ]]; then
            echo -e "${YELLOW}[DRY-RUN]${NC} would install: apt-get install -y --no-install-recommends ${missing[*]}"
        else
            log_info "Installing missing dependencies automatically..."
            run_as_root apt-get update -qq || true
            run_as_root apt-get install -y --no-install-recommends "${missing[@]}"
        fi
    fi
}

# 4. Uninstall action
uninstall_repository() {
    log_info "Uninstalling M3tal APT repository and key material..."
    if [[ -f "${SOURCES_LIST_PATH}" ]]; then
        log_info "Removing ${SOURCES_LIST_PATH}..."
        run_as_root rm -f "${SOURCES_LIST_PATH}"
    fi
    if [[ -f "${KEYRING_PATH}" ]]; then
        log_info "Removing ${KEYRING_PATH}..."
        run_as_root rm -f "${KEYRING_PATH}"
    fi
    # Only clean legacy keyring if operating on the standard system keyring path
    if [[ "${KEYRING_PATH}" == "/etc/apt/keyrings/m3tal-archive-keyring.gpg" && -f "${LEGACY_KEYRING_PATH}" ]]; then
        log_info "Removing legacy keyring ${LEGACY_KEYRING_PATH}..."
        run_as_root rm -f "${LEGACY_KEYRING_PATH}"
    fi

    if [[ "${SKIP_UPDATE}" != "true" ]]; then
        log_info "Refreshing package lists..."
        run_as_root apt-get update || true
    fi

    log_success "M3tal APT repository has been completely removed from this system."
    exit 0
}

# 5. Key Retrieval, Fingerprint Verification & Keyring Installation
install_keyring() {
    log_info "Downloading and validating M3tal signing key..."

    if [[ "${DRY_RUN}" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} would download key from: ${GPG_KEY_URL}"
        echo -e "${YELLOW}[DRY-RUN]${NC} would verify key fingerprint against: ${EXPECTED_FINGERPRINT}"
        echo -e "${YELLOW}[DRY-RUN]${NC} would dearmor and install keyring to: ${KEYRING_PATH} (mode 0644)"
        return 0
    fi

    TMP_DIR="$(mktemp -d /tmp/m3tal_bootstrap_XXXXXX)"
    chmod 700 "${TMP_DIR}"

    local raw_key="${TMP_DIR}/m3tal.key"
    local dearmored_key="${TMP_DIR}/keyring.gpg"
    local gpg_homedir="${TMP_DIR}/gnupg"
    mkdir -p -m 700 "${gpg_homedir}"

    # Download or copy key
    if [[ -f "${GPG_KEY_URL}" ]]; then
        cp "${GPG_KEY_URL}" "${raw_key}"
    elif [[ "${GPG_KEY_URL}" =~ ^file:// ]]; then
        local local_path="${GPG_KEY_URL#file://}"
        cp "${local_path}" "${raw_key}"
    elif [[ -f "${SCRIPT_DIR}/public.key" && "${GPG_KEY_URL}" == "https://jakej985-rgb.github.io/m3tal-apt-key/public.key" ]]; then
        # Local checkout fallback if network is disconnected or DNS unresolvable
        local downloaded=false
        if command -v curl >/dev/null 2>&1; then
            if curl -fsSL --connect-timeout 2 --max-time 5 "${GPG_KEY_URL}" -o "${raw_key}" 2>/dev/null; then
                downloaded=true
            fi
        elif command -v wget >/dev/null 2>&1; then
            if wget -q --timeout=3 -O "${raw_key}" "${GPG_KEY_URL}" 2>/dev/null; then
                downloaded=true
            fi
        fi

        if [[ "${downloaded}" != "true" ]]; then
            log_warn "Network unavailable or download failed; using local repository key: ${SCRIPT_DIR}/public.key"
            cp "${SCRIPT_DIR}/public.key" "${raw_key}"
        fi
    elif command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 3 --connect-timeout 10 "${GPG_KEY_URL}" -o "${raw_key}"
    else
        wget -qO "${raw_key}" "${GPG_KEY_URL}"
    fi

    if [[ ! -s "${raw_key}" ]]; then
        log_error "Failed to retrieve signing key from ${GPG_KEY_URL}"
        exit 1
    fi

    # Dearmor public key
    gpg --dearmor < "${raw_key}" > "${dearmored_key}"

    # Extract fingerprint
    local extracted_fpr=""
    extracted_fpr="$(GNUPGHOME="${gpg_homedir}" gpg --with-colons --show-keys "${dearmored_key}" 2>/dev/null | awk -F: '$1 == "fpr" { print $10; exit }' || true)"

    if [[ -z "${extracted_fpr}" ]]; then
        # Fallback inspection via import
        GNUPGHOME="${gpg_homedir}" gpg --quiet --import "${raw_key}" 2>/dev/null || true
        extracted_fpr="$(GNUPGHOME="${gpg_homedir}" gpg --with-colons --fingerprint 2>/dev/null | awk -F: '$1 == "fpr" { print $10; exit }' || true)"
    fi

    # Normalize fingerprints (remove whitespace, uppercase)
    extracted_fpr="$(echo "${extracted_fpr}" | tr -d ' ' | tr '[:lower:]' '[:upper:]')"
    local expected_norm
    expected_norm="$(echo "${EXPECTED_FINGERPRINT}" | tr -d ' ' | tr '[:lower:]' '[:upper:]')"

    if [[ "${extracted_fpr}" != "${expected_norm}" ]]; then
        log_error "SECURITY ALERT: GPG fingerprint mismatch!"
        log_error "  Expected: ${expected_norm}"
        log_error "  Received: ${extracted_fpr}"
        log_error "Aborting installation to prevent potential compromise."
        exit 1
    fi
    log_info "Key fingerprint verified: ${extracted_fpr}"

    # Check idempotency
    local needs_key_write=true
    if [[ -f "${KEYRING_PATH}" ]]; then
        if cmp -s "${dearmored_key}" "${KEYRING_PATH}"; then
            log_info "Keyring at ${KEYRING_PATH} is already up-to-date."
            needs_key_write=false
        fi
    fi

    if [[ "${needs_key_write}" == "true" ]]; then
        log_info "Installing trusted keyring to ${KEYRING_PATH}..."
        run_as_root mkdir -p -m 0755 "${KEYRING_DIR}"
        run_as_root cp "${dearmored_key}" "${KEYRING_PATH}.tmp"
        run_as_root chmod 0644 "${KEYRING_PATH}.tmp"
        run_as_root mv "${KEYRING_PATH}.tmp" "${KEYRING_PATH}"
    fi

    # Clean up legacy keyring if installing to official system path and legacy file exists
    if [[ "${KEYRING_PATH}" == "/etc/apt/keyrings/m3tal-archive-keyring.gpg" && -f "${LEGACY_KEYRING_PATH}" ]]; then
        log_info "Cleaning up legacy keyring at ${LEGACY_KEYRING_PATH}..."
        run_as_root rm -f "${LEGACY_KEYRING_PATH}"
    fi
}

# 6. APT Source Definition Installation
install_apt_source() {
    log_info "Configuring APT repository source list..."
    local source_line="deb [arch=${DEFAULT_ARCH} signed-by=${KEYRING_PATH}] ${REPO_URL} ${SUITE} ${COMPONENTS}"

    if [[ "${DRY_RUN}" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} would write to: ${SOURCES_LIST_PATH}"
        echo -e "${YELLOW}[DRY-RUN]${NC} content: ${source_line}"
        return 0
    fi

    local needs_list_write=true
    if [[ -f "${SOURCES_LIST_PATH}" ]]; then
        local current_content
        current_content="$(grep -v '^[[:space:]]*#' "${SOURCES_LIST_PATH}" | grep -v '^[[:space:]]*$' | tr -s ' ' || true)"
        local target_content
        target_content="$(echo "${source_line}" | tr -s ' ')"
        if [[ "${current_content}" == "${target_content}" ]]; then
            log_info "Repository source ${SOURCES_LIST_PATH} is already configured correctly."
            needs_list_write=false
        fi
    fi

    if [[ "${needs_list_write}" == "true" ]]; then
        log_info "Writing ${SOURCES_LIST_PATH}..."
        local tmp_list="${TMP_DIR}/m3tal.list"
        cat <<EOF > "${tmp_list}"
# Official M3tal Core APT Repository
# Documentation: https://jakej985-rgb.github.io/m3tal-apt-key/
${source_line}
EOF
        run_as_root mkdir -p -m 0755 "${SOURCES_DIR}"
        run_as_root cp "${tmp_list}" "${SOURCES_LIST_PATH}.tmp"
        run_as_root chmod 0644 "${SOURCES_LIST_PATH}.tmp"
        run_as_root mv "${SOURCES_LIST_PATH}.tmp" "${SOURCES_LIST_PATH}"
    fi
}

# 7. Update APT package lists
update_apt() {
    if [[ "${SKIP_UPDATE}" == "true" ]]; then
        log_info "Skipping 'apt-get update' due to --no-update flag."
        return 0
    fi

    if [[ "${DRY_RUN}" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} would synchronize package lists via 'apt-get update'"
        return 0
    fi

    log_info "Synchronizing APT package indices..."
    # Attempt targeted update first, fallback to general update
    if ! run_as_root apt-get update -o Dir::Etc::sourcelist="sources.list.d/m3tal.list" -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0"; then
        log_warn "Targeted index sync returned non-zero status; performing standard 'apt-get update'..."
        run_as_root apt-get update
    fi
}

# --- Main Flow ---
main() {
    parse_arguments "$@"

    echo -e "${BOLD}======================================================${NC}"
    echo -e "${BOLD}       M3tal Core Universal Repository Bootstrap      ${NC}"
    echo -e "${BOLD}======================================================${NC}"

    if [[ "${UNINSTALL}" == "true" ]]; then
        uninstall_repository
    fi

    check_distribution
    check_architecture
    check_prerequisites
    install_keyring
    install_apt_source
    update_apt

    echo -e "${BOLD}======================================================${NC}"
    log_success "M3tal repository has been successfully configured!"
    echo -e "Keyring: ${CYAN}${KEYRING_PATH}${NC}"
    echo -e "Source:  ${CYAN}${SOURCES_LIST_PATH}${NC}"
    echo ""
    echo -e "You can now install packages using:"
    echo -e "  ${BOLD}sudo apt install m3tal${NC}"
    echo -e "${BOLD}======================================================${NC}"
}

main "$@"
