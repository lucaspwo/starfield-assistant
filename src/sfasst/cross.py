"""Cruza objetivos de quest ativos com o inventário, classifica por tipo e
pontua o esforço pra responder "que quest dá pra fechar mais rápido?".

Trabalha em cima do JSON produzido por sfasst.parse_log.

Uso:
    python -m sfasst.cross <parsed.json> [--player-level N]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import textwrap
import unicodedata
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from sfasst.community_tips import find_tip

# ──────────────────────────────────────────────────────────────────────
# Proximidade geográfica (sistema → sistema, em anos-luz)
# ──────────────────────────────────────────────────────────────────────

from sfasst._paths import data_path

SYSTEMS_TSV = data_path("systems.tsv")
LOCATIONS_TSV = data_path("locations.tsv")


def _load_systems() -> dict[str, tuple[float, float, float]]:
    """starfield_system (UPPER) -> (x, y, z) em anos-luz."""
    out: dict[str, tuple[float, float, float]] = {}
    if not SYSTEMS_TSV.exists():
        return out
    for raw in SYSTEMS_TSV.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.startswith("starfield_system"):
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        try:
            out[parts[0].strip().upper()] = (
                float(parts[1]), float(parts[2]), float(parts[3])
            )
        except ValueError:
            continue
    return out


def _load_label_to_system() -> dict[str, str]:
    """label (lower) -> starfield_system (upper). '' = sistema desconhecido."""
    out: dict[str, str] = {}
    if not LOCATIONS_TSV.exists():
        return out
    for raw in LOCATIONS_TSV.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.startswith("label"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        label = parts[0].strip()
        sys_name = parts[1].strip().upper() if len(parts) >= 2 else ""
        out[label.lower()] = sys_name
    return out


# Tier de proximidade entre dois labels.
# 0 = mesma label  •  1 = mesmo sistema  •  2 = perto (~1 jump)
# 3 = intermediário (alguns jumps)  •  4 = longe  •  5 = sistema desconhecido
#
# As distâncias vêm de data/external/system_data.txt (s9w/starfield-navigator):
# coords reconstruídas por skybox tracking, NÃO são anos-luz reais
# (ex.: Sol→Alpha Centauri sai 42, não 4.37 ly). São consistentes entre si
# então servem como proxy de "quão grande precisa ser o grav jump".
PROX_NEAR_THRESHOLD = 60.0   # navigator units
PROX_MID_THRESHOLD = 150.0
def proximity_tier(
    here_label: str, quest_label: str,
    label_to_system: dict[str, str],
    systems_xyz: dict[str, tuple[float, float, float]],
) -> tuple[int, float | None]:
    """Retorna (tier, distance_ly_or_None)."""
    if not here_label or not quest_label:
        return (5, None)
    if quest_label == "?":
        return (5, None)
    a = _norm(here_label)
    b = _norm(quest_label)
    # AQUI = labels coincidem ou uma é substring da outra (cobre
    # 'Cydonia (Clínica)' quando here='cydonia')
    if a == b or (a and b and (a in b or b in a)):
        return (0, 0.0)

    here_sys = label_to_system.get(here_label.lower(), "")
    quest_sys = label_to_system.get(quest_label.lower(), "")
    if not here_sys or not quest_sys:
        return (5, None)
    if here_sys == quest_sys:
        return (1, 0.0)
    a = systems_xyz.get(here_sys)
    b = systems_xyz.get(quest_sys)
    if not a or not b:
        return (5, None)
    d = math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)
    if d <= PROX_NEAR_THRESHOLD:
        return (2, d)
    if d <= PROX_MID_THRESHOLD:
        return (3, d)
    return (4, d)


PROXIMITY_LABELS = {
    0: "AQUI",
    1: "MESMO SISTEMA",
    2: "PERTO",
    3: "INTERMEDIÁRIO",
    4: "LONGE",
    5: "DESCONHECIDO",
}

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
        # IMPORTANTE: o counter da quest (have_in_objective) já reflete o que
        # está no inventário do jogador — somar duplicaria. Usar o maior dos
        # dois é defensivo: cobre o caso de o counter estar stale e o caso
        # comum em que ambos coincidem.
        progress = max(self.have_in_objective, self.inventory_count)
        self.shortfall = max(0, self.needed - progress)
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
    at_here: bool = False                # location bate com --here (declarado pelo usuário)
    proximity_tier: int = 5              # 0=aqui, 1=mesmo sistema, 2=≤10ly, 3=≤30ly, 4=>30ly, 5=desconhecido
    distance_ly: float | None = None     # None se desconhecido ou mesma label


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


def _merge_quest_blocks(quests_objectives: list[dict]) -> list[dict]:
    """Junta múltiplos blocos `== Display ==` da mesma quest (mesmo display_name
    + instance) num único registro. O jogo emite um bloco por objetivo em
    quests com várias linhas de gather (ex.: 'Primeiro Contato' tem 4 blocos,
    um por material). Sem o merge, cada bloco é tratado como quest separada e
    pode parecer 'pronta' mesmo com objetivos pendentes em outro bloco."""
    merged: dict[tuple[str, int], dict] = {}
    order: list[tuple[str, int]] = []
    for q in quests_objectives:
        key = (q["display_name"], q["instance"])
        if key not in merged:
            merged[key] = {
                "display_name": q["display_name"],
                "instance": q["instance"],
                "objectives": list(q["objectives"]),
            }
            order.append(key)
        else:
            merged[key]["objectives"].extend(q["objectives"])
    return [merged[k] for k in order]


def _here_matches(location: str, here: str) -> bool:
    """Match case-insensitive entre o local declarado pelo usuário e o
    location inferido da quest. Substring acentuado-insensível em ambos os
    sentidos para casar 'cydonia' com 'Cydonia (Clínica)' e vice-versa."""
    a = _norm(here)
    b = _norm(location)
    if not a or not b or b == "?":
        return False
    return a in b or b in a


def analyze(
    parsed_json: dict,
    player_level: int | None = None,
    here: str | None = None,
) -> list[QuestAnalysis]:
    inventory = parsed_json["inventory"]
    npc_index = build_npc_to_editor_index(parsed_json.get("quests_targets", []))
    systems_xyz = _load_systems()
    label_to_system = _load_label_to_system()
    out: list[QuestAnalysis] = []

    for q in _merge_quest_blocks(parsed_json["quests_objectives"]):
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
        at_here = bool(here) and _here_matches(location, here)
        if here:
            ptier, pdist = proximity_tier(
                here, location, label_to_system, systems_xyz
            )
        else:
            ptier, pdist = 5, None
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
            at_here=at_here,
            proximity_tier=ptier,
            distance_ly=round(pdist, 1) if pdist is not None else None,
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


def render_route(analyses: list[QuestAnalysis], top: int) -> list[str]:
    """Top N quests acionáveis ordenadas por score combinado de
    proximidade × esforço. Cada tier de proximidade adiciona ~5 ao score
    (1 grav jump ≈ 1 farm leve), de modo que esforço 3 fora bate esforço
    21 em casa."""
    PROX_WEIGHT = 5.0

    def score(a: QuestAnalysis) -> float:
        return a.total_cost + PROX_WEIGHT * a.proximity_tier

    actionable = [
        a for a in analyses
        if a.bucket in ("ready", "almost", "in_progress")
        and a.proximity_tier <= 4
    ]
    actionable.sort(key=lambda a: (score(a), a.proximity_tier, a.total_cost))
    chosen = actionable[:top]
    if not chosen:
        return []
    lines: list[str] = []
    lines.append(f"── ROTA RÁPIDA (top {len(chosen)}, mais fáceis e próximas) ──")
    for a in chosen:
        prox = PROXIMITY_LABELS.get(a.proximity_tier, "?")
        if a.distance_ly is not None and a.proximity_tier in (2, 3, 4):
            # 'u' = unidades do navigator (não são ly reais — proxy de jump)
            prox = f"{prox} (~{a.distance_ly:.0f}u)"
        loc = a.location if a.location != "?" else "Local não identificado"
        lines.append(
            f"  • [{prox}]  {a.display_name}  "
            f"[esforço: {a.total_cost}]  — {loc}"
        )
    lines.append("")
    return lines


def render_report(
    analyses: list[QuestAnalysis],
    player_level: int | None,
    inventory: list[dict] | None = None,
    here: str | None = None,
    location_context: dict | None = None,
    top: int = 5,
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
    if location_context:
        ctx_parts: list[str] = []
        pos = location_context.get("pos") or {}
        if pos:
            ctx_parts.append(
                "coords ({}, {}, {})".format(
                    *(f"{pos.get(ax, '?'):.0f}" if isinstance(pos.get(ax), (int, float))
                      else "?" for ax in ("X", "Y", "Z"))
                )
            )
        is_int = location_context.get("is_interior")
        if is_int is not None:
            ctx_parts.append("interior" if is_int else "exterior")
        is_sp = location_context.get("is_in_space")
        if is_sp is not None:
            ctx_parts.append("no espaço" if is_sp else "em planeta/estação")
        if ctx_parts:
            lines.append("Contexto: " + " • ".join(ctx_parts))
    if here:
        n_here = sum(1 for a in analyses if a.at_here)
        lines.append(f"Local declarado: {here}  ({n_here} quest(s) batem)")
    lines.append("=" * 72)
    lines.append("")
    lines.append(
        "Aviso: cargo da nave e containers de outposts ainda não são dumpados."
    )
    lines.append("")

    if here:
        lines.extend(render_route(analyses, top))

    for bucket in ("ready", "almost", "in_progress", "stuck", "level_gated"):
        group = [a for a in analyses if a.bucket == bucket]
        if not group:
            continue
        lines.append(f"── {BUCKET_LABELS[bucket]} ({len(group)}) ──")

        # subagrupar por localização para favorecer rotas eficientes
        by_loc: dict[str, list[QuestAnalysis]] = {}
        for a in group:
            by_loc.setdefault(a.location, []).append(a)
        # local atual declarado primeiro; locais conhecidos antes do "?";
        # dentro de cada local, custo crescente
        def _loc_key(loc: str) -> tuple:
            has_here = any(a.at_here for a in by_loc[loc])
            return (not has_here, loc == "?", loc.lower())
        sorted_locs = sorted(by_loc.keys(), key=_loc_key)

        for loc in sorted_locs:
            quests_here = sorted(by_loc[loc], key=lambda a: a.total_cost)
            label = loc if loc != "?" else "Local não identificado"
            badge = "  [AQUI AGORA]" if any(a.at_here for a in quests_here) else ""
            lines.append(f"  ▸ {label} ({len(quests_here)}){badge}")
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
    ap.add_argument("--here", type=str, default=None,
                    help="local atual do jogador (ex.: 'cydonia', 'neon'); "
                         "quests cujo local infere igual ganham badge "
                         "[AQUI AGORA] e vão pro topo do bucket; também "
                         "habilita a seção 'ROTA RÁPIDA' por proximidade.")
    ap.add_argument("--top", type=int, default=5,
                    help="quantidade de quests na seção ROTA RÁPIDA (default 5)")
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
    analyses = analyze(parsed_json, player_level=level, here=args.here)

    location_context = {
        "pos": parsed_json.get("player_pos") or {},
        "is_interior": parsed_json.get("player_is_interior"),
        "is_in_space": parsed_json.get("player_is_in_space"),
    }

    if args.json:
        print(json.dumps([asdict(a) for a in analyses],
                         ensure_ascii=False, indent=2))
    else:
        print(render_report(analyses, player_level=level,
                            inventory=parsed_json.get("inventory"),
                            here=args.here,
                            location_context=location_context,
                            top=args.top))

    return 0


if __name__ == "__main__":
    sys.exit(main())
