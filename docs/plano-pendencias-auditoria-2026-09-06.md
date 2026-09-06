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

**Estado: concluída** (sessão de 06/09/2026, tarde). Commit: ver `STATUS.md`.

### O que foi confirmado no código (antes de mexer)

`decidir` grava, em sequência, snapshot (múltiplos arquivos), `decisao.md`,
duas linhas de linha do tempo em `processo.md` e um arquivo de veredito.
`aprender-veredito` grava marca, loja e lição na base de conhecimento e só
por último acrescenta o marcador "Aprendizado exportado" no veredito. Cada
gravação individual já era atômica (`atomic_write_text`), mas a sequência
não era: nada impedia que uma repetição do comando, após uma falha no meio,
repetisse passos já feitos.

### Reprodução

Script de reprodução (descartável, não entrou no repositório): abre uma
compra, fecha veredito D+30 com lição, corrompe `append_text` para falhar
exatamente na escrita do marcador de exportado, roda `aprender-veredito`
(falha como esperado) e roda de novo sem a falha simulada. **Resultado antes
da correção: a lição aparecia duas vezes em `base-conhecimento/licoes.md`.**
O mesmo padrão foi confirmado em `decidir`: falha simulada em
`append_timeline` na escrita da linha "veredito" e reexecução duplicava a
linha "decisao" em `processo.md`.

### Correção

Mecanismo novo em `scripts/central_compras.py`: `tracked_operation()` /
`OperationHandle` / `pending_operations()`.

- Antes de começar uma sequência de gravações, o comando grava um journal em
  `<escopo>/.operacoes/<op_id>.json` (dentro da pasta já travada por
  `project_lock`), com `situacao: em_andamento` e a lista de passos
  concluídos.
- Cada passo que pode duplicar em append-only (`register_marca`,
  `register_loja`, `register_lesson`, as duas chamadas de
  `append_timeline`) primeiro confere `op.concluido("nome")`; só executa e
  marca se ainda não tiver sido feito **nesta tentativa** (mesmo `op_id`).
- Terminou sem exceção → o journal é apagado. Não sobra rastro de operação
  concluída.
- Terminou com exceção → o journal fica em disco, com os passos já feitos.
  A próxima chamada com o mesmo `op_id` (mesmo produto, mesmo veredito+fase)
  lê esse journal e pula o que já foi feito.
- Comando novo `operacoes-pendentes` varre `base-conhecimento/.operacoes/` e
  `projetos/*/.operacoes/` e lista o que ficou `em_andamento` — nunca fica
  escondido atrás de um retry que "parece ter dado certo". `--strict` sai
  com código 1 se houver alguma pendente (para checagem em rotina).
- `.operacoes/` entrou no `.gitignore`, ao lado de `.central-compras.lock`.

Aplicado em `decidir` (journal por `produto_id`) e `aprender-veredito`
(journal por veredito + fase). **Não é transação atômica entre arquivos** —
isso não foi prometido. É recuperação: nenhum registro duplicado, nenhuma
operação incompleta passa por concluída, e o que ficou pendente é visível.

### Testes

`tests/test_operation_recovery.py`, 4 testes novos:

- retry de `aprender-veredito` após falha simulada não duplica a lição, e
  ainda assim completa o marcador que faltava;
- retry de `decidir` após falha simulada não duplica linha na linha do
  tempo, e completa a linha que faltava;
- `operacoes-pendentes` relata a pendência e some depois que a operação
  completa (inclusive o código de saída de `--strict`);
- journal corrompido (JSON inválido) é reportado como ilegível, não trava o
  comando nem finge que os passos anteriores são confiáveis.

Suíte completa depois da mudança: ver `STATUS.md` para o número final.

### O que este mecanismo não cobre (registrado, não é lacuna escondida)

- Concorrência entre dois processos ao mesmo tempo continua dependendo só de
  `project_lock`/`BASE` lock; o journal em si não tem lock próprio (documentado
  no docstring de `tracked_operation`).
- Falta de espaço em disco no meio da própria escrita do journal ainda pode
  deixar um estado inconsistente — é o mesmo limite que já existia em
  `atomic_write_text` para qualquer arquivo isolado.
- Não cobre a exportação para o Google Sheets (frente 3) nem qualquer outra
  sequência multi-arquivo fora de `decidir`/`aprender-veredito`. Se uma
  sessão futura achar outro ponto candidato, o mesmo `tracked_operation` deve
  ser reaproveitado, não reinventado.

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
