"""Gera data/systems.tsv a partir de:
- data/external/system_data.txt (XYZ por código de 3 letras, fonte: s9w)
- data/system_aliases.tsv (curadoria starfield_name -> match_pattern)

Saída: starfield_system, x_ly, y_ly, z_ly, source, real_name

Uso: python3 scripts/build_systems_data.py
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "src" / "sfasst" / "data"
SOURCE = DATA / "external" / "system_data.txt"
ALIASES = DATA / "system_aliases.tsv"
OUT = DATA / "systems.tsv"


def parse_source() -> tuple[dict[str, tuple[float, float, float]], dict[str, dict]]:
    """Retorna (xyz_by_code, meta_by_code).

    xyz_by_code: code -> (x, y, z)
    meta_by_code: code -> {'starfield_name': str, 'real_name': str, 'constellation': str}
    """
    raw = SOURCE.read_text(encoding="utf-8").splitlines()

    # Separar em seções (por linhas em branco)
    sections: list[list[str]] = [[]]
    for line in raw:
        if not line.strip():
            sections.append([])
        else:
            sections[-1].append(line)

    if len(sections) < 2:
        raise RuntimeError(f"{SOURCE} tem formato inesperado (esperava ≥2 seções)")

    xyz: dict[str, tuple[float, float, float]] = {}
    meta: dict[str, dict] = {}

    # Seção 1: XYZ
    for ln in sections[0]:
        # remover comentários inline (#) e split por ;
        clean = ln.split("#", 1)[0].strip()
        if not clean:
            continue
        parts = [p.strip() for p in clean.split(";")]
        if len(parts) < 4:
            continue
        code = parts[0]
        try:
            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
        except ValueError:
            continue
        xyz[code] = (x, y, z)

    # Seção 2: nomes
    for ln in sections[1]:
        clean = ln.split("#", 1)[0].strip()
        if not clean:
            continue
        # formato: CODE:size;STARFIELD_NAME;Real_Name_HIP_ID;Constellation
        # campos finais podem estar vazios (ex.: SOL não tem real_name ou constellation)
        parts = [p.strip() for p in clean.split(";")]
        if len(parts) < 2:
            continue
        # padding com strings vazias
        while len(parts) < 4:
            parts.append("")
        code_size = parts[0]
        code = code_size.split(":", 1)[0]
        starfield_name = parts[1]
        real_name = parts[2]
        constellation = parts[3]
        meta[code] = {
            "starfield_name": starfield_name,
            "real_name": real_name,
            "constellation": constellation,
        }

    return xyz, meta


def parse_aliases() -> list[tuple[str, str, str]]:
    """[(starfield_system, match_pattern, notes), ...]"""
    out: list[tuple[str, str, str]] = []
    if not ALIASES.exists():
        return out
    for raw in ALIASES.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.startswith("starfield_system"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        sf = parts[0].strip()
        pat = parts[1].strip()
        notes = parts[2].strip() if len(parts) >= 3 else ""
        out.append((sf, pat, notes))
    return out


def main() -> None:
    xyz, meta = parse_source()
    aliases = parse_aliases()

    rows: list[dict] = []
    seen_codes: set[str] = set()

    # 1. Sistemas explicitamente nomeados na seção 2 (starfield_name não-vazio)
    for code, m in meta.items():
        if not m["starfield_name"]:
            continue
        if code not in xyz:
            continue
        x, y, z = xyz[code]
        rows.append({
            "starfield_system": m["starfield_name"],
            "x_ly": x, "y_ly": y, "z_ly": z,
            "source": "direct",
            "real_name": m["real_name"] or "",
        })
        seen_codes.add(code)

    # 2. Sistemas via curadoria — buscar pattern em real_name
    for sf, pat, _notes in aliases:
        # já adicionado pela seção direct?
        if any(r["starfield_system"].upper() == sf.upper() for r in rows):
            continue
        # achar code cujo real_name contém o pattern
        match_code: str | None = None
        for code, m in meta.items():
            if pat.lower() in m["real_name"].lower():
                match_code = code
                break
        if match_code is None or match_code not in xyz:
            print(f"aviso: sem match para {sf} (pattern '{pat}')")
            continue
        x, y, z = xyz[match_code]
        rows.append({
            "starfield_system": sf,
            "x_ly": x, "y_ly": y, "z_ly": z,
            "source": f"via_alias:{pat}",
            "real_name": meta[match_code]["real_name"],
        })
        seen_codes.add(match_code)

    # ordenar por nome
    rows.sort(key=lambda r: r["starfield_system"].upper())

    # escrever TSV
    out_lines = ["starfield_system\tx_ly\ty_ly\tz_ly\tsource\treal_name"]
    for r in rows:
        out_lines.append(
            f"{r['starfield_system']}\t{r['x_ly']:.3f}\t{r['y_ly']:.3f}"
            f"\t{r['z_ly']:.3f}\t{r['source']}\t{r['real_name']}"
        )
    OUT.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"escrito {OUT}: {len(rows)} sistemas")


if __name__ == "__main__":
    main()
