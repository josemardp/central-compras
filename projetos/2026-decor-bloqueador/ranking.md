# Ranking

Gerado em 2026-09-21T13:09:00.

## Elegiveis

1. Impermeabilizante Block Total Decor Colors - 75.1
   qualidade -- · valor 1.00 · risco 0.44 · aderencia -- · conveniencia --
   custo total R$ 379,99 / Loja Decor Colors / estimativa web
   confianca 45% - sem dado em: qualidade, conveniencia, aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.
   cotacao vencida: 25 dias desde a coleta (limite 14 para fonte=web); recote antes de decidir

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
