# Containers: estado da arte

## Resumo

| Container | Suporte | Como |
|---|---|---|
| Player carry | ✅ | `Player.ShowInventory` |
| Cofre do Lodge | ✅ | `00266E81.ShowInventory` (FormID estático do container) |
| Outras estáticas (outpost storage, baús, faction safes) | ✅ via FormID | mesmo padrão: descobrir o FormID e adicionar no `dump.txt` |
| **Cargo da nave** | ❌ | bloqueado por design — Bethesda não expõe |

## Investigação

### Cargo da nave

- `Player.GetSpaceShip` retorna o ref do casco (e.g. `FF02FF39`)
- Clicar em qualquer parte do interior/exterior dá o mesmo ref
- `<shipRef>.ShowInventory` **retorna vazio**
- Interagir com o cargo via menu da nave + `getselectedref` retorna `None`
  (o menu não passa por seleção de ref)

### Cofre do Lodge — RESOLVIDO

- Mirar no cofre com console aberto dá ref `0014BCEC` — **ativador visual,
  não aceita ShowInventory**
- `0014BCEC.GetItemCount 0000000F` responde:

  ```
  Calling Reference is not a Container Object
  ```

- O **container real** é o FormID estático `00266E81` (documentado pela
  comunidade Bethesda). `00266E81.ShowInventory` lista os 64 itens
  efetivamente guardados.

**Lição**: o Starfield (diferente do Skyrim) não expõe a relação
ativador → container via `GetLinkedRef`. Quando `ShowInventory` falha
silenciosamente, vale procurar o FormID do container real em wikis
ou via xEdit/SF1Edit.

### Cargo da nave — BLOQUEADO POR DESIGN

Investigação no [Papyrus Index](https://papyrus.bellcube.dev/starfield/script/spaceshipreference/)
confirma: o script `SpaceshipReference` não expõe **nenhuma** função pra
obter o container de cargo. Existe `OpenInventory()` mas só abre a UI; não
retorna ObjectReference.

Implicações:
- `<shipref>.ShowInventory` retorna vazio (cargo não é inventário direto do casco)
- Não há FormID estático de "current ship cargo" — é um runtime instance
  que muda quando o jogador troca de home ship
- A relação ship → cargo está encapsulada no engine, fora do alcance Papyrus

**Único caminho técnico**: plugin SFSE em C++ que acessa a memória do jogo
diretamente. Investimento desproporcional ao escopo do projeto.

**Workaround prático**: antes do `bat dump`, no menu da nave fazer "Pegar
tudo" do cargo → tudo vai pro player carry → `bat dump` captura → depois
"Guardar tudo" volta. Pesado mas funciona.

### `GetBaseObject` não existe no Starfield

Diferente do Skyrim, o console responde `Unknown variable or function
'GetBaseObject'. Syntax Error`. É preciso usar `GetItemCount` ou outra
query como prova de que o ref aceita inventário.

## Caminhos para resolver no futuro

1. **Papyrus script** num `.esm` que use `Game.GetPlayer().GetCurrentShipReference().GetCargoContainer()` (ou equivalente) e dumpe o conteúdo via `Debug.Trace`. Requer Creation Kit ou edição do script via xEdit.
2. **Editor IDs / FormIDs conhecidos**: identificar os formIDs dos containers reais consultando os esm com xEdit/SF1Edit.
3. **Plugin SFSE C++** que exponha um novo comando `dumpcontainer <ref>`. Maior investimento.

## Decisão atual

- **Containers estáticos**: suportados. Adicionar `<FormID>.ShowInventory`
  no `dump.txt` pra qualquer container do mundo cujo FormID seja conhecido.
- **Cargo da nave**: pulando. Custo de implementar (SFSE C++ plugin) não
  compensa o benefício.
