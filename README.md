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
- ✅ Cruzamento materiais × inventário com scoring de esforço
- ❌ Cargo da nave / cofre do Lodge — limitação conhecida
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

## Coleta de dados (cada vez que quiser um snapshot)

1. Copie [`scripts/dump.txt`](scripts/dump.txt) para a raiz do diretório do jogo
   (mesmo lugar de `Starfield.exe`)
2. No jogo, abra o console (tecla `~`)
3. Digite `bat dump` e aperte Enter
4. Aguarde os comandos rodarem (saída no console)
5. O arquivo `Data/SFSE/plugins/sfse_plugin_console.log` agora contém o snapshot

## Parsing

(em construção — ver tasks)

```
python -m sfasst.parse_log "/mnt/c/.../sfse_plugin_console.log"
```
