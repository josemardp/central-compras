# Ranking

Gerado em 2026-09-21T13:43:51.

## Elegiveis

1. Nobreak TS Shara UPS Mini 700VA bivolt 6 tomadas saida 115V - 57.7
   qualidade 0.35 · valor 1.00 · risco 0.38 · aderencia -- · conveniencia --
   custo total R$ 409,00 / Amazon / estimativa web
   confianca 75% - sem dado em: conveniencia, aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

2. Nobreak Intelbras ATTIV 700VA bivolt - 52.2
   qualidade 0.45 · valor 0.70 · risco 0.38 · aderencia -- · conveniencia 0.57
   custo total R$ 582,52 / Amazon / estimativa web
   confianca 85% - sem dado em: aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

## Cortados pelos gates

- Nobreak APC Back-UPS 700VA bivolt saida 115V: nota_ajustada abaixo do gate (0.0 < 4.0); avaliacoes insuficientes (0 < 20)
- Nobreak SMS Tech 700VA interativo bivolt saida 115V: nota_ajustada abaixo do gate (0.0 < 4.0); avaliacoes insuficientes (0 < 20)

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
