# Plano: pendências da auditoria de 06/09/2026

Rastreia a execução das 6 frentes listadas em
[`auditoria-completa-2026-09-06.md`](auditoria-completa-2026-09-06.md), seção
"Pontos para evolução posterior". Cada sessão que trabalhar numa frente
atualiza o estado dela aqui, no mesmo commit da mudança — é assim que outra
máquina retoma sem perder o fio, igual ao `STATUS.md`.

Estados possíveis: `não iniciada` · `em andamento` · `concluída` · `bloqueada`.

## 1. Preparação

**Estado: concluída** (sessão de 06/09/2026, tarde).

- Lidos `AGENTS.md`, `CLAUDE.md`, `STATUS.md`,
  `docs/auditoria-completa-2026-09-06.md`, `docs/infraestrutura-externa.md`,
  `docs/aprendizados-google-sheets.md`.
- Git conferido: `main` limpo, sincronizado com `origin/main`, sem divergência.
- Baseline rodado antes de qualquer mudança: **321 testes passando em
  117,911 s**, igual ao número reportado pela auditoria — nenhuma sessão
  entre `fc3e269` e agora mexeu no código.

## 2. Recuperação de operações parciais — PRIORIDADE

**Estado: concluída sob reserva** (7ª revisão corrigida na sessão de
07/09/2026 — commit a publicar). Ficou **em andamento** entre cada entrega
e a revisão seguinte que achou lacuna nova — já aconteceu 6 vezes seguidas
(após `83c0901`, `2a682a7`, `833c4b9`, `df08fb5`, `5fb4f7c`, `4908c02`).
**Não declare concluída de novo só porque os exemplos testados passaram** —
confirme contra o inventário da subseção 7ª abaixo (o mais completo até
agora), e verifique se algum comando novo foi adicionado ao CLI, ou algum
comando existente passou a chamar `append_timeline`/`mark_steps`/`set_process_state`/
`build_ranking`, sem entrar nesse inventário.

### 1ª entrega (commit `83c0901`) — insuficiente, revisada pelo Codex

A primeira versão de `tracked_operation`/`OperationHandle` marcava um passo
como feito **depois** de executá-lo (`if not op.concluido(x): fazer(); op.
marcar(x)`). O Codex revisou o commit e reproduziu 3 falhas reais que os 4
testes daquela entrega não cobriam:

1. **Lição duplicada com sucesso aparente.** Se a exceção ocorresse *depois*
   de `register_lesson` gravar e *antes* de `op.marcar("licao")` persistir, o
   journal nunca sabia que o passo tinha sido feito. O retry não falhava —
   terminava "com sucesso" e `licoes.md` ficava com a lição duas vezes.
   Corrigir a ordem (marcar antes de executar) resolveria a duplicação mas
   criaria o problema espelhado: uma falha entre marcar e executar faria o
   journal achar que um passo foi feito quando na verdade não foi, **perdendo**
   a gravação.
2. **Marcador gravado deixava a recuperação presa.** Se a falha ocorresse
   depois de escrever `## Aprendizado exportado D+30` no veredito, o retry
   batia na guarda "já foi exportado, use --force" — que existe para impedir
   reexportar de propósito, não para bloquear a conclusão da própria
   tentativa que falhou.
3. **`decidir` criava um segundo snapshot a cada retry.** `_decide_writes`
   gerava um `instante`/diretório novo em toda chamada; uma falha depois do
   primeiro snapshot e antes do fim deixava um diretório órfão, e o retry
   criava outro, nunca reaproveitando o primeiro.

O Codex também pediu: reconciliação pelo **efeito realmente persistido** (não
só pelo journal), recusa clara quando uma retomada usa dados diferentes da
tentativa que falhou, journal corrompido tratado como "precisa de
conferência" (nunca como "recomeça do zero"), e testes com interrupção real
de processo e com comandos concorrentes.

### Reprodução das 3 falhas, contra o código antigo (`83c0901`)

Confirmadas rodando os testes atuais (`tests/test_operation_recovery.py`)
contra o código antigo via `git stash` — log completo descartável, resultado
citado aqui:

- **Bug 1** (`OperationHandle.marcar` patcheado para lançar exceção no passo
  `"licao"`, exatamente como o Codex descreveu): o retry **não levanta
  exceção** e `base-conhecimento/licoes.md` termina com a linha
  `2026-09-06 - fone - conferir estoque antes` **duas vezes**.
- **Bug 2** (falha simulada logo depois de `append_text` gravar o marcador):
  o retry levanta
  `SystemExit: Este veredito ja foi exportado na fase D+30 [...] Use --force`
  — a operação fica presa, exigindo uma flag que não deveria ser necessária
  para concluir a própria tentativa que falhou.
- **Bug 3** (falha simulada em `append_timeline` na linha "veredito"): o
  diretório `snapshots/` passa de 1 para 2 entradas depois do retry
  (`['20260906T190320944610-candidato', '20260906T190321136703-candidato']`).

Rodando os MESMOS testes contra o código corrigido: os 3 passam, mais 9
testes adicionais (12 no total).

### Correção

Redesenho de `tracked_operation`/`OperationHandle` em
`scripts/central_compras.py`:

- **`assinatura`**: impressão digital dos dados de ENTRADA da tentativa
  (preço, justificativa, perdedores, marca/loja/lição/notas). Uma retomada
  com o mesmo `op_id` mas `assinatura` diferente é **recusada** com
  `SystemExit` explicando o motivo — nunca mistura passo antigo com dado
  novo. Quem quiser recomeçar do zero apaga o journal manualmente, depois de
  conferir com `operacoes-pendentes`.
- **`detalhe` congelado**: dados como o caminho do snapshot são decididos na
  1ª tentativa e devolvidos via `op.detalhe` em qualquer retomada — nunca
  recalculados. Resolve o bug 3: `decidir` reusa o mesmo diretório de
  snapshot num retry.
- **`op.registrar_efeito(passo, arquivo, assinatura_efeito, executar)`**:
  resolve o bug 1 sem trocar duplicação por perda. Grava a assinatura do
  efeito ANTES de executar (para uma próxima chamada saber o que procurar);
  se o passo já estava "tentando", confere se a assinatura **congelada**
  daquela tentativa já está no arquivo de destino antes de decidir se executa
  de novo — nunca decide pela assinatura recém-calculada, que pode diferir da
  congelada (ex.: o título de um arquivo de marca que não existia na 1ª
  tentativa e passou a existir depois que o efeito ocorreu).
- **Marcador de "exportado"**: resolve o bug 2 reconhecendo, através de
  `has_pending_operation`, quando a guarda de "já exportado" está vendo o
  efeito da PRÓPRIA tentativa que falhou (não um reexport de propósito) — e
  nesse caso não exige `--force`.
- **Journal ilegível nunca reinicia sozinho**: JSON inválido OU JSON válido
  com estrutura incompleta levanta `JournalPrecisaReconciliacao`, convertida
  em `SystemExit` explicando o que fazer. O arquivo nunca é sobrescrito nem
  apagado automaticamente.
- **`operacoes-pendentes`** agora mostra passos concluídos separados de
  passos "tentados sem confirmar".
- **Limite entre máquinas, documentado no docstring de `tracked_operation`**:
  `.operacoes/` é local (gitignored) e não viaja no `git pull`. A defesa não
  é técnica, é de rotina: rodar `operacoes-pendentes --strict` antes de
  commitar/dar push, e `git status` ao voltar numa máquina onde ficou
  trabalho parado.

Continua **não sendo transação atômica entre arquivos** — isso nunca foi
prometido, e está dito assim no código.

### Testes

`tests/test_operation_recovery.py`, **12 testes**:

- as 3 reproduções exatas dos bugs 1, 2 e 3, com asserção explícita de que
  não regridem;
- retomada com justificativa diferente (decidir) e com lição diferente
  (aprender-veredito) são recusadas com mensagem clara;
- journal com JSON inválido e journal com JSON válido mas estrutura
  incompleta bloqueiam a operação (não reiniciam do zero) e preservam o
  arquivo;
- `pending_operations` relata journal ilegível sem apagá-lo;
- `operacoes-pendentes` relata e some depois que a operação completa
  (incluindo código de saída `--strict`);
- comandos concorrentes no mesmo projeto (3 threads chamando `decidir` ao
  mesmo tempo) não corrompem `processo.md` — a trava existente
  (`project_lock`) continua serializando;
- **interrupção real de subprocesso**: `python scripts/central_compras.py
  decidir ...` roda de verdade, é morto com `os._exit(70)` (sem exceção
  Python) num ponto controlado por variável de ambiente
  (`CENTRAL_COMPRAS_TESTE_CRASH_APOS`), e um segundo processo, limpo, recupera
  sem duplicar snapshot nem linha de linha do tempo.

Suíte completa depois da mudança: ver `STATUS.md` para o número final.

### 3ª revisão (Codex, sobre o commit `2a682a7`) — 3 falhas mais profundas

A 2ª correção resolveu os 3 bugs daquela rodada, mas o Codex reproduziu mais
3, todos na mesma raiz: eu tratava "gravar o snapshot" como uma sequência de
escritas independentes, quando deveria ser uma unidade que vira imutável ao
concluir; e `registrar_efeito` confundia "esse texto existe no arquivo" com
"esta operação, especificamente, teve efeito".

1. **Manifesto invalidado pela própria recuperação.** Numa retomada,
   `_decide_writes` reusava o diretório do snapshot (correto) mas
   RECALCULAVA o manifesto contando também o `manifesto.json` que a própria
   tentativa anterior tinha deixado ali — um arquivo que descreve a si mesmo
   nunca bate com o próprio conteúdo depois de ser reescrito. `auditar-
   decisoes --strict` acusava "arquivo alterado: manifesto.json" mesmo com
   `operacoes-pendentes` vazio. Confirmado existir apenas o arquivo nunca
   provou integridade — era preciso rodar a auditoria de verdade.
2. **Snapshot reescrito com entradas diferentes.** O caminho do snapshot
   estava congelado, mas o CONTEÚDO era recalculado a cada tentativa —
   `config/preferencias.yaml`, `categorias.yaml`, briefing e fichas de
   produto eram relidos do disco atual. Uma calibragem feita entre a falha e
   o retry (reproduzido mudando `preferencias.yaml`) vazava para dentro da
   evidência já "congelada", contradizendo o propósito do snapshot.
3. **Texto igual não identificava a operação.** `registrar_efeito` decidia
   "o efeito já aconteceu" só checando se a assinatura aparecia em algum
   lugar do arquivo — sem distinguir uma ocorrência de uma operação
   completamente diferente e legítima (duas lições idênticas, exportadas de
   projetos distintos, no mesmo dia). Uma retomada interrompida bem no início
   (antes de executar a gravação de verdade) via a entrada ALHEIA já
   presente, concluía "já feito" e nunca gravava a própria — perda
   silenciosa de conhecimento, com a pendência desaparecendo mesmo assim.

**Reprodução dos 3, contra o código antigo (`2a682a7`, via `git stash` + os
testes atuais):** `ERRO 2026-auditoria/<snapshot>: arquivo alterado:
manifesto.json` (bug 1); bytes do `preferencias.yaml` dentro do snapshot
literalmente ganhando a linha `valor_alterado_no_teste: true` injetada depois
do crash (bug 2); contagem de `"conferir garantia antes"` ficando em 1 em vez
de 2 depois da retomada de uma segunda exportação legítima (bug 3).

**Correção — revisão do contrato inteiro, não só dos 3 exemplos:**

- **`OperationHandle.executar_uma_vez(passo, executar)`**: primitivo novo
  para captura de VÁRIOS arquivos por sobrescrita cega (não append-only).
  Regra binária: `passo` concluído → não toca em NADA (evidência já
  finalizada permanece intacta, resolve os bugs 1 e 2 de uma vez, sem
  precisar fingerprintar preferências/categorias/fichas uma por uma); `passo`
  nunca concluído (nem tentado, ou interrompido no meio) → refaz a captura
  inteira do zero, seguro porque é sobrescrita, nunca duplica. `_decide_writes`
  agora chama isto uma vez, envolvendo build_ranking + todo o snapshot +
  `decisao.md`.
- **`manifesto.json` nunca entra no próprio manifesto** (`path.name !=
  "manifesto.json"` no glob) — defesa adicional, ainda que
  `executar_uma_vez` já torne o cenário que expôs isso impossível.
- **`registrar_efeito` agora identifica pela CONTAGEM de ocorrências antes
  da tentativa começar** (`contagem_anterior`, congelada junto da
  assinatura), não pela presença. Uma retomada só considera o efeito feito
  se uma ocorrência NOVA apareceu depois que ESTA tentativa começou —
  ocorrências pré-existentes (de outra operação legítima) nunca contam como
  prova de que esta, especificamente, teve efeito.

### Testes

`tests/test_operation_recovery.py`, **18 testes** (12 da 2ª revisão + 6
novos): as 3 reproduções da 3ª revisão (incluindo variantes "falha antes de
executar" e "falha depois de executar" para o bug 3, mais duas fases com
texto idêntico), e o teste de concorrência trocado de threads por
**processos separados de verdade** (`subprocess.Popen`), com verificação de
que todo código de saída não-zero é exatamente o timeout de trava esperado
(nunca corrupção), que o número de linhas de decisão bate exatamente com o
número de sucessos, e que `auditar-decisoes --strict` passa ao final.

### 4ª revisão (Codex, sobre o commit `833c4b9`) — operações intercaladas

A 3ª correção resolveu a reconciliação DENTRO de uma operação sendo
retomada, mas o Codex reproduziu 2 falhas que atravessam DUAS operações
diferentes, intercaladas no tempo:

1. **Perda de lição entre operações intercaladas.** A é interrompida em
   `licao:iniciado`, antes de gravar. B (veredito diferente, mesma lição,
   mesma categoria, mesmo dia) roda completo e grava a própria linha. Ao
   retomar A, a contagem-delta (correção da 3ª revisão) via a linha de B
   como se fosse prova de que A tinha escrito — A "concluía" sem nunca
   gravar a própria lição, e a pendência sumia mesmo assim.
2. **Decisão recuperada diverge do documento atual.** `decidir A` captura
   (escreve `decisao.md` com "Produto ID: A") e é interrompido na timeline
   "veredito". `decidir B`, do MESMO projeto, roda completo — sua própria
   captura SOBRESCREVE `decisao.md` para "Produto ID: B". Ao retomar A,
   `executar_uma_vez("captura", ...)` via a captura já marcada `concluída`
   (da 1ª tentativa de A) e não tocava em nada — mas o `decisao.md` real já
   não era mais o de A. A retomada terminava "com sucesso", imprimindo o
   snapshot de A, enquanto `decisao.md` continuava dizendo B.

**Causa raiz:** `project_lock`/trava de `BASE` só serializam enquanto um
comando está RODANDO. Nenhum dos dois protege o período em que uma operação
fica PENDENTE depois de uma falha — é exatamente nessa janela que uma
segunda operação, legítima e sem relação alguma com a primeira, escreve nos
mesmos arquivos.

**Reprodução, contra o código antigo (`833c4b9`, via `git stash` + os
testes atuais):** as 4 tentativas de bloquear B (`assertRaisesRegex(
SystemExit, "ja reivindica")`) falharam com `SystemExit not raised` — B
simplesmente rodava e corrompia o estado de A, exatamente como relatado.

**Estratégia escolhida: bloqueio conservador, não identidade persistente
por linha.** O relatório ofereceu duas saídas — bloquear antes de qualquer
escrita, ou permitir intercalamento com identidade persistente do efeito e
regra explícita de precedência. Optei pela primeira: inventar um
identificador embutido em cada linha de `licoes.md`/`marcas/*.md` (arquivos
pensados para leitura humana) trocaria uma lacuna por uma poluição
permanente do histórico, e ainda deixaria em aberto a regra de precedência
para decisões — que este repositório já trata como decisão do Josemar, não
do código (`docs/como-conferir-auditoria.md`). Bloquear é reversível
(basta retomar ou resolver a pendência) e não inventa fato novo.

**Correção — contrato de conflito, não só os 2 exemplos:**

- Cada operação declara, ao começar, os `recursos` (arquivos) que vai
  escrever fora do próprio journal: `decidir` declara `decisao.md` e
  `processo.md` do projeto (arquivos ÚNICOS por projeto, não por produto —
  é por isso que `decidir A` e `decidir B` do mesmo projeto colidem);
  `aprender-veredito` declara `licoes.md` (se houver lição — compartilhado
  por TODA exportação, de qualquer projeto) e o arquivo de marca/loja
  específico (se o nome coincidir com outra operação pendente).
- Uma operação NOVA (sem journal próprio ainda) que reivindicaria um
  recurso já reivindicado por outra `em_andamento` é RECUSADA antes de
  escrever qualquer byte, com `SystemExit` nomeando a operação conflitante
  e orientando a resolver a pendência primeiro (`operacoes-pendentes`).
- Uma RETOMADA (mesmo `op_id`) nunca recalcula nem reconfere `recursos`:
  eles já foram reivindicados pela própria operação na 1ª tentativa.
- Escritores diretos que nunca passam por `tracked_operation`
  (`registrar-licao`, `registrar-marca`, `registrar-loja`) também checam a
  reivindicação antes de escrever, pela mesma função (`_recusar_se_recurso_
  pendente`) — a lacuna não era só dentro do journal, era em qualquer
  caminho de escrita para o mesmo arquivo.

### Testes

`tests/test_operation_recovery.py`: 18 → **22 testes**. Os 4 novos cobrem:
B bloqueada e nada dela escrito, depois A recuperada e SÓ ENTÃO B rodando
com sucesso (lição e decisão, os dois cenários); `registrar-licao` direto
também bloqueado pela mesma pendência; `registrar-marca`/`registrar-loja`
também bloqueados. O cenário de decisão confere coerência entre
`decisao.md`, `processo.md` (timeline), snapshot e veredito em cada etapa,
e roda `auditar-decisoes --strict` depois de cada recuperação.

### 5ª revisão (Codex, sobre o commit `df08fb5`) — proteção incompleta por construção ad-hoc

Os 22 testes da 4ª revisão passaram, mas o Codex reproduziu 2 falhas que
mostram que a proteção só cobria os comandos citados nos testes, não todos
os que escrevem nos mesmos arquivos:

1. **Escritor direto não protegido.** `anotar --etapa decisao --decisao
   "Escolhido candidato" --porque <mesmo texto>` escreve na MESMA linha de
   `processo.md` que `decidir` reivindica, mas `anotar` nunca tinha sido
   conectado a `_recusar_se_recurso_pendente` (só `registrar-licao`,
   `registrar-marca`, `registrar-loja` tinham sido, porque foram os
   exemplos da 4ª revisão). Rodava livre, e a retomada de `decidir` confundia
   a linha de `anotar` com o próprio efeito.
2. **Journal ilegível desativava a proteção.** `_recursos_reivindicados_por_
   outros` só olhava journals `em_andamento`; um journal corrompido chegava
   como `journal_ilegivel` e era simplesmente ignorado pela checagem de
   conflito (embora `pending_operations`/`operacoes-pendentes` já o
   reportassem corretamente como pendência). Resultado: corromper o JSON de
   um journal pendente **destravava** a proteção para aquele recurso, o
   oposto do que corrupção deveria causar.

**Reprodução, contra o código antigo (`df08fb5`):** os 4 `SystemExit`
esperados (`anotar`, journal ilegível + `registrar-licao`,
`preencher-veredito`, `novo-veredito --force`) nunca eram levantados —
todos os quatro escreviam livremente.

**Causa raiz confirmada pelo padrão repetido 4 vezes: eu conectava a
proteção comando por comando, dentro de cada função, na medida em que um
teste apontava a lacuna.** A correção desta rodada parou de fazer isso.

**Correção — inventário completo + ponto único de checagem:**

| Comando | Arquivos REALMENTE escritos (verificado no código) | Trava adquirida | Verificação de conflito |
|---|---|---|---|
| `decidir` | `decisao.md`, `processo.md`, snapshot próprio, **e o arquivo de veredito** (`vereditos/<data>-<projeto>-<produto>.md`, via `create_verdict`) — corrigido na 7ª revisão, faltava | projeto (+ `base-conhecimento/`, herdado de `KNOWLEDGE_COMMANDS`) | `tracked_operation`; veredito congelado em `op.detalhe["veredito_nome"]` e criado dentro de `executar_uma_vez("veredito", ...)` |
| `aprender-veredito` | `licoes.md`, `marcas/<slug>.md`, `lojas/<slug>.md` (se aplicável), o arquivo de veredito | `base-conhecimento/` | `tracked_operation` |
| `anotar` | `processo.md`, via `append_timeline` | projeto | central |
| `cotar` | `cotacoes.csv` (`append_quote`) **e** `processo.md` (`append_timeline` + `mark_steps`) | projeto | central — cobre `processo.md`; `cotacoes.csv` continua como risco aceito (ver limitação) |
| `promover-cotacao` | `cotacoes.csv` **e** `processo.md` (`append_timeline` + `mark_steps` + `set_process_state`) | projeto | central — idem `cotar` |
| `novo-produto` | `produtos/<categoria>/<id>/produto.yaml`, `pesquisa.md` **e** `processo.md` (`append_timeline` + `mark_steps`) | projeto + `produtos/` | central — cobre `processo.md`; ficha do produto continua como risco aceito |
| `ranking` | `ranking.md`, `ranking.csv` **e** `processo.md` (`mark_steps` + `set_process_state`, sempre que há cotação) | projeto | **corrigido nesta rodada** — antes não bloqueava nada, mesmo escrevendo `processo.md` |
| `descartar` | `produto.yaml` **e** `processo.md` (`append_timeline` direto + de novo via `build_ranking` interno) | produto (`produtos/`) — **projeto não era travado quando `--projeto` era omitido, corrigido nesta rodada** | central — resolve o projeto pela ficha do produto quando `--projeto` falta, igual ao comando de verdade |
| `aguardar-preco` | `produto.yaml` **e** `processo.md` (`append_timeline` + `set_process_state`) | produto (`produtos/`) — mesma correção de trava de `descartar` | central, mesma resolução implícita |
| `regenerar` | `ranking.md/csv`, `validacao.md`, histórico, dashboard, **e `processo.md` de cada projeto tocado** (via `build_ranking` interno) | todos os projetos (ou um) + `base-conhecimento/` + dashboard | **corrigido nesta rodada** — declara `processo.md` de cada projeto no escopo |
| `novo-projeto` (sem `--force`, projeto novo) | briefing/processo/ranking/decisão/cotações do projeto sendo criado | `projetos/` (raiz) | não se aplica — nada pode reivindicar um caminho que ainda não existia |
| `novo-projeto --force` (projeto já existe) | os mesmos arquivos, **sobre um projeto que já existe** | `projetos/` (raiz) **e o próprio projeto, corrigido nesta rodada** | **corrigido nesta rodada**, em duas camadas: (1) central, contra operação pendente; (2) `_projeto_com_progresso_real()`, independente de pendência — recusa se `cotacoes.csv` tiver linha além do cabeçalho, `decisao.md` divergir do template vazio, ou `snapshots/` não estiver vazio |
| `registrar-licao` | `licoes.md` | `base-conhecimento/` | central |
| `registrar-marca` | `marcas/<slug>.md` | `base-conhecimento/` | central |
| `registrar-loja` | `lojas/<slug>.md` | `base-conhecimento/` | central |
| `preencher-veredito` | arquivo de veredito | `base-conhecimento/` (histórico, mantido) | central — **corrigido nesta rodada**: journal ilegível em BASE agora também bloqueia recursos em `vereditos/` (ver abaixo) |
| `novo-veredito --force` | arquivo de veredito | projeto | central |
| `categorias.yaml` (gate) | só via `apply_lesson_gate`, sempre junto de uma gravação em `licoes.md` na mesma chamada | — | coberto transitivamente: todo caminho que grava `categorias.yaml` também grava `licoes.md` na mesma operação |
| `briefing.md` | só via `set_project_state`, chamado apenas de dentro de `decidir` | — | não há comando standalone que escreva `briefing.md` |
| `validar`, `auditar`, `historico`, `migrar-cotacoes` | arquivos de relatório próprios (`validacao.md` etc.) ou `cotacoes.csv` só via `write_quotes` (reescreve cabeçalho, preserva linhas) | conforme já definido | verificado que **não** chamam `append_timeline`/`mark_steps`/`set_process_state`/`build_ranking` — confirmado lendo o corpo de cada função, não presumido |

Ponto único de checagem: `_bloquear_se_recursos_conflitantes()`, chamada (a)
dentro de `tracked_operation`, para operações com journal próprio
(`decidir`, `aprender-veredito`), e (b) uma vez em `main()`, para os
escritores diretos da tabela `RECURSOS_DIRETOS_POR_COMANDO`, logo após as
travas serem adquiridas e antes de `args.func(args)` — nenhuma checagem
solta dentro de função individual. `_recursos_diretos_processo()` é o
resolver comum a `anotar`/`cotar`/`promover-cotacao`/`novo-produto`/
`ranking`/`descartar`/`aguardar-preco`: todos escrevem `processo.md` do
MESMO projeto por baixo, então um resolver só, reaproveitado, é mais
confiável do que seis resolvers quase iguais divergindo com o tempo.

**Journal ilegível bloqueia todo escopo que aquele TIPO de operação pode
alcançar, não só a pasta física onde o `.operacoes/` mora.** Um journal de
`aprender-veredito` vive em `base-conhecimento/.operacoes/`, mas a operação
também reivindica o arquivo de veredito, em `vereditos/` — classificar só
pela pasta do journal deixava esse recurso "fora do alcance". Corrigido com
`_escopos_alcancados_por()`, ANTES da 7ª revisão: BASE alcançava BASE e
`vereditos/`; qualquer projeto só alcançava ele mesmo (`decidir` nunca
reivindicava nada fora do próprio projeto — o que a 7ª revisão mostrou
estar errado, ver abaixo).

### Testes

`tests/test_operation_recovery.py`: 26 → **31 testes** (30 na suíte
permanente; 1 segue flaky por corrida de limpeza de arquivo temporário do
Windows, não relacionado a este mecanismo — reproduzido isoladamente 5x
sem falhar, registrado como ruído conhecido, não como achado). As 4
reproduções desta rodada foram confirmadas **duas vezes**: como teste
permanente (via `ambiente.RepoTestCase`, contra o código atual) e como
script avulso rodando **subprocessos reais** contra uma cópia isolada do
código do commit `5fb4f7c` (extraída com `git show`, nunca via `git
stash`, para não mexer no workspace compartilhado) — os 3 primeiros casos
reproduzidos byte a byte como o relatório descreveu (cotações truncadas,
`processo.md` alterado, veredito reescrito), depois confirmados bloqueados
rodando o MESMO script contra o código corrigido.

### 7ª revisão (Codex, sobre o commit `4908c02`) — `decidir` nunca declarava o veredito

O Codex confirmou os 4 casos da 6ª revisão bloqueados e a retomada
funcional, mas achou uma omissão nova: `decidir` escreve no arquivo de
veredito (via `create_verdict`, dentro de `_decide_writes`), mas só
declarava `decisao.md` e `processo.md` como `recursos` — nunca o próprio
veredito. Dois sentidos de conflito, os dois reais:

**A. Aprendizagem pendente → decisão sobrescreve veredito.** Uma decisão
já fechada e completa (sem nada pendente dela mesma); D+30 preenchido;
`aprender-veredito` interrompido em `licao:iniciado` (pendente, já
reivindicando o arquivo de veredito desde a 5ª revisão). Um `decidir
--force-veredito` NOVO (não é retomada de nada — a decisão original já
tinha terminado) nunca via essa pendência, porque nunca declarava o
veredito como recurso próprio: rodava livre, `create_verdict(force=True)`
sobrescrevia o arquivo com o template em branco, apagando o D+30. A
retomada de `aprender-veredito` então falhava com "Fase D+30 ainda em
branco" — a lição, marca e loja já tinham sido extraídas para a base de
conhecimento antes do crash simulado, mas o marcador de exportado nunca
foi gravado, então a pendência ficava presa sem solução automática.

**B. Decisão pendente → preenchimento perdido na própria retomada.**
`decidir --comprado --force-veredito` interrompido em
`timeline_veredito:iniciado` — ou seja, DEPOIS que `create_verdict` já
tinha rodado uma vez nesta própria tentativa, criando o veredito. Human
preenche D+30 na janela. Retomar o MESMO comando `decidir`: como
`create_verdict` nunca era protegido por `executar_uma_vez` (diferente da
captura), a retomada chamava `create_verdict(force=True)` de novo,
incondicionalmente — apagando o preenchimento, mesmo sem qualquer segunda
operação envolvida.

**Reprodução, contra o código antigo (`4908c02`, via `git show` +
subprocessos reais, sem `git stash`):** caso A — `decidir --force-veredito`
roda com `returncode 0`, D+30 some do veredito, retomar
`aprender-veredito` falha com "Fase D+30 ainda em branco"; caso B —
`preencher-veredito` roda livre na janela de pendência (`returncode 0`),
D+30 é preenchido, e a retomada de `decidir` o apaga de novo.

**Correção:**

- `decide()` agora congela `veredito_nome` em `op.detalhe` (mesmo princípio
  do `snapshot_rel`: calculado com `today()` só na 1ª tentativa, nunca
  recalculado numa retomada) e declara `VEREDITOS / veredito_nome` como
  `recursos`, junto de `decisao.md`/`processo.md`. Isso sozinho fecha o
  caso A: um `decidir --force-veredito` novo agora é recusado enquanto
  `aprender-veredito` (ou qualquer operação) tiver aquele veredito
  reivindicado — e, como efeito direto, `preencher-veredito` também passou
  a ser bloqueado enquanto o próprio `decidir` está pendente no mesmo
  arquivo, o que evita a intercalação do caso B antes mesmo dela começar.
- `create_verdict()` ganhou parâmetro opcional `path` (evita recalcular
  `today()` a cada chamada) e a chamada dentro de `_decide_writes` passou a
  rodar dentro de `op.executar_uma_vez("veredito", ...)` — defesa adicional
  para a retomada da PRÓPRIA operação nunca recriar um veredito já criado,
  mesmo num cenário hipotético em que o bloqueio por `recursos` não
  estivesse ativo.
- `_escopos_alcancados_por()`: qualquer projeto agora também alcança
  `vereditos/` (antes só BASE alcançava). Um journal ilegível de `decidir`
  (que vive na pasta do projeto) passou a bloquear também o arquivo de
  veredito fora dela.

### Testes (7ª revisão)

`tests/test_operation_recovery.py`: 31 → **35 testes**. Os 4 novos: caso A
(bloqueio, depois recuperação da aprendizagem pendente, só então
`--force-veredito` permitido); caso B (a retomada de `decidir`, sozinha,
não chama `create_verdict` de novo — contado via patch — e preserva um
marcador escrito manualmente no arquivo); bloqueio de `preencher-veredito`
enquanto `decidir` está pendente no mesmo veredito; journal ilegível de
`decidir` bloqueando o veredito fora da pasta do projeto. Reproduções
confirmadas contra o código antigo (`4908c02`) via `git show` + script com
subprocessos reais, sem `git stash`.

### O que este mecanismo não cobre (registrado, não é lacuna escondida)

- Concorrência entre dois processos ao mesmo tempo continua dependendo só de
  `project_lock`/`BASE` lock; o journal em si não tem lock próprio (documentado
  no docstring de `tracked_operation`). Testado com processos separados de
  verdade, não só threads.
- Falta de espaço em disco no meio da própria escrita do journal ainda pode
  deixar um estado inconsistente — é o mesmo limite que já existia em
  `atomic_write_text` para qualquer arquivo isolado.
- Retomada que atravessa a virada do dia: a linha de linha do tempo
  reexecutada leva a data do dia da retomada, não da tentativa original (a
  assinatura/contagem congeladas evitam duplicação, mas não fixam a data de
  um efeito que nunca chegou a acontecer). Não é duplicação, é nuance de
  atribuição de data — registrado, não escondido.
- O bloqueio por `recursos` é deliberadamente GROSSO: qualquer duas
  operações pendentes que toquem o mesmo arquivo colidem, mesmo que o
  conteúdo específico não colidisse (duas lições DIFERENTES, por exemplo).
  Escolha consciente pela simplicidade e segurança — este é um sistema de
  um único operador, crash deveria ser raro e resolvido na hora.
- **Risco residual, ainda aceito nesta rodada:** `cotacoes.csv` (via
  `cotar`/`promover-cotacao`) e a ficha do produto (`produto.yaml`, via
  `novo-produto`/`descartar`/`aguardar-preco`) **não** são declarados como
  `recursos` — só o `processo.md` que essas mesmas chamadas também escrevem
  passou a ser protegido nesta rodada. Isso é diferente da justificativa
  anterior ("não bloqueado porque o comando não escreve nada reivindicável"),
  que a 6ª revisão mostrou ser **factualmente errada**: esses comandos SEMPRE
  escrevem `processo.md` também, e é isso que agora os bloqueia
  indiretamente sempre que `decidir` tem `processo.md` pendente. O risco que
  sobra é mais estreito do que antes, mas não nulo: numa janela hipotética
  em que `processo.md` NÃO estivesse entre os recursos pendentes mas
  `cotacoes.csv`/`produto.yaml` fossem relevantes, nada bloquearia. Não
  identificado nenhum cenário concreto assim até agora.
- Todo comando novo que passar a escrever `processo.md`, `decisao.md`,
  `licoes.md`, `marcas/*.md`, `lojas/*.md` ou um arquivo de veredito —
  direto OU por meio de `append_timeline`/`mark_steps`/`set_process_state`/
  `set_project_state`/`build_ranking` — precisa ser adicionado à tabela
  `RECURSOS_DIRETOS_POR_COMANDO`. Não há checagem automática disso; é
  responsabilidade de revisão de código. **Ao revisar, procure pelas 5
  funções acima no corpo do comando, não confie em suposição sobre "o que
  esse comando deveria escrever".**
- Não cobre a exportação para o Google Sheets (frente 3) nem qualquer outra
  sequência multi-arquivo fora de `decidir`/`aprender-veredito`. Se uma
  sessão futura achar outro ponto candidato, reaproveite
  `registrar_efeito`/`executar_uma_vez`/`recursos`, não reinvente.

## 3. Receptor do Google Sheets

**Estado: 3ª rodada de revisão do Codex sobre o commit `c5018dc` achou mais 2
ajustes (1 no Code.gs, 1 no cliente Python) — corrigidos e testados
localmente (07/09/2026), redeploy do Code.gs em andamento.** Mesma lição da
frente 2: **não declare esta frente concluída "para sempre" só porque
algumas rodadas já passaram — a próxima revisão pode achar outra lacuna** —
leia esta seção inteira antes de mexer.

### 1ª rodada (commits `84ecb64` + `d6246b6`) — histórico

Os 3 pontos pendentes de código foram corrigidos, implantados pela conta
`conta-comercial@exemplo.com` e verificados com sincronização real — ver
`docs/integracao-google-sheets.md`, seção "Code.gs (versão 11 ativa)":

1. **Validação do payload inteiro antes de escrever qualquer aba** —
   `validarPayload(dados)` roda logo depois de `coletarAvisos`, antes de
   `pastaCentral()`/qualquer `escreverX()`. Reproduzido antes da correção:
   um `null` em `visao_geral` derrubava `escreverVisaoGeral` DEPOIS de
   `escreverComparativo` já ter reescrito a aba do projeto — planilha ficava
   parcialmente atualizada. Depois da correção: recusa antes de qualquer
   escrita (`abas_escritas_antes_da_falha: []` na resposta de erro).
2. **Abas manuais não são mais candidatas a remoção por parecer geradas** —
   `limparAbasOrfas` não usa mais padrão de nome (`/^20\d\d-/` etc.); agora
   consulta um registro real (`PropertiesService`, propriedade
   `abas_geradas_pelo_script`) de que abas o PRÓPRIO script escreveu em
   sincronizações anteriores. Reproduzido antes da correção: uma aba criada
   à mão como `2026-manual` era apagada assim que o projeto correspondente
   saía do payload, só porque o nome batia com o padrão. Depois: só apaga o
   que está no registro.
3. **Falha no meio da escrita agora diz o que já foi gravado** — a resposta
   de erro ganhou `abas_escritas_antes_da_falha`; `sincronizar_planilha()`
   (Python) inclui essa lista na mensagem de erro.

Os 3 casos foram reproduzidos de verdade ANTES do deploy: um script Node
(`repro_gap1_payload_null.js`, `repro_gap2_aba_manual.js`,
`repro_gap3_falha_parcial.js`, no scratchpad da sessão, não commitados)
carrega o Code.gs de fato (extraído do doc) com fakes mínimos do runtime do
Apps Script (`SpreadsheetApp`/`DriveApp`/`PropertiesService`/etc.) e executa
`doPost` de ponta a ponta — os 3 falharam do jeito descrito contra o código
antigo e passaram contra o corrigido, incluindo duas sincronizações
idênticas seguidas sem duplicar aba.

**Redeploy real (07/09/2026, conta `conta-comercial@exemplo.com`):** o perfil de
navegador `conta-comercial` estava ocupado por um processo Chrome travado de uma
sessão anterior; com autorização explícita do Josemar, o processo foi
encerrado (`taskkill /T /F`) e o navegador voltou a funcionar — sem tocar em
nenhum outro perfil. Editei o `Código.gs` ao vivo no editor (substituição
cirúrgica via `monaco.editor` — só as regiões que mudaram, nunca reescrevendo
o arquivo inteiro, para nunca precisar digitar o TOKEN real em lugar
nenhum) e implantei como **Versão 10** via "Gerenciar implantações → Editar
→ Nova versão", preservando o mesmo ID/URL do Web App desde a Versão 9.

**A Versão 10 quebrou na primeira sincronização real** — algo que os fakes
de teste não pegaram: `PropertiesService.getDocumentProperties()` devolve
`null` porque este projeto do Apps Script é solto (não container-bound, de
propósito). A própria correção do item 3 (relatar `abas_escritas_antes_da_falha`)
mostrou que Visão Geral e os 10 comparativos já tinham sido escritos antes da
falha — nada de negócio foi perdido, só a limpeza de órfãs no fim quebrou.
Troquei as duas chamadas para `PropertiesService.getScriptProperties()`,
fortaleci o fake de teste em Node para replicar esse `null` de projeto solto
(pegaria essa classe de bug numa próxima vez) e implantei a **Versão 11**
minutos depois, mesmo dia — mesmo ID/URL preservado de novo.

Duas sincronizações reais contra a Versão 11 devolveram
`Planilha sincronizada: 10 projeto(s), 10 comparativo(s).` nas duas (prova de
idempotência). A planilha real
(`docs.google.com/spreadsheets/d/1WjO_Ax9Tw6zrMFY2MCLTwbwAoK_Um1g93LWy_HMION4`)
foi aberta e conferida: exatamente 11 abas (Visão Geral + 10 comparativos,
sem duplicata nem órfã), e capturas de tela confirmaram formatação, veredito,
cores e link de volta corretos na Visão Geral e numa aba de comparativo.

Suíte Python completa (361 testes — a nota anterior dizia 360, contagem
errada) e `checar-segredos --strict` passaram com o código novo — inclui
testes permanentes em `tests/test_sheets_export.py`
(`AppsScriptDocumentadoTest` para as 3 correções + o uso de
`getScriptProperties`; `SincronizarPlanilhaTest` para o novo campo de
diagnóstico).

### 2ª rodada (Codex sobre o commit `d6246b6`) — 3 lacunas novas

A 1ª rodada só provava as correções com scripts de scratchpad (não
commitados) e com `AppsScriptDocumentadoTest` (asserts de presença de
string) — o Codex apontou corretamente que **nenhum dos dois comprova
comportamento de verdade**, e reproduziu 3 falhas reais rodando o próprio
Code.gs sob Node:

1. **Aba manual podia ser sobrescrita.** `abaLimpa()` decidia propriedade só
   pelo NOME (`getSheetByName`); uma aba criada à mão com o mesmo nome de um
   projeto (ex.: `2026-a`) era encontrada e limpa como se fosse a aba do
   script. **Correção:** propriedade agora é `nome + sheetId` (id interno
   estável do Sheets — sobrevive a renomear, nunca reaproveitado após
   excluir). Uma aba cujo sheetId não bate com o registro é tratada como
   estranha; o projeto correspondente é redirecionado para outra aba (com
   aviso), a manual nunca é tocada. `abaLimpa()` reivindica a aba (grava o
   sheetId) ANTES de limpar, não só no fim — uma retomada após falha não
   trata a própria aba (agora em branco) como estranha. Registro legado
   (`{nome: true}`, até a V11) é migrado uma única vez para
   `{nome: sheetId}`, adotando o sheetId atual de qualquer nome que já
   constava nele.
2. **`estrelas` fora de 0–5 derrubava a sincronização já com abas
   limpas.** `renderizarLinha()` passa o campo `estrelas` (formato legado)
   direto pro construtor `Array()` sem checar tipo/faixa —
   `estrelas: -2` → `Array(-1)` → `RangeError: Invalid array length`, e
   isso rodava DEPOIS de `abaLimpa()` já ter limpado a 2ª aba (a 1ª já
   tinha terminado). **Correção:** `validarPayload()` valida o contrato do
   campo `estrelas` (inteiro de 0 a 5) nos formatos legado E tipado, antes
   de qualquer `abaLimpa`/escrita — o payload inválido agora resulta em
   zero mutações, não em duas abas limpas e uma delas corrompida.
3. **Aba limpa mas não reescrita ficava fora do diagnóstico.**
   `abas_escritas_antes_da_falha` (da V10) só listava abas que tinham
   terminado de verdade; uma aba que `abaLimpa()` já tinha limpado mas cuja
   escrita nova não chegou a terminar não aparecia em lugar nenhum — parecia
   intocada quando estava em branco. **Correção:** a resposta de erro ganhou
   `abas_parcialmente_alteradas`, preenchida a partir de um registro de
   estado (`iniciada`/`concluída`) por aba, marcado ANTES de `abaLimpa`
   rodar. A sincronização nunca prometeu atomicidade por aba; agora o
   diagnóstico diz a verdade sobre isso.

**Os 3 casos foram reproduzidos de verdade contra o código anterior
(`d6246b6`, extraído do próprio doc) e passaram contra o corrigido** —
desta vez com testes PERMANENTES e commitados, exatamente o que a rodada
anterior não tinha:

- `tests/apps_script/fakes.js` — fakes mínimos do runtime do Apps Script
  (SpreadsheetApp/DriveApp/PropertiesService/etc.), reutilizáveis por
  qualquer cenário futuro.
- `tests/apps_script/harness.js` — carrega o Code.gs extraído do doc nesse
  ambiente e expõe `doPost`.
- `tests/apps_script/cenarios/*.js` — um script por cenário (colisão com
  aba manual, falha operacional pós-`clear()`, duas sincronizações
  idempotentes, migração do registro legado) mais um executor genérico de
  payload (`rodar_payload.js`) para os casos de contrato de `estrelas`.
- `tests/test_apps_script_execucao.py` — 7 testes Python que invocam esses
  cenários via `subprocess` e leem o JSON estruturado que cada um imprime;
  pula (não falha) em máquina sem `node` no PATH, com o motivo visível no
  relatório da suíte.

Cobertura confirmada com antes/depois em ambiente isolado: os 3 cenários
falharam do jeito descrito contra `d6246b6` e passaram contra o código
corrigido; payload inválido resulta em zero mutações (`mutacoes: 0`,
planilha nunca chega a ser criada/aberta); colisão com aba manual preserva
conteúdo E identidade (sheetId); falha operacional real (injetada via
monkeypatch em `RealRange.prototype.setValues`, simulando um erro
transiente da API do Sheets — não um payload inválido) identifica a aba
afetada como parcial; duas sincronizações válidas seguidas continuam sem
duplicar aba, inclusive com o registro no formato legado.

Suíte Python completa (371 testes) e `checar-segredos --strict` passaram
com o código corrigido.

**Redeploy real (07/09/2026, conta `conta-comercial@exemplo.com`):** publicado como
**Versão 12**, editando a implantação existente (mesmo ID/URL desde a V9).
Duas sincronizações reais devolveram
`Planilha sincronizada: 10 projeto(s), 10 comparativo(s).` nas duas. O
registro de propriedade migrou em produção do formato legado da V11
(`{nome: true}`) para o novo (`{nome: sheetId}`) sem incidente — não criou
aba duplicada nem tratou os 10 projetos reais como estranhos (o que teria
acontecido sem a migração explícita — exatamente o cenário que
`migracao_registro_legado.js` prova em ambiente isolado). A planilha real
(`docs.google.com/spreadsheets/d/1WjO_Ax9Tw6zrMFY2MCLTwbwAoK_Um1g93LWy_HMION4`)
continua com exatamente 11 abas (Visão Geral + 10 comparativos, sem
duplicata nem órfã) — conferido pela listagem de páginas visíveis e por
captura de tela da Visão Geral. Ver `docs/integracao-google-sheets.md`,
"VERSÃO 12 IMPLANTADA E VERIFICADA", para o relato completo.

**Os 2 syncs reais só provam o caminho feliz (deploy + idempotência) na
planilha de produção — não substituem a cobertura de falha.** Os 3 cenários
de falha (colisão com aba manual, payload inválido, falha operacional
pós-`clear()`) foram provados ANTES do deploy, em ambiente isolado; nunca
foram (nem deveriam ser) reproduzidos contra a planilha real.

### 3ª rodada (Codex sobre o commit `c5018dc`) — 2 ajustes

A 2ª rodada protegeu as abas de COMPARATIVO por propriedade verificada
(nome + sheetId), mas deixou "Visao Geral" de fora de propósito — e o
diagnóstico novo (`abas_parcialmente_alteradas`) nunca chegou a ser lido
pelo cliente Python.

1. **"Visao Geral" não tinha a mesma proteção de propriedade.** `doPost`
   excluía esse nome explicitamente da checagem de abas estranhas
   (`nome !== 'Visao Geral'`), e `abaLimpa()` adotava/limpava qualquer aba
   com esse nome sem checar sheetId. Reproduzido antes da correção: excluir
   a "Visao Geral" gerada, criar uma aba manual com o mesmo nome (sheetId
   diferente) e uma anotação, sincronizar de novo — `ok:true`, mas a
   anotação some. **Correção:** "Visao Geral" passa pelo mesmo mecanismo de
   propriedade verificada dos projetos; se o nome estiver ocupado por uma
   aba estranha, a Visão Geral real é redirecionada para um destino
   alternativo estável entre sincronizações (mesmo mecanismo de sufixo de
   hash determinístico via `nomeAbaProjeto`), preservando a aba manual
   intacta. `migrarRegistroLegado()` ganhou um bootstrap de uma única vez
   (`__visao_migrada__`): sem ele, a primeira sincronização depois deste
   deploy trataria a PRÓPRIA "Visao Geral" real (criada por uma versão
   anterior, nunca registrada por nome até a V12) como estranha — reproduzi
   isso de verdade ao atualizar `migracao_registro_legado.js` e ver o
   teste falhar antes de escrever o bootstrap.
2. **`sincronizar_planilha()` só mostrava metade do diagnóstico de falha
   parcial.** A V12 introduziu `abas_parcialmente_alteradas` na resposta do
   Apps Script, mas o cliente Python só lia `abas_escritas_antes_da_falha`
   — uma falha com as duas listas preenchidas ao mesmo tempo (ex.:
   `abas_escritas_antes_da_falha: ["2026-a"]`,
   `abas_parcialmente_alteradas: ["2026-b"]`) informava só `2026-a` e
   escondia `2026-b`. **Correção:** as duas listas aparecem separadamente
   na mensagem de erro, mantendo compatibilidade com respostas antigas
   (sem o campo novo, nada extra aparece) e a ocultação do token continua
   valendo sobre a mensagem inteira.

Regressões: `tests/apps_script/cenarios/colisao_aba_visao_geral_manual.js`
(nova) + `migracao_registro_legado.js` (atualizado, agora também prova o
bootstrap) em `tests/test_apps_script_execucao.py`; três testes novos em
`tests/test_sheets_export.py::SincronizarPlanilhaTest` (as duas listas
distintas, compatibilidade com resposta antiga, token oculto mesmo com o
campo novo presente) e um em `AppsScriptDocumentadoTest` (contrato de
código: `nomeVisao` usado de fato em todos os pontos, não só declarado).
Suíte Python completa: 376 testes. `checar-segredos --strict` limpo.

`docs/infraestrutura-externa.md` também estava desatualizado — ainda
anunciava a Versão 11 como ativa quando a V12 já tinha sido implantada e
verificada na 2ª rodada. Corrigido no mesmo commit.

**Redeploy real (07/09/2026, conta `conta-comercial@exemplo.com`):** publicado como
**Versão 13**, editando a implantação existente (mesmo ID/URL desde a V9).
O ponto mais delicado era o bootstrap de migração (`__visao_migrada__`):
até a V12, "Visao Geral" nunca tinha sido registrada por nome, então a
primeira sincronização depois deste deploy corria o risco de tratar a
Visão Geral REAL (criada pela V9-V12) como estranha e criar uma
redirecionada, duplicando a aba — funcionou sem incidente em produção.
Duas sincronizações reais devolveram
`Planilha sincronizada: 10 projeto(s), 10 comparativo(s).` nas duas, e a
planilha real
(`docs.google.com/spreadsheets/d/1WjO_Ax9Tw6zrMFY2MCLTwbwAoK_Um1g93LWy_HMION4`)
continua com exatamente 11 abas (Visão Geral + 10 comparativos, sem
duplicata nem órfã, nenhuma "Visao Geral" redirecionada) — conferido pela
listagem de páginas visíveis e por captura de tela. Ver
`docs/integracao-google-sheets.md`, "VERSÃO 13 IMPLANTADA E VERIFICADA",
para o relato completo.

## 4. Proveniência das informações

**Estado: implementada e testada (07/09/2026).**

Cada observação de `cotacoes.csv` carrega, na coluna nova `proveniencia`
(JSON), origem/evidência/data/estado para os 6 campos comerciais (preço,
variação, vendedor, frete, estoque, garantia) — amarrado àquela linha, nunca
ao produto em geral. `fonte` (web/manual) e `confirmacao` (texto livre)
continuam existindo, mas deixaram de ser a única fonte da verdade sobre o
que foi conferido.

**Extensão do CSV, não arquivo auxiliar:** duas colunas novas no fim de
`COTACOES_HEADER` — `estoque` (valor livre: `disponivel`/`indisponivel`/
`sob_encomenda`/vazio; campo novo, não existia antes) e `proveniencia`
(JSON com as 4 chaves por campo: `origem`, `evidencia`, `data`, `estado`).
Reaproveita o mecanismo de migração de schema já existente
(`quotes_header()`/`migrar-cotacoes`) — colunas desconhecidas do arquivo
são preservadas, nada histórico é quebrado; uma linha antiga sem a coluna
lê como "legado sem evidência" nos 6 campos, nunca como fabricação.

**Contrato por campo** (`parse_proveniencia`/`serializar_proveniencia`/
`marcar_proveniencia`, `scripts/central_compras.py`):
```json
{"preco": {"origem": "relatorio_ia", "evidencia": "relatorio-x.md", "data": "2026-09-07T...", "estado": "conferido"}, ...}
```
- `origem`: `observacao_direta` | `relatorio_ia` | `conferencia_humana` |
  `inferencia` (escolhidas pelo usuário) ou `legado_sem_evidencia`
  (nunca escolhida — só atribuída por `parse_proveniencia` quando não há
  nada gravado; JSON ilegível ou com origem desconhecida também cai aqui,
  nunca vira exceção nem evidência inventada).
- `estado`: `conferido` | `nao_conferido`.

**`cotar` (coleta):** flags novas `--estoque`, `--origem-dados` (default
`observacao_direta`), `--evidencia`. Preço/variação/vendedor/frete/garantia
sempre ganham proveniência nesta linha (mesmo usando o default do CLI, que
é um fato observado, não uma lacuna); `estoque` só vira `conferido` se
`--estoque` foi de fato informado — sem ele, fica "sem evidência", nunca
inventado.

**`promover-cotacao` (confirmação):** mesmas 3 flags novas
(`--origem-dados` default `conferencia_humana`). A proveniência começa
**herdando a da cotação base** (`parse_proveniencia(base)`) e só marca como
conferido AGORA os campos que esta chamada de fato recebeu — confirmação
parcial nunca vira "conferido" para o resto. `--sem-alteracao` é a exceção
deliberada: reconfirmação total, os 6 campos viram conferidos.

**Painel (`scripts/painel.py`):** grava pelo MESMO caminho da CLI
(`cc.main(["cotar", ...])`), então usa automaticamente o mesmo contrato —
`CAMPOS_COTACAO` ganhou os 3 campos novos, o formulário "Nova cotação" tem
os inputs correspondentes, e tanto o Ranking quanto "Últimas cotações"
mostram um badge de proveniência (origem abreviada, cor conforme
conferido/não conferido) com tooltip listando os 6 campos — testado de
verdade no navegador com dados sintéticos (projeto/produtos/cotações
fictícios num ambiente isolado, nunca a árvore real do Josemar): badges
corretos no Ranking e em "Últimas cotações", formulário grava e a
proveniência herdada aparece certa na promoção parcial. Um bug real
apareceu nessa verificação — o fallback do em-dash para "Estoque" vazio
estava sendo escapado duas vezes (`&amp;mdash;` literal em vez do
caractere `—`) — corrigido no mesmo commit.

**Snapshot (`decidir`):** nenhuma mudança de código foi necessária —
`metadados.json` já embutia o dict inteiro da cotação vencedora
(`"cotacao": quote`) e `cotacoes.csv` inteiro já era copiado pro snapshot;
como `estoque`/`proveniencia` agora são só mais duas chaves nesse dict, a
imutabilidade que já existia (cópia congelada + hash em `manifesto.json`)
passou a cobrir a proveniência automaticamente. Testado explicitamente:
uma `promover-cotacao` DEPOIS de uma decisão fechada não muda uma vírgula
do `metadados.json` nem do `cotacoes.csv` já congelados no snapshot, e
`auditar-decisoes --strict` continua batendo.

**Testes:** `tests/test_proveniencia.py` (18 testes) cobre os 7 critérios
de aceite pedidos — relatório de IA identificado como tal; confirmação
parcial afeta só os campos conferidos; nova cotação preserva histórico e
origem anterior (append-only, linha antiga bit-a-bit igual); registro
legado nunca ganha comprovação fabricada (JSON ausente/ilegível/origem
desconhecida, todos caem em "legado sem evidência"); CLI e painel usam o
mesmo contrato (mesmo teste roda os dois caminhos e compara); snapshot
conserva valores e proveniência depois de alteração posterior; e duas
observações seguidas nunca compartilham nem misturam proveniência (dicts
independentes, erro de validação não deixa linha parcial). Mutação de
teste aplicada na linha central (`parse_proveniencia(base)` → `{}`):
exatamente 1 dos 18 testes falhou, confirmando que o teste prova o
comportamento e não só existe. Suíte completa: 394 testes,
`checar-segredos --strict` limpo.

**Fora do escopo desta frente, deliberadamente:** o dashboard estático
(`generate_project_page`/`spec_comparison_section`/`comercial_valor`) não
foi tocado — essa função também alimenta `sheets_export_payload` (frente
3, endurecida em 3 rodadas nesta mesma sessão), e o pedido explícito listava
CLI/promoção/painel/leitura de dados/snapshot, não o dashboard. Pesos,
gates e limites de score do ranking também não foram tocados, como pedido.

## 5. Produtos reutilizados em projetos diferentes

**Estado: implementada (sessão 13), corrigida em quatro rodadas de revisão
independente da Astra (sessões 14, 15, 16 e 17 — 6 + 3 + 3 + 4 achados).
Ainda falta UMA rodada de revisão que passe limpa antes de declarar
"concluída sob reserva" — já foi dada como pronta QUATRO vezes e as quatro
vezes apareceu lacuna nova; não presuma que a 5ª rodada não vai achar mais
nada. Padrão que se repete: cada rodada acha problema mais profundo no
MESMO conjunto de mecanismos — as 3 primeiras em `link_product`/
`migrate_products` + `tracked_operation`, a 4ª no contrato de participação
(`_participacao_invalida`/`read_participation`) e nos consumidores que
ainda liam `estado` bruto do YAML em vez de passar por ele
(`project_candidate_ids`/`project_discarded_candidate_ids`) — a próxima
revisão (ou correção) deveria ler o contrato inteiro dessas áreas, não só
o diff da última rodada.**

**Contrato:** `produto.yaml` (ficha) passou a guardar só identidade e dado
técnico — `id`, `categoria`, `nome`, `marca`, `atributos`,
`atributos_classificacao`, `proveniencia`. Estado de pesquisa, descarte
(com motivo), preço-alvo/teto, aguardando-preço (motivo+data) e
`requisitos_atendidos` viraram **participação**: um arquivo por produto
dentro de CADA projeto, `projetos/<projeto>/participacoes/<produto_id>.yaml`
— nunca mais um campo `projeto` único na ficha. O mesmo produto_id pode ter
uma participação em cada projeto, com estado, motivo e requisitos
totalmente independentes.

Ponto único de leitura (o "cache" citado no pedido original):
`find_product(produto_id, project=None)`, em `scripts/central_compras.py`.
Sem `project`, devolve só a ficha (identidade) — usado onde só nome/marca
importam. Com `project`, mescla ficha + participação DAQUELE projeto
(`read_participation`) e é a única função que faz essa junção; todo
consumidor que precisa saber "descartado ou não", "aguardando preço",
`preco_alvo/teto` ou `requisitos_atendidos` passa a chamar com `project` —
`compute_ranking`, `sem_cotacao_candidates`, `decide()` (via
`ranqueado.product`, já mesclado), `waiting_price_rows()`. Isso é o que
alimenta ranking, gate, regra de parada, painel, dashboard e o payload do
Sheets a partir do MESMO cálculo (`compute_ranking`/`spec_comparison_rows`,
já reaproveitados desde a frente 3/4) — nenhum consumidor lê a ficha crua
para decidir estado.

**CLI:**
- `vincular-produto --produto-id X --projeto Y [--preco-alvo] [--preco-teto]
  [--requisito chave=valor]`: caminho explícito para reaproveitar uma ficha
  já existente em outro projeto, sem recriar nada (`pesquisa.md` e
  `atributos` preservados). Recusa se a ficha não existe (orienta
  `novo-produto`), ou se já existe participação para aquele par
  produto/projeto (novo formato OU legado) — nunca sobrescreve.
- `novo-produto` sobre um `produto_id` que já tem ficha (sem `--force`)
  agora recusa apontando para `vincular-produto` no lugar — `--force`
  continua existindo, mas só para recriar a MESMA ficha do zero, nunca como
  atalho de reaproveitamento (pedido explícito).
- `descartar`/`aguardar-preco`: `--projeto` continua opcional, mas a
  resolução implícita mudou de "o único campo `projeto` da ficha" para "o
  único projeto onde este produto participa" (`resolve_participation_project`).
  Produto participando de 2+ projetos sem `--projeto` é RECUSADO antes de
  qualquer escrita, listando os projetos e pedindo para escolher — critério
  de aceite 5, testado via CLI real no sandbox (`descartar --produto-id
  fone-comum --porque ...` sem `--projeto`, com o produto vinculado a 2
  projetos, devolveu erro e `git status`/participação de nenhum dos dois
  mudou 1 byte).
- `migrar-produtos [--projeto X] [--aplicar]`: migração em lote do formato
  legado. Sem `--aplicar`, só mostra a prévia (nenhuma escrita). Migra
  **só o caso inequívoco**: ficha com `projeto` gravado, esse projeto existe,
  e nenhuma cotação do mesmo produto_id aparece em outro projeto diferente —
  qualquer outra combinação (campo legado sem `projeto`, projeto referenciado
  que não existe mais, ou cotação em projeto diferente do `projeto` da
  ficha — "uso cruzado") é RELATADA, nunca decidida sozinha. Participação já
  existente para aquele par (ex.: `descartar` já rodou sobre o registro
  legado antes da migração em lote) nunca é sobrescrita pelo dado mais velho
  da ficha — só a ficha é limpa nesse caso. Idempotente por construção: cada
  ficha é reavaliada do zero a cada chamada (sem depender de progresso
  gravado), então não precisa de journal próprio — a trava de
  projeto/`produtos/` já herdada de `main()` basta.

**Migração e compatibilidade:** `read_participation` cai para os campos
legados da ficha quando não há participação no formato novo E a ficha
ainda aponta (`projeto`) para o projeto pedido — nunca para outro. Isso
significa que um registro nunca migrado continua funcionando sem rodar
`migrar-produtos` (a leitura já é compatível); a migração em lote só limpa
a ficha e formaliza o arquivo de participação. `descartar`/`aguardar-preco`
já escrevem sempre no formato novo, mesmo sobre um registro ainda legado —
por isso a ordem de precedência importa e foi testada explicitamente
(`test_participacao_mais_fresca_nunca_e_sobrescrita_pela_ficha_legada`).

**Recuperação de operações (frente 2):** `descartar`/`aguardar-preco`/
`vincular-produto` passaram a declarar o arquivo de participação como
recurso direto (`_recursos_diretos_participacao`, ao lado de `processo.md`),
pelo mesmo mecanismo central (`_bloquear_se_recursos_conflitantes`) que já
protege `decisao.md`/veredito — testado plantando um journal `em_andamento`
que reivindica a participação e confirmando que `descartar` é recusado
(zero escrita) até a pendência ser resolvida. Nenhum comando hoje cria esse
tipo de pendência sobre participação (nem `decidir` a reivindica — risco já
aceito e documentado na seção 2, subseção "risco residual"), então esta é
proteção estrutural para o futuro, não uma lacuna fechada retroativamente.

**Testes:** `tests/test_participacoes.py`, 18 testes cobrindo os 9 critérios
de aceite pedidos: isolamento nos dois sentidos (com e sem cotação, cenário
âncora com `compute_ranking` cortando só no projeto certo), `vincular-produto`
seguro e idempotente, ambiguidade recusada sem escrita, migração (prévia,
aplicação, idempotência, participação mais fresca preservada, uso cruzado
relatado), e proteção de operação pendente. Mutação de teste aplicada no
coração do merge (`find_product` devolvendo só a ficha, ignorando
participação): 2 dos 18 falharam — o teste do cenário âncora com cotação
(`test_descartado_com_cotacao_e_cortado_pelo_gate_so_no_proprio_projeto`) e o
de migração que compara leitura antes/depois — confirmando que os testes
detectam a classe de bug que a frente existe para prevenir, não só os
exemplos escritos. Dois testes existentes precisaram de ajuste, não por bug
deles: `test_waiting_price_and_verdict_learning_flow` verificava
`estado: aguardando_preco` dentro do `produto.yaml` (campo que mudou de
arquivo); o fuzzer `test_invariants_hold_on_pathological_data` gravava ficha
legada sem o campo `projeto`, o que — sem o ajuste — faria a fuzzagem de
estado/descarte/requisitos parar de alcançar o motor silenciosamente (sem
falhar, só sem testar o que dizia testar).

**Validado end-to-end no sandbox isolado** (cópia de
`config`/`templates`/`scripts`, nunca a árvore real): mesmo produto_id
vinculado a dois projetos com cotações e requisitos diferentes, descartado
só num deles — `ranking.md` de cada projeto confirmado com o corte certo
em cada lugar; `decidir` fechado no projeto elegível, `auditar-decisoes
--strict` e `operacoes-pendentes --strict` passando; alteração de
participação em OUTRO projeto depois da decisão não mudou 1 byte do
`ranking.md` congelado no snapshot (hash SHA-256 idêntico antes/depois) —
critério de aceite 9. Painel aberto nos dois projetos ao mesmo tempo
(portas diferentes), com screenshot confirmando "elegível" num e
"aguardando preço" no outro para o MESMO produto, ao mesmo tempo real.

Suíte completa: 415 testes (414 passando + 1 falha pré-existente e
não-relacionada, ver nota abaixo), `checar-segredos --strict` e
`git diff --check` limpos.

**Nota sobre a suíte, não é desta frente:** o baseline limpo (antes de
qualquer mudança desta sessão, commit `6b48a51`) já reprovava em
`test_decision_engine.py::RankingGateAwareQuoteSelectionTest::
test_same_day_quote_without_accepted_warranty_does_not_hide_valid_quote`.
Causa raiz diagnosticada: o teste fixa `data="2026-08-31"` como cotação
"do mesmo dia" e depende de `quote_is_stale` ser `False` (janela de 7 dias
para `fonte=manual`) para exercitar o desempate por gate em `latest_quotes`;
com o calendário real já em 2026-09-08 (8 dias depois), as duas cotações do
teste ficam "vencidas" e caem no fallback "tudo vencido" de `latest_quotes`
(pega a última gravada, sem olhar gate) — apodrecimento de data-fixa no
fixture, não um bug de participação/produto. Fora do escopo desta frente;
registrado aqui para não ser confundido com regressão.

**Fora do escopo, deliberadamente:** frente 6 (datas/veredito) não foi
tocada. Pesos, gates e comparabilidade do score não foram alterados. Não foi
criada infraestrutura externa nem tocado o Apps Script/Sheets — o payload do
Sheets passou a refletir participação por projeto de graça, só por
reaproveitar `spec_comparison_rows`/`compute_ranking` (já `find_product`
consciente de projeto), sem nenhuma mudança no `Code.gs` nem novo deploy.

### 1ª revisão independente (Astra, sessão 14, sobre o commit `e29c45c`) — 6 falhas

Contexto/inventário/correção detalhada dos 6 achados (vazamento de contexto
de IA entre projetos, mesmo vazamento na validação, snapshot sem congelar
participação, `vincular-produto` sem recuperação, `migrar-produtos` sem
checar recurso pendente, ficha órfã com `--requisito` inválido) ficaram
registrados só em `STATUS.md` (sessão 14) quando foram corrigidos — não
duplico aqui, ver lá. Testes: `tests/test_participacoes.py`,
`RevisaoIndependenteFrente5Test` (13 testes). Suíte depois da correção: 428
testes, 0 falhas.

### 2ª revisão independente (Astra, sessão 15, sobre o commit `fcdb6f9`) — 3 falhas

A correção da 1ª revisão tinha mais 3 lacunas, todas no mesmo par de
mecanismos (`link_product`/`migrate_products` + `tracked_operation`):

1. **`migrar-produtos` perdia o descarte com participação existente mas
   vazia/inválida.** A checagem de "já tinha participação" era só
   `Path.exists()` — um arquivo de 0 bytes contava como "válido" e a
   migração limpava a ficha legada (única fonte real do descarte) por cima
   dele, sem nenhum dado sobrevivendo em nenhum dos dois lugares. Corrigido:
   a checagem agora lê o conteúdo (`read_yaml`) e só considera "participação
   válida" um mapa YAML não vazio; vazio/inválido é tratado como "sem
   participação recuperável" — a migração recupera do legado pra dentro
   dele, mesmo caminho já usado quando o arquivo simplesmente não existia.
2. **`vincular-produto` podia concluir sem marcar a etapa 3 do processo, sem
   deixar pendência visível.** `mark_steps(project, [3])` rodava DEPOIS do
   `with tracked_operation(...)` — fora da recuperação. Uma interrupção ali
   (dado já gravado, journal já apagado porque o `with` tinha terminado sem
   exceção) deixava o checkbox preso, sem nenhuma pendência para
   `operacoes-pendentes` mostrar, e a retomada normal era recusada por "já
   tem participação". Corrigido: `mark_steps` passou para dentro do `with`,
   como última linha — uma falha ali agora mantém o journal `em_andamento`
   (visível, retomável).
3. **A linha da timeline podia duplicar numa retomada em outro dia.** A
   assinatura do efeito (usada por `registrar_efeito` para reconhecer "isso
   já foi escrito") era montada com a data do início da tentativa, mas
   `append_timeline` recalculava `today()` de novo na hora de escrever de
   verdade — numa retomada em outro dia, a linha gravada saía com data NOVA,
   nunca batendo com a assinatura congelada (data velha), e cada retomada
   escrevia outra linha. Corrigido: `append_timeline` ganhou parâmetro
   `data` opcional; `link_product` congela `data_evento` em `op.detalhe`
   (mesmo princípio do `snapshot_rel` de `decidir` — nunca recalculado numa
   retomada) e passa essa mesma data para `append_timeline`.

### Testes (2ª revisão)

`tests/test_participacoes.py`, `SegundaRevisaoIndependenteFrente5Test`: 3
testes-armadilha (uma reprodução real de cada achado contra o código antigo,
confirmada ANTES da correção) + 3 controles que a Astra confirmou que já
passavam (retomada com argumento diferente recusa, migração retomada entre
duas escritas preserva estado, snapshot imutável após descarte no mesmo
projeto) — protegidos contra regressão futura também. Mutação de teste
aplicada em cada uma das 3 correções (desfeita uma de cada vez): só o
teste-armadilha daquele achado falhou, os outros 36 testes do arquivo
(inclusive os 3 controles) continuaram passando. Suíte completa depois da
correção: **434 testes, 0 falhas** (428 + 6 novos).
`auditar-decisoes --strict`, `operacoes-pendentes --strict`,
`checar-segredos --strict` e `git diff --check` limpos contra a árvore real.

### 3ª revisão independente (Astra, sessão 16, sobre o commit `6669b9d`) — 3 falhas

A correção da 2ª revisão tinha mais 3 lacunas, cada uma um nível mais
profundo no mesmo par de mecanismos:

1. **Contrato de participação insuficiente na migração.**
   `isinstance(dados, dict) and bool(dados)` só provava que o arquivo tinha
   ALGUM conteúdo, nunca que esse conteúdo era uma participação de
   verdade — um mapa só com `produto_id`, só com uma anotação solta, com
   `produto_id` de OUTRO produto, ou com `estado` fora do vocabulário
   conhecido, todos "passavam" e autorizavam `migrar-produtos` a apagar o
   campo legado da ficha (única evidência real) por cima de lixo.
   Corrigido: função nova `_participacao_invalida(dados, produto_id)`
   define o contrato mínimo — IDENTIDADE (`produto_id` bate com o próprio
   arquivo) e ESTADO (dentro de `ESTADOS_PARTICIPACAO`, vocabulário fechado
   novo: `pesquisando`/`aguardando_preco`/`descartado`); os demais campos
   continuam opcionais. Usado nos dois lugares que precisam do mesmo
   critério: `read_participation` (participação inválida deixa de ser
   autoridade, cai pro legado/default, nunca fabrica estado confirmado) e
   `migrate_products` (participação que não passa no contrato vira
   categoria nova `INVALIDO(S)`, que recusa a migração daquele candidato —
   ficha E participação preservadas, `--aplicar` termina em `SystemExit`
   como já acontecia para `BLOQUEADO(S)`). O caso "vazio" (0 bytes) da
   correção anterior continua recuperando do legado normalmente — só o caso
   "tem conteúdo mas não faz sentido" passou a recusar em vez de aceitar.
2. **`nome_produto` não estava congelado, só a data.** A correção anterior
   congelou `data_evento` mas `nome_produto` continuava sendo relido da
   FICHA compartilhada a cada tentativa — um `novo-produto --force` rodado
   em OUTRO projeto entre a falha e a retomada muda o nome ali, e a
   retomada escrevia a linha da timeline com o nome NOVO, nunca reconhecida
   como o mesmo efeito da assinatura congelada (nome antigo) — duplicava a
   cada retomada. Corrigido: `nome_produto` entrou em `op.detalhe` junto da
   data.
3. **Journal de versão anterior quebrava a retomada com `KeyError`.**
   `link_product` passou a exigir `op.detalhe["data_evento"]` e depois
   também `["nome_produto"]`, mas um journal `em_andamento` começado por
   uma versão ANTERIOR do comando (antes desses campos existirem) não tem
   essas chaves — a retomada quebrava com traceback cru de `KeyError` em
   vez de reconciliar. Corrigido com um método novo em `OperationHandle`:
   `efeito_congelado(passo)`, que devolve a `assinatura_efeito` já
   persistida por `registrar_efeito` para aquele passo (de QUALQUER versão
   do código que a começou), se alguma tentativa já chegou a registrá-la —
   reaproveita esse texto exato em vez de reconstruir. Só cai pro dado
   atual de `op.detalhe` (com `.get(...)` e fallback, nunca indexação
   direta) quando o passo nunca foi tentado por ninguém — nesse caso não há
   efeito parcial nenhum que dependa de bater com texto antigo, então é
   seguro. `append_timeline` ganhou parâmetro `linha` (texto inteiro já
   pronto) para escrever exatamente o que foi reaproveitado, sem
   reconstruir. Testado com o CÓDIGO REAL do commit `fcdb6f9` via
   `git show` + subprocesso, criando uma pendência de verdade com aquele
   código antigo antes de trocar pro código atual e confirmar retomada
   limpa, sem duplicação.

### Testes (3ª revisão)

`tests/test_participacoes.py`, `TerceiraRevisaoIndependenteFrente5Test`: os
3 testes-armadilha da Astra (reprodução real de cada achado contra o código
antigo, confirmada ANTES da correção) + 1 teste adicional
(`test_nome_congelado_mesmo_quando_timeline_nunca_foi_tentada`) para uma
janela que o teste da Astra não forçava — interrupção ENTRE concluir a
participação e sequer tentar a timeline pela primeira vez (via
`CENTRAL_COMPRAS_TESTE_CRASH_APOS=participacao`, hook de teste real do
próprio motor), onde o mecanismo do achado 3 ainda não tem nada persistido
para reaproveitar. A mutação de teste do achado 2 revelou esse ponto cego:
desfazer a correção de `nome_produto` não quebrou o teste copiado da Astra
(porque o mecanismo do achado 3 já cobria aquele cenário específico
"por baixo"), só o teste adicional detectou. Mutação aplicada nas 3
correções, uma de cada vez: só o(s) teste(s)-armadilha daquele achado
falharam. Suíte completa depois da correção: **438 testes, 0 falhas**
(434 + 4 novos). `auditar-decisoes --strict`, `operacoes-pendentes
--strict`, `checar-segredos --strict` e `git diff --check` limpos contra a
árvore real.

**Fora do escopo desta correção, deliberadamente:** o contrato novo de
participação (`_participacao_invalida`) não foi estendido para
`project_candidate_ids`/`project_discarded_candidate_ids` (leem `estado`
direto do YAML sem passar por `read_participation`) — a Astra não apontou
esses dois como achado, e mexer neles agora seria escopo além do pedido.
**Essa omissão foi exatamente o gancho da 4ª revisão, abaixo.**

### 4ª revisão independente (Astra, sessão 17, sobre o commit `f2d5cd1`) — 4 falhas

A correção da 3ª revisão criou o contrato mínimo
(`_participacao_invalida`), mas só o usava em `read_participation` e
`migrate_products` — os dois consumidores deixados de fora de propósito na
3ª revisão (nota acima) continuavam lendo `estado` bruto do YAML, e o
próprio contrato ainda tinha dois buracos:

1. **Identidade divergente reabilitava candidato descartado.** Alterar só
   `produto_id` num arquivo de participação já `descartado` fazia
   `read_participation` cair pro legado (ou pro default `pesquisando`) —
   `compute_ranking` voltava a considerar o candidato ELEGÍVEL, enquanto
   `project_discarded_candidate_ids` (lendo o YAML bruto, sem passar pelo
   contrato) continuava contando o MESMO candidato como descartado.
   Simultaneidade real: `elegiveis=['candidato']` e
   `descartados=['candidato']` ao mesmo tempo, `validation_report` mudo.
   Corrigido com um estado sintético novo, `ESTADO_PARTICIPACAO_INVALIDA`
   ("invalido") — fora de `ESTADOS_PARTICIPACAO`, nunca gravável por
   nenhum comando —, devolvido por `read_participation` quando o conteúdo
   é incoerente. Nunca cai pro legado (resolve também o caso "reverte pra
   estado legado mais antigo", variante do mesmo achado). `_classificar_
   participacao` virou o ponto único que decide "vazio" (ausente/0 bytes/
   mapa vazio — recupera do legado, como antes) vs. "inválida" (tem
   conteúdo mas não presta — nunca recupera, nunca é autoridade) vs.
   "válida"; usado por `read_participation` E `migrate_products`.
   `project_candidate_ids`/`project_discarded_candidate_ids` passaram a ler
   pelo MESMO `read_participation` (nunca mais `estado` bruto) e excluem o
   estado `invalido` dos dois conjuntos — nem "ativo" nem "descartado"
   confirmado, fica de fora dos dois até reconciliar. `gate_eliminations`
   corta o candidato (nunca elegível) com mensagem de reconciliação
   distinta da de descarte confirmado; `validation_report` aponta ERRO
   (não aviso) mesmo quando o candidato não tem cotação ainda (loop
   adicional sobre os arquivos de participação, não só sobre `latest`).
2. **Campo opcional aceitava qualquer tipo.** `_participacao_invalida` só
   validava identidade e estado — `requisitos_atendidos: ["uso"]` (lista,
   quebraria `.items()` em `gate_eliminations` com `AttributeError`),
   `preco_teto: "barato"` e `preco_alvo: NaN` (viraria limite ausente em
   silêncio via `quote_float`) passavam no contrato e autorizavam
   `migrar-produtos` a apagar o legado por cima. Corrigido:
   `_tipo_invalido_participacao` valida tipo dos campos opcionais
   CONHECIDOS quando presentes (`requisitos_atendidos` precisa ser mapa;
   `preco_alvo`/`preco_teto` precisam ser número finito; os três campos de
   texto precisam ser string) — ausência continua válida, campo
   desconhecido (schema futuro) nunca invalida.
3. **Conteúdo não-mapa era tratado como arquivo vazio na migração.**
   `participacao_vazia = not (isinstance(dados, dict) and bool(dados))`
   classificava QUALQUER conteúdo não-dicionário — inclusive uma LISTA
   YAML não vazia com `estado`/`descartado_porque` reais — como "arquivo
   sem dado", autorizando a migração a sobrescrever com o legado por cima
   de evidência de verdade. Corrigido dentro de `_classificar_
   participacao` (mesma função do achado 1): só `None` (0 bytes/`null`) ou
   mapa vazio `{}` contam como "vazio"; qualquer outro conteúdo não-mapa
   vira "inválido" (recusa, preserva os dois arquivos).

**Achado colateral, corrigido junto:** o dict sintético devolvido por
`read_participation` para o estado `invalido` carrega `_motivo_invalido`
(diagnóstico interno) — sem cuidado, esse campo vazaria pro YAML gravado em
disco na próxima escrita (`descartar`/`aguardar-preco` sobre um arquivo já
inválido, que é o caminho normal de reconciliação) ou pro snapshot congelado
de uma decisão. `_participacao_serializavel` remove campos com prefixo `_`
antes de qualquer escrita (`write_participation` e o snapshot de
participações em `_decide_writes`).

### Testes (4ª revisão)

`tests/test_participacoes.py`, `QuartaRevisaoIndependenteFrente5Test`: os 4
testes-armadilha da Astra (reprodução real de cada achado contra o commit
`f2d5cd1`, confirmada ANTES da correção — scripts
`astra_review_f2d5cd1.py`/`astra_review_f2d5cd1_details.py`) + 3 testes de
controle/efeito colateral (`test_arquivo_realmente_vazio_continua_
recuperando_do_legado` — a recuperação de 0 bytes da 2ª revisão não
regrediu; `test_requisitos_lista_nao_derruba_gate_eliminations` — o
`AttributeError` real que o achado 2 evitava; `test_motivo_invalido_nunca_
vaza_para_disco`). Mutação aplicada nas 3 correções de fundo, uma de cada
vez (desfeita e restaurada em seguida): achado 1 desfeito derrubou
exatamente os 2 testes de identidade + o teste de `.items()` + o teste do
vazamento (4 falhas, nenhuma outra); achado 2 desfeito derrubou as 3
subTests do teste de tipo + o teste de `.items()` com `AttributeError` real
(3 falhas + 1 erro, nenhum outro); achado 3 desfeito derrubou só o teste da
lista (1 falha, nenhum outro). Suíte completa depois da correção: **445
testes, 0 falhas** (438 + 7 novos). `auditar-decisoes --strict`,
`operacoes-pendentes --strict`, `checar-segredos --strict` e
`git diff --check` limpos contra a árvore real (`migrar-produtos` sem
`--aplicar` também rodado contra a árvore real como conferência adicional —
preview idêntico ao anterior, 0 inválido).

**Fora do escopo desta correção, deliberadamente:** frente 6 não iniciada
(pedido explícito do Josemar); pesos/gates/calibragem do score intocados;
nenhuma infraestrutura externa tocada; `migrar-produtos --aplicar` não foi
rodado contra a árvore real (seria aplicar uma migração de 46 produtos sem
pedido explícito para isso — só o preview, read-only, foi conferido).

## 6. Datas e vereditos

**Estado: não iniciada.**

Pendente: diferenciar data da decisão, da compra/pagamento, da entrega e do
início de uso; definir e documentar qual evento dispara D+30/D+180. Não
presumir compra realizada só por haver decisão ou cotação manual.

## 7. Validação e publicação

**Estado (08/09/2026, sessão 13, reconciliado): feita integralmente para as
frentes 2, 3, 4 e 5. Frente 6 não iniciada, sem checklist ainda.**

Esta seção estava desatualizada desde a sessão 9-12: as frentes 3 (receptor
Sheets, 3 rodadas de revisão + redeploy verificado na nuvem) e 4
(proveniência, 18 testes + verificação no painel) já tinham completado o
checklist inteiro nas próprias seções acima, mas nunca foi marcado aqui.
Corrigido agora, sem reescrever o histórico de cada seção — só a marca
desta.

Checklist por frente, quando implementada: problema reproduzido → correção →
teste direcionado → doc/STATUS.md atualizados → commit coerente → (no fim de
todas as frentes de uma sessão) suíte completa, scanner de segredos, diff
revisado, fluxos testados no navegador quando aplicável, push para
`origin/main`.

- **Frente 2** (recuperação de operações): feito, 7 rodadas de revisão, ver
  seção 2.
- **Frente 3** (receptor Sheets): feito, Versão 13 implantada e verificada
  na planilha real, ver seção 3.
- **Frente 4** (proveniência): feito, 18 testes, verificado no painel com
  dados sintéticos, ver seção 4.
- **Frente 5** (produtos reutilizados): implementada (sessão 13); quatro
  rodadas de revisão independente da Astra acharam 6, depois 3, depois mais
  3 e depois mais 4 lacunas reais, as quatro corrigidas com teste
  permanente + mutação (sessões 14, 15, 16 e 17) — suíte completa,
  `checar-segredos --strict`, `operacoes-pendentes --strict`,
  `auditar-decisoes --strict` e `git diff --check` limpos nas quatro
  rodadas, ver seção 5. **Ainda falta uma rodada de revisão independente
  que passe limpa** — já foi dada como pronta QUATRO vezes e as quatro
  vezes apareceu lacuna nova; não presumir "concluída sob reserva" até
  isso acontecer de verdade.
- **Frente 6** (datas/veredito): não iniciada.
