# Prompt para auditoria externa (Codex) — terceira rodada

Copie tudo daqui para baixo e cole no Codex, com o repositório aberto.
(As rodadas 1 e 2 estão no histórico do Git: `git log -- docs/prompt-auditoria-externa.md`.)

---

Você já auditou este repositório duas vezes. Nas duas, seus achados eram reais,
foram reproduzidos, corrigidos e viraram teste de regressão. Obrigado — e é
justamente por isso que esta rodada não é mais do mesmo.

A rodada 1 auditou o **motor de decisão** e a integridade dos dados.
A rodada 2 auditou as **regressões** dessas correções, mais a skill, os
templates, o ciclo de veredito, o dashboard e a experiência de erro.

**Não repita esse território.** Aquilo está julgado. Esta rodada tem dois alvos
que nunca foram olhados por ninguém, e o segundo é o mais importante.

## O repositório

`C:\projetos\central-compras` — GitHub privado `josemardp/central-compras`, `main`.

Memória permanente de decisão de compra de uma pessoa física. Preço envelhece em
48 horas; o par *decisão + veredito* ("por que escolhi X" e, seis meses depois,
"deu certo?") vale para sempre. Serve para um perfume de R$ 70 e para um carro
elétrico de R$ 150.000 — muda a profundidade da pesquisa, nunca a estrutura.

- Python 3, dependência única `PyYAML`.
- `scripts/central_compras.py` — 4.190 linhas, arquivo único, ~30 subcomandos.
- `scripts/painel.py` — 683 linhas, servidor HTTP local que **escreve no repositório**.
- **200 testes**: `python -m unittest discover -s tests`. Passam aqui.
- Usado de **várias máquinas Windows**, PowerShell e Git Bash, por uma pessoa que
  **não é desenvolvedor profissional**.
- Fontes: `cotacoes.csv` (append-only, o livro-razão), `produto.yaml`,
  `briefing.md`, `config/*.yaml`, `base-conhecimento/`, `vereditos/`.
- Derivados versionados de propósito; `regenerar` refaz todos; `snapshots/` é
  congelado e nunca regenerado.

Os cinco princípios do PRD continuam sendo o critério:

1. Fato datado nunca é sobrescrito.
2. Gate antes de score.
3. Todo número é rastreável, reconstruível à mão com uma calculadora.
4. O "não escolhi" vale mais que o "escolhi".
5. Dado pessoal não mora em repositório versionado.

## O que existe hoje que você nunca viu

`git log 02807b0..HEAD` mostra tudo. Depois do pacote de estabilização v1:

| Commit | O que entrou |
|---|---|
| `6857093`, `a7bea15` | guia prático visual (`docs/guia-pratico-visual.html`) |
| `789d305` | processo real: Decor Bloqueador (material de construção) |
| `73b10cd` | **`painel` local editável + `artifact` de consulta** |
| `6ed32e3` | artifact também no formato de publicação |
| `10466b5`, `9d2a958` | **projeto de carro elétrico**, absorvido de um projeto morto |

O `painel` e o `artifact` são ~700 linhas que nenhuma auditoria tocou. O projeto
de carro é o primeiro uso real da categoria `carro` e do caminho de TCO.

---

# A IDEIA ORIGINAL (o critério de aceite que você nunca viu)

Isto é o que o dono pediu, com as palavras dele, antes de existir qualquer linha
de código. É o padrão contra o qual eu quero que você julgue o produto:

> "Eu faço muitas compras na internet e dependo de cotações tops. Quero
> construir uma central de compras, repositório local e GitHub. Vai ter
> habilidades de navegação e pesquisa em tempo real atual eficaz, preferências
> minhas, dados, endereços etc. Um ou mais arquivos de controle, tipo produto
> pretendido, daí vai criando as colunas com variações de tipo, marca, preço.
> A princípio prefiro compras no ML e Amazon, mas nada impede cotar em outras
> frentes. Foco em produtos bem validados, bem avaliados. Tipo, eu quero
> comprar um carro X, a central vai me construindo e me guiando na melhor
> escolha. Ou até algo mais simples: comprar um celular, um tênis."
>
> "Tipo, eu abro uma aba, pode ser no VS Code mesmo, vou conversando com a
> central e do lado vai sendo editado tudo. A IA me mostra as opções, vai
> salvando os dados cabíveis e tal. Seria como eu conversar com a tela de
> pesquisa ao mesmo tempo que vejo ela. E ir montando um dossiê, um controle de
> todos os dados pra guiar minha decisão, tudo isso lado a lado: conversa e tela
> de dados para decisão. Eu peço pra IA pesquisar, ela pesquisa e já lança o
> dado na tela ao lado que está aberta na central."

Leia isso duas vezes. O sistema de hoje é um CLI de 30 subcomandos, uma skill e
um painel que precisa ser recarregado. **A pergunta é honesta e eu quero a
resposta honesta:** isso virou a coisa que ele pediu, ou virou uma coisa boa e
diferente?

---

## O que eu quero desta rodada

### 1. O painel e o artifact (código novo, risco novo)

`scripts/painel.py` sobe um `ThreadingHTTPServer` em `127.0.0.1:8800` que grava
no repositório. O README promete: *"o painel não é porta dos fundos: toda
gravação passa pelos mesmos caminhos do CLI, com a mesma trava por projeto, a
mesma validação de entrada e o mesmo append-only."*

**Verifique se essa frase é verdadeira ou apenas quase verdadeira.** Onde o
caminho do painel diverge do caminho do CLI, ainda que um pouco, é achado.

Superfícies que eu quero que você olhe com nome e sobrenome (não estou afirmando
que há bug em nenhuma delas — estou dizendo onde procurar):

- **`_resolver()`** recebe nome de projeto vindo da query string (`/api/estado`)
  e do corpo JSON (`/api/acao`). Ele aceita `../`, caminho absoluto, nome com
  separador, nome vazio, nome com unicode? Dá para fazer o painel ler ou
  escrever fora de `projetos/`?
- **`POST /api/acao` não tem verificação de origem visível.** O servidor escuta
  em 127.0.0.1 e não pede autenticação, por desenho. Mas enquanto o painel está
  no ar, uma página qualquer que o dono abra no navegador pode disparar `fetch`
  para `http://127.0.0.1:8800/api/acao`? O `Content-Type: application/json`
  segura sozinho, ou passa com `text/plain`? E rebind de DNS? Se der para
  escrever no repositório a partir de uma aba aleatória, isso é o achado mais
  grave desta rodada. Se não der, diga por que não dá — quero o argumento, não a
  suposição.
- **`ThreadingHTTPServer` + `project_lock`.** Duas abas abertas no mesmo projeto,
  dois POSTs simultâneos: perde linha? Emperra? A trava por projeto foi desenhada
  para processos separados; ela se comporta igual entre *threads* do mesmo
  processo?
- **Ctrl+C com requisição em voo**, e o `finally: server_close()`: deixa trava
  órfã? Deixa `.tmp` para trás?
- **O limite de 1 MB no corpo** e o `int(Content-Length or 0)`: `Content-Length`
  negativo, ausente, ou não numérico derruba o servidor?
- **`artifact.html`** é gerado para ser lido no celular e é "página única e
  autossuficiente". **Ele pode conter dado pessoal?** Endereço, CEP, nome de
  vendedor, link com parâmetro identificável, qualquer coisa que viole o
  princípio 5 se a página for compartilhada ou parar num serviço de publicação.
  O `checar-segredos` varre a árvore versionada — ele varre o `artifact.html`?

### 2. A distância entre a ideia original e o que existe

Esta é a parte principal, e é julgamento de produto, não caça a bug.

Releia a ideia original acima. Depois faça, de verdade, o exercício abaixo, e
me diga onde a ferramenta ficou devendo:

**a) A promessa da "tela ao lado".** O painel foi a primeira tentativa. Abra-o
(`python scripts/central_compras.py painel`), coloque-o lado a lado com um chat,
e simule: o dono pede uma pesquisa, o agente responde, o dado precisa aparecer
na grade. Quantos passos manuais existem entre "a IA achou o preço" e "o preço
está na tela"? A grade atualiza sozinha ou ele tem que recarregar? Isso é
"conversar com a tela de pesquisa ao mesmo tempo que vejo ela", ou é um CRUD com
navegador?

**b) A "pesquisa em tempo real".** O sistema não tem navegação nem scraping, por
decisão explícita e bem argumentada (site de loja quebra toda semana). Mas a
ideia original pedia exatamente isso. Hoje o caminho é: o agente pesquisa por
fora, o humano digita. **Qual é o menor caminho honesto que aproxima o sistema
do pedido sem construir um scraper frágil?** Quero a sua recomendação, incluindo
a possibilidade de "não faça nada disso, a decisão original está certa e o que
falta é explicar melhor". E se você recomendar algo, diga o que **não** construir
junto.

**c) Onde ele trabalha por ela.** Você já fez o teste dirigido pelo produto na
rodada 2, com uma compra fictícia. Agora faça diferente: **use o projeto de
carro elétrico que já está no repositório** (`projetos/2026-comprar-carro-eletrico`).
Ele tem 10 candidatos mapeados, nenhuma cotação, e uma regra de parada que só
permite 4 candidatos. Tente levá-lo do estado atual até ter uma shortlist de 4.
Onde a ferramenta ajuda? Onde ela só cobra? A categoria `carro` e o caminho de
TCO nunca rodaram de verdade — eles se sustentam?

**d) O ML e a Amazon.** A ideia original nomeia as duas lojas como principais.
`lojas_preferidas` é uma lista em YAML que entra no eixo risco, e é isso. Existe
algo específico dessas duas que o sistema deveria saber e não sabe (padrão de
anúncio, vendedor oficial vs. terceiro, reputação, histórico de preço)? Ou
generalizar foi a escolha certa?

### 3. Erosão de escala

Um arquivo de 4.190 linhas com 30 subcomandos, escrito ao longo de 14 sprints
por agentes diferentes.

- Existe **regra duplicada em dois lugares** que já divergiu, ou vai divergir na
  próxima mudança? (Na rodada 1 você achou uma: `custo_total` vs `tco_total`,
  resolvida com `value_field_for()`. Existem outras?)
- Existe subcomando **morto, quebrado ou que ninguém usaria**? 30 é muito.
- Os 200 testes: eles cobrem o que quebra, ou cresceram cobrindo o que é fácil
  de testar? Aponte a área com mais risco e menos teste.
- `config/categorias.yaml` tem 7 categorias. Abrir a oitava exige o quê? Um
  não-desenvolvedor consegue?

### 4. Um achado que eu já confirmei — comece por ele

O README manda instalar a skill em `C:\Users\pc\.codex\skills\central-compras`.
**Esse caminho não existe nesta máquina** (o usuário é `josem`, não `pc`), e a
skill também não está em `C:\Users\josem\.codex\skills\`. Ou seja: a skill está
documentada como instalada e não está.

Isso levanta a pergunta maior, que é a que me interessa: **como a skill chega às
várias máquinas dele?** Não há script de instalação. Ele usa Codex *e* Claude
Code; `skills/central-compras/agents/openai.yaml` só atende o Codex. Qual é o
desenho certo aqui?

### 5. Julgamento, de novo

Você já opinou sobre escalas e pesos, e várias sugestões suas viraram
`preferencias.yaml`. Agora, com dois projetos reais no repositório:

- `confianca_minima_para_decidir` subiu para 0,90 (padrão) e 0,95 (acima de
  R$ 20 mil). Na rodada 2 o número era 0,75 e você achou frouxo. **Passou do
  ponto?** Com 0,95, um carro fecha algum dia?
- `peso_ancora: 250` na nota bayesiana veio da sua crítica ao `m=50`. Ficou bom
  para marketplace grande, mas e para categoria de poucas avaliações — material
  de construção, por exemplo, onde 30 avaliações já é muito? O número único
  serve para as duas pontas?
- O eixo `valor` é razão contra o mais barato do conjunto, e o README avisa que
  o score total não é comparável entre projetos. Isso é limitação aceitável ou
  defeito de desenho que ainda vai morder?

Se você mantiver uma crítica que eu não implementei, **insista com argumento**.

## Regras

- **Reproduza antes de reportar.** Comando e saída real. Sem reprodução eu descarto.
- **Não conserte.** Diagnóstico primeiro. Se propuser correção, em diff separado,
  no fim, e claramente marcada como proposta.
- **Não invente.** `[NÃO VERIFICADO: motivo]` em vez de completar com
  plausibilidade. Isso vale em dobro para as perguntas de segurança do painel:
  se você não conseguiu montar o ataque, diga que não conseguiu, não diga que é
  seguro.
- Os 200 testes passam aqui. Se falharem aí, isso já é achado — reporte o ambiente.
- **Se não achar nada crítico, diga isso.** "Procurei em X, Y e Z e está sólido"
  é resultado válido e útil. Não invente achado para justificar a auditoria.
- Ordene por **impacto na decisão de compra**, não por severidade técnica. Um bug
  que faz o dono comprar o carro errado vale mais que dez avisos de lint.
- Lembre quem usa: uma pessoa que não é desenvolvedora, em várias máquinas
  Windows. "Bastaria rodar um `git filter-repo`" não é solução para ele.

## Já sei, não gaste tempo

- O projeto de carro elétrico tem 10 candidatos e nenhuma cotação. É de
  propósito: nenhum preço da pesquisa de origem foi verificado em fonte
  primária, então nenhum foi transferido. A shortlist é o próximo passo.
- `nota 4.8` com `n_avaliacoes 0` na linha do JBL é dado de entrada errado; a
  validação já acusa.
- Nenhuma compra foi fechada ainda em nenhum projeto. O ciclo de veredito nunca
  rodou com dado real — se isso atrapalhar sua análise, diga.
- Falta a tag `v1.0` e a rotina semanal.
- Derivados versionados: já discutimos duas vezes, mantive com `regenerar`.
  Só volte ao assunto se tiver argumento novo.

## Formato

```
## Veredito em uma linha

## O painel e o artifact
[o mais grave primeiro; com reprodução, ou "tentei X e Y e não consegui"]

## A distância entre a ideia original e o que existe
[a) tela ao lado  b) pesquisa em tempo real  c) onde ele trabalha por ela
 d) ML e Amazon — e a sua recomendação, incluindo o que NÃO construir]

## Erosão de escala

## Skill e várias máquinas

## Julgamento revisado

## Onde eu continuo discordando de você

## O que não consegui verificar
```

Se, ao fim de tudo, a sua conclusão for "o sistema é bom, mas não é o que foi
pedido", eu quero ler isso em letras grandes. É a resposta mais valiosa que esta
auditoria pode produzir.
