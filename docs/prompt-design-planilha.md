# Prompt para o Codex — redesign visual da planilha

Copie tudo daqui para baixo e cole no Codex.

O plano de design abaixo foi montado com uma metodologia de visualização de
dados e **as cores foram validadas por script** (contraste, banda de
luminosidade, separação para daltonismo) contra a superfície branca do Google
Sheets. Não troque os valores hex "no olho": eles passaram em teste e a
substituição por outro tom quebra o que foi verificado.

---

Você vai redesenhar a planilha `Central de Compras - Cotacoes e Comparacoes`
inteiramente por código, no Apps Script que a gera.

## Contexto

A planilha é o **espelho publicado** da Central de Compras — um sistema de
decisão de compra pessoal. Ela não é a fonte da verdade (isso é o
`cotacoes.csv` de cada projeto); ela é onde o dono **olha** para decidir.

- Repositório: `C:\projetos\central-compras`, GitHub privado `josemardp/central-compras`.
- O script que a escreve está versionado em
  [`docs/integracao-google-sheets.md`](integracao-google-sheets.md), bloco `Code.gs`,
  e implantado como Web App na conta **conta-comercial**.
- O payload vem de `sheets_export_payload()` em `scripts/central_compras.py`.
- Hoje são 9 abas: `Visao Geral` + uma por projeto de compra.
- Quem lê **não é desenvolvedor**, abre no desktop e no celular, e usa a
  planilha para decidir compras de R$ 70 a R$ 150.000.

**O problema:** a planilha hoje é dado cru despejado em célula. Sem hierarquia,
sem cor, sem gráfico, sem destaque. Tudo tem o mesmo peso visual, então nada
tem peso nenhum. O objetivo é que, ao abrir uma aba, o dono veja **em dois
segundos** quem está ganhando e por quê.

## Restrição de ordem (leia antes de começar)

Se você ainda não aplicou as correções de bug da auditoria anterior (datas
falsas no consumo, `Página1` órfã, `gerado_em` ignorado), **faça aquilo
primeiro e em commit separado**. Este trabalho é visual e vai mexer nas mesmas
funções; misturar os dois deixa impossível dizer o que quebrou o quê.

**Você provavelmente não conseguirá implantar.** O deploy exige navegador
logado na conta conta-comercial com verificação em duas etapas no celular do dono.
Altere o arquivo versionado, deixe claro no fim que o deploy está pendente, e
avise. Não conclua que aplicou.

## As regras que não se negociam

Estas vêm da metodologia e cada uma existe porque o contrário já deu errado em
dashboards reais. **Se o seu resultado bater com um destes, está errado:**

1. **Nunca colorir barras por posição no ranking.** Projetos e produtos são
   categorias nominais. Colorir "mais escuro = maior" duplica o comprimento da
   barra na cor e queima o único canal livre. Uma série, uma cor.
2. **Nunca dois eixos Y no mesmo gráfico.** Duas medidas de escala diferente
   viram dois gráficos.
3. **Nada de pizza nem rosca.** Nem para "part-to-whole".
4. **Nada de arco-íris para magnitude.** Escala de magnitude é uma cor só,
   clara para escura.
5. **Cor de status nunca aparece sozinha.** Sempre acompanhada de ícone **e**
   rótulo em texto. Testei a paleta de status como se fosse categórica e ela
   reprova (vermelho e verde ficam a ΔE 4.1 sob daltonismo deutan) — é
   exatamente por isso que a cor não pode carregar o significado sozinha.
6. **Texto nunca usa a cor da série.** Valores e rótulos ficam em tinta
   primária/secundária; quem carrega identidade é a marca colorida ao lado.
7. **Não põe número em cima de todo ponto do gráfico.** Rotule o extremo, o
   líder, o que importa. O resto fica no eixo e na tabela.
8. **Nada de linha de grade tracejada** nem borda desenhada em volta das
   marcas. Grade é fio fino sólido, um tom acima da superfície.
9. **Se a história é "este venceu", isso é destaque, não paleta categórica.**
   Uma cor no vencedor, cinza recuado no resto. Este é o caso da maioria das
   abas desta planilha.

## Paleta — valores validados, use exatamente estes

Validados contra a superfície `#ffffff` do Sheets.

### Tinta e superfície

| Papel | Hex |
|---|---|
| Superfície | `#ffffff` |
| Faixa de cabeçalho | `#f9f9f7` |
| Tinta primária (título, valor que importa) | `#0b0b0b` |
| Tinta secundária (rótulo de linha) | `#52514e` |
| Tinta apagada (eixo, nota de rodapé, unidade) | `#898781` |
| Fio de grade / divisória | `#e1e0d9` |
| Linha de base / borda de bloco | `#c3c2b7` |

### Destaque (o uso principal desta planilha)

| Papel | Hex |
|---|---|
| Líder / vencedor | `#2a78d6` |
| Fundo suave do líder | `#eaf2fd` |
| Demais candidatos (recuado) | `#898781` |

### Categórica — só quando os candidatos são o assunto, no máximo 3

| Slot | Hex |
|---|---|
| 1 | `#2a78d6` |
| 2 | `#eb6834` |
| 3 | `#1baf7a` |

Nesta ordem, sempre. Não cicle, não gere um quarto. Passou com pior par ΔE 9.2
sob deutan e 24.0 em visão normal. **Com 4 ou mais candidatos**, use gráfico de
barras com uma cor só (`#2a78d6`) e deixe a identidade para o rótulo do eixo.

O verde `#1baf7a` tem contraste 2.82:1 contra o branco, abaixo de 3:1. Numa
planilha isso é aceitável **porque o valor numérico está sempre visível na
célula ao lado** — a tabela é o alívio. Não use esse tom para texto.

### Magnitude (score, confiança) — uma cor, 4 degraus

| Faixa | Hex |
|---|---|
| baixo | `#86b6ef` |
| médio | `#3987e5` |
| alto | `#1c5cab` |
| máximo | `#0d366b` |

São 4 degraus de propósito: testei com 6 e reprovou — os degraus ficavam a
ΔL 0.047, indistinguíveis. Com 4, todos os intervalos passam de 0.06.

### Status — sempre com ícone e rótulo

| Estado | Hex | Ícone | Rótulo |
|---|---|---|---|
| decidido / comprado | `#0ca30c` | ● | "Decidido" |
| pesquisando | `#fab219` | ◐ | "Pesquisando" |
| aguardando preço | `#ec835a` | ◔ | "Aguardando preço" |
| cotação vencida / bloqueado | `#d03b3b` | ▲ | "Vencida" |

Use como **cor de texto ou de um marcador pequeno**, não como fundo chapado da
linha inteira. Fundo saturado em bloco grande fica pesado e infantil.

## Tipografia — uma família só

Uma resposta franca a "falta variação de fontes": **variar família é o erro**.
Duas ou três tipografias diferentes numa planilha lêem como convite de
casamento, não como instrumento de decisão. A hierarquia vem de **peso,
tamanho, cor e espaço** — e fica mais forte assim, não mais fraca.

Família única: **Inter** (se indisponível, `Roboto`; nunca serifada, nunca
decorativa).

| Papel | Tamanho | Peso | Cor |
|---|---|---|---|
| Número-herói do topo | 24 | bold | `#0b0b0b` |
| Título de bloco | 13 | bold | `#0b0b0b` |
| Cabeçalho de coluna | 10 | bold | `#52514e`, MAIÚSCULAS, espaçado |
| Rótulo de linha (coluna A) | 10 | bold | `#52514e` |
| Valor comum | 10 | normal | `#0b0b0b` |
| Valor do líder | 10 | bold | `#0b0b0b` |
| Unidade, nota, fonte do dado | 9 | normal | `#898781` |

**Números em coluna usam fonte de largura fixa** (`Roboto Mono`, 10) para
alinharem casa a casa. O número-herói **não** — em tamanho grande, largura fixa
faz `121` parecer frouxo.

Alinhamento: texto à esquerda, número à direita, cabeçalho acompanha a coluna
que titula. Nunca centralize número.

## Layout — aba por aba

### Aba `Visao Geral`

**Bloco 1, linhas 1-3: faixa de indicadores.** Quatro números grandes, lado a
lado, cada um com rótulo pequeno em cima e o valor 24px embaixo:

- Projetos ativos
- Decisões fechadas
- Aguardando confirmação de preço
- Cotações vencidas (se > 0, valor em `#d03b3b` com o ▲; se 0, tinta primária)

Isso substitui um gráfico: quatro números soltos não viram barra, viram
indicador.

**Bloco 2: a tabela dos projetos.** Colunas: Projeto · Categoria · Estado ·
Líder · Score · Confiança · Cotações · Decidido em.

- Linha 1 congelada, coluna A congelada.
- Cabeçalho com a faixa `#f9f9f7`, texto 10 bold maiúsculo `#52514e`.
- Linhas alternadas: branco e `#f9f9f7`. Sem borda entre linhas — a alternância
  já separa.
- **Estado**: ícone + rótulo, cor de status no texto.
- **Score**: número à direita **mais** uma barra na célula seguinte, via
  `SPARKLINE` tipo `bar`, `max` 100, cor `#2a78d6`.
- **Confiança**: é uma razão contra um limite, então é medidor, não barra
  colorida por valor. Barra `SPARKLINE` na cor do degrau correspondente
  (`#86b6ef` até 60%, `#3987e5` até 80%, `#1c5cab` até 95%, `#0d366b` acima).
- Nome do projeto vira **link para a aba dele** (`HYPERLINK` com `#gid=`).

**Bloco 3: um gráfico de barras horizontais** com o score dos projetos,
ordenado do maior para o menor. **Todas as barras em `#2a78d6`** — projetos são
categorias nominais, colorir por posição é o erro nº 1 da lista acima. Sem
linhas de grade verticais pesadas; eixo em `#898781`.

**Rodapé**: "Espelho gerado em {gerado_em} · a fonte é o cotacoes.csv de cada
projeto" em 9px `#898781`. Use o campo `gerado_em` do payload, que hoje é
descartado.

### Abas de projeto

A história aqui é **quem está ganhando e por quê**. Isso é destaque, não
paleta categórica.

**Linha 1 — cabeçalho de produto** (já existe, melhore): nome de cada
candidato, 13px bold. A coluna do líder ganha fundo `#eaf2fd` e texto
`#0b0b0b`; as demais ficam com texto `#52514e`. Linha congelada.

**Linha 2 — faixa de veredito**, nova: uma frase por coluna. Para o líder,
"Líder · score 71,9". Para os outros, o motivo de estarem atrás, curto.
Se a diferença entre o primeiro e o segundo for **≤ 3 pontos**, escreva
"Empate técnico" nos dois, em `#fab219` com ◐ — porque nesse caso o número não
decidiu, e a planilha não pode fingir que decidiu.

**Linhas de dados**: rótulo em coluna A (10 bold `#52514e`), valores
alinhados por tipo. Preço em negrito. A coluna do líder inteira com fundo
`#eaf2fd` bem claro — é o destaque que faz o olho pousar sem gritar.

**Separadores de seção** (PREÇOS, ATRIBUTOS, SCORE): linha de faixa `#f9f9f7`
com o título em 10 bold maiúsculo, sem borda.

**Gráfico 1 — barras do score total por candidato.** Líder em `#2a78d6`,
demais em `#898781`. Este é o destaque: uma cor no que importa, cinza no resto.

**Gráfico 2 — os eixos do score**, que é o dado mais rico e hoje não aparece
em lugar nenhum: qualidade, valor, risco, aderência, conveniência, de 0 a 1.
Barras agrupadas, um grupo por eixo. **Com até 3 candidatos**, use os slots
categóricos 1-2-3. **Com 4 ou mais, faça pequenos múltiplos**: um mini-gráfico
por candidato, todos na mesma escala, em vez de amontoar cores.
Nada de radar: área de polígono engana sobre magnitude.

Se um eixo não tiver dado, ele **não vira zero** — fica fora do gráfico, com
nota "sem dado" abaixo. Zerar seria mentir sobre o candidato.

**Legenda** sempre presente quando houver 2 ou mais séries. Rotule direto só o
líder.

## Interação — o que dá para fazer no Sheets

Uma planilha não tem hover customizado, mas tem mais recurso do que se usa:

- **Congelar** linha 1 e coluna A em todas as abas (`setFrozenRows`, `setFrozenColumns`).
- **Filtro nativo** na tabela da Visão Geral (`sheet.getRange(...).createFilter()`),
  para filtrar por estado ou categoria. Um filtro só, acima de tudo que ele
  controla.
- **Links entre abas**: nome do projeto na Visão Geral leva à aba dele; um
  "← Visão Geral" no topo de cada aba de projeto volta.
- **Nota em célula** (`setNote`) explicando como o score foi montado, na célula
  do score. É o mais perto de tooltip que existe aqui, e o valor continua
  visível sem ela.
- **Formatação condicional** para as faixas de score e para destacar cotação
  vencida.
- **Proteger as abas** (`protect().setWarningOnly(true)`) com o aviso "espelho
  gerado por script; edite o repositório, não aqui". Evita que alguém corrija
  na planilha e perca na próxima sincronização.
- **Largura de coluna** calculada (`setColumnWidth`), não automática: coluna A
  mais larga para os rótulos, colunas de candidato iguais entre si.
- **Quebra de texto** (`setWrapStrategy`) nas colunas de texto longo — hoje
  nome de projeto e líder ficam cortados.

## Detalhes de implementação que vão te morder

- **Locale pt-BR**: em fórmula o separador de argumentos é `;` e o de array é
  `\`. Uma `SPARKLINE` escrita com `,` não vai funcionar. Prefira
  `setFormula` com a sintaxe correta do locale, ou monte os gráficos por
  `EmbeddedChartBuilder`, que não depende disso.
- **Desempenho**: hoje o script escreve linha a linha com `appendRow` e leva
  ~47s com 8 projetos. Se você acrescentar formatação célula a célula, isso
  explode e bate no limite de 6 minutos do Apps Script. **Escreva em lote**
  (`setValues`, `setBackgrounds`, `setFontColors`, `setFontWeights` sobre um
  `Range` inteiro) — a formatação em lote é obrigatória aqui, não opcional.
- **`clear()` apaga formatação junto**, o que é o que queremos entre
  sincronizações, mas significa que **toda** a formatação precisa ser reaplicada
  a cada rodada. Não dá para formatar à mão uma vez.
- **Gráficos precisam ser removidos antes de recriados**, senão duplicam a cada
  sincronização: `sheet.getCharts().forEach(c => sheet.removeChart(c))`.
- **Não coloque o número em cada barra** do gráfico; a tabela acima já tem.
- O dono abre no celular. Teste se a faixa de indicadores não quebra em tela
  estreita; prefira 4 colunas curtas a 1 linha longa.

## Critérios de aceite

1. Abrindo qualquer aba de projeto, dá para dizer **em dois segundos** quem é o
   líder, sem ler número nenhum.
2. Nenhum estado é comunicado só por cor — todos têm ícone e rótulo.
3. Nenhuma barra é colorida por posição no ranking.
4. Empate técnico (≤ 3 pontos) está escrito, não deduzido.
5. Eixo sem dado aparece como "sem dado", nunca como zero.
6. A sincronização inteira continua abaixo de 2 minutos com 8 projetos.
7. Rodar duas vezes seguidas produz o mesmo resultado, sem gráfico duplicado e
   sem formatação acumulada.
8. Os 270 testes continuam passando (`python -m unittest discover -s tests`;
   o resumo sai em **stderr**, cuidado ao usar pipe, e leva 2-3 minutos).
9. `python scripts/central_compras.py checar-segredos --strict` continua limpo.

## Formato da entrega

1. O diff do `Code.gs` no arquivo versionado.
2. Se mexer no Python (por exemplo para expor `gerado_em` ou os eixos do score
   no payload), diff separado, e diga **explicitamente** se o script novo
   funciona com o payload antigo — porque o deploy e o commit não acontecem no
   mesmo instante.
3. Uma lista do que você **não** conseguiu implementar e por quê.
4. O aviso de deploy pendente, se for o caso.

Não invente valor de cor. Se precisar de um tom que não está na tabela acima,
diga qual papel ele cumpre e por que os existentes não servem — em vez de
escolher um.
