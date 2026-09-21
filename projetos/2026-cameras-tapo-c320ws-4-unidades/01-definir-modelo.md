# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

Comprar mais 4 cameras Tapo C320WS, o mesmo modelo das 2 ja compradas em 16/09, para o Fabio instalar 6 no total no muro de casa.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: 2 Tapo C320WS ja compradas em 16/09 (Loja Oficial TP-Link no Mercado Livre, R$ 309,90 cada, 2 anos de garantia); casa em 127V; celular S20 FE com app Tapo; clima de sol forte e chuva de verao.
- Perguntas decisivas respondidas: 6 cameras no total, todas C320WS (Josemar, 21/09); Josemar compra o material.
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): preco teto de R$ 1.300 para as 4 (referencia: R$ 309,90 pagos em 16/09 x 4 = R$ 1.239,60).

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Modelo | Tapo C320WS | Tapo C320WS, mesma versao de hardware das 2 compradas | um app, mesma fonte, mesma caixinha e mesmo cartao para as 6 |
| Resolucao | 2K 4MP | 2K 4MP | igual as ja compradas |
| Protecao | IP66 | IP66 | fica no muro, sol e chuva |
| Conexao | Wi-Fi 2,4 GHz + porta de rede RJ45 | idem | sem PoE; cabo de rede so onde o Wi-Fi nao chegar |
| Alimentacao | fonte 9V 0,6A inclusa | idem | a caixinha e dimensionada para essa fonte |
| Garantia | nacional | nacional 2 anos | mesma condicao da compra de 16/09 |
| Vendedor | oficial | Loja Oficial TP-Link ou vendido pela propria Amazon/ML | evita versao importada sem garantia |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Cartao microSD 128 GB High Endurance (6 un) | obrigatorio | ver projeto dos cartoes | grava sem assinatura | projeto: 2026-cartoes-microsd-128gb-cameras |
| Caixa de passagem externa (6 un) | obrigatorio | IP65 ou mais, cabe a fonte 9V plugada | protege fonte e emendas no muro | projeto: 2026-caixas-de-passagem-cameras |
| Cabo PP 3x1,5 mm2 (50 m) | obrigatorio | ver projeto do cabo | leva 127V ate cada caixinha | projeto: 2026-cabo-pp-3x1-5-50m |
| Plugue femea 2P+T 10A (6 un) | obrigatorio | padrao NBR 14136, 10A | liga a fonte original na ponta do cabo, sem cortar a fonte [VERIFICAR com Fabio como ele liga] | junto com o cabo |
| Conector de emenda tipo alavanca (~12 un) | recomendado | 3 vias, ate 2,5 mm2 | deriva o cabo principal para cada caixinha sem fita | junto com o cabo |
| Nobreak ~600 VA 127V | recomendado | alimenta roteador + circuito das cameras | cameras seguem gravando se cortarem a luz (estimativa 2 a 3 h) | decisao pendente do Josemar |
| Cabo de rede Cat6 externo | recomendado so onde o Wi-Fi nao chegar | UTP Cat6 com cobertura para area externa | a C320WS aceita cabo; testar o sinal em cada ponto antes de fixar | decisao depois do teste de sinal |
| Assinatura Tapo Care | dispensavel | - | o cartao ja grava local; nuvem so se quiser copia fora de casa | - |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: Tapo C320WS (4 unidades).
- Alternativas descartadas: outros modelos Tapo/Intelbras.
- Motivo: padronizar as 6 cameras com as 2 ja compradas.

## Requisitos gerados

### Obrigatorios

- Tapo C320WS nova, lacrada, garantia nacional
- 4 unidades

### Desejaveis

- Loja oficial com frete Full/Prime
- Parcelamento sem juros

### Deal-breakers

- Versao importada/sem garantia nacional
- Vendedor terceiro sem reputacao
