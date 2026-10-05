# Ranking

Gerado em 2026-10-05T12:44:58.

## Elegiveis

1. Midea AI Ecomaster 12000 Frio 42EZVCA12M5 - 85.1
   qualidade 0.78 · valor 0.99 · risco 0.83 · aderencia -- · conveniencia 0.75
   custo total R$ 2.183,94 / Amazon / estimativa web
   confianca 85% - sem dado em: aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

2. LG Dual Inverter Voice +AI 12000 Frio S3-Q12JA31L - 82.8
   qualidade 0.78 · valor 1.00 · risco 0.83 · aderencia -- · conveniencia 0.54
   custo total R$ 2.159,10 / Amazon / estimativa web
   empate tecnico com o lider: decida pelo criterio humano, nao pelo numero
   confianca 85% - sem dado em: aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

3. Gree G-Side Auto Inverter 12000 Frio GWC12ATCXB - 74.1
   qualidade 0.53 · valor 0.92 · risco 0.90 · aderencia -- · conveniencia 0.64
   custo total R$ 2.355,90 / Amazon / estimativa web
   confianca 85% - sem dado em: aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

## Cortados pelos gates

- LG Dual Inverter Voice +AI 12000 Frio S3-Q12JA31J: nota_ajustada abaixo do gate (0.0 < 4.3); avaliacoes insuficientes (0 < 10)
- Samsung WindFree AI Pro 12000 Frio AR60H12D1AWNAZ: nota_ajustada abaixo do gate (0.0 < 4.3); avaliacoes insuficientes (0 < 10)

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
