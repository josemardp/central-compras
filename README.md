# Central de Compras

Sistema local para transformar cada compra em um processo decisorio rastreavel.

A ideia principal e simples: preco envelhece rapido, mas a memoria da decisao continua valendo. Para cada compra, o repositorio guarda o que voce queria comprar, quais modelos foram considerados, quais cotacoes foram vistas, quais criterios eliminaram candidatos e por que a decisao final fez sentido naquele momento.

Perdido sobre como usar na pratica? Comece pelo guia visual interativo:
[`docs/guia-pratico-visual.html`](docs/guia-pratico-visual.html).
A versao simples em Markdown continua em
[`docs/guia-pratico-visual.md`](docs/guia-pratico-visual.md).

> **Agente de IA ou maquina nova?** Leia [`CLAUDE.md`](CLAUDE.md) antes de
> mexer. E se for criar planilha, pasta no Drive, Apps Script ou integracao,
> confira antes o inventario em
> [`docs/infraestrutura-externa.md`](docs/infraestrutura-externa.md): a
> configuracao local fica fora do Git e nao sincroniza entre maquinas, entao
> "nao existe aqui" nao quer dizer "nao existe la fora".

## Fluxo de uma compra

Cada compra vira um projeto em `projetos/`.

1. `briefing.md` - necessidade, faixa de valor, preco teto, criterios obrigatorios.
2. `processo.md` - checklist vivo das etapas e registro do que ja foi decidido.
3. `01-definir-modelo.md` - conversa com IA para transformar "quero um fone" em requisitos tecnicos.
4. `cotacoes.csv` - observacoes datadas e append-only.
5. `ranking.md` - gates, score aberto e motivos de corte.
6. `ranking.csv` - saida derivada e sobrescrevivel para auditoria do score.
7. `validacao.md` - pendencias de schema, cotacao e alertas.
8. `decisao.md` - escolhido, motivo, segundo colocado e por que perdeu.
9. `vereditos/` - D+30 e D+180 para fechar o aprendizado.

Cada candidato tambem tem um `produto.yaml` em `produtos/<categoria>/<id>/`.
Use o campo opcional `proveniencia` para guardar fonte, URL e data de consulta
de especificacoes pesquisadas. Evite comentarios YAML para esse dado: comandos
como `descartar` regravam o arquivo e preservam campos, nao comentarios.

## Comandos

```powershell
python scripts/central_compras.py init
python scripts/central_compras.py novo-projeto "fone bluetooth para chamadas" --categoria fone --valor-estimado 400 --preco-teto 600
python scripts/central_compras.py novo-produto projetos/2026-fone-bluetooth-para-chamadas "QCY H3" --marca QCY --categoria fone --atributo tipo=headphone --atributo cancelamento_ruido=anc
python scripts/central_compras.py anotar projetos/2026-fone-bluetooth-para-chamadas --etapa modelo --decisao "Pesquisar headphone over-ear com bom microfone" --porque "A prioridade e chamada longa, nao uso esportivo."
python scripts/central_compras.py cotar projetos/2026-fone-bluetooth-para-chamadas --produto-id qcy-h3 --loja Amazon --vendedor "Loja oficial" --vendedor-tipo oficial --preco 299 --frete 0 --nota 4.6 --avaliacoes 1200 --garantia-meses 12 --garantia-tipo nacional --fonte manual --link "https://..."
python scripts/central_compras.py promover-cotacao projetos/2026-fone-bluetooth-para-chamadas --produto-id qcy-h3 --preco 289 --frete 10 --garantia-meses 12 --garantia-tipo nacional
python scripts/central_compras.py ranking projetos/2026-fone-bluetooth-para-chamadas
python scripts/central_compras.py configurar-sheets --token SEU_TOKEN   # so na primeira vez em cada maquina
python scripts/central_compras.py sincronizar-planilha
python scripts/central_compras.py validar projetos/2026-fone-bluetooth-para-chamadas
python scripts/central_compras.py registrar-marca QCY --categoria fone --projeto projetos/2026-fone-bluetooth-para-chamadas --nota 8 --compraria-de-novo talvez --resumo "Boa relacao custo-beneficio; falta veredito proprio."
python scripts/central_compras.py registrar-loja Amazon --categoria fone --projeto projetos/2026-fone-bluetooth-para-chamadas --nota 9 --compraria-de-novo sim --resumo "Entrega e devolucao reduzem risco."
python scripts/central_compras.py registrar-licao "Fone para chamadas precisa de relato especifico de microfone." --categoria fone
python scripts/central_compras.py reaproveitamento --categoria fone
python scripts/central_compras.py prompt-ia projetos/2026-fone-bluetooth-para-chamadas --etapa modelo
python scripts/central_compras.py descartar --produto-id anker-q30 --projeto projetos/2026-fone-bluetooth-para-chamadas --porque "Melhor ANC, mas passou do preco teto."
python scripts/central_compras.py aguardar-preco --produto-id qcy-h3 --projeto projetos/2026-fone-bluetooth-para-chamadas --preco-alvo 260 --preco-teto 330 --porque "Produto aprovado, mas acima do alvo."
python scripts/central_compras.py listar-aguardando-preco --categoria fone
python scripts/central_compras.py decidir projetos/2026-fone-bluetooth-para-chamadas --produto-id qcy-h3 --porque "Melhor equilibrio entre microfone, garantia nacional e preco confirmado." --perdedores "anker-q30: melhor ANC, mas passou do preco teto" --comprado
python scripts/central_compras.py preencher-veredito vereditos/2026-09-25-projeto-produto.md --fase d30 --nota-arrependimento 1 --compraria-de-novo sim --resumo "Chegou certo e resolveu." --licao "Compraria de novo."
python scripts/central_compras.py aprender-veredito vereditos/2026-09-25-projeto-produto.md --marca QCY --loja Amazon --categoria fone
python scripts/central_compras.py dashboard
python scripts/central_compras.py historico projetos/2026-fone-bluetooth-para-chamadas
python scripts/central_compras.py regenerar
python scripts/central_compras.py migrar-cotacoes
python scripts/central_compras.py dados-privados
python scripts/central_compras.py resumo projetos/2026-fone-bluetooth-para-chamadas
python scripts/central_compras.py status projetos/2026-fone-bluetooth-para-chamadas
```

Para compra cara, como carro, informe os campos de TCO:

```powershell
python scripts/central_compras.py cotar projetos/2026-comprar-carro --produto-id byd-dolphin-mini --loja "Concessionaria" --vendedor "Loja fisica" --vendedor-tipo fisica --preco 150000 --nota 4.7 --avaliacoes 1000 --garantia-meses 36 --garantia-tipo nacional --fonte manual --custo-operacional-mensal 300 --valor-revenda-estimado 85000 --link "https://..."
```

Se a categoria tiver `tco_meses` em `config/categorias.yaml`, o ranking usa `tco_total` no eixo valor.

## Como o score funciona

O score vai de 0 a 100 e e sempre exibido aberto, nos cinco eixos do PRD.

**Atencao ao que o score nao e.** `qualidade`, `risco` e `conveniencia` sao
absolutos: a mesma cotacao da o mesmo numero em qualquer projeto. `valor` e
`aderencia` nao sao. `valor` e a razao contra o mais barato do conjunto, entao
entrar um candidato barato rebaixa os outros sem que nada neles tenha mudado.
Isso e proposital (valor so existe em comparacao), mas significa que **o score
total nao e comparavel entre projetos diferentes** - so dentro do mesmo.

| Eixo | Peso | Como e calculado |
|---|---|---|
| qualidade | 0,30 | `nota_ajustada` mapeada de 4,0 (0,00) a 4,8 (1,00) |
| valor | 0,25 | razao `menor_custo / custo`. Custar o dobro vale 0,50 |
| risco | 0,20 | vendedor, tipo e prazo de garantia, loja preferida, menos penalidade por alerta |
| aderencia | 0,15 | percentual de requisitos do briefing atendidos |
| conveniencia | 0,10 | prazo de frete, de 2 dias (1,00) a 30 dias (0,00) |

Os limites ficam em `config/preferencias.yaml`, em `escala:`. `lojas_preferidas`
entra no eixo risco: loja da sua lista pesa menos risco que loja desconhecida.

Quando falta dado num eixo, ele **fica fora da conta** e os pesos restantes sao
renormalizados. O score passa a medir so o que se sabe, e `confianca` diz quanto
do peso total esta apoiado em dado real.

Isso corrige um incentivo perverso: com o eixo ausente valendo 0,50 neutro,
"nao informei o prazo" valia 5 pontos a mais que "o prazo e pessimo e eu sei
disso". O score premiava o silencio.

Score 80 com confianca 60% **nao e comparavel** com score 80 com confianca 100%.
A confianca aparece no `ranking.md`, no `ranking.csv`, na memoria de calculo e
no dashboard.

A criticidade ja esta embutida: o peso do eixo **e** a criticidade dele. Faltar
`qualidade` (0,30) derruba a confianca tres vezes mais que faltar `conveniencia`
(0,10), sem precisar de uma segunda tabela de numeros.

| Falta | Confianca | Compra ate R$ 20 mil | Acima de R$ 20 mil |
|---|---:|---|---|
| so conveniencia | 90% | passa | barra |
| so aderencia | 85% | barra (eixo obrigatorio) | barra |
| aderencia + conveniencia | 75% | barra | barra |
| qualidade | 70% | barra | barra |

Os minimos ficam em `confianca_minima_para_decidir`. Compra cara exige mais.

Limite alto sozinho nao resolve: omitir um eixo ruim continuava rendendo score
maior que informar um valor ruim. Por isso `valor` e `aderencia` sao
**obrigatorios** numa decisao final (`eixos_obrigatorios_para_decidir`) - sem
eles a comparacao simplesmente nao existe, qualquer que seja a confianca.

`nota_ajustada` e recalculada na hora do ranking a partir de `nota` e
`n_avaliacoes`, nunca lida congelada do CSV: se voce mudar os pesos da nota
bayesiana, o gate e o score acompanham.

## Auditar um score

```powershell
python scripts/central_compras.py auditar projetos/<projeto> --produto-id <id>
```

Gera `memoria-calculo.md` com a conta inteira: nota bayesiana, cada parcela do
risco com o que foi lido da cotacao, e a soma final eixo por eixo. E o principio
3 do PRD entregue de verdade: da para refazer o numero na calculadora.

Os pesos internos do risco ficam em `preferencias.yaml`, em `escala.risco`.
Antes eles viviam cravados no codigo, entao `risco 0,71` era um numero que voce
nao tinha como conferir.

## Frescor da cotacao

Preco envelhece. Cotacao `web` vale 14 dias e `manual` vale 7 (`frescor:` em
`preferencias.yaml`). Passou disso:

- `validar` e `status` avisam;
- `ranking.md` marca a linha como vencida;
- `decidir` **recusa** fechar, a menos que voce use `--permitir-vencida`.

A data e validada na entrada: `--data ontem` e recusado. Sem data ISO, a cotacao
escaparia calada de toda guarda de frescor e da deteccao de preco ancora.

## Travas do `decidir`

Fechar uma decisao e o unico ato irreversivel aqui. Ele recusa quando:

| Situacao | Escape |
|---|---|
| cotacao nao e `fonte=manual` | `--permitir-web` |
| cotacao passou da validade | `--permitir-vencida` |
| produto em `aguardando_preco` acima do alvo | `--permitir-aguardando` |
| falta o motivo da derrota de algum candidato | `--perdedores` ou `--sem-perdedores` |

Nenhuma delas bloqueia sozinha: todas tem escape nomeado. A trava existe para
voce dizer "sim, e de proposito", nao para o sistema decidir por voce.

## Regra de parada

Vem da faixa de valor do projeto (secao 7.5 do PRD) e e escrita no `briefing.md`
na criacao. `status` e `validar` comparam a pesquisa real contra o orcamento:
candidatos demais e cotacoes de menos por candidato viram aviso. A regra existe
para proteger voce de gastar seis horas para economizar R$ 40.

## Qual cotacao representa o produto

O ranking usa uma cotacao por produto, escolhida assim:

1. a **manual mais recente dentro da validade** (foi conferida por voce);
2. se nao houver, a **observacao mais recente dentro da validade**, ainda que seja `web`;
3. se tudo estiver vencido, a manual mais nova, e o ranking marca como vencida.

O passo 2 existe porque preferir a manual cegamente fazia um preco de dois anos
atras rankear no lugar do de hoje.

## Historico de preco

```powershell
python scripts/central_compras.py historico projetos/<projeto>
```

Mostra, por produto, a serie de custo com minimo, mediana, maximo e variacao. E
essa serie que desmascara preco ancora: desconto so e desconto contra o seu
proprio historico. Com uma unica observacao, o relatorio diz isso na cara.

## Painel local: a grade no navegador

```powershell
python scripts/central_compras.py painel
```

Sobe um servidor em `127.0.0.1:8800` e abre a grade editavel: ranking com score
aberto, confianca, avisos e um formulario de nova cotacao que **grava direto no
repositorio**.

No VS Code, `Ctrl+Shift+P` > `Simple Browser: Show` > cole a URL. A grade fica
ao lado do chat, na mesma janela.

O painel **nao e porta dos fundos**: toda gravacao passa pelos mesmos caminhos do
CLI, com a mesma trava por projeto, a mesma validacao de entrada e o mesmo
append-only. `NaN` e recusado ali igual e recusado no terminal. Editar cotacao
antiga nao existe no painel de proposito: preco novo e linha nova.

Ele so escuta em `127.0.0.1` — escreve no repo, entao nao pode aceitar conexao
de fora.

## Artifact: consultar do celular

```powershell
python scripts/central_compras.py artifact
```

Gera `dashboard/artifact.html`, pagina unica e autossuficiente, boa de ler no
celular. **So leitura**, e a propria pagina diz isso: cotar e decidir e no painel
local, onde o repositorio e a verdade.

E uma foto tirada quando voce gera. Se cotar depois e nao regerar, ela mostra o
estado anterior — nao e defeito, e o que uma foto e.

## Dashboard local

Gere a visao HTML da Central:

```powershell
python scripts/central_compras.py dashboard
```

Abra `dashboard/index.html` no navegador para ver projetos, itens aguardando preco, ranking por processo, marcas, lojas, licoes, arrependimento, aderencia ao gate e tempo ate decisao.

## Conflito de merge entre maquinas

`ranking.md`, `ranking.csv`, `validacao.md`, `historico.md`, `memoria-calculo.md`
e `dashboard/` sao derivados, mas ficam versionados de proposito: o `ranking.md`
ao lado do `decisao.md` e a evidencia de por que voce decidiu naquele dia.

No ato da decisao, o motor recalcula o ranking e congela `ranking.md`,
`ranking.csv` e a cotacao usada em `snapshots/<instante>-<produto>/`. O
`decisao.md` registra o caminho e o SHA-256 da cotacao. Uma cotacao nova pode
mudar os derivados atuais, mas nunca essa evidencia; `regenerar` ignora
`snapshots/`.

Se der conflito num derivado, **nao resolva a mao**. Fique com qualquer lado e rode:

```powershell
python scripts/central_compras.py regenerar
```

Conflito nas fontes (`cotacoes.csv`, `produto.yaml`, `briefing.md`) e outra
historia: ai o conteudo importa e tem que ser resolvido de verdade. O
`cotacoes.csv` e append-only e uma linha por observacao, entao o merge textual
do Git costuma dar certo; confira com `validar` depois.

## Seguranca antes do commit

```powershell
python scripts/central_compras.py checar-segredos --strict
```

Procura CPF formatado, numero de cartao (validado no Luhn, para nao acusar CEP,
EAN nem codigo de anuncio), CVV, senha e token na arvore versionada. Com
`--strict` ele retorna erro, entao serve de trava.

Para rodar sozinho antes de cada commit, crie `.git/hooks/pre-commit` com:

```sh
#!/bin/sh
python scripts/central_compras.py checar-segredos --strict || exit 1
```

Um exemplo legitimo em teste ou documentacao pode ser liberado escrevendo
`central-compras:exemplo-nao-e-segredo` na mesma linha. E excecao explicita,
nunca adivinhacao do varredor.

**Se um dado sensivel ja foi commitado, `git rm` nao resolve**: o historico
guarda. O procedimento e reescrever o historico com `git filter-repo` e trocar
o que vazou.

## Principios

- Cotacao nova e linha nova. Nao sobrescreva historico.
- Gate vem antes de score.
- Linha com `fonte=web` ajuda a pesquisar; linha com `fonte=manual` e que fecha compra.
- Produto descartado precisa de motivo.
- Decisao final cria veredito automaticamente para D+30 e D+180.
- `ranking.csv` e `validacao.md` sao derivados; `cotacoes.csv` preserva o historico.
- Acima de R$ 20.000, compare por TCO, nao por preco de etiqueta.
- Produto aprovado mas caro deve ir para `aguardando_preco`, com `preco_alvo` e motivo.
- Veredito preenchido vira aprendizado de marca, loja e categoria.
- Dado pessoal fica fora do repositorio, em `~/.central-compras/dados-privados/` (`dados-privados` cria a pasta).
- Cotacao vencida nao fecha compra. Preco de tres semanas atras nao e preco.
- Decisao sem o motivo da derrota do segundo colocado nao e aceita.
- Coluna que o schema nao conhece nunca e descartada do `cotacoes.csv`.
- Toda gravacao e atomica: Ctrl+C no meio nao deixa arquivo truncado.
- `preco_teto` do produto vence o do briefing quando for menor.
- Cotacao manual nao herda a suspeita da linha web: e observacao nova.
- `promover-cotacao` exige dizer o que foi conferido no site: `manual` sem
  conferencia seria carimbar preco velho de novo.
- Produto reprovado no gate nao fecha compra, so com excecao declarada.
- `NaN`, infinito, negativo e data no futuro sao recusados na entrada do CLI.
- Cotacao sem custo utilizavel e cortada no gate: produto sem preco nao e candidato.
- `historico` compara pela mesma base do ranking (TCO quando for o caso).
- A base de conhecimento tem trava propria: registrar licao em paralelo nao perde nada.
- `regenerar` refaz derivado e nao encosta em fonte.
- O CSV registra se a cotacao manual foi coleta, conferencia com alteracao ou reconfirmacao.
- Manual vencida nao vence observacao recente.
- `aprender-veredito` roda uma vez por veredito; repetir exige `--force`.
- Editar gate por `--gate` preserva os comentarios do `categorias.yaml`.
- Dinheiro sai no formato brasileiro: `R$ 1.234,50`.
- Nenhuma constante de score mora no codigo: tudo em `preferencias.yaml`.

## Estrutura

```text
config/
  categorias.yaml
  preferencias.yaml
projetos/
  <ano>-<compra>/
produtos/
  <categoria>/
base-conhecimento/
  lojas/
  marcas/
  licoes.md
vereditos/
scripts/
templates/
dashboard/
```

## Como a IA entra

A IA ajuda principalmente em tres momentos:

- definir o modelo certo a partir de uma necessidade vaga;
- mapear candidatos e problemas recorrentes em reviews;
- explicar a decisao, inclusive por que os finalistas perderam.

Os prompts gerados por `prompt-ia` incluem automaticamente licoes da categoria, marcas e lojas ja registradas na base de conhecimento.

Tambem ha uma skill local. Apos cada `git pull`, instale-a nas maquinas de agente que voce usa:

```powershell
python scripts/instalar_skill.py
```

Use no Codex:

```text
$central-compras abra um processo para comprar um fone de ate R$ 600
```

A copia versionada da skill fica em `skills/central-compras/`.

Ela nao deve fingir que confirmou preco, estoque, frete ou cupom quando isso depende do site no momento da compra. Esses dados entram como `fonte=manual`.

## Testes

```powershell
python -m unittest discover -s tests
```

281 testes. Alem dos casos de exemplo, ha teste de invariante que gera cotacoes
aleatorias (inclusive patologicas: preco negativo, `1e309`, data impossivel,
unicode) e confere propriedades que tem que valer sempre: score entre 0 e 100,
eixo entre 0 e 1, cortado nunca pontua, o mais barato elegivel sempre tira 1,00
no eixo valor, processos concorrentes nao perdem linha e um processo morto nao
deixa trava orfa.
