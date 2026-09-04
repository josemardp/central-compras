# Prompt para auditoria externa (Codex) — quarta rodada

Copie tudo daqui para baixo e cole no Codex, com o repositório aberto.
(As rodadas 1 a 3 estão no histórico do Git: `git log -- docs/prompt-auditoria-externa.md`.)

---

Esta rodada tem um alvo estreito e um motivo concreto: **a integração com o
Google Sheets foi construída três vezes, por três agentes diferentes, e o
código dela já produziu três bugs — todos descobertos tarde, um deles só
porque o dono abriu a planilha e reparou que faltava coisa.**

Quero que você olhe justamente isso: a planilha publicada, o script que a
escreve, e os documentos que deviam ter impedido a confusão toda.

## O repositório

`C:\projetos\central-compras` — GitHub privado `josemardp/central-compras`, `main`.

Memória permanente de decisão de compra de uma pessoa física. Preço envelhece
em 48 horas; o par *decisão + veredito* ("por que escolhi X" e, seis meses
depois, "deu certo?") vale para sempre.

- Python 3, dependência única `PyYAML`. `scripts/central_compras.py`, arquivo
  único, ~30 subcomandos.
- **270 testes**: `python -m unittest discover -s tests`. Passam aqui, e levam
  uns 2 minutos.
- Usado de **várias máquinas Windows**, por uma pessoa que **não é
  desenvolvedora**.
- Os cinco princípios do PRD continuam sendo o critério: (1) fato datado nunca
  é sobrescrito; (2) gate antes de score; (3) todo número é rastreável;
  (4) o "não escolhi" vale mais que o "escolhi"; (5) dado pessoal não mora em
  repositório versionado.

## O alvo desta rodada

### 1. O Apps Script que escreve a planilha

Código versionado em [`docs/integracao-google-sheets.md`](integracao-google-sheets.md)
(bloco `Code.gs`), implantado na conta conta-comercial como Web App.

**Três bugs já saíram desse mesmo arquivo. Todos corrigidos, e listo aqui para
você não gastar tempo redescobrindo — e para calibrar o tipo de coisa que
passou despercebida:**

| Versão | Bug | Como se manifestou |
|---|---|---|
| 1 → 2 | `DriveApp.getRoot()` não existe na API (é `getRootFolder()`) | `TypeError`, sincronização 100% quebrada |
| 2 → 3 | pasta procurada só na raiz do Drive | criou pasta duplicada, porque a certa é aninhada |
| 3 → 4 | campo `comp.colunas` do payload simplesmente ignorado | tabela sem cabeçalho: dava para ler preço e nota, mas **não qual coluna era qual produto** |

O terceiro é o que mais me incomoda, e é o padrão que eu quero que você cace:
**o script recebia o dado certo e jogava fora em silêncio.** Nada falhou, nada
logou erro, o comando respondeu `ok`. Só quem abriu a planilha viu.

Perguntas concretas:

- O `Code.gs` atual usa **tudo** o que o payload manda? Compare campo a campo
  com o que `sheets_export_payload()` produz em `scripts/central_compras.py`.
  Tem mais algum dado sendo descartado calado?
- `escreverVisaoGeral` monta a lista `campos` **cravada no script**. Se o
  Python passar a mandar um campo novo, ele entra na planilha ou é ignorado em
  silêncio, como aconteceu com `colunas`?
- O tratamento de `linha.tipo === 'estrela'` cobre os tipos que o Python
  realmente emite? O que acontece com um tipo novo — vira texto, vira vazio,
  ou quebra?
- `appendRow` linha a linha: com 8 projetos a execução leva ~47 s (foi por isso
  que o timeout do cliente subiu de 30 s para 120 s). Em quantos projetos isso
  estoura o limite de 6 minutos do Apps Script? Vale trocar por `setValues` em
  lote antes de chegar lá?
- `abaLimpa` usa `clear()` e refaz `setFrozenRows`. Aba que existia antes com
  mais colunas do que agora fica com resíduo?
- **Nome de aba**: `comp.projeto.replace(/[\[\]:*?\/\\]/g, '-').slice(0, 100)`.
  Isso cobre todos os caracteres que o Google recusa? E dois projetos com nome
  longo que só diferem depois do caractere 100 — colidem?
- O token é conferido com `dados.token !== TOKEN`, comparação simples. Para
  este caso (endpoint que só escreve planilha de compras pessoais) isso basta,
  ou você vê um risco concreto que justifique mudar?

### 2. A planilha publicada, aba por aba

`Central de Compras - Cotacoes e Comparacoes`, na conta conta-comercial, dentro de
`Meu Drive/10_JOSEMAR_PESSOAL/03_PROJETOS_ATIVOS/02_TECNOLOGIA_E_IA/Central de Compras`.

São 8 abas de projeto mais a `Visao Geral`. **Abra uma por uma.** Foi assim
que o terceiro bug apareceu, e a única razão de ele ter passado por três
agentes é que ninguém abriu.

- Alguma aba está com dado faltando, trocado de coluna, ou desalinhado em
  relação ao que está no repositório (`ranking.csv` e `cotacoes.csv` do projeto
  correspondente)?
- Os números batem com o repositório? O `ranking.csv` é a fonte; a planilha é
  espelho. Divergência aí é bug.
- A aba `Visao Geral` está legível e completa?
- Sobrou aba órfã de projeto que não existe mais, ou a `Página1` padrão?
- Formatação: número virou texto? Data virou número? Preço perdeu casa decimal?
- **Se estiver tudo certo, diga que está tudo certo.** É resultado válido.

### 3. Os documentos do repositório

Foram escritos ou reescritos hoje, depois de o problema acontecer, e nunca
foram lidos por ninguém de fora:

- `CLAUDE.md` e `AGENTS.md` (novos — o repositório não tinha instrução nenhuma
  para agente até hoje)
- `docs/infraestrutura-externa.md` (novo — inventário do que existe fora do Git)
- `docs/integracao-google-sheets.md` (reescrito)
- `STATUS.md` (doc de handoff entre máquinas)
- `README.md`

**O problema que esses documentos existem para resolver:** a URL e o token da
integração moram em `~/.central-compras/dados-privados/`, fora do Git. Em
outra máquina o arquivo não existe. Três agentes (Kimi, Antigravity e Claude),
em sessões separadas, concluíram daí que "a integração nunca foi ativada" e
recriaram planilha, script e endpoint do zero — enquanto havia um Web App
**ativo e público** desde 31/08. Chegou a ter dois endpoints abertos ao mesmo
tempo.

A correção estrutural foi dividir a configuração: a **URL** passou a ser
versionada em `config/integracao_sheets.yaml` (ela sozinha não dá acesso; quem
protege é o token) e só o **token** ficou local, gravado por
`configurar-sheets --token X`.

Então:

- Você, lendo esses documentos **sem conhecer esta conversa**, evitaria o erro?
  Ou cairia nele de novo? Seja literal: aponte a frase que salvaria e a que
  induziria ao erro.
- O roteiro de busca em `infraestrutura-externa.md` ("confira a lixeira do
  Drive; script container-bound some da listagem quando o arquivo dono está na
  lixeira") é suficiente para achar infraestrutura escondida, ou tem caso que
  ele não cobre?
- `CLAUDE.md` e `AGENTS.md` apontam para o mesmo conteúdo para não divergir.
  Funciona para você, que é Codex? Você lê `AGENTS.md` por convenção — o
  ponteiro é claro o bastante ou você passaria batido?
- Tem contradição entre os documentos? Algum diz uma coisa e outro diz o
  contrário?
- O que **falta** que só se percebe de fora?

## Regras

- **Reproduza antes de reportar.** Comando e saída real. Se não puder executar
  neste ambiente, **diga isso na primeira linha** e marque tudo como análise
  estática.
- **Não conserte.** Diagnóstico primeiro. Correção proposta, se houver, em diff
  separado no fim, marcada como proposta.
- **Não invente.** `[NÃO VERIFICADO: motivo]` em vez de completar com
  plausibilidade.
- **Não reproduza o token em lugar nenhum da sua resposta.** Ele está em texto
  puro na linha 1 do `Code.gs` e no `integracao_sheets.json` local. Se precisar
  falar dele, escreva "o token". Se encontrar o valor em algum arquivo
  versionado, isso é achado grave — reporte o **caminho e a linha**, nunca o
  valor.
- Os 270 testes passam aqui. Se falharem aí, isso já é achado.
- **Se não achar nada, diga isso.** "Abri as 9 abas, conferi contra o
  ranking.csv, está tudo consistente" é resposta útil.
- Ordene por **impacto na decisão de compra**, não por severidade técnica.
- Lembre quem usa: pessoa não desenvolvedora, várias máquinas Windows.

## Já sei, não gaste tempo

- O comando `sincronizar-planilha` responder `ok` não prova que a planilha
  ficou legível — prova só que o POST chegou. Já está escrito na doc.
- A planilha é **espelho descartável**. A verdade é o `cotacoes.csv` de cada
  projeto. Se ela for apagada, o script recria.
- Existe uma planilha antiga (`Central de Compras - Comparativo de Produtos`,
  de 31/08) na lixeira do Drive, com o Web App dela já arquivado e o
  compartilhamento público já fechado. É legado consciente, expira sozinha.
- O projeto `2026-servico-a` está inteiro com
  `categoria: generico`, e provavelmente duplica
  `2026-servico-b`. Já identificado, decisão de
  fundir é do dono. **Não é o alvo desta rodada** — mas se você vir consequência
  técnica disso na planilha, aí sim reporte.
- Nenhuma compra foi fechada ainda. O ciclo de veredito nunca rodou com dado
  real.

## Formato

```
## Veredito em uma linha

## O Apps Script
[o mais grave primeiro; com reprodução, ou "não consegui executar, é análise estática"]

## A planilha, aba por aba
[uma linha por aba, dizendo o que conferiu e o que achou; "consistente" é resposta]

## Os documentos
[a) você evitaria o erro lendo isso?  b) contradições  c) o que falta]

## O que não consegui verificar
```

Se a sua conclusão for "esse script vai quebrar de novo pelo mesmo motivo, e
os documentos não impedem", eu quero ler isso em letras grandes. É a resposta
mais valiosa que esta rodada pode produzir.
