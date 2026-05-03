# Limitação: containers da nave e do Lodge

## Resumo

Não é possível ler o conteúdo do **cargo da nave** nem do **cofre do quarto
pessoal no Lodge** apenas via comandos de console + Console Output To File.
Ambos usam menus especiais cujo container interno **não é exposto ao console**.

## Investigação

### Cargo da nave

- `Player.GetSpaceShip` retorna o ref do casco (e.g. `FF02FF39`)
- Clicar em qualquer parte do interior/exterior dá o mesmo ref
- `<shipRef>.ShowInventory` **retorna vazio**
- Interagir com o cargo via menu da nave + `getselectedref` retorna `None`
  (o menu não passa por seleção de ref)

### Cofre do Lodge

- Mirar no cofre com console aberto dá ref `0014BCEC`
- Interagir com o cofre + fechar UI + `getselectedref` retorna o **mesmo**
  `0014BCEC`
- `0014BCEC.ShowInventory` retorna vazio
- `0014BCEC.GetLinkedRef` retorna `(00000000)` (sem ref linkada)
- `0014BCEC.GetItemCount 0000000F` responde:

  ```
  Calling Reference is not a Container Object
  ```

  Confirmação textual de que o ref é o **ativador/decoração**, não o
  container interno. O Starfield (diferente do Skyrim) não expõe a relação
  ativador→container via `GetLinkedRef`.

### `GetBaseObject` não existe no Starfield

Diferente do Skyrim, o console responde `Unknown variable or function
'GetBaseObject'. Syntax Error`. É preciso usar `GetItemCount` ou outra
query como prova de que o ref aceita inventário.

## Caminhos para resolver no futuro

1. **Papyrus script** num `.esm` que use `Game.GetPlayer().GetCurrentShipReference().GetCargoContainer()` (ou equivalente) e dumpe o conteúdo via `Debug.Trace`. Requer Creation Kit ou edição do script via xEdit.
2. **Editor IDs / FormIDs conhecidos**: identificar os formIDs dos containers reais consultando os esm com xEdit/SF1Edit.
3. **Plugin SFSE C++** que exponha um novo comando `dumpcontainer <ref>`. Maior investimento.

## Decisão atual

Tratar containers como **fora de escopo do MVP**. O `dump.txt` aceita refs
de containers extras quando soubermos os corretos, e o parser/cross já
lidam com múltiplos containers. Quando uma das vias acima for explorada,
os refs entram no batch sem mudança no resto do pipeline.
