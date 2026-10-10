#!/usr/bin/env bash
# ==============================================================================
# Drishti — Vultr Cloud Compute Startup Script (Cloud-Init)
# Paste this into the "Startup Script" field when launching a Vultr Instance
# Tested on: Ubuntu 22.04 LTS / Ubuntu 24.04 LTS
# ==============================================================================

set -euo pipefail

echo "========================================================"
echo " Starting Drishti Cloud Server Provisioning on Vultr"
echo "========================================================"

# 1. Update system packages
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get upgrade -y
apt-get install -y ca-certificates curl gnupg lsb-release git ufw fail2ban

# 2. Configure UFW Firewall for Vultr instance
echo "Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp     # SSH
ufw allow 80/tcp     # HTTP (Caddy / Let's Encrypt challenge)
ufw allow 443/tcp    # HTTPS (SSL)
ufw allow 8000/tcp   # Drishti Token Server direct port
ufw --force enable

# 3. Install Docker Engine & Docker Compose Plugin
echo "Installing Docker..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker

# 4. Prepare application directory
APP_DIR="/opt/drishti"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

echo "========================================================"
echo " Drishti Server Setup Completed Successfully!"
echo " Next steps:"
echo " 1. Clone your repo or copy code into $APP_DIR"
echo " 2. Copy .env.example to .env and configure your keys"
echo " 3. Run: docker compose up -d --build"
echo "========================================================"
