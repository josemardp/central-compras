# Ranking

Gerado em 2026-09-04T11:34:33.

## Elegiveis

1. Pulseira Silicone Trava-Clique (Generic) - 62.1
   qualidade 0.47 · valor 1.00 · risco 0.38 · aderencia -- · conveniencia --
   custo total R$ 27,99 / Amazon / estimativa web
   confianca 75% - sem dado em: conveniencia, aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

## Cortados pelos gates

- Pulseira Aco Inoxidavel Band 9/8: custo_total acima do preco_teto do briefing (110.16 > 60.0); avaliacoes insuficientes (1 < 20)
- Pulseira Nylon Compativel Band 9/8: custo_total acima do preco_teto do briefing (97.19 > 60.0); nota_ajustada abaixo do gate (0.0 < 4.0); avaliacoes insuficientes (0 < 20)
- Pulseira Silicone Fivela Reversa (xDfind): avaliacoes insuficientes (13 < 20)

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
