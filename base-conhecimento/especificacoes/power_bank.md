# Guia do especialista: power_bank

Conhecimento tecnico reaproveitavel desta categoria. Cresce a cada compra:
o que decidiu, o que era marketing, o que faltou. Fato de datasheet/norma e
inferencia ficam separados; valor nao confirmado leva [VERIFICAR].

## Perguntas que decidem

| Pergunta | Padrao se nao houver resposta | O que muda |
|---|---|---|
| Qual aparelho e qual protocolo de carga rapida ele usa? | celular do perfil (S20 FE: PD 3.0 + PPS 25W) | protocolo obrigatorio na porta USB-C |
| Precisa carregar notebook? | nao | 65W+ e outra faixa de preco |
| Bolso ou bolsa? | bolsa | 20.000 mAh (~350-450 g) x 10.000 mAh (~200 g) |

## Especificacoes que importam

| Atributo | Faixa de entrada | Faixa boa | Como ler no anuncio/datasheet |
|---|---|---|---|
| Protocolo para Samsung | PD 3.0 + PPS 25W | PPS 3,3/5-11V ate 3A | procurar a linha "PPS: x-yV z A" na tabela de saida; so "22,5W PD/QC" nao basta |
| Potencia USB-C | 25W | 30W | acima de 30W o S20 FE nao aproveita |
| Entrada | 18-20W | 30W | tempo para recarregar a propria bateria |
| Capacidade | 20.000 mAh (74 Wh) | 20.000 mAh | ~60-65% vira carga util no celular [inferencia] |
| Peso | ate 450 g | ~350 g | ficha ou review (anuncio as vezes traz tabela generica da linha) |

## Marketing que pode ignorar

- "22,5W" com SCP/FCP (protocolos Huawei): nao acelera Samsung.
- "45W" e "65W" para celular que so puxa 25W.
- "100.000 mAh" e capacidades absurdas: falsificacao.

## Mercado brasileiro (observado em 09/10/2026, Amazon)

- Baseus Bipow2 Pro 22,5W: R$ 188,94 (Baseus Oficial). Ficha: USB-C 5V/2,4A, 9V/2,22A, 12V/1,5A, 10V/2,25A SCP. Sem PPS.
- Anker Zolo 20K A1689 (30W): R$ 265,03 na AnkerDirect BR. Titulo do anuncio diz 45W, ficha diz A1689. PPS 5-11V/2,75A segundo ficha de revendedor do Vietna, nao confirmado pela Anker. Review alemao (techtest.org) aponta aquecimento.
- Samsung EB-P4520 45W: R$ 269,10, so com vendedor terceiro na Amazon (risco de falsificado).
- Basike (marca de marketplace) 20.000 mAh 45W: ~R$ 195, vendedor terceiro; PPS nao aparece no anuncio do modelo C10.
- KaBuM: so marketplace e mais caro nesta categoria.

## Armadilhas e incompatibilidades

- Anuncio da Amazon mistura modelos: titulo, ficha e tabela comparativa podem falar de produtos diferentes da mesma linha. Conferir o numero do modelo.
- Cabo USB-A para USB-C nao faz PD/PPS: carga rapida Samsung exige cabo C-C.

## Acessorios

| Acessorio | Necessidade | Especificacao tecnica | Quando vale |
|---|---|---|---|
| Cabo USB-C/USB-C | obrigatorio se nao vier embutido | 3A (60W) | sempre que o modelo nao tiver cabo integrado |

## Historico

| Data | Projeto | O que este projeto ensinou |
|---|---|---|
| 2026-10-09 | 2026-power-bank-20000mah | primeira compra: para Samsung o PPS decide, nao a potencia nominal |
