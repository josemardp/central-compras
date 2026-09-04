# Integração Google Sheets / Drive (conta conta-comercial)

O comando `python scripts/central_compras.py sincronizar-planilha` exporta a
visão geral dos projetos e os comparativos de cotações para uma planilha Google.

**Status: ativo.** Implantado na conta conta-comercial, testado de ponta a ponta em
2026-09-04.

## Como funciona

```
repo ──POST JSON──> Apps Script Web App (conta conta-comercial)
                      ├─ valida o token
                      ├─ abre a pasta "Central de Compras" (por ID fixo)
                      ├─ procura a planilha "Central de Compras - Cotacoes e Comparacoes" dentro da pasta
                      │    └─ se não existir, CRIA
                      └─ reescreve a aba "Visao Geral" e uma aba por projeto comparativo
```

- O envio é **só de saída** (repo → Sheets). O `cotacoes.csv` continua sendo a
  verdade append-only; a planilha é espelho descartável.
- O arquivo `comparacao.xlsx` gerado manualmente (abas Detalhado/Pulseiras) NÃO
  passa por esse fluxo; se quiser espelhá-lo também, suba o arquivo na mesma
  pasta do Drive manualmente.
- A pasta "Central de Compras" vive em
  `Meu Drive/10_JOSEMAR_PESSOAL/03_PROJETOS_ATIVOS/02_TECNOLOGIA_E_IA/Central de Compras`
  (mesmo padrão dos outros projetos de código nessa conta, tipo FisioAI e DISC).
  O script referencia essa pasta **por ID fixo**, não por busca de nome na raiz
  do Drive — isso evita criar uma pasta duplicada na raiz se um dia a pasta for
  movida ou renomeada.

## Onde está o projeto do Apps Script

Projeto "Central de Compras - Sync" em https://script.google.com, conta
conta-comercial. Editor:
`https://script.google.com/home/projects/1m-BuWuaktiFJ7zWYsLyCI_L6EesZB9SaSCsvScc9IQv5g5L5i3BFiiaz/edit`

## Code.gs (versão implantada)

```javascript
const TOKEN = '...'; // cole aqui uma senha longa aleatoria. O valor real vive
                     // so no Code.gs (na conta conta-comercial) e no
                     // integracao_sheets.json local. Nunca neste arquivo.
const PASTA_ID = '1MyR5NNhHz5Q2RtSHbgPZxXDV3kRM2ARU';
const PLANILHA_NOME = 'Central de Compras - Cotacoes e Comparacoes';

function doPost(e) {
  let dados;
  try {
    dados = JSON.parse(e.postData.contents);
  } catch (err) {
    return resposta({ ok: false, error: 'JSON invalido' });
  }
  if (dados.token !== TOKEN) {
    return resposta({ ok: false, error: 'token invalido' });
  }

  const pasta = pastaCentral();
  const planilha = planilhaCentral(pasta);
  escreverVisaoGeral(planilha, dados.visao_geral || []);
  (dados.comparativos || []).forEach(function (c) {
    escreverComparativo(planilha, c);
  });
  return resposta({
    ok: true,
    mensagem: 'sincronizado',
    pasta: pasta.getUrl(),
    planilha: planilha.getUrl(),
  });
}

function pastaCentral() {
  return DriveApp.getFolderById(PASTA_ID);
}

function planilhaCentral(pasta) {
  const arquivos = pasta.getFilesByType(MimeType.GOOGLE_SHEETS);
  while (arquivos.hasNext()) {
    const arquivo = arquivos.next();
    if (arquivo.getName() === PLANILHA_NOME) {
      return SpreadsheetApp.openById(arquivo.getId());
    }
  }
  const nova = SpreadsheetApp.create(PLANILHA_NOME);
  pasta.addFile(DriveApp.getFileById(nova.getId()));
  DriveApp.getRootFolder().removeFile(DriveApp.getFileById(nova.getId()));
  return nova;
}

function escreverVisaoGeral(planilha, linhas) {
  const campos = [
    'categoria', 'estado', 'lider', 'score', 'confianca', 'cotacoes',
    'manual', 'dias_ate_decisao', 'escolhido', 'aguardando_preco',
  ];
  const aba = abaLimpa(planilha, 'Visao Geral');
  aba.appendRow(['projeto'].concat(campos));
  linhas.forEach(function (linha) {
    aba.appendRow([linha.projeto].concat(campos.map(function (c) {
      return linha[c] !== undefined && linha[c] !== null ? linha[c] : '';
    })));
  });
}

function escreverComparativo(planilha, comp) {
  let nomeAba = comp.projeto.replace(/[\[\]:*?\/\\]/g, '-').slice(0, 100);
  const aba = abaLimpa(planilha, nomeAba);
  // Sem esta linha, a tabela mostrava numero sem dono: dava para ver preco e
  // nota, mas nao qual coluna era qual produto. O payload sempre mandou
  // comp.colunas; o script e que ignorava.
  aba.appendRow(['Produto'].concat(comp.colunas || []));
  aba.appendRow(['Situacao'].concat(comp.situacao || []));
  comp.linhas.forEach(function (linha) {
    if (linha.tipo === 'estrela') {
      aba.appendRow([linha.rotulo].concat((linha.valores || []).map(function (v) {
        if (!v.estrelas) return v.texto;
        return v.texto + '  ' + '*'.repeat(v.estrelas) + ' (' + v.estrelas + '/5)';
      })));
    } else {
      aba.appendRow([linha.rotulo].concat(linha.valores || []));
    }
  });
  aba.getRange(1, 1, 1, aba.getLastColumn()).setFontWeight('bold');
  aba.setFrozenRows(1);
}

function abaLimpa(planilha, nome) {
  let aba = planilha.getSheetByName(nome);
  if (!aba) aba = planilha.insertSheet(nome);
  // clear() e nao clearContents(): precisa levar junto negrito e linha
  // congelada da execucao anterior, senao formatacao velha gruda na aba.
  aba.clear();
  aba.setFrozenRows(0);
  return aba;
}

function resposta(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
```

**Nota histórica — três bugs, todos herdados do mesmo Code.gs de origem:**

| Versão | Bug | Sintoma |
|---|---|---|
| 1 → 2 | `DriveApp.getRoot()` não existe (é `getRootFolder()`) | `TypeError`, sincronização quebrada por completo |
| 2 → 3 | pasta buscada só na raiz do Drive | criou pasta duplicada na raiz, já que a certa é aninhada |
| 3 → 4 | `comp.colunas` ignorado | tabela sem cabeçalho: dava para ver preço e nota, mas **não qual coluna era qual produto** |

O terceiro só apareceu quando o Josemar olhou a planilha e perguntou "não
estou vendo as marcas". Vale a lição: `sincronizar-planilha` responder
`ok` prova que o POST chegou, não que a planilha ficou legível. **Confira
abrindo a planilha.**

## Implantação (para redeploy futuro)

1. Editor do projeto → editar o `Código.gs` → salvar (Ctrl+S).
2. Implantar → Gerenciar implantações → editar a implantação existente →
   Versão: **Nova versão** → Implantar. (Isso preserva a mesma URL /exec —
   nunca criar uma implantação nova do zero, senão a URL muda e o
   `integracao_sheets.json` local fica desatualizado.)

## Configuração da máquina

A URL já vem versionada em `config/integracao_sheets.yaml`, pelo `git pull`.
Falta só o token, que não vai pelo Git:

```powershell
python scripts/central_compras.py configurar-sheets --token SEU_TOKEN
```

Isso grava `{"token": "..."}` em
`~/.central-compras/dados-privados/integracao_sheets.json` — fora do
repositório, nunca commitado.

Para apontar uma máquina a um endpoint de teste sem sujar o repositório,
acrescente `--url https://.../exec`. Sem esse argumento vale sempre a URL
versionada (é o que evita máquina presa numa URL velha depois de redeploy).

## Sincronizar

```bash
python scripts/central_compras.py sincronizar-planilha
```

Sucesso devolve `Planilha sincronizada: N projeto(s), N comparativo(s).`

**Timeout:** com muitos projetos (8 no teste de 2026-09-04), a implantação
leva até ~47s para responder (o Apps Script escreve linha por linha em cada
aba, sem batch). O timeout do cliente Python foi ajustado de 30s para 120s em
`scripts/central_compras.py` por causa disso. Se o número de projetos crescer
muito e voltar a estourar, o próximo passo é trocar `appendRow` por
`setValues` em lote no `escreverComparativo`/`escreverVisaoGeral`.
