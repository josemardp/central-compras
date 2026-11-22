# 18. Relatório da fase 6: preparação final e ativação controlada (21/11/2026, noite)

Escopo: resolver os últimos impedimentos para uma ativação controlada antes da Black Friday de 27/11. O commit e o push do radar foram feitos ao final, com a sua autorização expressa (seção 7). Os alertas seguem **desligados** (modo SOMBRA). Com a sua autorização foi enviada **uma única mensagem de teste** ao seu próprio WhatsApp (seção 4); nenhum alerta real foi enviado.

## 9. Recomendação objetiva (resumo no topo)

**APTO PARA PILOTO, condicionado. NÃO APTO para produção completa.**

O radar já está em condição de iniciar um **piloto restrito** (2 alertas comuns e 1 crítico por dia, 1 por varredura, só produto exato, sem nenhum aviso, fonte revalidada no envio, destinatário confirmado por você). O que ainda falta antes de ligar é de ordem manual e não de código:

1. ~~Teste único de entrega~~ **feito** (21:12, 15,6 s, confirmação do mecanismo). Falta **você** ver no celular que a mensagem chegou no **seu** chat.
2. Você preencher `piloto.destinatario_confirmado_em`. Sem isso o piloto não envia nada.
3. O **commit** do radar, com a sua autorização (hoje o código só existe nesta máquina e nos backups).

A exigência de "3 ofertas reais em sombra" foi retirada, como você pediu. O que está comprovado e o risco residual estão na seção 6. Em uma frase: o caminho ao vivo funcionou de ponta a ponta com 1 oferta real e **detectou sozinho que ela não era uma oferta**; não há amostra para medir recall nem taxa de falso positivo em mercado, e o piloto limita o dano em vez de fingir que essa prova existe.

**Aprovação nos testes não é eficácia comercial.** A suíte completa passou (**941 testes, OK**, 409 s; eram 892 no fim da fase 5). Isso prova que o código faz o que foi desenhado. Que ele encontra boas ofertas inéditas sem alarme falso só se prova com ofertas reais, e até agora existe 1.

## 1. Estado operacional

| Item | Estado | Evidência |
|---|---|---|
| Modo | **SOMBRA** | `enviar: false`, `homologado_em: null`, `piloto.ativo: false` |
| Varredura a cada 10 min | funcionando | tarefa `Ready`/`Running`, ciclos recentes com resultado 0, nenhuma falha durante as edições desta fase |
| Relatórios 08h, 14h e 20h | funcionando | 12 de 12 envios reais ao WhatsApp nos dias 20 e 21/11, todos na 1ª tentativa, 0 retentativa, 0 fila |
| Cinco fontes comunitárias | funcionando | Promobit, Gatry, HardMOB, Pelando, Méliuz com 0 falhas seguidas |
| Banco, histórico, correções, trava de máquina | íntegros | `radar ativacao`: 21 OK, 0 FALHA, 0 PENDENTE, 5 MANUAL |
| Verificação prévia | **APTO PARA PILOTO** | `python -m radar ativacao` (somente leitura) |
| Telegram | não autenticado | 0 credencial, 0 sessão, 0 canal; comandos prontos |
| Tarefa da Black Friday | preparada, **não criada** no Windows | `radar status` diz "AINDA NÃO CRIADA" |

## 2. Evidência da oferta Philco

Oferta #232 no banco real, lida de novo na fonte e na loja em 21/11 à noite (somente leitura). Comando que repete tudo: `python -m radar conferir 232`.

| Campo | Resultado | Como foi verificado |
|---|---|---|
| Produto exato | Philco Eco Inverter 18.000 BTU, **SKU PAC18FTW**, com Wi-Fi | título da fonte contra o catálogo; EAN 7891356132421 na loja |
| Voltagem | **220V** (o catálogo exige 220V; o título informa) | título da fonte |
| Vendedor | **WebContinental**, estoque próprio (loja verificada, CNPJ válido segundo o Promobit) | API pública da loja: `sellerName` |
| Preço anunciado | **R$ 2.379,00** (de R$ 2.930,68) | Promobit |
| Preço confirmado na loja | **R$ 2.579,00** sem cupom (lista R$ 2.930,68) | API pública VTEX da WebContinental |
| Frete | **não informado**; depende do CEP | o radar não usa CEP (dado pessoal) |
| Disponibilidade | **em estoque** na loja; a fonte devolveu **ATIVA (APPROVED)** horas depois da publicação | API da loja e revalidação na fonte |
| Cupom | **PHI200**, valor **não informado** pela fonte, **NAO_CONFIRMADO** | `offerCoupon` sem instruções |

## 3. Resultado da verificação de preço e cupom

**Os R$ 2.379 já incluem o PHI200.** A conta fecha exatamente: R$ 2.579,00 (loja) menos R$ 200,00 = R$ 2.379,00 (anunciado). O mesmo cupom PHI200 aparece em ofertas anteriores desse produto na mesma loja (R$ 2.099,01 e R$ 2.299,00), o que indica um cupom recorrente da loja, mas não prova o valor dele. Duas ressalvas explícitas: o valor de R$ 200 é **inferido pela diferença**, a fonte não o declara; e que o cupom funcione no carrinho **não foi confirmado**.

Os três níveis de preço, que nunca se misturam:

| Nível | Valor | Situação |
|---|---|---|
| Preço **anunciado** | R$ 2.379,00 | publicado pela comunidade, supõe o cupom |
| Preço **confirmado** | R$ 2.579,00 | conferido na loja, **sem cupom**: é o único garantido hoje |
| Preço **entregue** | n/d | frete e prazo só o carrinho sabe |

**Cupom nunca é descontado duas vezes.** Regra nova no código: cupom que vem no campo da própria oferta é tratado como já embutido no preço anunciado, e fica como "necessário para este preço, não confirmado". Antes, se alguém validasse o cupom, o motor poderia descontar R$ 200 de novo sobre os R$ 2.379. Há teste dedicado.

**Efeito na decisão:** o melhor preço monitorado do Philco 18k é R$ 2.569,00. Sem o cupom (R$ 2.579) o produto custa **mais** que isso; com o cupom, R$ 190 (7%) a menos. Ou seja, a "oferta" só existe se o PHI200 funcionar. Rodei a **mesma oferta real**, lida agora na fonte, pelo pipeline novo com o histórico real:

| Pipeline | Classe | Confiança | Resultado |
|---|---|---|---|
| sem conferir a loja (como na fase 5) | ALTA | MEDIA | **candidato a alerta** (pontuação 64) |
| conferindo a loja (agora) | **MEDIA** | MEDIA | **sem alerta**: "o preço anunciado só vale com um cupom NAO confirmado (a loja cobra mais sem ele)" |

Ou seja, o radar passou a **recusar sozinho** um alerta que dependia de um cupom não verificado. Para virar oferta você valida o PHI200 no carrinho (sem finalizar) e roda `radar validar`.

**Outras oportunidades em sombra:** não houve outra. Foram ~15.500 publicações lidas e 1 candidato (a Philco). O cruzamento de cupons de loja segue com 7 "potencialmente elegíveis" (economia só estimada), 0 validados. `BLACK150` continua **NAO_CONFIRMADO**.

**Lojas conferíveis.** Medi 11 lojas com o SKU PAC18FTW: só **WebContinental e FrioPeças** têm API pública de catálogo. Nas demais (Amazon, KaBuM, Magalu, Mercado Livre, Casas Bahia, Frigelar, Dufrio, Fastshop, Leroy) o preço fica "não conferido na loja" e a confiança do alerta nunca passa de MEDIA.

## 4. Medição de latência do WhatsApp

**Executada com a sua autorização, uma única vez, em 21/11 às 21:12.** Resultado:

| Registro | Valor |
|---|---|
| Destino | a **conta logada** na aba do WhatsApp (conferido antes: destino configurado igual à conta; chat próprio) |
| Mensagem | começa com "TESTE DO RADAR DE COMPRAS (mensagem sintética, não é oferta real)"; produto e preço inventados; 1.250 caracteres; formato real do alerta com os 3 níveis de preço e a confiança |
| Início da tentativa | 21:12:14 (mensagem montada em 0,06 s antes do envio) |
| Confirmação do mecanismo | **ok na 1ª tentativa**: a mensagem foi lida de volta na conversa da aba (`confirmado_no_chat: true`, `caixa_vazia: true`) |
| Tempo do envio | **15,6 s** (criação até confirmação: **15,64 s**) |
| Fila | **0 pendente** antes e depois; nada foi para a fila |
| Erros | nenhum; 0 retentativa |
| Trava do teste único | 2ª tentativa no mesmo dia **recusada** (nada enviado) |

**Atenção ao que isto prova.** É a confirmação do **mecanismo de envio** (o radar leu a própria mensagem na conversa da aba). **Não é** confirmação de leitura nem de chegada no aparelho: isso só você vê no celular. O tempo de 15,6 s vale para uma mensagem longa (1.250 caracteres) e substitui a estimativa de "pelo menos 4 s": um alerta real gasta algo parecido. Latência total revista do alerta do Promobit: **~7,9 min** na mediana (7,5 de leitura + 10 s de processamento + ~16 s de envio).

- **Instrumentação pronta** (testada): para cada alerta, criação do candidato, início do envio, confirmação lida de volta na conversa, entrada na fila se falhar e tempo na fila até a reentrega. `python -m radar latencia` mostra tudo como MEDIDO quando houver dado.
- **Teste único:** `python -m radar teste-entrega` mostra a prévia (a mensagem de teste com o formato real do alerta, incluindo os 3 níveis de preço e a confiança, rotulada TESTE). `--confirmo` envia **1** mensagem ao seu chat e mede. No máximo 1 por dia. Falha do canal não conta como teste feito.
- **Os testes controlados anteriores como evidência:** não deixaram tempo gravado. Mas os logs reais dos relatórios provam **confiabilidade**: 12 de 12 envios ok na primeira tentativa (3 em 20/11, 9 em 21/11), mensagem lida de volta na conversa (`caixa_vazia=True`), 0 retentativa, 0 fila. Os relatórios de hoje (08h, 14h, 20h) já gravam o tempo de envio a partir desta versão (`envio_relatorio`).
- **Dominante:** a espera até o próximo ciclo e o atraso da fonte, não o envio.
- **Kill switch e fila, de novo:** `python -m radar ativacao --ensaio-kill-switch` (5/5): alerta e relatório na fila, desligamento, alerta descartado, relatório preservado, próxima varredura sem alerta, configuração real intacta.

## 5. Plano temporário da Black Friday (26 a 30/11)

**Viabilidade: viável e barata, sem reduzir páginas.** Só o Promobit muda; Gatry, HardMOB, Pelando e Méliuz continuam exatamente como estão.

| | Hoje (a cada 10 min) | Janela (a cada 5 min) |
|---|---|---|
| leituras por hora | 6 | 12 |
| requisições por leitura | 7 (5 páginas + 2 lojas) | 7 |
| requisições por hora | 42 | **84** (uma a cada ~43 s) |
| tempo de uma leitura | 3,7 a 6,6 s [MEDIDO] | 2,6 a 4,1 s só das 5 páginas [MEDIDO] |

**Cobertura efetiva.** Pior momento medido hoje: a lista de 60 itens cobre só **14 min** (pico da tarde, ~4,3 itens/min), ou seja, 2,8x o intervalo de 5 min. Por isso as **5 páginas foram mantidas**: reduzir para 2 ou 3 páginas daria 6 a 8 min de cobertura no pico, margem curta que na Black Friday (volume maior) viraria buraco. À noite, com ~1,3 itens/min, todas as chegadas novas (33 de 33) estavam na 1ª página. A telemetria de cada leitura grava `cobertura_min`, `lacuna`, `buraco` e `janela_intensiva`; `python -m radar lacunas` e `python -m radar latencia` mostram cobertura contra intervalo.

**Estimado (teoria) contra medido (real):**

| | Teórico | Medido |
|---|---|---|
| Chance de ler ao menos uma vez uma promoção de 5 min | 49% (ciclo 10 min) para ~100% (ciclo 5 min) | **não medido**: exigiria promoções reais de 5 min; é cálculo de agenda e supõe que a oferta já esteja na lista |
| Atraso da publicação até a leitura, Promobit | espera média cai de 5 para 2,5 min | **10 min:** mediana 7,5, p90 11,4, máx 12,5 (n = 53, tarde). **5 min:** mediana 6,4, p90 7,4, máx 7,6 (n = 33, noite) |

Leitura honesta do medido: o ciclo de 5 min **corta a cauda** (p90 de 11,4 para 7,4 min; máximo de 12,5 para 7,6) e a mediana cai ~1 min, não os 2,5 min da teoria. O resto é o atraso da própria fonte até a oferta aparecer na lista, que não depende de nós. As duas amostras são de horários e volumes diferentes (tarde de sábado contra noite de sábado): indicam a direção, não são um experimento controlado.

**Limites de acesso, bloqueios e custos.** Só páginas públicas, como hoje, sem contornar nada. Carga adicional: +42 requisições por hora numa única fonte. Se o Promobit começar a recusar (429, bloqueio), a leitura vira `erro` visível no relatório de efetividade e as outras fontes não são afetadas; não há tentativa em rajada.

**Sem sobreposição de execuções.** A tarefa dedicada usa a **mesma trava** (`varredura`) da varredura normal, tem `MultipleInstances IgnoreNew`, limite de 4 min e **não recupera disparo perdido** (um atraso não gera duas leituras). Dispara em :05, :15, :25..., a normal em :00, :10... (testado).

**Retorno automático à frequência normal, em três camadas independentes** (todas testadas):
1. a janela é **por data** em `config/radar_fontes.yaml` (`janela_intensiva`, de 26/11 00:00 a 30/11 23:59): passou o `ate`, o Promobit volta sozinho a 10 min, sem estado para desligar;
2. a tarefa do Windows tem **início 26/11 00:05 e fim 01/12 00:00** (`EndBoundary`): depois disso não dispara mais;
3. a tarefa é **apagada sozinha 24 h depois** de expirar (`DeleteExpiredTaskAfter`).

**Passo a passo:**
1. **Até 25/11 (seu):** `python -m radar agendar --aplicar --job varredura_promobit_bf`. Cria **só** a tarefa `Central Compras - Radar Promobit BF`. Confirmar com `python -m radar status`.
2. **26/11, 00:15:** `python -m radar status` (janela "ATIVA AGORA") e `python -m radar lacunas --horas 1`.
3. **Durante:** `python -m radar latencia` (cobertura contra intervalo) e `python -m radar efetividade`.
4. **01/12:** `python -m radar status` deve mostrar "fora da janela"; a tarefa não dispara mais.
5. **Parar antes:** `Disable-ScheduledTask -TaskName "Central Compras - Radar Promobit BF"` (ou apagar o bloco `janela_intensiva`).

Sem o passo 1, a janela da configuração não traz ganho: o Promobit segue sendo lido só pela varredura normal, a cada 10 min.

## 6. Piloto: o que está comprovado e o risco residual

Modos: **SOMBRA** (padrão, nada sai), **PILOTO** (restrito) e **COMPLETO**. Guia: [17-piloto-controlado.md](17-piloto-controlado.md).

**Limites conservadores propostos:** 2 comuns, 1 crítico e 0 de exceção por dia; 1 por varredura; mesmo produto só após 4 h ou melhora de 7%. **Proteção contra repetição** e orçamento retido visível (`retida_orcamento`). **Barreiras:** produto exato da lista (11 produtos; o Xiaomi do Paraguai em dólar fica fora), nenhum aviso, confiança mínima MEDIA exibida com a razão, link da fonte, fonte revalidada no envio, destinatário confirmado por você. **Monitoramento:** `python -m radar piloto`. **Desligamento imediato:** `python -m radar ativacao --desligar` (limpa a fila na hora).

**Comprovado:**
- caminho ao vivo de ponta a ponta com 1 oferta real em sombra, que ainda **detectou que ela dependia de cupom não verificado** (seção 3);
- preço conferido na própria loja para 2 lojas, preço x cupom sem desconto duplo, 3 níveis de preço;
- 12 de 12 relatórios reais entregues na primeira tentativa; fila, TTL, reconexão e kill switch em simulação e ensaio;
- 0 falso positivo em 96 negativos reais independentes; 941 testes.

**Risco residual de liberar o piloto:**
1. **Amostra ao vivo mínima** (1 oferta em ~15.500 publicações): não mede recall nem falso positivo em mercado.
2. **Entrega medida uma vez** (15,6 s, 1 mensagem): amostra de 1, e é confirmação do mecanismo de envio, não leitura no aparelho.
3. **Só 2 lojas** com preço conferível; nas outras a confiança máxima é MEDIA e o preço vem só da comunidade.
4. A promoção pode estar acabando quando o alerta chegar (mediana de ~7,5 min de atraso do Promobit).
5. Atenção: a primeira oferta real foi **barrada**, o que mostra o filtro funcionando mas também que a taxa de alerta será **muito baixa**. O piloto pode ficar dias sem enviar nada.
6. O destino do WhatsApp só você confirma.

No pior caso, o piloto manda 2 alertas por dia de produto exato, sem aviso e com a fonte revalidada.

## 7. Estado do Git e manifesto do commit

Antes do commit, o HEAD era `3234e4d` ("Registra cotacao inicial de sacolas", 21/11 20:08): é um commit de **outra sessão** que só alterou `STATUS.md` (+6 linhas, seção de sacolas) e não tocou no radar nem no Climatizador. O patch do `STATUS.md` foi **regenerado contra esse HEAD** e validado (`git apply --check --cached`, exit 0).

| Conjunto | Arquivos | Entra no commit do radar? |
|---|---|---|
| Radar (código, config, testes, docs, corpus; inclui 6 rastreados modificados) | **106** | **sim** (lista exata: `python -m radar git-escopo --manifesto`) |
| Climatizador (outra sessão) | 30 | **não** (`config/categorias.yaml`, `produtos/climatizador/`, `projetos/2026-climatizador-...`, `base-conhecimento/especificacoes/climatizador.md`); foto SHA-256: **intactos** |
| `STATUS.md` (misto) | 1 | **só as 6 seções do radar**, por patch validado com `git apply --check`; a seção do Climatizador fica de fora |

Novos nesta fase: `radar/lojas.py`, `radar/piloto.py`, `config/radar_lojas.yaml`, `tests/test_radar_lojas.py`, `tests/test_radar_piloto.py`, `tests/test_radar_black_friday.py`, docs 17 e 18. Alterados: `radar/` (varredura, prioridade, alertas, ranking, ativacao, latencia, outbox, efetividade, agenda_windows, status, cli, telegram_conta), `config/radar_regras.yaml`, `radar_fontes.yaml`, `radar_jobs.yaml`, testes e docs 09, 10, 11, 12, 16.

Verificações: `git add --dry-run` dos caminhos propostos inclui **106 arquivos, idênticos ao manifesto** (nenhum a mais, nenhum a menos); segredos limpos (`checar-segredos --strict`), backup do código e das cópias da outra sessão com **restauração testada**, nenhum arquivo do Climatizador na lista do radar, nenhum arquivo esquecido fora da lista.

**Escopo final proposto para a sua autorização** (nada executado; `git add --dry-run` mostra o conteúdo exato):

```
git add config/radar_*.yaml docs/ecossistema/ radar/ tests/corpus/ tests/test_radar_*.py
git add requirements.txt scripts/rastrear_ares_bf.py scripts/rastrear_chuveiro_bf.py scripts/rastrear_robos_bf.py scripts/rodar_rastreador_robos.ps1 tests/test_rastrear_chuveiro_bf.py
git apply --cached <pasta de backups>\STATUS.radar.patch
git commit -m "feat(radar): radar de compras V3 (central-compras dono unico das automacoes de compras)"
git push origin main
```

Antes do `git add`, rode de novo `python -m radar git-escopo --manifesto` e confira que não aparece `climatizador`. Confira também o remote da conta correta antes do push.

## 8. Pendências que exigem a sua intervenção

1. Conferir no celular que a mensagem de teste das 21:12 chegou no **seu** chat (o teste já foi feito).
2. Preencher `piloto.destinatario_confirmado_em`.
3. Validar **PHI200** e **BLACK150** no carrinho (até a tela de pagamento, sem finalizar) e registrar com `radar validar`, se quiser que virem oferta.
4. Criar a tarefa da Black Friday: `python -m radar agendar --aplicar --job varredura_promobit_bf` (antes de 26/11).
5. ~~Autorizar o commit~~ **feito** (commit e push autorizados por você em 21/11).
6. Telegram: login seu (guia 12): `telegram-login`, `telegram-listar`, colar só os canais de oferta em `config/radar_fontes.yaml`.
7. Ativar o piloto (3 edições em `config/radar_regras.yaml`) só depois de 1 a 3.

## Telegram

Os três comandos estão prontos: `telegram-login` (interativo, `api_hash`, código e senha não aparecem na tela), `telegram-listar` (só canais, nenhuma mensagem lida; `--grupos` mostra também nomes de grupos) e `telegram-status` (sem segredos). Guia mínimo em `docs/ecossistema/12-telegram-passo-a-passo.md`. Travado por teste: nenhuma chamada que entre em grupo, envie, apague, encaminhe ou marque como lida; id de pessoa ou bot é recusado antes de ler e a entidade é conferida ao conectar; a sessão fica só em `dados-privados\radar\telegram\`, **sem tocar no Coral**.

## Defeitos achados e corrigidos nesta fase

| # | Defeito | Correção |
|---|---|---|
| 1 | Oferta com cupom no campo da fonte podia ter o cupom descontado de novo se fosse validado | cupom embutido nunca é descontado; fica como "necessário, não confirmado" |
| 2 | Preço que depende de cupom não confirmado virava candidato a alerta ALTA | conferência na loja + aviso bloqueante: classe limitada a MEDIA |
| 3 | Motivo mostrado era "voltagem/modelo" para um problema de cupom | motivo específico |
| 4 | A telemetria nova quebrava o relatório de efetividade (`int(None)`) | pego pelos testes e corrigido antes de afetar a rotina |

Risco operacional anotado: as tarefas agendadas executam a árvore de trabalho; um arquivo salvo pela metade quebra um ciclo. Durante as edições desta fase nenhuma varredura agendada falhou, mas vale congelar o código quando o piloto começar.

## Efetividade é com você

Eu entrego a conferência, os limites e as evidências, mas só você sabe se um alerta por dia ou nenhum é o que a sua rotina quer receber, e se um Philco 18k a R$ 2.379 condicionado a um cupom que ninguém testou merece o seu tempo. Antes de ligar o piloto, valide o PHI200 no carrinho: é a forma mais barata de descobrir se o radar acertou ao barrar essa oferta.
