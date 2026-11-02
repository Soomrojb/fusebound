#!/usr/bin/env bash
# Adds Fusebound to your desktop's application menu.
set -e
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/fusebound.desktop <<DESK
[Desktop Entry]
Type=Application
Name=Fusebound
Comment=Grid-arena bomb battler
Exec=$DIR/run.sh
Path=$DIR
Icon=applications-games
Terminal=false
Categories=Game;ArcadeGame;
DESK
echo "Installed: ~/.local/share/applications/fusebound.desktop"
