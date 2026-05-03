# starfield-assistant

Assistente local que lê o estado do seu jogo Starfield (quests ativas + inventário)
e ajuda a decidir quais quests dá pra fazer agora com os itens que você já tem.

## Estado atual

Pivot de parsing direto do `.sfs` (formato proprietário, change forms ainda não
documentados publicamente) para captura runtime via **SFSE + Console Output To File**.
Detalhes em [`docs/decisao-abordagem.md`](docs/decisao-abordagem.md).

**Cobertura:**
- ✅ Quests ativas com objetivos (DISPLAYED no journal)
- ✅ Inventário do jogador (carry)
- ✅ Cofre do Lodge e qualquer container estático cujo FormID seja conhecido
- ✅ Cruzamento materiais × inventário com scoring de esforço
- ✅ Filtro por local atual via `--here` (declaração manual — engine não
  expõe location, ver [`docs/limitacao-localizacao.md`](docs/limitacao-localizacao.md))
- ✅ Skills/perks com rank atual, sugestões do próximo rank por skill
  (cruzando unlocks curados em `data/skills.tsv`) e sugestões de pesquisa
  estáticas (cruzando pré-requisitos com `data/research.tsv`)
- ❌ Cargo da nave — bloqueado por design do engine
  (ver [`docs/limitacao-containers.md`](docs/limitacao-containers.md))

## Como funciona

```
        in-game console                  arquivo log                  parser Python
  ┌─────────────────────────┐    ┌──────────────────────────┐    ┌─────────────────┐
  │ bat dump                │ →  │ sfse_plugin_console.log  │ →  │ inventário.json │
  │ (scripts/dump.txt)      │    │                          │    │ quests.json     │
  └─────────────────────────┘    └──────────────────────────┘    └─────────────────┘
```

## Pré-requisitos (Windows / instalar uma única vez)

1. **SFSE — Starfield Script Extender**: <https://www.nexusmods.com/starfield/mods/106>
   - Extrair os DLLs e `sfse_loader.exe` no diretório do jogo
     (`C:\Program Files (x86)\Steam\steamapps\common\Starfield`)
2. **Console Output To File (SFSE plugin)**: <https://www.nexusmods.com/starfield/mods/3142>
   - Instalar conforme instruções do mod (em geral, copiar pro `Data/SFSE/plugins/`)
3. **Inicie o jogo via `sfse_loader.exe`** (não pelo Steam direto)

## Configuração local

Os caminhos da instalação do jogo ficam em `.env` (não comitado).

```bash
cp .env.example .env
$EDITOR .env   # ajustar STARFIELD_GAME_LOG e STARFIELD_SAVES_DIR
```

## Coleta de dados (cada vez que quiser um snapshot)

1. Copie [`scripts/dump.txt`](scripts/dump.txt) para a raiz do diretório do jogo
   (mesmo lugar de `Starfield.exe`)
2. No jogo, abra o console (tecla `~`)
3. Digite `bat dump` e aperte Enter
4. Aguarde os comandos rodarem (saída no console)
5. O arquivo `Data/SFSE/plugins/sfse_plugin_console.log` agora contém o snapshot

## Pipeline (atalho)

```bash
scripts/run.sh                  # texto, com agrupamento por local
scripts/run.sh --json           # JSON estruturado
scripts/run.sh --here cydonia   # destaca quests do local atual ([AQUI AGORA])
                                # e mostra ROTA RÁPIDA (top 5 por proximidade × esforço)
scripts/run.sh --here neon --top 10  # mais quests na rota
```

## Interface gráfica

App nativo em PySide6 com 4 abas (Quests / Skills / Research / Status),
botão **Refresh** que executa o pipeline (após você rodar `bat dump` no jogo)
e campo **Local atual** que dispara a rota rápida por proximidade.

```bash
pip install -r requirements.txt   # primeira vez: PySide6
scripts/gui.sh                    # abre a janela
```

Em WSL2, requer WSLg (Windows 11) para renderizar a janela nativamente.

Faz tudo: copia o log do jogo, extrai só o último `bat dump`, parseia,
detecta o save mais recente pra ler o nível e cruza tudo com inventário.
