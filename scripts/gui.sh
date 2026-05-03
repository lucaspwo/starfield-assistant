#!/usr/bin/env bash
# Abre a GUI do Starfield Assistant.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec env PYTHONPATH="$REPO/src" python3 -m sfasst.gui "$@"
