# Decisão de abordagem

## Contexto

Objetivo: ler quests ativas e inventário do personagem para cruzar com
requisitos de quest e responder "que quests dá pra fazer agora?".

## Opções avaliadas

### A. Parsing direto do `.sfs`

`.sfs` é zlib-comprimido em chunks. A descompressão está resolvida em
[Nexus-Mods/StarfieldSaveTool](https://github.com/Nexus-Mods/StarfieldSaveTool).

Mas o tool da Nexus só decodifica header + lista de plugins. O autor declara:
> "Rest of file has not been worked out yet."

Os "change forms" (quests, inventário, NPCs) usam formato Bethesda parecido
com Skyrim/FO4, mas com diferenças não documentadas publicamente. Reverter
isso é trabalho de pesquisa de semanas.

**Veredito:** inviável como atalho. Bloqueia o projeto.

### B. Heurística sobre a strings array já decodificada

A "strings array" do save fica num offset apontado por `newBlock2.stringsArrayOffset`
e tem editor IDs de quests/itens em texto. Daria pra grep, mas sem estrutura
(que quest está ativa? em que estágio? quanto temos de cada item?).

**Veredito:** entrega muito pouco. Útil só como fallback parcial.

### C. SFSE + Console Output To File (escolhida) ✅

**Como funciona:**
- SFSE injeta uma DLL no Starfield.exe e expõe APIs adicionais
- O mod ["Console Output To File"](https://www.nexusmods.com/starfield/mods/3142)
  redireciona todo output do console para `Data/SFSE/plugins/sfse_plugin_console.log`
- O console aceita `bat <nome>` para rodar batch files de comandos
- Comandos relevantes (todos nativos do engine, sem código custom):
  - `ShowQuests` — lista todas as quests do jogo com flag de ativa/completa
  - `ShowQuestObjectives` — objetivos ativos
  - `ShowQuestTargets` — alvos atuais
  - `Player.ShowInventory` — inventário completo do jogador
  - `<RefID>.ShowInventory` — inventário de qualquer container (Lodge, nave)

**Vantagens:**
- Zero código C++/plugin custom
- Dados frescos do runtime (autoritativos)
- Suporta DLCs e mods automaticamente
- Reverter `.sfs` não é problema nosso

**Limitações:**
- Requer instalar SFSE + um plugin (one-time, padrão na cena de mods)
- Snapshot é manual (jogador digita `bat dump` quando quiser atualizar)
- Containers como cargo da nave precisam do RefID — temos que descobrir o RefID
  uma vez e gravar no batch file

### D. Plugin SFSE custom em C++

Se C tivesse limitação fatal, escreveríamos um plugin SFSE em C++/CommonLibSF
que dumpa direto pra JSON. Custa tempo de setup MSVC + curva da API. Mantemos
como plano B se C bater num teto.

## Decisão

Seguir com **C**. Plano B (D) só se algo crítico faltar no que o console expõe.
