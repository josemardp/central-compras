# STATUS — Central de Compras

> Doc de handoff. Qualquer máquina ou agente retoma a partir daqui.
> Estado do **repositório**. O estado de cada compra fica em
> `projetos/<projeto>/processo.md`, ou rodando
> `python scripts/central_compras.py status projetos/<projeto>`.

## Última sessão: 28/08/2026 (continuação)

- **As duas decisões de calibragem abaixo foram tomadas e implementadas**:
  categoria `carro` marcada `sem_frete` no `categorias.yaml` (eixo
  `conveniencia` sai da conta, confiança deixa de travar em 0,90), e a regra
  de parada agora conta todo `produto.yaml` mapeado pro projeto, não só quem
  tem cotação (`project_candidate_ids()`). 208 testes passando. `validar` no
  carro elétrico já mostra os dois avisos reais: 10 candidatos contra teto de
  4, e os 10 sem cotação suficiente. Commit `1023200`, já em `origin/main`.

## Sessão anterior: 28/08/2026

- Absorvido o projeto `ev-decisao` (repo local que nunca foi publicado, encerrado
  e apagado). Virou `projetos/2026-comprar-carro-eletrico`: briefing, 10
  candidatos, 11 anotações de pesquisa, 10 lições na categoria `carro`, e
  `pesquisa-herdada.md` com os 14 campos de fonte primária e o simulador de
  viagem. Nenhum preço foi transferido, de propósito: nenhum tinha fonte primária.
- Documentos de origem preservados em
  `projetos/2026-comprar-carro-eletrico/referencia/`, com aviso do que já foi
  substituído pela Central.
- Reescrito `docs/prompt-auditoria-externa.md` para a **3ª rodada de auditoria**.
  Quem rodou não foi o Kimi, foi o **Antigravity** (agente Gemini) — protocolo
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
  do painel — ver "Do repositório" abaixo.

## Próximo passo

**As duas decisões de calibragem que travavam o carro já foram feitas.** O
que falta agora pra cotar de verdade são os passos manuais do Josemar (ver
"Pendências" abaixo: km/mês, rotas, quadro elétrico, data-limite, distância
máxima) — sem eles não dá pra registrar cotação de verdade nem simular TCO.
Nenhum passo de código bloqueia o carro neste momento.

## Pendências

### Passos manuais do Josemar (bloqueiam o projeto do carro)

- Medir **km/mês por 2 semanas** e o percentual de rodovia. Não chutar.
- Listar as **rotas recorrentes** (origem, destino, km, vezes por mês).
- Levantar em casa: tensão (127/220 V), capacidade do quadro, distância do
  quadro até a vaga, tarifa de kWh da fatura e se há tarifa branca.
- Definir a **data-limite de decisão**. Sem ela, a única trava contra pesquisar
  para sempre é a regra de 30 dias da Central.
- Definir a distância máxima aceitável até concessionária.

### Do repositório

- **A skill não está instalada nesta máquina.** O README manda instalar em
  `C:\Users\pc\.codex\skills\central-compras`, caminho que não existe (o usuário
  é `josem`). Não há script de instalação, e o repo é usado de várias máquinas
  por agentes diferentes (Codex, Claude Code, Antigravity). A 3ª auditoria
  confirmou de novo, ainda sem dono.
- Falta a tag `v1.0` e a rotina semanal.
- Carro elétrico: 10 candidatos mapeados, regra de parada permite 4 (agora com
  aviso de verdade em `validar`). O corte final pra 4 depende de levantar
  preço público com fonte e data — ainda não feito.
- `nota 4.8` com `n_avaliacoes 0` na linha do JBL é dado de entrada errado. A
  validação acusa, aguarda decisão.
- `peso_ancora: 250` (nota bayesiana) é global; a 3ª auditoria mostrou que
  esmaga categoria de poucas avaliações (ex.: material de construção). Migrar
  pra `categorias.yaml` é julgamento do Josemar, não feito ainda.
- `artifact.html` é varrido por `checar-segredos`, mas os padrões só pegam
  CPF/cartão/senha/token — não pegam CEP, endereço ou nome solto em texto
  livre (campo `porque`, notas). Risco condicional ao que for digitado ali.

## Decisões que valem lembrar

- **Nenhum preço sem fonte primária entra no repositório.** Foi por isso que a
  migração do ev-decisao trouxe a pesquisa e deixou todos os preços para trás.
- **Derivados ficam versionados de propósito** (`ranking.md` ao lado do
  `decisao.md` é a evidência de por que a decisão foi tomada naquele dia).
  Conflito de merge em derivado se resolve com `regenerar`, não à mão.
- O ev-decisao morreu porque **reconstruía o que a Central já faz**. Antes de
  criar ferramenta nova para decidir compra, verificar se a Central já resolve.
