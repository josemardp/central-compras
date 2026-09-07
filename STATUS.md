# STATUS: Central de Compras

> Doc de handoff. Qualquer máquina ou agente retoma a partir daqui.
> Estado do **repositório**. O estado de cada compra fica em
> `projetos/<projeto>/processo.md`, ou rodando
> `python scripts/central_compras.py status projetos/<projeto>`.

## AO RETOMAR — comece por aqui (07/09/2026, sessao 10)

**Implementando as pendencias da auditoria de 06/09.** Plano com estado por
frente: [`docs/plano-pendencias-auditoria-2026-09-06.md`](docs/plano-pendencias-auditoria-2026-09-06.md).
Frente 2 (recuperacao de operacoes parciais) **concluida sob reserva** —
commit `d49a3cd` (7a revisao). Ja foi declarada concluida 6 vezes antes e
cada vez o Codex achou lacuna nova - **nao declare concluida de novo so
porque os exemplos testados passaram**; leia a secao 2 do plano inteira,
incluindo o inventario comando-a-comando, antes de mexer.

**Frente 3 (receptor Sheets): 2a rodada de revisao do Codex sobre o commit
`d6246b6` achou 3 lacunas novas.** Mesmo padrao da frente 2 - **nao declare
esta frente concluida de novo so porque a rodada anterior (V9→V11) passou**;
leia a secao 3 do plano inteira antes de mexer. As 3 lacunas desta rodada:

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

**Redeploy real: ver o proximo bloco desta sessao** (ainda nao aconteceu no
momento de escrever este paragrafo - se este texto nao foi atualizado
depois, o redeploy NAO aconteceu e a nuvem continua na Versao 11).

Frentes 4 (proveniencia), 5 (produtos reutilizados) e 6 (datas/veredito)
**nao iniciadas** — comece pelo plano, nao redescubra o escopo.

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
