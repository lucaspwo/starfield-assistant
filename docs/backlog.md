# Backlog

Itens em aberto, ordenados por custo/benefício aparente. Sem compromisso de prazo.

## Gaps de cobertura

### Cargo da nave
Bloqueado por design do engine. Detalhes e caminhos técnicos em
[`limitacao-containers.md`](limitacao-containers.md). Workaround atual:
"Pegar tudo" no menu da nave antes do `bat dump`.

Caminhos possíveis:
1. Papyrus script num `.esm` usando `GetCurrentShipReference().GetCargoContainer()` + `Debug.Trace`
2. Descobrir FormIDs de containers reais via xEdit/SF1Edit
3. Plugin SFSE em C++ expondo `dumpcontainer <ref>`

### Containers estáticos além do cofre do Lodge
A infra (`dump.txt` + parser) já suporta múltiplos containers por FormID.
Só o cofre do Lodge (`00266E81`) está cadastrado. Falta cadastrar:
- Outpost storage (FormIDs variam por outpost — runtime instances)
- Baús/safes de facção
- Containers de companions

Caminho: garimpar FormIDs estáticos conhecidos (wiki/xEdit) e adicionar
no `dump.txt`.

## Qualidade de dados

### Dicas curadas para quests com esforço > 5
Hoje `community_tips.py` cobre só quests com esforço ≤ 5. Quests pesadas
ficam sem hint. Avaliar se vale curar dicas pra elas ou se o esforço alto
já desqualifica a quest do fluxo "fazer agora".

### TSV de skills/perks é manual
`5e37686` introduziu regeneração do `dump.txt` a partir de TSV de IDs,
mas a TSV em si é mantida à mão. Possível automação: scrape de wiki ou
extração via xEdit.

### Cobertura de sistemas no mapa estelar
`data/systems.tsv` tem 16 sistemas (7 explicitamente nomeados em
`system_data.txt` + 9 via `system_aliases.tsv`). Sistemas como Valo,
Kryx, Va'ruun'kai, Sagan, Freya, Nirvana, Suvorov ainda não estão
mapeados — quests nesses locais caem em `proximity_tier=5` (não entram
na ROTA RÁPIDA). Caminho: pesquisar correspondência real_name→starfield_name
na comunidade e adicionar em `system_aliases.tsv`. Alternativa: substituir
a fonte (s9w/starfield-navigator é incompleta — só ~73 dos ~120 sistemas)
por dump direto de STDT records via xEdit, se alguém publicar.

### Curadoria de unlocks de skills incompleta
45 das 82 skills têm `unlock_r1..r4` preenchidos. As 37 restantes
(p.ex. Ballistics, Lasers, Particle Beams, Boxing, Martial Arts,
Theft, Manipulation, etc.) aparecem em `sfasst.skill_suggestions`
sem texto se `--show-uncurated` for usado. Expandir conforme demanda.

## Não priorizado

- Inferência de localização (`681c7e2`) parece estável; revisitar só se
  surgir caso onde agrupamento por local falha.

## v1.1 (próxima)

- **Botão "Iniciar jogo via sfse_loader"** na toolbar da GUI: spawn do
  `sfse_loader.exe` (caminho relativo a `STARFIELD_GAME_LOG`) via
  `QProcess.startDetached`. Não bloqueia a janela do assistente.

## Concluído

- **Filtro de quests por local atual via `--here <label>`** —
  console não expõe nome de location (ver
  [`limitacao-localizacao.md`](limitacao-localizacao.md)). Pivot
  para declaração manual + contexto de coords/flags no header.
- **Sugestões de pesquisa (estático)** — `data/research.tsv` curado
  + `sfasst.research_suggestions` cruza com skills do save pra
  marcar projetos acessíveis vs bloqueados. Cobertura inicial: 24
  projetos das categorias Weaponry, Pharmacology, Equipment, Food
  and Drink, Outpost Development, Manufacturing.
- **Sugestões de skills pelo próximo rank** — `data/skills.tsv`
  expandido com colunas `unlock_r1..r4`; `sfasst.skill_suggestions`
  mostra o que cada próximo rank desbloqueia, agrupando por árvore
  e priorizando skills já investidas. Cobertura inicial: 45/82
  skills com unlocks curados.
- **GUI nativa em PySide6** — `sfasst.gui` com 4 abas (Quests/Skills/Research/Status),
  toolbar com botão Refresh (executa `scripts/run.sh` via QProcess e recarrega
  JSON) e campo "Local atual" que dispara rota rápida. Atalhos F5 / Ctrl+R.
  Launcher: `scripts/gui.sh`.
- **Prioridade de skills (onde gastar o próximo ponto)** — `sfasst.skill_priorities`
  combina (a) proximidade do gate de tier (4/8/12 ranks por árvore), (b) completion
  bonus pra skills em rank 3, (c) continuidade de investimento. Mostra painel de
  árvores + top N skills com justificativa.
- **Rota rápida por proximidade geográfica** — `data/external/system_data.txt`
  (s9w/starfield-navigator) + curadoria `data/system_aliases.tsv` →
  `data/systems.tsv` (16 sistemas com XYZ). `data/locations.tsv` mapeia
  labels de quest → sistema. `cross.py` calcula tier de proximidade
  (AQUI / MESMO SISTEMA / PERTO / INTERMEDIÁRIO / LONGE / DESCONHECIDO)
  e novo bloco "ROTA RÁPIDA" mostra top N quests por score
  `esforço + 5 × tier`. Habilitado quando `--here` é passado.

## Pendente em pesquisa

- **Rastreio de pesquisa em andamento**: hoje só sugerimos. Quando
  começarem a pesquisar, marcar projetos já feitos para sumirem da
  lista. Caminho: `Player.GetPerkRank <FormID>` aceita IDs de
  research projects (probe confirmou a função, mas FormIDs canônicos
  não estão na mão). Próximo passo: descobrir FormIDs via xEdit ou
  via `help` quando o matchstring exato for conhecido. Alternativa
  barata: arquivo `data/research_done.txt` editado à mão.
- **Curadoria de mais research projects**: 24 dos ~80 totais. Expandir
  conforme demanda.
