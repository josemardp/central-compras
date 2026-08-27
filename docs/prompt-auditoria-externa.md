# Prompt para auditoria externa (Codex) — segunda rodada

Copie tudo daqui para baixo e cole no Codex, com o repositório aberto.

---

Você já auditou este repositório uma vez. **Todos os seus seis achados eram
reais**, foram reproduzidos e corrigidos, e viraram teste de regressão. Esta é a
segunda rodada, e ela tem um objetivo diferente da primeira.

Na primeira, você procurou defeito num código que ninguém de fora tinha olhado.
Agora você procura duas coisas mais difíceis:

1. **Correção que criou problema novo.** Toda correção mexe em algo. Seis
   correções suas mais três minhas foram aplicadas de uma vez.
2. **O que nenhuma das duas auditorias tocou.** A primeira olhou o motor de
   decisão e a integridade. Ninguém olhou a skill, os templates, o ciclo de
   veredito, o dashboard como produto, nem o sistema como *ferramenta de compra*.

## O repositório

`C:\projetos\central-compras` — GitHub privado `josemardp/central-compras`, `main`.

Memória permanente de decisão de compra de uma pessoa física. Preço envelhece em
48 horas; o par *decisão + veredito* ("por que escolhi X" e, seis meses depois,
"deu certo?") vale para sempre. Serve para um perfume de R$ 70 e para um carro
elétrico de R$ 150.000 — muda a profundidade da pesquisa, nunca a estrutura.

- Python 3, dependência única `PyYAML`. Arquivo único, 30 subcomandos.
- 143 testes: `python -m unittest discover -s tests`.
- Usado de **várias máquinas Windows**, PowerShell e Git Bash.
- Fontes: `cotacoes.csv` (append-only, o livro-razão), `produto.yaml`,
  `briefing.md`, `config/*.yaml`, `base-conhecimento/`, `vereditos/`.
- Derivados: `ranking.md`, `ranking.csv`, `validacao.md`, `historico.md`,
  `memoria-calculo.md`, `dashboard/`. Versionados de propósito; `regenerar`
  refaz todos.

Os cinco princípios do PRD, que continuam sendo o critério:

1. Fato datado nunca é sobrescrito.
2. Gate antes de score.
3. Todo número é rastreável, reconstruível à mão com uma calculadora.
4. O "não escolhi" vale mais que o "escolhi".
5. Dado pessoal não mora em repositório versionado.

## O que mudou desde a sua auditoria

`git log 447aa0d..HEAD` mostra tudo. Dois commits: `e28af86` (seus achados) e
`c321550` (concorrência).

**Seus seis achados, corrigidos assim:**

| Achado | Correção |
|---|---|
| `decidir` fechava produto cortado no gate | `decide()` agora chama `gate_eliminations`; recusa sem `--permitir-cortado` |
| `promover-cotacao` lavava web antiga como manual | exige informar ao menos um campo conferido, ou `--sem-alteracao` explícito |
| `NaN`/infinito passavam como preço | barrados em `quote_float` via `math.isnan`/`isinf`; reportados em `validar` |
| Data futura passava | `reject_future()` no `iso_datetime`; `validar` também acusa |
| `auditar` usava `custo_total` com ranking em `tco_total` | regra extraída para `value_field_for()`, única, usada pelos dois |
| Varredor com falsos-negativos | CPF rotulado sem pontuação, `_` como separador de cartão, `.env` varrido, `\b` removido antes de `api_key` |

**Seu achado de julgamento (o 0,50 neutro premiando o silêncio)** virou uma
mudança estrutural: o eixo sem dado agora **sai da conta** e os pesos restantes
são renormalizados. O score mede só o que se sabe. Nasceu um índice `confianca`
(fração do peso apoiada em dado real), publicado no `ranking.md`, no
`ranking.csv` e na memória de cálculo, e `decidir` recusa fechar abaixo de 75%.

**Sobre derivados versionados eu discordei de você** e quero que reavalie: não
tirei do Git, porque o `ranking.md` ao lado do `decisao.md` é a evidência de por
que a decisão foi tomada naquele dia. Em vez disso criei `regenerar`. Diga se
continua achando errado.

**Três achados que eu mesmo encontrei ao preparar esta rodada**, seguindo a sua
pista de concorrência (você tinha testado 30 `cotar` paralelos e não visto perda;
a corrida existia mas seu teste não a expôs):

- `cotar` relia e reescrevia o CSV inteiro para acrescentar uma linha. Dois
  comandos simultâneos liam a mesma base e um sobrescrevia o outro. Agora anexa
  de verdade, sem reler.
- `atomic_write_text` usava nome de temporário **fixo**: dois processos
  escreviam no mesmo `.processo.md.tmp` e um apagava o do outro.
- No Windows, `os.replace` falha se outro processo tiver o destino aberto, mesmo
  só para leitura. Adicionei repetição com espera e uma trava por projeto.

Medido: 25 `cotar` em paralelo saíram de 6 linhas gravadas / 20 processos com
erro para **25 linhas e zero erros**.

## O que eu quero desta rodada

### 1. As correções criaram problema novo?

Esta é a pergunta principal. Especificamente:

- **A trava por projeto** (`project_lock` em `central_compras.py`). Ela pode
  emperrar? Deadlock, trava órfã que não expira, comando que morre segurando,
  Ctrl+C no meio, dois comandos em projetos diferentes se bloqueando à toa?
  O `MUTATING_COMMANDS` cobre os comandos certos, ou sobrou um que escreve sem
  travar, ou trava um que só lê?
- **O `append_quote`** substituiu o ciclo ler-modificar-reescrever. Ele preserva
  colunas extras escritas à mão? Lida com arquivo sem newline final? E se o
  cabeçalho tiver coluna a mais que o schema, em vez de a menos?
- **A renormalização do score.** Ela pode produzir divisão por zero, score fora
  de 0-100, ou um caso em que *todos* os eixos faltam? A `confianca` bate com o
  que realmente entrou na conta? Compare `ranking.csv` com `memoria-calculo.md`.
- **As quatro travas do `decidir`** (`--permitir-cortado`, `--permitir-vencida`,
  `--permitir-aguardando`, `--permitir-incompleto`). Elas se contradizem? Existe
  ordem em que uma esconde a outra? Existe caminho que passa por todas?
- **Os padrões novos do varredor.** `(?i)(token|api[_-]?key|...)` sem `\b` à
  esquerda: isso gera falso-positivo em texto comum? E o CPF rotulado?

### 2. O território que ninguém auditou

Nenhuma das duas rodadas olhou isto:

- **A skill** (`skills/central-compras/`). Ela descreve o sistema como ele é
  hoje, ou ficou defasada depois de 12 sprints? Um agente seguindo só ela
  conseguiria conduzir uma compra do início ao fim? Ela ensina algum comando
  que não existe mais, ou omite trava que faria o agente travar sem entender?
- **Os templates** (`templates/`). As perguntas do `briefing.md` e do
  `veredito.md` extraem o que precisa ser extraído? O que falta perguntar para
  uma compra dar errado menos vezes?
- **O ciclo de veredito de ponta a ponta.** Rode: compra → `decidir` →
  `preencher-veredito` D+30 → `aprender-veredito` → veja se a lição vira gate →
  abra uma compra nova da mesma categoria e veja se o `prompt-ia` aproveita.
  Esse loop é o produto inteiro. Ele fecha de verdade ou tem elo solto?
- **O dashboard como produto**, não como código. Abra
  `dashboard/index.html`. Ele responde as perguntas que alguém realmente faz
  ("o que estou esperando baixar de preço?", "me arrependi de quê?"), ou é
  tabela bonita de dado que não decide nada?
- **A experiência de erro.** Erre de propósito em dez lugares. As mensagens
  dizem o que fazer, ou só o que aconteceu?

### 3. O teste dirigido pelo produto

Faça uma compra fictícia inteira, de ponta a ponta, como se você fosse o dono,
**sem ler o README antes**. Só `--help`. Anote onde travou, onde teve que
adivinhar, onde a ferramenta te fez trabalhar por ela.

Depois faça a mesma compra lendo o README. O que o README não conta e deveria?

### 4. Julgamento, de novo

Você já opinou sobre escalas e pesos. Agora que o 0,50 virou renormalização mais
confiança, reavalie:

- O limite de **75% de confiança** para decidir é bem calibrado? Com que
  frequência ele vai atrapalhar sem motivo?
- A **renormalização** resolveu o incentivo perverso, ou só mudou de lugar?
  Continua valendo a pena omitir dado?
- `μ=4,3` e `m=50` na nota bayesiana: você disse que `m=50` é fraco para
  marketplace grande. Que valor você usaria, e por quê?
- Qualidade de **3,8 a 5,0**: você disse que é otimista. Qual faixa?

Se você mantiver uma crítica que eu não implementei, **insista com argumento**.
Eu discordei da sua sugestão sobre derivados versionados; se você continuar
achando que estou errado, diga por quê de novo.

## Regras

- **Reproduza antes de reportar.** Comando e saída real. Sem reprodução eu descarto.
- **Não conserte.** Diagnóstico primeiro; correção, se propuser, em diff separado.
- **Não invente.** `[NÃO VERIFICADO: motivo]` em vez de completar com plausibilidade.
- Os 143 testes passam aqui. Se falhar aí, isso já é achado — reporte o ambiente.
- **Se não achar nada crítico, diga isso.** Não invente achado para justificar a
  auditoria. "Procurei em X, Y e Z e está sólido" é resultado válido e útil.

## Já sei, não gaste tempo

- `nota 4.8` com `n_avaliacoes 0` na linha do JBL: dado de entrada errado, a
  validação acusa, aguarda decisão do dono.
- As 4 cotações daquele projeto são `fonte=web`; nenhuma compra fechada ainda.
- O carro elétrico (Dolphin Mini GL, Geely EX2 Pro, King GL, Atto 2 DM-i) ainda
  não foi registrado. É o próximo passo.
- Falta a tag `v1.0`, o guia de nova categoria e a rotina semanal.

## Formato

```
## Veredito em uma linha

## As correções criaram problema novo?
[o principal; com reprodução, ou "não encontrei, procurei em X e Y"]

## Território não auditado (skill, templates, ciclo de veredito, dashboard, erros)

## O teste dirigido pelo produto
[onde a ferramenta te fez trabalhar por ela]

## Julgamento revisado

## Onde eu continuo discordando de você
[se for o caso]

## O que não consegui verificar
```

Ordene por **impacto na decisão de compra**, não por severidade técnica.
