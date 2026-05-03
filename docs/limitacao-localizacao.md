# Localização do jogador: estado da arte

## Resumo

| Capacidade | Suporte | Como |
|---|---|---|
| Coordenadas X/Y/Z | ✅ | `Player.GetPos X` (e Y, Z) |
| Em interior? | ✅ | `Player.IsInInterior` (texto: "is an Interior" / "is not an Interior") |
| No espaço? | ✅ | `Player.IsInSpace` (0/1) |
| **Nome da location atual** | ❌ | bloqueado por design — console não expõe |
| Nome da cell atual | ❌ | mesmo problema |

## Investigação

Sondamos várias funções via `scripts/probe_location.txt` e `probe_isinloc.txt`.

### Não funcionam (engine retorna `Unknown variable or function` ou `Script command not found`)

- `Player.GetCurrentLocation`
- `Player.GetParentCell`
- `Player.GetWorldspace` / `GetWorldspace`
- `Player.GetCurrentRegion` / `GetPlayerRegion`
- `Player.GetPlanet`
- `Player.GetSpaceshipParentLocation`
- `Player.GetCurrentLocationName`
- `Player.GetEditorLocation`
- `Player.IsInLocation <FormID>` / `GetIsInLocation` / `GetInCurrentLoc` (todas variantes)

### Funcionam parcialmente

- `Player.GetInWorldspace`: aceita a função mas exige um WorldSpace como parâmetro
  (`Missing parameter WorldSpace`). Inviável sem enumerar FormIDs de worldspaces.
- `Player.GetAVInfo Variable10`: retorna info, mas as variáveis customizadas
  expostas não trazem semântica de location.

## Conclusão

Mesmo padrão documentado em `limitacao-containers.md` (engine não expõe certos
getters via console). Não há caminho técnico simples pra ler o nome do local.

## Decisão atual

- **Capturar o que dá**: coordenadas + flags `IsInInterior` / `IsInSpace`. Vai
  pro header do relatório como contexto de sanidade.
- **Filtro por local atual**: declarado pelo usuário via `--here <label>`
  (ex.: `scripts/run.sh --here cydonia`). O label é casado por substring
  case-insensitive contra `LOCATION_KEYWORDS` em `cross.py`. Quests que batem
  ganham badge `[AQUI AGORA]` e vão pro topo do bucket.

## Caminhos pra resolver no futuro

1. **Plugin SFSE C++** que exponha `getplayerlocation` lendo a memória do jogo.
   Mesmo padrão de investimento desproporcional citado em containers.
2. **Tabela de bounding boxes** mapeando coords → nome de local. Funciona só em
   cells nomeadas estáveis (cidades). Custo de curadoria alto.
3. **Mod terceiro** que escreva o nome da location num save variable acessível
   via `GetAV` ou `GetGlobalValue`. Depende de existir um mod assim.
