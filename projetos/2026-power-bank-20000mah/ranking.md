# Ranking

Gerado em 2026-10-09T07:55:51.

## Elegiveis

1. Basike C10 20.000 mAh 45W cabo integrado - 80.6
   qualidade 0.71 · valor 1.00 · risco 0.60 · aderencia -- · conveniencia 1.00
   custo total R$ 194,75 / Amazon / estimativa web
   confianca 85% - sem dado em: aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

2. Samsung EB-P4520 20.000 mAh 45W - 73.4
   qualidade 0.90 · valor 0.72 · risco 0.54 · aderencia -- · conveniencia 0.64
   custo total R$ 269,10 / Amazon / estimativa web
   confianca 85% - sem dado em: aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

3. Anker Zolo 20K A1689 - 70.3
   qualidade 0.45 · valor 0.73 · risco 0.90 · aderencia -- · conveniencia 1.00
   custo total R$ 265,03 / Amazon / estimativa web
   confianca 85% - sem dado em: aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

## Cortados pelos gates

- Baseus EnerFill FC51 Bipow2 Pro 20.000 mAh 22,5W: produto descartado (Sem PPS na ficha do anuncio oficial (so PD fixo e SCP Huawei): S20 FE fica em ~15W. Falha requisito obrigatorio.); avaliacoes insuficientes (30 < 300)

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
