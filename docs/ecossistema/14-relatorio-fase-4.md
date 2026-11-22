# 14. Relatório da fase 4: consolidação, segurança e preparação para a Black Friday (21/11/2026)

Escopo: proteger o código, trocar o limite de 6 alertas por ordem de chegada por uma política de prioridade, separar as três horas de uma oferta, medir lacunas de coleta, separar treino de regressão e de avaliação independente, manter as regras estritas de cupom e fechar a homologação. Nada foi commitado ou enviado ao GitHub. Alertas reais seguem desligados (modo sombra).

## Veredito

O radar está tecnicamente protegido e pronto para ativação controlada, **mas não ativado**. `alertas.enviar` continua `false` e `alertas.homologado_em` continua vazio: só você liga. A política de prioridade já roda de verdade em sombra (as tarefas agendadas de 10 em 10 minutos usam o código novo e gravam o que SERIA enviado).

O que melhorou de forma comprovada nesta fase:

1. Código e arquivos de outras sessões têm backup recuperável fora do Git, com restauração testada.
2. O orçamento de alertas deixou de ser "os 6 primeiros do dia". Uma oferta muito melhor chegando depois passa na frente (cenário P01).
3. A hora de uma oferta sem hora de postagem (HardMOB) nunca mais é tratada como hora de postagem, nunca é "relâmpago" e não ganha pontos de urgência.
4. A avaliação passou a ter um conjunto independente de 106 itens reais. Ele achou **1 falso positivo real** (abreviação "Q/f" de quente/frio) que o conjunto antigo não pegava. Corrigido, com teste que impede de voltar.

O que continua NÃO provado: o **recall de mercado**. Só há 7 positivos reais no conjunto independente, então o intervalo de confiança vai de 64,6% a 100%. Ver seção 4.

## 1. Proteção do código e do Git (item 1)

| | Antes | Depois |
|---|---|---|
| Backup do código fora do Git | zip simples | zip do radar + zip das cópias de arquivos de outras sessões, ambos com **restauração testada** (195 testes passaram a partir da cópia restaurada) |
| Arquivos da outra sessão (Climatizador, 30 caminhos) | sem foto | foto SHA-256 (`alheios-baseline.json`); `git-escopo --verificar` compara e hoje retorna **intacto** (30 arquivos, 0 alterados, 0 sumidos) |
| STATUS.md misto | risco de levar a seção do Climatizador junto | `STATUS.radar.patch` gerado só com as seções do radar, validado com `git apply --check` (HEAD e árvore) |
| Comandos Git do módulo | leitura | continuam só leitura: `status`, `diff`, `log`, `stash list`, `show` e `apply --check`. Nenhum `add`, `commit`, `push`, `stash` ou `checkout` |

Onde estão (fora do Git): `C:\Users\pc\.central-compras\dados-privados\radar\backups\`.

Comandos: `python -m radar git-escopo --manifesto` (lista exata do que entra no commit do radar), `--verificar`, `--backup-completo`, `--baseline`.

O manifesto do commit do radar tem **89 arquivos** (inclui os testes novos desta fase e este relatório; eram 83 no início da fase 3). Os 30 arquivos do Climatizador ficam de fora. `STATUS.md` entra pelo patch (só as seções do radar), não inteiro.

## 2. Prioridade e orçamento de notificações (item 2)

**Antes:** `limite_diario: 6`, ordem de chegada. Um alerta fraco das 9h gastava a vaga de um excelente das 15h.

**Depois:** cada oferta que passa nos portões (produto reconhecido, status enviável, sem duplicidade) vira um *candidato* com pontuação de 0 a 100. No fim de cada ciclo, o despachante (`radar/prioridade.py`) ordena todos os pendentes e decide.

Pontuação (pesos em `config/radar_regras.yaml`, seção `prioridade`):

| Componente | Peso | O que mede |
|---|---|---|
| economia % | 35 | % abaixo do melhor preço atual monitorado (20% = nota máxima) |
| economia em R$ | 10 | R$ abaixo do melhor preço atual (R$ 300 = nota máxima) |
| histórico | 15 | posição no seu histórico (mínimo e mediana de 30 dias) |
| confiança | 20 | validado vale mais que provável; hora incerta reduz (x0,7) |
| exatidão | 10 | penaliza aviso de voltagem, SKU não confirmado, nome alternativo |
| urgência | 10 | frescor da publicação; **zero** quando a hora é incerta |
| repetição | menos 8 por alerta do mesmo produto nas últimas 24 h (até 2) | |

Regras do despacho:

- **Orçamento diário:** 6 comuns, 3 críticos, mais 2 de exceção (só pontuação 80 ou mais, acima do comum).
- **Anti-rajada:** no máximo 2 alertas comuns e 2 críticos por varredura (10 min).
- **Anti-repetição:** o mesmo produto só volta depois de 90 min (30 min se crítico), ou se o preço melhorar 5% sobre o último alerta.
- **Substituição:** candidato que espera e está 15 pontos ou mais abaixo de um selecionado é substituído. Duas ofertas do mesmo produto: só a melhor.
- **Pontuação mínima 40:** abaixo disso não vira alerta mesmo sobrando orçamento.
- **CRÍTICO pode passar do limite comum**, mas tem orçamento próprio (3/dia), limite por ciclo e intervalo próprio. Não é ilimitado.
- **Validade:** candidato não enviado em 30 min vence (`expirado`). Quem esperou mais de 5 min é conferido na fonte antes de ser entregue; revalidação que falha ou quebra não entrega.
- **Falha de envio:** a mensagem vai para a fila (outbox) com validade de 30 min e é entregue na reconexão.
- **Modo sombra:** com `enviar: false` o resultado é `selecionado_sombra` e nenhuma mensagem sai.

Estados de um candidato: `pendente`, `selecionado_sombra`, `enviado`, `substituido`, `nao_selecionado`, `suprimido_repeticao`, `expirado`, `adiado`, `falha_envio`.

Comando para ver tudo: `python -m radar prioridade` (orçamento de hoje, candidatos, pontuação e motivo).

**Evidência:** 21 testes novos em `tests/test_radar_prioridade.py` (pontuação, ordem, orçamento, substituição, críticos, repetição, validade, revalidação, falha de envio e um fluxo completo na varredura em que a melhor oferta ganha de quem chegou primeiro). A homologação por cenários subiu de 16 para **22/22**: P01 a P06 cobrem ordenação, mesmo produto, orçamento esgotado com crítico acima do limite, expiração, queda e volta da internet e sombra.

**Importante:** os pesos e orçamentos são uma proposta minha. Quem decide quanto alerta é útil por dia é você (ver seção 9).

## 3. Três horas e lacunas de coleta (item 3)

Cada oferta agora guarda três horas diferentes (migração 4 do banco, com reversão e backup automático):

| Campo | Significa | Quando existe |
|---|---|---|
| `publicado_em` (published_at) | hora da postagem informada pela FONTE | só se a fonte informa |
| `primeira_vista_em` (first_seen_at) | quando o RADAR viu a oferta pela primeira vez | fonte sem hora (HardMOB), ids maiores que a marca-d'água |
| `coletado_em` (collected_at) | quando o radar leu a página | sempre |

Antes, o HardMOB gravava a hora em que o radar viu como se fosse a hora da postagem. Agora isso não acontece. Oferta sem `publicado_em` fica com `hora_incerta`:

- nunca é anunciada como "RELÂMPAGO", mesmo crítica (sai como "OFERTA EM DESTAQUE" com a nota de que a fonte não informa a hora);
- não ganha pontos de urgência e a confiança é multiplicada por 0,7;
- só é tratada como nova se foi vista agora **e** não houve lacuna de coleta antes (senão pode ter sido postada na janela em que o radar estava fora).

**A janela de indisponibilidade maior que a cobertura da fonte gera lacuna? Sim, e agora é medida.** A cada ciclo o radar compara o tempo desde a última leitura boa com o alcance da lista da fonte (a cobertura medida; para o HardMOB, a estimativa `cobertura_estimada_min: 120`, **declarada como estimativa** porque a fonte não informa hora). Se a janela for maior, grava `lacuna`, `lacuna_min`, `perdido_min` e marca as ofertas sem hora como "não novas". Também detecta transbordo da lista do HardMOB (quase todos os itens são novos entre dois ciclos).

Provas:

- Teste simula notebook suspenso por 7 h com lista de 40 min: lacuna de 420 min, **380 min perdidos** (`test_notebook_suspenso_por_mais_que_a_cobertura_gera_lacuna_medida`).
- Teste simula internet fora por 590 min: 550 min perdidos. Janela de 180 min com lista de 968 min (Gatry): nenhuma perda.
- Dado real (`python -m radar lacunas --horas 30`, 21/11, ciclos desde as 10:23): **0 lacunas** em Promobit, Gatry, HardMOB e Pelando; maior intervalo entre leituras 16 a 20 min. A queda de 590 min citada na fase 3 aconteceu antes da telemetria existir, então ela só está provada em teste, não no histórico gravado.
- Achado real: a lista do **Promobit cobriu apenas 18 min** no ciclo das 15:30, contra ciclo de 10 min. A margem é curta e na Black Friday o volume sobe. Se uma execução atrasar mais de 18 min, ofertas do Promobit se perdem. O radar agora avisa (`buraco` e `lacuna`), mas não corrige sozinho.
- Méliuz roda a cada 90 min por desenho (cupom de loja dura dias e não tem hora): marcado `lista_estatica`, fora da análise de lacunas.

## 4. Corpus de avaliação independente (item 4)

O corpus (`tests/corpus/radar_ofertas_rotuladas.yaml`, 179 itens) passou a ter o campo `conjunto`:

| Conjunto | Itens | Uso |
|---|---|---|
| treino | 27 | itens que eu vi ao construir o catálogo: só provam que não regrediu |
| regressão | 46 | escritos para travar uma regra ou um defeito já corrigido (otimista por construção) |
| independente | 106 | reais, rotulados por leitura do título **antes** de rodar o reconhecimento. É o único que mede mercado |

O conjunto independente tem 90 títulos reais do histórico do Gatry (busca pública por marca, categoria e SKU, mais 16 itens sorteados fora das marcas), 8 da cotação independente de outras sessões e 8 lidos ao vivo. Cada item do Gatry guarda data e identificador para conferência. Dado sintético nunca entra no independente (teste trava isso).

Cobertura dos tipos pedidos: URLs e anúncios reais, ofertas históricas da comunidade (Gatry, anos de 2016 a 2026), variações de título e modelo, produtos de outra tensão (127V/220V), produtos parecidos de outras marcas, ofertas sem SKU (3 ambíguos) e cupom de loja sem produto explícito (N21 e cruzamento).

**Resultado, primeira passada (antes de qualquer correção), conjunto independente:**

| | TP | FP | FN | TN | precisão | recuperação (IC95) | falso positivo (IC95) |
|---|---|---|---|---|---|---|---|
| primeira passada | 7 | **1** | 0 | 95 | 87,5% | 100% (64,6% a 100%) | 1,0% (0,2% a 5,7%) |
| depois da correção | 7 | 0 | 0 | 96 | 100% | 100% (64,6% a 100%) | 0% (0% a 3,8%) |
| ambíguos com o comportamento esperado | | | | | | 3 de 3 | |

O falso positivo: "Ar Condicionado 12k Elgin Eco Inverter III Wi-fi **Q/f** Branco". Q/f é quente/frio abreviado, mas o catálogo só excluía a palavra "quente". Corrigido nas 6 regras de ar-condicionado (`\bq\s*[/&]\s*f\b`) e travado por R01 a R04 (inclui um caso para garantir que um "q" solto não exclui).

**Limites, sem maquiagem:**

- Só 7 positivos reais independentes (3 da cotação de outras sessões e 4 do Gatry). O Gatry quase não traz estes produtos. Recuperação de 100% com IC de 64,6% a 100% **não prova recall alto**. O que está bem provado é a **taxa de falso positivo**: 96 negativos reais, entre eles os difíceis (mesma marca em outra categoria, Eco Inverter II no lugar de III, 9k e 18k no lugar de 12k, quente/frio, chuveiros 6800W de outros modelos, "K800" de fone, "Philco Eco Inverter" em geladeira).
- Treino e regressão com 100% não dizem nada sobre mercado.
- O Pelando não tem busca pública utilizável (404), e não tentei contornar bloqueio.
- Rótulos incertos foram **excluídos**, não forçados (ex.: Xiaomi S40 Pro vendido no Brasil, Philco PAC18FI, Midea AirVolution sem Lite).

Para medir recall de verdade é preciso mais positivos reais: o caminho é acumular, durante a Black Friday, os anúncios reais que você confirmar e rotulá-los no conjunto independente.

## 5. Cupons (item 5)

Regras estritas mantidas: publicação não prova funcionamento; cupom não confirmado não desconta do preço final; "até X" nunca entra no preço; cruzamento de cupom de loja é **informativo**, nunca alerta.

Novidade: `tests/test_radar_cupons_guarda.py` (6 testes) trava por código que:

- nenhum módulo que decide alerta (varredura, alertas, prioridade, outbox, ciclo, ranking, histórico, recuperação) importa o cruzamento nem os equivalentes;
- todo resultado do cruzamento sai com `confirmado: False` e nunca com status `VALIDADO` (só o `radar validar` manual chega lá);
- cupom de loja sem produto não vira candidato nem envio, mesmo com alertas ligados;
- oferta de produto com `BLACK150` não confirmado tem preço final igual ao anunciado (nenhum desconto contado) e nenhuma mensagem diz "garantido".

**BLACK150 continua `NAO_CONFIRMADO`.** O cruzamento o trata como candidato a teste: R$ 150 acima de R$ 1.499, sem restrição conhecida. Economia estimada de R$ 150 no Dreame F10 da Amazon, **nada confirmado**.

**Como verificar elegibilidade e desconto no carrinho sem comprar** (não executei nada em loja; o que está marcado `[VERIFICAR]` depende de como a Amazon se comporta hoje e só você confirma):

1. Forma segura e permitida: **você**, logado, coloca o item no carrinho, avança até a etapa de pagamento, informa o código e lê a linha de desconto. **Não** clica em finalizar o pedido. `[VERIFICAR: se o código BLACK150 é aceito já no carrinho ou só na tela de pagamento]`.
2. Registrar a evidência: `python -m radar validar <id da oferta> --por "carrinho Amazon 21/11"`. Só isso sobe o status para VALIDADO.
3. Não é possível pelo radar: a conta exige login e 2FA, e automatizar carrinho em conta de compra é exatamente o tipo de ação que não faço sem sua ordem explícita. Navegador anônimo não avalia elegibilidade do cupom (depende da conta e do vendedor).
4. Uma leitura pública da página do produto pode mostrar um selo de cupom clicável, mas isso não substitui o passo 1.

## 6. Fontes, Telegram e WhatsApp (item 6)

- **As 5 fontes comunitárias seguem funcionando** (`radar status`, 15:33): Promobit (172 itens), Gatry (40), HardMOB (32), Pelando (20), Méliuz (118 cupons), mais Telegram público sem canais configurados. Zero falhas seguidas.
- **Telegram:** adaptador de usuário pronto, `telethon 1.46` instalado, **nenhuma credencial gravada e nenhuma sessão criada** (`telegram-status`). O login é seu, passo a passo em `docs/ecossistema/12-telegram-passo-a-passo.md`. Os canais a ler só entram na configuração depois do login.
- **WhatsApp:** nenhum grupo autorizado (`whatsapp-grupos`). O radar só envia ao seu chat e **não lê nenhum grupo**. Não existe leitor.
- **Bloqueios de rede social:** nada foi contornado. O Pelando continua por HTML público; o Chrome automatizado dele é bloqueado e fica assim. A estabilidade do radar não foi trocada por acesso a nenhuma fonte.

## 7. Homologação final (item 7)

| Verificação | Resultado | Evidência |
|---|---|---|
| Suíte completa | **847 testes, OK** (347 s; eram 798 no fim da fase 3, +49 desta fase) | `python -m unittest discover -s tests` |
| Cenários ponta a ponta | **22/22** | `python -m radar homologar` |
| Relatórios 08h, 14h e 20h preservados | tarefa "Rastrear Robos BF" `Ready`, última execução 14:00 com resultado 0, próxima 20:00 | `radar status` |
| Varredura a cada 10 min | `Ready`, última 15:30 com resultado 0 (já com o código novo), jobs sem falhas seguidas | `radar status` |
| Dedupe e ordem de prioridade | cenários P01, P02 e testes de prioridade | seção 2 |
| Alerta acima do limite comum | P03: CRÍTICO passa do orçamento comum e a repetição é suprimida | seção 2 |
| Expiração da fila | P04 (candidato vence em 30 min) e testes do outbox (alerta 30 min, relatório 24 h) | `test_radar_prioridade`, `test_radar_resiliencia` |
| Reconexão após queda da internet | P05: falha registrada, alerta guardado e entregue ao reconectar dentro da validade | cenário P05 |
| Recuperação após suspensão do notebook | recuperação automática do horário de relatório perdido (fase 3) e lacuna medida (seção 3) | `test_radar_recuperacao`, `test_radar_lacunas` |
| Integridade do histórico | 1 leitura suspeita já corrigida em `radar_correcoes.yaml`; nenhuma nova | `radar auditar` |
| Arquivos de outras sessões | 30 arquivos conferidos: intactos | `radar git-escopo --verificar` |
| Estado real dos agendamentos | 2 tarefas do radar `Ready`; "Zap vivo" `Ready` | `Get-ScheduledTask` |
| Segurança de credenciais | nenhum segredo na árvore; sem credencial nem sessão do Telegram; nenhum token no repositório | `checar-segredos --strict` e `telegram-status` |
| Alertas reais | **desligados** (`enviar: false`, `homologado_em` vazio); painel mostra "EM SOMBRA" | `python -m radar prioridade` |

## 8. Arquivos alterados e criados nesta fase

Alterados (já existiam na fase 3, ainda não commitados): `radar/db.py` (migração 4), `radar/modelos.py`, `radar/alertas.py`, `radar/varredura.py`, `radar/efetividade.py`, `radar/qualidade.py`, `radar/avaliacao.py`, `radar/cenarios.py`, `radar/cli.py`, `radar/git_escopo.py`, `config/radar_regras.yaml` (seção `prioridade`), `config/radar_fontes.yaml` (`cobertura_estimada_min`, `lista_estatica`), `config/radar_catalogo.yaml` (Q/f), `tests/corpus/radar_ofertas_rotuladas.yaml`, `tests/test_radar_resiliencia.py`, `tests/test_radar_git_escopo.py`.

Novos: `radar/prioridade.py`, `tests/test_radar_prioridade.py`, `tests/test_radar_avaliacao.py`, `tests/test_radar_cupons_guarda.py`, `tests/test_radar_lacunas.py`, este relatório.

Novos comandos: `radar prioridade`, `radar lacunas`, `radar git-escopo --baseline|--verificar|--backup-completo|--manifesto`.

Banco real: migrado para a versão 4 com backup automático antes (`radar-20261121-*-pre-migracao.db`). Reversão: `python -m radar migrar --reverter`.

## 9. Riscos restantes

1. **Cobertura do Promobit (18 min) com ciclo de 10 min:** margem curta, pior na Black Friday. Decisão sua: encurtar o ciclo ou aprofundar a paginação.
2. **Recall de mercado não provado** (n = 7). Só cresce com anúncios reais confirmados.
3. **Pesos, orçamentos e intervalos da prioridade são propostos por mim**, sem histórico de uso. Podem ficar apertados ou frouxos. Em sombra dá para ver o que seria enviado antes de ligar.
4. **HardMOB sem hora:** a cobertura de 120 min é estimativa. Oferta do HardMOB nunca ganha urgência.
5. **Notebook oficial desligado ou dormindo:** o radar roda só na máquina oficial (`LAPTOP-3NSQG27T`). Há detecção de lacuna e recuperação do relatório, mas não há como recuperar o que sumiu da lista durante a queda.
6. **Código sem commit:** 89 arquivos só existem nesta máquina e nos backups. Até o commit, outra máquina não os vê.
7. **STATUS.md misto:** commit do arquivo inteiro levaria a seção do Climatizador (outra sessão). Use o patch.
8. **Telegram sem login:** a fonte mais rápida de oferta de comunidade ainda está desligada.

## 10. Instruções de homologação (para você)

1. Ver o que o radar SELECIONARIA: `python -m radar prioridade` (de hoje até 27/11, deixar em sombra e conferir se as ofertas "selecionadas" valem mesmo avisar).
2. Ver lacunas: `python -m radar lacunas --horas 48`.
3. Ver o reconhecimento: `python -m radar avaliar`.
4. Testar o cupom no carrinho (seção 5) e registrar com `radar validar`.
5. Decidir o orçamento: ajustar a seção `prioridade` de `config/radar_regras.yaml`.
6. Só depois, para ligar alertas reais, preencher `alertas.enviar: true` e `alertas.homologado_em` com a data. Sem os dois, nada sai.
7. Autorizar o commit. O comando para ver exatamente o que entra é `python -m radar git-escopo --manifesto`; o patch do STATUS está em `...\dados-privados\radar\backups\STATUS.radar.patch`.
8. Opcional: login do Telegram, conforme `docs/ecossistema/12-telegram-passo-a-passo.md`.

## Efetividade é com você

Eu entrego o trabalho técnico e a prova do que foi medido, mas só você sabe o que o seu dia aguenta de notificação e quais ofertas valem interromper o que está fazendo. Antes da Black Friday, olhe a lista de "selecionados em sombra" e diga se aquelas são as ofertas que você realmente gostaria de ter recebido.
