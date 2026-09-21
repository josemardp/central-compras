# Ranking

Gerado em 2026-09-21T15:07:55.

## Elegiveis

1. Polissonografia Tipo I - Hospital CEMA SP - 73.1
   qualidade -- · valor 1.00 · risco 0.40 · aderencia --
   custo total R$ 800,00 / Hospital CEMA / estimativa web
   confianca 50% - sem dado em: qualidade, conveniencia, aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

2. Polissonografia Tipo I - Instituto do Sono Aracatuba - 69.8
   qualidade -- · valor 0.94 · risco 0.40 · aderencia --
   custo total R$ 850,00 / Instituto do Sono Aracatuba / estimativa web
   confianca 50% - sem dado em: qualidade, conveniencia, aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

3. Polissonografia Tipo I - Fleury SP - 54.6
   qualidade -- · valor 0.67 · risco 0.40 · aderencia --
   custo total R$ 1.200,00 / Grupo Fleury / estimativa web
   confianca 50% - sem dado em: qualidade, conveniencia, aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

4. Polissonografia Tipo I - Instituto do Sono SP - 43.7
   qualidade -- · valor 0.47 · risco 0.40 · aderencia --
   custo total R$ 1.700,00 / Instituto do Sono SP / confirmada manualmente
   confianca 50% - sem dado em: qualidade, conveniencia, aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

## Cortados pelos gates

- Polissonografia Domiciliar Tipo III - Clinica Fontanelli Aracatuba: produto descartado (descartado: usuario determinou realizar exclusivamente Polissonografia Tipo I (laboratorio completo); Tipo III descartada)
- Polissonografia Domiciliar Tipo III - Delboni Auriemo SP: produto descartado (descartado: usuario determinou realizar exclusivamente Polissonografia Tipo I (laboratorio completo); Tipo III descartada)

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
