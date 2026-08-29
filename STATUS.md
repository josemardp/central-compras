# STATUS: Central de Compras

> Doc de handoff. Qualquer máquina ou agente retoma a partir daqui.
> Estado do **repositório**. O estado de cada compra fica em
> `projetos/<projeto>/processo.md`, ou rodando
> `python scripts/central_compras.py status projetos/<projeto>`.

## Última sessão: 28/08/2026 (fechamento)

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

- v1 estabilizada. **208 testes passando** (`python -m unittest discover -s tests`).
- Três projetos: fone bluetooth, Decor Bloqueador, carro elétrico.
- **Nenhuma compra fechada ainda.** O ciclo de veredito (D+30 / D+180) nunca
  rodou com dado real.
- `scripts/painel.py` e o `artifact` já foram auditados (3ª rodada), bugs
  corrigidos, e as duas calibragens específicas do carro já decididas e
  implementadas. Seguem pendentes, como julgamento (não bug): `peso_ancora`
  global, escala de prazo por categoria pras demais (não-carro), reatividade
  do painel. Ver "Do repositório" abaixo.

## Próximo passo

**Josemar decidiu atacar as pendências gerais do repositório antes de voltar
pro carro.** Enviar `docs/prompt-ajustes-repositorio.md` ao Codex (6 itens:
dado errado do JBL, `peso_ancora` por categoria, gap de PII no
`artifact.html`, reatividade do painel, instalador da skill, tag `v1.0` +
docs de rotina semanal/nova categoria).

**Quando o Josemar colar o retorno do Codex aqui, leia
`docs/como-conferir-auditoria.md` ANTES de agir**: o mesmo protocolo de
triagem de auditoria vale pra retorno de implementação: conferir diff, rodar
teste, só então aceitar. Já foi feito assim com o Antigravity nesta mesma
sessão e funcionou.

Separado disso, ainda pendente no projeto do carro (não é o foco agora, mas
não sumiu): nenhum dos 10 candidatos tem autonomia/consumo/bateria
preenchido, então não dá pra estimar custo de energia por carro nem cortar
pra 4. Perguntei ao Josemar se quer que eu pesquise isso com fonte oficial;
ainda sem resposta.

## Pendências

### Passos manuais do Josemar (bloqueiam o projeto do carro)

- Levantar em casa: **capacidade do quadro elétrico e distância do quadro até
  a vaga** (define custo de wallbox). Exige inspeção física, ninguém consegue
  fazer por ele.
- Definir a **data-limite de decisão**. Confirmado em 28/08 que ainda não
  existe. Sem ela, a única trava contra pesquisar para sempre é a regra de 30
  dias da Central.
- Definir a **distância máxima aceitável até concessionária**. Confirmado em
  28/08 que ainda não existe.

~~Medir km/mês, rotas, tensão residencial~~: feito em 28/08/2026 a partir da
conta de energia e da rotina declarada, ver `briefing.md` do projeto.

### Do repositório

- **A skill não está instalada nesta máquina.** O README manda instalar em
  `C:\Users\pc\.codex\skills\central-compras`, caminho que não existe (o usuário
  é `josem`). Não há script de instalação, e o repo é usado de várias máquinas
  por agentes diferentes (Codex, Claude Code, Antigravity). A 3ª auditoria
  confirmou de novo, ainda sem dono.
- Falta a tag `v1.0` e a rotina semanal.
- Carro elétrico: 10 candidatos mapeados, regra de parada permite 4 (agora com
  aviso de verdade em `validar`). O corte final pra 4 depende de levantar
  preço público com fonte e data, ainda não feito.
- `nota 4.8` com `n_avaliacoes 0` na linha do JBL é dado de entrada errado. A
  validação acusa, aguarda decisão.
- `peso_ancora: 250` (nota bayesiana) é global; a 3ª auditoria mostrou que
  esmaga categoria de poucas avaliações (ex.: material de construção). Migrar
  pra `categorias.yaml` é julgamento do Josemar, não feito ainda.
- `artifact.html` é varrido por `checar-segredos`, mas os padrões só pegam
  CPF/cartão/senha/token, não pegam CEP, endereço ou nome solto em texto
  livre (campo `porque`, notas). Risco condicional ao que for digitado ali.

## Decisões que valem lembrar

- **Nenhum preço sem fonte primária entra no repositório.** Foi por isso que a
  migração do ev-decisao trouxe a pesquisa e deixou todos os preços para trás.
- **Derivados ficam versionados de propósito** (`ranking.md` ao lado do
  `decisao.md` é a evidência de por que a decisão foi tomada naquele dia).
  Conflito de merge em derivado se resolve com `regenerar`, não à mão.
- O ev-decisao morreu porque **reconstruía o que a Central já faz**. Antes de
  criar ferramenta nova para decidir compra, verificar se a Central já resolve.
