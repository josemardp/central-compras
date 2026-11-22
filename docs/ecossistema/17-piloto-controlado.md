# 17. Piloto controlado dos alertas reais

O radar tem três modos, sem ambiguidade. Hoje ele está em **SOMBRA**.

| Modo | Como fica a configuração | O que faz |
|---|---|---|
| **SOMBRA** | `alertas.enviar: false` (ou `homologado_em` vazio) | coleta, reconhece, confere a loja, classifica, prioriza e **simula**. Nada é enviado |
| **PILOTO** | `alertas.enviar: true` + `homologado_em` preenchido + `piloto.ativo: true` | envia **só** o que passar em todas as barreiras abaixo, com limites bem menores |
| **COMPLETO** | `enviar: true` + `homologado_em` + `piloto.ativo: false` | política de prioridade inteira (6 comuns, 3 críticos, 2 de exceção). Só depois de o piloto dar certo |

Ver o modo atual e o que o piloto está fazendo: `python -m radar piloto` (e `python -m radar status`).

## Barreiras do piloto (todas obrigatórias)

Cada oferta só vira mensagem se passar em **todas**. O que não passa fica registrado como `nao_selecionado` com o motivo, visível em `radar prioridade` e `radar piloto`.

1. **Produto exato** da lista `piloto.produtos_exatos` (os 11 produtos do catálogo em reais; o Xiaomi S40 Pro do Paraguai, em dólar, fica de fora).
2. **Nenhum aviso**: nada de voltagem não informada, SKU não confirmado, nome alternativo, importado, hora incerta, nem **preço que depende de cupom não confirmado**.
3. **Confiança mínima MÉDIA**, exibida na mensagem junto com a razão. BAIXA nunca sai.
4. **Link da fonte** presente.
5. **Fonte revalidada no momento do envio** (a oferta ainda está ativa). No piloto isso vale sempre, não só para quem esperou.
6. **Destinatário confirmado por você** (`piloto.destinatario_confirmado_em`). Enquanto estiver vazio, o piloto não envia nada.

## Limites conservadores

| Parâmetro | Piloto | Política completa |
|---|---|---|
| alertas comuns por dia | **2** | 6 |
| alertas críticos por dia | **1** | 3 |
| alertas de exceção por dia | **0** | 2 |
| por varredura (10 min) | **1 no TOTAL**, de qualquer categoria (o crítico tem preferência; o comum espera o próximo ciclo) | 2 comuns e 1 crítico, por categoria |
| mesmo produto de novo | só após **4 h**, ou melhora de **7%**, ou queda de **3% com R$ 100 ou mais** de economia | 90 min ou 5% |

Quando o orçamento acaba, o que sobrar fica `retida_orcamento` (visível, não some).

## Como o preço aparece na mensagem

Três níveis que nunca se misturam:

- **Preço anunciado** (a fonte). Pode já embutir um cupom: nesse caso o cupom aparece como "já embutido no preço anunciado; NÃO confirmado no carrinho" e **nunca é descontado de novo**.
- **Confirmado na loja** (só lojas com consulta pública: WebContinental e FrioPeças). É o preço da loja **sem cupom**. Se a loja cobra mais que o anunciado e há cupom, o preço depende do cupom: a confiança fica MÉDIA e, no piloto, a oferta **não** é enviada (aviso bloqueante) até você validar o cupom no carrinho (`radar validar`).
- **Entregue (com frete)**: sempre "não confirmado". Frete e prazo dependem do seu CEP e só o carrinho sabe. O radar não usa CEP.

## O que já está comprovado e o risco residual

**Comprovado** (com evidência):
- caminho completo em sombra com 1 oferta real (Philco 18k): coleta, reconhecimento, conferência na fonte e na loja, preço x cupom, prioridade e despacho. A conferência achou que os R$ 2.379 anunciados já embutem o PHI200 (loja R$ 2.579) e que sem o cupom não é oferta;
- 12 de 12 relatórios reais entregues no WhatsApp na primeira tentativa em 20 e 21/11, sem retentativa nem fila;
- política de prioridade, fila, expiração e kill switch em simulação (8 situações) e ensaio dedicado;
- 0 falsos positivos em 96 negativos reais independentes.

**Risco residual de liberar o piloto**:
1. A amostra ao vivo é mínima: 1 oferta real em ~8.500 publicações. Não mede recall nem taxa de falso positivo em mercado.
2. A entrega foi medida **uma vez** (teste de 21/11: 15,6 s para 1 mensagem de 1.250 caracteres, confirmação do mecanismo de envio, não leitura no aparelho). Amostra de 1.
3. Só duas lojas permitem conferir o preço na loja; nas outras a confiança máxima é MÉDIA.
4. Um alerta pode chegar com a promoção já no fim (a mediana de atraso do Promobit é ~7,5 min).
5. O destino do WhatsApp só é confirmado por você.

O piloto limita o dano: no pior caso, 2 alertas por dia, de produto exato, sem aviso, com a fonte revalidada no envio.

## Repetição entre fontes, limites de 3% e 7% e reavaliação (corrigido em 22/11/2026)

Testes: `tests/test_radar_dedup_entre_fontes.py` (deduplicação entre fontes, 20 testes) e `tests/test_radar_repeticao_melhora_relevante.py` (regra nova e reavaliação, 27 testes). Banco temporário, nenhum envio real.

**A mesma oferta em várias fontes (Pelando site, Pelando Telegram, Promobit) não gera notificação duplicada.** Quatro camadas:
1. **No mesmo ciclo:** só a melhor oferta de cada produto segue; as outras viram `substituido`.
2. **Porta de 24 h** (`alertas.gates`): chave `produto + loja + vendedor`, sem a fonte. Libera de novo só com queda de pelo menos **3%**, cupom novo ou cupom validado.
3. **Anti-repetição do produto** (despachante): olha só o produto. No piloto: **240 min**, ou queda de **7%**, ou a exceção abaixo.
4. **Travas do piloto:** 1 alerta por varredura no total e 2 comuns + 1 crítico por dia.

**Regra nova do piloto (`piloto.queda_extra_pct: 3` e `piloto.queda_extra_reais: 100`):** dentro dos 240 min, um novo alerta do mesmo produto também sai quando o preço cai **pelo menos 3% E pelo menos R$ 100** sobre o último preço alertado, com preço comparável (mesma loja, ou loja desconhecida de um dos lados). Produto exato, sem avisos, fonte revalidada, orçamento e limite por varredura continuam valendo. Mesmo preço de outra fonte não tem queda e não libera nada. A política completa não muda (a regra só liga no piloto). Exemplos: de R$ 3.300 para R$ 3.201 (R$ 99) segue suprimido; para R$ 3.200 (R$ 100) alerta. De R$ 1.700 para R$ 1.598 (6%, R$ 102) alerta; para R$ 1.632 (4%, R$ 68) segue suprimido.

**Reavaliação do candidato suprimido:** a oferta suprimida por repetição que continua no ar **sem mudar de preço** não é mais descartada como `sem_mudanca_desde_a_ultima_vez`. Quando a janela do produto acaba (240 min no piloto, 90 min na completa), ela vira um novo candidato e passa de novo por tudo: porta de 24 h (3%), revalidação na fonte, orçamento, limite por varredura e anti-repetição. Reavalia **uma vez por janela**. Oferta velha demais (mais de 6 h), encerrada na fonte ou fora da lista da fonte não gera alerta retroativo.

**Dois defeitos achados e corrigidos no caminho:**
- **Porta de 24 h inoperante com loja conhecida.** O despachante registrava o alerta enviado com loja e vendedor vazios, mas a porta procura o alerta anterior pela família com a loja da oferta. Com loja conhecida ela nunca achava nada, e só a janela de 240 min segurava repetições. Agora o alerta é registrado com a loja e o vendedor da oferta. Efeito visível: uma queda pequena (por exemplo 1,8%) é barrada na porta de 24 h, e não mais como `suprimido_repeticao`; os alertas enviados são os mesmos.
- **Borda dos 7%.** Uma queda de exatamente 7,00% (R$ 1.000 para R$ 930) não liberava, por erro de arredondamento de ponto flutuante. A comparação agora é feita em reais, com a borda inclusiva.

**Lacunas que continuam (não alteradas):**
- **Pelando e Telegram agora podem gerar alerta** (ver a seção abaixo), desde que a loja da oferta seja verificável (WebContinental e FrioPeças). Antes de 22/11/2026 a revalidação só existia para Promobit e Gatry e essas ofertas expiravam.
- **Porta de 24 h e oferta sem loja.** Uma oferta sem loja (o Telegram) não casa com o alerta de uma loja nessa porta. No piloto real isso não vaza, pelo motivo acima.
- **Nenhuma fonte informa o vendedor** (todas deixam vazio), então a família é `produto + loja`. Grafias diferentes da mesma loja entre fontes não se casam.

## Revalidação na loja, independente da fonte de descoberta (22/11/2026)

**Problema:** o piloto revalida a oferta antes de enviar, mas só Promobit e Gatry sabiam se revalidar. Uma oferta descoberta só no Telegram ou no Pelando virava `expirado: fonte ... nao permite revalidar` e nunca alertava. Pior: uma postagem ainda acessível não prova que o desconto continua valendo.

**Como funciona agora** (`lojas.revalidar_na_loja`, chamada por `varredura.revalidar_oferta`): a oportunidade é conferida **direto na API pública da loja**, sem seguir o link da postagem (que passa pelo rastreador do afiliado) e sem comprar nada.
1. **Loja:** a da fonte; se a fonte não informa (o Telegram nunca informa), a loja **configurada** citada no texto ou no domínio do link direto. Link encurtado ou de afiliado (`pelando.promo`, `link.amazon`, `meli.la`) nunca é resolvido.
2. **Produto exato:** busca pelo SKU do catálogo e confere modelo e voltagem pelo nome que a loja devolve.
3. **Vendedor:** só estoque **próprio** conta (vendedor terceiro do marketplace é ignorado).
4. **Disponibilidade e preço:** em estoque e com preço que cobre o prometido pelo alerta.
5. **Cupom:** quando o preço prometido depende de cupom, a **simulação do carrinho** da loja diz se o cupom é aceito e quanto o carrinho cobra com ele. É a mesma API de checkout que o site usa, sem login, sem CEP, sem forma de pagamento e sem criar pedido.

**Quatro resultados, em três estados para o despachante:**

| Resultado | Estado | O que acontece com o candidato |
|---|---|---|
| `confirmada` | `True` | segue para as barreiras e o orçamento do piloto |
| `encerrada` (sem estoque, produto ou vendedor próprio ausente) | `False` | `expirado`, com o motivo |
| `divergente` (preço diferente no carrinho, cupom inválido ou sem efeito) | `False` | `expirado`, com o motivo |
| `pendente` (loja sem API pública, fora do ar, sem loja identificada) | `None` | fica `pendente` e é reconferido a cada ciclo; ao vencer a validade vira `nao_confirmada` (**nunca** `expirado`, não é prova de que a oferta acabou) |

Uma oferta pendente **não inventa preço confirmado** (a mensagem do candidato diz "Confirmado na loja: não") e **não engole** outra oferta confirmável do mesmo produto: a revalidação agora acontece **antes** de escolher o melhor candidato do produto.

**Cobertura real (sondada em 22/11/2026):** só **WebContinental e FrioPeças** têm API pública utilizável. Dufrio (404), Casas Bahia (devolve página), Fast Shop (503), KaBuM (DNS não resolve) e Mercado Livre (403) não servem; Amazon e Magalu não têm API pública. Ofertas dessas lojas ficam `pendente`. Para acrescentar uma loja VTEX que responda, basta uma entrada em `config/radar_lojas.yaml` (`tipo: vtex`, `base`, `vendedor_contem`, `nome`, `simula_carrinho`).

**Promobit e Gatry:** continuam validando a publicação; agora a loja também tem voz. Publicação encerrada manda mais que a loja. Publicação ativa com loja divergente **não alerta**. Publicação ativa com loja não verificável segue como antes. Se a página da fonte não abre (falha de rede), o resultado é `pendente`, e não mais "encerrada".

**Limites da simulação:** sem CEP e sem forma de pagamento, o carrinho pode não mostrar desconto que só aparece no checkout (por exemplo, cupom restrito a PIX ou a cartão). Por isso a **validação manual** (`radar validar`, o que você viu no SEU carrinho) vale enquanto o preço não piorar mais de 2%, **só para divergência de preço ou cupom**. Ela nunca vence "encerrada".

**Resultado real de 22/11 (13:55):** oferta #232, Philco 18k anunciado R$ 2.379 com o cupom **PHI200** na WebContinental. A loja vende o produto exato, do vendedor próprio e em estoque, por R$ 2.579, e o carrinho **aceita o PHI200 mas não reduz o preço** (R$ 2.579 com e sem cupom). Resultado: `divergente`, e o alerta não sai. É o comportamento certo para não transformar publicação de cupom em falso desconto.

**O que não mudou:** os limites do piloto (2 comuns + 1 crítico por dia, 1 por varredura), as barreiras (produto exato, sem avisos, confiança mínima MEDIA, destinatário confirmado), os agendamentos e a ativação local.

## Primeiros envios: o que olhar

```
python -m radar piloto          # modo, limites, o que ficou fora, envios (ok e falhas)
python -m radar prioridade      # candidatos e motivos
python -m radar latencia        # latência medida dos envios
```

Para cada alerta recebido: o produto é exatamente esse? a voltagem? a oferta ainda existe? o preço bate? Se **2 falsos positivos em 24 h**, ou o mesmo padrão 2 vezes, desligue:

```
python -m radar ativacao --desligar
```

Isso grava `enviar: false` e `homologado_em: null` e **descarta na hora os alertas que esperavam na fila**. Os relatórios 08/14/20h não são tocados.

## Passar de piloto para completo

Só depois de pelo menos 3 dias de piloto sem falso positivo recorrente: troque `piloto.ativo` para `false`. Para voltar ao piloto, `true`.
