# Ranking

Gerado em 2026-09-02T01:29:08.

## Elegiveis

1. Viapol Viaplus 1000 18 kg - 73.3
   qualidade 0.81 · valor 1.00 · risco 0.29 · aderencia -- · conveniencia --
   custo total R$ 192,90 / Elos Cimento / estimativa web
   confianca 75% - sem dado em: conveniencia, aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.
   alertas: AVAL_SUSPEITA

2. Impermeabilizante Block Total Decor Colors - 47.8
   qualidade -- · valor 0.51 · risco 0.44 · aderencia -- · conveniencia --
   custo total R$ 379,99 / Loja Decor Colors / estimativa web
   confianca 45% - sem dado em: qualidade, conveniencia, aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

3. Sika SikaTop 107 Cinza 18 kg - 33.3
   qualidade -- · valor 0.25 · risco 0.44 · aderencia -- · conveniencia --
   custo total R$ 779,70 / Superpro Atacado / estimativa web
   confianca 45% - sem dado em: qualidade, conveniencia, aderencia. Esses eixos ficaram FORA da conta; o score mede so o que se sabe.

## Cortados pelos gates

- Sika Igolflex Fachada Branco 3,6 L: produto descartado (Mesma limitacao do Vedapren: pintura acrilica para fachada, pressao positiva. A propria Sika separa a linha Igolflex Fachada da linha SikaTop, que e a indicada para negativa.)
- Vedacit Vedapren Parede Branco 3,6 kg: produto descartado (Membrana acrilica de face positiva. Nao resiste a contrapressao: descola sob umidade negativa. A ficha do fabricante posiciona o produto contra batida de chuva na fachada, nao contra agua empurrando por tras.)

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
