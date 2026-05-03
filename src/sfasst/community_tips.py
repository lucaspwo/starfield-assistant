"""Dicas curadas da comunidade pra quests específicas.

Cada entrada é um par (matcher, tip):
- matcher pode ser substring do display_name OU prefixo de editor_id (com `eid:`)
- tip é string curta (até ~120 chars) com a dica

Apenas dicas com alta confiança (wikis, guides amplamente citados). Quando
em dúvida, NÃO adicione — preferir vazio a inventar.
"""

# Lista ordenada — primeiro match vence.
COMMUNITY_TIPS: list[tuple[str, str]] = [
    # ── Main quest (Constellation) ──
    ("vislumbres finais",
     "Main quest. Vai a Freya III; ao concluir libera 'Descoberta' e leva ao NG+. "
     "Faça side quests pendentes ANTES, NG+ não carrega progresso de side."),
    ("descoberta",
     "Depende de 'Vislumbres Finais'. Última main quest antes do NG+; ponto de "
     "não-retorno — finalize tudo que importa antes."),

    # ── Faction questlines (entry points) ──
    ("de volta ao trabalho",
     "Entrada da Ryujin Industries (Neon). Questline longa (~10h) com "
     "stealth/hacking; só vale se for fazer a faction inteira."),
    ("medidas defensivas",
     "Questline UC Vanguard. Davis Wilson (Akila) é tangencial — checar se faz "
     "parte de Freestar Rangers; pode confundir as duas."),
    ("indicador adicional da comte tuala",
     "Entrada da UC Vanguard. Recomenda nível 5+ pelo MAST simulator; "
     "primeira missão é a Eccentric (combate espacial básico)."),

    # ── Crimson Fleet / Sysdef ──
    ("o teste",
     "Quest CFSD: ponto de decisão entre Frota Escarlate e UC SysDef. Escolha "
     "afeta toda a faction line; pesquise as duas rotas antes de comprometer."),
    ("ônus da prova",
     "Quest da UC Sysdef. Dependendo da rota CF/UC escolhida, este é o ponto "
     "que sela o lado escolhido."),

    # ── Constellation side ──
    ("casa do vlad",
     "Visita à casa de Vladimir Sall; libera diálogo extra e contexto da "
     "Constellation. Ele te dá Plataforma de Pesquisa e info de planetas."),
    ("primeiro contato",
     "Em Porrima II. Resolução pacífica é amplamente recomendada — concede "
     "grav drive raro e XP. Resolução violenta perde recompensas."),

    # ── Misc city/companion ──
    ("coleção de espécimes",
     "Dra. Darvish (Paradiso). Antimicrobiano dropa de criaturas em planetas "
     "específicos; biome trópical. Use scanner pra identificar a fauna."),
    ("zona de impacto",
     "Quest curta na Akila. Diálogo com Sr. Tate; usar fala persuasiva resolve "
     "sem combate."),
    ("em fuga",
     "Cydonia. 'Vá para a Via Rubra' inicia uma missão de bar curta — "
     "rastreio de NPC suspeito pelos arredores."),
    ("ordens médicas",
     "Quest do Dr. Gennady Ayton (Cydonia). Entrega/diálogo curto; opção "
     "Persuasão evita ter que farmar item."),

    # ── Survey / Research helpers ──
    ("ache condutor contínuo",
     "Quest do skill tree de Astrodinâmica/Geofísica. Procure planetas "
     "extremos; o material é raro mas spawn é determinístico."),
    ("ache plumas mantélicas",
     "Skill Química. Spawn em planetas vulcânicos do sistema Altair."),
    ("ache estações de tempestade solar",
     "Skill Geofísica. Spawn perto de estrelas binárias/quentes."),

    # ── Outras com prefix de editor_id ──
    ("eid:ffneonguardpointer",
     "Patrol pointer dos guardas de Neon. Conversa rápida (1 fala), XP "
     "pequeno. Bom de fazer ao passar por Neon."),
    ("eid:ffcydonia",
     "Misc de Cydonia. Tipicamente uma conversa ou entrega no perímetro "
     "da cidade."),
    ("eid:ffparadiso",
     "Misc de Paradiso. Maioria são pedidos de funcionários no resort."),

    # ── DLC ──
    ("topo da lici",
     "Quest do DLC Shattered Space. Pousa em Dazra e inicia contato com a "
     "House Va'ruun — campanha do DLC, recomenda 35+."),

    # ── Companion ──
    ("desfecho para neonz",
     "Cleanup pointer das misc de Neon — fim de dialogue chain de NPC. "
     "Geralmente concede créditos e fecha a quest line do bairro."),
]


def find_tip(display_name: str, editor_id: str | None = None) -> str | None:
    """Retorna a primeira dica que casar; None se nenhuma."""
    dn = display_name.lower()
    eid = (editor_id or "").lower()
    for matcher, tip in COMMUNITY_TIPS:
        if matcher.startswith("eid:"):
            if eid and eid.startswith(matcher[4:]):
                return tip
        else:
            if matcher in dn:
                return tip
    return None
