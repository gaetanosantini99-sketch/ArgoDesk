#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/argodesk-ui.service"

if [ ! -f "$SERVICE_FILE" ]; then
  echo "Error: argodesk-ui.service not found in $SCRIPT_DIR"
  exit 1
fi

echo "Installing ArgoDesk UI service..."
echo "Make sure you've edited argodesk-ui.service with your username and paths first!"
echo ""

sudo cp "$SERVICE_FILE" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable argodesk-ui
sudo systemctl start argodesk-ui
sudo systemctl status argodesk-ui
