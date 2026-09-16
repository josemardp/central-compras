# Ranking

Gerado em 2026-09-15T20:28:44.

## Elegiveis

1. Fechadura Dianteira Direita Universal Automotive 15640 Eletrica - 79.3
   qualidade 0.50 · valor 1.00 · risco 0.71 · aderencia 1.00 · conveniencia 1.00
   custo total R$ 219,10 / Mercado Livre / confirmada manualmente

2. Fechadura Dianteira Direita Genuina Hyundai Mobis 81320-1S021 - 75.4
   qualidade 0.78 · valor 0.59 · risco 0.73 · aderencia 1.00 · conveniencia --
   custo total R$ 370,30 / Mercado Livre / estimativa web
   confianca 90% - sem dado em: conveniencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

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
