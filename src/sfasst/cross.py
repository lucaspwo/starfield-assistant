"""Cruza objetivos de quest ativos com o inventário, classifica por tipo e
pontua o esforço pra responder "que quest dá pra fechar mais rápido?".

Trabalha em cima do JSON produzido por sfasst.parse_log.

Uso:
    python -m sfasst.cross <parsed.json> [--player-level N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
import unicodedata
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from sfasst.community_tips import find_tip

# ──────────────────────────────────────────────────────────────────────
# Classificação de objetivos (heurística sobre o texto PT-BR)
# ──────────────────────────────────────────────────────────────────────


class Cls(str, Enum):
    GATHER = "gather"          # Obtenha X (Y/Z) | Colete X (Y/Z)
    SURVEY_PCT = "survey_pct"  # Conclua a inspeção (X%)
    LOCATE = "locate"          # Localize um planeta com X
    TALK = "talk"              # Fale com X
    TRAVEL = "travel"          # Vá até X | Visite X | Viaje | Pouse | Siga para
    INVESTIGATE = "invest"     # Investigue | Encontre | Junte-se
    APPLY = "apply"            # Candidate-se | Compareça
    DELIVER = "deliver"        # Entregue
    OFFER = "offer"            # Ofereça
    META = "meta"              # Conclua "<outra quest>"
    UNKNOWN = "unknown"


# Padrões aplicados em ordem; o primeiro que casar define a classe.
RE_GATHER = re.compile(
    r"^(?:Obtenha|Colete)\s+(.+?)(?:\s+para .+?)?\s+\((\d+)/(\d+)\)$",
    re.IGNORECASE,
)
RE_SURVEY = re.compile(r"^(?:Conclua a inspeção|Conclua a pesquisa)\s+\((\d+)%\)$",
                       re.IGNORECASE)
RE_LOCATE = re.compile(r"^Localize\b", re.IGNORECASE)
RE_TALK = re.compile(r"^(?:Fale com|Pergunte|Converse com|Diga)\b", re.IGNORECASE)
RE_TRAVEL = re.compile(
    r"^(?:Vá até|Vá para|Viaje (?:para|até)|Pouse|Visite|Siga para)\b",
    re.IGNORECASE,
)
RE_INVEST = re.compile(r"^(?:Investigue|Encontre|Junte-se|Pesquise)\b",
                       re.IGNORECASE)
RE_APPLY = re.compile(r"^(?:Candidate-se|Compareça)\b", re.IGNORECASE)
RE_DELIVER = re.compile(r"^Entregue\b", re.IGNORECASE)
RE_OFFER = re.compile(r"^Ofere[çc]a\b", re.IGNORECASE)
# Conclua "Foo" / Conclua "Foo" — aspas curvas ou retas
RE_META = re.compile(r"^Conclua [\"“”](.+)[\"“”]$", re.IGNORECASE)

RE_LEVEL_REC = re.compile(r"N[ií]vel recomendado:\s*(\d+)\+?", re.IGNORECASE)
RE_OPTIONAL = re.compile(r"^\(Opc\.\)\s*", re.IGNORECASE)


@dataclass
class ParsedObjective:
    raw: str
    cls: str  # Cls.value
    optional: bool = False
    item_name: str | None = None      # gather: nome do item
    have: int | None = None            # gather: quantidade já coletada (do objetivo)
    needed: int | None = None
    percent: int | None = None         # survey
    level_required: int | None = None
    meta_quest: str | None = None      # quest que precisa concluir antes


def classify(desc: str) -> ParsedObjective:
    optional = False
    m = RE_OPTIONAL.match(desc)
    if m:
        optional = True
        desc_eff = desc[m.end():]
    else:
        desc_eff = desc

    # nível recomendado pode aparecer em qualquer classe
    level_req: int | None = None
    m_lvl = RE_LEVEL_REC.search(desc_eff)
    if m_lvl:
        level_req = int(m_lvl.group(1))
        # remove pra simplificar matching seguinte
        desc_eff = RE_LEVEL_REC.sub("", desc_eff).strip().rstrip(" ()")

    if m := RE_GATHER.match(desc_eff):
        return ParsedObjective(
            raw=desc, cls=Cls.GATHER.value, optional=optional,
            item_name=m.group(1).strip(), have=int(m.group(2)),
            needed=int(m.group(3)), level_required=level_req,
        )
    if m := RE_SURVEY.match(desc_eff):
        return ParsedObjective(
            raw=desc, cls=Cls.SURVEY_PCT.value, optional=optional,
            percent=int(m.group(1)), level_required=level_req,
        )
    if m := RE_META.match(desc_eff):
        return ParsedObjective(
            raw=desc, cls=Cls.META.value, optional=optional,
            meta_quest=m.group(1), level_required=level_req,
        )
    if RE_LOCATE.match(desc_eff):
        return ParsedObjective(raw=desc, cls=Cls.LOCATE.value,
                               optional=optional, level_required=level_req)
    if RE_TALK.match(desc_eff):
        return ParsedObjective(raw=desc, cls=Cls.TALK.value,
                               optional=optional, level_required=level_req)
    if RE_TRAVEL.match(desc_eff):
        return ParsedObjective(raw=desc, cls=Cls.TRAVEL.value,
                               optional=optional, level_required=level_req)
    if RE_INVEST.match(desc_eff):
        return ParsedObjective(raw=desc, cls=Cls.INVESTIGATE.value,
                               optional=optional, level_required=level_req)
    if RE_APPLY.match(desc_eff):
        return ParsedObjective(raw=desc, cls=Cls.APPLY.value,
                               optional=optional, level_required=level_req)
    if RE_DELIVER.match(desc_eff):
        return ParsedObjective(raw=desc, cls=Cls.DELIVER.value,
                               optional=optional, level_required=level_req)
    if RE_OFFER.match(desc_eff):
        return ParsedObjective(raw=desc, cls=Cls.OFFER.value,
                               optional=optional, level_required=level_req)

    return ParsedObjective(raw=desc, cls=Cls.UNKNOWN.value,
                           optional=optional, level_required=level_req)


# ──────────────────────────────────────────────────────────────────────
# Cruzamento com inventário
# ──────────────────────────────────────────────────────────────────────


def _norm(s: str) -> str:
    """Lowercase + remove acentos + colapsa espaços."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = s.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class InventoryMatch:
    objective_item: str
    needed: int
    have_in_objective: int
    inventory_count: int          # soma do que temos no inventário do jogador
    inventory_entries: list[dict] = field(default_factory=list)
    # campos computados (preenchidos em __post_init__ pra sobreviverem ao asdict)
    shortfall: int = 0
    can_complete_now: bool = False

    def __post_init__(self) -> None:
        self.shortfall = max(
            0, self.needed - self.have_in_objective - self.inventory_count
        )
        self.can_complete_now = self.shortfall == 0


def match_inventory(item_name: str, inventory: list[dict]) -> tuple[int, list[dict]]:
    """Retorna (count, entries) do inventário cujo nome contém o item buscado."""
    target = _norm(item_name)
    if not target:
        return 0, []
    matches = [
        i for i in inventory
        if target in _norm(i["name"])
    ]
    return sum(i["count"] for i in matches), matches


# ──────────────────────────────────────────────────────────────────────
# Pontuação de esforço por objetivo / quest
# ──────────────────────────────────────────────────────────────────────

# pontos = "passos restantes" estimados (menor = mais rápido)
COST_BY_CLASS: dict[str, float] = {
    Cls.TALK.value: 1,
    Cls.OFFER.value: 1,
    Cls.APPLY.value: 1,
    Cls.DELIVER.value: 1,
    Cls.TRAVEL.value: 2,
    Cls.LOCATE.value: 4,        # achar um planeta exige scan
    Cls.INVESTIGATE.value: 5,   # geralmente combate / dungeon
    Cls.SURVEY_PCT.value: 3,
    Cls.META.value: 3,          # depende de outra quest
    Cls.UNKNOWN.value: 3,
}


def score_objective(po: ParsedObjective, inv_match: InventoryMatch | None) -> float:
    if po.optional:
        return 0.0
    if po.cls == Cls.GATHER.value:
        if inv_match is None:
            return float(po.needed or 1)
        return float(inv_match.shortfall) if inv_match.shortfall > 0 else 0.5
    return COST_BY_CLASS.get(po.cls, 3)


# ──────────────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────────────


@dataclass
class QuestAnalysis:
    display_name: str
    instance: int
    objectives: list[dict]              # [{parsed: ..., inv: ... | None, cost: ...}]
    total_cost: float
    has_level_gate: bool
    level_required: int | None          # max gate entre objetivos
    can_finish_now: bool                 # todas needs satisfeitas, só falta entregar
    bucket: str                          # "ready" | "almost" | "in_progress" | "stuck" | "level_gated"
    location: str = "?"                  # hint de local/cidade ("Neon", "Akila", ...)
    community_tip: str | None = None     # dica curada (não derivada do save)


# Heurística de localização baseada em substring de display_name + objetivos.
# Ordem importa: matchers mais específicos primeiro.
LOCATION_KEYWORDS: list[tuple[str, str]] = [
    ("ryujin", "Neon (Ryujin)"),
    ("xenofresh", "Neon (Xenofresh)"),
    ("neonz", "Neon"),
    ("neon_", "Neon"),
    ("neon", "Neon"),
    ("ffnewatlantis", "Nova Atlântida"),
    ("nova atlântida", "Nova Atlântida"),
    ("new atlantis", "Nova Atlântida"),
    ("vanguarda", "Nova Atlântida (Vanguarda)"),
    ("tuala", "Nova Atlântida (Vanguarda)"),
    ("akila", "Akila City"),
    ("ashta", "Akila City"),
    ("ngodup tate", "Akila City"),
    ("davis wilson", "Akila City"),
    ("cydonia", "Cydonia"),
    ("via rubra", "Cydonia"),
    ("gennady ayton", "Cydonia (Clínica)"),
    ("paradiso", "Paradiso"),
    ("red mile", "Red Mile"),
    ("frota escarlate", "The Key"),
    ("astroleiro", "Astroleiro Stroud-Eklund"),
    ("stroud-eklund", "Astroleiro Stroud-Eklund"),
    ("hopetown", "Hopetown"),
    ("vlad", "Casa do Vlad"),
    # quests de Constellation / Lodge
    ("vislumbres", "Constellation"),
    ("descoberta", "Constellation"),
    # quests específicas com NPCs conhecidos
    ("toft", "Nova Atlântida (UC Vanguarda)"),
    ("darvish", "Paradiso"),
    ("primeiro contato", "Paradiso (Porrima II)"),
    ("artilheiros", "Frota Escarlate (espaço)"),
    ("topo da lici", "Shattered Space (Dazra)"),
    ("kapteyn", "Sistema Kapteyn"),
    ("altair", "Sistema Altair"),
    ("procyon", "Sistema Procyon"),
    ("oráculo", "Estação Oráculo"),
    ("nirvana", "Sistema Nirvana"),
    ("suvorov", "Suvorov"),
    ("freya", "Sistema Freya"),
]


def infer_location(display_name: str, objective_descs: list[str]) -> str:
    haystack = (display_name + " " + " ".join(objective_descs)).lower()
    for keyword, label in LOCATION_KEYWORDS:
        if keyword in haystack:
            return label
    return "?"


# Heurística sobre o editor_id da quest (mais confiável que o display_name)
# pra resolver "Indicador Adicional" e quests genéricas via target ref_name.
EDITOR_ID_KEYWORDS: list[tuple[str, str]] = [
    ("ffneon", "Neon"),
    ("city_neon", "Neon"),
    ("ffcydonia", "Cydonia"),
    ("city_cy", "Cydonia"),
    ("ffparadiso", "Paradiso"),
    ("ffakila", "Akila City"),
    ("city_akila", "Akila City"),
    ("city_na", "Nova Atlântida"),
    ("ffnewatlantis", "Nova Atlântida"),
    ("uc01_tuala", "Nova Atlântida (Vanguarda)"),
    ("ffnewhomestead", "New Homestead"),
    ("ffhopetown", "Hopetown"),
    ("cf01", "The Key"),
    ("cf02", "The Key"),
    ("cf03", "The Key"),
    ("cf06", "The Key"),
    ("cfsd", "Frota Escarlate (campo)"),
    ("ffkey", "The Key"),
    ("fc05", "Akila City (Rangers)"),
    ("ms02", "Akila City"),
    ("ri01", "Red Mile"),
    ("sfter", "Cidade Esquecida"),
    ("sfbgs001", "Va'ruun (Shattered Space)"),
    ("mqmisc", "Constellation (Lodge)"),
    ("ms05", "Constellation (Lodge)"),
    ("mb_survey", "Surveys de planeta"),
]


def infer_location_from_editor_id(editor_id: str) -> str | None:
    eid = editor_id.lower()
    for keyword, label in EDITOR_ID_KEYWORDS:
        if eid.startswith(keyword) or keyword in eid:
            return label
    return None


def build_npc_to_editor_index(
    quests_targets: list[dict],
) -> dict[str, str]:
    """ref_name normalizado (sem 'REF' final) -> editor_id da quest."""
    out: dict[str, str] = {}
    for t in quests_targets:
        eid = t["editor_id"]
        for tgt in t["targets"]:
            nm = tgt.get("ref_name") or ""
            if not nm:
                continue
            # MitchBenjaminREF -> mitchbenjamin; Neon_TevinAnastasREF -> tevinanastas
            key = nm.lower()
            for suffix in ("refduplicate000", "ref"):
                if key.endswith(suffix):
                    key = key[: -len(suffix)]
            # tirar prefixo "neon_", "fc_", etc.
            for prefix in ("neon_", "fc_", "ms02_", "uc_"):
                if key.startswith(prefix):
                    key = key[len(prefix):]
            out[key] = eid
    return out


def refine_location_via_targets(
    objective_descs: list[str], npc_index: dict[str, str]
) -> str | None:
    """Acha um NPC mencionado no objetivo no índice e infere local pelo
    editor_id da quest correspondente."""
    text = " ".join(objective_descs).lower()
    # ordenar por tamanho decrescente pra evitar substring boba
    for npc_key, eid in sorted(npc_index.items(), key=lambda kv: -len(kv[0])):
        if len(npc_key) < 4:  # evita falsos positivos com siglas curtas
            continue
        # transformar "mitchbenjamin" em "mitch benjamin" pra casar texto livre
        # estratégia simples: match de cada token de pelo menos 4 chars
        if npc_key in text.replace(" ", ""):
            loc = infer_location_from_editor_id(eid)
            if loc:
                return loc
    return None


def analyze(parsed_json: dict, player_level: int | None = None) -> list[QuestAnalysis]:
    inventory = parsed_json["inventory"]
    npc_index = build_npc_to_editor_index(parsed_json.get("quests_targets", []))
    out: list[QuestAnalysis] = []

    for q in parsed_json["quests_objectives"]:
        # só nos interessam quests com objetivos DISPLAYED (no journal)
        active = [o for o in q["objectives"] if o["status"] == "DISPLAYED"]
        if not active:
            continue

        ana_objs: list[dict] = []
        total_cost = 0.0
        gates: list[int] = []
        all_gather_satisfied = True
        has_gather = False

        for o in active:
            po = classify(o["description"])
            inv_m: InventoryMatch | None = None
            if po.cls == Cls.GATHER.value and po.item_name:
                cnt, entries = match_inventory(po.item_name, inventory)
                inv_m = InventoryMatch(
                    objective_item=po.item_name,
                    needed=po.needed or 0,
                    have_in_objective=po.have or 0,
                    inventory_count=cnt,
                    inventory_entries=entries,
                )
                has_gather = True
                if not inv_m.can_complete_now:
                    all_gather_satisfied = False

            cost = score_objective(po, inv_m)
            total_cost += cost
            if po.level_required:
                gates.append(po.level_required)

            ana_objs.append({
                "parsed": asdict(po),
                "inventory_match": asdict(inv_m) if inv_m else None,
                "cost": cost,
            })

        max_gate = max(gates) if gates else None
        has_level_gate = (
            player_level is not None and max_gate is not None
            and max_gate > player_level
        )
        can_finish_now = has_gather and all_gather_satisfied and not has_level_gate

        # bucketing
        if has_level_gate:
            bucket = "level_gated"
        elif can_finish_now:
            bucket = "ready"
        elif total_cost <= 3:
            bucket = "almost"
        elif has_gather and any(
            o["inventory_match"] and o["inventory_match"]["inventory_count"] > 0
            for o in ana_objs
        ):
            bucket = "in_progress"
        elif has_gather:
            bucket = "stuck"  # precisa farmar do zero
        else:
            bucket = "in_progress"

        objective_descs = [o["parsed"]["raw"] for o in ana_objs]
        location = infer_location(q["display_name"], objective_descs)
        editor_id_hint: str | None = None
        if location == "?":
            # Busca editor_id do NPC pra refinar local E pra pesquisar dica.
            text = " ".join(objective_descs).lower()
            for npc_key, eid in sorted(
                npc_index.items(), key=lambda kv: -len(kv[0])
            ):
                if len(npc_key) >= 4 and npc_key in text.replace(" ", ""):
                    editor_id_hint = eid
                    refined = infer_location_from_editor_id(eid)
                    if refined:
                        location = refined
                    break

        # Dica da comunidade só pra quests viáveis (custo ≤ 5)
        tip: str | None = None
        if total_cost <= 5:
            tip = find_tip(q["display_name"], editor_id_hint)
        out.append(QuestAnalysis(
            display_name=q["display_name"],
            instance=q["instance"],
            objectives=ana_objs,
            total_cost=round(total_cost, 1),
            has_level_gate=has_level_gate,
            level_required=max_gate,
            can_finish_now=can_finish_now,
            bucket=bucket,
            location=location,
            community_tip=tip,
        ))

    out.sort(key=lambda a: (
        # ordem de buckets: ready primeiro, level_gated por último
        {"ready": 0, "almost": 1, "in_progress": 2, "stuck": 3, "level_gated": 4}[a.bucket],
        a.total_cost,
    ))
    return out


# ──────────────────────────────────────────────────────────────────────
# Relatório legível
# ──────────────────────────────────────────────────────────────────────


BUCKET_LABELS = {
    "ready": "PRONTO PRA ENTREGAR",
    "almost": "FALTA POUCO",
    "in_progress": "EM ANDAMENTO",
    "stuck": "SEM ESTOQUE NO CARRY",
    "level_gated": "NÍVEL INSUFICIENTE",
}


def render_report(
    analyses: list[QuestAnalysis],
    player_level: int | None,
    inventory: list[dict] | None = None,
) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("RELATÓRIO DE QUESTS ATIVAS")
    if player_level:
        lines.append(f"Nível do jogador: {player_level}")
    if inventory:
        from collections import Counter
        c = Counter(i["container"] for i in inventory)
        parts = ", ".join(f"{k} ({n})" for k, n in sorted(c.items()))
        lines.append(f"Containers dumpados: {parts}")
    lines.append("=" * 72)
    lines.append("")
    lines.append(
        "Aviso: cargo da nave e containers de outposts ainda não são dumpados."
    )
    lines.append("")

    for bucket in ("ready", "almost", "in_progress", "stuck", "level_gated"):
        group = [a for a in analyses if a.bucket == bucket]
        if not group:
            continue
        lines.append(f"── {BUCKET_LABELS[bucket]} ({len(group)}) ──")

        # subagrupar por localização para favorecer rotas eficientes
        by_loc: dict[str, list[QuestAnalysis]] = {}
        for a in group:
            by_loc.setdefault(a.location, []).append(a)
        # locais conhecidos antes do "?"; dentro de cada local, custo crescente
        sorted_locs = sorted(
            by_loc.keys(),
            key=lambda x: (x == "?", x.lower()),
        )

        for loc in sorted_locs:
            quests_here = sorted(by_loc[loc], key=lambda a: a.total_cost)
            label = loc if loc != "?" else "Local não identificado"
            lines.append(f"  ▸ {label} ({len(quests_here)})")
            for a in quests_here:
                head = f"    • {a.display_name}  [esforço: {a.total_cost}]"
                if a.has_level_gate:
                    head += f"  (precisa nível {a.level_required})"
                lines.append(head)
                if a.community_tip:
                    wrapped = textwrap.fill(
                        a.community_tip, width=72,
                        initial_indent="        ↳ dica: ",
                        subsequent_indent="                ",
                    )
                    lines.append(wrapped)
                for o in a.objectives:
                    p = o["parsed"]
                    im = o["inventory_match"]
                    tag = f"[{p['cls']}]"
                    if p["optional"]:
                        tag = "[opc] " + tag
                    line = f"        - {tag} {p['raw']}"
                    if im:
                        by_container: dict[str, int] = {}
                        for e in im["inventory_entries"]:
                            by_container[e["container"]] = (
                                by_container.get(e["container"], 0) + e["count"]
                            )
                        parts = ", ".join(
                            f"{c}: {n}" for c, n in sorted(by_container.items())
                        ) or "—"
                        line += (
                            f"  → tenho [{parts}], total {im['inventory_count']}"
                            f", falta {im['shortfall']}"
                        )
                    lines.append(line)
            lines.append("")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────


SAVE_FILENAME_LEVEL_RE = re.compile(r"_(\d+)_\d+_\d+\.sfs$", re.IGNORECASE)


def player_level_from_save(savepath: str) -> int | None:
    m = SAVE_FILENAME_LEVEL_RE.search(savepath)
    return int(m.group(1)) if m else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("parsed", type=Path, help="JSON gerado por sfasst.parse_log")
    ap.add_argument("--player-level", type=int, default=None,
                    help="nível do jogador (pra detectar quests level-gated)")
    ap.add_argument("--from-save", type=Path, default=None,
                    help="extrai o nível do nome de um arquivo .sfs")
    ap.add_argument("-j", "--json", action="store_true",
                    help="emite JSON estruturado em vez do relatório de texto")
    args = ap.parse_args(argv)

    if not args.parsed.exists():
        print(f"erro: parsed.json não encontrado: {args.parsed}", file=sys.stderr)
        return 2

    level = args.player_level
    if level is None and args.from_save:
        level = player_level_from_save(str(args.from_save))
        if level is None:
            print(f"aviso: não consegui extrair nível de {args.from_save.name}",
                  file=sys.stderr)

    parsed_json = json.loads(args.parsed.read_text(encoding="utf-8"))
    analyses = analyze(parsed_json, player_level=level)

    if args.json:
        print(json.dumps([asdict(a) for a in analyses],
                         ensure_ascii=False, indent=2))
    else:
        print(render_report(analyses, player_level=level,
                            inventory=parsed_json.get("inventory")))

    return 0


if __name__ == "__main__":
    sys.exit(main())
