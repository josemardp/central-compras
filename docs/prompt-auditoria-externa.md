# Prompt para auditoria externa (Codex) — quinta rodada

Copie tudo daqui para baixo e cole no Codex, com o repositório aberto.
(As rodadas anteriores estão no histórico do Git:
`git log -- docs/prompt-auditoria-externa.md`.)

---

Esta rodada tem um alvo estreito e um motivo concreto: **a integração com o
Google Sheets já falhou no contrato, no deploy, na coerção de tipos e na
renderização. Várias falhas devolveram HTTP 200 ou execução “Concluído” e só
foram percebidas quando o dono abriu a planilha.**

Quero que você olhe justamente isso: a planilha publicada, o script que a
escreve, e os documentos que deviam ter impedido a confusão toda.

## O repositório

`C:\projetos\central-compras` — GitHub privado `josemardp/central-compras`, `main`.

Memória permanente de decisão de compra de uma pessoa física. Preço envelhece
em 48 horas; o par *decisão + veredito* ("por que escolhi X" e, seis meses
depois, "deu certo?") vale para sempre.

- Python 3, dependência única `PyYAML`. `scripts/central_compras.py`, arquivo
  único, ~30 subcomandos.
- **284 testes**: `python -m unittest discover -s tests`. Passam aqui, e levam
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

**Falhas já corrigidas, listadas para você não gastar tempo redescobrindo e
para calibrar o tipo de coisa que passou despercebida:**

| Versão | Bug | Como se manifestou |
|---|---|---|
| 1 → 2 | `DriveApp.getRoot()` não existe na API (é `getRootFolder()`) | `TypeError`, sincronização 100% quebrada |
| 2 → 3 | pasta procurada só na raiz do Drive | criou pasta duplicada, porque a certa é aninhada |
| 3 → 4 | campo `comp.colunas` do payload simplesmente ignorado | tabela sem cabeçalho: dava para ler preço e nota, mas **não qual coluna era qual produto** |
| 4 → 5 | emissor e receptor evoluíam sem compatibilidade nos dois sentidos | a ordem de commit/deploy podia quebrar a `Visao Geral` |
| 5 | implantação publicada por uma conta editora | o Web App perdeu acesso à pasta da conta proprietária |
| 5 → 7 | congelamento da coluna A atravessava células mescladas | erro em tempo de execução |
| 7 → 8 | gráficos liam intervalos separados e transpostos | ranking vazio e eixos com rótulos misturados, sem falha no POST |

O padrão que eu quero que você cace é: **algo pode estar errado sem o pipeline
parecer quebrado.** Não confie apenas no status HTTP, na execução “Concluído”,
no JSON nem na existência do gráfico. Verifique dado, tipo, fonte e aparência.

Perguntas concretas:

- Compare campo a campo `sheets_export_payload()` e o `Code.gs`. Campo novo
  continua aditivo, com fallback antigo e aviso para descarte desconhecido?
- Force payload antigo, payload novo, campo desconhecido, tipo desconhecido e
  comparativo ausente. O comportamento observado bate com o contrato?
- Force exceção dentro do `doPost`. O cliente mostra `detalhe`, mesmo quando o
  Apps Script responde HTTP 200?
- Confirme que preços, scores, notas e medidas chegam como números, enquanto
  códigos, datas textuais e atributos textuais não sofrem coerção.
- Rode a sincronização duas vezes. A segunda mantém exatamente as mesmas abas,
  filtros, proteções e quantidades de gráficos?
- Teste nomes de projeto inválidos, vazios, longos e colidentes. Nenhuma aba é
  sobrescrita ou reaproveitada para o projeto errado?
- Estime o crescimento com mais projetos e candidatos. `setValues` em lote e
  timeout de 120 s ainda deixam margem para o limite do Apps Script?
- Faça revisão de ameaça do endpoint e do token sem reproduzir o segredo.
  Reporte apenas risco concreto compatível com o uso pessoal desta integração.

### 2. A planilha publicada, aba por aba

`Central de Compras - Cotacoes e Comparacoes`, na conta conta-comercial, dentro de
`Meu Drive/10_JOSEMAR_PESSOAL/03_PROJETOS_ATIVOS/02_TECNOLOGIA_E_IA/Central de Compras`.

São 8 abas de projeto mais a `Visao Geral`. **Abra uma por uma.** Foi assim
que os bugs silenciosos apareceram; eles atravessaram mais de uma revisão
porque ninguém tinha conferido o resultado final.

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

Foram escritos ou reescritos depois dos incidentes e precisam ser avaliados
como um conjunto, sem depender do contexto desta conversa:

- `CLAUDE.md` e `AGENTS.md` (entrada obrigatória para agentes)
- `docs/infraestrutura-externa.md` (inventário do que existe fora do Git)
- `docs/integracao-google-sheets.md` (código e operação)
- `docs/aprendizados-google-sheets.md` (falhas conhecidas e checklist)
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
- Os 284 testes passam aqui. Se falharem aí, isso já é achado. O resumo do
  `unittest` sai em `stderr`; não use pipe que esconda o código de saída.
- **Se não achar nada, diga isso.** "Abri as 9 abas, conferi contra o
  ranking.csv, está tudo consistente" é resposta útil.
- Ordene por **impacto na decisão de compra**, não por severidade técnica.
- Lembre quem usa: pessoa não desenvolvedora, várias máquinas Windows.

## Já sei, não gaste tempo

- O comando `sincronizar-planilha` responder `ok` não prova que a planilha
  ficou legível. HTTP 200 e “Concluído” também não: `doPost` captura exceções e
  pode devolver `ok: false`. Já está escrito na doc.
- A implantação ativa é a **Versão 8**, publicada pela conta proprietária
  `conta-comercial`, no mesmo endpoint. As versões 5 a 7 foram intermediárias.
- O checklist consolidado está em
  [`aprendizados-google-sheets.md`](aprendizados-google-sheets.md).
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
