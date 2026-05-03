"""Regenera scripts/dump.txt incluindo o bloco de skills/perks gerado a
partir de data/skills.tsv. As seções 'estáticas' (quests/inventário/cofre)
ficam num cabeçalho fixo; o bloco de skills é regerado.

Uso:
    python3 scripts/regen_dump.py
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_TSV = REPO / "data" / "skills.tsv"
DUMP_TXT = REPO / "scripts" / "dump.txt"

HEADER = """; Starfield console batch — dump de estado do jogador
; Uso no jogo: abra o console (~) e digite:  bat dump
; Requer: SFSE + "Console Output To File" (Nexus mod 3142)
; Saída em: <Starfield>/Data/SFSE/plugins/sfse_plugin_console.log
;
; Este arquivo é gerado por scripts/regen_dump.py — edições manuais no
; bloco "skills" serão sobrescritas. Edite data/skills.tsv para mudar.

; --- Quests ---
ShowQuests
ShowQuestObjectives
ShowQuestTargets

; --- Inventário do jogador ---
Player.ShowInventory

; --- Containers extras ---
; Cofre do quarto pessoal no Lodge (Nova Atlântida).
; FormID estático do CONTAINER (00266E81), distinto do ativador visual
; (0014BCEC) que aparece ao mirar e não aceita ShowInventory. Achado
; documentado em docs/limitacao-containers.md.
00266E81.ShowInventory

; --- Nível ---
Player.GetLevel

; --- Skills (ranks atuais) ---
; gerado a partir de data/skills.tsv
"""


def main() -> None:
    rows = []
    for raw in SKILLS_TSV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("form_id"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        rows.append(parts[:3])

    skill_block_lines = []
    # ordenar por tree depois nome para output legível no log
    rows.sort(key=lambda r: (r[2], r[1]))
    for form_id, name, tree in rows:
        skill_block_lines.append(f"Player.GetPerkRank {form_id}  ; {name} [{tree}]")

    DUMP_TXT.write_text(HEADER + "\n".join(skill_block_lines) + "\n", encoding="utf-8")
    print(f"escrito {DUMP_TXT}: {len(rows)} skills")


if __name__ == "__main__":
    main()
