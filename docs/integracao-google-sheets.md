# Integração Google Sheets / Drive (conta conta-comercial)

O comando `python scripts/central_compras.py sincronizar-planilha` exporta a
visão geral dos projetos e os comparativos de cotações para uma planilha Google.

**Status externo: Versão 9 ainda é a que está ativa na nuvem.** A Versão 10
(código abaixo) corrige 3 falhas reais da Versão 9 - ver
"Code.gs (versão 10 - DEPLOY PENDENTE)" logo adiante - mas **ainda não foi
publicada**. Enquanto a implantação não for atualizada pela conta
`conta-comercial@exemplo.com`, o Web App continua rodando o código da Versão 9.

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

## Code.gs (versão 10 - DEPLOY PENDENTE)

> **O código abaixo NÃO está implantado ainda.** A nuvem continua rodando a
> Versão 9. Esta Versão 10 corrige, em 07/09/2026, 3 falhas reais encontradas
> nesta sessão (reproduzidas de verdade executando o próprio Code.gs sob Node
> com fakes do runtime do Apps Script, script em
> `docs/plano-pendencias-auditoria-2026-09-06.md` §3):
>
> 1. **Payload com `null`/tipo errado quebrava no meio da escrita.** Um
>    elemento `null` em `visao_geral` (ou em `comparativos[].metricas`,
>    `.linhas` ou `.linhas[].valores_tipados`) chegava intacto até
>    `escreverVisaoGeral`/`renderizarLinha`, que faziam `linha.campo` sem
>    checar null - e isso rodava DEPOIS de `escreverComparativo` já ter
>    reescrito abas de projeto. Resultado: planilha parcialmente atualizada e
>    inconsistente. Agora `validarPayload(dados)` percorre o payload inteiro e
>    recusa antes de tocar qualquer aba.
> 2. **`limparAbasOrfas` apagava aba criada à mão.** A checagem de "essa aba
>    foi gerada pelo script" era só um padrão de nome
>    (`/^20\d\d-/`, `'Painel'`, `'_Dados'`, ...); uma aba renomeada ou criada
>    manualmente com nome parecido (ex.: `2026-manual`) caía no mesmo padrão e
>    era apagada assim que o projeto correspondente saísse do payload. Agora
>    há um registro real (`PropertiesService`, propriedade
>    `abas_geradas_pelo_script`) das abas que o PRÓPRIO script escreveu em
>    alguma sincronização anterior; só essas são candidatas a limpeza.
> 3. **Falha no meio da escrita não dizia o que já tinha sido gravado.** A
>    resposta de erro só tinha `error`/`detalhe` (a mensagem da exceção), sem
>    dizer quais abas a sincronização já tinha escrito antes de quebrar.
>    Agora a resposta de erro inclui `abas_escritas_antes_da_falha`, e
>    `sincronizar_planilha()` (Python) mostra essa lista na mensagem.
>
> Redeploy (pela conta `conta-comercial@exemplo.com`, preservando ID/URL - ver
> "Implantação" adiante), duas sincronizações e conferência visual da
> planilha real ficaram **bloqueados nesta sessão**: o perfil de navegador
> `conta-comercial` já estava em uso por outro processo
> (`Browser is already in use for ...perfil-conta-comercial`). Fica para a próxima
> sessão com esse perfil livre - ver `STATUS.md`.

```javascript
const TOKEN = '...'; // cole aqui uma senha longa aleatoria. O valor real vive
                     // so no Code.gs (na conta conta-comercial) e no
                     // integracao_sheets.json local. Nunca neste arquivo.
const PASTA_ID = '1MyR5NNhHz5Q2RtSHbgPZxXDV3kRM2ARU';
const PLANILHA_NOME = 'Central de Compras - Cotacoes e Comparacoes';
const SCHEMA_SUPORTADO = 3;
const CAMPOS_VISAO_FALLBACK = [
  'projeto', 'categoria', 'estado', 'lider', 'score', 'confianca', 'cotacoes',
  'manual', 'dias_ate_decisao', 'escolhido', 'aguardando_preco',
];
const CAMPOS_METRICAS_FALLBACK = [
  'projeto', 'produto', 'situacao', 'score', 'confianca', 'custo_total',
  'nota', 'avaliacoes', 'qualidade', 'valor', 'risco', 'aderencia',
  'conveniencia',
];
const TEMA = {
  tinta: '#0b0b0b',
  secundaria: '#52514e',
  apagada: '#898781',
  faixa: '#f9f9f7',
  linha: '#e1e0d9',
  base: '#c3c2b7',
  lider: '#2a78d6',
  liderFundo: '#eaf2fd',
  magnitudeBaixa: '#86b6ef',
  magnitudeMedia: '#3987e5',
  magnitudeAlta: '#1c5cab',
  magnitudeMaxima: '#0d366b',
  decidido: '#0ca30c',
  pesquisando: '#fab219',
  aguardando: '#ec835a',
  vencida: '#d03b3b',
  slot2: '#eb6834',
  slot3: '#1baf7a',
  branco: '#FFFFFF',
};

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

  const bloqueio = LockService.getScriptLock();
  if (!bloqueio.tryLock(30000)) {
    return resposta({ ok: false, error: 'outra sincronizacao esta em andamento' });
  }

  const abasEscritas = [];
  try {
    const avisos = coletarAvisos(dados);
    // Valida a forma do payload inteiro ANTES de tocar qualquer aba. Uma
    // planilha so pode ficar parcialmente escrita se algo falhar depois
    // desse ponto - null/tipo errado em visao_geral ou dentro de
    // comparativos tem que barrar aqui, nunca no meio de um escreverX().
    validarPayload(dados);
    const pasta = pastaCentral();
    const planilha = planilhaCentral(pasta);
    const comparativos = Array.isArray(dados.comparativos) ? dados.comparativos : [];
    const camposVisao = colunasOuFallback(
      dados.visao_geral_colunas, CAMPOS_VISAO_FALLBACK, 'projeto', avisos
    );
    const camposMetricas = colunasOuFallback(
      dados.metricas_colunas, CAMPOS_METRICAS_FALLBACK, 'projeto', avisos
    );
    const nomesUsados = { 'Painel': true, 'Visao Geral': true, '_Dados': true };
    const destinos = comparativos.map(function (comp) {
      return nomeAbaProjeto(comp.projeto, nomesUsados);
    });
    const abaVisao = planilha.getSheetByName('Visao Geral') || planilha.insertSheet('Visao Geral');
    const linkVisao = planilha.getUrl() + '#gid=' + abaVisao.getSheetId();
    comparativos.forEach(function (comp, indice) {
      escreverComparativo(planilha, comp, destinos[indice], dados.gerado_em, linkVisao);
      abasEscritas.push(destinos[indice]);
    });
    escreverVisaoGeral(
      planilha, Array.isArray(dados.visao_geral) ? dados.visao_geral : [],
      camposVisao, dados.gerado_em, avisos, comparativos, destinos
    );
    abasEscritas.push('Visao Geral');

    // Se o campo sumir por regressao, preservar abas e avisar e mais seguro
    // que apagar tudo. Com uma lista valida, remove so abas que o proprio
    // script gerou em alguma sincronizacao anterior (registro persistido) -
    // nunca por o nome parecer gerado.
    if (Array.isArray(dados.comparativos)) {
      limparAbasOrfas(planilha, destinos);
    }

    return resposta({
      ok: true,
      mensagem: 'sincronizado',
      schema_versao: SCHEMA_SUPORTADO,
      linhas_visao: Array.isArray(dados.visao_geral) ? dados.visao_geral.length : 0,
      projetos_escritos: comparativos.length,
      avisos: avisos,
      pasta: pasta.getUrl(),
      planilha: planilha.getUrl(),
    });
  } catch (err) {
    // abas_escritas_antes_da_falha deixa o cliente conferir exatamente o
    // que ja foi gravado quando a sincronizacao quebra no meio - antes so
    // tinha a mensagem do erro, sem dizer o que a planilha ficou refletindo.
    return resposta({
      ok: false,
      error: 'falha na sincronizacao',
      detalhe: String(err),
      abas_escritas_antes_da_falha: abasEscritas,
    });
  } finally {
    bloqueio.releaseLock();
  }
}

function validarPayload(dados) {
  validarListaDeObjetos(dados.visao_geral, 'visao_geral');
  const comparativos = Array.isArray(dados.comparativos) ? dados.comparativos : [];
  comparativos.forEach(function (comp, ci) {
    validarObjeto(comp, 'comparativos[' + ci + ']');
    validarListaDeObjetos(comp.metricas, 'comparativos[' + ci + '].metricas');
    validarListaDeObjetos(comp.linhas, 'comparativos[' + ci + '].linhas');
    (Array.isArray(comp.linhas) ? comp.linhas : []).forEach(function (linha, li) {
      validarListaDeObjetos(
        linha.valores_tipados, 'comparativos[' + ci + '].linhas[' + li + '].valores_tipados'
      );
    });
  });
}

function validarObjeto(valor, caminho) {
  if (valor === null || typeof valor !== 'object' || Array.isArray(valor)) {
    throw new Error('payload invalido em ' + caminho + ': esperava objeto, recebeu ' + JSON.stringify(valor));
  }
}

function validarListaDeObjetos(lista, caminho) {
  if (lista === undefined) return;
  if (!Array.isArray(lista)) {
    throw new Error('payload invalido em ' + caminho + ': esperava lista, recebeu ' + JSON.stringify(lista));
  }
  lista.forEach(function (item, indice) {
    validarObjeto(item, caminho + '[' + indice + ']');
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

// ---------------------------------------------------------------- Visao Geral

function decidido(linha) {
  return Boolean(linha.data_decisao || linha.escolhido || linha.estado === 'comprado');
}

function pesoAtencao(linha) {
  // Cockpit: quem precisa de acao primeiro, decididos por ultimo. Nunca por
  // score: o eixo valor e relativo ao mais barato de cada projeto, entao o
  // score total nao e comparavel entre projetos (README, "Como o score
  // funciona").
  if (decidido(linha)) return -1;
  return (Number(linha.cotacoes_vencidas) || 0) * 100
    + (Number(linha.aguardando_preco) || 0) * 10
    + (linha.lider ? 0 : 5)
    + (linha.empate_tecnico ? 2 : 0);
}

function pendenciasProjeto(linha) {
  // So fatos presentes no payload. Ausencia nao vira zero nem recomendacao.
  const pendencias = [];
  if (decidido(linha)) return pendencias;
  const vencidas = Number(linha.cotacoes_vencidas) || 0;
  const aguardando = Number(linha.aguardando_preco) || 0;
  const cotacoes = Number(linha.cotacoes) || 0;
  const manual = Number(linha.manual) || 0;
  const baixaConfianca = Number(linha.abaixo_confianca_minima) || 0;
  if (vencidas) pendencias.push('▲ ' + vencidas + ' cotacao(oes) vencida(s)');
  if (aguardando) pendencias.push('◔ ' + aguardando + ' produto(s) aguardando confirmacao de preco');
  if (!linha.lider) pendencias.push('◔ nenhum candidato elegivel ainda');
  if (cotacoes && !manual) pendencias.push('◔ so fonte web; nenhuma cotacao manual');
  if (baixaConfianca) pendencias.push('◐ ' + baixaConfianca + ' candidato(s) abaixo da confianca minima');
  if (linha.empate_tecnico) pendencias.push('◐ empate tecnico no topo do ranking');
  return pendencias;
}

function escreverVisaoGeral(planilha, linhas, campos, geradoEm, avisos, comparativos, destinos) {
  const aba = abaLimpa(planilha, 'Visao Geral');
  const largura = Math.max(1, campos.length);
  const larguraFaixa = Math.max(10, largura);
  const ordenadas = linhas.slice().sort(function (a, b) {
    const peso = pesoAtencao(b) - pesoAtencao(a);
    if (peso) return peso;
    return String(a.projeto).localeCompare(String(b.projeto));
  });

  // Faixa de indicadores: o numero e o protagonista; cor forte so quando ha
  // algo a resolver.
  const ativos = linhas.filter(function (linha) { return !decidido(linha); }).length;
  const decididos = linhas.length - ativos;
  const aguardando = linhas.reduce(function (total, linha) {
    return total + (decidido(linha) ? 0 : (Number(linha.aguardando_preco) || 0));
  }, 0);
  const vencidas = linhas.reduce(function (total, linha) {
    return total + (decidido(linha) ? 0 : (Number(linha.cotacoes_vencidas) || 0));
  }, 0);
  const bloqueados = linhas.filter(function (linha) {
    return !decidido(linha) && !linha.lider;
  }).length;
  const indicadores = [
    ['PROJETOS ATIVOS', ativos, ''],
    ['DECISOES FECHADAS', decididos, ''],
    ['AGUARDANDO PRECO', aguardando, aguardando ? TEMA.pesquisando : ''],
    ['COTACOES VENCIDAS', vencidas, vencidas ? TEMA.vencida : ''],
    ['PROJETOS BLOQUEADOS', bloqueados, bloqueados ? TEMA.vencida : ''],
  ];
  indicadores.forEach(function (indicador, indice) {
    const coluna = indice * 2 + 1;
    aba.getRange(1, coluna, 1, 2).merge().setValue(indicador[0]);
    aba.getRange(2, coluna, 1, 2).merge().setValue(indicador[1]);
  });
  aba.getRange(3, 1, 1, larguraFaixa).merge()
    .setValue('Central de Compras · espelho de decisao · gerado em ' +
      String(geradoEm || 'data nao informada'))
    .setNote(avisos.length ? avisos.join('\n') : 'Sem avisos de compatibilidade.');
  aba.getRange(1, 1, 3, larguraFaixa).setFontFamily('Inter');
  aba.getRange(1, 1, 1, larguraFaixa).setFontSize(10).setFontWeight('bold')
    .setFontColor(TEMA.secundaria).setBackground(TEMA.faixa);
  aba.getRange(2, 1, 1, larguraFaixa).setFontSize(24).setFontWeight('bold')
    .setFontColor(TEMA.tinta).setBackground(TEMA.branco);
  indicadores.forEach(function (indicador, indice) {
    if (indicador[2]) aba.getRange(2, indice * 2 + 1, 1, 2).setFontColor(indicador[2]);
  });
  aba.getRange(3, 1, 1, larguraFaixa).setFontSize(9).setFontColor(TEMA.apagada)
    .setHorizontalAlignment('left');

  // Fila de atencao: quem precisa de acao e por que. So fatos do payload.
  let proximaLinha = 5;
  const fila = ordenadas.map(function (linha) {
    return { linha: linha, pendencias: pendenciasProjeto(linha) };
  }).filter(function (item) { return item.pendencias.length; });
  if (fila.length) {
    aba.getRange(proximaLinha, 1, 1, larguraFaixa).merge()
      .setValue('FILA DE ATENCAO · ' + fila.length + ' projeto(s) precisam de acao')
      .setFontFamily('Inter').setFontSize(10).setFontWeight('bold')
      .setFontColor(TEMA.secundaria).setBackground(TEMA.faixa)
      .setBorder(false, false, true, false, false, false, TEMA.linha, SpreadsheetApp.BorderStyle.SOLID);
    proximaLinha += 1;
    fila.forEach(function (item) {
      aba.getRange(proximaLinha, 2, 1, larguraFaixa - 1).merge()
        .setValue(item.pendencias.join('  ·  '))
        .setFontFamily('Inter').setFontSize(10)
        .setFontColor(item.pendencias[0].indexOf('▲') === 0 ? TEMA.vencida : TEMA.secundaria);
      const destino = destinoPorProjeto(planilha, item.linha.projeto, comparativos, destinos);
      const celula = aba.getRange(proximaLinha, 1);
      if (destino) {
        celula.setRichTextValue(SpreadsheetApp.newRichTextValue()
          .setText(String(item.linha.projeto))
          .setLinkUrl(planilha.getUrl() + '#gid=' + destino.getSheetId()).build());
      } else {
        celula.setValue(String(item.linha.projeto));
      }
      celula.setFontFamily('Inter').setFontSize(10).setFontColor(TEMA.tinta);
      proximaLinha += 1;
    });
    proximaLinha += 1;
  }

  // Tabela principal.
  const linhaCabecalho = proximaLinha;
  const tabela = [campos.map(tituloCampo)].concat(ordenadas.map(function (linha) {
    return campos.map(function (c) {
      if (c === 'estado') return estadoVisao(linha);
      return linha[c] !== undefined && linha[c] !== null ? linha[c] : '';
    });
  }));
  const formatosTabela = [linhaFormato(largura, '@')].concat(ordenadas.map(function () {
    return campos.map(function (campo) {
      if (campo === 'score') return '0.0';
      if (campo === 'confianca') return '0%';
      if (['cotacoes', 'manual', 'dias_ate_decisao', 'aguardando_preco'].indexOf(campo) >= 0) return '0';
      return '@';
    });
  }));
  const faixaTabela = aba.getRange(linhaCabecalho, 1, tabela.length, largura);
  faixaTabela.setNumberFormats(formatosTabela);
  faixaTabela.setValues(tabela);
  const cabecalho = aba.getRange(linhaCabecalho, 1, 1, largura);
  cabecalho.setBackground(TEMA.faixa).setFontColor(TEMA.secundaria)
    .setFontWeight('bold').setFontFamily('Inter').setHorizontalAlignment('left')
    .setBorder(false, false, true, false, false, false, TEMA.base, SpreadsheetApp.BorderStyle.SOLID);

  if (ordenadas.length) {
    const corpo = aba.getRange(linhaCabecalho + 1, 1, ordenadas.length, largura);
    corpo.setFontFamily('Inter').setFontColor(TEMA.tinta).setFontSize(10)
      .setVerticalAlignment('middle').setWrap(true);
    aplicarFaixas(corpo);
    aplicarLinksProjetos(planilha, aba, ordenadas, campos, comparativos, destinos, linhaCabecalho + 1);
    colorirEstadosVisao(aba, ordenadas, campos, linhaCabecalho + 1);
    formatarColunasVisao(aba, campos, ordenadas.length, linhaCabecalho + 1);
    aba.getRange(linhaCabecalho, 1, ordenadas.length + 1, largura).createFilter();
    inserirGraficoPendencias(aba, ordenadas, linhaCabecalho, larguraFaixa + 16, largura + 2);
  }
  aplicarLargurasVisao(aba, campos);
  const rodape = linhaCabecalho + tabela.length + 1;
  aba.getRange(rodape, 1, 1, largura).merge()
    .setValue('Espelho gerado em ' + String(geradoEm || 'data nao informada') +
      ' · a fonte e o cotacoes.csv de cada projeto')
    .setFontFamily('Inter').setFontSize(9).setFontColor(TEMA.apagada);
  // Titulos e rodapes atravessam varias colunas mescladas; congelar uma
  // coluna cortaria essas mesclas e o Google Sheets rejeitaria a renderizacao.
  // As mesclas ficam acima da linha de congelamento, que e horizontal.
  // A fila e dinamica. Congelar ate o cabecalho prenderia muitas linhas no
  // celular quando varios projetos exigissem atencao.
  aba.setFrozenRows(3);
  aba.setFrozenColumns(0);
  aba.setTabColor(TEMA.lider);
  protegerEspelho(aba);
}

function destinoPorProjeto(planilha, projeto, comparativos, destinos) {
  for (let i = 0; i < comparativos.length; i += 1) {
    if (comparativos[i].projeto === projeto) {
      return planilha.getSheetByName(destinos[i]);
    }
  }
  return null;
}

function estadoVisao(linha) {
  if (decidido(linha)) return '● Decidido';
  if (linha.cotacoes_vencidas > 0) return '▲ Vencida';
  if (linha.aguardando_preco > 0) return '◔ Aguardando preco';
  return '◐ Pesquisando';
}

function colorirEstadosVisao(aba, linhas, campos, inicio) {
  const indice = campos.indexOf('estado');
  if (indice < 0) return;
  linhas.forEach(function (linha, linhaIndice) {
    let cor = TEMA.pesquisando;
    if (decidido(linha)) cor = TEMA.decidido;
    else if (linha.cotacoes_vencidas > 0) cor = TEMA.vencida;
    else if (linha.aguardando_preco > 0) cor = TEMA.aguardando;
    aba.getRange(linhaIndice + inicio, indice + 1).setFontColor(cor).setFontWeight('bold');
  });
}

function aplicarLinksProjetos(planilha, aba, linhas, campos, comparativos, destinos, inicio) {
  const indice = campos.indexOf('projeto');
  if (indice < 0) return;
  linhas.forEach(function (linha, i) {
    const destino = destinoPorProjeto(planilha, linha.projeto, comparativos, destinos);
    if (!destino) return;
    const link = planilha.getUrl() + '#gid=' + destino.getSheetId();
    aba.getRange(i + inicio, indice + 1).setRichTextValue(
      SpreadsheetApp.newRichTextValue().setText(String(linha.projeto)).setLinkUrl(link).build()
    );
  });
}

// Grafico geral: pendencias por projeto (contagens, comparaveis entre
// projetos). NUNCA score total: o eixo valor e relativo ao mais barato de
// cada compra, entao scores de projetos diferentes nao dividem a mesma base.
function inserirGraficoPendencias(aba, linhas, ancoraLinha, colunaFonte, colunaGrafico) {
  const dados = [['Projeto', 'Cotacoes vencidas', 'Aguardando preco']];
  linhas.forEach(function (linha) {
    if (decidido(linha)) return;
    const vencidas = Number(linha.cotacoes_vencidas) || 0;
    const aguardando = Number(linha.aguardando_preco) || 0;
    if (vencidas + aguardando > 0) {
      dados.push([String(linha.projeto), vencidas, aguardando]);
    }
  });
  if (dados.length < 2) return; // sem pendencias, nao ha o que comparar
  if (aba.getMaxColumns() < colunaFonte + 2) {
    aba.insertColumnsAfter(aba.getMaxColumns(), colunaFonte + 2 - aba.getMaxColumns());
  }
  const fonte = aba.getRange(1, colunaFonte, dados.length, 3);
  fonte.setValues(dados);
  fonte.setFontColor(TEMA.branco).setBackground(TEMA.branco).setFontSize(6);
  aba.setColumnWidths(colunaFonte, 3, 24);
  const grafico = aba.newChart().setChartType(Charts.ChartType.COLUMN)
    .addRange(fonte).setNumHeaders(1)
    .setOption('title', 'Pendencias por projeto (contagem)')
    .setOption('fontName', 'Inter')
    .setOption('legend', { position: 'bottom' })
    .setOption('colors', [TEMA.vencida, TEMA.pesquisando])
    .setOption('vAxis', { viewWindow: { min: 0 }, textStyle: { color: TEMA.apagada } })
    .setPosition(ancoraLinha, colunaGrafico, 0, 0).build();
  aba.insertChart(grafico);
}

function formatarColunasVisao(aba, campos, quantidade, inicio) {
  formatarColunaPorNome(aba, campos, 'score', inicio, quantidade, '0.0');
  formatarColunaPorNome(aba, campos, 'confianca', inicio, quantidade, '0%');
  ['cotacoes', 'manual', 'dias_ate_decisao', 'aguardando_preco'].forEach(function (campo) {
    formatarColunaPorNome(aba, campos, campo, inicio, quantidade, '0');
  });
  ['score', 'confianca', 'cotacoes'].forEach(function (campo) {
    const indice = campos.indexOf(campo);
    if (indice >= 0) aba.getRange(inicio, indice + 1, quantidade, 1)
      .setFontFamily('Roboto Mono').setHorizontalAlignment('right');
  });
  const indiceConfianca = campos.indexOf('confianca');
  const regras = [];
  if (indiceConfianca >= 0) {
    const alvo = aba.getRange(inicio, indiceConfianca + 1, quantidade, 1);
    regras.push(SpreadsheetApp.newConditionalFormatRule().whenNumberLessThan(0.6)
      .setFontColor(TEMA.magnitudeBaixa).setRanges([alvo]).build());
    regras.push(SpreadsheetApp.newConditionalFormatRule().whenNumberBetween(0.6, 0.799999)
      .setFontColor(TEMA.magnitudeMedia).setRanges([alvo]).build());
    regras.push(SpreadsheetApp.newConditionalFormatRule().whenNumberBetween(0.8, 0.949999)
      .setFontColor(TEMA.magnitudeAlta).setRanges([alvo]).build());
    regras.push(SpreadsheetApp.newConditionalFormatRule().whenNumberGreaterThanOrEqualTo(0.95)
      .setFontColor(TEMA.magnitudeMaxima).setRanges([alvo]).build());
  }
  aba.setConditionalFormatRules(regras);
}

function aplicarLargurasVisao(aba, campos) {
  const larguras = {
    projeto: 360, categoria: 170, estado: 170, lider: 280, score: 90,
    confianca: 105, cotacoes: 90, manual: 90, dias_ate_decisao: 145,
    escolhido: 240, aguardando_preco: 145, data_decisao: 120,
  };
  campos.forEach(function (campo, indice) {
    aba.setColumnWidth(indice + 1, larguras[campo] || 150);
  });
}

// ------------------------------------------------------------- Comparativos

function escreverComparativo(planilha, comp, nomeAba, geradoEm, linkVisao) {
  const aba = abaLimpa(planilha, nomeAba);
  const colunas = Array.isArray(comp.colunas) ? comp.colunas : [];
  const situacaoRecebida = Array.isArray(comp.situacao) ? comp.situacao : [];
  const situacao = colunas.map(function (_, indice) {
    return situacaoRecebida[indice] || '';
  });
  const metricasRecebidas = Array.isArray(comp.metricas) ? comp.metricas : [];
  const metricas = metricasRecebidas.length ? colunas.map(function (_, indice) {
    return metricasRecebidas[indice] || {};
  }) : [];
  const linhas = Array.isArray(comp.linhas) ? comp.linhas : [];
  const largura = Math.max(1, colunas.length + 1);
  const matriz = [];
  const formatos = [];
  const notas = [];
  const fundos = [];
  const alinhamentos = [];

  function empurrar(valoresLinha) {
    matriz.push(valoresLinha);
    formatos.push(linhaFormato(largura, '@'));
    notas.push(linhaFormato(largura, ''));
    fundos.push(linhaFormato(largura, TEMA.branco));
    alinhamentos.push(linhaFormato(largura, 'left'));
  }

  // Cabecalho da aba: navegacao, titulo, contexto, veredito e alertas.
  empurrar(['← Visao Geral'].concat(linhaFormato(largura - 1, '')));
  empurrar([String(comp.projeto || nomeAba)].concat(linhaFormato(largura - 1, '')));
  const contexto = [comp.categoria ? String(comp.categoria) : 'categoria nao informada',
    'gerado em ' + String(geradoEm || 'data nao informada')].join(' · ');
  empurrar([contexto].concat(linhaFormato(largura - 1, '')));
  const veredito = vereditoProjeto(comp, metricas, situacao, colunas);
  empurrar([veredito.texto].concat(linhaFormato(largura - 1, '')));
  const alertas = alertasProjeto(metricas, situacao, colunas);
  const linhaAlertas = alertas.length ? matriz.length + 1 : 0;
  if (alertas.length) empurrar([alertas.join('  ·  ')].concat(linhaFormato(largura - 1, '')));

  const linhaProdutos = matriz.length + 1;
  empurrar(['Candidato'].concat(colunas));
  const linhaVereditos = matriz.length + 1;
  empurrar(['VEREDITO'].concat(vereditosProdutos(metricas, situacao)));
  fundos[fundos.length - 1] = linhaFormato(largura, TEMA.faixa);

  if (metricas.length) {
    adicionarSecao(matriz, formatos, notas, fundos, alinhamentos, largura, 'SCORE');
    adicionarLinhaMetrica(matriz, formatos, notas, fundos, alinhamentos, 'Score', metricas, 'score', '0.0');
    adicionarLinhaMetrica(matriz, formatos, notas, fundos, alinhamentos, 'Confianca', metricas, 'confianca', '0%');
    ['qualidade', 'valor', 'risco', 'aderencia', 'conveniencia'].forEach(function (eixo) {
      adicionarLinhaMetrica(
        matriz, formatos, notas, fundos, alinhamentos, tituloCampo(eixo), metricas, eixo, '0%'
      );
    });
  }

  adicionarSecao(matriz, formatos, notas, fundos, alinhamentos, largura, 'PRECOS');
  let secaoAnterior = 'precos';
  linhas.forEach(function (linha) {
    if (linha.secao === 'atributos' && secaoAnterior !== 'atributos') {
      adicionarSecao(matriz, formatos, notas, fundos, alinhamentos, largura, 'ATRIBUTOS');
      secaoAnterior = 'atributos';
    }
    const renderizada = renderizarLinha(linha, colunas.length);
    matriz.push([linha.rotulo || 'Sem rotulo'].concat(renderizada.valores));
    formatos.push(['@'].concat(renderizada.formatos));
    notas.push([''].concat(renderizada.notas));
    fundos.push(linhaFormato(largura, TEMA.branco));
    alinhamentos.push(['left'].concat(renderizada.alinhamentos));
  });

  const faixa = aba.getRange(1, 1, matriz.length, largura);
  faixa.setNumberFormats(formatos);
  faixa.setValues(matriz);
  faixa.setNotes(notas);
  faixa.setBackgrounds(fundos);
  faixa.setHorizontalAlignments(alinhamentos);
  aba.getRange(1, 1).setRichTextValue(
    SpreadsheetApp.newRichTextValue().setText('← Visao Geral').setLinkUrl(linkVisao).build()
  );
  faixa.setFontFamily('Inter').setFontColor(TEMA.tinta).setFontSize(10)
    .setVerticalAlignment('middle').setWrap(true);
  // Numeros tabulares em Roboto Mono; texto em Inter (derivado do alinhamento
  // que cada linha ja declarou na montagem).
  const familias = alinhamentos.map(function (linhaAlinh) {
    return linhaAlinh.map(function (alinh) {
      return alinh === 'right' ? 'Roboto Mono' : 'Inter';
    });
  });
  faixa.setFontFamilies(familias);

  aba.getRange(1, 1).setFontColor(TEMA.apagada).setFontSize(9);
  aba.getRange(2, 1, 1, largura).merge()
    .setFontSize(14).setFontWeight('bold').setFontColor(TEMA.tinta);
  aba.getRange(3, 1, 1, largura).merge().setFontSize(9).setFontColor(TEMA.apagada);
  aba.getRange(4, 1, 1, largura).merge()
    .setFontSize(11).setFontWeight('bold').setFontColor(veredito.cor).setBackground(TEMA.faixa);
  if (linhaAlertas) {
    aba.getRange(linhaAlertas, 1, 1, largura).merge()
      .setFontSize(9).setFontColor(TEMA.secundaria);
  }
  aba.getRange(linhaProdutos, 2, 1, Math.max(1, colunas.length)).setFontSize(13).setFontWeight('bold');
  aba.getRange(linhaProdutos, 1, 1, largura).setFontWeight('bold')
    .setBorder(false, false, true, false, false, false, TEMA.base, SpreadsheetApp.BorderStyle.SOLID);
  aba.getRange(linhaVereditos, 1, 1, largura).setFontWeight('bold');
  colorirProdutos(aba, linhaProdutos, metricas, situacao, matriz.length);
  estilizarSecoes(aba, matriz, largura);
  aba.getRange(1, 1, matriz.length, 1)
    .setFontWeight('bold').setFontColor(TEMA.secundaria);
  aba.setColumnWidth(1, 220);
  for (let c = 2; c <= largura; c += 1) aba.setColumnWidth(c, 220);
  aba.autoResizeRows(1, matriz.length);
  const rodape = matriz.length + 2;
  aba.getRange(rodape, 1, 1, largura).merge()
    .setValue('Espelho gerado em ' + String(geradoEm || 'data nao informada') +
      ' · edite o repositorio, nao esta planilha')
    .setFontFamily('Inter').setFontSize(9).setFontColor(TEMA.apagada);
  // Congela ate a linha de produtos: o cabecalho mesclado fica inteiro acima
  // da divisoria horizontal; coluna congelada cortaria as mesclas.
  aba.setFrozenRows(linhaProdutos);
  aba.setFrozenColumns(0);
  aba.setTabColor(TEMA.lider);
  protegerEspelho(aba);

  if (metricas.length) {
    inserirGraficosComparativo(aba, colunas, metricas, situacao, matriz.length + 4);
  }
}

function vereditoProjeto(comp, metricas, situacao, colunas) {
  if (comp.escolhido || comp.data_decisao) {
    const data = comp.data_decisao ? ' em ' + String(comp.data_decisao) : '';
    return {
      texto: '● Decisao fechada: ' + String(comp.escolhido || 'registrada no repositorio') + data,
      cor: TEMA.decidido,
    };
  }
  if (!metricas.length) {
    return {
      texto: '◐ Score indisponivel neste payload; comparacao textual preservada',
      cor: TEMA.pesquisando,
    };
  }
  const scores = metricas.map(function (m, indice) {
    return situacao[indice] === 'elegivel' && typeof m.score === 'number' ? m.score : null;
  });
  const validos = scores.map(function (score, indice) {
    return { score: score, indice: indice };
  }).filter(function (item) { return item.score !== null; })
    .sort(function (a, b) { return b.score - a.score; });
  if (!validos.length) {
    return { texto: '◔ Nenhum candidato elegivel ainda — a pesquisa continua', cor: TEMA.aguardando };
  }
  const melhor = validos[0];
  const nomeMelhor = String(colunas[melhor.indice] || 'candidato');
  if (validos.length > 1 && melhor.score - validos[1].score <= 3) {
    const nomes = validos.filter(function (item) { return melhor.score - item.score <= 3; })
      .map(function (item) { return String(colunas[item.indice]); });
    return {
      texto: '◐ Empate tecnico: ' + nomes.join(' e ') +
        ' separados por ' + (melhor.score - validos[1].score).toFixed(1) +
        ' ponto(s); diferenca ate 3 e empate',
      cor: TEMA.pesquisando,
    };
  }
  const vantagem = validos.length > 1
    ? ' — ' + (melhor.score - validos[1].score).toFixed(1) + ' ponto(s) a frente de ' +
      String(colunas[validos[1].indice])
    : '';
  return {
    texto: '● Lider: ' + nomeMelhor + ' · score ' + melhor.score.toFixed(1) + vantagem,
    cor: TEMA.lider,
  };
}

function alertasProjeto(metricas, situacao, colunas) {
  // So fatos do payload (schema 3). Com payload antigo os campos faltam e a
  // faixa simplesmente nao aparece — nunca um alerta inventado.
  const vencidos = [];
  const soWeb = [];
  const cortados = [];
  metricas.forEach(function (m, indice) {
    const nome = String(colunas[indice] || 'candidato');
    if (m.vencida) vencidos.push(nome);
    if (situacao[indice] === 'elegivel' && m.fonte && m.fonte !== 'manual') soWeb.push(nome);
    if (situacao[indice] === 'cortado') {
      const motivos = Array.isArray(m.motivos_corte) && m.motivos_corte.length
        ? ' (' + m.motivos_corte.join('; ') + ')' : '';
      cortados.push(nome + motivos);
    }
  });
  const partes = [];
  if (vencidos.length) partes.push('▲ Cotacao vencida: ' + vencidos.join(', '));
  if (soWeb.length) partes.push('◔ Preco nao confirmado (so fonte web): ' + soWeb.join(', '));
  if (cortados.length) partes.push('▲ Fora do gate: ' + cortados.join(', '));
  return partes;
}

function vereditosProdutos(metricas, situacao) {
  const scores = situacao.map(function (estado, indice) {
    const metrica = metricas[indice] || {};
    return estado === 'elegivel' && typeof metrica.score === 'number' ? metrica.score : null;
  });
  const validos = scores.filter(function (score) { return score !== null; }).sort(function (a, b) { return b - a; });
  const melhor = validos.length ? validos[0] : null;
  const empate = validos.length > 1 && melhor - validos[1] <= 3;
  return situacao.map(function (estado, indice) {
    const score = scores[indice];
    if (estado === 'cortado') {
      const motivos = metricas[indice] && Array.isArray(metricas[indice].motivos_corte)
        ? metricas[indice].motivos_corte : [];
      return motivos.length ? '▲ Bloqueado: ' + motivos.join('; ') : '▲ Bloqueado pelo gate';
    }
    if (estado === 'sem_cotacao') return '◔ Sem cotacao';
    if (score === null) return '◐ Pesquisando';
    if (empate && melhor - score <= 3) return '◐ Empate tecnico · score ' + score.toFixed(1);
    if (score === melhor) return '● Lider · score ' + score.toFixed(1);
    return '◐ Atrás por ' + (melhor - score).toFixed(1) + ' pontos';
  });
}

function abaLimpa(planilha, nome) {
  let aba = planilha.getSheetByName(nome);
  if (!aba) aba = planilha.insertSheet(nome);
  if (aba.isSheetHidden()) aba.showSheet();
  aba.getCharts().forEach(function (grafico) { aba.removeChart(grafico); });
  aba.getBandings().forEach(function (faixa) { faixa.remove(); });
  if (aba.getFilter()) aba.getFilter().remove();
  aba.setConditionalFormatRules([]);
  aba.getRange(1, 1, aba.getMaxRows(), aba.getMaxColumns()).breakApart();
  aba.clear();
  aba.setFrozenRows(0);
  aba.setFrozenColumns(0);
  aba.setHiddenGridlines(true);
  return aba;
}

function renderizarLinha(linha, quantidade) {
  const tipados = Array.isArray(linha.valores_tipados) ? linha.valores_tipados : null;
  const valores = [];
  const formatos = [];
  const notas = [];
  const alinhamentos = [];
  for (let i = 0; i < quantidade; i += 1) {
    if (tipados && tipados[i]) {
      const item = tipados[i];
      const tipo = item.tipo || 'texto';
      valores.push(tipo === 'vazio' ? '' : item.valor);
      formatos.push(formatoTipo(tipo));
      const estrelas = item.estrelas ? item.estrelas + '/5 estrelas' : '';
      // Ausente nunca vira zero: celula vazia com nota explicando a ausencia.
      notas.push([item.detalhe || (tipo === 'vazio' ? 'Sem dado' : ''), estrelas]
        .filter(String).join(' | '));
      alinhamentos.push(tipo === 'moeda' || tipo === 'nota' || tipo === 'numero' ? 'right' : 'left');
    } else {
      const legado = (linha.valores || [])[i];
      if (linha.tipo === 'estrela' && legado && typeof legado === 'object') {
        valores.push(legado.texto + (legado.estrelas ? '  ' + estrelas(legado.estrelas) : ''));
      } else {
        valores.push(legado === undefined || legado === null ? '' : legado);
      }
      formatos.push('@');
      notas.push('Payload legado; valor preservado como texto.');
      alinhamentos.push('left');
    }
  }
  return { valores: valores, formatos: formatos, notas: notas, alinhamentos: alinhamentos };
}

function formatoTipo(tipo) {
  if (tipo === 'moeda') return 'R$ #,##0.00';
  if (tipo === 'nota') return '0.0 "estrela"';
  if (tipo === 'numero') return '0.##';
  if (tipo === 'booleano') return 'General';
  return '@';
}

function adicionarLinhaMetrica(matriz, formatos, notas, fundos, alinhamentos, rotulo, metricas, campo, formato) {
  matriz.push([rotulo].concat(metricas.map(function (m) {
    const valor = m[campo];
    const eixo = ['qualidade', 'valor', 'risco', 'aderencia', 'conveniencia'].indexOf(campo) >= 0;
    return valor !== undefined && valor !== null && valor !== '' ? valor : (eixo ? 'sem dado' : '');
  })));
  formatos.push(['@'].concat(metricas.map(function () { return formato; })));
  notas.push([''].concat(metricas.map(function (m) {
    if (m[campo] === undefined || m[campo] === null || m[campo] === '') return 'Sem dado';
    if (campo === 'score') return 'Score total de 0 a 100, calculado pelo motor de ranking do repositorio.';
    return '';
  })));
  fundos.push(linhaFormato(metricas.length + 1, TEMA.branco));
  alinhamentos.push(['left'].concat(linhaFormato(metricas.length, 'right')));
}

function adicionarSecao(matriz, formatos, notas, fundos, alinhamentos, largura, titulo) {
  matriz.push([titulo].concat(linhaFormato(largura - 1, '')));
  formatos.push(linhaFormato(largura, '@'));
  notas.push(linhaFormato(largura, ''));
  fundos.push(linhaFormato(largura, TEMA.faixa));
  alinhamentos.push(linhaFormato(largura, 'left'));
}

function estilizarSecoes(aba, matriz, largura) {
  matriz.forEach(function (linha, indice) {
    if (['SCORE', 'PRECOS', 'ATRIBUTOS'].indexOf(linha[0]) >= 0) {
      aba.getRange(indice + 1, 1, 1, largura).setBackground(TEMA.faixa)
        .setFontFamily('Inter').setFontSize(10).setFontWeight('bold')
        .setFontColor(TEMA.secundaria)
        .setBorder(false, false, true, false, false, false, TEMA.linha, SpreadsheetApp.BorderStyle.SOLID);
    }
    if (linha[0] === 'Preco') {
      aba.getRange(indice + 1, 2, 1, Math.max(1, largura - 1)).setFontWeight('bold');
    }
  });
}

function inserirGraficosComparativo(aba, colunas, metricas, situacao, ancora) {
  const quantidade = colunas.length;
  const scores = metricas.map(function (m, indice) {
    return situacao[indice] === 'elegivel' && typeof m.score === 'number' ? m.score : null;
  });
  const validos = scores.filter(function (score) { return score !== null; })
    .slice().sort(function (a, b) { return b - a; });
  const melhor = validos.length ? validos[0] : null;
  const empate = validos.length > 1 && melhor - validos[1] <= 3;
  const camposEixo = ['qualidade', 'valor', 'risco', 'aderencia', 'conveniencia'];
  const nomesEixos = camposEixo.map(tituloCampo);
  const colunaFonte = larguraGraficoFonte(colunas);

  // Fontes contiguas, orientadas como o grafico espera, fora da area
  // visivel. Intervalos separados e transpostos ja produziram graficos
  // vazios e rotulos trocados (Versao 7).
  // Sem dado fica fora do grafico (celula vazia), nunca zero.
  const rankingDados = [['Produto', 'Lider', 'Demais']];
  colunas.forEach(function (produto, indice) {
    if (scores[indice] === null) return;
    const destaque = scores[indice] === melhor || (empate && melhor - scores[indice] <= 3);
    rankingDados.push([String(produto), destaque ? scores[indice] : '', destaque ? '' : scores[indice]]);
  });
  const eixosDados = [['Eixo'].concat(colunas)];
  camposEixo.forEach(function (campo, indiceEixo) {
    eixosDados.push([nomesEixos[indiceEixo]].concat(metricas.map(function (m) {
      return typeof m[campo] === 'number' ? m[campo] : '';
    })));
  });

  const ultimaColunaFonte = colunaFonte + Math.max(2, quantidade);
  if (aba.getMaxColumns() < ultimaColunaFonte) {
    aba.insertColumnsAfter(aba.getMaxColumns(), ultimaColunaFonte - aba.getMaxColumns());
  }
  const rankingFonte = aba.getRange(ancora, colunaFonte, rankingDados.length, 3);
  rankingFonte.setValues(rankingDados);
  const linhaFonteEixos = ancora + rankingDados.length + 1;
  const eixosFonte = aba.getRange(linhaFonteEixos, colunaFonte, eixosDados.length, quantidade + 1);
  eixosFonte.setValues(eixosDados);
  aba.getRange(
    ancora, colunaFonte, linhaFonteEixos + eixosDados.length - ancora,
    Math.max(3, quantidade + 1)
  ).setFontColor(TEMA.branco).setBackground(TEMA.branco).setFontSize(6);
  aba.setColumnWidths(colunaFonte, Math.max(3, quantidade + 1), 24);

  // Duas series, uma celula vazia por linha: o Sheets nao pinta pontos
  // isolados, entao o destaque do lider (azul) contra os demais (cinza) sai
  // por serie. Em empate tecnico, todos os empatados ficam azuis.
  if (rankingDados.length > 1) {
    const ranking = aba.newChart().setChartType(Charts.ChartType.BAR)
      .addRange(rankingFonte).setNumHeaders(1)
      .setOption('title', 'Score total por candidato (azul = lideranca)')
      .setOption('fontName', 'Inter')
      .setOption('legend', { position: 'none' })
      .setOption('colors', [TEMA.lider, TEMA.apagada])
      .setOption('hAxis', { viewWindow: { min: 0, max: 100 }, textStyle: { color: TEMA.apagada } })
      .setPosition(ancora, 1, 0, 0).build();
    aba.insertChart(ranking);
  }

  if (quantidade <= 3) {
    const eixos = aba.newChart().setChartType(Charts.ChartType.COLUMN)
      .addRange(eixosFonte).setNumHeaders(1)
      .setOption('title', 'Cinco eixos da decisao (0 a 1)')
      .setOption('fontName', 'Inter')
      .setOption('legend', { position: quantidade > 1 ? 'bottom' : 'none' })
      .setOption('colors', [TEMA.lider, TEMA.slot2, TEMA.slot3].slice(0, quantidade))
      .setOption('vAxis', { viewWindow: { min: 0, max: 1 }, textStyle: { color: TEMA.apagada } })
      .setPosition(ancora + 16, 1, 0, 0).build();
    aba.insertChart(eixos);
  } else {
    for (let indice = 0; indice < quantidade; indice += 1) {
      const mini = aba.newChart().setChartType(Charts.ChartType.COLUMN)
        .addRange(aba.getRange(linhaFonteEixos, colunaFonte, eixosDados.length, 1))
        .addRange(aba.getRange(linhaFonteEixos, colunaFonte + indice + 1, eixosDados.length, 1))
        .setNumHeaders(1).setOption('title', String(colunas[indice]) + ' (0 a 1)')
        .setOption('fontName', 'Inter').setOption('legend', { position: 'none' })
        .setOption('colors', [TEMA.lider])
        .setOption('vAxis', { viewWindow: { min: 0, max: 1 }, textStyle: { color: TEMA.apagada } })
        .setPosition(ancora + 16 + Math.floor(indice / 2) * 15, 1 + (indice % 2) * 6, 0, 0).build();
      aba.insertChart(mini);
    }
  }
}

function larguraGraficoFonte(colunas) {
  return colunas.length + 9;
}

function colorirProdutos(aba, linha, metricas, situacao, quantidadeLinhas) {
  const scores = situacao.map(function (estado, indice) {
    const metrica = metricas[indice] || {};
    return estado === 'elegivel' && typeof metrica.score === 'number' ? metrica.score : null;
  });
  const validos = scores.filter(function (score) { return score !== null; }).sort(function (a, b) { return b - a; });
  const melhor = validos.length ? validos[0] : null;
  const empate = validos.length > 1 && melhor - validos[1] <= 3;
  situacao.forEach(function (estado, indice) {
    const score = scores[indice];
    const destaque = score !== null && (score === melhor || (empate && melhor - score <= 3));
    if (destaque) aba.getRange(linha, indice + 2, quantidadeLinhas - linha + 1, 1)
      .setBackground(TEMA.liderFundo).setFontWeight('bold');
    aba.getRange(linha, indice + 2).setFontColor(destaque ? TEMA.tinta : TEMA.secundaria);
    let cor = TEMA.secundaria;
    if (estado === 'cortado') cor = TEMA.vencida;
    else if (estado === 'sem_cotacao') cor = TEMA.aguardando;
    else if (empate && score !== null && melhor - score <= 3) cor = TEMA.pesquisando;
    else if (score === melhor) cor = TEMA.lider;
    aba.getRange(linha + 1, indice + 2).setFontColor(cor).setHorizontalAlignment('left');
  });
}

// --------------------------------------------------------------- Utilidades

function aplicarFaixas(faixa) {
  const cores = [];
  for (let r = 0; r < faixa.getNumRows(); r += 1) {
    cores.push(linhaFormato(faixa.getNumColumns(), r % 2 ? TEMA.faixa : TEMA.branco));
  }
  faixa.setBackgrounds(cores);
}

function protegerEspelho(aba) {
  aba.getProtections(SpreadsheetApp.ProtectionType.SHEET).forEach(function (protecao) {
    if (protecao.canEdit()) protecao.remove();
  });
  aba.protect().setDescription('Espelho gerado por script; edite o repositorio, nao aqui.')
    .setWarningOnly(true);
}

function formatarColunaPorNome(aba, campos, campo, linha, quantidade, formato) {
  const indice = campos.indexOf(campo);
  if (indice >= 0 && quantidade > 0) aba.getRange(linha, indice + 1, quantidade, 1).setNumberFormat(formato);
}

function colunasOuFallback(recebidas, fallback, obrigatoria, avisos) {
  if (!Array.isArray(recebidas) || !recebidas.length) return fallback.slice();
  const unicas = [];
  recebidas.forEach(function (campo) {
    if (typeof campo === 'string' && unicas.indexOf(campo) < 0) unicas.push(campo);
  });
  if (unicas.indexOf(obrigatoria) < 0) {
    unicas.unshift(obrigatoria);
    adicionarAviso(avisos, 'Coluna obrigatoria acrescentada por fallback: ' + obrigatoria);
  }
  return unicas;
}

function coletarAvisos(dados) {
  const avisos = [];
  const camposVisao = colunasOuFallback(
    dados.visao_geral_colunas, CAMPOS_VISAO_FALLBACK, 'projeto', avisos
  );
  const camposMetricas = colunasOuFallback(
    dados.metricas_colunas, CAMPOS_METRICAS_FALLBACK, 'projeto', avisos
  ).filter(function (campo) { return campo !== 'projeto'; });
  if (dados.schema_versao !== undefined && dados.schema_versao > SCHEMA_SUPORTADO) {
    adicionarAviso(avisos, 'Schema ' + dados.schema_versao + ' e mais novo que o suportado ' + SCHEMA_SUPORTADO);
  }
  avisarCampos(dados, [
    'token', 'schema_versao', 'gerado_em', 'visao_geral_colunas',
    'metricas_colunas', 'visao_geral', 'comparativos',
  ], 'payload', avisos);
  const camposVisaoConhecidos = CAMPOS_VISAO_FALLBACK.concat(camposVisao, [
    'manual', 'dias_ate_decisao', 'escolhido', 'aguardando_preco',
    'data_decisao', 'cotacoes_vencidas', 'abaixo_confianca_minima', 'empate_tecnico',
  ]);
  (Array.isArray(dados.visao_geral) ? dados.visao_geral : []).forEach(function (linha, indice) {
    avisarCampos(linha, camposVisaoConhecidos, 'visao geral ' + indice, avisos);
  });
  (Array.isArray(dados.comparativos) ? dados.comparativos : []).forEach(function (comp, ci) {
    avisarCampos(comp, ['projeto', 'categoria', 'escolhido', 'data_decisao', 'colunas', 'situacao', 'linhas', 'metricas'], 'comparativo ' + ci, avisos);
    (Array.isArray(comp.metricas) ? comp.metricas : []).forEach(function (metrica, mi) {
      avisarCampos(metrica, camposMetricas.concat(['vencida', 'fonte', 'motivos_corte']), 'metrica ' + ci + '/' + mi, avisos);
    });
    (Array.isArray(comp.linhas) ? comp.linhas : []).forEach(function (linha, li) {
      avisarCampos(linha, ['rotulo', 'tipo', 'secao', 'valores', 'valores_tipados'], 'linha ' + ci + '/' + li, avisos);
      (Array.isArray(linha.valores_tipados) ? linha.valores_tipados : []).forEach(function (valor, vi) {
        avisarCampos(
          valor, ['tipo', 'valor', 'texto', 'estrelas', 'detalhe'],
          'valor tipado ' + ci + '/' + li + '/' + vi, avisos
        );
      });
      if (linha.tipo !== 'texto' && linha.tipo !== 'estrela') {
        adicionarAviso(avisos, 'Tipo desconhecido tratado como texto: ' + String(linha.tipo));
      }
    });
  });
  if (!Array.isArray(dados.visao_geral)) adicionarAviso(avisos, 'visao_geral ausente ou invalida');
  if (!Array.isArray(dados.comparativos)) adicionarAviso(avisos, 'comparativos ausente ou invalido; abas antigas preservadas');
  return avisos;
}

function avisarCampos(objeto, conhecidos, contexto, avisos) {
  if (!objeto || typeof objeto !== 'object') return;
  Object.keys(objeto).forEach(function (campo) {
    if (conhecidos.indexOf(campo) < 0) adicionarAviso(avisos, contexto + ': campo ignorado ' + campo);
  });
}

function adicionarAviso(avisos, aviso) {
  if (avisos.length < 50 && avisos.indexOf(aviso) < 0) avisos.push(aviso);
}

function nomeAbaProjeto(projeto, usados) {
  const original = String(projeto || 'projeto');
  let nome = original.replace(/[\[\]:*?\/\\]/g, '-');
  if (nome.length > 100 || usados[nome]) {
    const sufixo = digestHex(original).slice(0, 8);
    nome = nome.slice(0, 91) + '-' + sufixo;
  }
  let tentativa = nome;
  let contador = 2;
  while (usados[tentativa]) {
    tentativa = nome.slice(0, 96) + '-' + contador;
    contador += 1;
  }
  usados[tentativa] = true;
  return tentativa;
}

const PROPRIEDADE_ABAS_GERADAS = 'abas_geradas_pelo_script';

function abasGeradasRegistradas() {
  const bruto = PropertiesService.getDocumentProperties().getProperty(PROPRIEDADE_ABAS_GERADAS);
  if (!bruto) return {};
  try {
    const registro = JSON.parse(bruto);
    return (registro && typeof registro === 'object' && !Array.isArray(registro)) ? registro : {};
  } catch (err) {
    return {};
  }
}

function registrarAbasGeradas(nomes) {
  const registro = {};
  nomes.forEach(function (nome) { registro[nome] = true; });
  PropertiesService.getDocumentProperties().setProperty(PROPRIEDADE_ABAS_GERADAS, JSON.stringify(registro));
}

function limparAbasOrfas(planilha, projetosAtuais) {
  // Antes: uma aba "parecia gerada" so pelo nome (padrao /^20\d\d-/, etc.) -
  // uma aba criada A MAO com nome parecido (ex.: "2026-manual") caia no
  // mesmo padrao e era apagada. Agora so apaga o que o PROPRIO script
  // escreveu numa sincronizacao anterior (registro persistido na planilha) -
  // uma aba nunca escrita por ele nunca entra no registro, entao nunca e
  // candidata a remocao so por causa do nome.
  const manter = { 'Visao Geral': true };
  projetosAtuais.forEach(function (nome) { manter[nome] = true; });
  const conhecidas = abasGeradasRegistradas();
  planilha.getSheets().forEach(function (aba) {
    const nome = aba.getName();
    const geradaPeloScript = conhecidas[nome] === true;
    if (geradaPeloScript && !manter[nome] && planilha.getSheets().length > 1) planilha.deleteSheet(aba);
  });
  registrarAbasGeradas(projetosAtuais);
}

function linhaFormato(tamanho, valor) {
  return Array.apply(null, Array(tamanho)).map(function () { return valor; });
}

function tituloCampo(campo) {
  return String(campo || '').replace(/_/g, ' ').replace(/\b\w/g, function (letra) {
    return letra.toUpperCase();
  });
}

function estrelas(quantidade) {
  return Array(quantidade + 1).join('★');
}

function digestHex(texto) {
  return Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256, texto, Utilities.Charset.UTF_8
  ).map(function (byte) {
    const valor = (byte + 256) % 256;
    return ('0' + valor.toString(16)).slice(-2);
  }).join('');
}

function resposta(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
```

**Nota histórica — falhas já encontradas nesta integração:**

| Versão | Bug | Sintoma |
|---|---|---|
| 1 → 2 | `DriveApp.getRoot()` não existe (é `getRootFolder()`) | `TypeError`, sincronização quebrada por completo |
| 2 → 3 | pasta buscada só na raiz do Drive | criou pasta duplicada na raiz, já que a certa é aninhada |
| 3 → 4 | `comp.colunas` ignorado | tabela sem cabeçalho: dava para ver preço e nota, mas **não qual coluna era qual produto** |
| 4 → 5 | payload e receptor evoluíam sem contrato compatível | a ordem entre commit e deploy podia quebrar a `Visao Geral` |
| 5 | deploy feito por uma conta editora | o Web App perdeu acesso à pasta que pertence a conta-comercial |
| 5 → 7 | coluna congelada atravessava títulos mesclados | exceção em tempo de execução, apesar do código salvo e publicado |
| 7 → 8 | gráficos usavam intervalos horizontais separados e transpostos | ranking vazio e eixos com rótulos misturados, sem erro de sincronização |
| 8 → 9 | visão geral comparava scores relativos de compras diferentes | gráfico conceitualmente enganoso, substituído por contagens de pendências comparáveis |

Os bugs visuais só apareceram quando a planilha foi aberta. Vale a lição:
resposta HTTP, execução “Concluído” no Apps Script e contagens corretas não
provam que a planilha ficou legível. O `doPost` captura exceções e pode devolver
HTTP 200 com `ok: false`; por isso o cliente também precisa exibir `detalhe`.
O procedimento completo e as razões estão em
[`aprendizados-google-sheets.md`](aprendizados-google-sheets.md).

## Implantação (para redeploy futuro)

1. Entre como **`conta-comercial@exemplo.com`**, proprietária da pasta e do projeto.
   Compartilhar o script com outro editor não transfere a identidade de
   execução. Confirme o e-mail no avatar e na tela de implantação; “executar
   como eu” significa a conta que está publicando.
2. Editor do projeto → editar o `Código.gs` → salvar (Ctrl+S).
3. Implantar → Gerenciar implantações → editar a implantação existente →
   Versão: **Nova versão** → Implantar. (Isso preserva a mesma URL /exec —
   nunca criar uma implantação nova do zero, senão a URL muda e o
   `integracao_sheets.json` local fica desatualizado.)
4. Rode a sincronização duas vezes e abra a planilha. Confira dados, tipos,
   filtros, links e gráficos; a segunda execução prova que não houve duplicação.

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

**Timeout:** a Versão 4 levou até ~47s com 8 projetos no teste de 2026-09-04
porque escrevia linha por linha. As Versões 8 e 9 usam `setValues` em lote, mas a
renderização dos gráficos ainda pode passar de um minuto. Por isso o cliente
Python continua com timeout de 120s; **não reduza esse valor**.

## Estado implantado e validado

- O cliente Python envia schema 3. Os campos são aditivos, e o receptor mantém
  fallback para o payload anterior; a ordem de deploy não quebra a planilha.
- O Code.gs V9 preserva fallback para payload antigo e registra campos
  desconhecidos sem rejeitar a sincronização inteira.
- A V9 troca o gráfico inválido de scores entre projetos por pendências
  comparáveis, acrescenta fila de atenção, contexto, veredito e alertas por
  projeto, e preserva tipos numéricos e fontes contíguas de gráficos.
- **VERSÃO 9 IMPLANTADA E VERIFICADA:** publicada em 05/09/2026 pela conta
  `conta-comercial@exemplo.com` na implantação existente. Duas sincronizações
  consecutivas devolveram 8 projetos e 8 comparativos. A planilha ficou com 9
  abas, sem abas órfãs ou erros de célula, e os gráficos foram inspecionados no
  arquivo real no desktop e em largura de celular.
