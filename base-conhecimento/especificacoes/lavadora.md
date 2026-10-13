# Guia do especialista: lavadora

Conhecimento tecnico reaproveitavel desta categoria. Cresce a cada compra:
o que decidiu, o que era marketing, o que faltou. Fato de datasheet/norma e
inferencia ficam separados; valor nao confirmado leva [VERIFICAR].

## Perguntas que decidem

| Pergunta | Padrao se nao houver resposta | O que muda |
|---|---|---|
| Tensao da tomada da lavanderia | 127V (perfil) | lavadora nao e bivolt: 127V e 220V sao produtos (e anuncios) diferentes |
| So lava ou lava e seca | so lava, abertura superior | lava e seca e frontal, custa o dobro ou mais e gasta mais energia |
| Espaco disponivel | [VERIFICAR medir] | largura, profundidade e altura livre acima (a tampa abre para cima) |
| Teto com frete | - | define se entram os modelos com cesto inox e painel digital |

## Especificacoes que importam

| Atributo | Faixa de entrada | Faixa boa | Como ler no anuncio/datasheet |
|---|---|---|---|
| Energia | classe A | A, ate 0,40 kWh/ciclo | selo INMETRO; Brastemp publica 0,36 "kWh/ano" so para 220V (unidade errada na ficha) |
| Agua | ate 150 L/ciclo | 140 L ou menos | ficha oficial; Electrolux LED13 150 L, LDA13 140 L, Brastemp BWK13AB 139 L (127V) |
| Centrifugacao | 600 rpm | 630 a 750 rpm | Electrolux 13 kg: 630 rpm; Brastemp so diz "Normal" |
| Cesto | polipropileno | inox | nome do modelo costuma dizer |
| Filtro de fiapos | presente | facil de limpar | LDA13 NAO tem (filtro flutuante vendido a parte, ficha oficial) |
| Garantia | 12 meses nacional | 12 meses + rede na regiao | todas as marcas grandes dao 12 meses; confirmar no anuncio |

## Marketing que pode ignorar

- Numero de programas (11, 12, 13): na pratica usa-se 3 ou 4.
- "De R$ X" na loja oficial: a LED13 aparecia "de R$ 2.839 por R$ 1.849" em 12/10/2026; ancora tipica.

## Armadilhas e incompatibilidades

- Anuncio da Amazon lista as versoes 127V e 220V como ASINs separados com o mesmo titulo: conferir a tensao no titulo antes de cotar.
- "110V" no anuncio = 127V.
- Anuncio de lavadora tem poucas avaliacoes (13 a 41 tipico, 12/10/2026): gate com minimo 10 e ancora bayesiana 50.
- Lavadora pesa ~40 kg: confirmar se a entrega leva ate o local de uso.
- Electrolux (manual G0051111 e guia rapido LED13/14/15/17): disjuntor EXCLUSIVO obrigatorio, 20A na fase em 127V; pressao 0,02 a 0,8 MPa (caixa d'agua 2,4 m acima da entrada); saida de agua entre 90 e 140 cm de altura, no maximo 20 cm dentro do esgoto, nunca emendar a mangueira; torneira 3/4" 14 fios.
- Altura com a tampa aberta (guia rapido): LED13 139 cm, LED15 143 cm. Conferir prateleira ou armario acima.
- Na mesma linha, capacidade maior gasta menos agua por kg: LED13 150 L/13 kg = 11,5 L/kg; LED15 160 L/15 kg = 10,7 L/kg. Energia por kg igual (0,031 kWh/kg).
- A loja Electrolux parcela em 10x sem juros pelo preco do Pix; a Amazon mostra o preco do Pix e cobra 5 a 7% a mais no cartao (12/10/2026).

## Acessorios

| Acessorio | Necessidade | Especificacao tecnica | Quando vale |
|---|---|---|---|
| Tomada 2P+T | obrigatorio se nao houver terra | NBR 14136, corrente do plugue (10A/20A) | ponto antigo sem terra |
| Torneira com bico | obrigatorio se nao houver | saida rosca 3/4" | ponto novo |
| Capa | recomendado | medida da maquina | area aberta, sol forte |
| Base com rodinhas | dispensavel | - | piora nivelamento [inferencia] |

## Historico

| Data | Projeto | O que este projeto ensinou |
|---|---|---|
| 2026-10-12 | 2026-maquina-de-lavar-13kg | primeira compra da categoria; mapa da linha 13 kg Electrolux (LED13, LDA13, LET13, LEM13 em estoque na loja oficial) |
