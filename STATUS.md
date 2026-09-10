# STATUS: Central de Compras

> Doc de handoff. Qualquer máquina ou agente retoma a partir daqui.
> Estado do **repositório**. O estado de cada compra fica em
> `projetos/<projeto>/processo.md`, ou rodando
> `python scripts/central_compras.py status projetos/<projeto>`.

## AO RETOMAR — comece por aqui (10/09/2026, sessao 24)

**Proximo passo:** submeter a correcao da sessao 24 a uma nova revisao
independente da frente 6. Os 2 achados sobre `ad6a04a` foram corrigidos
(ver bloco abaixo). Nao declarar a frente 6
concluida ainda: precisa de nova revisao
independente que passe limpa antes de considerar "concluida sob reserva".

**Pendencias / bloqueios:**
- **Frente 5 (produtos reutilizados): CONCLUIDA SOB RESERVA** - a 7a
  revisao independente (Astra), sobre o commit `5998a15`, passou limpa:
  456 testes oficiais, 25 testes externos das rodadas anteriores e 3
  controles novos, sem achado. Historico completo (6 rodadas, 19 achados
  reais corrigidos) preservado nas secoes anteriores deste arquivo e na
  secao 5 do plano. Migracao de produtos legados
  (`migrar-produtos --aplicar`) continua **nao executada** contra a arvore
  real - so o preview foi conferido em cada rodada.
- **Frente 6 (datas/veredito): AINDA NAO CONCLUIDA.** Implementada na
  sessao 20; 3 rodadas de revisao independente (Astra) ja acharam 5,
  depois 4, e agora mais 2 falhas reais. As 2 primeiras rodadas foram
  corrigidas e testadas nos commits `3acc96a` e `ad6a04a`; a 3a rodada
  (sessao 23) foi corrigida na sessao 24. **Nao considere a frente
  6 encerrada depois de apenas rodar a suite local** - a frente 5 levou
  7 rodadas ate uma revisao passar limpa. **Achado transversal da 2a
  rodada, registrado para nao se repetir**: `_assinaturas_compativeis`
  (mecanismo
  COMPARTILHADO por TODO `tracked_operation` - `decidir`,
  `registrar-evento`, `vincular-produto`, `aprender-veredito`), criada na
  1a rodada pra tolerar evolucao de schema, comparava valores com `==` do
  Python, que confunde `False` com `0` mesmo dentro de estruturas
  aninhadas - uma correcao num mecanismo COMPARTILHADO pode quebrar
  QUALQUER comando que passa por ele, nao so o que motivou a correcao;
  antes de mexer em `tracked_operation`/`_assinaturas_compativeis`/
  `_valores_equivalentes` de novo, rode a suite completa E pense em quem
  MAIS usa esse mecanismo (`grep -n "tracked_operation(" scripts/central_compras.py`).
  Os outros 3 achados desta rodada repetem o padrao ja visto: validar
  ANTES de criar journal/escrever (nunca deixar pendencia por entrada
  invalida), recuperar de evidencia PERSISTIDA em vez de exigir campo
  novo no journal, e replicar o MESMO contrato de validacao em todo
  caminho que grava o mesmo dado (aqui, cronologia em `decidir` E
  `registrar-evento`).
- Frentes 2 e 3 continuam "concluidas sob reserva" - ja levaram 7 e 3
  rodadas de revisao do Codex respectivamente, cada uma achando lacuna
  nova. Se pedirem revisao de novo, **nao presuma que passou so porque
  passou antes**; leia as secoes 2 e 3 do plano inteiras antes de mexer.
- Nenhum passo manual pendente do Josemar neste momento.

**Frente 6, 3a correcao da revisao independente (10/09/2026, sessao 24).**
Os 2 achados da sessao 23 foram reproduzidos antes da correcao e viraram
testes permanentes em `tests/test_frente6_datas_veredito.py`, classe
`QuartaRevisaoIndependenteFrente6Test`.

- `decidir --comprado` implicito recupera a data de journal antigo pelo
  nome congelado do veredito ou por `iniciado_em`, quando falta
  `data_compra_efetiva`. Sem evidencia valida, recusa a retomada;
  nao usa mais o dia atual como ultimo recurso.
- `registrar-evento` revalida a cronologia de journals pendentes legiveis
  com a data persistida. Um journal antigo vazio, deixado por uma recusa,
  nao autoriza a gravacao do evento invalido; continua pendente para
  reconciliacao manual. Journals ilegiveis mantem a recusa existente.

**Verificacao:** os 4 testes externos de
`%TEMP%\astra_review_ad6a04a.py` passaram (2 achados + 2 controles).
Os testes direcionados de datas/veredito (51), recuperacao (35) e
participacoes (59) passaram. Suite completa: **508 testes, 0 falhas**.
`auditar-decisoes --strict`, `operacoes-pendentes --strict`,
`checar-segredos --strict` e `git diff --check` passaram; a auditoria
continua sinalizando o snapshot legado sem manifesto de entradas.
Nenhuma migracao real, alteracao de pesos/gates ou reescrita de historico.
Detalhes na secao 6 de `docs/plano-pendencias-auditoria-2026-09-06.md`.
**Frente 6 ainda nao concluida: falta nova revisao independente limpa.**

**Frente 6, 3a revisao independente (09/09/2026, sessao 23).**
A Astra revisou o commit `ad6a04a` depois da 2a correcao da frente 6.
Baseline confirmado: suite oficial **506 testes, 0 falhas**; os 14 testes
externos das revisoes anteriores tambem passam. A nova revisao externa
adicionou 4 testes em sandbox isolado (`%TEMP%\astra_review_ad6a04a.py`):
2 controles passam e 2 achados falham contra o codigo atual. Resultado:
o commit `ad6a04a` melhora a frente 6, mas ainda nao fecha a frente.

1. **Journal antigo de `decidir --comprado` implicito troca a data da
   compra ao retomar depois de upgrade.** Um journal real criado pelo
   codigo do commit `e564618` antes de gravar o veredito, com
   `--comprado` sem `--data-compra`, nao tinha `data_compra_efetiva`,
   mas tinha a evidencia persistida da data original em `iniciado_em` e
   no nome congelado do veredito. Ao retomar em `ad6a04a` no dia
   seguinte, `_decide_writes` cai em `today()` e grava a data da retomada
   como `Data da compra`. Isso viola o contrato da frente 6: fato
   datado implicito precisa ser congelado pela tentativa original, nunca
   fabricado pelo dia da retomada. O executor deve recuperar da evidencia
   persistida quando possivel; se for ambiguo, deve recusar com mensagem
   clara em vez de inventar uma data.
2. **Journal antigo de `registrar-evento` deixado por uma recusa da
   versao anterior vira execucao valida depois do upgrade.** No commit
   `3acc96a`, `registrar-evento --evento entrega` com `--data` omitida
   validava a cronologia tarde demais: recusava entrega "hoje" depois de
   `inicio_uso` ontem, mas deixava um journal pendente vazio
   (`passos: {}`). Em `ad6a04a`, a existencia desse journal faz a
   validacao previa ser pulada como se a tentativa anterior tivesse sido
   validada; a retomada entao grava exatamente o evento que a versao
   anterior recusou. Existir journal pendente nao prova validacao
   concluida; a retomada precisa validar a data congelada real da
   tentativa ou tratar journal sem efeitos como pendencia invalida a
   reconciliar.

**Prompt recomendado ao Claude Code:** corrigir esses 2 achados sobre
`ad6a04a`, reproduzindo ambos antes de mexer com o script externo da
Astra; transformar os cenarios em testes permanentes; manter os controles
de retomada valida em outro dia e de recusa nova sem journal; rodar suite
completa, `auditar-decisoes --strict`, `operacoes-pendentes --strict`,
`checar-segredos --strict` e `git diff --check`; atualizar STATUS/plano;
commitar e fazer push na `main`. Nao mexer em pesos/gates, nao rodar
migracao real de produtos, nao reescrever snapshots/vereditos historicos
e nao declarar a frente 6 concluida nesta correcao.

**Frente 6, 2a correcao da revisao independente (09/09/2026, sessao 22).**
A Astra reproduziu 4 falhas reais contra o commit `3acc96a` (sessao 21,
que corrigiu as 5 anteriores), com o script `astra_review_3acc96a.py` (6
testes: 4 achados + 2 controles, todos reproduzidos ANTES de corrigir -
o baseline confirmou 498 testes oficiais + 8 testes externos anteriores
passando). As 4 viraram teste permanente em
`tests/test_frente6_datas_veredito.py`
(`TerceiraRevisaoIndependenteFrente6Test`: 8 testes - os 4 achados + 4
controles).

1. **Regressao transversal: `_assinaturas_compativeis` confundia `False`
   com `0`.** A comparacao usava `==` do Python, que trata `bool` como
   subclasse de `int` (`False == 0` e `True == 1` sao `True`) - inclusive
   dentro de estruturas aninhadas como `requisitos_atendidos`. Um
   `vincular-produto --requisito uso=false` interrompido antes de gravar
   a participacao, retomado com `uso=0` (INTEIRO, nao bool), era aceito
   como "mesma retomada" - a participacao gravada ficava com `uso=0`, que
   `gate_eliminations` (checagem `is False`, nao `==`) nao corta, e o
   candidato virava elegivel. Corrigido com `_valores_equivalentes`, uma
   igualdade mais estrita (bool nunca equivale a int do mesmo valor,
   recursiva em dict/list) usada em toda comparacao de assinatura -
   beneficia TODO `tracked_operation` (`decidir`, `registrar-evento`,
   `vincular-produto`, `aprender-veredito`), nao so o caminho que motivou
   o achado.
2. **Complemento de `decidir --comprado` nao recuperava `--data-compra`
   explicita de journal de versao anterior.** `_decide_writes` so
   consultava `op.detalhe.get("data_compra_efetiva")` - um journal real
   criado pelo codigo do commit `e564618` (que ja tinha `--data-compra`,
   mas ainda nao o campo `data_compra_efetiva` congelado, adicionado so
   na rodada anterior) perdia a data explicita na retomada apos o
   upgrade. Corrigido: `args.data_compra` explicita e o proprio dado de
   ENTRADA da chamada (deterministico em qualquer tentativa, nao depende
   de ter sido congelado nenhuma vez) - passa a ter prioridade sobre o
   valor congelado, que so continua servindo pro caso implicito
   (`--comprado` sem `--data-compra`, onde `today()` da 1a tentativa
   ainda precisa ser preservado).
3. **`registrar-evento` com `--data` omitida validava cronologia DEPOIS
   de criar o journal.** A checagem cronologica so rodava com valor
   conhecido quando `--data` era explicita; com `--data` omitida, a
   unica checagem acontecia DENTRO do `tracked_operation`, ou seja, DEPOIS
   do journal ja criado e persistido (`situacao: em_andamento`). Uma
   recusa por cronologia impossivel (ex.: `entrega` com data-padrao hoje
   depois de `inicio_uso` ontem) deixava esse journal pendente pra tras -
   e corrigir a data manualmente na chamada seguinte (`--data ontem`)
   virava "argumento diferente" contra o proprio journal invalido que a
   recusa tinha deixado. Corrigido: a validacao roda ANTES de
   `tracked_operation` ser chamado, usando `args.data or today()` (o
   mesmo valor que seria congelado se a chamada passasse) - uma chamada
   invalida nunca chega a criar journal nenhum. Pulada so numa retomada
   legitima (`has_pending_operation` ja confirma que a validacao real
   rodou na tentativa original).
4. **Complemento de compra em `create_verdict` nao aplicava a validacao
   cronologica de `registrar-evento`.** `inicio_uso` registrado ontem, e
   `decidir --comprado --data-compra hoje` (posterior ao inicio de uso)
   era aceito sem checagem - o MESMO dado (`Data da compra`) tinha
   contratos DIFERENTES dependendo de qual comando gravava. Corrigido com
   `_erro_cronologia_evento`, funcao unica compartilhada entre
   `registrar-evento` e o complemento de `decidir` - recusa ANTES de
   tocar em decisao.md/processo.md/snapshot/veredito, mesmo padrao do
   achado 3 (pula a checagem numa retomada legitima de `decidir`).

**Verificacao (sessao 22):** suite completa **506 testes, 0 falhas**
(498 + 8 novos). Mutacao aplicada nas 4 correcoes de fundo, uma de cada
vez, desfeita e restaurada em seguida: derrubou exatamente os testes do
mecanismo mutado (1o: 2; 2o: 1; 3o: 2 - 1 falha direta + 1 efeito em
cascata, mesma causa; 4o: 1), nenhum fora disso.
`tests/test_participacoes.py` (que exercita `vincular-produto`, tambem
afetado pela regressao transversal do achado 1) reconferido, 59 testes,
0 falhas. `auditar-decisoes --strict`, `operacoes-pendentes --strict`,
`checar-segredos --strict` e `git diff --check` limpos contra a arvore
real. Nenhuma migracao rodada contra produtos reais, pesos/gates
intocados. Detalhe completo:
`docs/plano-pendencias-auditoria-2026-09-06.md`, secao 6.

## Sessao anterior (09/09/2026, sessao 21) — historico

**Frente 6, 1a correcao da revisao independente (09/09/2026, sessao 21).**
A Astra reproduziu 5 falhas reais contra o commit `e564618` (sessao 20,
que implementou a frente 6 pela primeira vez), com o script
`astra_review_e564618.py` (8 testes: 5 achados + 3 controles, todos
reproduzidos ANTES de corrigir). As 5 viraram teste permanente em
`tests/test_frente6_datas_veredito.py`
(`SegundaRevisaoIndependenteFrente6Test`: 16 testes - os 5 achados + 8
controles + 3 testes de cobertura adicional pedida explicitamente
- travas, recursos reivindicados, falha intermediaria, retomada).

1. **`registrar-evento --evento comprado` nao sincronizava o estado
   operacional.** O veredito recebia a data, mas `processo.md`/
   `briefing.md` continuavam dizendo "pesquisando"/"comprar ou marcar
   como comprado". Corrigido: `_marcar_projeto_comprado` (extraida da
   logica que `decidir --comprado` ja tinha) roda tambem aqui - MAS SO
   quando o veredito e comprovadamente o da decisao ABERTA agora
   (`_projeto_da_confirmacao_de_compra` confere `Projeto`/`Produto ID` do
   veredito contra `decisao.md`); um veredito de decisao ja substituida,
   ou standalone sem `Produto ID`, nunca mexe no estado - so avisa.
2. **2a chamada de `decidir --comprado` nao complementava o veredito ja
   criado.** `create_verdict` retornava direto porque o arquivo ja
   existia - o projeto ficava marcado comprado, mas o veredito sem `Data
   da compra`. Corrigido: quando o arquivo ja existe e nao ha `--force-
   veredito`, complementa SO `Data da compra` se ainda estiver em branco
   (nunca sobrescreve uma ja registrada, nunca mexe no resto do
   conteudo) - nao precisa apagar/recriar o veredito so pra confirmar uma
   compra que chegou depois.
3. **Retomada em outro dia trocava a data da compra.** `decidir
   --comprado` sem `--data-compra` interrompido ANTES de criar o veredito,
   retomado no dia seguinte, gravava a data da RETOMADA como data da
   compra. Corrigido: `data_compra_efetiva` e calculada e congelada em
   `op.detalhe` na 1a tentativa (mesmo mecanismo ja usado para
   `snapshot_rel`/`veredito_nome`), nunca recalculada numa retomada.
4. **Journal de versao anterior a frente 6 parava de ser retomavel.** A
   assinatura de `decidir` ganhou o campo `data_compra`; um journal real
   criado pelo codigo de `5998a15` (sem esse campo), apos atualizar o
   codigo, era recusado como "dados diferentes" so por causa da propria
   evolucao do schema. Corrigido com `_assinaturas_compativeis`: um campo
   AUSENTE na assinatura antiga so e compativel com o valor ATUAL se for
   o default neutro (None/False/vazio) - um valor PREENCHIDO continua
   recusado (protecao contra argumento realmente diferente preservada,
   testada em separado).
5. **Cronologia de `registrar-evento` so validava pra tras.** Registrar
   `inicio_uso` ontem e depois `entrega` hoje era aceito, mesmo sendo
   cronologicamente impossivel (entrega tem que vir ANTES do inicio de
   uso) - a checagem so olhava os eventos ANTERIORES na ordem
   (`comprado`→`entrega`→`inicio_uso`), nunca os posteriores ja
   registrados. Corrigido com um segundo loop simetrico checando os
   eventos posteriores.

**Achado colateral do proprio pacote, corrigido junto:** como a
sincronizacao do achado 1 passou a gravar `processo.md`/`briefing.md`
alem do veredito, `registrar-evento` ganhou o proprio `tracked_operation`
(mesmo mecanismo de `decidir`/`aprender-veredito`) - uma falha ENTRE
gravar o evento no veredito e sincronizar o projeto fica pendente e
RETOMAVEL (testado com crash injetado), o projeto e reivindicado como
recurso ANTES de escrever (bloqueia contra um `decidir` concorrente no
mesmo projeto, tambem testado), e a data efetiva tambem e congelada em
`op.detalhe` pelo mesmo motivo do achado 3.

**Verificacao (sessao 21):** suite completa **498 testes, 0 falhas**
(482 + 16 novos). Mutacao aplicada nas 5 correcoes de fundo, uma de cada
vez, desfeita e restaurada em seguida: derrubou exatamente os testes do
mecanismo mutado (1o: 3; 2o: 1; 3o: 1; 4o: 1, so depois de corrigir o
proprio teste pra usar o commit `5998a15` - o correto pra achado 4 - em
vez de `e564618`, que ja tinha o campo novo; 5o: 1), nenhum fora disso.
`auditar-decisoes --strict`, `operacoes-pendentes --strict`,
`checar-segredos --strict` e `git diff --check` limpos contra a arvore
real. Nenhuma migracao rodada contra produtos reais, pesos/gates
intocados. Detalhe completo:
`docs/plano-pendencias-auditoria-2026-09-06.md`, secao 6.

## Sessao anterior (09/09/2026, sessao 20) — historico

**Frente 6 - Datas e vereditos (09/09/2026, sessao 20).** Pedido do
Josemar: separar data da decisao, compra/pagamento, entrega e inicio de
uso; D+30/D+180 tem que contar do inicio de uso EXPLICITAMENTE
registrado, nunca fabricado a partir de hoje/decisao/compra/entrega;
cotacao manual confirma oferta, nao compra realizada.

Inventario ANTES de mexer (agente Explore dedicado, depois conferido a
mao): `create_verdict` (chamada por `decidir`) fabricava
`Veredito D+30/D+180 previsto` como `hoje()+30/180 dias` na CRIACAO do
veredito - ancorado na data da decisao, nunca no uso real. `Data da
compra` dependia de `quote.fonte == 'manual'`, nao da flag `--comprado` -
um `decidir --comprado --permitir-web` (cotacao web) nao registrava data
nenhuma, e um `decidir` comum com cotacao manual registrava `Data da
compra` sem nenhuma confirmacao de pagamento. Nao existia campo nem
comando para entrega ou inicio de uso. `novo-veredito` (caminho
standalone) ja nao preenchia os previstos - inconsistente com `decidir`.

**Corrigido:**
- `templates/veredito.md`: campos novos `Data de entrega`/`Data de
  inicio de uso`, ao lado de `Data da compra`.
- `create_verdict`: `Data da compra` passa a depender SO de `comprado`
  (de `args.comprado`, nunca da fonte da cotacao) + `data_compra`
  opcional (`--data-compra`, so aceito junto de `--comprado` - `decidir`
  recusa a combinacao errada ANTES de qualquer escrita).
  `Veredito D+30/D+180 previsto` ficam em BRANCO na criacao.
- Comando novo `registrar-evento <veredito> --evento
  {comprado,entrega,inicio_uso} [--data AAAA-MM-DD]`: grava o evento no
  veredito ja existente. Recusa ANTES de escrever se o evento ja estava
  registrado (fato datado nao e sobrescrito - mesmo principio ja usado
  para `cotacoes.csv` e participacao invalida) e se a data e
  cronologicamente anterior a um evento anterior ja registrado; registrar
  sem os anteriores existirem e permitido. So `inicio_uso` recalcula
  `Veredito D+30/D+180 previsto`, e so quando a fase ainda nao foi
  RESPONDIDA (preserva veredito ja preenchido). `--data` recusa formato
  invalido e data no futuro. Protegido pelo mesmo mecanismo de trava que
  `preencher-veredito`/`decidir` - operacao pendente no MESMO veredito
  bloqueia, com recuperacao real testada via crash injetado.
- `phase_status` (painel): mensagem "sem previsto ainda" mudou de "sem
  data" pra "aguardando inicio de uso" - conferido visualmente no
  dashboard HTML gerado em sandbox.
- Registros antigos: NENHUM veredito existente foi reescrito. Um veredito
  com `Veredito D+30 previsto` ja fabricado pela formula antiga continua
  calculando status normalmente - `phase_status` so LE, nunca recalcula
  por conta propria. `Data da compra` legada nunca vira inicio de uso por
  inferencia.
- Fora do escopo, deliberadamente: pesos/gates/estrela intocados; nenhuma
  migracao rodada contra produtos reais; nenhuma infraestrutura externa
  tocada (Sheets so exporta `data_decisao`, nunca veredito - confirmado
  no inventario); `painel.py` (servidor local) nao expoe `decidir` nem
  comandos de veredito hoje - frente 6 e 100% CLI, sem UI propria a
  atualizar.

**Verificacao (sessao 20):** `tests/test_frente6_datas_veredito.py`, 25
testes novos (separacao de datas, previsto ancorado em inicio de uso,
integridade de `registrar-evento`, fluxo completo ponta a ponta com
`auditar-decisoes --strict` no final, compatibilidade com registro
legado) + 1 teste novo em `test_templates.py`. Datas relativas ao dia real
da execucao ou controladas via `patch.object(cc, "today", ...)` de forma
autoconsistente - nunca comparadas contra `dt.date.today()` nao mockado -
pra nao quebrar conforme o calendario avanca. Mutacao aplicada nos 3
mecanismos de fundo, cada uma desfeita e restaurada em seguida: derrubou
exatamente os testes do mecanismo mutado (1o: 4 diretos + 2 colaterais em
cascata, mesma causa; 2o: 1; 3o: 4), nenhum fora disso. Suite completa:
**482 testes, 0 falhas** (456 + 25 + 1). `auditar-decisoes --strict`,
`operacoes-pendentes --strict`, `checar-segredos --strict` e
`git diff --check` limpos. Fluxo conferido visualmente ponta a ponta num
SANDBOX ISOLADO (copia de config/templates/scripts, nunca a arvore real).

**Licao registrada para a proxima sessao:** `scripts/central_compras.py`
resolve `ROOT` a partir do proprio `__file__`, nao do diretorio de
trabalho - rodar o SCRIPT REAL com `cwd` diferente NAO isola nada, ele
sempre escreve na arvore real. Isolar de verdade exige uma COPIA do
script (`ambiente.montar` faz isso). Nesta sessao isso foi tentado por
engano uma vez (`cd /tmp/sandbox && python c:/projetos/.../central_compras.py
...`), criou projeto/veredito de teste na arvore real - identificados via
`git status` (tudo untracked) e removidos antes do commit, nunca
versionados. Detalhe completo:
`docs/plano-pendencias-auditoria-2026-09-06.md`, secao 6.

## Sessao anterior (09/09/2026, sessao 19) — historico

**Frente 5, 6a correcao da revisao independente (09/09/2026, sessao 19).**
A Astra reproduziu 1 falha real contra o commit `88ba7c2` (sessao 18, que
tinha corrigido as 2 anteriores), com o script `astra_review_88ba7c2.py`
(2 testes: 1 achado + 1 controle, ambos reproduzidos ANTES de corrigir - o
controle ja passava contra o codigo antigo, confirmando que a lacuna era
so no caso invalido). Virou teste permanente em `tests/test_participacoes.py`
(`SextaRevisaoIndependenteFrente5Test`: 5 testes - reproducao do achado,
inclusao no manifesto, imutabilidade apos alteracao posterior, controle da
distincao evidencia-vs-elegibilidade, e controle do caso valido sem
cotacao).

**O achado.** Um produto com participacao INVALIDA e SEM NENHUMA cotacao
desaparecia por completo da evidencia de uma decisao - nem a ficha nem a
participacao apareciam em nenhum arquivo do snapshot, e
`auditar-decisoes --strict` passava mesmo assim. Causa: a correcao da
sessao 17 fez `project_candidate_ids`/`project_discarded_candidate_ids`
excluirem participacao invalida dos dois conjuntos DE PROPOSITO (nao e
"ativo" nem "descartado" confirmado) - correto para elegibilidade, mas
`project_product_ids` (usado pelo loop de captura do snapshot em
`_decide_writes`) e so a uniao desses dois conjuntos com quem tem cotacao.
Sem cotacao E excluido dos dois conjuntos, o produto nunca entrava em
`project_product_ids`, e o loop nunca alcancava o ramo (da sessao 18) que
copiaria o arquivo bruto.

**Corrigido:** funcao nova `project_evidence_participant_ids(project)` -
superset de `project_product_ids` que tambem inclui todo produto_id com
um ARQUIVO de participacao no projeto, valido ou nao (`participacoes/*.yaml`
no disco). Usada SO nos dois loops de `_decide_writes` (fontes de ficha e
de participacao); `project_product_ids` continua exatamente como estava,
e nenhum outro consumidor (ranking, regra de parada, `sem_cotacao_candidates`,
prompt-ia) foi tocado - confirmado com teste dedicado que o produto
continua fora de `project_candidate_ids`, `project_discarded_candidate_ids`,
elegiveis e cortados mesmo entrando no snapshot.

**Verificacao (sessao 19):** suite completa **456 testes, 0 falhas** (451
+ 5 novos). Mutacao aplicada revertendo os dois loops de volta para
`project_product_ids` (script Python, nao Edit manual, pra trocar as duas
ocorrencias identicas de forma atomica) e restaurada em seguida: derrubou
exatamente os 3 testes-armadilha (evidencia bruta, manifesto,
imutabilidade), nenhum outro - os 2 testes de controle (distincao
evidencia-vs-elegibilidade, caso valido sem cotacao) continuaram passando
porque nao dependem do mecanismo mutado. `auditar-decisoes --strict`,
`operacoes-pendentes --strict`, `checar-segredos --strict` e
`git diff --check` limpos contra a arvore real. Nenhuma migracao rodada
contra produtos reais, pesos/gates intocados. Detalhe completo:
`docs/plano-pendencias-auditoria-2026-09-06.md`, secao 5.

## Sessao anterior (09/09/2026, sessao 18) — historico

**Frente 5, 5a correcao da revisao independente (09/09/2026, sessao 18).**
A Astra reproduziu 2 falhas reais contra o commit `70c3df8` (sessao 17, que
tinha corrigido as 4 anteriores), com os scripts
`astra_review_70c3df8.py`/`astra_review_70c3df8_details.py` (reproduzidos
ANTES de corrigir). As 2 eram PERDA DE DADOS de verdade - a correcao da
sessao 17 tinha criado o estado sintetico `invalido` so pros consumidores
de LEITURA (`gate_eliminations`, `validation_report`), mas dois lugares que
tratam o retorno de `read_participation` como dado a MUTAR/PRESERVAR ainda
nao sabiam da diferenca. As 2 viraram teste permanente em
`tests/test_participacoes.py` (`QuintaRevisaoIndependenteFrente5Test`: os 2
testes da Astra + 3 testes de controle/efeito colateral).

1. **Comandos de estado apagavam evidencia real.** `descartar`/
   `aguardar-preco` liam a participacao via `read_participation` - pra
   participacao com conteudo invalido isso e um dict SINTETICO (so
   defaults + estado `invalido`, nunca o conteudo do arquivo). Os dois
   comandos mudavam so o campo de estado nesse dict e regravavam TUDO com
   `write_participation` - apagando preco-alvo/teto, `requisitos_atendidos`
   e qualquer campo desconhecido que so existia no arquivo real. Efeito
   concreto reproduzido: `aguardar-preco` sobre uma participacao com
   `preco_teto=100` e `requisitos_atendidos={uso: false}` fazia uma oferta
   de R$200 (que devia ficar cortada pelos dois) virar ELEGIVEL depois do
   comando. Corrigido: `_recusar_se_participacao_invalida` roda ANTES de
   qualquer leitura/escrita nos dois comandos - participacao invalida
   recusa com `SystemExit`, nomeando o arquivo a reconciliar a mao, sem
   tocar em nada. Defesa em profundidade: `write_participation` (unico
   lugar que efetivamente grava um arquivo de participacao) tambem passou
   a recusar gravar o proprio estado sintetico `invalido`, mesmo chamada
   direto - o diagnostico nunca pode virar dado persistente por nenhum
   caminho.
2. **Snapshot de decisao substituia a fonte pelo diagnostico.** O snapshot
   gravava, para CADA produto do projeto (inclusive perdedores), o
   resultado INTERPRETADO de `read_participation` - para um concorrente com
   participacao invalida isso e o dict sintetico, nunca o arquivo real.
   `auditar-decisoes --strict` passava, mas a decisao deixava de ser
   reconstruivel: nenhum arquivo congelado preservava preco-alvo/teto,
   requisito ou campo desconhecido do concorrente perdedor. Corrigido: o
   snapshot agora classifica cada participacao
   (`_classificar_participacao`, mesma funcao usada pelo resto do
   contrato) e, so quando o status e "invalida", copia o arquivo BRUTO tal
   como esta em disco - a fonte, nao a interpretacao. Participacao "vazia"
   (ausente/0 bytes) continua gravando o resultado interpretado
   (recuperacao do legado, comportamento da 2a revisao, preservado). O
   manifesto (`manifesto.json`) inclui o arquivo automaticamente - ele so
   itera sobre tudo que existe no diretorio do snapshot, sem tratamento
   especial por tipo de conteudo.

**Achado colateral do proprio pacote:** o teste da sessao 17
(`test_motivo_invalido_nunca_vaza_para_disco`) tratava `descartar` sobre
arquivo invalido como "caminho normal de reconciliacao" e so checava a
ausencia de `_motivo_invalido` - nunca a perda dos demais campos, por isso
nao pegou a lacuna. Reescrito para testar a filtragem de `_motivo_invalido`
direto em `write_participation` (defesa em profundidade, independente de
`descartar` agora recusar); o cenario de reconciliacao automatica saiu do
teste porque deixou de existir - reconciliacao de participacao invalida e
sempre manual agora.

**Verificacao (sessao 18):** suite completa **451 testes, 0 falhas** (445 +
6 novos). Mutacao aplicada nas 3 correcoes de fundo (recusa nos dois
comandos, snapshot bruto, guarda de `write_participation`), uma de cada
vez, desfeita e restaurada em seguida: cada mutacao derrubou exatamente
o(s) teste(s)-armadilha daquele achado, nenhum outro. `auditar-decisoes
--strict`, `operacoes-pendentes --strict`, `checar-segredos --strict` e
`git diff --check` limpos contra a arvore real. Confirmacao manual
adicional (fora dos testes automatizados) reproduzindo os 2 cenarios da
Astra ponta a ponta: arquivo inalterado apos recusa, participacao
congelada no snapshot byte-identica a original com o marcador exclusivo
preservado. Detalhe completo:
`docs/plano-pendencias-auditoria-2026-09-06.md`, secao 5.

## Sessao anterior (08/09/2026, sessao 17) — historico

**Frente 5, 4a correcao da revisao independente (08/09/2026, sessao 17).**
A Astra reproduziu 4 falhas reais contra o commit `f2d5cd1` (sessao 16, que
tinha corrigido as 3 anteriores), com os scripts
`astra_review_f2d5cd1.py`/`astra_review_f2d5cd1_details.py` (reproduzidos
ANTES de corrigir). As 4 viraram teste permanente em
`tests/test_participacoes.py` (`QuartaRevisaoIndependenteFrente5Test`: os 4
testes da Astra + 3 testes de controle/efeito colateral).

1. **Identidade divergente reabilitava candidato descartado.** Alterar so
   `produto_id` num arquivo de participacao ja `descartado` fazia
   `read_participation` cair pro legado (ou pro default `pesquisando`) -
   `compute_ranking` voltava a considerar ELEGIVEL o mesmo candidato que
   `project_discarded_candidate_ids` (lendo `estado` bruto do YAML, sem
   passar pelo contrato) continuava contando como descartado.
   Simultaneidade real confirmada: `elegiveis=['candidato']` E
   `descartados=['candidato']` ao mesmo tempo, `validation_report` mudo.
   Corrigido com um estado sintetico novo, `ESTADO_PARTICIPACAO_INVALIDA`
   ("invalido") - fora de `ESTADOS_PARTICIPACAO`, nunca gravavel por
   nenhum comando -, devolvido por `read_participation` quando o conteudo
   e incoerente (NUNCA cai pro legado nem pro default neutro).
   `_classificar_participacao` virou o ponto UNICO que decide
   "vazio"/"invalida"/"valida", usado por `read_participation` E
   `migrate_products`. `project_candidate_ids`/
   `project_discarded_candidate_ids` passaram a ler pelo MESMO
   `read_participation` (nunca mais `estado` bruto) e excluem o estado
   `invalido` dos dois conjuntos. `gate_eliminations` corta o candidato
   (nunca elegivel); `validation_report` aponta ERRO mesmo sem cotacao
   ainda.
2. **Campo opcional aceitava qualquer tipo.** `requisitos_atendidos:
   ["uso"]` (lista - quebraria `.items()` em `gate_eliminations` com
   `AttributeError` real, reproduzido), `preco_teto: "barato"` e
   `preco_alvo: NaN` (viraria limite ausente em silencio via
   `quote_float`) passavam no contrato minimo e autorizavam
   `migrar-produtos` a apagar o legado por cima. Corrigido:
   `_tipo_invalido_participacao` valida tipo dos campos opcionais
   CONHECIDOS quando presentes - ausencia continua valida, campo
   desconhecido nunca invalida.
3. **Conteudo nao-mapa (lista) era tratado como arquivo vazio na
   migracao.** `participacao_vazia = not (isinstance(dados, dict) and
   bool(dados))` classificava QUALQUER conteudo nao-dicionario - inclusive
   uma LISTA YAML nao vazia com `estado`/`descartado_porque` reais - como
   "arquivo sem dado", autorizando a migracao a sobrescrever com o legado
   por cima de evidencia de verdade. Corrigido dentro de
   `_classificar_participacao`.
4. **Achado colateral, corrigido junto:** o dict sintetico do estado
   `invalido` carrega `_motivo_invalido` (diagnostico interno) - sem
   cuidado, vazaria pro YAML na proxima escrita
   (`descartar`/`aguardar-preco` sobre arquivo ja invalido - o caminho
   normal de reconciliacao) ou pro snapshot congelado de uma decisao.
   `_participacao_serializavel` remove campos com prefixo `_` antes de
   qualquer escrita.

**Verificacao (sessao 17):** suite completa **445 testes, 0 falhas** (438 +
7 novos). Mutacao aplicada nas 3 correcoes de fundo, uma de cada vez,
desfeita e restaurada em seguida: achado 1 desfeito derrubou exatamente os
2 testes de identidade + o teste de `.items()` + o teste do vazamento (4
falhas, nenhuma outra); achado 2 desfeito derrubou as 3 subTests do teste
de tipo + o teste de `.items()` com `AttributeError` real (3 falhas + 1
erro, nenhum outro); achado 3 desfeito derrubou so o teste da lista (1
falha, nenhum outro). `auditar-decisoes --strict`, `operacoes-pendentes
--strict`, `checar-segredos --strict` e `git diff --check` limpos contra a
arvore real. `migrar-produtos` sem `--aplicar` tambem rodado contra a
arvore real como conferencia adicional (preview identico ao anterior, 0
invalido) - **`--aplicar` NAO foi rodado contra a arvore real**, seria
aplicar uma migracao de 46 produtos sem pedido explicito para isso.
Detalhe completo: `docs/plano-pendencias-auditoria-2026-09-06.md`, secao 5.

## Sessao anterior (08/09/2026, sessao 16) — historico

**Frente 5, 3a correcao da revisao independente (08/09/2026, sessao 16).**
A Astra reproduziu 3 falhas reais contra o commit `6669b9d` (sessao 15, que
tinha corrigido as 3 anteriores), com o script
`astra_review_6669b9d.py` (3 testes, um por achado, todos reproduzidos
ANTES de corrigir). As 3 viraram teste permanente em
`tests/test_participacoes.py` (`TerceiraRevisaoIndependenteFrente5Test`: os
3 testes da Astra + 1 teste adicional que escrevi pra cobrir uma janela que
o teste dela nao forcava - ver achado 2 abaixo).

1. **Contrato de participacao insuficiente na migracao.**
   `isinstance(dados, dict) and bool(dados)` so provava que o arquivo tinha
   ALGUM conteudo - um mapa so com `produto_id`, so com uma anotacao solta,
   com `produto_id` de OUTRO produto, ou com `estado` fora do vocabulario
   conhecido, todos "passavam" e autorizavam `migrar-produtos` a apagar o
   campo legado da ficha (unica evidencia real) por cima de lixo. Corrigido:
   funcao nova `_participacao_invalida(dados, produto_id)` define o
   contrato minimo - IDENTIDADE (`produto_id` tem que bater com o proprio
   arquivo) e ESTADO (dentro de `ESTADOS_PARTICIPACAO`, vocabulario fechado
   novo: `pesquisando`/`aguardando_preco`/`descartado`); os demais campos
   continuam opcionais (uma participacao recem-criada nao tem preco/
   requisitos ainda, e isso e valido). Usado nos DOIS lugares que precisam
   do mesmo criterio: `read_participation` (participacao invalida deixa de
   ser autoridade, cai pro legado/default, nunca fabrica estado confirmado)
   e `migrate_products` (participacao que nao passa no contrato vira
   categoria nova, `INVALIDO(S)`, que RECUSA a migracao daquele candidato -
   ficha E participacao preservadas intactas, `--aplicar` termina em
   `SystemExit` como ja acontecia pra `BLOQUEADO(S)`). O caso "vazio" (0
   bytes) da correcao anterior continua recuperando do legado normalmente -
   so o caso "tem conteudo mas nao faz sentido" passou a recusar em vez de
   aceitar.
2. **`nome_produto` nao estava congelado, so a data.** A correcao da sessao
   15 congelou `data_evento` mas `nome_produto` continuava sendo relido da
   FICHA compartilhada a cada tentativa - um `novo-produto --force` rodado
   em OUTRO projeto entre a falha e a retomada muda o nome ali, e a
   retomada escrevia a linha da timeline com o nome NOVO, nunca reconhecida
   como o mesmo efeito da assinatura congelada (nome antigo) - duplicava a
   cada retomada. Corrigido: `nome_produto` entrou em `op.detalhe` junto da
   data (mesmo mecanismo). Escrevi um teste adicional
   (`test_nome_congelado_mesmo_quando_timeline_nunca_foi_tentada`) pra uma
   janela que o teste da Astra nao forcava - interrupcao ENTRE concluir a
   participacao e sequer tentar a timeline pela primeira vez (via
   `CENTRAL_COMPRAS_TESTE_CRASH_APOS=participacao`, hook de teste real do
   proprio motor) - onde o mecanismo do achado 3 (abaixo) ainda nao tem
   nada persistido pra reaproveitar.
3. **Journal de versao anterior quebrava a retomada com `KeyError`.**
   `link_product` passou a exigir `op.detalhe["data_evento"]` (sessao 15) e
   depois tambem `["nome_produto"]` (achado 2 acima), mas um journal
   `em_andamento` comecado por uma versao ANTERIOR do comando (antes desses
   campos existirem) nao tem essas chaves - a retomada quebrava com
   traceback cru de `KeyError` em vez de reconciliar. Corrigido com um
   metodo novo em `OperationHandle`: `efeito_congelado(passo)`, que devolve
   a `assinatura_efeito` JA persistida por `registrar_efeito` pra aquele
   passo (de QUALQUER versao do codigo que a comecou), se alguma tentativa
   ja chegou a registra-la - reaproveita esse texto exato em vez de
   reconstruir. So cai pro dado atual de `op.detalhe` (com `.get(...)` e
   fallback pro valor desta chamada, nunca indexacao direta) quando o passo
   nunca foi tentado por ninguem - nesse caso nao ha nenhum efeito parcial
   que dependa de bater com texto antigo, entao e seguro. `append_timeline`
   ganhou parametro `linha` (o texto INTEIRO ja pronto, ignora
   `etapa`/`decisao`/`porque`/`data`) pra escrever exatamente o que foi
   reaproveitado, sem reconstruir. Testado com o CODIGO REAL do commit
   `fcdb6f9` (2 correcoes atras) via `git show` + subprocesso, criando uma
   pendencia de verdade com aquele codigo antigo antes de trocar pro codigo
   atual e confirmar retomada limpa, sem duplicacao.

**Verificacao (sessao 16):**
- Baseline ANTES de tocar em qualquer coisa: 434 testes, 0 falhas -
  confirmado rodando a suite antes de editar (a Astra ja tinha relatado o
  mesmo numero).
- As 3 falhas: reproduzidas com o script da Astra contra o codigo do commit
  `6669b9d` (rodou os 3 testes dela direto, os 3 falharam do jeito descrito
  contra o codigo antigo), corrigidas, e cobertas por teste permanente com
  **mutacao aplicada em cada correcao** - desfiz cada correcao de proposito,
  uma de cada vez, rodei so `tests/test_participacoes.py` e confirmei que
  SO o(s) teste(s)-armadilha daquele achado falharam (os outros continuaram
  passando). A mutacao do achado 2 revelou que meu primeiro teste (copiado
  da Astra) na verdade nao cobria aquele ramo do codigo especificamente -
  por isso o teste adicional citado acima.
- Suite completa depois de tudo: **438 testes, 0 falhas** (434 + 4 novos).
- `auditar-decisoes --strict`, `operacoes-pendentes --strict`,
  `checar-segredos --strict` e `git diff --check` limpos, contra a arvore
  real do repositorio.
- **Fora do escopo desta correcao, deliberadamente**: nao reabri julgamento
  de produto (pesos, gates, calibragem); nao toquei infraestrutura externa
  (Sheets/Apps Script); frente 6 nao iniciada; nao estendi o contrato novo
  de participacao (`_participacao_invalida`) para `project_candidate_ids`/
  `project_discarded_candidate_ids` (leem `estado` direto do YAML sem
  passar por `read_participation`) - a Astra nao apontou esses dois como
  achado, e mexer neles agora seria escopo alem do pedido.

## Sessao anterior (08/09/2026, sessao 15) — historico

**Frente 5, 2a correcao da revisao independente (08/09/2026, sessao 15).**
A Astra reproduziu 3 falhas reais contra o commit `fcdb6f9` (sessao 14, que
tinha corrigido as 6 anteriores), com dois scripts de reproducao locais:
`astra_review_fcdb6f9.py` (6 testes: 3 regressoes + 3 controles que ja
passavam) e `astra_review_fcdb6f9_details.py` (evidencia detalhada via
subprocesso real e `compute_ranking`). As 3 foram reproduzidas ANTES de
corrigir, seguindo `docs/como-conferir-auditoria.md`, e viraram teste
permanente em `tests/test_participacoes.py`
(`SegundaRevisaoIndependenteFrente5Test`: 3 testes-armadilha + os 3
controles que a Astra confirmou que ja passavam, agora protegidos contra
regressao futura tambem).

1. **`migrar-produtos` perdia o descarte quando a participacao existia mas
   estava vazia ou invalida.** `ja_tinha_participacao =
   participation_path(...).exists()` so checava EXISTENCIA do arquivo, nao
   se ele tinha dado de verdade - um `participacoes/<id>.yaml` de 0 bytes
   (existente mas sem conteudo legivel) contava como "ja tinha
   participacao", entao a migracao limpava a ficha legada (unica fonte real
   do descarte, motivo, limites e requisitos) por cima do arquivo vazio. O
   candidato voltava a `pesquisando` e reaparecia elegivel no ranking -
   confirmado com `compute_ranking` antes/depois no script de detalhe.
   Corrigido: `migrate_products` agora le o conteudo
   (`read_yaml(participacao_alvo, None)`) e so trata como "participacao
   valida" um mapa YAML nao vazio; arquivo vazio ou com conteudo invalido
   (nao e mapa, ou mapa vazio) e tratado como SEM participacao recuperavel -
   a migracao recupera o dado do legado pra dentro dele, do jeito que ja
   fazia quando o arquivo simplesmente nao existia. Participacao valida
   continua NUNCA sendo sobrescrita pelo legado (comportamento antigo
   preservado, testado pelo controle
   `test_migracao_retomada_entre_duas_escritas_preserva_estado`).
2. **`vincular-produto` podia concluir sem marcar a etapa 3, sem deixar
   pendencia visivel.** `mark_steps(project, [3])` rodava DEPOIS do bloco
   `with tracked_operation(...)`, ou seja, fora da recuperacao - uma
   interrupcao bem ali (participacao e timeline ja gravadas, journal ja
   apagado porque o `with` tinha terminado sem excecao) deixava a etapa 3
   sem marcar, sem NENHUMA operacao pendente pra `operacoes-pendentes`
   mostrar, e a retomada era recusada por "ja tem participacao" (a mesma
   guarda que protege contra vincular de novo depois de concluido).
   Corrigido: `mark_steps(project, [3])` passou pra dentro do `with`, como
   ultima linha do bloco - agora uma falha ali mantem o journal
   `em_andamento` (visivel, retomavel), e uma retomada real so termina de
   marcar a etapa (as outras duas ja concluidas nao repetem nada).
3. **A linha da timeline podia duplicar numa retomada em outro dia.** A
   assinatura do efeito (`linha_timeline`, usada por `registrar_efeito` pra
   reconhecer "essa linha ja foi escrita") era montada com `today()` no
   INICIO da chamada, mas o `executar()` que de fato grava chamava
   `append_timeline(...)` sem passar essa data - `append_timeline` calculava
   `today()` de novo, na hora de escrever. Numa retomada no dia seguinte (ou
   depois), a linha realmente gravada saia com a data NOVA, que nunca batia
   com a assinatura congelada (data velha) - toda retomada via "efeito nunca
   aconteceu" e escrevia outra linha. Corrigido: `append_timeline` ganhou
   parametro `data` opcional (default `today()`, comportamento antigo
   preservado pros outros chamadores); `link_product` agora congela
   `data_evento` em `op.detalhe` (mesmo mecanismo ja usado por `decidir` pro
   caminho do snapshot - nunca recalculado numa retomada) e passa essa MESMA
   data pra `append_timeline`, garantindo que a linha gravada bate
   exatamente com o que a reconciliacao esta procurando.

**Verificacao (sessao 15):**
- Baseline ANTES de tocar em qualquer coisa: 428 testes, 0 falhas -
  confirmado rodando a suite antes de editar (a Astra ja tinha relatado o
  mesmo numero).
- As 3 falhas: reproduzidas contra o codigo do commit `fcdb6f9` (os scripts
  da Astra), corrigidas, e cobertas por teste permanente com **mutacao
  aplicada em cada correcao** - desfiz cada correcao de proposito, uma de
  cada vez, rodei so `tests/test_participacoes.py` e confirmei que SO o
  teste-armadilha daquele achado falhou (os outros 36, incluindo os 3
  controles, continuaram passando).
- Suite completa depois de tudo: **434 testes, 0 falhas** (428 + 6 testes
  novos: 3 regressoes + 3 controles).
- `auditar-decisoes --strict`, `operacoes-pendentes --strict`,
  `checar-segredos --strict` e `git diff --check` limpos, contra a arvore
  real do repositorio.
- **Fora do escopo desta correcao, deliberadamente**: nao reabri julgamento
  de produto (pesos, gates, calibragem); nao toquei infraestrutura externa
  (Sheets/Apps Script); frente 6 nao iniciada.

## Sessao anterior (08/09/2026, sessao 14) — historico

**Frente 5, correcao da revisao independente (08/09/2026, sessao 14).** A
Astra reproduziu 6 falhas reais contra o commit `e29c45c` (sessao 13), com
dois scripts de reproducao (dados sinteticos, sem tocar a arvore real):
`astra_review_frente5.py` (6 cenarios) e `astra_crash_vinculo_frente5.py`
(interrupcao dura via `os._exit`). Todas as 6 foram reproduzidas ANTES de
corrigir, seguindo `docs/como-conferir-auditoria.md`, e viraram teste
permanente em `tests/test_participacoes.py`
(`RevisaoIndependenteFrente5Test` + 3 testes novos em
`MigracaoParticipacaoTest`).

1. **Contexto de IA vazava participacao entre projetos.** `ai_prompt`
   chamava `find_product(pid)` SEM `project` - o motivo de descarte de um
   produto no projeto A aparecia no `prompt-ia` do projeto B, e o estado de
   um produto novo (so `pesquisando`) ficava omitido do contexto em
   qualquer projeto. Corrigido: `find_product(pid, project)`.
2. **Validacao tinha o mesmo vazamento.** `validation_report` chamava
   `find_product(produto_id)` sem projeto - produto ativo e cotado em B
   podia ser acusado de "descartado sem motivo" por causa de um descarte
   (sem motivo) so em A. Mesma correcao. Os demais consumidores de
   `find_product` foram conferidos um a um: os que so usam `nome`/`marca`/
   `categoria` (identidade, nunca participacao) ficaram como estavam de
   proposito.
3. **Snapshot da decisao nao congelava a participacao.** `_decide_writes`
   copiava a ficha (`produtos/<id>.yaml`) para o snapshot mas nunca o
   arquivo de participacao - um requisito exclusivo daquela compra, gravado
   so na participacao, passava por `auditar-decisoes --strict` sem aparecer
   em NENHUM arquivo congelado. Corrigido: `_capturar()` agora grava
   `snapshots/<id>/participacoes/<produto_id>.yaml` (efetivo, via
   `read_participation` - cobre tambem fallback legado) para todo produto
   do projeto. Testado tambem que a evidencia congelada nao muda com
   alteracao POSTERIOR no mesmo projeto (mesmo principio ja valido para
   ranking.md/cotacoes.csv).
4. **`vincular-produto` sem recuperacao.** Gravava a participacao e SO
   DEPOIS chamava `append_timeline`, sem journal proprio - uma interrupcao
   entre os dois passos deixava a participacao gravada e a timeline
   incompleta, e a retomada era recusada por "ja tem participacao" (a
   propria guarda contra sobrescrever um vinculo concluido bloqueava a
   retomada do vinculo INCOMPLETO). Corrigido: `link_product` agora usa
   `tracked_operation` (mesmo mecanismo de `decidir`/`aprender-veredito`);
   a guarda de "ja existe" e liberada so quando ha journal `em_andamento`
   com o MESMO op_id (retomada legitima), continua recusando uma segunda
   chamada normal depois de concluida. `vincular-produto` saiu de
   `RECURSOS_DIRETOS_POR_COMANDO` (a checagem generica de `main()`, sem
   excecao de op_id, bloquearia a propria retomada). Testado com excecao
   mockada E com interrupcao dura (`os._exit(70)`) num subprocesso real,
   confirmando `operacoes-pendentes --strict` limpo depois da retomada.
5. **`migrar-produtos` nao respeitava operacao pendente.** Escrevia
   participacao e limpava a ficha sem checar a checagem central de recursos
   conflitantes - um journal valido (`decidir`, `vincular-produto` ou
   qualquer outro escritor) reivindicando o arquivo de participacao nao
   impedia a migracao de cria-lo e apagar o campo legado da ficha por
   baixo. Corrigido: cada candidato do lote passa por
   `_bloquear_se_recursos_conflitantes` antes de escrever; se bloqueado,
   fica de fora (relatado, ficha e participacao intocadas) e o resto do
   lote continua migrando normalmente; com `--aplicar` e pelo menos um
   bloqueado, o comando termina em `SystemExit` (nunca silencioso). Testado
   recusa-antes-de-escrita, liberacao apos o journal ser removido, e que so
   o candidato reivindicado fica de fora num lote com mais de um.
6. **`novo-produto --requisito` invalido deixava ficha orfa.** `parse_pairs`
   em `--requisito` (sem `chave=valor`) levantava `SystemExit` DEPOIS de
   `produto.yaml`/`pesquisa.md` ja gravados - ficha ficava no disco sem
   participacao, sem caminho limpo de retomada (`novo-produto` de novo
   recusa por ja existir; `vincular-produto` tambem recusa por causa do
   campo `projeto` legado que nunca foi setado). Corrigido: `--atributo` e
   `--requisito` sao validados (parse completo) ANTES de qualquer escrita.
   Testado tambem que a entrada corrigida, chamada de novo com os MESMOS
   argumentos exceto o requisito, funciona normalmente.

**Suite tambem corrigida: 1 falha PRE-EXISTENTE (nao relacionada a frente
5, ja documentada nas sessoes anteriores) eliminada.**
`test_same_day_quote_without_accepted_warranty_does_not_hide_valid_quote`
fixava `data="2026-08-31"` para simular "cotacao do mesmo dia"; o
calendario real passou dessa data e as duas cotacoes do teste caiam no
fallback "tudo vencido" do motor (ignora gate), fazendo o teste passar por
motivo errado ou falhar dependendo do dia. Corrigido usando
`dt.date.today().isoformat()` nas duas cotacoes do fixture - preserva o
cenario real (duas ofertas do MESMO dia, uma sem garantia aceita) sem
depender de quando o teste roda. **Motor e asserçao intocados**, so a
fixture deixou de apodrecer.

**Verificacao (sessao 14):**
- Baseline ANTES de tocar em qualquer coisa: 415 testes, 1 falha (a do
  calendario acima) — confirmado rodando a suite antes de editar.
- Os 6 achados: reproduzidos contra o codigo do commit `e29c45c` (os 2
  scripts da Astra rodaram limpo so DEPOIS da correcao), corrigidos, e
  cobertos por teste permanente com mutacao aplicada em CADA correcao
  (desfiz a correcao de proposito, um mutante por vez, e confirmei que so
  o(s) teste(s)-armadilha daquele achado falharam - nenhum efeito
  colateral em teste de outra frente).
- Suite completa depois de tudo: **428 testes, 0 falhas** (415 + 13 testes
  novos; a falha pre-existente do calendario foi eliminada, nao so
  escondida).
- `auditar-decisoes --strict`, `operacoes-pendentes --strict`,
  `checar-segredos --strict` e `git diff --check` limpos, contra a arvore
  real do repositorio (nao so sandbox de teste).
- **Fora do escopo desta correcao, deliberadamente**: nao reabri
  julgamento de produto (pesos, gates, calibragem); nao toquei
  infraestrutura externa (Sheets/Apps Script); frente 6 nao iniciada.

## Sessao anterior (08/09/2026, sessao 13) — historico

**Frente 5 (produtos reutilizados em projetos diferentes): IMPLEMENTADA E
TESTADA (08/09/2026), depois corrigida na sessao 14 (ver bloco acima - 6
falhas achadas por revisao independente).** `produto.yaml` (ficha) agora
guarda so identidade e
dado tecnico (`id`, `categoria`, `nome`, `marca`, `atributos`,
`atributos_classificacao`, `proveniencia`); estado de pesquisa, descarte
(com motivo), preco-alvo/teto, aguardando-preco e `requisitos_atendidos`
viraram **participacao** — um arquivo por produto DENTRO de cada projeto
(`projetos/<projeto>/participacoes/<produto_id>.yaml`). O mesmo produto_id
pode participar de projetos diferentes com estados totalmente
independentes; descartar/aguardar-preco num projeto nunca toca o outro.

- **Leitura unica**: `find_product(produto_id, project=None)` e a UNICA
  funcao que mescla ficha+participacao; sem `project` devolve so identidade
  (compat com chamadas antigas que so precisam de nome/marca). Ranking,
  gate, regra de parada, painel, dashboard e o payload do Sheets passaram a
  chamar com `project` — nenhum consumidor le a ficha crua pra decidir
  estado.
- **CLI novo**: `vincular-produto --produto-id X --projeto Y` reaproveita
  ficha existente noutro projeto sem recriar nada nem sobrescrever
  participacao ja existente. `novo-produto` sobre ficha existente (sem
  `--force`) agora orienta pra `vincular-produto` em vez de so recusar.
  `migrar-produtos [--projeto] [--aplicar]` migra o formato legado em lote
  — so o caso inequivoco (ficha aponta pra um unico projeto existente, sem
  cotacao em projeto diferente); resto e RELATADO, nunca adivinhado; sem
  `--aplicar` so mostra previa; idempotente (roda quantas vezes quiser).
- **Ambiguidade sempre recusa antes de escrever**: `descartar`/
  `aguardar-preco` sem `--projeto` com o produto participando de 2+
  projetos e recusado, listando os projetos, zero alteracao — testado via
  CLI real (nao so unittest).
- **Recuperacao de operacoes (frente 2)**: arquivo de participacao entrou
  no mesmo mecanismo central de recursos pendentes que ja protege
  decisao.md/veredito (`_recursos_diretos_participacao`); testado plantando
  journal `em_andamento` reivindicando a participacao e confirmando recusa.
- **Testes**: `tests/test_participacoes.py`, 18 testes, cobrindo os 9
  criterios de aceite do pedido (isolamento nos dois sentidos com e sem
  cotacao, `vincular-produto` seguro/idempotente, ambiguidade recusada sem
  escrita, migracao com previa/idempotencia/uso-cruzado-relatado, protecao
  de operacao pendente). Mutacao de teste no coracao do merge
  (`find_product` ignorando participacao): 2 dos 18 falharam, confirmando
  deteccao real. Dois testes existentes ajustados por mudanca de contrato
  (nao eram bugs deles): `test_waiting_price_and_verdict_learning_flow`
  checava `estado:` dentro da ficha (campo mudou de arquivo);
  `test_invariants_hold_on_pathological_data` (fuzzer) precisou do campo
  `projeto` na ficha legada pra fuzzagem continuar alcancando o motor.
- **Validado ponta a ponta num sandbox isolado** (copia de
  config/templates/scripts, nunca a arvore real): mesmo produto vinculado a
  2 projetos, cotado e descartado só num deles — `ranking.md` de cada
  projeto com o corte certo; `decidir` fechado, `auditar-decisoes --strict`
  e `operacoes-pendentes --strict` passando; alteracao de participacao em
  OUTRO projeto depois da decisao nao mudou 1 byte do snapshot (hash
  SHA-256 identico). Painel aberto nos dois projetos ao mesmo tempo (portas
  diferentes), screenshot confirmando "elegivel" num e "aguardando preco"
  no outro pro MESMO produto.
- **Fora do escopo, deliberadamente**: frente 6 nao tocada; pesos/gates/
  comparabilidade do score intocados; nenhuma infraestrutura externa
  criada — o Sheets reflete participacao por projeto de graca, sem mudar
  Code.gs nem novo deploy.

Suite completa: **415 testes** (414 passando + 1 falha PRE-EXISTENTE e
NAO relacionada — ver nota abaixo), `checar-segredos --strict` e
`git diff --check` limpos. Detalhe completo, com o contrato inteiro:
`docs/plano-pendencias-auditoria-2026-09-06.md`, secao 5.

**Nota sobre a suite (nao e da frente 5, registrar pra nao confundir com
regressao futura):** o baseline limpo (antes desta sessao, commit
`6b48a51`) ja reprovava em `test_decision_engine.py::
RankingGateAwareQuoteSelectionTest::
test_same_day_quote_without_accepted_warranty_does_not_hide_valid_quote`.
Causa: o teste fixa `data="2026-08-31"` esperando cotacao "do mesmo dia"
(dentro da janela de 7 dias de `fonte=manual`); com o calendario real ja em
2026-09-08 (8 dias depois), as duas cotacoes do teste ficam "vencidas" e
`latest_quotes` cai no fallback "tudo vencido" (ultima gravada, ignora
gate) — apodrecimento de data fixa no fixture, nao bug de codigo. Nao
corrigido nesta sessao (fora do escopo pedido).

**Commit avulso de hoje, ainda nao registrado no STATUS quando esta sessao
comecou:** `6b48a51` — `atributo_valor` passou a tratar candidato SEM
cotacao igual a eliminado pelo gate (nunca mostra estrela pra nenhum dos
dois, so o valor bruto). Preservado e coberto de novo por
`test_candidato_sem_cotacao_sem_estrela_respeita_projeto` nesta sessao.

## Sessao anterior (07/09/2026, sessao 12) — historico

Frente 2 (recuperacao de operacoes parciais) **concluida sob reserva** —
commit `d49a3cd` (7a revisao). Ja foi declarada concluida 6 vezes antes e
cada vez o Codex achou lacuna nova - **nao declare concluida de novo so
porque os exemplos testados passaram**; leia a secao 2 do plano inteira,
incluindo o inventario comando-a-comando, antes de mexer.

**Frente 3 (receptor Sheets): 3a rodada CONCLUIDA e implantada (Versao
13)** - "Visao Geral" ganhou a mesma protecao de propriedade
(nome+sheetId) dos comparativos, com bootstrap de migracao pro upgrade
V11/V12 -> V13 nao duplicar a Visao Geral real; `sincronizar_planilha()`
(Python) passou a mostrar `abas_parcialmente_alteradas` alem de
`abas_escritas_antes_da_falha`. Ver secao anterior desta sessao (abaixo)
pro relato completo, ou a secao 3 do plano. **Mesmo assim, nao declare
esta frente concluida "para sempre" so porque 3 rodadas ja passaram.**

**Frente 4 (proveniencia): IMPLEMENTADA E TESTADA (07/09/2026).** Cada
observacao de `cotacoes.csv` carrega, numa coluna nova `proveniencia`
(JSON), origem/evidencia/data/estado para os 6 campos comerciais (preco,
variacao, vendedor, frete, estoque, garantia) - amarrado aquela LINHA,
nunca ao produto em geral. `fonte`/`confirmacao` continuam existindo, mas
deixaram de ser a unica fonte da verdade sobre o que foi conferido.

- **Schema**: 2 colunas novas (`estoque`, `proveniencia`) no fim de
  `COTACOES_HEADER`, via o mecanismo de migracao ja existente
  (`migrar-cotacoes`) - nada historico quebra, linha antiga sem a coluna
  le como "legado sem evidencia" nos 6 campos.
- **`cotar`**: flags novas `--estoque`/`--origem-dados`/`--evidencia`.
- **`promover-cotacao`**: mesmas 3 flags; a proveniencia comeca HERDANDO
  a da cotacao base e so marca "conferido" agora os campos que esta
  chamada de fato recebeu - confirmacao parcial nunca vira "conferido"
  pra tudo (`--sem-alteracao` e a excecao deliberada: reconfirmacao
  total).
- **Painel**: mesmo caminho da CLI (`cc.main(["cotar",...])`), badge de
  proveniencia com tooltip no Ranking e em "Ultimas cotacoes", formulario
  com os campos novos - testado de verdade no navegador com dados
  SINTETICOS (ambiente isolado, script/config copiados pra um tmpdir,
  nunca a arvore real do Josemar). Achei e corrigi um bug real nessa
  verificacao: o fallback do em-dash pra Estoque vazio tava escapado duas
  vezes (`&amp;mdash;` literal em vez de `—`).
- **Snapshot**: nenhuma mudanca de codigo foi necessaria - `metadados.json`
  ja embutia o dict inteiro da cotacao vencedora e `cotacoes.csv` inteiro
  ja era copiado; a imutabilidade que ja existia (copia congelada + hash)
  passou a cobrir proveniencia de graca. Testado explicitamente: uma
  `promover-cotacao` DEPOIS de decisao fechada nao muda 1 byte do
  snapshot.
- **Testes**: `tests/test_proveniencia.py`, 18 testes cobrindo os 7
  criterios de aceite pedidos (relatorio de IA identificado, confirmacao
  parcial isolada, historico preservado, legado sem fabricacao, CLI=painel,
  snapshot imutavel, sem mistura entre observacoes). Mutacao de teste
  aplicada na linha central da heranca parcial - exatamente 1 dos 18
  falhou, confirmando que prova comportamento.
- **Fora do escopo, deliberadamente**: dashboard estatico
  (`comercial_valor`, tambem usado pelo export do Sheets - frente 3) nao
  foi tocado; pesos/gates/limites de score do ranking tambem nao.

Suite completa: 394 testes, `checar-segredos --strict` limpo.

Frentes 5 (produtos reutilizados) e 6 (datas/veredito) **nao iniciadas** ao
fim desta sessao — comece pelo plano, nao redescubra o escopo. (Frente 5
foi implementada na sessao seguinte, 13; ver bloco "AO RETOMAR" no topo.)

## Sessao anterior (07/09/2026, sessao 11) — historico

**Frente 3 (receptor Sheets): 3a rodada de revisao do Codex sobre o commit
`c5018dc` achou mais 2 ajustes — corrigidos, testados e implantados
(Versao 13).** Os 2 ajustes desta rodada:

1. **"Visao Geral" ficou de fora da protecao de propriedade que a V12 deu
   aos comparativos** - `doPost` excluia esse nome de proposito
   (`nome !== 'Visao Geral'`) da checagem de abas estranhas, e `abaLimpa()`
   adotava/limpava qualquer aba com esse nome sem checar sheetId. Uma aba
   manual chamada "Visao Geral" tinha o conteudo apagado.
2. **`sincronizar_planilha()` (Python) so mostrava metade do diagnostico
   de falha parcial** - lia `abas_escritas_antes_da_falha` mas nunca
   `abas_parcialmente_alteradas` (introduzido na V12), escondendo qual aba
   ficou em branco quando as duas listas vinham preenchidas ao mesmo tempo.

**Correcao local: feita e testada.** "Visao Geral" passa pelo mesmo
mecanismo de propriedade verificada (nome + sheetId) dos projetos, com
redirecionamento estavel entre sincronizacoes quando o nome esta ocupado
por aba estranha, e um bootstrap de uma unica vez
(`migrarRegistroLegado`/`__visao_migrada__`) pro upgrade V11/V12 -> V13 nao
duplicar a Visao Geral real (nunca registrada por nome ate a V12) - achei
esse bug no meu proprio teste antes de sequer cogitar o deploy. O cliente
Python agora mostra as duas listas separadamente, preservando
compatibilidade com respostas antigas (sem o campo novo) e ocultacao de
token. Regressao executavel nova:
`tests/apps_script/cenarios/colisao_aba_visao_geral_manual.js` +
`migracao_registro_legado.js` atualizado (agora tambem prova o bootstrap);
3 testes novos em `SincronizarPlanilhaTest`. Suite completa: 376 testes,
`checar-segredos --strict` limpo. `docs/infraestrutura-externa.md` tambem
corrigido - ainda anunciava a Versao 11 quando a V12 ja estava implantada.

**Redeploy real: FEITO.** Publicado como **Versao 13** pela conta
`conta-comercial@exemplo.com`, editando a implantacao existente (mesmo ID/URL desde
a V9). O ponto mais delicado era o bootstrap de migracao
(`__visao_migrada__`): ate a V12, "Visao Geral" nunca tinha sido registrada
por nome, entao a primeira sincronizacao depois deste deploy corria o
risco de tratar a Visao Geral REAL (criada pela V9-V12) como estranha e
criar uma redirecionada, duplicando a aba - funcionou sem incidente. Duas
sincronizacoes reais devolveram `Planilha sincronizada: 10 projeto(s), 10
comparativo(s).` nas duas, e a planilha real
(`docs.google.com/spreadsheets/d/1WjO_Ax9Tw6zrMFY2MCLTwbwAoK_Um1g93LWy_HMION4`)
continua com exatamente 11 abas (Visao Geral + 10 comparativos, sem
duplicata nem orfa, nenhuma "Visao Geral" redirecionada) - conferido pela
listagem de paginas visiveis e por captura de tela.

## Sessao anterior (07/09/2026, sessao 10) — historico

**Frente 3 (receptor Sheets), 2a rodada: CONCLUIDA e implantada (Versao
12).** As 3 lacunas desta rodada:

1. **Aba manual podia ser sobrescrita** - `abaLimpa()` decidia propriedade
   so pelo nome; uma aba criada a mao com o mesmo nome de um projeto
   (ex.: `2026-a`) era limpa como se fosse do script.
2. **`estrelas` fora de 0-5 derrubava a sincronizacao com abas ja limpas**
   - `estrelas: -2` (formato legado) chegava direto no `Array()` de
   `renderizarLinha()` sem checar tipo/faixa, e isso rodava DEPOIS de
   `abaLimpa()` ja ter limpado a 2a aba.
3. **Aba limpa mas nao reescrita ficava fora do diagnostico** -
   `abas_escritas_antes_da_falha` so listava abas que tinham terminado de
   verdade, escondendo qual aba ficou em branco.

**Correcao local: feita e testada.** Propriedade de aba agora e
`nome + sheetId` (nao so nome), com migracao explicita do registro legado;
`validarPayload()` valida o contrato de `estrelas` (0-5, formatos legado E
tipado) antes de qualquer escrita; a resposta de erro ganhou
`abas_parcialmente_alteradas`. Desta vez os testes que provam isso sao
PERMANENTES e commitados (a rodada anterior so tinha scripts de scratchpad
+ asserts de string, e o Codex apontou certo que isso nao prova
comportamento): `tests/apps_script/` (fakes do runtime do Apps Script +
harness + 5 cenarios Node) e `tests/test_apps_script_execucao.py` (7 testes
Python que rodam o Code.gs de verdade via `subprocess`, pulam com motivo
visivel se `node` nao existir no PATH). Suite completa: 371 testes,
`checar-segredos --strict` limpo.

**Redeploy real: FEITO.** Publicado como **Versao 12** pela conta
`conta-comercial@exemplo.com`, editando a implantacao existente (mesmo ID/URL desde
a V9). Duas sincronizacoes reais devolveram `Planilha sincronizada: 10
projeto(s), 10 comparativo(s).` nas duas. O registro de propriedade migrou
em producao do formato legado da V11 (`{nome: true}`) para o novo (`{nome:
sheetId}`) sem incidente - nao criou aba duplicada nem tratou os 10 projetos
reais como estranhos. A planilha real
(`docs.google.com/spreadsheets/d/1WjO_Ax9Tw6zrMFY2MCLTwbwAoK_Um1g93LWy_HMION4`)
continua com exatamente 11 abas (Visao Geral + 10 comparativos, sem
duplicata nem orfa) - conferido pela listagem de paginas visiveis e por
captura de tela da Visao Geral.

**Importante: os 2 syncs reais só provam o caminho feliz (deploy +
idempotência) na planilha de produção.** Os 3 cenários de FALHA (colisão com
aba manual, payload inválido, falha operacional pós-`clear()`) foram
provados antes do deploy, contra o Code.gs real rodando em ambiente isolado
(`tests/apps_script/` + `tests/test_apps_script_execucao.py`) — nunca contra
a planilha de produção, de propósito (destrutivo só em ambiente isolado).

## Sessao anterior (07/09/2026, sessao 9) — historico

**Frente 3 (receptor Sheets), 1a rodada: CONCLUIDA e verificada na nuvem
(Versao 11).** Os 3 resultados, agora todos fechados:

1. **Recuperacao local (frente 2): feita e verificada** (ver secao 2 do
   plano).
2. **Implementacao do codigo do Sheets: feita e verificada por execucao
   real.** Corrigi 3 falhas reais da Versao 9 do `Code.gs`
   (`docs/integracao-google-sheets.md`, secao "Code.gs (versao 11 ativa)"):
   payload com `null` podia deixar a planilha parcialmente escrita,
   `limparAbasOrfas` podia apagar aba criada a mao (so por o nome bater com
   um padrao), e a resposta de erro nao dizia o que ja tinha sido gravado
   antes de quebrar. Reproduzi os 3 casos de verdade rodando o proprio
   `Code.gs` sob Node com fakes minimos do runtime do Apps Script (script no
   scratchpad da sessao, nao commitado — `apps_script_fakes.js` +
   `repro_gap{1,2,3}_*.js`): os 3 falharam do jeito descrito contra o codigo
   antigo e passaram contra o corrigido.
3. **Validacao real na nuvem: FEITA.** O perfil de navegador `conta-comercial`
   estava travado por um Chrome de sessao anterior (`Browser is already in
   use`); com autorizacao explicita do Josemar ("pode forcar o fechamento e
   tenta de novo"), matei so esse processo (`taskkill /T /F`, confirmado por
   `Get-CimInstance ... -Filter chrome.exe` antes, filtrando por
   `perfil-conta-comercial` — nenhum outro perfil tocado) e o navegador voltou a
   funcionar. Editei o `Código.gs` ao vivo via `monaco.editor` (substituicao
   cirurgica das 2 regioes que mudaram, nunca reescrevendo o arquivo
   inteiro — assim o TOKEN real nunca precisou passar por texto digitado) e
   implantei como **Versao 10**, preservando ID/URL da implantacao (mesma
   desde a V9). **A V10 quebrou na primeira sincronizacao real**:
   `PropertiesService.getDocumentProperties()` e `null` porque este projeto
   e solto (nao container-bound, de proposito) — algo que o fake de teste
   nao pegava (sempre devolvia um objeto funcional). A propria correcao do
   item 3 mostrou, na resposta de erro, que Visao Geral e os 10
   comparativos ja tinham sido escritos antes da falha — nada de negocio
   foi perdido. Troquei para `PropertiesService.getScriptProperties()`,
   fortaleci o fake em Node pra replicar esse `null` (nao passa batido de
   novo) e implantei a **Versao 11** minutos depois, mesmo dia, mesmo
   ID/URL. Duas sincronizacoes reais contra a V11: `Planilha sincronizada:
   10 projeto(s), 10 comparativo(s).` nas duas (idempotencia confirmada). A
   planilha real foi aberta: exatamente 11 abas (Visao Geral + 10
   comparativos, sem duplicata nem orfa), e capturas de tela confirmaram
   formatacao/veredito/cores corretos na Visao Geral e numa aba de
   comparativo.

Suite Python completa (361 testes - a nota da sessao dizia 360, contagem
errada) e `checar-segredos --strict` passaram com o codigo final (com
`getScriptProperties`).

## Sessao anterior (07/09/2026, sessao 8) — historico

- **A 6a correcao (commit `4908c02`) confirmou os 4 casos anteriores
  bloqueados, mas o Codex achou que `decidir` nunca declarava o proprio
  arquivo de VEREDITO como recurso** - so `decisao.md`/`processo.md`.
  Dois sentidos de conflito: (A) uma decisao ja fechada, com D+30
  preenchido e `aprender-veredito` pendente (reivindicando o veredito
  desde a 5a revisao); um `decidir --force-veredito` NOVO nunca via essa
  pendencia e sobrescrevia o veredito com o template em branco, apagando
  o D+30 - a retomada de `aprender-veredito` falhava com "Fase D+30 ainda
  em branco"; (B) `decidir --force-veredito` interrompido DEPOIS de criar
  o veredito nesta mesma tentativa; preenchimento manual de D+30 na
  janela; a PROPRIA retomada de `decidir` chamava `create_verdict` de novo
  (nunca protegido por `executar_uma_vez`, diferente da captura) e apagava
  o preenchimento. As 2 reproduzidas contra o codigo antigo (`git show` +
  subprocessos reais, sem `git stash`).
- **Correcao**: `decide()` congela `veredito_nome` em `op.detalhe` (mesmo
  principio do `snapshot_rel`) e declara o arquivo como `recursos` -
  fecha o caso A, e como efeito colateral direto tambem passou a bloquear
  `preencher-veredito` enquanto `decidir` esta pendente no mesmo veredito
  (o que impede a intercalacao do caso B antes dela comecar).
  `create_verdict()` ganhou parametro `path` opcional e a chamada dentro de
  `_decide_writes` passou a rodar em `executar_uma_vez("veredito", ...)` -
  defesa adicional para a propria retomada nunca recriar um veredito ja
  criado. `_escopos_alcancados_por()`: qualquer projeto agora tambem
  alcanca `vereditos/` (antes so BASE alcancava) - journal ilegivel de
  `decidir` passou a bloquear o veredito tambem.
- **Testes**: `tests/test_operation_recovery.py` foi de 31 para 35.
- HB20S continua intocado (sem `git stash` nesta sessao tambem).

## Sessao anterior (07/09/2026, sessao 6) — historico

- **A 2a correcao (commit `2a682a7`) tambem estava incompleta.** O Codex
  revisou de novo e reproduziu 3 falhas mais profundas, todas na mesma raiz:
  eu tratava "gravar o snapshot" como uma sequencia de escritas
  independentes em vez de uma unidade que devia virar imutavel ao concluir,
  e `registrar_efeito` confundia "esse texto existe no arquivo" com "esta
  operacao teve efeito". (1) retomada recalculava o manifesto contando o
  `manifesto.json` que a propria tentativa anterior tinha deixado no
  diretorio - um arquivo que se autodescreve nunca bate com o proprio
  conteudo depois de reescrito, e `auditar-decisoes --strict` acusava
  "arquivo alterado: manifesto.json"; (2) o CONTEUDO do snapshot (nao so o
  caminho) era recalculado a cada retomada - uma calibragem em
  `preferencias.yaml` feita entre a falha e o retry vazava para dentro da
  evidencia ja congelada; (3) `registrar_efeito` decidia "ja aconteceu" so
  pela presenca do texto, sem distinguir a ocorrencia de uma operacao
  diferente e legitima - duas licoes identicas em projetos distintos, no
  mesmo dia, faziam a retomada da segunda "concluir" sem gravar nada,
  perdendo conhecimento em silencio. As 3 reproduzidas contra o codigo
  antigo antes de corrigir — evidencia completa na secao 2 do plano.
- **Correcao — revisao do contrato, nao so dos exemplos**: primitivo novo
  `OperationHandle.executar_uma_vez()` para captura de varios arquivos por
  sobrescrita cega: passo concluido nunca mais toca em nada (resolve 1 e 2
  juntos, sem precisar fingerprintar cada arquivo de entrada);
  `registrar_efeito()` agora identifica pela CONTAGEM de ocorrencias antes
  da tentativa comecar, nao pela presenca (resolve 3).
- **Testes**: `tests/test_operation_recovery.py` foi de 12 para **18
  testes**; o teste de concorrencia trocou de threads por **processos
  separados de verdade**, com verificacao de que todo codigo de saida
  nao-zero e exatamente o timeout de trava esperado e que `auditar-decisoes
  --strict` passa ao final.
- **Nota**: esta sessao encontrou `produtos/autopecas/` e dois projetos HB20S
  nao rastreados no repositorio (provavelmente outra sessao do Josemar
  rodando em paralelo) - nao foram tocados nem commitados aqui.

## Sessao anterior (06/09/2026, sessao 3) — historico

- **A entrega da sessao 2 (commit `83c0901`) estava incompleta.** O Codex
  revisou o commit e reproduziu 3 falhas reais que os 4 testes daquela
  entrega nao cobriam: (1) `aprender-veredito` podia duplicar a licao com
  "sucesso aparente" se a falha ocorresse entre gravar e confirmar o passo
  no journal; (2) uma falha logo apos gravar o marcador de "exportado"
  deixava o retry preso atras da guarda de "ja exportado"; (3) `decidir`
  criava um segundo snapshot orfao a cada retry, porque o caminho nunca era
  congelado. As 3 foram reproduzidas contra o codigo antigo (`git stash` +
  os testes atuais) antes de corrigir — evidencia completa na secao 2 do
  plano.
- **Redesenho do mecanismo**: `tracked_operation`/`OperationHandle` agora
  congelam a `assinatura` (dados de entrada) e o `detalhe` (ex.: caminho do
  snapshot) na 1a tentativa — uma retomada com dados diferentes e recusada
  em vez de misturar passo antigo com dado novo, e o snapshot e reaproveitado
  em vez de duplicado. `op.registrar_efeito()` reconcilia pelo que
  REALMENTE esta gravado no arquivo de destino, nao so pelo que o journal
  diz — resolve a duplicacao sem trocar por perda de gravacao. Journal
  corrompido (JSON invalido ou estrutura incompleta) bloqueia com
  `SystemExit` claro, nunca reinicia sozinho.
  Comando `operacoes-pendentes` continua listando o que ficou `em_andamento`
  (agora separando passos concluidos de passos so tentados).
- **Testes**: `tests/test_operation_recovery.py`, 12 testes (as 3 reproducoes
  exatas dos bugs, retomada com dado incompativel recusada, journal
  corrompido/malformado bloqueia, interrupcao real de subprocesso
  (`os._exit`, nao excecao Python) com recuperacao, e comandos concorrentes
  usando a trava existente).
- Continua **nao sendo transacao atomica entre arquivos** — isso nunca foi
  prometido, e esta documentado assim no docstring de `tracked_operation`,
  junto do limite de recuperacao entre maquinas (`.operacoes/` e local,
  gitignored).

## AO RETOMAR (06/09/2026, sessao 1)

**Auditoria completa entregue: 321 testes passando em 138,343 s.** Relatorio:
[`docs/auditoria-completa-2026-09-06.md`](docs/auditoria-completa-2026-09-06.md).
Baseline da auditoria: `feae025`; os registros de sessoes anteriores abaixo sao historicos.

- Decisao usa a mesma oferta do ranking. Novos snapshots congelam entradas,
  configuracao, motor, ambiente e justificativa, com manifesto e excecoes efetivas.
  Conferir: `python scripts/central_compras.py auditar-decisoes --strict`.
- Promocao exige conferencia monetaria ou reconfirmacao explicita; desconto antigo
  nao sobrevive silenciosamente a uma alteracao de preco. Regra de parada conta
  ofertas atuais distintas e verifica presenca fisica quando exigida.
- Prompt incorpora modelo/candidatos, geracoes e variantes; licoes antigas nao
  desaparecem por limite de dez entradas. Recuperacao inclui historico da categoria.
- Painel usa parser/travas do CLI, valida JSON/origem e preserva formulario no erro;
  TCO, atualizacao automatica e candidatos sem cotacao conferidos no navegador com
  dados sinteticos. Campos possuem labels associados.
- Cache por operacao e isolamento por contexto substituem preferencias eternamente
  antigas e alteracao global de funcoes. Tipos, caminhos, YAML, gates, resposta
  Sheets e instalador receberam protecoes cobertas por testes.
- Benchmark comparativo, mesmo catalogo de 40 projetos/120 produtos: baseline
  15.881 interpretacoes YAML / 24,303 s; atual 5.040 / 11,124 s. Tempos indicativos
  sob carga da maquina; reproduzir com `python tests/benchmark_pipeline.py --projetos 40`.
- Scanner estrito e `git diff --check` passaram. CSVs historicos, fichas reais,
  decisoes antigas, pesos e configuracoes comerciais permaneceram intactos.
- Quatro snapshots ignorados de `.playwright-mcp/` foram preservados, com hashes
  conferidos, em `C:\Users\josem\.central-compras\dados-privados\central-compras\auditoria-2026-09-06\playwright\`.
  Eles causavam a falha inicial do scanner na suite de 287 testes.

**Nuvem:** nao houve novo deploy ou sincronizacao real nesta auditoria. A Versao 9
verificada em 05/09, como `conta-comercial`, continua sendo o ultimo registro confirmado.
Enderecos e procedimento: `docs/infraestrutura-externa.md` e
`docs/aprendizados-google-sheets.md`. O relatorio lista limites de transacoes,
proveniencia, reutilizacao de produtos e endurecimento futuro do receptor.

**Compras:** permanecem como registradas antes da auditoria. O relogio foi fechado
na sessao de 05/09; o veredito D+30 segue pendente. Nenhuma compra foi refeita.

---

## Última sessão: 05/09/2026 — decisão do relógio

- **Compra fechada**: `huawei-band-11-pro`, R$ 346,00 (Mercado Livre),
  `--permitir-cortado` (passou do teto de R$ 300) e `--comprado`. Perdedores
  registrados: Samsung Galaxy Fit3 (única com Samsung Health nativo, mas
  Josemar preferiu geração nova + GPS próprio), Redmi Watch 5 Lite, Xiaomi
  Smart Band 9 Active, Huawei Band 11 comum, Huawei Band 10, Huawei Band 9
  (descartado por instabilidade). Snapshot e veredito criados.
- **Lição cara desta sessão, registrada em `base-conhecimento/licoes.md`**:
  relatório de IA externa (tipo ChatGPT agêntico) pesquisando preço **não é
  confiável sozinho**. Nesta compra ele inventou link de produto (Amazon
  404), errou garantia (disse 12 meses, era 3), o mesmo anúncio do ML voltou
  com 4 preços diferentes em relatórios seguidos, e quase descartou a Band 11
  inteira por "cara" (R$339-418) citando só a variante de alumínio — a
  variante em polímero do mesmo produto estava R$ 214,95 e ninguém tinha
  achado.
  **Correção de método**: quando o Playwright MCP desta sessão consegue
  acessar a loja direto (confirmado em Amazon e KaBuM), pesquisar ali
  primeiro, antes de pedir relatório pra IA externa. Mercado Livre bloqueia
  acesso automatizado (403) — ali só resta prompt pra IA externa ou
  conferência manual do Josemar, e mesmo assim tratar como pista a conferir,
  nunca como preço fechado. Print de tela do próprio Josemar (logado,
  Mercado Livre/Amazon) conta como confirmação manual real.

## Última sessão: 05/09/2026 — Versão 9

- **Versão 9 implantada e verificada.** O `Code.gs` foi atualizado preservando
  o token já existente e publicado como nova versão da implantação atual pela
  conta `conta-comercial@exemplo.com`; ID e URL `/exec` permaneceram iguais.
- O payload passou ao schema 3 de forma aditiva. O receptor continua aceitando
  o formato anterior, avisa sobre campos desconhecidos e não produz `NaN`
  quando métricas novas não existem.
- A `Visao Geral` ganhou fila de atenção e gráfico de pendências comparáveis.
  Scores relativos de compras diferentes deixaram de ser comparados. Projetos
  fechados têm precedência sobre cotação vencida e não entram nas pendências.
- As abas de projeto ganharam contexto, alertas e vereditos de líder, empate,
  bloqueio ou ausência de cotação. O relógio mostra Huawei Band 9 e Galaxy Fit3
  em empate técnico por diferença de 2,2 pontos.
- Duas sincronizações consecutivas retornaram 8 projetos e 8 comparativos. A
  inspeção da planilha confirmou 9 abas, gráfico geral, rankings e gráficos de
  eixos, sem `#REF!`, `#ERROR!`, `NaN` ou `undefined`. Desktop e largura de
  celular foram conferidos; a fila dinâmica não ficou congelada.
- Verificações locais: 287 testes passaram em 143,477 segundos, o scanner
  estrito de segredos passou e o JavaScript documentado passou na checagem de
  sintaxe.

## Sessão anterior: 05/09/2026 — Versão 8

- **Redesign premium implantado e verificado na planilha real.** A implantação
  existente foi atualizada até a Versão 8 sem trocar a URL. O Web App executa
  como `conta-comercial@exemplo.com`. A sincronização final confirmou 8 projetos e 8
  comparativos; a planilha tem 9 abas, um gráfico geral, ranking em cada
  comparativo e gráficos de eixos (ou minigráficos para muitos candidatos).
- A conferência visual encontrou dois bugs invisíveis ao retorno `ok`: o
  congelamento de uma coluna cortava células mescladas, e a transposição de
  intervalos separados deixava o ranking vazio e misturava rótulos no gráfico
  de eixos. Ambos foram corrigidos com testes; os gráficos agora usam fontes
  contíguas fora da área principal.
- `sincronizar-planilha` agora inclui o campo `detalhe` devolvido pelo Apps
  Script na mensagem de erro. Foi isso que permitiu diagnosticar as duas
  falhas sem expor o token.
- Verificações de dados: `11,7`, `11,4` e `10,8` do consumo dos carros seguem
  como números com formato `0.##`; textos permanecem texto. O comparativo dos
  relógios mostra Huawei Band 9 e Galaxy Fit3 em empate técnico.
- **Documentação operacional consolidada.** Os aprendizados de infraestrutura,
  contrato, deploy, tipos, gráficos, validação visual, testes no Windows e
  pesquisa bloqueada por 403 estão em
  `docs/aprendizados-google-sheets.md`. README, CLAUDE, rotina semanal,
  inventário, guia de auditoria e os dois prompts históricos foram alinhados
  ao estado da Versão 8 e à suíte de 284 testes.

### Aprendizados que não podem se perder

- Deploy de Web App deve ser feito por `conta-comercial@exemplo.com`; permissão de
  editor não transfere identidade nem acesso à pasta. Atualize a implantação
  existente com **Nova versão** para manter URL e ID.
- Código documentado, código salvo e código implantado são três estados
  diferentes. Registre qual deles foi realmente alterado.
- HTTP 200 e execução “Concluído” podem conter `{ok: false}`; o cliente deve
  mostrar `detalhe`. Mesmo `ok: true` não valida aparência: abra a planilha.
- Células mescladas não podem atravessar a divisória de colunas congeladas.
  Gráficos devem ler blocos contíguos, orientados como a série espera.
- Rode sincronização duas vezes para conferir idempotência. Rode `unittest` sem
  pipe porque o resumo sai em `stderr`, preserve LF e passe no
  `checar-segredos --strict` antes do commit.

## Sessão anterior: 04/09/2026

- **Versão 5 premium da planilha preparada no repositório, mas ainda não
  implantada.** O payload Python agora acrescenta schema, colunas dinâmicas,
  métricas e valores tipados sem remover os campos lidos pela Versão 4. O
  Code.gs documentado aceita os formatos antigo e novo, registra campos
  ignorados sem abortar, usa escrita em lote, lock, indicadores, gráficos,
  formatação numérica seletiva e limpeza controlada de abas. **A implantação
  ativa continua na Versão 4.** O deploy depende de navegador autenticado em
  **conta-comercial** e confirmação em duas etapas pelo dono; depois disso é
  obrigatório sincronizar e abrir a planilha para validar visualmente. Não
  considerar o retorno `ok` como comprovação.
- **Integração Google Sheets reativada nesta máquina, do zero.** A sessão de
  31/08 (abaixo) dizia que a sincronização já rodava contra "o link
  publicado" — e rodava mesmo, mas **essa informação não bastava para
  retomar**: a URL + token vivem em
  `~/.central-compras/dados-privados/integracao_sheets.json`, que fica **fora
  do Git de propósito** e portanto **não sincroniza entre máquinas**. Nesta
  máquina o arquivo não existia, então a integração parecia nunca ter sido
  ativada. **Lição para o handoff: dado que mora só em `dados-privados`
  precisa estar registrado aqui como "existe, mas é local da máquina X",
  senão o próximo agente reconstrói tudo.**
- **O que existia da rodada de 31/08, achado e neutralizado.** Vasculhando a
  conta conta-comercial (Apps Script "Meus projetos" e "Todos os projetos" não
  mostravam nada; a conta josemardp também não tinha nada), o rastro apareceu
  **na lixeira do Drive**: planilha `Central de Compras - Comparativo de
  Produtos`, criada 31/08, modificada 01/09, aberta 02/09, na raiz do Meu
  Drive. Não foi esta sessão que a apagou. **O Apps Script daquela rodada era
  *container-bound* a ela** (Extensões → Apps Script abre o projeto
  `1dbv6oCJefa6WiAXijBN3XOuFBFolF-JxdzZsQHFLww5r_HlI4Rhycwec`, sem título,
  com `doPost` usando `LockService`): por isso não aparecia em listagem
  nenhuma — com a planilha na lixeira, o script vinculado some junto. **Fica
  a lição de busca: script container-bound não aparece na lista de projetos
  quando o arquivo dono está na lixeira; procure pelo arquivo, não pelo
  script.**
  - **Dois problemas reais de segurança, os dois resolvidos hoje:**
    1. A planilha estava com `Qualquer pessoa na Internet com o link pode
       editar`. Trocado para **Restrito**.
    2. O Web App daquela rodada **continuava ativo e publicado** na internet
       ("Integração Central de Compras", Versão 1 de 31/08 15:30). Ou seja,
       havia **dois endpoints abertos** ao mesmo tempo. A implantação antiga
       foi **arquivada**; conferido com `curl`: o endpoint antigo agora
       responde **404** e o novo segue respondendo normalmente.
  - Conferido antes de mexer: a planilha antiga era espelho dos mesmos dados
    (Visão Geral + abas de carro, servico, decor, fone, câmera), tudo
    já no repositório e já na planilha nova. Nada exclusivo a preservar. Foi
    devolvida à lixeira, agora sem link público e sem endpoint — expira
    sozinha em ~30 dias.
- **Montagem nova (a que está no ar)**, tudo na conta **conta-comercial**:
  - Pasta `Central de Compras` em
    `Meu Drive/10_JOSEMAR_PESSOAL/03_PROJETOS_ATIVOS/02_TECNOLOGIA_E_IA/`
    (id `1MyR5NNhHz5Q2RtSHbgPZxXDV3kRM2ARU`), seguindo o padrão dos outros
    projetos de código dessa conta (FisioAI, DISC).
  - Apps Script `Central de Compras - Sync`, Web App implantado (Versão 3),
    execução como conta-comercial, acesso "qualquer pessoa", protegido por token.
  - Planilha `Central de Compras - Cotacoes e Comparacoes` dentro da pasta.
  - Config local em `~/.central-compras/dados-privados/integracao_sheets.json`
    (fora do repo). Detalhes em `docs/integracao-google-sheets.md`.
- **Três bugs reais achados e corrigidos no caminho**:
  1. O `Code.gs` que estava documentado usava `DriveApp.getRoot()`, que **não
     existe** na API (o certo é `getRootFolder()`). Quebrava toda
     sincronização com `TypeError`. A doc anterior propagava o bug.
  2. `pastaCentral()` procurava a pasta **só na raiz** do Drive: como a pasta
     certa está aninhada, o script criou uma pasta duplicada na raiz na
     primeira execução. Trocado por ID fixo (`DriveApp.getFolderById`). A
     duplicata foi movida para a lixeira com autorização do Josemar.
  3. `sincronizar-planilha` usava `timeout=30` no `urllib`, mas com 8
     projetos a Versão 4 implantada leva ~47s para responder (escreve linha a
     linha, sem batch). Passava do timeout **sempre**, com traceback cru de
     `TimeoutError`. Timeout subido para 120s e mantido. A Versão 5 preparada
     usa `setValues` em lote, mas ainda aguarda deploy e validação visual.
- Sincronização rodada de verdade no fim: `8 projeto(s), 8 comparativo(s)`,
  conferida abrindo a planilha real (abas por projeto, incluindo relógio e
  pulseira).
- **Dois projetos novos de compra** abertos nesta sessão:
  `2026-relogio-integrado-ao-celular-para-passos-e-batimentos` (Huawei Band 9
  escolhido pelo critério de saúde: SpO2 contínuo e FC mais responsiva; **a
  cor preta cotada a R$ 239,88 está esgotada**, as opções vivas são amarela
  R$ 312 e rosa R$ 399, ambas acima do teto de R$ 300) e
  `2026-pulseira-para-huawei-band-9` (o módulo do Band 9 é destacável, então
  a cor da unidade não trava a decisão).

## Última sessão: 31/08/2026 (continuação 3)

- **Sincronização com Google Sheets** (`sincronizar-planilha`, comando novo).
  Josemar pediu pro Gemini construir a planilha + um Apps Script (Web App)
  que recebe JSON via POST e escreve as abas "Visão Geral" + uma por
  projeto; testado por ele de ponta a ponta antes de eu escrever qualquer
  Python. `sheets_export_payload()` reaproveita `project_counts()` e
  `spec_comparison_rows()` (o mesmo motor do dashboard) - extraí
  `comercial_valor`/`atributo_valor` de dentro de `spec_comparison_section`
  como funções puras (texto, estrelas) pra que HTML e planilha nunca
  divirjam no mesmo número. `urllib.request` (stdlib, sem dependência
  nova). Config (URL + token) fica em
  `~/.central-compras/dados-privados/integracao_sheets.json`, fora do repo.
  Planejado com `EnterPlanMode` de novo (mesmo processo da feature de
  estrelas). **Rodou de verdade contra o link publicado** - sem precisar
  ajustar nada pro risco de redirecionamento que eu tinha sinalizado no
  plano. Conferido por outra IA (Codex) direto na planilha real, não só
  pelo "ok" do terminal.
  **Achado na conferência real**: candidato do decor-bloqueador (cotação
  web sem nota) mostrava "0.0 (0 aval.)" em vez de "-" na linha Nota -
  bug de exibição (a nota="0.0" é string não-vazia, então `not nota`
  não pegava; a régua de estrela em si já estava correta, só o texto
  enganava). Corrigido com `quote_float(nota)`, mesmo critério de
  `current_adjusted_rating`. **259 testes passando.**

## Última sessão: 31/08/2026 (continuação 2)

- **Estrelas absolutas no comparativo de características**, pedido do
  Josemar com uma condição inegociável: a nota tem que valer contra o
  mercado, nunca "o melhor destes 5 leva 5 estrelas". Desenho em duas
  etapas — normalizar (`atributos_classificacao`, dicionário irmão de
  `atributos` com valor limpo, nunca dentro do texto livre de exibição) e
  classificar (`estrelas` em `categorias.yaml`, faixas numéricas ou mapa
  categórico, sempre absoluto). Funções novas: `stars_for_attribute`,
  `stars_from_score`, `stars_glyphs`. Linhas Nota e Garantia reaproveitam a
  escala que já existe no motor de score (`quality_score`, `risk_parts`),
  não inventam régua nova. Preço fica sem estrela de propósito (é o único
  eixo relativo ao mais barato do projeto). 21 testes novos, incluindo um
  cenário isolado provando o empate pedido e uma guarda pra nota ausente
  nunca virar 1 estrela por tabela. **245 testes passando.**
  Planejado com `EnterPlanMode` + agente de plano antes de codar (achou 2
  bugs reais no meu rascunho: colisão de linha nova no quadro, e a guarda da
  Nota). Um erro de conta meu na conferência manual (ângulo de visão de
  73,5° deveria valer 2 estrelas, não 3) foi pego pelo proprio teste antes
  de ir pro ar.

## Última sessão: 31/08/2026 (continuação)

- **Comparativo de características no dashboard** (pedido do Josemar: "quadro
  comparativo estilo compara celular"). `spec_comparison_section()` em
  `scripts/central_compras.py`, genérico por categoria (lê
  `atributos_obrigatorios` do `categorias.yaml`), um candidato por coluna,
  linhas comerciais (preço/loja/vendedor/nota/garantia/fonte) + atributos
  técnicos. Atributo ausente vira "-", nunca inventado.
- **Enriquecidos os 5 candidatos da câmera** com 4 atributos técnicos novos
  (ângulo de visão, zoom digital, detecção por IA, áudio bidirecional), todos
  de datasheet oficial do fabricante (TP-Link `static.tp-link.com`, Intelbras
  espelhado por revendedor autorizado), fonte e data em
  `produtos/camera/<id>/pesquisa.md` (não em comentário no YAML - esse já
  é apagado pela escrita, pendência conhecida do repositório).
- Achado no processo: o datasheet oficial da Intelbras iM5 SC só confirma
  "áudio: sim", sem detalhar alto-falante/bidirecional, embora uma busca
  agregada tivesse afirmado "bidirecional" - **não registrado** por falta de
  confirmação primária.

## Última sessão: 31/08/2026

- **Novo projeto: câmera de monitoramento externa**
  (`projetos/2026-camera-de-monitoramento-externa`), categoria `camera` nova
  em `config/categorias.yaml`. Orçamento R$ 200 (unidade) a R$ 800
  (2-3 câmeras), uso externo, sem prazo. Deal-breaker: app de visualização
  tem que ser de qualidade real (padrão Tapo/TP-Link), nada de marca obscura.
- **5 candidatos pesquisados via prompt fechado pro Codex** (fichas técnicas
  oficiais + anúncios reais Amazon/Mercado Livre, 11 cotações web):
  Tapo C500, Tapo TC40, Tapo C320WS, Tapo C510W, Intelbras iM5 SC.
- **Bug real achado e corrigido**, mesmo padrão dos dois do carro:
  `latest_quotes()` escolhia a cotação representante de cada produto só pela
  data mais recente, nunca considerando se ela passava no gate. Registrar uma
  2ª cotação (loja diferente, sem dado de garantia) depois da 1ª (com garantia
  confirmada) fazia o produto ser cortado por "garantia não aceita", mesmo
  havendo cotação válida e não vencida que passava no gate. Corrigido com
  parâmetro `prefer` em `latest_quotes()`: dentro do mesmo nível de
  prioridade (manual não vencida > web não vencida > vencida), cotação que
  passa no gate vence a que não passa; empate desfaz por menor custo.
  Prompt fechado pro Codex, conferido aqui (diff + suíte completa + teste de
  mutação: desfiz a correção e confirmei que só o teste-armadilha falhou).
  **224 testes passando.** Commits `7d6efd8` (fix) e `5e470e2` (projeto),
  já em `origin/main`.
- **Categoria `camera` passou a aceitar `garantia_tipo=nenhuma`** no gate,
  decisão do Josemar em 31/08 (a Tapo TC40 não tinha garantia de fábrica
  confirmada em nenhuma loja, só devolução de 30 dias, e ele não quis cortar
  só por isso). Achado no processo: `nenhuma` também é o valor padrão do CLI
  `cotar` quando ninguém informa `--garantia-tipo`, então essa mudança vale
  tanto pra "não confirmei" quanto pra "confirmei que não tem garantia" -
  daqui pra frente qualquer câmera sem dado de garantia passa o gate. Commit
  `83cc2cd`.
- **Ranking atual da câmera** (tudo `fonte=web`, ninguém confirmou manual
  ainda): 1º Intelbras iM5 SC (95,8, R$ 247,22 ML) e 2º Tapo C500 (94,8,
  R$ 269,91 ML) em empate técnico (diferença ≤3); depois Tapo C320WS (91,0),
  Tapo C510W (78,9) e Tapo TC40 (75,1, a mais barata: R$ 238,41).

## Sessão de 30/08/2026 (fechamento)

- **Ficha técnica dos 10 candidatos do carro preenchida com fonte oficial BR**
  (autonomia, protocolo, potência, porta-malas, garantia de bateria, consumo),
  um commit por candidato, fonte e data em comentário no próprio `produto.yaml`.
  Nenhum preço entrou. SoH só a JAC publica (75%); as demais não publicam.
- **Dois bugs do mesmo tipo achados e corrigidos**, ambos de relatório que
  afirmava o que os dados não sustentavam:
  1. `build_ranking` marcava as etapas 5 e 6 do `processo.md` como concluídas
     mesmo com zero cotações. Agora a 5 exige cotação e a 6 exige pelo menos
     2 candidatos elegíveis. Commit `9159c72`.
  2. A regra de parada contava candidato descartado, tanto na contagem quanto
     na cobrança de cotações. Corrigido nos dois lados da união em
     `stop_rule_status` (descartado com cotação voltava por `cotacoes_por_produto`).
     Commit `301162d`.
  As duas correções vieram de prompt fechado enviado ao Codex e foram
  conferidas aqui: diff, suíte completa e, na segunda, teste de mutação
  (desfiz a subtração de propósito e confirmei que só o teste da armadilha
  falhou). **221 testes passando.**
- **Carro cortado de 10 para 6 candidatos.** Descartados com motivo gravado:
  `byd-seagull` (entrada duplicada, a BYD Brasil vende como Dolphin Mini),
  `jac-e-js1` (181 km), `renault-kwid-etech` (180 km) e `caoa-chery-icar`
  (197 km) por autonomia insuficiente na rota de Araçatuba (120 km ida e
  volta, 2x/mês, uso 71% rodovia).
- **Critério de SoH relaxado no `briefing.md` do carro**, decisão do Josemar
  em 30/08: exigir percentual de SoH garantido eliminava 9 dos 10 candidatos
  e deixava de pé justamente o de menor autonomia. Passou a exigir garantia
  em anos e km por fonte oficial; SoH virou desejável, com registro de que
  era obrigatório até 30/08.

## Sessão de 28/08/2026 (fechamento)

- Escrito `docs/prompt-ajustes-repositorio.md`: prompt autocontido pro Codex
  atacar as 6 pendências gerais do repositório (não bloqueiam nada, mas
  estavam em aberto desde a 3ª auditoria). Ver "Próximo passo" abaixo.

## Sessão de 28/08/2026, rodada 2

- **As duas decisões de calibragem abaixo foram tomadas e implementadas**:
  categoria `carro` marcada `sem_frete` no `categorias.yaml` (eixo
  `conveniencia` sai da conta, confiança deixa de travar em 0,90), e a regra
  de parada agora conta todo `produto.yaml` mapeado pro projeto, não só quem
  tem cotação (`project_candidate_ids()`). 208 testes passando. `validar` no
  carro elétrico já mostra os dois avisos reais: 10 candidatos contra teto de
  4, e os 10 sem cotação suficiente. Commit `1023200`, já em `origin/main`.
- Josemar mandou a conta de energia e a rotina de rotas. Preenchido no
  `briefing.md` do carro: km/mês (~1.141, estimado por rotina declarada, não
  odômetro), 71% rodovia / 29% urbano, tensão residencial 127V bifásico,
  tarifa B1 convencional (~R$ 0,944/kWh bruto). Nenhum dado pessoal da conta
  entrou no repo. Confirmado que data-limite e distância até concessionária
  ainda não existem. Commit `c020649`.

## Sessão de 28/08/2026, rodada 1

- Absorvido o projeto `ev-decisao` (repo local que nunca foi publicado, encerrado
  e apagado). Virou `projetos/2026-comprar-carro-eletrico`: briefing, 10
  candidatos, 11 anotações de pesquisa, 10 lições na categoria `carro`, e
  `pesquisa-herdada.md` com os 14 campos de fonte primária e o simulador de
  viagem. Nenhum preço foi transferido, de propósito: nenhum tinha fonte primária.
- Documentos de origem preservados em
  `projetos/2026-comprar-carro-eletrico/referencia/`, com aviso do que já foi
  substituído pela Central.
- Reescrito `docs/prompt-auditoria-externa.md` para a **3ª rodada de auditoria**.
  Quem rodou não foi o Kimi, foi o **Antigravity** (agente Gemini). O protocolo
  de triagem vale igual, independe de qual LLM auditou.
- **3ª auditoria triada e os 4 bugs confirmados corrigidos**, implementados em
  outra sessão a partir de um prompt fechado, conferidos aqui (diff + teste +
  suíte completa) antes do push: CSRF em `/api/acao` (faltava checar
  `Content-Type`), path traversal em `project_path()` (achei um caso pior do
  que a auditoria relatou: caminho absoluto driblava a checagem inteira, não só
  `..`), crash em `Content-Length` invalido/negativo, e duplicação no cálculo
  de TCO entre `add_quote`/`promote_quote` (agora unificados em
  `compute_costs()`). Commits `bea9824`..`7d03631`, já em `origin/main`.

## Estado atual

- v1 estabilizada, tag `v1.0` publicada. **224 testes passando**
  (`python -m unittest discover -s tests`).
- Quatro projetos: fone bluetooth, Decor Bloqueador, carro elétrico, câmera de
  monitoramento externa.
- **Nenhuma compra fechada ainda.** O ciclo de veredito (D+30 / D+180) nunca
  rodou com dado real.
- `scripts/painel.py` e o `artifact` já foram auditados (3ª rodada), bugs
  corrigidos, e as duas calibragens específicas do carro já decididas e
  implementadas. Seguem pendentes, como julgamento (não bug): `peso_ancora`
  global, escala de prazo por categoria pras demais (não-carro), reatividade
  do painel. Ver "Do repositório" abaixo.

## Próximo passo

> O deploy e o redesign da planilha foram concluídos em 05/09. O que segue
> abaixo são as compras que continuam abertas.

**Câmera de monitoramento:** confirmar manualmente (abrir o checkout de
verdade) o preço/frete/estoque/garantia de pelo menos o Intelbras iM5 SC e o
Tapo C500 (empatados tecnicamente), com `promover-cotacao`, antes de decidir.
Prazo: nenhum.

**Carro elétrico:** coletar cotação dos 6 candidatos vivos (etapa 4 do
`processo.md`). São eles: `byd-dolphin`, `byd-dolphin-mini`,
`chevrolet-spark-euv`, `gac-aion-ut`, `geely-ex2`, `gwm-ora-03-bev58`. A
regra de parada pede 3 cotações + 1 presencial por candidato, e o teto da
faixa é 4 candidatos: **os 2 cortes que faltam dependem de preço**, por isso
não foram feitos ainda. Prazo de decisão: **28/09/2026**.

Ordem sugerida: preço público com fonte e data primeiro (para cortar de 6
para 4), depois cotação presencial na concessionária só dos 4 finalistas.

**Quando o Josemar colar retorno de IA externa aqui, leia
`docs/como-conferir-auditoria.md` ANTES de agir**: conferir diff, rodar
teste, só então aceitar. Funcionou com o Antigravity e funcionou de novo com
o Codex em 30/08. Vale ir além quando a correção é sutil: no bug da regra de
parada, aplicar uma mutação de propósito foi o que provou que o teste novo
tinha poder de detecção real.

## Pendências

### Abertas em 05/09/2026

- [x] **Implantar e conferir o redesign premium.** Concluído na Versão 8; a
  inspeção real encontrou e corrigiu dois bugs após respostas `ok`.
- [x] **Relógio: decidir.** Fechado em 05/09/2026: `huawei-band-11-pro`,
  R$ 346,00, comprado. Ver "Última sessão: 05/09/2026 — decisão do relógio".

### Passos manuais do Josemar (bloqueiam o projeto do carro)

- Levantar em casa: **capacidade do quadro elétrico e distância do quadro até
  a vaga** (define custo de wallbox). Exige inspeção física, ninguém consegue
  fazer por ele.
- **Falar com a esposa.** O briefing exige, como critério de sucesso, que ela
  concorde "por motivos dela, não meus". Ninguém faz por ele, e isso não pode
  aparecer só no fim.

~~Definir data-limite de decisão e distância máxima até concessionária~~:
feito em 29/08/2026 (prazo 28/09/2026, raio de 700 km), commit `30123cb`.

~~Medir km/mês, rotas, tensão residencial~~: feito em 28/08/2026 a partir da
conta de energia e da rotina declarada, ver `briefing.md` do projeto.

### Do repositório

As de 04/09 estão no bloco acima. O que segue é histórico das anteriores.

As 6 que existiam foram todas
resolvidas: skill installer, rotina semanal, `peso_ancora` por categoria e
filtro de CEP (já estavam feitas, a lista é que estava desatualizada); e as
duas últimas — **`write_yaml` apagava comentário de proveniência** e
**`descartar` sobrescrevia a "Próxima ação" com texto genérico** — corrigidas
por prompt fechado ao Codex em 01/09/2026 (commits `3b808c4` e `89baf02`),
conferidas aqui: diff, suíte completa (262 testes) e teste de mutação no
item da "Próxima ação" (desfiz a correção, só os 2 testes-armadilha
falharam, restaurada em seguida). `produto.yaml` ganhou o campo opcional
`proveniencia`; `descartar` agora chama `build_ranking` para recalcular a
próxima ação de verdade, em vez de escrever texto fixo.

## Decisões que valem lembrar

- **Nenhum preço sem fonte primária entra no repositório.** Foi por isso que a
  migração do ev-decisao trouxe a pesquisa e deixou todos os preços para trás.
- **Derivados ficam versionados de propósito** (`ranking.md` ao lado do
  `decisao.md` é a evidência de por que a decisão foi tomada naquele dia).
  Conflito de merge em derivado se resolve com `regenerar`, não à mão.
- O ev-decisao morreu porque **reconstruía o que a Central já faz**. Antes de
  criar ferramenta nova para decidir compra, verificar se a Central já resolve.
