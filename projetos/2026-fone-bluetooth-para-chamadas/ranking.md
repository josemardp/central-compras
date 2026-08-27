# Ranking

Gerado em 2026-08-27T11:16:40.

## Elegiveis

1. QCY H3 ANC - 84.3
   qualidade 0.97 · valor 1.00 · risco 0.71 · aderencia 0.50 · conveniencia --
   custo total R$ 296,64 / Amazon / estimativa web
   confianca 90% - sem dado em: conveniencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.
   aguardando preco desde 2026-08-26: faltam R$ 36,64 para o alvo de R$ 260,00. Voce decidiu esperar, nao comprar.

2. Soundcore Anker Life Q30 - 58.6
   qualidade 0.58 · valor 0.64 · risco 0.60 · aderencia 0.50 · conveniencia --
   custo total R$ 466,00 / Amazon / estimativa web
   confianca 90% - sem dado em: conveniencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

## Cortados pelos gates

- Edifier W820NB Plus: avaliacoes insuficientes (128 < 150) alertas: AVAL_SUSPEITA
- JBL Tune 770NC: avaliacoes insuficientes (0 < 150)

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
