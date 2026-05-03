"""Sugere projetos de pesquisa a partir de um TSV curado, marcando quais
são acessíveis dado o rank atual de skills do jogador (lido do parsed.json).

Uso:
    python -m sfasst.research_suggestions <parsed.json>
    python -m sfasst.research_suggestions <parsed.json> --accessible-only
    python -m sfasst.research_suggestions <parsed.json> --category Weaponry
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

RESEARCH_TSV = data_path("research.tsv")


@dataclass
class ResearchProject:
    category: str
    project: str
    tier: int
    prereq_skills: list[tuple[str, int]] = field(default_factory=list)
    unlocks: str = ""

    @property
    def label(self) -> str:
        return f"{self.project} [T{self.tier}]"


def _parse_prereq(s: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for part in s.split("|"):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            name, rank = part.rsplit(":", 1)
            try:
                out.append((name.strip(), int(rank.strip())))
            except ValueError:
                continue
    return out


def load_projects(tsv: Path = RESEARCH_TSV) -> list[ResearchProject]:
    if not tsv.exists():
        return []
    out: list[ResearchProject] = []
    for raw in tsv.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\r\n")
        if not line.strip() or line.startswith("category"):
            continue
        cols = line.split("\t")
        if len(cols) < 5:
            continue
        category, project, tier, prereqs, unlocks = cols[:5]
        try:
            tier_n = int(tier)
        except ValueError:
            tier_n = 0
        out.append(ResearchProject(
            category=category.strip(),
            project=project.strip(),
            tier=tier_n,
            prereq_skills=_parse_prereq(prereqs),
            unlocks=unlocks.strip(),
        ))
    return out


def player_skill_ranks(parsed: dict) -> dict[str, int]:
    return {s["name"]: s["rank"] for s in parsed.get("skills", [])}


def evaluate(
    project: ResearchProject, ranks: dict[str, int]
) -> tuple[bool, list[str]]:
    """Retorna (acessivel, faltas). 'faltas' é lista 'Skill: tem/precisa'."""
    missing: list[str] = []
    for name, req in project.prereq_skills:
        have = ranks.get(name, 0)
        if have < req:
            missing.append(f"{name} {have}/{req}")
    return (not missing, missing)


def render(
    parsed: dict,
    accessible_only: bool = False,
    category_filter: str | None = None,
) -> str:
    projects = load_projects()
    if not projects:
        return f"erro: {RESEARCH_TSV} não encontrado ou vazio."

    if category_filter:
        cf = category_filter.lower()
        projects = [p for p in projects if p.category.lower() == cf]
        if not projects:
            return f"Nenhum projeto na categoria '{category_filter}'."

    ranks = player_skill_ranks(parsed)

    rated: list[tuple[ResearchProject, bool, list[str]]] = []
    for p in projects:
        ok, miss = evaluate(p, ranks)
        rated.append((p, ok, miss))

    if accessible_only:
        rated = [r for r in rated if r[1]]

    n_total = len(load_projects())
    n_accessible = sum(1 for r in rated if r[1])

    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("SUGESTÕES DE PESQUISA")
    head = f"{n_total} projetos no catálogo"
    if category_filter:
        head += f" • filtro: {category_filter}"
    head += f" • {n_accessible} acessíveis agora"
    lines.append(head)
    lines.append("=" * 72)
    lines.append("")

    by_cat: dict[str, list[tuple[ResearchProject, bool, list[str]]]] = defaultdict(list)
    for triple in rated:
        by_cat[triple[0].category].append(triple)

    for cat in sorted(by_cat.keys()):
        items = by_cat[cat]
        # ordenar: acessíveis primeiro, depois por tier
        items.sort(key=lambda t: (not t[1], t[0].tier, t[0].project))
        lines.append(f"── {cat.upper()} ({len(items)}) ──")
        for proj, ok, miss in items:
            mark = "✓" if ok else "✗"
            lines.append(f"  {mark} {proj.label}")
            if proj.prereq_skills:
                req_str = ", ".join(
                    f"{name} {req}" for name, req in proj.prereq_skills
                )
                if ok:
                    lines.append(f"      requer: {req_str}")
                else:
                    lines.append(
                        f"      falta: {', '.join(miss)}  (de {req_str})"
                    )
            if proj.unlocks:
                wrapped = textwrap.fill(
                    proj.unlocks, width=72,
                    initial_indent="      desbloqueia: ",
                    subsequent_indent="                   ",
                )
                lines.append(wrapped)
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("parsed", type=Path, help="JSON gerado por sfasst.parse_log")
    ap.add_argument("--accessible-only", action="store_true",
                    help="esconde projetos cujos pré-requisitos não estão atendidos")
    ap.add_argument("--category", type=str, default=None,
                    help="filtra por categoria (ex.: Weaponry, Pharmacology)")
    args = ap.parse_args(argv)

    if not args.parsed.exists():
        print(f"erro: parsed.json não encontrado: {args.parsed}", file=sys.stderr)
        return 2

    data = json.loads(args.parsed.read_text(encoding="utf-8"))
    print(render(data, accessible_only=args.accessible_only,
                 category_filter=args.category))
    return 0


if __name__ == "__main__":
    sys.exit(main())
