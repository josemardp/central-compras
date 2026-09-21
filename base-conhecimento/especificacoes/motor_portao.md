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

## Conta rapida de peso (estimativa, nao medida)

- Area do portao x peso por m2: gradil/tubular de ferro ~10-20 kg/m2; fechado em chapa ~20-35 kg/m2.
- Portao 4 x 2 m (8 m2): ~80-160 kg gradil; ~160-280 kg chapa. Classe 500 kg sobra; 800 kg (1/2 CV) so para portao muito pesado.

## O que o manual tecnico PPA DZ Rio exige (P08665 REV1, lido em 21/09/2026)

- DR de 30 mA e aterramento obrigatorios; disjuntor de 5 A (no mercado: 6 A bipolar curva C).
- Cabo de alimentacao minimo: flexivel 3 x 0,75 mm2 500V (NBR NM 247-5). PP 3 x 1,5 sobra.
- Eletroduto 3/4" ate o motor; 1/2" para fotocelula e botoeira.
- Roldanas de no minimo 120 mm; trilho de secao circular (cantoneira gasta mais); portao tem que correr leve na mao.
- Fixacao: parafusos S 1/4" x 2 1/2" em piso firme e nivelado; senao base de concreto a ~20 mm da face do portao. Base metalica regulavel (Base Flex PPA, 80-150 mm) e alternativa sem alvenaria.
- Folga de ~2 mm entre o topo do dente da engrenagem e o fundo do dente da cremalheira; cremalheira fixada a cada 300-400 mm.
- "Dimensao max. do portao 2,5 x 3,0 m" aparece IGUAL do DZ Rio 350 ao R800: e referencia (velocidade tambem e medida "em 3 metros"), nao limite de forca. Portao de 4 m: preferir engrenagem Z14 (mais torque) e ajustar desaceleracao.
- Velocidade oficial: Z14 = 33 m/min; Z18 = 42,9 m/min. Anuncio que promete mais do que isso esta errado.
- Central Jetflex tem inversor de frequencia: DR tipo A e o indicado (inferencia tecnica, nao exigencia do manual).

## Marketing que pode ignorar

- "Potencia" (1/4 x 1/3 CV) como argumento isolado: a capacidade em kg e o que decide. O mesmo DZ Rio 500 Jetflex aparece como 1/4 e como 1/3 em lojas diferentes.

## Armadilhas e incompatibilidades

- Portao pesado de empurrar na mao (roldana/trilho gastos) queima motor: revisar antes de instalar.
- Completar cremalheira com modelo diferente do kit: o passo do dente pode nao bater na emenda.
- Kit "sem cremalheira" e "com 3 m" tem o mesmo nome em muitas lojas: conferir o conteudo do kit.
- Versao "R800 / 800 kg" (Z14) as vezes sai MAIS BARATA que a de 500 kg em kit completo: comparar kit a kit, nao por capacidade.
- Cremalheira "Gold" tem variante modulo 6 (industrial) que nao encaixa no DZ Rio (modulo 4).
- Sites-espelho de anuncios do Mercado Livre (gooseguardian, megsegurancaeletronica) com certificado invalido: nunca comprar por eles.

## Acessorios

| Acessorio | Necessidade | Especificacao tecnica | Quando vale |
|---|---|---|---|
| Cremalheira | obrigatorio | nylon com alma de aco, M4, compativel com a engrenagem (PPA DZ: Z18) | sempre |
| Base regulavel | obrigatorio | aco zincado, furacao do motor | sempre |
| Fotocelula | recomendado (forte) | refletiva (fio so de um lado; PPA F10-R para Triflex) ou par emissor-receptor | crianca, pedestre ou carro passando |
| DR 30 mA tipo A | obrigatorio (manual) | 2P 25 A 30 mA tipo A (ex.: Steck SDR22530A) | sempre; sai se o quadro ja tiver DR geral de 30 mA |
| DPS + disjuntor proprio | recomendado | 220V fase-fase: disjuntor bipolar + 1 DPS por fase (Uc para 127V fase-terra); fase-neutro: DPS 275V | regiao com tempestade; central com inversor |
| Controles extras | depende | mesma frequencia/protocolo (PPA: 433,92 MHz rolling code) | um por motorista |
| Nobreak de motor | dispensavel | - | destravamento manual resolve falta de luz |

## Historico

| Data | Projeto | O que este projeto ensinou |
|---|---|---|
| 2026-09-21 | 2026-motor-portao-deslizante | primeira compra; lista do instalador revisada; manual PPA trouxe DR, disjuntor 5 A, roldanas 120 mm; R800 Z14 kit 4 m + 3 controles R$ 915 (Amazon) |
