# Ranking

Gerado em 2026-11-04T11:03:10.

## Elegiveis

1. Rivotril gotas (clonazepam) 2,5 mg/mL, 20 mL - 56.3
   qualidade -- · valor 1.00 · risco 0.44 · aderencia 0.00 · conveniencia --
   custo total R$ 25,51 / Drogaria Sao Paulo / estimativa web
   confianca 60% - sem dado em: qualidade, conveniencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

## Cortados pelos gates

- Clonazepam gotas 2,5 mg/mL, 20 mL (Generico): produto descartado (Decisao do Josemar em 04/11: quer o medicamento de marca de referencia (Rivotril), nao o generico.)

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
