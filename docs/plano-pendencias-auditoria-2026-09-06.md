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

**Estado: concluída sob reserva** (5ª revisão corrigida na sessão de
07/09/2026 — commit a publicar). Ficou **em andamento** entre cada entrega
e a revisão seguinte que achou lacuna nova — já aconteceu 4 vezes seguidas
(após `83c0901`, `2a682a7`, `833c4b9`, `df08fb5`). **Não declare concluída
de novo só porque os exemplos testados passaram** — confirme contra o
inventário da subseção 5ª abaixo, e verifique se algum comando novo foi
adicionado ao CLI desde então sem entrar nesse inventário.

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

| Comando | Arquivos afetados | Trava adquirida | Verificação de conflito |
|---|---|---|---|
| `decidir` | `decisao.md`, `processo.md` (projeto); snapshot próprio (não compartilhado) | projeto | `tracked_operation` (recursos declarados) |
| `aprender-veredito` | `licoes.md`, `marcas/<slug>.md`, `lojas/<slug>.md` (se aplicável), o **arquivo de veredito** | `base-conhecimento/` | `tracked_operation` (recursos declarados) |
| `anotar` | `processo.md` (projeto) | projeto | **novo**: central (`RECURSOS_DIRETOS_POR_COMANDO`) |
| `preencher-veredito` | arquivo de veredito (path direto do argumento) | `base-conhecimento/` (histórico; não é o escopo natural, mantido como estava) | **novo**: central |
| `novo-veredito` (com `--force`) | arquivo de veredito (`VEREDITOS/<data>-<projeto>.md`) | projeto | **novo**: central |
| `registrar-licao` | `licoes.md` | `base-conhecimento/` | central (antes era chamada inline dentro da função; movida para a tabela central) |
| `registrar-marca` | `marcas/<slug>.md` | `base-conhecimento/` | central (idem) |
| `registrar-loja` | `lojas/<slug>.md` | `base-conhecimento/` | central (idem) |
| `novo-projeto` | briefing/processo/ranking/decisão/cotações **do projeto que está sendo criado** | `projetos/` (raiz) | não se aplica — projeto não existe antes desta chamada, não há como haver pendência prévia |
| `novo-produto` | `produtos/<categoria>/<id>/produto.yaml` | `produtos/` | não bloqueado — ficha de produto não é recurso reivindicado por nenhuma operação; ver limitação abaixo |
| `cotar` | `cotacoes.csv` (append-only) | projeto | não bloqueado — `cotacoes.csv` é append-only e `decidir` já recusa retomada se o hash da cotação mudar (`assinatura`); risco residual só durante uma captura ainda não concluída, ver limitação abaixo |
| `promover-cotacao` | `cotacoes.csv` | projeto | idem `cotar` |
| `ranking` | `ranking.md`, `ranking.csv` (projeto) | projeto | não bloqueado — recomputados deterministicamente a partir de `cotacoes.csv`+produtos; seguro de rodar a qualquer momento, inclusive dentro da própria captura de `decidir` |
| `descartar` | `produto.yaml` | produto (`produtos/`) | não bloqueado — mesmo raciocínio de `novo-produto` |
| `aguardar-preco` | `produto.yaml` | produto (`produtos/`) | idem |
| `regenerar` | `ranking.md/csv`, `validacao.md`, histórico, dashboard (não toca `decisao.md`/`processo.md`/snapshots) | todos os projetos (ou um) + `base-conhecimento/` + dashboard | não bloqueado — não escreve nenhum arquivo reivindicável; testado que preserva ranking congelado (`decisao-*-ranking.md`) |
| `categorias.yaml` (gate) | escrito só via `apply_lesson_gate`, sempre junto de uma gravação em `licoes.md` na mesma chamada | — | coberto **transitivamente**: todo caminho que grava `categorias.yaml` também grava `licoes.md` na mesma operação, que já é protegida |
| `briefing.md` | escrito só por `set_project_state`, chamado apenas de dentro de `decidir` | — | não há comando standalone que escreva briefing.md; não se aplica |

Ponto único de checagem: `_bloquear_se_recursos_conflitantes()`, chamada (a)
dentro de `tracked_operation`, para operações com journal próprio
(`decidir`, `aprender-veredito`), e (b) uma vez em `main()`, para os
escritores diretos da tabela `RECURSOS_DIRETOS_POR_COMANDO`, logo após as
travas serem adquiridas e antes de `args.func(args)` — nenhuma checagem
solta dentro de função individual.

**Journal ilegível agora bloqueia o ESCOPO inteiro (BASE ou o projeto onde
está o journal corrompido)**, não silenciosamente nada: qualquer novo
recurso naquele escopo é recusado até o journal ser lido com confiança ou
apagado manualmente após conferência.

### Testes

`tests/test_operation_recovery.py`: 22 → **26 testes**. Os 4 novos: `anotar`
bloqueado enquanto `decidir` pendente (com o ciclo completo bloqueio →
recuperação → escrita permitida); journal corrompido bloqueando
`registrar-licao` no mesmo escopo, sem apagar o journal sozinho;
`preencher-veredito` e `novo-veredito --force` bloqueados enquanto
`aprender-veredito` está pendente no mesmo arquivo de veredito.

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
- **Risco residual, aceito e documentado (não bloqueado):** `cotar`,
  `promover-cotacao`, `novo-produto`, `descartar` e `aguardar-preco` não são
  bloqueados por uma captura de `decidir` ainda pendente (não concluída).
  Se o operador editar cotações/produtos nessa janela estreita entre a
  falha e o retry, a captura retomada (que ainda não rodou
  `executar_uma_vez`) vai ler o estado ATUAL, não o do momento da falha —
  aceitável porque, até a captura concluir, a decisão ainda não foi tomada
  de verdade, e o operador está livre para atualizar os dados de pesquisa.
  Uma vez que a captura conclui, ela nunca mais é tocada
  (`executar_uma_vez`), então esse risco só existe nessa janela inicial.
  Se uma sessão futura quiser fechar essa janela também, o padrão a seguir
  é o mesmo: declarar os arquivos como `recursos` do `decidir` pendente.
- Todo comando novo que passar a escrever `processo.md`, `decisao.md`,
  `licoes.md`, `marcas/*.md`, `lojas/*.md` ou um arquivo de veredito por
  fora de `decidir`/`aprender-veredito` precisa ser adicionado à tabela
  `RECURSOS_DIRETOS_POR_COMANDO` — não há checagem automática de que isso
  foi feito. É uma responsabilidade de revisão de código, registrada aqui
  para não se perder.
- Não cobre a exportação para o Google Sheets (frente 3) nem qualquer outra
  sequência multi-arquivo fora de `decidir`/`aprender-veredito`. Se uma
  sessão futura achar outro ponto candidato, reaproveite
  `registrar_efeito`/`executar_uma_vez`/`recursos`, não reinvente.

## 3. Receptor do Google Sheets

**Estado: não iniciada.**

Pendente: validação de payload completo antes de limpar/escrever abas
(inclusive `null`), proteção contra remoção de aba manual/estranha ao
gerador, comunicação de falha parcial, resposta que permita ao cliente
conferir o que foi gravado de verdade. Depois: redeploy pela conta
`conta-comercial@exemplo.com` preservando URL/permissões, duas sincronizações,
conferência de idempotência e aparência na planilha real, atualização de
`docs/infraestrutura-externa.md` no mesmo commit.

Depende de sessão com acesso ao navegador autenticado como `conta-comercial`
(`mcp__nav-conta-comercial__*` ou perfil Chrome equivalente) para o redeploy e a
conferência visual — a parte de código (Apps Script documentado +
`sheets_export_payload`) pode ser feita sem isso, mas não a implantação.

## 4. Proveniência das informações

**Estado: não iniciada.**

Pendente: schema de origem/conferência por campo comercial (preço, variação,
vendedor, frete, estoque, garantia), distinguindo relatório de IA externa,
observação direta, conferência humana, inferência e legado sem evidência.
Extensão do CSV ou arquivo auxiliar (não quebrar `cotacoes.csv` histórico),
mudanças em CLI/promoção/painel/snapshot/documentação.

## 5. Produtos reutilizados em projetos diferentes

**Estado: não iniciada.**

Pendente: separar dado próprio do produto (ficha) do dado de participação
numa compra específica (estado de pesquisa, descarte, motivo, preço-alvo).
Migração explícita e verificável, compatível com registros antigos. Teste
âncora: mesmo produto em dois projetos com estados diferentes não pode
vazar de um para o outro.

## 6. Datas e vereditos

**Estado: não iniciada.**

Pendente: diferenciar data da decisão, da compra/pagamento, da entrega e do
início de uso; definir e documentar qual evento dispara D+30/D+180. Não
presumir compra realizada só por haver decisão ou cotação manual.

## 7. Validação e publicação

**Estado: parcial — feita integralmente para a frente 2; as frentes 3-6
ainda não chegaram a este passo.**

Checklist por frente, quando implementada: problema reproduzido → correção →
teste direcionado → doc/STATUS.md atualizados → commit coerente → (no fim de
todas as frentes de uma sessão) suíte completa, scanner de segredos, diff
revisado, fluxos testados no navegador quando aplicável, push para
`origin/main`.
