# Validacao

Gerado em 2026-09-15T20:28:45.

## Erros

- cotacoes.csv linha 12: campos obrigatorios ausentes: garantia_meses
- cotacoes.csv linha 13: campos obrigatorios ausentes: garantia_meses
- cotacoes.csv linha 14: campos obrigatorios ausentes: garantia_meses
- cotacoes.csv linha 15: campos obrigatorios ausentes: garantia_meses
- cotacoes.csv linha 16: campos obrigatorios ausentes: garantia_meses
- cotacoes.csv linha 17: campos obrigatorios ausentes: garantia_meses

## Avisos

- cotacoes.csv linha 11 (huawei-band-10): alertas AVAL_SUSPEITA
- huawei-band-11: cotacao usada no ranking tem 10 dias (limite 7 para fonte=manual). Recote antes de decidir.
- huawei-band-11-pro: cotacao usada no ranking tem 10 dias (limite 7 para fonte=manual). Recote antes de decidir.
- redmi-watch-5-lite: cotacao usada no ranking tem 10 dias (limite 7 para fonte=manual). Recote antes de decidir.
- Regra de parada (de_200_a_2000): 6 candidatos para um teto de 5. Pesquisar demais tambem custa caro.
- Regra de parada (de_200_a_2000): minimo de 2 cotacao(oes) por candidato. Abaixo disso: huawei-band-10, huawei-band-11, huawei-band-11-pro, redmi-watch-5-lite, samsung-galaxy-fit3, xiaomi-smart-band-9-active.
- cotacoes.csv esta num schema antigo, sem as colunas: estoque, proveniencia. Rode `migrar-cotacoes` para atualizar o cabecalho.
- Categoria `wearable` sem configuracao propria: usa regras genericas. Revise atributos e gates.

## Criterio

- Erro: impede decisao confiavel ou viola schema.
- Aviso: nao impede pesquisa, mas precisa ser considerado antes de comprar.
