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

## Inventário atual (04/09/2026)

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
- Código e procedimento de redeploy: [`integracao-google-sheets.md`](integracao-google-sheets.md).

### Config local (por máquina, fora do Git)

```
~/.central-compras/dados-privados/integracao_sheets.json
{"url": "<URL /exec do Web App>", "token": "<o mesmo token do Code.gs>"}
```

**Este arquivo não sincroniza entre máquinas.** Se `sincronizar-planilha`
falhar numa máquina nova, quase sempre é só isso: o arquivo não existe ali
ainda. Copie de uma máquina que funciona — não crie infraestrutura nova.

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
