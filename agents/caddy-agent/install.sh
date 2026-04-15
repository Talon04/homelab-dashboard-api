#!/bin/bash
# =============================================================================
# CADDY MANAGER INSTALLER - Install script for caddy-manager service
# =============================================================================
# Installation script for Caddy Manager service from homelab-dashboard-api repo
# 
# Usage:
#   sudo bash install.sh
#   sudo bash install.sh --repo /path/to/repo
#   sudo bash install.sh --help
#

set -e

# =============================================================================
# CONFIGURATION
# =============================================================================

REPO_URL="https://github.com/Talon04/homelab-dashboard-api.git"
REPO_DIR="${REPO_DIR:-./homelab-dashboard-api}"
INSTALL_DIR="/opt/caddy-manager"
DATA_DIR="/var/lib/caddy-manager"
SERVICE_NAME="caddy-manager"
SERVICE_USER="caddy"
SERVICE_GROUP="caddy"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =============================================================================
# FUNCTIONS
# =============================================================================

print_help() {
    cat << EOF
Caddy Manager Installer

Usage: sudo bash install.sh [OPTIONS]

Options:
  --repo PATH          Path to homelab-dashboard-api repo (default: ./homelab-dashboard-api)
  --install-dir PATH   Installation directory (default: /opt/caddy-manager)
  --data-dir PATH      Data directory (default: /var/lib/caddy-manager)
  --no-start           Install but don't start the service
  --help               Show this help message

Examples:
  sudo bash install.sh
  sudo bash install.sh --repo /home/user/projects/homelab-dashboard-api
  sudo bash install.sh --no-start

EOF
}

log_info() {
    echo -e "${GREEN}[*]${NC} $1"
}

log_error() {
    echo -e "${RED}[!]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "Required command not found: $1"
        exit 1
    fi
}

check_user_exists() {
    if ! id "$1" &>/dev/null; then
        log_error "User '$1' does not exist"
        exit 1
    fi
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    elif [ -f /etc/redhat-release ]; then
        echo "rhel"
    elif [ -f /etc/debian_version ]; then
        echo "debian"
    else
        echo "unknown"
    fi
}

install_python_packages() {
    local os=$(detect_os)
    
    log_info "Installing Python packages for $os..."
    
    case "$os" in
        ubuntu|debian)
            apt-get update
            apt-get install -y python3-flask python3-werkzeug
            ;;
        fedora|rhel|centos)
            dnf install -y python3-flask python3-werkzeug || yum install -y python3-flask python3-werkzeug
            ;;
        *)
            log_error "Unsupported OS: $os"
            log_info "Please manually install: Flask and Werkzeug"
            exit 1
            ;;
    esac
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    local no_start=false
    
    log_info "Caddy Manager Installation Script"
    echo ""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help)
                print_help
                exit 0
                ;;
            --repo)
                REPO_DIR="$2"
                shift 2
                ;;
            --install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            --data-dir)
                DATA_DIR="$2"
                shift 2
                ;;
            --no-start)
                no_start=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                print_help
                exit 1
                ;;
        esac
    done
    
    # Verify root
    check_root
    
    # Check required commands
    log_info "Checking required commands..."
    check_command python3
    check_command git
    check_command systemctl
    
    # Install system Python packages
    log_info "Installing system Python packages..."
    install_python_packages
    
    # Check if caddy binary exists
    if ! command -v caddy &> /dev/null; then
        log_warn "Caddy binary not found - validation will fail at runtime"
    fi
    
    # Check if user exists
    log_info "Checking if '$SERVICE_USER' user exists..."
    check_user_exists "$SERVICE_USER"
    
    # Clone/update repo if needed
    if [ ! -d "$REPO_DIR" ]; then
        log_info "Cloning repo from $REPO_URL..."
        git clone "$REPO_URL" "$REPO_DIR"
    else
        log_info "Repo already exists at $REPO_DIR, pulling latest..."
        cd "$REPO_DIR"
        git pull
        cd - > /dev/null
    fi
    
    # Check if agents/caddy-agent exists
    if [ ! -d "$REPO_DIR/agents/caddy-agent" ]; then
        log_error "agents/caddy-agent not found in repo at $REPO_DIR"
        exit 1
    fi
    
    # Create installation directory
    log_info "Creating installation directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    
    # Copy files
    log_info "Copying files to $INSTALL_DIR..."
    cp -r "$REPO_DIR/agents/caddy-agent/"* "$INSTALL_DIR/"
    
    # Create data directory
    log_info "Creating data directory: $DATA_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "$DATA_DIR/backups"
    mkdir -p "$DATA_DIR/temp"

    # Set permissions
    log_info "Setting permissions..."
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$DATA_DIR"
    chmod 750 "$DATA_DIR"
    chmod 750 "$INSTALL_DIR"
    
    # Install systemd service
    log_info "Installing systemd service..."
    cp "$INSTALL_DIR/caddy-manager.service" "/etc/systemd/system/$SERVICE_NAME.service"
    chmod 644 "/etc/systemd/system/$SERVICE_NAME.service"
    
    # Update systemd service with correct paths
    log_info "Updating systemd service with correct paths..."
    sed -i "s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|g" "/etc/systemd/system/$SERVICE_NAME.service"
    sed -i "s|Environment=\"CADDY_MANAGER_DATA=.*\"|Environment=\"CADDY_MANAGER_DATA=$DATA_DIR\"|g" "/etc/systemd/system/$SERVICE_NAME.service"
    
    # Reload systemd
    log_info "Reloading systemd..."
    systemctl daemon-reload
    
    # Enable service
    log_info "Enabling $SERVICE_NAME service..."
    systemctl enable "$SERVICE_NAME"
    
    # Start service if not --no-start
    if [ "$no_start" = false ]; then
        log_info "Starting $SERVICE_NAME service..."
        systemctl start "$SERVICE_NAME"
        
        # Wait a moment for service to start
        sleep 2
        
        # Check status
        log_info "Checking service status..."
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            log_info "✓ Service is running!"
        else
            log_error "Service failed to start. Check logs:"
            journalctl -u "$SERVICE_NAME" -n 20 --no-pager
            exit 1
        fi
    else
        log_info "Service installed but not started (use --no-start)"
    fi
    
    echo ""
    log_info "Installation complete!"
    echo ""
    echo "Installation Summary:"
    echo "  Install directory: $INSTALL_DIR"
    echo "  Data directory:    $DATA_DIR"
    echo "  Service name:      $SERVICE_NAME"
    echo "  Service user:      $SERVICE_USER"
    echo ""
    echo "Useful commands:"
    echo "  sudo systemctl status $SERVICE_NAME"
    echo "  sudo systemctl restart $SERVICE_NAME"
    echo "  sudo journalctl -u $SERVICE_NAME -f"
    echo "  curl http://localhost:9999/health"
    echo ""
}

# Run main
main "$@"
