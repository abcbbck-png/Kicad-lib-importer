#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PLUGIN_SRC="$REPO_ROOT/plugins/connector-generator/connector_generator_plugin"

if [[ ! -d "$PLUGIN_SRC" ]]; then
  echo "Plugin source not found: $PLUGIN_SRC" >&2
  exit 1
fi

version=""
if command -v kicad-cli >/dev/null 2>&1; then
  version="$(kicad-cli version 2>/dev/null | sed -n 's/^\\([0-9][0-9]*\\.[0-9][0-9]*\\).*/\\1/p' | head -n1)"
fi

if [[ -z "$version" ]]; then
  version="10.0"
fi

PLUGIN_DIR="${KICAD_PLUGIN_DIR:-$HOME/.local/share/kicad/$version/scripting/plugins}"
PLUGIN_DEST="$PLUGIN_DIR/connector_generator_plugin"

mkdir -p "$PLUGIN_DIR"

if [[ -e "$PLUGIN_DEST" || -L "$PLUGIN_DEST" ]]; then
  current="$(readlink -f "$PLUGIN_DEST" 2>/dev/null || true)"
  source_real="$(readlink -f "$PLUGIN_SRC")"
  if [[ "$current" != "$source_real" ]]; then
    echo "Destination already exists and is not this plugin:" >&2
    echo "  $PLUGIN_DEST" >&2
    echo "Remove it manually or set KICAD_PLUGIN_DIR." >&2
    exit 1
  fi
else
  ln -s "$PLUGIN_SRC" "$PLUGIN_DEST"
fi

echo "Connector Generator plugin installed:"
echo "  $PLUGIN_DEST -> $PLUGIN_SRC"
echo
echo "Restart KiCad, then open:"
echo "  PCB Editor -> Tools -> External Plugins -> Generate Connector Symbols"
