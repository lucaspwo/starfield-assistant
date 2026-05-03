"""Carrega configuração do .env (paths do jogo).

Procura em ordem:
1. variáveis de ambiente já setadas pelo shell
2. `<repo>/.env` (modo dev — `__file__` está dentro do repo)
3. `~/.config/starfield-assistant/.env`
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# Linha "KEY=VALUE" ou 'KEY="VALUE WITH SPACES"'. Aceita quotes simples ou duplas.
_RE_LINE = re.compile(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$')


def _parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _RE_LINE.match(line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        # remover aspas externas, se houver
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        out[key] = val
    return out


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    # 1. .env no repo (dev mode): subir até achar .git ou .env
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / ".env").is_file():
            paths.append(parent / ".env")
            break
        if (parent / ".git").exists():
            break
    # 2. ~/.config/starfield-assistant/.env
    user_cfg = Path.home() / ".config" / "starfield-assistant" / ".env"
    if user_cfg.is_file():
        paths.append(user_cfg)
    return paths


def load_env() -> dict[str, str]:
    """Retorna dict com STARFIELD_* keys. os.environ tem prioridade."""
    merged: dict[str, str] = {}
    for path in _candidate_paths():
        try:
            merged.update(_parse_env(path.read_text(encoding="utf-8")))
        except OSError:
            continue
    # variáveis do shell sobrepõem
    for key, val in os.environ.items():
        if key.startswith("STARFIELD_"):
            merged[key] = val
    return merged


def sfse_loader_path(cfg: dict[str, str] | None = None) -> Path | None:
    """Resolve o caminho do sfse_loader.exe.

    Ordem: STARFIELD_SFSE_LOADER explícito → derivado de STARFIELD_GAME_LOG
    (subindo 4 níveis até a raiz do jogo).
    """
    if cfg is None:
        cfg = load_env()
    explicit = cfg.get("STARFIELD_SFSE_LOADER")
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    log = cfg.get("STARFIELD_GAME_LOG")
    if not log:
        return None
    # .../Starfield/Data/SFSE/plugins/sfse_plugin_console.log
    # parents: [plugins, SFSE, Data, Starfield]
    log_path = Path(log)
    if len(log_path.parents) < 4:
        return None
    game_root = log_path.parents[3]
    loader = game_root / "sfse_loader.exe"
    return loader if loader.is_file() else None
