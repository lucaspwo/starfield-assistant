"""Sugestões de skills focadas no próximo rank a investir, baseadas em
unlocks curados em data/skills.tsv (colunas unlock_r1..unlock_r4).

Lê o rank atual do jogador no parsed.json e, pra cada skill com unlock
curado, mostra o que o próximo rank desbloqueia. Agrupa por árvore.

Uso:
    python -m sfasst.skill_suggestions <parsed.json>
    python -m sfasst.skill_suggestions <parsed.json> --tree Combat
    python -m sfasst.skill_suggestions <parsed.json> --owned-only
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from sfasst._paths import data_path

SKILLS_TSV = data_path("skills.tsv")

MAX_RANK = 4


@dataclass
class SkillUnlocks:
    form_id: str
    name: str
    tree: str
    unlocks: list[str] = field(default_factory=list)  # índice = rank-1 (rank 1..4)

    @property
    def has_curated(self) -> bool:
        return any(u for u in self.unlocks)


def load_skills() -> dict[str, SkillUnlocks]:
    """form_id (upper) -> SkillUnlocks."""
    out: dict[str, SkillUnlocks] = {}
    if not SKILLS_TSV.exists():
        return out
    for raw in SKILLS_TSV.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\r\n")
        if not line.strip() or line.startswith("form_id"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        form_id = parts[0].strip().upper()
        name = parts[1].strip()
        tree = parts[2].strip()
        unlocks = [(parts[i].strip() if i < len(parts) else "") for i in (3, 4, 5, 6)]
        out[form_id] = SkillUnlocks(form_id=form_id, name=name, tree=tree, unlocks=unlocks)
    return out


def render(
    parsed: dict,
    tree_filter: str | None = None,
    owned_only: bool = False,
    show_uncurated: bool = False,
) -> str:
    catalog = load_skills()
    if not catalog:
        return f"erro: {SKILLS_TSV} não encontrado ou vazio."

    # Player current ranks, indexed by form_id
    player_ranks: dict[str, int] = {}
    for s in parsed.get("skills", []):
        # parsed.json acumula entries se o log tiver vários bat dumps;
        # ficamos com o último por form_id
        player_ranks[s["form_id"].upper()] = s["rank"]

    # Construir lista de sugestões
    suggestions: list[tuple[SkillUnlocks, int, str]] = []  # (skill, current_rank, next_unlock)
    for fid, skill in catalog.items():
        cur = player_ranks.get(fid, 0)
        if cur >= MAX_RANK:
            continue
        if owned_only and cur == 0:
            continue
        if not skill.has_curated and not show_uncurated:
            continue
        if tree_filter and skill.tree.lower() != tree_filter.lower():
            continue
        next_rank = cur + 1
        next_unlock = skill.unlocks[next_rank - 1] if next_rank <= MAX_RANK else ""
        suggestions.append((skill, cur, next_unlock))

    if not suggestions:
        return ("Nenhuma sugestão (filtro vazio ou todas as skills atingiram "
                "rank 4 nas curadas).")

    n_curated = sum(1 for s in catalog.values() if s.has_curated)
    n_total = len(catalog)
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("SUGESTÕES DE SKILL — próximo rank")
    head = f"{n_curated}/{n_total} skills com unlocks curados"
    if tree_filter:
        head += f" • árvore: {tree_filter}"
    if owned_only:
        head += " • só skills já investidas"
    lines.append(head)
    lines.append("=" * 72)
    lines.append("")

    # Agrupar por tree e dentro de cada tree, ordenar por:
    #   primeiro skills com cur > 0 (em ordem de cur desc — quase no topo);
    #   depois skills com cur == 0.
    by_tree: dict[str, list[tuple[SkillUnlocks, int, str]]] = defaultdict(list)
    for triple in suggestions:
        by_tree[triple[0].tree].append(triple)

    tree_order = ["Combat", "Physical", "Science", "Social", "Tech", "?"]
    for tree in tree_order:
        items = by_tree.get(tree)
        if not items:
            continue
        items.sort(key=lambda t: (t[1] == 0, -t[1], t[0].name))
        owned = [t for t in items if t[1] > 0]
        unowned = [t for t in items if t[1] == 0]

        lines.append(f"── {tree.upper()} ({len(items)}) ──")

        if owned:
            lines.append(f"  ▸ já investidas ({len(owned)}) — próximo rank:")
            for skill, cur, nxt_unlock in owned:
                stars = "★" * cur + "☆" * (MAX_RANK - cur)
                head_line = f"    {stars}  {skill.name}  (rank {cur} → {cur+1})"
                lines.append(head_line)
                if nxt_unlock:
                    wrapped = textwrap.fill(
                        nxt_unlock, width=72,
                        initial_indent="        desbloqueia: ",
                        subsequent_indent="                     ",
                    )
                    lines.append(wrapped)
            lines.append("")

        if unowned and not owned_only:
            lines.append(f"  ▸ não investidas ({len(unowned)}) — primeiro rank:")
            for skill, cur, nxt_unlock in unowned:
                head_line = f"    ☆☆☆☆  {skill.name}"
                lines.append(head_line)
                if nxt_unlock:
                    wrapped = textwrap.fill(
                        nxt_unlock, width=72,
                        initial_indent="        rank 1: ",
                        subsequent_indent="                ",
                    )
                    lines.append(wrapped)
            lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("parsed", type=Path, help="JSON gerado por sfasst.parse_log")
    ap.add_argument("--tree", type=str, default=None,
                    help="filtra árvore (Combat/Physical/Science/Social/Tech)")
    ap.add_argument("--owned-only", action="store_true",
                    help="só skills já com rank > 0")
    ap.add_argument("--show-uncurated", action="store_true",
                    help="incluir skills sem unlock curado (linha sem texto)")
    args = ap.parse_args(argv)

    if not args.parsed.exists():
        print(f"erro: parsed.json não encontrado: {args.parsed}", file=sys.stderr)
        return 2

    data = json.loads(args.parsed.read_text(encoding="utf-8"))
    print(render(data, tree_filter=args.tree,
                 owned_only=args.owned_only,
                 show_uncurated=args.show_uncurated))
    return 0


if __name__ == "__main__":
    sys.exit(main())
