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
| mesmo produto de novo | só após **4 h** ou melhora de **7%** | 90 min ou 5% |

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
