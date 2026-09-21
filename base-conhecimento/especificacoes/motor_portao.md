# Guia do especialista: motor_portao

Conhecimento tecnico reaproveitavel desta categoria. Cresce a cada compra.
Fato de datasheet/anuncio e inferencia ficam separados; valor nao
confirmado leva [VERIFICAR].

## Perguntas que decidem

| Pergunta | Padrao se nao houver resposta | O que muda |
|---|---|---|
| Portao de correr, basculante ou pivotante? | de correr (deslizante) | tipo de motor inteiro |
| Peso e comprimento do portao? | instalador avalia | capacidade (kg) e metros de cremalheira |
| Qual tensao no ponto do motor? | 127V | so importa se o motor nao for bivolt |
| Quantas pessoas abrem o portao? | 2 | controles extras |
| Quem instala e qual marca ele atende? | marca do instalador | manutencao e garantia de instalacao |

## Especificacoes que importam

| Atributo | Faixa de entrada | Faixa boa | Como ler no anuncio/datasheet |
|---|---|---|---|
| Capacidade | igual ao peso do portao | peso do portao + folga | "portoes ate X kg" |
| Tensao | 127 ou 220 fixo | bivolt (motor e central) | PPA DZ Rio Jetflex: bivolt (anuncios, 09/2026) |
| Ciclos por hora | 20 | 40 ou mais | uso residencial diario fica bem abaixo |
| Central | com entrada para fotocelula | + modulo de trava/luz de garagem | ex.: PPA Triflex |
| Cremalheira no kit | 0 m | 3 m | muda o que comprar a parte |

## Marketing que pode ignorar

- "Potencia" (1/4 x 1/3 CV) como argumento isolado: a capacidade em kg e o que decide. O mesmo DZ Rio 500 Jetflex aparece como 1/4 e como 1/3 em lojas diferentes.

## Armadilhas e incompatibilidades

- Portao pesado de empurrar na mao (roldana/trilho gastos) queima motor: revisar antes de instalar.
- Completar cremalheira com modelo diferente do kit: o passo do dente pode nao bater na emenda.
- Kit "sem cremalheira" e "com 3 m" tem o mesmo nome em muitas lojas: conferir o conteudo do kit.

## Acessorios

| Acessorio | Necessidade | Especificacao tecnica | Quando vale |
|---|---|---|---|
| Cremalheira | obrigatorio | nylon com alma de aco, M4, compativel com a engrenagem (PPA DZ: Z18) | sempre |
| Base regulavel | obrigatorio | aco zincado, furacao do motor | sempre |
| Fotocelula | recomendado (forte) | par infravermelho compativel com a central | crianca, pedestre ou carro passando |
| DPS + disjuntor proprio | recomendado | conforme o circuito | regiao com tempestade; central com inversor |
| Controles extras | depende | mesma frequencia/protocolo (PPA: 433,92 MHz rolling code) | um por motorista |
| Nobreak de motor | dispensavel | - | destravamento manual resolve falta de luz |

## Historico

| Data | Projeto | O que este projeto ensinou |
|---|---|---|
| 2026-09-21 | 2026-motor-portao-deslizante | primeira compra; lista do instalador revisada pelo especialista |
