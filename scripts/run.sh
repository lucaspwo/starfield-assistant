#!/usr/bin/env bash
# Pipeline completa: traz o log mais recente do Starfield, parseia,
# cruza com inventário e mostra o relatório.
#
# Uso:
#   scripts/run.sh                # relatório de texto
#   scripts/run.sh --json         # JSON estruturado em vez do texto
#   scripts/run.sh -o relatorio.txt   # também grava no arquivo
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GAME_LOG="/mnt/c/Program Files (x86)/Steam/steamapps/common/Starfield/Data/SFSE/plugins/sfse_plugin_console.log"
SAVES_DIR="/mnt/c/Users/lucas/OneDrive/Documents/my games/Starfield/Saves"
LOG_DIR="$REPO/data/logs"
OUT_DIR="$REPO/out"

mkdir -p "$LOG_DIR" "$OUT_DIR"

if [[ ! -f "$GAME_LOG" ]]; then
    echo "erro: log do Starfield não encontrado em:" >&2
    echo "  $GAME_LOG" >&2
    echo "rode 'bat dump' no console do jogo antes." >&2
    exit 1
fi

# 1. trazer o log integral (cumulativo)
cp "$GAME_LOG" "$LOG_DIR/sfse_plugin_console.log"

# 2. extrair só a última invocação do bat dump (linhas a partir do último 'bat dump')
LAST_START=$(awk '/^bat dump/{n=NR} END{print (n?n:1)}' "$LOG_DIR/sfse_plugin_console.log")
TS=$(date +%Y%m%d_%H%M%S)
LATEST="$LOG_DIR/dump_${TS}.log"
awk -v start="$LAST_START" 'NR>=start' "$LOG_DIR/sfse_plugin_console.log" > "$LATEST"

# também atualiza o symlink "latest" pra conveniência
ln -sf "$(basename "$LATEST")" "$LOG_DIR/latest.log"

# 3. parsear → JSON
JSON="$OUT_DIR/latest.json"
PYTHONPATH="$REPO/src" python3 -m sfasst.parse_log "$LATEST" -o "$JSON"

# 4. resolver caminho do save mais recente pra extrair o nível
LATEST_SAVE=$(ls -t "$SAVES_DIR"/*.sfs 2>/dev/null | head -n1 || true)
SAVE_ARG=()
if [[ -n "$LATEST_SAVE" ]]; then
    SAVE_ARG=(--from-save "$LATEST_SAVE")
fi

# 5. relatório (passa argumentos extras como --json, -o, --player-level)
PYTHONPATH="$REPO/src" python3 -m sfasst.cross "$JSON" "${SAVE_ARG[@]}" "$@"
