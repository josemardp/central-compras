# 15. Relatório da fase 5: estabilização operacional e pré-Black Friday (21/11/2026)

Escopo: proteger o código, homologar a política de prioridade, auditar a latência, fechar o cruzamento de cupons, preparar o Telegram, escrever o plano de ativação e fazer a auditoria final. Nada foi commitado ou enviado ao GitHub. Alertas reais seguem desligados (modo sombra). Nenhuma mensagem foi enviada ao seu WhatsApp nesta fase.

## 10. Recomendação objetiva (resumo no topo)

**NÃO APTO hoje para ativar alertas reais.** O radar está tecnicamente sólido e pronto para a ativação controlada, mas faltam três evidências que nenhum teste substitui:

1. **O caminho ao vivo foi exercitado uma única vez.** Há 1 candidato real em sombra (Philco 18k, R$ 2.379, 7% abaixo do melhor preço monitorado, confirmado ativo na fonte). O mínimo do plano é 3, sem falso positivo.
2. **A entrega no WhatsApp nunca foi medida.** Só há estimativa (pelo menos 4 s). Só o teste controlado (1 mensagem rotulada TESTE ao seu chat) fecha isso, e ele é passo seu.
3. **O código não tem commit.** Até você autorizar, 98 arquivos só existem nesta máquina e nos backups.

`python -m radar ativacao` resume isso: veredito **NÃO APTO AINDA (itens PENDENTE)**, 0 FALHA. Ele passa a **APTO** sozinho assim que houver 3 candidatos reais em sombra, e depois é com você (seção 9).

**Aprovação nos testes não é eficácia comercial.** Os 8 cenários, a simulação e a suíte provam que a política faz o que foi desenhada. Que ela encontra boas ofertas inéditas só se prova com ofertas reais, e hoje existe 1.

## 1. Estado operacional

| Item | Estado | Evidência |
|---|---|---|
| Relatórios 08h, 14h e 20h | funcionando | tarefa `Central Compras - Rastrear Robos BF` `Ready`, última 14:00 com resultado 0, próxima 20:00 |
| Radar a cada 10 min | funcionando | tarefa `Central Compras - Radar Varredura` `Ready`, ciclos das 16:00 e 16:20 com resultado 0; maior intervalo real entre leituras 15 a 20 min |
| Cinco fontes comunitárias | funcionando | Promobit, Gatry, HardMOB, Pelando e Méliuz: 0 falhas seguidas, leitura há menos de 8 min (Méliuz a cada 90 min por desenho) |
| Banco SQLite | íntegro | versão 4 de 4, `integrity_check` ok |
| Histórico e correções | íntegros | `radar auditar`: 1 leitura suspeita, já corrigida em `radar_correcoes.yaml`; nenhuma nova |
| Trava de máquina oficial | ativa | `LAPTOP-3NSQG27T` é a oficial; teste simula outra máquina (nada coletado, enviado ou gravado) |
| Alertas reais | **desligados** | `enviar: false`, `homologado_em: null` |
| Telegram | não autenticado | credenciais NÃO, sessão NÃO, 0 canais |
| WhatsApp (leitura de grupos) | nenhum grupo autorizado | o radar só envia ao seu chat |

## 2. Testes e evidências

- **Suíte completa:** **892 testes, OK** (332 s; eram 847 no fim da fase 4, +45 desta fase).
- **Cenários de homologação:** 22/22 (`python -m radar homologar`).
- **Simulação da política:** 8 situações, 8/8 como esperado, com o histórico real lido (`python -m radar simular-prioridade`), e 11 testes dedicados.
- **Verificação prévia de ativação** (`python -m radar ativacao`): 19 OK, 0 FALHA, 1 PENDENTE (evidência ao vivo: 1 de 3 candidatos reais em sombra), 4 MANUAL (passos seus: conferir os alertas em sombra, teste de envio, commit, BLACK150).
- **Segredos:** `checar-segredos --strict` limpo; nenhuma credencial nem sessão do Telegram.
- **Git:** HEAD inalterado (`0b84a7a`); o `git status` só ganhou 3 arquivos de teste novos não rastreados (40 para 43 entradas); nenhum arquivo foi adicionado, commitado ou removido. 30 arquivos do Climatizador intactos (foto SHA-256).

### Defeitos achados e corrigidos nesta fase (todos com teste)

| # | Defeito | Como apareceu | Correção |
|---|---|---|---|
| 1 | **Ordem de chegada voltava por dentro do orçamento**: uma oferta mediana (pontuação 48) gastava vaga às 07:50 e a melhor da manhã (Loren Shower R$ 76,49, pontuação 73) era barrada às 08:50 | simulação do dia cheio (S8) | limiar de pontuação que sobe com as vagas usadas (40 na 1ª, 65 na 6ª); depois disso as 6 vagas foram para as melhores |
| 2 | **Perda silenciosa**: candidato que esperava vaga e vencia virava `expirado` genérico; o excedente do orçamento não aparecia em lugar nenhum | análise do despachante | estado explícito `retida_orcamento` com motivo, lista `retidas`, painel e bloco no relatório (só com alertas reais) |
| 3 | **Kill switch incompleto**: alerta que esperava na fila ainda seria entregue depois de desligar | leitura do `outbox.drenar` | a varredura descarta a fila de alertas quando desligados; `radar ativacao --desligar` limpa na hora |
| 4 | Cupom `100IMPRESSORA` (KaBuM) saía "potencialmente elegível" para robô aspirador | `radar cruzar` ao vivo | heurística de categoria no código ampliada (impressora, teclado, celular etc.); vira "descoberto" |
| 5 | Telegram aceitaria um id positivo (pessoa ou bot) colado por engano; mensagem do `telegram-listar` apontava para arquivo errado | revisão do módulo | id positivo recusado antes de ler, entidade conferida ao conectar, listagem só de canais por padrão |

## 3. Riscos remanescentes

1. **Evidência ao vivo mínima** (1 candidato real). Os pesos e limiares são propostas minhas.
2. **Cobertura do Promobit com margem curta**: pior momento medido 14 min, ciclo de 10 min (1,4x). Nenhuma lacuna real até agora, mas na Black Friday o volume sobe.
3. **HardMOB sem hora de postagem**: cobertura (120 min) é estimativa; nunca ganha urgência nem "relâmpago".
4. **Entrega no WhatsApp sem medida**: depende da aba do zap-vivo (CDP 9230) estar viva; o envio tem esperas fixas de pelo menos 4 s.
5. **Promoção de poucos minutos:** com ciclo de 10 min, a chance de ler pelo menos uma vez uma promoção de 5 min é ~50% (seção 4). O K800 de R$ 959, que durou menos de 10 min, é o caso típico.
6. **Código sem commit** e **STATUS.md misto** (use o patch).
7. **Notebook oficial dormindo ou sem rede**: a lacuna é detectada e registrada, mas o que sumiu da lista na queda não se recupera.
8. **Telegram sem login**: a fonte mais rápida de comunidade segue desligada.
9. **BLACK150 não validado**; nenhum cupom estava `VALIDADO` em nenhum momento.

## 4. Latências reais

Legenda: **[MEDIDO]** = tempo real gravado ou observado; **[ESTIMADO]** = cálculo ou limite, sem medida; **[NÃO MEDIDO]** = não há como medir hoje. Comando: `python -m radar latencia`. Os tempos internos passam a ser gravados a cada ciclo em `latencia.jsonl` (fora do Git).

### Do evento até a mensagem

| Etapa | Valor | Tipo | Como foi obtido |
|---|---|---|---|
| **Publicação → coleta, Promobit** | mediana **7,5 min**, p90 11,4, máximo 12,5 (n = 53 chegadas novas) | [MEDIDO] | 3 leituras das listas com 10 min de intervalo; idade (agora menos hora de publicação) dos itens que não estavam na leitura anterior. Resolução ~1 min ("há X min") |
| Publicação → coleta, Pelando | mediana 4,4 min (n = 3) | [MEDIDO], amostra pequena | idem |
| Publicação → coleta, Gatry | sem chegadas novas em 20 min | [NÃO MEDIDO] | a lista do Gatry quase não muda (0 itens novos) |
| Publicação → coleta, HardMOB | não existe | [NÃO MEDIDO] | a fonte não informa hora de postagem |
| Caso real (Philco 18k) | publicada 15:50, detectada **16:00:02** (~10 min) | [MEDIDO], n = 1 | banco real |
| Decomposição do atraso do Promobit | espera até o próximo ciclo (média ~5 min) + atraso da fonte (a idade mínima vista foi 2,4 min) | [ESTIMADO] | 7,5 menos 5 dá cerca de 2,5 min de atraso da própria fonte |
| **Coleta → classificação** | **0,37 ms** por oferta (máx 0,58 ms) | [MEDIDO] | cronômetro em cada ciclo real (7 registros); 170 ofertas custam ~0,1 s |
| **Classificação → criação do alerta** | candidato + mensagem **1,3 ms**; despacho menos de 0,1 s | [MEDIDO] (n = 1 candidato real) | idem |
| Leitura das fontes (dominante no ciclo) | Promobit 3,7 a 6,6 s, Gatry 1,1 a 1,8 s, HardMOB 1,0 a 1,3 s, Pelando 0,3 s | [MEDIDO] | idem |
| Ciclo completo da varredura | mediana **7,3 s**, máximo 8,8 s (limite da tarefa: 8 min) | [MEDIDO] (n = 3) | idem |
| **Criação → entrega no WhatsApp** | **pelo menos 4 s** (esperas fixas do envio: 0,8 s + 3,0 s, mais digitação) | **[ESTIMADO]** | nunca houve envio medido. O relatório das 20h de hoje grava o primeiro valor real (`envio_relatorio`); o teste controlado grava o de alerta |
| **Total estimado, Promobit** | **~7,7 min** na mediana (7,5 de leitura + menos de 10 s de processamento + ~4 s de envio) | parte medida, parte estimada | a entrega é o único pedaço sem medida |

O tempo é dominado pela **espera entre ciclos e pelo atraso da fonte**, não pelo código: o processamento inteiro cabe em menos de 10 s.

### Cobertura da lista contra o intervalo entre consultas

| Fonte | Ciclo configurado (real) | Cobertura da lista | Avaliação |
|---|---|---|---|
| Promobit | 10 min (mediana 10, maior 16) | **pior 14 min**, p10 18, mediana 39 | **margem curta** (1,4x no pior momento); sem lacuna real até agora |
| Gatry | 10 min | pior 973 min | suficiente |
| Pelando | 15 min configurado, **20 min real** | pior 58 min | suficiente; o ciclo efetivo é 20 porque a varredura roda de 10 em 10 min (15 vira 20) |
| HardMOB | 10 min | não medida (sem hora; estimativa 120 min) | indeterminada |
| Méliuz | 90 min | lista estática (cupons de loja) | não se aplica |

### A frequência atual capta promoção de poucos minutos?

Chance de a promoção ser lida **pelo menos uma vez**, com os horários reais dos ciclos (só considera o agendamento; a oferta ainda precisa estar na lista da fonte):

| Duração da promoção | Promobit, Gatry, HardMOB (10 min) | Pelando (20 min real) |
|---|:-:|:-:|
| 3 min | 29% | 16% |
| 5 min | 49% | 26% |
| 10 min | 97% | 52% |
| 15 min | 100% | 78% |

**Conclusão:** capta promoção de 10 minutos ou mais; **perde metade das de 5 min e a maioria das de 3 min**. O R$ 959 do K800 (duração menor que 10 min) estava no limite. Mesmo lendo, o alerta chega ~7,7 min depois da publicação, então uma promoção de 10 min deixa cerca de 2 min para você agir.

**Não recomendo aumentar tudo.** A fonte que gera chegadas novas é o Promobit (53 itens novos em 20 min, contra 0 do Gatry e 3 do Pelando). Opção barata e dirigida, **não aplicada, decisão sua**: na Black Friday, uma leitura LEVE a cada 5 min só da 1ª página do Promobit (1 requisição a mais por 5 min; 1 página cobre ~9 min), mantendo o resto em 10 min. Isso leva a chance de ler uma promoção de 5 min do Promobit de ~49% para perto de 100%. Exige trocar a tarefa agendada para 5 min com as outras fontes respeitando o próprio intervalo.

## 5. Ofertas detectadas e descartadas

**Leitura de 24 h (telemetria desde 10:23):** 8.585 publicações coletadas nas fontes; **1** casou com os seus 12 produtos.

| Destino | Quantidade | Observação |
|---|---|---|
| fora do catálogo | 5.367 | outros produtos |
| cupom de loja sem produto | 3.093 | só informativo, nunca alerta |
| quase casou: mesma marca, outro produto | 98 | ex.: Tapo câmera, KaBuM Smart 900 |
| quase casou: outra capacidade (BTU) | 14 | 9k e 24k no lugar de 12k/18k |
| quase casou: outra tensão | 8 | 127V no lugar de 220V |
| quase casou: acessório | 4 | filtro, escova |
| **candidato real em sombra** | **1** | ver abaixo |

**A única oferta real:** `Philco Eco Inverter 18.000 BTU` na WebContinental, R$ 2.379,00, cupom `PHI200` (NAO_CONFIRMADO, desconto não contado), Promobit, publicada às 15:50 e detectada às 16:00:02. Classe ALTA, pontuação 64, 7% abaixo do melhor preço atual (R$ 2.569). Orçamento comum 1 de 6. A revalidação na fonte devolveu **ativa (APPROVED)**. Em sombra, não foi enviada. Fica para você decidir: o preço de R$ 2.379 já inclui o cupom ou não? O radar não sabe.

**Cupons de loja cruzados com os preços** (`radar cruzar`, ao vivo): 421 pares; **7 potencialmente elegíveis** (economia só estimada), 318 descobertos sem regra suficiente, 96 inaplicáveis. Nenhum validado.

## 6. Política de prioridade recomendada

Manter como está **mais** o limiar progressivo (seção 2, defeito 1), que é a única mudança. Configuração experimental preservada:

| Parâmetro | Valor |
|---|---|
| alertas comuns por dia | 6 |
| alertas críticos por dia | 3 |
| alertas de exceção por dia (pontuação 80 ou mais) | 2 |
| máximo por varredura | 2 |
| pontuação mínima / limiar da última vaga comum | 40 / 65 |
| repetição do mesmo produto | 90 min (30 min se crítico), ou melhora de 5% |
| validade de candidato | 30 min; revalidação na fonte se esperou mais de 5 min |

### Simulação: o que seria enviado, adiado, substituído, retido ou descartado

Histórico real lido, banco temporário, nada enviado. Log completo no [anexo 15-A](15-anexo-simulacao-prioridade.md).

| Situação | Resultado |
|---|---|
| **S1** três ofertas importantes ao mesmo tempo (K800 R$ 959, Dreame R$ 1.102, Philco R$ 2.099) | pontuações 83, 90 e 87. Saem **2 na varredura** (Dreame, Philco); o K800 fica **adiado** e sai no ciclo seguinte. 3 enviadas, 0 perdidas |
| **S2** excepcional depois do orçamento esgotado | orçamento comum 2 gasto; K800 (83) usa a **vaga de exceção**; Dreame (90) chega depois: **RETIDA** com motivo "orçamento diário e de exceção esgotados", listada em `retidas` |
| **S3** reduções sucessivas do Dreame (1.100, 1.080, 1.060, 1.000, 940) | envia 1.100; 1.080 e 1.060 **descartadas por repetição** (menos de 5% melhor); 1.000 e 940 enviadas (melhora acima de 5%) |
| **S4** mesmo cupom em Promobit, Gatry e Pelando | **1 mensagem**; as duas cópias ficam **substituídas** pela melhor do mesmo produto; quarta cópia em ciclo seguinte barrada por repetição |
| **S5** promoção expira antes do envio | a que esperava vaga é revalidada na fonte (encerrada), **descartada**, nada enviado |
| **S6** oferta aguardando vaga (1 por varredura, validade 15 min) | uma sai no ciclo seguinte; a de menor pontuação vence esperando e fica **RETIDA, visível** |
| **S7** WhatsApp indisponível | falha registrada, alerta **guardado na fila**; volta em 12 min: **entregue revalidado**; volta só em 50 min: **descartado** (não entrega oferta velha) |
| **S8** dia cheio: 24 ofertas reais reencenadas, 1 a cada 10 min | 6 enviadas (Dreame 90, K800 83, Philco 77 e 79, Loren Shower 81 e 73), 3 por repetição, 7 abaixo da pontuação mínima, **4 retidas** (Elgin 12k, Agratto, Midea, todas pontuação 45 a 53), nenhuma pendente |

**Perda silenciosa:** resolvida no sentido de que toda oferta decente que não virou alerta tem estado e motivo (`retida_orcamento`), aparece em `radar prioridade` e, com alertas reais ligados, em um bloco no relatório seguinte das 08/14/20h. Continua existindo **perda por desenho** (a oferta retida não vira alerta): o orçamento é um limite de atenção, não de cobertura.

## 7. Estado do Git

Nada commitado. HEAD `0b84a7a`.

| Conjunto | Arquivos | Entra no commit do radar? |
|---|---|---|
| Radar (código, config, testes, docs, corpus; inclui os 6 rastreados modificados) | 98 | **sim** (lista exata: `python -m radar git-escopo --manifesto`) |
| Climatizador (outra sessão) | 30 | **não** (`config/categorias.yaml`, `produtos/climatizador/`, `projetos/2026-climatizador-...`, `base-conhecimento/especificacoes/climatizador.md`) |
| `STATUS.md` (misto) | 1 | **só as seções do radar**, pelo patch validado; a seção do Climatizador fica de fora |
| Rastreados modificados do radar | 6 | sim: `requirements.txt`, 3 scripts `rastrear_*`, `rodar_rastreador_robos.ps1`, `tests/test_rastrear_chuveiro_bf.py` (nenhuma menção ao Climatizador) |

Verificado: nenhum arquivo do Climatizador está na lista do radar; 0 ocorrências de "climatizador" nos diffs dos rastreados; só um módulo (`git_escopo.py`) e docs citam o nome, para classificar. Segredos: limpo. Backup recente com restauração testada.

**Escopo final proposto para a sua autorização** (nada executado):

```
git add config/radar_*.yaml docs/ecossistema/ radar/ tests/corpus/ tests/test_radar_*.py
git add requirements.txt scripts/rastrear_ares_bf.py scripts/rastrear_chuveiro_bf.py scripts/rastrear_robos_bf.py scripts/rodar_rastreador_robos.ps1 tests/test_rastrear_chuveiro_bf.py
git apply --cached <pasta de backups>\STATUS.radar.patch
git commit -m "feat(radar): radar de compras V3 (central-compras dono unico das automacoes)"
git push origin main
```

Antes do `git add`, rode `python -m radar git-escopo --manifesto` de novo (a lista pode ter mudado) e confira que não aparece `climatizador`. Conferir também o remote da conta certa antes do push.

## 8. Pendências de autenticação

- **Telegram (seu):** criar o app em my.telegram.org, `python -m radar telegram-login` no seu PowerShell, `telegram-listar`, colar só os canais de oferta em `config/radar_fontes.yaml`. Guia: `docs/ecossistema/12-telegram-passo-a-passo.md`. Id de pessoa é recusado; o Coral não é tocado.
- **WhatsApp:** nenhuma autenticação nova. O envio usa a aba do zap-vivo (já pareada). O teste controlado (`homologar --enviar-teste-whatsapp --confirmo`) é seu.
- **Amazon (BLACK150):** teste no carrinho até a tela de pagamento, sem finalizar, e `radar validar`. Depende do seu login.
- **GitHub:** conferir a conta do remote antes do push (nunca passar token no chat).

## 9. Procedimento de ativação

Plano completo, com verificação prévia, conferência em sombra, teste da fila, ativação explícita, monitoramento, critérios de desligar e rollback: [16-plano-de-ativacao.md](16-plano-de-ativacao.md). Resumo:

1. `python -m radar ativacao` (só leitura) até dar **APTO**.
2. `python -m radar prioridade --horas 72` e aprovar cada alerta em sombra (mínimo 3 reais, 0 falso positivo).
3. `python -m radar homologar --enviar-teste-whatsapp --confirmo` (1 mensagem TESTE ao seu chat).
4. Editar `enviar: true` e `homologado_em` (seu).
5. Acompanhar os primeiros ciclos; desligar com `python -m radar ativacao --desligar` ao primeiro sinal de falso positivo recorrente.

## Comandos novos desta fase

`radar simular-prioridade`, `radar latencia`, `radar ativacao` (`--desligar`), `radar prioridade` (agora com retidas), `radar telegram-listar --grupos`, `radar cruzar` (com estágios).

## Arquivos desta fase

Alterados: `radar/prioridade.py`, `radar/varredura.py`, `radar/ciclo.py`, `radar/outbox.py`, `radar/cruzamento.py`, `radar/telegram_conta.py`, `radar/cenarios.py`, `radar/cli.py`, `config/radar_regras.yaml`, `config/radar_fontes.yaml`, `tests/` (prioridade, resiliência, telegram, cupons), docs 07, 09, 10, 11, 12.
Novos: `radar/simulacao.py`, `radar/latencia.py`, `radar/ativacao.py`, `tests/test_radar_simulacao.py`, `tests/test_radar_latencia.py`, `tests/test_radar_ativacao.py`, docs 15, 15-A e 16.

## Efetividade é com você

Eu entrego a política testada, a simulação e as evidências do que foi medido. Só você sabe quantos alertas por dia o seu celular e a sua rotina aguentam e se um "7% abaixo do melhor preço" no Philco 18k é o tipo de oferta que merece te interromper. O limiar de pontuação e o orçamento são chutes bem fundamentados até você ver os primeiros alertas reais em sombra e dizer quais teria querido receber.
