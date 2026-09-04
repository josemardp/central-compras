# STATUS: Central de Compras

> Doc de handoff. Qualquer máquina ou agente retoma a partir daqui.
> Estado do **repositório**. O estado de cada compra fica em
> `projetos/<projeto>/processo.md`, ou rodando
> `python scripts/central_compras.py status projetos/<projeto>`.

## Última sessão: 04/09/2026

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
- **O que existia da rodada de 31/08** (achado vasculhando a conta conta-comercial):
  planilha `Central de Compras - Comparativo de Produtos`, criada 31/08,
  modificada 01/09, na raiz do Meu Drive — **hoje está na lixeira do Drive**
  (não foi esta sessão que apagou). O Apps Script daquela rodada não aparece
  em `script.google.com` provavelmente porque era *container-bound* à
  planilha: com a planilha na lixeira, o script some da listagem.
  **Pendência de segurança**: essa planilha está com
  `Qualquer pessoa na Internet com o link pode editar`. Decidir se restaura
  (e fecha o compartilhamento) ou deixa expirar na lixeira (30 dias).
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
     projetos o Apps Script leva ~47s para responder (escreve linha a linha,
     sem batch). Passava do timeout **sempre**, com traceback cru de
     `TimeoutError`. Timeout subido para 120s. Se o número de projetos
     crescer muito, o próximo passo é trocar `appendRow` por `setValues` em
     lote no Apps Script.
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

Nenhuma pendência aberta no momento. As 6 que existiam foram todas
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
