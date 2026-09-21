# Ranking

Gerado em 2026-09-21T13:43:53.

## Elegiveis

1. Samsung Galaxy Fit3 - 70.0
   qualidade 1.00 · valor 0.61 · risco 0.38 · aderencia 0.67 · conveniencia --
   custo total R$ 275,00 / Mercado Livre / confirmada manualmente
   confianca 90% - sem dado em: conveniencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.
   cotacao vencida: 16 dias desde a coleta (limite 7 para fonte=manual); recote antes de decidir

2. Redmi Watch 5 Lite - 69.0
   qualidade 1.00 · valor 0.56 · risco 0.38 · aderencia -- · conveniencia --
   custo total R$ 298,86 / Mercado Livre / confirmada manualmente
   empate tecnico com o lider: decida pelo criterio humano, nao pelo numero
   confianca 75% - sem dado em: conveniencia, aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.
   cotacao vencida: 16 dias desde a coleta (limite 7 para fonte=manual); recote antes de decidir

3. Xiaomi Smart Band 9 Active - 67.6
   qualidade 0.49 · valor 1.00 · risco 0.61 · aderencia 0.67 · conveniencia 0.57
   custo total R$ 169,00 / Amazon / confirmada manualmente
   empate tecnico com o lider: decida pelo criterio humano, nao pelo numero
   cotacao vencida: 17 dias desde a coleta (limite 7 para fonte=manual); recote antes de decidir

4. Huawei Band 11 - 65.9
   qualidade 0.74 · valor 0.79 · risco 0.38 · aderencia -- · conveniencia --
   custo total R$ 214,95 / Amazon / confirmada manualmente
   confianca 75% - sem dado em: conveniencia, aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.
   cotacao vencida: 16 dias desde a coleta (limite 7 para fonte=manual); recote antes de decidir

## Cortados pelos gates

- Huawei Band 10: avaliacoes insuficientes (2 < 20) alertas: AVAL_SUSPEITA
- Huawei Band 11 Pro: custo_total acima do preco_teto do briefing (369.55 > 300.0); nota_ajustada abaixo do gate (0.0 < 4.0); avaliacoes insuficientes (0 < 20)
- Huawei Band 9: produto descartado (Preco so tem fonte web instavel (mesmo anuncio variou entre R$239,88 e R$312 em relatorios diferentes no mesmo periodo) e o produto aparece esgotado nas lojas onde foi possivel verificar de verdade (KaBuM). Sem cotacao manual confiavel, nao serve pra decisao.); nota_ajustada abaixo do gate (0.0 < 4.0); avaliacoes insuficientes (0 < 20)

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
