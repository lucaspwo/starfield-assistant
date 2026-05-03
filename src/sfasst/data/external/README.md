# Fontes externas

## `system_data.txt`

Coordenadas 3D de sistemas estelares de Starfield em anos-luz, reconstruídas
por **s9w** rastreando estrelas visíveis no skybox do jogo e alinhando ao
catálogo HIPPARCOS/HYG.

- Origem: <https://github.com/s9w/starfield-navigator>
- Arquivo raw: <https://raw.githubusercontent.com/s9w/starfield-navigator/master/starfield_navigator/system_data.txt>
- Cobertura: 73 sistemas com XYZ
- Limitação: só 7 estão explicitamente mapeados ao nome do jogo
  (Sol, Alpha Centauri, Cheyenne, Volii, Narion, Porrima, Jaffa).
  O resto aparece por nome real (HIP/Gliese) — precisamos cruzar com curadoria
  manual em `data/system_name_aliases.tsv` (mapping starfield_name → nome real).
- Erro: coordenadas reconstruídas, ~1 ly de imprecisão.

Não editar. Pra atualizar, baixar fresh do raw acima.
