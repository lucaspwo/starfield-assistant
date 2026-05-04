"""Prioriza onde investir o próximo ponto de skill, dado o que já foi gasto.

Score por skill combina:
- gate_proximity: árvore perto de cruzar 4/8/12 ranks (desbloqueia próximo tier)
- completion_bonus: rank 3 -> 4 fecha último benefício curado
- investment_continuity: rank > 0 vale mais que zerar do zero
- max-rank: skills em rank 4 saem da lista

Uso:
    python -m sfasst.skill_priorities <parsed.json>
    python -m sfasst.skill_priorities <parsed.json> --top 10
    python -m sfasst.skill_priorities <parsed.json> --tree Combat
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from sfasst.skill_suggestions import load_skills, MAX_RANK

# Gates do Starfield: skill points gastos numa árvore pra desbloquear o
# próximo tier. Confirmado por documentação (games.gg, game8):
#   "Reaching tier 2 requires spending 4 skill points in that category,
#    tier 3 requires 8, and tier 4 requires 12."
# Cada rank de uma skill custa 1 SP (rank 1 abre a skill; ranks 2/3/4
# exigem completar o challenge + gastar mais 1 SP). Logo, rank atual de
# cada skill == SPs gastos nela, e a soma dos ranks por árvore é o total
# de SPs gastos naquela árvore.
TIER_GATES = [4, 8, 12]


@dataclass
class TreeStatus:
    name: str
    total_ranks: int
    tier_unlocked: int                  # 1..4
    next_gate: int | None               # 4 / 8 / 12 / None se já em tier 4
    points_to_next_gate: int | None


def tree_status(total_ranks: int, name: str) -> TreeStatus:
    tier_unlocked = 1
    for i, gate in enumerate(TIER_GATES):
        if total_ranks >= gate:
            tier_unlocked = i + 2  # gate 4 -> tier 2 unlocked
    next_gate: int | None = None
    pts_left: int | None = None
    for gate in TIER_GATES:
        if total_ranks < gate:
            next_gate = gate
            pts_left = gate - total_ranks
            break
    return TreeStatus(
        name=name, total_ranks=total_ranks,
        tier_unlocked=tier_unlocked,
        next_gate=next_gate,
        points_to_next_gate=pts_left,
    )


@dataclass
class Recommendation:
    name: str
    tree: str
    current_rank: int
    next_rank_unlock: str
    score: float
    reasons: list[str] = field(default_factory=list)


def score_skill(
    skill_name: str,
    tree: str,
    current_rank: int,
    next_unlock_text: str,
    ts: TreeStatus,
) -> Recommendation | None:
    if current_rank >= MAX_RANK:
        return None
    score = 0.0
    reasons: list[str] = []

    # 1. Gate proximity — qualquer skill da árvore conta pra cruzar gate
    if ts.points_to_next_gate is not None and ts.points_to_next_gate <= 2:
        bonus = 10.0 * (3 - ts.points_to_next_gate)  # 1 pt: +20, 2 pts: +10
        score += bonus
        next_tier = ts.tier_unlocked + 1
        reasons.append(
            f"a {ts.points_to_next_gate} ponto(s) de abrir Tier {next_tier} {tree}"
        )

    # 2. Completion bonus — fechar rank 3 -> 4
    if current_rank == 3:
        score += 8.0
        reasons.append("último rank: fecha benefício max")

    # 3. Investment continuity — já investido
    if current_rank > 0:
        score += 3.0 + current_rank
        reasons.append(f"continua investimento (rank {current_rank} → {current_rank+1})")
    else:
        reasons.append("primeira investida")

    return Recommendation(
        name=skill_name, tree=tree,
        current_rank=current_rank,
        next_rank_unlock=next_unlock_text,
        score=score,
        reasons=reasons,
    )


def render(
    parsed: dict,
    top: int = 10,
    tree_filter: str | None = None,
) -> str:
    catalog = load_skills()
    if not catalog:
        return "erro: data/skills.tsv não encontrado ou vazio."

    player_ranks: dict[str, int] = {}
    for s in parsed.get("skills", []):
        player_ranks[s["form_id"].upper()] = s["rank"]

    # Total de ranks por árvore
    tree_totals: dict[str, int] = defaultdict(int)
    for fid, skill in catalog.items():
        tree_totals[skill.tree] += player_ranks.get(fid, 0)
    statuses: dict[str, TreeStatus] = {
        tree: tree_status(total, tree) for tree, total in tree_totals.items()
    }

    # Score de cada skill candidata
    recs: list[Recommendation] = []
    for fid, skill in catalog.items():
        if tree_filter and skill.tree.lower() != tree_filter.lower():
            continue
        cur = player_ranks.get(fid, 0)
        next_rank = cur + 1
        next_unlock = (
            skill.unlocks[next_rank - 1] if next_rank <= MAX_RANK else ""
        )
        ts = statuses.get(skill.tree)
        if ts is None:
            continue
        r = score_skill(
            skill.name, skill.tree, cur, next_unlock, ts
        )
        if r:
            recs.append(r)

    # Ordenar: score desc, rank atual desc (continua o que já tá quente)
    recs.sort(key=lambda r: (-r.score, -r.current_rank, r.name))
    chosen = recs[:top]

    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("PRIORIDADE DE INVESTIMENTO DE SKILL")
    if tree_filter:
        lines.append(f"Filtro: árvore {tree_filter}")
    lines.append("=" * 72)
    lines.append("")

    # Painel de gates por árvore
    lines.append("Status das árvores:")
    for tree in ("Combat", "Physical", "Science", "Social", "Tech"):
        ts = statuses.get(tree)
        if ts is None:
            continue
        if ts.next_gate is None:
            line = f"  {tree:<10}  {ts.total_ranks:>2} ranks  •  Tier 4 desbloqueado"
        else:
            line = (
                f"  {tree:<10}  {ts.total_ranks:>2} ranks  •  "
                f"Tier {ts.tier_unlocked} ativo  •  "
                f"faltam {ts.points_to_next_gate} pra Tier {ts.tier_unlocked+1}"
            )
        lines.append(line)
    lines.append("")

    if not chosen:
        lines.append("Nenhuma skill candidata.")
        return "\n".join(lines)

    lines.append(f"Top {len(chosen)} próximos pontos:")
    lines.append("")
    for i, r in enumerate(chosen, 1):
        head = (
            f"{i:>2}. {r.name}  [{r.tree}]  "
            f"(rank {r.current_rank} → {r.current_rank+1})  "
            f"score {r.score:.1f}"
        )
        lines.append(head)
        for reason in r.reasons:
            lines.append(f"      • {reason}")
        if r.next_rank_unlock:
            wrapped = textwrap.fill(
                r.next_rank_unlock, width=72,
                initial_indent="      desbloqueia: ",
                subsequent_indent="                   ",
            )
            lines.append(wrapped)
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("parsed", type=Path, help="JSON gerado por sfasst.parse_log")
    ap.add_argument("--top", type=int, default=10,
                    help="quantidade de skills sugeridas (default 10)")
    ap.add_argument("--tree", type=str, default=None,
                    help="filtra árvore (Combat/Physical/Science/Social/Tech)")
    args = ap.parse_args(argv)

    if not args.parsed.exists():
        print(f"erro: parsed.json não encontrado: {args.parsed}", file=sys.stderr)
        return 2

    data = json.loads(args.parsed.read_text(encoding="utf-8"))
    print(render(data, top=args.top, tree_filter=args.tree))
    return 0


if __name__ == "__main__":
    sys.exit(main())
