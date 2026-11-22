# 07. Alertas e cupons

Regras em `config/radar_regras.yaml` (limites) e `radar/cupons.py` (interpretação). Tudo determinístico; nenhuma IA decide preço.

## Interpretação de cupom

Extrai: código, loja, tipo (`percentual`, `fixo`, `frete`, `cashback`), valor, compra mínima, teto, restrições
(`primeira_compra`, `app`, `pix`, `selecionados`, `vendedor_especifico`, `categoria_limitada`), acumulação, validade, cashback e frete grátis.

| Texto | Resultado |
|---|---|
| `CASATECH10` "10% de desconto" | percentual 10 |
| `70OFF` "R$ 70 de desconto em compras acima de R$ 1.000, só na primeira compra pelo app" | fixo 70, mínimo 1.000, restrições primeira compra + app |
| `70OFF` sozinho | valor 70 **só como pista** (`valor_inferido`), nunca entra no cálculo |
| `25PRIMEBF` "em itens vendidos e entregues pela Amazon" | restrição `vendedor_especifico`: elegibilidade indeterminada, não aplica |
| `PRIMEIRA20BF` | exige primeira compra: não aplica enquanto `perfil_comprador.primeira_compra` for falso |
| "10% no Pix" / "no app" | restrições tratadas contra `perfil_comprador` |
| `ACESSEEGANHE`, `APLIQUENOLINK`, `RESGATENOLINK`, "cupom funcionando" | ignorados (não são código) |
| `K800`, `220V`, `12X`, SKUs do catálogo | ignorados (não são código) |

**Preço final entregue** = preço anunciado - desconto efetivamente elegível + frete obrigatório. Só aplica se o cupom está `PROVAVEL` ou `VALIDADO`,
tem valor confirmado, atende compra mínima e a elegibilidade é verdadeira. Vários cupons: escolhe **um**, o de menor preço final; não soma (acumulação não é presumida). Cashback é informado à parte.

## Estados

| Estado | Como se chega |
|---|---|
| `VALIDADO` | somente confirmação explícita: `python -m radar validar <id> --por "carrinho Amazon 21/11"` |
| `PROVAVEL` | evidência recente (até 6 h) de funcionamento nos textos/comentários, ou verificação recente pela própria fonte |
| `NAO_CONFIRMADO` | padrão: publicação não prova que o desconto funciona |
| `EXPIRADO` | validade vencida ou sinais de que parou ("expirou", "não funciona", ...) em maioria nos comentários |

Limitação declarada: a validação automática por simulação de carrinho **não foi implementada** (exige login e arrisca estado da conta); `VALIDADO` é manual.

## Classificação

| Classe | Condição (padrão) |
|---|---|
| CRÍTICA | preço final no mínimo validado (ou 25%+ abaixo da mediana de 30 dias) **e** `VALIDADO` |
| ALTA | `PROVAVEL`/`VALIDADO` e (até 3% acima do mínimo validado ou 15%+ abaixo da mediana) |
| MÉDIA | 5%+ abaixo da mediana, ou histórico insuficiente com evidência; avisos de tensão ambígua/importado rebaixam |
| BAIXA | sem vantagem demonstrada, expirado, sem preço, fora do catálogo de moeda |

## Alertas urgentes

- Gera alerta só para `CRITICA` e `ALTA`, **oferta publicada há até 6 h**, das 07:00 às 23:00. **Desde a fase 4 o limite de 6 por ordem de chegada foi substituído por prioridade e orçamento** (pontuação 0 a 100, 6 comuns, 3 críticos e 2 de exceção por dia, 2 por varredura, anti-repetição por produto, substituição de candidato fraco por um muito melhor; ver [14-relatorio-fase-4.md](14-relatorio-fase-4.md)). Oferta sem hora de postagem (`hora_incerta`) nunca é anunciada como "relâmpago".
- **Deduplicação persistente** (tabela `alertas`): chave = produto + loja + vendedor (+ cupom, preço, link normalizado). Equivalente nas últimas 24 h é suprimido; novo alerta só com preço pelo menos 3% menor, cupom diferente ou status melhorado para `VALIDADO`. Envio com falha não conta como enviado (reavalia no ciclo seguinte).
- **Ativação explícita (alterada em 21/11/2026).** O período de sombra por data foi **removido**: depois das 08:00 de 21/11 ele teria ligado o envio sozinho. Agora o alerta só sai se `alertas.enviar: true` **e** `alertas.homologado_em` estiver preenchido por você, depois de revisar `python -m radar alertas`. Sem os dois, tudo é registrado em modo sombra. Hoje: `enviar: false`, `homologado_em: null`. `python -m radar status` mostra "EM SOMBRA" ou "LIGADOS e homologados em ...".
- **Alerta de oferta não confirmada não sai como promoção validada.** Só `status_enviaveis: [PROVAVEL, VALIDADO]` geram alerta; `NAO_CONFIRMADO` e `EXPIRADO` nunca. O texto mostra o status, "(estimado)" no preço final enquanto não houver `VALIDADO`, e "Confirme preço, voltagem e vendedor no carrinho antes de pagar".
- **Validade (TTL) e revalidação.** Alerta que falha no envio entra na fila com validade de `ttl_alerta_min` (30 min). Vencido, **só é entregue se a oferta for revalidada na fonte** (Promobit: página da oferta; Gatry: `/v1/promotions/{id}`): status fora de `FINISHED/EXPIRED/REMOVED...`, validade não vencida e preço no máximo 2% pior. Entregue assim, vem rotulado "Alerta atrasado, revalidado na fonte às HH:MM". Sem como revalidar (Pelando, HardMOB, Telegram), erro de revalidação ou oferta encerrada: **descartado** com `desfecho = descartado_revalidacao`. Relatório na fila vence em 24 h (`expirado_ttl`). Todo desfecho fica na tabela `outbox`.
- Mensagem no padrão pedido (produto, loja, preço anunciado, cupom, preço final com "(estimado)", economia, menor validado, comparação, fonte, hora, status, link), sem travessão e com o aviso "Confirme preço, voltagem e vendedor no carrinho antes de pagar".
- Relatórios das 08/14/20h seguem independentes e inalterados.
