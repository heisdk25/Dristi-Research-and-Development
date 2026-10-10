#!/usr/bin/env bash
# ==============================================================================
# Helper to install systemd services on Vultr VPS (Bare-metal Python mode)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Install uv if not already installed
if ! command -v uv &> /dev/null; then
    echo "Installing Astral uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    cp "$HOME/.local/bin/uv" /usr/local/bin/uv
fi

# Copy service files
echo "Registering systemd units..."
cp "$SCRIPT_DIR/drishti-token-server.service" /etc/systemd/system/
cp "$SCRIPT_DIR/drishti-agent.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable drishti-token-server.service
systemctl enable drishti-agent.service

systemctl restart drishti-token-server.service
systemctl restart drishti-agent.service

echo "Services started! Check status with:"
echo "systemctl status drishti-token-server"
echo "systemctl status drishti-agent"
