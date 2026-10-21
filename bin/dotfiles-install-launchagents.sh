#!/usr/bin/env bash
#===============================================================================
# dotfiles-install-launchagents.sh - Install all dotfiles LaunchAgents
#===============================================================================
#
# DESCRIPTION:
#   Installs LaunchAgents for automated dotfiles management:
#   - com.dotfiles.sync   : Syncs dotfiles every 4 hours
#   - com.dotfiles.update : Updates brew/zinit weekly (Fridays 9 AM)
#   - com.ashtonian.codex-remote-control : the local Codex app-server that
#     gptmore/gptmax connect to (only when codex is installed; see bin/codex-daemon
#     for the one-time Full Disk Access step)
#   - com.ashtonian.opencode : the OpenCode server (web UI + API) that `oc` attaches
#     to (only when opencode is installed; see stow/opencode/README.md)
#   - com.ashtonian.agent-monitor : the loopback Claude Code / Codex agent dashboard
#     (only after `agent-monitor install`; see docs/AGENT-MONITOR.md)
#   - com.ashtonian.agent-monitor-gate : its token-checked LAN gate (only after
#     `agent-monitor lan enable`)
#   - com.ashtonian.otel-agent : the local collector that forwards coding-agent
#     telemetry to the cluster (only after `otel-agent install` and `configure`;
#     see docs/AGENT-TELEMETRY.md)
#   - com.ashtonian.go-cache-trim : every six hours, deletes Go build cache
#     entries unused for 48 hours (only when go is installed; see bin/go-cache-trim)
#
# USAGE:
#   dotfiles-install-launchagents.sh [options]
#
# OPTIONS:
#   --sync-only    Install only the sync agent
#   --update-only  Install only the update agent
#   --codex-only   Install only the Codex app-server agent
#   --opencode-only  Install only the OpenCode server agent
#   --agent-monitor-only  Install only the agent dashboard (and its LAN gate when enabled)
#   --agent-monitor-gate-only  Install only the agent dashboard's LAN gate
#   --otel-agent-only  Install only the agent telemetry collector
#   --go-cache-trim-only  Install only the Go build cache trim
#   --uninstall    Remove all dotfiles LaunchAgents
#   --status       Show status of installed agents
#   --help         Show this help
#
#===============================================================================

set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.dotfiles}"
LAUNCH_AGENTS_SRC="$DOTFILES_DIR/launchagents"
LAUNCH_AGENTS_DST="$HOME/Library/LaunchAgents"
CODEX_AGENT="com.ashtonian.codex-remote-control"
OPENCODE_AGENT="com.ashtonian.opencode"
AGENT_MONITOR_AGENT="com.ashtonian.agent-monitor"
AGENT_MONITOR_GATE_AGENT="com.ashtonian.agent-monitor-gate"
OTEL_AGENT="com.ashtonian.otel-agent"
GO_CACHE_TRIM_AGENT="com.ashtonian.go-cache-trim"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

#===============================================================================
# FUNCTIONS
#===============================================================================

# agent_info prints launchd's record for a loaded agent and fails when it is not
# loaded. Asking for the label directly avoids piping the full `launchctl list`
# into `grep -q`, which under pipefail fails with SIGPIPE whenever the label is
# not near the end of the list.
agent_info() {
    launchctl list "$1" 2>/dev/null
}

install_agent() {
    local name="$1"
    local src="$LAUNCH_AGENTS_SRC/${name}.plist"
    local dst="$LAUNCH_AGENTS_DST/${name}.plist"

    if [[ ! -f "$src" ]]; then
        log_error "Source plist not found: $src"
        return 1
    fi

    # Create destination directory
    mkdir -p "$LAUNCH_AGENTS_DST"

    # Unload existing agent if running
    if agent_info "$name" >/dev/null; then
        log_info "Unloading existing $name..."
        launchctl unload "$dst" 2>/dev/null || true
    fi

    # Copy and process the plist (replace $HOME with actual path)
    log_info "Installing $name..."
    sed "s|\$HOME|$HOME|g" "$src" > "$dst"

    # Load the agent
    log_info "Loading $name..."
    if launchctl load "$dst"; then
        log_info "$name installed and running"
    else
        log_error "Failed to load $name"
        return 1
    fi
}

uninstall_agent() {
    local name="$1"
    local dst="$LAUNCH_AGENTS_DST/${name}.plist"

    if [[ -f "$dst" ]]; then
        log_info "Unloading $name..."
        launchctl unload "$dst" 2>/dev/null || true
        rm -f "$dst"
        log_info "$name removed"
    else
        log_warn "$name not installed"
    fi
}

# install_codex_agent installs the Codex app-server agent when codex is installed.
# The agent runs bin/codex-daemon, which keeps codex at a fixed path so one Full
# Disk Access grant survives upgrades; granting it is a manual, one-time step.
install_codex_agent() {
    if [[ ! -x /opt/homebrew/bin/codex ]]; then
        log_warn "codex is not installed (brew install --cask codex); skipping $CODEX_AGENT"
        return 0
    fi
    mkdir -p "$HOME/Library/Logs/CodexHomebrew" # launchd does not create log directories
    "$DOTFILES_DIR/bin/codex-daemon" --version >/dev/null # creates ~/.local/libexec/codex-stable
    install_agent "$CODEX_AGENT"
    log_info "One-time: grant Full Disk Access to ~/.local/libexec/codex-stable/bin/codex"
    log_info "  (System Settings > Privacy & Security > Full Disk Access > + > Cmd+Shift+G)"
}

# install_opencode_agent installs the OpenCode server agent when opencode is
# installed. Like codex it runs from a fixed path (bin/stable-exec), so one Full
# Disk Access grant survives upgrades; the server's password and LLM gateway
# credentials are local files that must exist first (stow/opencode/README.md).
install_opencode_agent() {
    if [[ ! -x /opt/homebrew/bin/opencode ]]; then
        log_warn "opencode is not installed (brew install anomalyco/tap/opencode); skipping $OPENCODE_AGENT"
        return 0
    fi
    if [[ ! -s "$HOME/.local/share/opencode/homelab/server-password" ]]; then
        log_warn "$HOME/.local/share/opencode/homelab is not set up (see stow/opencode/README.md); skipping $OPENCODE_AGENT"
        return 0
    fi
    mkdir -p "$HOME/Library/Logs/opencode" # launchd does not create log directories
    "$DOTFILES_DIR/bin/stable-exec" opencode --version >/dev/null # creates ~/.local/libexec/opencode-stable
    install_agent "$OPENCODE_AGENT"
    log_info "One-time: grant Full Disk Access to ~/.local/libexec/opencode-stable/bin/opencode"
    log_info "  (System Settings > Privacy & Security > Full Disk Access > + > Cmd+Shift+G)"
}

# install_agent_monitor_agent installs the agent dashboard once bin/agent-monitor
# has installed its release. The service's node reads the data volume, so the
# first start raises a one-time Removable Volumes prompt for that binary.
install_agent_monitor_agent() {
    if [[ ! -f "$HOME/.local/share/agent-monitor/app/server/index.js" ]]; then
        log_warn "agent-monitor is not installed (run $DOTFILES_DIR/bin/agent-monitor install); skipping $AGENT_MONITOR_AGENT"
        return 0
    fi
    mkdir -p "$HOME/Library/Logs/agent-monitor" # launchd does not create log directories
    install_agent "$AGENT_MONITOR_AGENT"
    log_info "One-time: allow node access to the data volume when macOS asks (Privacy & Security > Files and Folders)"
    install_agent_monitor_gate_agent
}

# install_agent_monitor_gate_agent installs the dashboard's LAN gate. LAN access
# is opt-in: the gate exists only once `agent-monitor lan enable` stored a token.
install_agent_monitor_gate_agent() {
    if [[ ! -s "$HOME/.local/share/agent-monitor/config/gate-token" ]]; then
        return 0
    fi
    mkdir -p "$HOME/Library/Logs/agent-monitor"
    install_agent "$AGENT_MONITOR_GATE_AGENT"
    log_info "One-time: allow node to accept incoming connections when the macOS firewall asks"
}

# install_otel_agent installs the telemetry collector once bin/otel-agent has
# installed its release and stored a gateway. The collector reaches the gateway
# on the LAN, so its first connection raises macOS's Local Network prompt.
install_otel_agent() {
    if [[ ! -s "$HOME/.local/share/otel-agent/endpoint" || ! -s "$HOME/.local/share/otel-agent/token" ]]; then
        log_warn "otel-agent is not configured (run $DOTFILES_DIR/bin/otel-agent configure); skipping $OTEL_AGENT"
        return 0
    fi
    if ! compgen -G "$HOME/.local/libexec/otelcol/*/otelcol" >/dev/null; then
        log_warn "otel-agent is not installed (run $DOTFILES_DIR/bin/otel-agent install); skipping $OTEL_AGENT"
        return 0
    fi
    mkdir -p "$HOME/Library/Logs/otel-agent" # launchd does not create log directories
    install_agent "$OTEL_AGENT"
    log_info "One-time: allow otelcol to find devices on the local network when macOS asks"
}

install_go_cache_trim_agent() {
    if [[ ! -x /opt/homebrew/bin/go ]]; then
        log_warn "go is not installed (brew install go); skipping $GO_CACHE_TRIM_AGENT"
        return 0
    fi
    mkdir -p "$HOME/Library/Logs/go-cache-trim" # launchd does not create log directories
    install_agent "$GO_CACHE_TRIM_AGENT"
}

show_status() {
    echo ""
    echo "=== Dotfiles LaunchAgents Status ==="
    echo ""

    for agent in com.dotfiles.sync com.dotfiles.update "$CODEX_AGENT" "$OPENCODE_AGENT" "$AGENT_MONITOR_AGENT" "$AGENT_MONITOR_GATE_AGENT" "$OTEL_AGENT" "$GO_CACHE_TRIM_AGENT"; do
        local dst="$LAUNCH_AGENTS_DST/${agent}.plist"
        printf "%-36s: " "$agent"

        if [[ -f "$dst" ]]; then
            local info
            if ! info=$(agent_info "$agent"); then
                echo -e "${YELLOW}Installed (not loaded)${NC}"
            elif [[ $info == *'"PID" = '* ]]; then
                echo -e "${GREEN}Running${NC}"
            else
                echo -e "${GREEN}Loaded (idle until scheduled)${NC}"
            fi
        else
            echo -e "${RED}Not installed${NC}"
        fi
    done

    echo ""
    echo "=== Recent Activity ==="
    echo ""

    if [[ -f "$DOTFILES_DIR/logs/sync.log" ]]; then
        echo "Last sync:"
        tail -3 "$DOTFILES_DIR/logs/sync.log" 2>/dev/null || echo "  No logs yet"
    fi

    if [[ -f "$DOTFILES_DIR/logs/update.log" ]]; then
        echo ""
        echo "Last update:"
        tail -3 "$DOTFILES_DIR/logs/update.log" 2>/dev/null || echo "  No logs yet"
    fi

    echo ""
}

show_help() {
    # The header comment, from its first line to the first line that is not a comment.
    awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
}

install_all() {
    echo ""
    echo "=== Installing Dotfiles LaunchAgents ==="
    echo ""

    install_agent "com.dotfiles.sync"
    install_agent "com.dotfiles.update"
    install_codex_agent
    install_opencode_agent
    install_agent_monitor_agent
    install_otel_agent
    install_go_cache_trim_agent

    echo ""
    echo "=== Installation Complete ==="
    echo ""
    echo "Sync agent:   Runs every 4 hours"
    echo "Update agent: Runs every Friday at 9 AM"
    echo ""
    echo "Commands:"
    echo "  Check status:    $0 --status"
    echo "  Manual sync:     ~/.dotfiles/sync.sh sync"
    echo "  Manual update:   ~/.dotfiles/bin/dotfiles-update.sh --all"
    echo "  Trigger sync:    launchctl start com.dotfiles.sync"
    echo "  Trigger update:  launchctl start com.dotfiles.update"
    echo ""
}

uninstall_all() {
    echo ""
    echo "=== Removing Dotfiles LaunchAgents ==="
    echo ""

    uninstall_agent "com.dotfiles.sync"
    uninstall_agent "com.dotfiles.update"
    uninstall_agent "$CODEX_AGENT"
    uninstall_agent "$OPENCODE_AGENT"
    uninstall_agent "$AGENT_MONITOR_AGENT"
    uninstall_agent "$AGENT_MONITOR_GATE_AGENT"
    uninstall_agent "$OTEL_AGENT"
    uninstall_agent "$GO_CACHE_TRIM_AGENT"

    echo ""
    echo "All LaunchAgents removed."
    echo ""
}

#===============================================================================
# MAIN
#===============================================================================

main() {
    case "${1:-}" in
        --sync-only)
            install_agent "com.dotfiles.sync"
            ;;
        --update-only)
            install_agent "com.dotfiles.update"
            ;;
        --codex-only)
            install_codex_agent
            ;;
        --opencode-only)
            install_opencode_agent
            ;;
        --agent-monitor-only)
            install_agent_monitor_agent
            ;;
        --agent-monitor-gate-only)
            install_agent_monitor_gate_agent
            ;;
        --otel-agent-only)
            install_otel_agent
            ;;
        --go-cache-trim-only)
            install_go_cache_trim_agent
            ;;
        --uninstall)
            uninstall_all
            ;;
        --status)
            show_status
            ;;
        --help|-h)
            show_help
            ;;
        "")
            install_all
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
