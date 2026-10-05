# Guia do especialista: ar_condicionado

Conhecimento tecnico reaproveitavel desta categoria. Cresce a cada compra:
o que decidiu, o que era marketing, o que faltou. Fato de datasheet/norma e
inferencia ficam separados; valor nao confirmado leva [VERIFICAR].

## Perguntas que decidem

| Pergunta | Padrao se nao houver resposta | O que muda |
|---|---|---|
| Area do comodo, sol da tarde, quantas pessoas | Quarto ate 18 m2 -> 12.000 BTU | Sala, sol forte ou 3+ pessoas pode pedir 18.000 |
| So frio ou quente e frio | So frio no interior de SP | Quente/frio custa R$ 200 a 300 a mais |
| Ja existe ponto 220V e instalador? Ele e credenciado da marca? | Instalador local a parte | Garantia estendida (2 a 5 anos) das grandes marcas exige credenciado |
| Distancia entre unidades | Ate 7,5 m | Acima do comprimento sem recarga precisa gas extra |
| Cidade de entrega | - | Frete varia R$ 0 a 170 entre vendedores da Amazon |

## Especificacoes que importam

| Atributo | Faixa de entrada | Faixa boa | Como ler no anuncio/datasheet |
|---|---|---|---|
| IDRS (etiqueta INMETRO) | 7,0 Wh/Wh (classe A em 2026 [VERIFICAR]) | >= 7,5 | Ficha da Frigelar traz o campo "IDRS"; na Amazon raramente aparece |
| Consumo anual | ~415 kWh/ano | <= 385 kWh/ano | Campo "Consumo Aproximado"; Amazon ja mostrou "3,52 kWh/ano" (erro de cadastro) |
| Garantia | 24 meses + 10 anos compressor | 60 meses + 10 anos compressor (Gree) | Vale so com instalador credenciado; leia o texto da garantia |
| Gas e serpentina | R-32, cobre | R-32, cobre | Ficha tecnica |

## Marketing que pode ignorar

- "AI", "Voice", "WindFree": conforto ou conveniencia, nao mudam eficiencia nem durabilidade.
- "Ate 70% de economia": comparado a aparelho sem inverter; entre inverters o que vale e o IDRS.
- Selo Procel/"classe A" sem o numero do IDRS: a classe A de 2026 vai de 7,0 para cima, e 7,0 a 7,7 ja muda ~10% de consumo.

## Armadilhas e incompatibilidades

- Mesmo nome comercial, sufixo diferente: LG S3-Q12JA31J (IDRS 7,7, 377 kWh) e S3-Q12JA31L (~415 kWh) sao "Dual Inverter Voice +AI" e gastam diferente. Confira o sufixo.
- LG "AI Smart Inverter" (S3-Q12JA31E) e linha de entrada, classe B. Nao confundir com Dual Inverter.
- Frete e prazo da Amazon mudam com o CEP da conta: cote com o CEP de entrega real.
- Mercado Livre: busca pelo codigo do modelo traz anuncios de "apenas condensadora" ou "apenas evaporadora" com preco de aparelho pela metade. Confira o titulo inteiro.
- Na Amazon, veja todas as ofertas do anuncio: o vendedor mais barato pode ter 53 a 61% de avaliacoes positivas, e outro com 88 a 94% sai por poucos reais a mais.
- Frigelar nao mostra avaliacoes por produto (todas "seja o primeiro"); serve de referencia de ficha tecnica e preco PIX.

## Acessorios

| Acessorio | Necessidade | Especificacao tecnica | Quando vale |
|---|---|---|---|
| Kit de instalacao | obrigatorio | Cobre 1/4" e 3/8" (12.000 BTU), isolamento, cabo PP, dreno | Sempre; geralmente o instalador fornece |
| Suporte condensadora | obrigatorio | Para >= 25 kg | Quando nao vai no piso |
| Disjuntor bipolar dedicado | obrigatorio | Pela corrente da ficha e bitola do cabo | Sempre |

## Historico

| Data | Projeto | O que este projeto ensinou |
|---|---|---|
| 2026-10-05 | 2026-ar-condicionado-split-12000-btu-irmao | Amazon (Chrome logado) foi mais barata que Frigelar; fichas tecnicas completas so na Frigelar |
