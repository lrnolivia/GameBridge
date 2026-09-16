#!/usr/bin/env bash
set -euo pipefail
SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.local/share/gamebridge-lite"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICON_ROOT="$HOME/.local/share/icons/hicolor"
mkdir -p "$DEST" "$BIN" "$APPS"
cp "$SRC/GameBridge-Lite.py" "$DEST/"
cp "$SRC/gamebridge_core.py" "$DEST/"
cp "$SRC/gamebridge-lite" "$DEST/"
chmod +x "$DEST/GameBridge-Lite.py" "$DEST/gamebridge-lite"
ln -sfn "$DEST/gamebridge-lite" "$BIN/gamebridge-lite"
cp "$SRC/com.loew.gamebridgelite.desktop" "$APPS/com.loew.gamebridgelite.desktop"
sed -i "s|^Exec=.*|Exec=$BIN/gamebridge-lite|" "$APPS/com.loew.gamebridgelite.desktop"
for size_dir in "$SRC"/icons/hicolor/*x*/apps; do
    [ -d "$size_dir" ] || continue
    size_name="$(basename "$(dirname "$size_dir")")"
    mkdir -p "$ICON_ROOT/$size_name/apps"
    cp "$size_dir/com.loew.gamebridgelite.png" "$ICON_ROOT/$size_name/apps/com.loew.gamebridgelite.png"
done
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS" >/dev/null 2>&1 || true
fi
printf 'Installed GameBridge Lite with icon. Launch it from your app menu or run: %s
' "$BIN/gamebridge-lite"
