"""Relatório de skills/perks a partir do JSON gerado por sfasst.parse_log.

Uso:
    python -m sfasst.skills_report <parsed.json>
    python -m sfasst.skills_report <parsed.json> --owned-only
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# rank → label de tier (gameplay): 1=Novice, 2=Advanced, 3=Expert, 4=Master
RANK_LABELS = {0: "—", 1: "Novato", 2: "Avançado", 3: "Especialista", 4: "Mestre"}


def render(parsed: dict, owned_only: bool = False) -> str:
    skills = parsed.get("skills", [])
    if not skills:
        return ("Nenhuma skill capturada. O dump.txt foi atualizado? "
                "Rode scripts/regen_dump.py + bat dump.")

    level = parsed.get("player_level")
    xp_next = parsed.get("player_xp_for_next_level")

    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("SKILLS / PERKS")
    head_parts: list[str] = []
    if level is not None:
        head_parts.append(f"Nível {level}")
    if xp_next is not None:
        head_parts.append(f"{xp_next} XP para o próximo")
    n_owned = sum(1 for s in skills if s["rank"] > 0)
    head_parts.append(f"{n_owned}/{len(skills)} skills com rank")
    lines.append(" • ".join(head_parts))
    lines.append("=" * 72)
    lines.append("")

    by_tree: dict[str, list[dict]] = defaultdict(list)
    for s in skills:
        by_tree[s["tree"]].append(s)

    tree_order = ["Combat", "Physical", "Science", "Social", "Tech", "?"]
    for tree in tree_order:
        items = by_tree.get(tree)
        if not items:
            continue
        items.sort(key=lambda s: (-s["rank"], s["name"]))
        owned = [s for s in items if s["rank"] > 0]
        unowned = [s for s in items if s["rank"] == 0]
        lines.append(f"── {tree.upper()} ({len(owned)}/{len(items)}) ──")
        for s in owned:
            tier = RANK_LABELS.get(s["rank"], f"R{s['rank']}")
            stars = "★" * s["rank"]
            lines.append(f"  {stars:<5} [{tier:<13}] {s['name']}")
        if unowned and not owned_only:
            lines.append(f"  ── não desbloqueadas ({len(unowned)}) ──")
            for s in unowned:
                lines.append(f"  ☆     [—            ] {s['name']}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("parsed", type=Path, help="JSON gerado por sfasst.parse_log")
    ap.add_argument("--owned-only", action="store_true",
                    help="esconde skills com rank 0")
    args = ap.parse_args(argv)
    data = json.loads(args.parsed.read_text(encoding="utf-8"))
    print(render(data, owned_only=args.owned_only))
    return 0


if __name__ == "__main__":
    sys.exit(main())
