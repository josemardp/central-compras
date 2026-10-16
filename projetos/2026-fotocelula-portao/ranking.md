# Ranking

Gerado em 2026-10-16T13:27:17.

## Elegiveis

Nenhum candidato passou pelos gates.
## Cortados pelos gates

- Fotocelula refletiva PPA F10-R: avaliacoes insuficientes (2 < 20) alertas: AVAL_SUSPEITA
- Fotocelula de barreira PPA F30 (emissor + receptor): produto descartado (Pedido de 16/10 cancelado (junto com a base): F30 e de barreira e exige fio dos dois lados do portao; o modelo escolhido e a F10-R refletiva); avaliacoes insuficientes (4 < 20) alertas: AVAL_SUSPEITA

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
