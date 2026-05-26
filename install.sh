#!/bin/bash
set -e

# M3TAL Core Repository Setup Script
# Usage: curl -fsSL https://jakej985-rgb.github.io/m3tal-apt-key/install.sh | sudo bash

REPO_URL="https://jakej985-rgb.github.io/m3tal-apt-key"
GPG_KEY_URL="${REPO_URL}/public.key"
KEYRING_PATH="/usr/share/keyrings/m3tal-archive-keyring.gpg"
LIST_PATH="/etc/apt/sources.list.d/m3tal.list"

echo "🚀 Setting up M3TAL Core APT Repository..."

# 1. Download and de-armor the GPG key
echo "📦 Importing GPG key..."
curl -fsSL "$GPG_KEY_URL" | gpg --dearmor | sudo tee "$KEYRING_PATH" > /dev/null
sudo chmod 644 "$KEYRING_PATH"

# 2. Add the repository to sources.list
echo "📝 Adding repository to sources..."
echo "deb [signed-by=$KEYRING_PATH] $REPO_URL stable main" | sudo tee "$LIST_PATH" > /dev/null

# 3. Update apt
echo "🔄 Updating package lists..."
sudo apt-get update

echo "✅ M3TAL Core repository is now configured!"
echo "   You can now install the agent with: sudo apt install m3tal"
