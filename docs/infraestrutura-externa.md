# Infraestrutura externa — LEIA ANTES DE CRIAR QUALQUER COISA

> **Para qualquer agente (Claude, Codex, Kimi, Antigravity, Gemini) e para o
> Josemar em outra máquina.** Este arquivo é o inventário do que a Central já
> tem **fora do repositório**: contas, pastas no Drive, scripts publicados,
> endpoints. Se você está prestes a "criar a planilha", "publicar o Apps
> Script" ou "configurar a integração", **pare e leia esta lista primeiro**.

## Por que este arquivo existe

Em 04/09/2026 três agentes diferentes (Kimi, Antigravity e Claude), em
sessões separadas, concluíram que a integração com Google Sheets "nunca tinha
sido ativada" e partiram para criar tudo de novo. Estavam errados: existia
desde 31/08 uma planilha, um Apps Script e um Web App publicado e **ativo**.

O motivo do erro não foi desatenção. Foi estrutural, e vale entender para não
repetir:

1. **A prova de que existia morava fora do Git.** URL e token ficam em
   `~/.central-compras/dados-privados/integracao_sheets.json`, que é local da
   máquina de propósito (é segredo). Em outra máquina o arquivo não existe, e
   a conclusão natural — errada — é "nunca foi configurado".
2. **O script era *container-bound*.** Ele vivia dentro da planilha, não como
   projeto solto. Quando a planilha foi para a lixeira, o script sumiu de
   `script.google.com` (some de "Meus projetos" **e** de "Todos os
   projetos"). Procurar por script não achava nada.
3. **O STATUS.md dizia que "rodou de verdade", mas não dizia onde.** Registro
   sem endereço não permite retomar.

**Regra que sai disso: dado que mora só em `dados-privados` tem que estar
anunciado aqui — sem o segredo, mas com o endereço.**

## Como conferir se já existe, antes de criar (3 minutos)

Na ordem, porque cada passo pega um caso que o anterior não pega:

1. **Este arquivo.** É a fonte declarada.
2. **A pasta no Drive** da conta certa (abaixo). Procure pelo nome da pasta,
   não pelo script.
3. **A lixeira do Drive.** Arquivo na lixeira não aparece em busca normal, e
   leva o script vinculado junto para a invisibilidade.
4. **`script.google.com/home/all`** ("Todos os projetos", não só "Meus").
5. Achou a planilha? Abra **Extensões → Apps Script** dentro dela: é assim
   que se encontra script *container-bound*.
6. Achou o script? Abra **Implantar → Gerenciar implantações** para ver se há
   Web App **ativo** (é o que responde na internet) e **Acionadores** para
   ver se há automação agendada.

## Inventário atual (05/09/2026)

### Conta

Tudo na conta Google **conta-comercial@exemplo.com** (perfil "Esdra Aline").
Navegador: servidor MCP `nav-conta-comercial`.

### Pasta no Drive

```
Meu Drive/10_JOSEMAR_PESSOAL/03_PROJETOS_ATIVOS/02_TECNOLOGIA_E_IA/Central de Compras
```

ID: `1MyR5NNhHz5Q2RtSHbgPZxXDV3kRM2ARU`

Fica junto dos outros projetos de código dessa conta (FisioAI, DISC,
central_automacoes_sync). **Não é na raiz do Drive** — e é justamente por
buscar só na raiz que a primeira versão do script criou uma pasta duplicada.

### Planilha

`Central de Compras - Cotacoes e Comparacoes`, dentro da pasta acima.
É **espelho descartável**: a verdade é o `cotacoes.csv` de cada projeto.
Pode ser recriada sem perda — o script a recria se não existir.

### Apps Script

Projeto **`Central de Compras - Sync`** (projeto solto, não container-bound,
de propósito: assim não desaparece se a planilha for para a lixeira).

- Editor: `script.google.com/home/projects/1m-BuWuaktiFJ7zWYsLyCI_L6EesZB9SaSCsvScc9IQv5g5L5i3BFiiaz/edit`
- Web App **ativo**, execução como conta-comercial, acesso "qualquer pessoa",
  protegido por token no corpo do POST.
- A implantação ativa é a **Versão 8**, publicada em 05/09/2026 pela conta
  **conta-comercial**, no mesmo ID e na mesma URL do Web App. O layout premium foi
  sincronizado com 8 projetos e 8 comparativos e conferido na planilha real:
  9 abas, filtros, links, formatos numéricos e gráficos. As versões 5 a 7
  foram etapas intermediárias do mesmo deploy; a 8 corrige o congelamento de
  colunas com células mescladas e as fontes transpostas dos gráficos.
- Código e procedimento de redeploy: [`integracao-google-sheets.md`](integracao-google-sheets.md).

### Configuração: o que viaja no `git pull` e o que não viaja

A configuração é dividida de propósito, para que `git pull` deixe uma máquina
nova a **um comando** de funcionar:

| Onde | O quê | Viaja no Git? |
|---|---|---|
| `config/integracao_sheets.yaml` | a **URL** do Web App | **Sim** |
| `~/.central-compras/dados-privados/integracao_sheets.json` | o **token** | Não, e nem deve |

A URL pode ser versionada porque sozinha ela não dá acesso: quem protege o
endpoint é o token, conferido dentro do Apps Script.

**Máquina nova, do zero:**

```powershell
git pull
python scripts/central_compras.py configurar-sheets --token SEU_TOKEN
python scripts/central_compras.py sincronizar-planilha
```

O token está em `const TOKEN` no Code.gs (conta conta-comercial) ou no
`integracao_sheets.json` de uma máquina que já funciona.

Se faltar o token, o próprio comando diz isso e ensina a linha acima — não é
sinal de que a integração não existe.

**Depois de um redeploy que gere URL nova:** atualize
`config/integracao_sheets.yaml` e **commite**. Senão as outras máquinas
continuam batendo no endpoint velho e tomando 404 — foi o que aconteceu em
04/09. O `configurar-sheets` remove URL antiga presa no arquivo local
justamente para essa armadilha não sobreviver a um `git pull`.

## Desativado (não recriar, não reativar)

- **Planilha `Central de Compras - Comparativo de Produtos`** (31/08/2026) —
  na lixeira, acesso já fechado para Restrito. Expira sozinha ~04/10/2026.
- **Apps Script sem título** `1dbv6oCJefa6WiAXijBN3XOuFBFolF-JxdzZsQHFLww5r_HlI4Rhycwec`,
  container-bound à planilha acima. Implantação "Integração Central de
  Compras" (Versão 1, 31/08 15:30) **arquivada em 04/09/2026** porque havia
  dois Web Apps abertos na internet ao mesmo tempo. O endpoint antigo
  responde 404 desde então.
  - Verificado antes de arquivar: **zero acionadores** no projeto e **nenhuma
    referência àquela URL em nenhum projeto de `C:\projetos`** — ou seja, não
    era peça de nenhuma automação, era a implantação anterior deste mesmo
    comando `sincronizar-planilha`.
  - **Efeito colateral conhecido:** qualquer máquina cujo
    `integracao_sheets.json` ainda aponte para a URL antiga vai receber 404.
    A correção é substituir o arquivo pelo que aponta para o Web App atual.

## Ao mexer nessa infraestrutura, atualize este arquivo

Criou, moveu, arquivou ou trocou de conta? Edite aqui **no mesmo commit**.
Um inventário desatualizado é pior que nenhum, porque dá confiança falsa.
Nunca escreva o token aqui: só o endereço.
