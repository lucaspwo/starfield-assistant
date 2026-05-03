"""Parser do sfse_plugin_console.log gerado por `bat dump` no jogo.

Consome um log com 4 blocos (ShowQuests, ShowQuestObjectives, ShowQuestTargets,
Player.ShowInventory) e produz JSON estruturado.

Uso:
    python -m sfasst.parse_log <caminho-do-log> [--out <arquivo.json>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# Regexes — ancoradas para não casar fora do bloco esperado
# ──────────────────────────────────────────────────────────────────────

# `> ShowQuests` etc. — linha de eco do batch file, marca início de seção
RE_ECHO = re.compile(r"^> (.+)$")

# ShowQuests:        `MQ101 (Off) -- Stage 9000`
RE_QUEST_FLAG = re.compile(r"^(\S+) \((On|Off)\) -- Stage (-?\d+)$")

# ShowQuestObjectives:
#   `== Um Pequeno Passo ==`
#   `( Instance: 1 )`
#   `5 Siga a supervisora Lin COMPLETED`
RE_OBJ_HEADER = re.compile(r"^== (.+) ==$")
RE_OBJ_INSTANCE = re.compile(r"^\( Instance: (-?\d+) \)$")
RE_OBJ_LINE = re.compile(r"^(\d+) (.+) (COMPLETED|DISPLAYED|DORMANT|FAILED)$")

# ShowQuestTargets:
#   `Current quest: MQ207B`
#   `1 current targets`
#   `Target 1:  Reference: NomeRef (0023B895), Intermediate Reference:  (FF027936)`
RE_TGT_QUEST = re.compile(r"^Current quest: (\S+)$")
RE_TGT_COUNT = re.compile(r"^(\d+) current targets$")
RE_TGT_LINE = re.compile(
    r"^Target (\d+):\s+Reference:\s*(\S*)\s*\(([0-9A-Fa-f]{8})\),\s*"
    r"Intermediate Reference:\s*(\S*)\s*\(([0-9A-Fa-f]{8})\)\s*$"
)

# Player.GetLevel: `GetLevel >> 32.00`
# Player.GetXPForNextLevel: `GetXPForNextLevel >> 200.00` (algo similar)
# Player.GetPerkRank: `GetPerkRank >> 2.00`
RE_NUMERIC_RESULT = re.compile(r"^(\w+)\s*>>\s*(-?\d+(?:\.\d+)?)$")

# Player.ShowInventory:
#   `1 - Orion (002773C8) `
#   `1 - Spacesuit_MS04_Mantis_Helmet (0016640A)  - Worn`
#   `28 - FragGrenade (000115EF)  - Worn: AltAttackSlot1`
#   `1 - Estatuto Original (002E4C1A)  Quest Item`
# A "anotação" depois do FormID é opcional e pode vir com ou sem hífen.
RE_INV_LINE = re.compile(
    r"^(\d+) - (.+?) \(([0-9A-Fa-f]{8})\)"
    r"(?:\s+-?\s*(\S.*?))?\s*$"
)

OBJ_ACTIVE_STATUSES = {"DISPLAYED", "DORMANT"}


# ──────────────────────────────────────────────────────────────────────
# Modelos
# ──────────────────────────────────────────────────────────────────────


@dataclass
class QuestFlag:
    editor_id: str
    on: bool
    stage: int


@dataclass
class Objective:
    stage: int
    description: str
    status: str  # COMPLETED | DISPLAYED | DORMANT | FAILED


@dataclass
class QuestObjectives:
    display_name: str
    instance: int
    objectives: list[Objective] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return any(o.status in OBJ_ACTIVE_STATUSES for o in self.objectives)

    @property
    def displayed(self) -> bool:
        return any(o.status == "DISPLAYED" for o in self.objectives)


@dataclass
class QuestTarget:
    index: int
    ref_name: str  # "" se anônimo
    ref_id: str
    intermediate_ref_id: str


@dataclass
class QuestTargetGroup:
    editor_id: str
    targets: list[QuestTarget] = field(default_factory=list)


@dataclass
class InventoryItem:
    count: int
    name: str
    form_id: str
    annotation: str = ""  # "Worn", "Worn: RightHand", "Quest Item", ""
    container: str = "player"  # "player" | "<RefID hex>" | rótulo livre


@dataclass
class SkillRank:
    form_id: str
    name: str
    tree: str
    rank: int


@dataclass
class ParseResult:
    captured_at: str
    source_log: str
    quests_flags: list[QuestFlag]
    quests_objectives: list[QuestObjectives]
    quests_targets: list[QuestTargetGroup]
    inventory: list[InventoryItem]
    player_level: int | None = None
    player_xp_for_next_level: int | None = None
    skills: list[SkillRank] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────


def _load_skill_index() -> dict[str, tuple[str, str]]:
    """Carrega data/skills.tsv → {form_id_upper: (name, tree)}."""
    tsv = Path(__file__).resolve().parent.parent.parent / "data" / "skills.tsv"
    out: dict[str, tuple[str, str]] = {}
    if not tsv.exists():
        return out
    for raw in tsv.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("form_id"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            out[parts[0].upper()] = (parts[1], parts[2])
    return out


def parse(log_path: Path) -> ParseResult:
    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    skill_index = _load_skill_index()

    section: str | None = None  # "quests" | "objectives" | "targets" | "inventory"
    inventory_container: str = "player"  # rótulo do container atual
    pending_perk_form_id: str | None = None  # cmd era GetPerkRank <FormID>; espera resposta
    pending_numeric_kind: str | None = None  # "level" | "xp_next" | "perk"

    quests_flags: list[QuestFlag] = []
    quests_objectives: list[QuestObjectives] = []
    quests_targets: list[QuestTargetGroup] = []
    inventory: list[InventoryItem] = []
    skills: list[SkillRank] = []
    player_level: int | None = None
    player_xp_for_next_level: int | None = None

    # estado para parsing multilinha
    current_quest_obj: QuestObjectives | None = None
    pending_obj_name: str | None = None
    current_target_group: QuestTargetGroup | None = None

    def flush_quest_obj() -> None:
        nonlocal current_quest_obj
        if current_quest_obj is not None:
            quests_objectives.append(current_quest_obj)
            current_quest_obj = None

    def flush_target_group() -> None:
        nonlocal current_target_group
        if current_target_group is not None:
            quests_targets.append(current_target_group)
            current_target_group = None

    for raw in lines:
        line = raw.rstrip()

        m = RE_ECHO.match(line)
        if m:
            cmd = m.group(1).strip()
            # comentários do batch (começam com `;`) não mudam seção
            if cmd.startswith(";"):
                continue
            flush_quest_obj()
            flush_target_group()
            cmd_lower = cmd.lower()
            if cmd_lower.startswith("showquests") and "objective" not in cmd_lower:
                section = "quests"
            elif cmd_lower.startswith("showquestobjectives"):
                section = "objectives"
            elif cmd_lower.startswith("showquesttargets"):
                section = "targets"
            elif cmd_lower.endswith("showinventory") or cmd_lower.endswith(
                ".showinventory"
            ):
                section = "inventory"
                # rótulo do container = prefixo antes do "." (ou "player" se vazio)
                if "." in cmd:
                    prefix = cmd.split(".", 1)[0].strip()
                    inventory_container = prefix or "player"
                else:
                    inventory_container = "player"
            elif "getlevel" in cmd_lower:
                section = "numeric"
                pending_numeric_kind = "level"
            elif "getxpfornextlevel" in cmd_lower:
                section = "numeric"
                pending_numeric_kind = "xp_next"
            elif "getperkrank" in cmd_lower:
                section = "numeric"
                pending_numeric_kind = "perk"
                # extrair o FormID do comando: "Player.GetPerkRank 002C2C5A"
                tokens = cmd.split()
                pending_perk_form_id = tokens[-1].upper() if tokens else None
            else:
                section = None
            continue

        if not line.strip():
            # linha em branco fecha bloco corrente em objetivos/targets
            flush_quest_obj()
            continue

        if section == "quests":
            m = RE_QUEST_FLAG.match(line)
            if m:
                quests_flags.append(
                    QuestFlag(
                        editor_id=m.group(1),
                        on=m.group(2) == "On",
                        stage=int(m.group(3)),
                    )
                )
            continue

        if section == "objectives":
            m = RE_OBJ_HEADER.match(line)
            if m:
                flush_quest_obj()
                pending_obj_name = m.group(1).strip()
                continue
            m = RE_OBJ_INSTANCE.match(line)
            if m and pending_obj_name is not None:
                current_quest_obj = QuestObjectives(
                    display_name=pending_obj_name, instance=int(m.group(1))
                )
                pending_obj_name = None
                continue
            m = RE_OBJ_LINE.match(line)
            if m and current_quest_obj is not None:
                current_quest_obj.objectives.append(
                    Objective(
                        stage=int(m.group(1)),
                        description=m.group(2).strip(),
                        status=m.group(3),
                    )
                )
            continue

        if section == "targets":
            m = RE_TGT_QUEST.match(line)
            if m:
                flush_target_group()
                current_target_group = QuestTargetGroup(editor_id=m.group(1))
                continue
            m = RE_TGT_COUNT.match(line)
            if m:
                continue  # contagem é redundante; conferimos ao final
            m = RE_TGT_LINE.match(line)
            if m and current_target_group is not None:
                current_target_group.targets.append(
                    QuestTarget(
                        index=int(m.group(1)),
                        ref_name=m.group(2) or "",
                        ref_id=m.group(3).upper(),
                        intermediate_ref_id=m.group(5).upper(),
                    )
                )
            continue

        if section == "inventory":
            m = RE_INV_LINE.match(line)
            if m:
                inventory.append(
                    InventoryItem(
                        count=int(m.group(1)),
                        name=m.group(2).strip(),
                        form_id=m.group(3).upper(),
                        annotation=(m.group(4) or "").strip(),
                        container=inventory_container,
                    )
                )
            continue

        if section == "numeric":
            m = RE_NUMERIC_RESULT.match(line)
            if m:
                value = int(float(m.group(2)))
                if pending_numeric_kind == "level":
                    player_level = value
                elif pending_numeric_kind == "xp_next":
                    player_xp_for_next_level = value
                elif pending_numeric_kind == "perk" and pending_perk_form_id:
                    name, tree = skill_index.get(
                        pending_perk_form_id, (pending_perk_form_id, "?")
                    )
                    skills.append(SkillRank(
                        form_id=pending_perk_form_id,
                        name=name, tree=tree, rank=value,
                    ))
            # após receber a resposta numérica, dessa "subseção" se foi
            section = None
            pending_numeric_kind = None
            pending_perk_form_id = None
            continue

    flush_quest_obj()
    flush_target_group()

    return ParseResult(
        captured_at=datetime.now(timezone.utc).isoformat(),
        source_log=str(log_path),
        quests_flags=quests_flags,
        quests_objectives=quests_objectives,
        quests_targets=quests_targets,
        inventory=inventory,
        player_level=player_level,
        player_xp_for_next_level=player_xp_for_next_level,
        skills=skills,
    )


def to_dict(result: ParseResult) -> dict:
    d = asdict(result)
    # injetar campos derivados úteis para consumo
    for q in d["quests_objectives"]:
        statuses = {o["status"] for o in q["objectives"]}
        q["active"] = bool(statuses & OBJ_ACTIVE_STATUSES)
        q["displayed"] = "DISPLAYED" in statuses
    return d


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────


def _print_summary(result: ParseResult) -> None:
    n_on = sum(1 for q in result.quests_flags if q.on)
    n_active = sum(1 for q in result.quests_objectives if q.active)
    n_displayed = sum(1 for q in result.quests_objectives if q.displayed)
    n_targets = len(result.quests_targets)
    n_inv = len(result.inventory)
    n_skills = sum(1 for s in result.skills if s.rank > 0)
    extra = ""
    if result.player_level is not None:
        extra = f", nível {result.player_level}, {n_skills}/{len(result.skills)} skills com rank"
    print(
        f"resumo: {len(result.quests_flags)} quest flags ({n_on} On), "
        f"{len(result.quests_objectives)} blocos de objetivos "
        f"({n_active} ativas, {n_displayed} no journal), "
        f"{n_targets} quests com markers, {n_inv} itens no inventário"
        f"{extra}",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("log", type=Path, help="caminho do sfse_plugin_console.log")
    ap.add_argument(
        "-o",
        "--out",
        type=Path,
        default=None,
        help="arquivo JSON de saída (default: stdout)",
    )
    args = ap.parse_args(argv)

    if not args.log.exists():
        print(f"erro: log não encontrado: {args.log}", file=sys.stderr)
        return 2

    result = parse(args.log)
    _print_summary(result)
    payload = json.dumps(to_dict(result), ensure_ascii=False, indent=2)

    if args.out:
        args.out.write_text(payload + "\n", encoding="utf-8")
        print(f"json escrito em {args.out}", file=sys.stderr)
    else:
        print(payload)

    return 0


if __name__ == "__main__":
    sys.exit(main())
