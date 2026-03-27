#!/usr/bin/env bash
# NeedIt DevTraining - ServiceNow Application Installer
# Helps set up the NeedIt training application for ServiceNow development

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

REPO_URL="https://github.com/michaelmowrey/devtraining-needit-newyork.git"
APP_SCOPE="x_58872_needit"
APP_NAME="NeedIt"

print_banner() {
  echo -e "${BOLD}${CYAN}"
  echo "╔══════════════════════════════════════════════╗"
  echo "║   NeedIt DevTraining — ServiceNow Installer  ║"
  echo "║   App Scope: ${APP_SCOPE}        ║"
  echo "╚══════════════════════════════════════════════╝"
  echo -e "${NC}"
}

check_prerequisites() {
  info "Checking prerequisites..."

  if ! command -v git &>/dev/null; then
    error "git is required but not installed. Install git and retry."
  fi
  success "git found: $(git --version)"
}

clone_or_update_repo() {
  local target_dir="${1:-needit-newyork}"

  if [[ -d "$target_dir/.git" ]]; then
    info "Repository already exists at '$target_dir'. Pulling latest changes..."
    git -C "$target_dir" pull origin master
    success "Repository updated."
  else
    info "Cloning NeedIt repository into '$target_dir'..."
    git clone "$REPO_URL" "$target_dir"
    success "Repository cloned."
  fi

  echo "$target_dir"
}

verify_checksum() {
  local repo_dir="$1"

  if [[ -f "$repo_dir/checksum.txt" ]]; then
    success "Checksum file found."
  else
    warn "No checksum.txt found — repository may be incomplete."
  fi

  if [[ -f "$repo_dir/sys_app_6ead8e780f603200cd674f8ce1050ed1.xml" ]]; then
    success "Application XML found (${APP_NAME})."
  else
    error "Application XML not found. Repository may be corrupt."
  fi
}

print_import_instructions() {
  local repo_dir="$1"
  local abs_dir
  abs_dir="$(cd "$repo_dir" && pwd)"

  echo ""
  echo -e "${BOLD}Next Steps — Import into ServiceNow:${NC}"
  echo "──────────────────────────────────────────────"
  echo ""
  echo "  1. Log in to your ServiceNow developer instance."
  echo ""
  echo "  2. Navigate to:"
  echo "       Studio  →  Import From Source Control"
  echo ""
  echo "  3. Enter the following repository URL:"
  echo -e "       ${CYAN}${REPO_URL}${NC}"
  echo ""
  echo "  4. Select branch: ${BOLD}master${NC}"
  echo ""
  echo "  5. After import, verify the app scope:"
  echo -e "       ${CYAN}${APP_SCOPE}${NC}"
  echo ""
  echo "  6. Activate the ${BOLD}${APP_NAME}${NC} application and begin training."
  echo ""
  echo -e "${YELLOW}Note:${NC} Do not edit files outside a ServiceNow instance."
  echo "      See README.md for recovery instructions if needed."
  echo ""
}

main() {
  print_banner
  check_prerequisites

  # Detect if running via curl | bash (no local directory context)
  local repo_dir
  if [[ -f "./sys_app_6ead8e780f603200cd674f8ce1050ed1.xml" ]]; then
    # Already inside the repo
    repo_dir="."
    info "Running from within the repository."
    verify_checksum "$repo_dir"
  else
    # Clone the repo
    repo_dir=$(clone_or_update_repo "needit-newyork")
    verify_checksum "$repo_dir"
  fi

  print_import_instructions "$repo_dir"

  echo -e "${GREEN}${BOLD}Setup complete! Follow the steps above to import into ServiceNow.${NC}"
}

main "$@"
