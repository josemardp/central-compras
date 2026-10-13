# Ranking

Gerado em 2026-10-12T22:53:04.

## Elegiveis

1. Electrolux LED13 Essential Care 13kg 127V - 91.0
   qualidade 0.97 · valor 1.00 · risco 0.82 · aderencia -- · conveniencia 0.68
   custo total R$ 1.868,90 / Loja Electrolux / estimativa web
   confianca 85% - sem dado em: aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

2. Electrolux LED15 Essential Care 15kg 127V - 86.0
   qualidade 0.85 · valor 0.97 · risco 0.82 · aderencia -- · conveniencia 0.68
   custo total R$ 1.918,90 / Loja Electrolux / estimativa web
   confianca 85% - sem dado em: aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

## Cortados pelos gates

- Brastemp BWK13AB 13kg 127V: custo_total acima do preco_teto do briefing (3047.0 > 2300.0)
- Consul CWH13AB 13kg 127V: garantia_tipo nao aceito (nenhuma)
- Electrolux LDA13 Efficient 13kg 127V: nota_ajustada abaixo do gate (4.259 < 4.3)
- Electrolux LET13 Efficient 13kg 127V: avaliacoes insuficientes (6 < 10)
- Midea Wave Agitator 13kg MA512W130A 127V: garantia_tipo nao aceito (nenhuma)

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
