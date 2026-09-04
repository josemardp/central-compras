# Ranking

Gerado em 2026-09-04T11:34:32.

## Elegiveis

1. Huawei Band 9 - 71.9
   qualidade 0.98 · valor 0.70 · risco 0.38 · aderencia 0.67 · conveniencia --
   custo total R$ 239,88 / Mercado Livre / estimativa web
   confianca 90% - sem dado em: conveniencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

2. Samsung Galaxy Fit3 - 69.7
   qualidade 1.00 · valor 0.61 · risco 0.38 · aderencia 0.67 · conveniencia --
   custo total R$ 279,00 / Mercado Livre / estimativa web
   empate tecnico com o lider: decida pelo criterio humano, nao pelo numero
   confianca 90% - sem dado em: conveniencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

3. Xiaomi Smart Band 9 Active - 67.3
   qualidade 0.49 · valor 1.00 · risco 0.59 · aderencia 0.67 · conveniencia 0.57
   custo total R$ 169,00 / Amazon / confirmada manualmente

## Cortados pelos gates

Nenhum corte.

## Observacoes

- Score zerado significa corte por gate, nao produto ruim em absoluto.
- `confianca` e a fracao do peso do score apoiada em dado real. Score 80 com confianca 60% nao e comparavel com score 80 com confianca 100%.
- Linha `fonte=web` nao fecha compra; confirme preco, estoque e frete antes de decidir.
- Diferenca de ate 3 pontos entre finalistas deve ser tratada como empate tecnico.
- `ranking.csv` e derivado e pode ser sobrescrito; `cotacoes.csv` preserva a serie historica.

## Como o score foi montado

- `qualidade`: nota ajustada em escala absoluta (4.0 = 0,00 / 4.8 = 1,00).
- `valor`: razao entre o custo do mais barato elegivel e o custo deste. Custar o dobro vale 0,50.
- `risco`: vendedor, tipo e prazo de garantia, menos penalidade por alerta de manipulacao.
- `aderencia`: percentual de requisitos do briefing atendidos pelo produto.
- `conveniencia`: prazo de frete em escala absoluta.
- O score e comparativo dentro do projeto: qualidade e conveniencia usam escalas fixas, mas valor depende do candidato elegivel mais barato. Compare candidatos da mesma compra.
