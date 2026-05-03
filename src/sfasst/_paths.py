"""Resolução de caminhos pra dados empacotados.

Os TSVs curados (skills, research, locations, system_aliases) e a fonte
externa (system_data.txt) ficam em `src/sfasst/data/` — co-localizados com
o package, então funcionam tanto no clone do repo quanto no wheel instalado.
"""
from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


def data_path(*parts: str) -> Path:
    """Retorna `src/sfasst/data/<parts...>`."""
    return DATA_DIR.joinpath(*parts)
