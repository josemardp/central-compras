# Ranking

Gerado em 2026-11-21T10:22:12.

## Elegiveis

1. Ventilador Torre Ventisol Fenix 75W c/ Controle Remoto 127V - 77.8
   qualidade 0.63 · valor 1.00 · risco 0.61 · aderencia 0.78 · conveniencia 1.00
   custo total R$ 245,98 / Amazon / estimativa web
   alertas: AVAL_SUSPEITA

2. Midea Climatizador de Ar Frio Liva AKAF1 (4,5L util / 7L) 60W 127V - 75.9
   qualidade 0.75 · valor 0.61 · risco 0.87 · aderencia 0.89 · conveniencia --
   custo total R$ 404,11 / Amazon / estimativa web
   empate tecnico com o lider: decida pelo criterio humano, nao pelo numero
   confianca 90% - sem dado em: conveniencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

3. WAP Climatizador de Ar Torre Control Digital 8,5L 100W 127V - 66.4
   qualidade 0.49 · valor 0.57 · risco 0.87 · aderencia 0.89 · conveniencia --
   custo total R$ 429,90 / Amazon / estimativa web
   confianca 90% - sem dado em: conveniencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

4. Climatizador Ventisol Torre Clit Abastece 3,6L 75W 127V (CLIT3.6-01) - 60.0
   qualidade 0.32 · valor 0.78 · risco 0.76 · aderencia 0.56 · conveniencia 0.75
   custo total R$ 315,90 / Amazon / estimativa web

5. Mondial Climatizador Flash Air CL-03 3,2L 80W 127V - 57.4
   qualidade 0.25 · valor 0.64 · risco 0.87 · aderencia 0.72 · conveniencia --
   custo total R$ 386,90 / Amazon / estimativa web
   confianca 90% - sem dado em: conveniencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

6. Climatizador Ventisol CLIN16-01 16L 130W 127V - 54.5
   qualidade 0.26 · valor 0.65 · risco 0.76 · aderencia 0.67 · conveniencia --
   custo total R$ 379,90 / Amazon / estimativa web
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
