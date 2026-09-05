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

## Code.gs (versão 5 preparada, deploy pendente)

> **ATENÇÃO:** o código abaixo ainda não está implantado. A versão publicada
> continua sendo a Versão 4. O deploy exige navegador autenticado na conta
> conta-comercial e confirmação em duas etapas pelo dono. Não rode
> `sincronizar-planilha` esperando este visual antes desse deploy.

```javascript
const TOKEN = '...'; // cole aqui uma senha longa aleatoria. O valor real vive
                     // so no Code.gs (na conta conta-comercial) e no
                     // integracao_sheets.json local. Nunca neste arquivo.
const PASTA_ID = '1MyR5NNhHz5Q2RtSHbgPZxXDV3kRM2ARU';
const PLANILHA_NOME = 'Central de Compras - Cotacoes e Comparacoes';
const SCHEMA_SUPORTADO = 2;
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

  try {
    const avisos = coletarAvisos(dados);
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
    });
    escreverVisaoGeral(
      planilha, Array.isArray(dados.visao_geral) ? dados.visao_geral : [],
      camposVisao, dados.gerado_em, avisos, comparativos, destinos
    );

    // Se o campo sumir por regressao, preservar abas e avisar e mais seguro
    // que apagar tudo. Com uma lista valida, remove so abas geradas/orfas.
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
    return resposta({ ok: false, error: 'falha na sincronizacao', detalhe: String(err) });
  } finally {
    bloqueio.releaseLock();
  }
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

function escreverVisaoGeral(planilha, linhas, campos, geradoEm, avisos, comparativos, destinos) {
  const aba = abaLimpa(planilha, 'Visao Geral');
  const largura = Math.max(1, campos.length);
  const ordenadas = linhas.slice().sort(function (a, b) {
    return (Number(b.score) || -1) - (Number(a.score) || -1);
  });
  const tabela = [campos.map(tituloCampo)].concat(ordenadas.map(function (linha) {
    return campos.map(function (c) {
      if (c === 'estado') return estadoVisao(linha);
      return linha[c] !== undefined && linha[c] !== null ? linha[c] : '';
    });
  }));

  const ativos = linhas.filter(function (linha) {
    return !linha.data_decisao && linha.estado !== 'comprado';
  }).length;
  const decididos = linhas.filter(function (linha) {
    return Boolean(linha.data_decisao || linha.escolhido || linha.estado === 'comprado');
  }).length;
  const aguardando = linhas.reduce(function (total, linha) {
    return total + (Number(linha.aguardando_preco) || 0);
  }, 0);
  const vencidas = linhas.reduce(function (total, linha) {
    return total + (Number(linha.cotacoes_vencidas) || 0);
  }, 0);
  const indicadores = [
    ['PROJETOS ATIVOS', ativos],
    ['DECISOES FECHADAS', decididos],
    ['AGUARDANDO PRECO', aguardando],
    ['COTACOES VENCIDAS', vencidas ? '▲ ' + vencidas : 0],
  ];
  indicadores.forEach(function (indicador, indice) {
    const coluna = indice * 2 + 1;
    aba.getRange(1, coluna, 1, 2).merge().setValue(indicador[0]);
    aba.getRange(2, coluna, 1, 2).merge().setValue(indicador[1]);
  });
  aba.getRange(3, 1, 1, 8).merge()
    .setValue('Central de Compras · espelho de decisao')
    .setNote(avisos.length ? avisos.join('\n') : 'Sem avisos de compatibilidade.');
  const formatosTabela = [linhaFormato(largura, '@')].concat(ordenadas.map(function () {
    return campos.map(function (campo) {
      if (campo === 'score') return '0.0';
      if (campo === 'confianca') return '0%';
      if (['cotacoes', 'manual', 'dias_ate_decisao', 'aguardando_preco'].indexOf(campo) >= 0) return '0';
      return '@';
    });
  }));
  const faixaTabela = aba.getRange(5, 1, tabela.length, largura);
  faixaTabela.setNumberFormats(formatosTabela);
  faixaTabela.setValues(tabela);

  aba.getRange(1, 1, 3, Math.max(8, largura)).setFontFamily('Inter');
  aba.getRange(1, 1, 1, 8).setFontSize(10).setFontWeight('bold')
    .setFontColor(TEMA.secundaria).setBackground(TEMA.faixa);
  aba.getRange(2, 1, 1, 8).setFontSize(24).setFontWeight('bold')
    .setFontColor(TEMA.tinta).setBackground(TEMA.branco);
  if (vencidas) aba.getRange(2, 7, 1, 2).setFontColor(TEMA.vencida);
  aba.getRange(3, 1, 1, 8).setFontSize(9).setFontColor(TEMA.apagada)
    .setHorizontalAlignment('left');
  const cabecalho = aba.getRange(5, 1, 1, largura);
  cabecalho.setBackground(TEMA.faixa).setFontColor(TEMA.secundaria)
    .setFontWeight('bold').setFontFamily('Inter').setHorizontalAlignment('left');

  if (ordenadas.length) {
    const corpo = aba.getRange(6, 1, ordenadas.length, largura);
    corpo.setFontFamily('Inter').setFontColor(TEMA.tinta).setFontSize(10)
      .setVerticalAlignment('middle').setWrap(true);
    aplicarFaixas(corpo);
    aplicarLinksProjetos(planilha, aba, ordenadas, campos, comparativos, destinos);
    colorirEstadosVisao(aba, ordenadas, campos);
    formatarColunasVisao(aba, campos, ordenadas.length, 6);
    aba.getRange(5, 1, ordenadas.length + 1, largura).createFilter();
    inserirGraficoVisao(aba, campos, ordenadas.length, 6, largura + 2);
  }
  aplicarLargurasVisao(aba, campos);
  const rodape = 7 + ordenadas.length;
  aba.getRange(rodape, 1, 1, Math.max(1, largura)).merge()
    .setValue('Espelho gerado em ' + String(geradoEm || 'data nao informada') +
      ' · a fonte e o cotacoes.csv de cada projeto')
    .setFontFamily('Inter').setFontSize(9).setFontColor(TEMA.apagada);
  aba.setFrozenRows(5);
  aba.setFrozenColumns(1);
  aba.setTabColor(TEMA.lider);
  protegerEspelho(aba);
}

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

  matriz.push(['← Visao Geral'].concat(colunas));
  formatos.push(linhaFormato(largura, '@'));
  notas.push(linhaFormato(largura, ''));
  fundos.push(linhaFormato(largura, TEMA.branco));
  matriz.push(['VEREDITO'].concat(vereditosProdutos(metricas, situacao)));
  formatos.push(linhaFormato(largura, '@'));
  notas.push(linhaFormato(largura, ''));
  fundos.push(linhaFormato(largura, TEMA.faixa));

  const linhasMetricas = [];
  if (metricas.length) {
    adicionarSecao(matriz, formatos, notas, fundos, largura, 'SCORE');
    adicionarLinhaMetrica(matriz, formatos, notas, fundos, 'Score', metricas, 'score', '0.0');
    linhasMetricas.push(matriz.length);
    adicionarLinhaMetrica(matriz, formatos, notas, fundos, 'Confianca', metricas, 'confianca', '0%');
    linhasMetricas.push(matriz.length);
    ['qualidade', 'valor', 'risco', 'aderencia', 'conveniencia'].forEach(function (eixo) {
      adicionarLinhaMetrica(
        matriz, formatos, notas, fundos, tituloCampo(eixo), metricas, eixo, '0%'
      );
      linhasMetricas.push(matriz.length);
    });
  }

  adicionarSecao(matriz, formatos, notas, fundos, largura, 'PRECOS');
  let secaoAnterior = 'precos';
  linhas.forEach(function (linha) {
    if (linha.secao === 'atributos' && secaoAnterior !== 'atributos') {
      adicionarSecao(matriz, formatos, notas, fundos, largura, 'ATRIBUTOS');
      secaoAnterior = 'atributos';
    }
    const renderizada = renderizarLinha(linha, colunas.length);
    matriz.push([linha.rotulo || 'Sem rotulo'].concat(renderizada.valores));
    formatos.push(['@'].concat(renderizada.formatos));
    notas.push([''].concat(renderizada.notas));
    fundos.push(linhaFormato(largura, TEMA.branco));
  });

  const inicioTabela = 1;
  const faixa = aba.getRange(inicioTabela, 1, matriz.length, largura);
  faixa.setNumberFormats(formatos);
  faixa.setValues(matriz);
  faixa.setNotes(notas);
  faixa.setBackgrounds(fundos);
  aba.getRange(1, 1).setRichTextValue(
    SpreadsheetApp.newRichTextValue().setText('← Visao Geral').setLinkUrl(linkVisao).build()
  );
  faixa.setFontFamily('Inter').setFontColor(TEMA.tinta).setFontSize(10)
    .setVerticalAlignment('middle').setWrap(true);
  aba.getRange(1, 2, 1, Math.max(1, colunas.length)).setFontSize(13).setFontWeight('bold');
  aba.getRange(2, 1, 1, largura).setFontWeight('bold');
  colorirProdutos(aba, inicioTabela, metricas, situacao, matriz.length);
  estilizarSecoes(aba, matriz, largura);
  const corpo = aba.getRange(inicioTabela + 1, 1, matriz.length - 1, largura);
  corpo.setFontFamily('Inter').setFontSize(10).setVerticalAlignment('middle').setWrap(true);
  aba.getRange(inicioTabela, 1, matriz.length, 1)
    .setFontWeight('bold').setFontColor(TEMA.secundaria);
  if (linhasMetricas.length) {
    aba.getRange(4, 2, linhasMetricas.length, Math.max(1, colunas.length))
      .setFontFamily('Roboto Mono').setHorizontalAlignment('right');
  }
  aba.setColumnWidth(1, 220);
  for (let c = 2; c <= largura; c += 1) aba.setColumnWidth(c, 220);
  aba.autoResizeRows(1, inicioTabela + matriz.length - 1);
  const rodape = matriz.length + 2;
  aba.getRange(rodape, 1, 1, largura).merge()
    .setValue('Espelho gerado em ' + String(geradoEm || 'data nao informada') +
      ' · edite o repositorio, nao esta planilha')
    .setFontFamily('Inter').setFontSize(9).setFontColor(TEMA.apagada);
  aba.setFrozenRows(2);
  aba.setFrozenColumns(1);
  aba.setTabColor(TEMA.lider);
  protegerEspelho(aba);

  if (metricas.length) {
    inserirGraficosComparativo(aba, 1, largura, 4, 6, matriz.length + 4, colunas.length);
  }
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
  for (let i = 0; i < quantidade; i += 1) {
    if (tipados && tipados[i]) {
      const item = tipados[i];
      const tipo = item.tipo || 'texto';
      valores.push(tipo === 'vazio' ? '' : item.valor);
      formatos.push(formatoTipo(tipo));
      const estrelas = item.estrelas ? item.estrelas + '/5 estrelas' : '';
      notas.push([item.detalhe || '', estrelas].filter(String).join(' | '));
    } else {
      const legado = (linha.valores || [])[i];
      if (linha.tipo === 'estrela' && legado && typeof legado === 'object') {
        valores.push(legado.texto + (legado.estrelas ? '  ' + estrelas(legado.estrelas) : ''));
      } else {
        valores.push(legado === undefined || legado === null ? '' : legado);
      }
      formatos.push('@');
      notas.push('Payload legado; valor preservado como texto.');
    }
  }
  return { valores: valores, formatos: formatos, notas: notas };
}

function formatoTipo(tipo) {
  if (tipo === 'moeda') return 'R$ #,##0.00';
  if (tipo === 'nota') return '0.0 "estrela"';
  if (tipo === 'numero') return '0.##';
  if (tipo === 'booleano') return 'General';
  return '@';
}

function adicionarLinhaMetrica(matriz, formatos, notas, fundos, rotulo, metricas, campo, formato) {
  matriz.push([rotulo].concat(metricas.map(function (m) {
    const valor = m[campo];
    const eixo = ['qualidade', 'valor', 'risco', 'aderencia', 'conveniencia'].indexOf(campo) >= 0;
    return valor !== undefined && valor !== null && valor !== '' ? valor : (eixo ? 'sem dado' : '');
  })));
  formatos.push(['@'].concat(metricas.map(function () { return formato; })));
  notas.push([''].concat(metricas.map(function (m) {
    if (m[campo] === undefined || m[campo] === null || m[campo] === '') return 'sem dado';
    if (campo === 'score') return 'Score total de 0 a 100, calculado pelo motor de ranking do repositorio.';
    return '';
  })));
  fundos.push(linhaFormato(metricas.length + 1, TEMA.branco));
}

function adicionarSecao(matriz, formatos, notas, fundos, largura, titulo) {
  matriz.push([titulo].concat(linhaFormato(largura - 1, '')));
  formatos.push(linhaFormato(largura, '@'));
  notas.push(linhaFormato(largura, ''));
  fundos.push(linhaFormato(largura, TEMA.faixa));
}

function vereditosProdutos(metricas, situacao) {
  const scores = metricas.map(function (m, indice) {
    return situacao[indice] === 'elegivel' && typeof m.score === 'number' ? m.score : null;
  });
  const validos = scores.filter(function (score) { return score !== null; }).sort(function (a, b) { return b - a; });
  const melhor = validos.length ? validos[0] : null;
  const empate = validos.length > 1 && melhor - validos[1] <= 3;
  return situacao.map(function (estado, indice) {
    const score = scores[indice];
    if (estado === 'cortado') return '▲ Bloqueado pelo gate';
    if (estado === 'sem_cotacao') return '◔ Sem cotacao';
    if (score === null) return '◐ Pesquisando';
    if (empate && melhor - score <= 3) return '◐ Empate tecnico · score ' + score.toFixed(1);
    if (score === melhor) return '● Lider · score ' + score.toFixed(1);
    return '◐ Atrás por ' + (melhor - score).toFixed(1) + ' pontos';
  });
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

function inserirGraficosComparativo(aba, linhaProdutos, largura, linhaScore, linhaEixos, ancora, quantidade) {
  const cores = linhaFormato(Math.max(1, quantidade), TEMA.apagada);
  if (cores.length) cores[0] = TEMA.lider;
  const ranking = aba.newChart().setChartType(Charts.ChartType.BAR)
    .addRange(aba.getRange(linhaProdutos, 1, 1, largura))
    .addRange(aba.getRange(linhaScore, 1, 1, largura))
    .setTransposeRowsAndColumns(true).setNumHeaders(1)
    .setOption('title', 'Score total por candidato').setOption('fontName', 'Inter')
    .setOption('legend', { position: 'none' }).setOption('colors', cores)
    .setOption('hAxis', { viewWindow: { min: 0, max: 100 }, textStyle: { color: TEMA.apagada } })
    .setPosition(ancora, 1, 0, 0).build();
  aba.insertChart(ranking);

  if (quantidade <= 3) {
    const eixos = aba.newChart().setChartType(Charts.ChartType.COLUMN)
      .addRange(aba.getRange(linhaProdutos, 1, 1, largura))
      .addRange(aba.getRange(linhaEixos, 1, 5, largura))
      .setTransposeRowsAndColumns(true).setNumHeaders(1)
      .setOption('title', 'Cinco eixos da decisao').setOption('fontName', 'Inter')
      .setOption('legend', { position: quantidade > 1 ? 'bottom' : 'none' })
      .setOption('colors', [TEMA.lider, TEMA.slot2, TEMA.slot3].slice(0, quantidade))
      .setOption('vAxis', { viewWindow: { min: 0, max: 1 }, textStyle: { color: TEMA.apagada } })
      .setPosition(ancora + 16, 1, 0, 0).build();
    aba.insertChart(eixos);
  } else {
    for (let indice = 0; indice < quantidade; indice += 1) {
      const mini = aba.newChart().setChartType(Charts.ChartType.COLUMN)
        .addRange(aba.getRange(linhaEixos, 1, 5, 1))
        .addRange(aba.getRange(linhaEixos, indice + 2, 5, 1))
        .setNumHeaders(0).setOption('title', String(aba.getRange(1, indice + 2).getValue()))
        .setOption('fontName', 'Inter').setOption('legend', { position: 'none' })
        .setOption('colors', [TEMA.lider])
        .setOption('vAxis', { viewWindow: { min: 0, max: 1 }, textStyle: { color: TEMA.apagada } })
        .setPosition(ancora + 16 + Math.floor(indice / 2) * 15, 1 + (indice % 2) * 6, 0, 0).build();
      aba.insertChart(mini);
    }
  }
}

function aplicarFaixas(faixa) {
  const cores = [];
  for (let r = 0; r < faixa.getNumRows(); r += 1) {
    cores.push(linhaFormato(faixa.getNumColumns(), r % 2 ? TEMA.faixa : TEMA.branco));
  }
  faixa.setBackgrounds(cores);
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

function colorirProdutos(aba, linha, metricas, situacao, quantidadeLinhas) {
  const scores = metricas.map(function (m, indice) {
    return situacao[indice] === 'elegivel' && typeof m.score === 'number' ? m.score : null;
  });
  const validos = scores.filter(function (score) { return score !== null; }).sort(function (a, b) { return b - a; });
  const melhor = validos.length ? validos[0] : null;
  const empate = validos.length > 1 && melhor - validos[1] <= 3;
  situacao.forEach(function (estado, indice) {
    const score = scores[indice];
    const destaque = score !== null && (score === melhor || (empate && melhor - score <= 3));
    if (destaque) aba.getRange(linha, indice + 2, quantidadeLinhas, 1)
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

function estadoVisao(linha) {
  if (linha.cotacoes_vencidas > 0) return '▲ Vencida';
  if (linha.aguardando_preco > 0) return '◔ Aguardando preco';
  if (linha.data_decisao || linha.escolhido || linha.estado === 'comprado') return '● Decidido';
  return '◐ Pesquisando';
}

function colorirEstadosVisao(aba, linhas, campos) {
  const indice = campos.indexOf('estado');
  if (indice < 0) return;
  linhas.forEach(function (linha, linhaIndice) {
    let cor = TEMA.pesquisando;
    if (linha.cotacoes_vencidas > 0) cor = TEMA.vencida;
    else if (linha.aguardando_preco > 0) cor = TEMA.aguardando;
    else if (linha.data_decisao || linha.escolhido || linha.estado === 'comprado') cor = TEMA.decidido;
    aba.getRange(linhaIndice + 6, indice + 1).setFontColor(cor).setFontWeight('bold');
  });
}

function aplicarLinksProjetos(planilha, aba, linhas, campos, comparativos, destinos) {
  const indice = campos.indexOf('projeto');
  if (indice < 0) return;
  const abas = {};
  comparativos.forEach(function (comp, i) { abas[comp.projeto] = destinos[i]; });
  linhas.forEach(function (linha, i) {
    const destino = planilha.getSheetByName(abas[linha.projeto]);
    if (!destino) return;
    const link = planilha.getUrl() + '#gid=' + destino.getSheetId();
    aba.getRange(i + 6, indice + 1).setRichTextValue(
      SpreadsheetApp.newRichTextValue().setText(String(linha.projeto)).setLinkUrl(link).build()
    );
  });
}

function inserirGraficoVisao(aba, campos, quantidade, inicio, coluna) {
  const projeto = campos.indexOf('projeto');
  const score = campos.indexOf('score');
  if (projeto < 0 || score < 0 || !quantidade) return;
  const grafico = aba.newChart().setChartType(Charts.ChartType.BAR)
    .addRange(aba.getRange(inicio - 1, projeto + 1, quantidade + 1, 1))
    .addRange(aba.getRange(inicio - 1, score + 1, quantidade + 1, 1))
    .setNumHeaders(1).setOption('title', 'Score dos projetos')
    .setOption('fontName', 'Inter').setOption('legend', { position: 'none' })
    .setOption('colors', [TEMA.lider])
    .setOption('hAxis', { viewWindow: { min: 0, max: 100 }, textStyle: { color: TEMA.apagada } })
    .setPosition(5, coluna, 0, 0).build();
  aba.insertChart(grafico);
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
    'data_decisao', 'cotacoes_vencidas',
  ]);
  (Array.isArray(dados.visao_geral) ? dados.visao_geral : []).forEach(function (linha, indice) {
    avisarCampos(linha, camposVisaoConhecidos, 'visao geral ' + indice, avisos);
  });
  (Array.isArray(dados.comparativos) ? dados.comparativos : []).forEach(function (comp, ci) {
    avisarCampos(comp, ['projeto', 'colunas', 'situacao', 'linhas', 'metricas'], 'comparativo ' + ci, avisos);
    (Array.isArray(comp.metricas) ? comp.metricas : []).forEach(function (metrica, mi) {
      avisarCampos(metrica, camposMetricas, 'metrica ' + ci + '/' + mi, avisos);
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

function limparAbasOrfas(planilha, projetosAtuais) {
  const manter = { 'Visao Geral': true };
  projetosAtuais.forEach(function (nome) { manter[nome] = true; });
  planilha.getSheets().forEach(function (aba) {
    const nome = aba.getName();
    const gerada = nome === 'Página1' || nome === 'Pagina1' || nome === 'Painel' ||
      nome === '_Dados' || /^20\d\d-/.test(nome);
    if (gerada && !manter[nome] && planilha.getSheets().length > 1) planilha.deleteSheet(aba);
  });
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

**Timeout:** a Versão 4, ainda implantada, levou até ~47s com 8 projetos no
teste de 2026-09-04 porque escreve linha por linha. Por isso o cliente Python
continua com timeout de 120s; **não reduza esse valor**. A Versão 5 preparada
acima usa `setValues` em lote, mas esse ganho só existe depois do deploy e da
verificação visual na planilha real.

## Estado desta mudança

- O cliente Python e o Code.gs da Versão 5 estão versionados com
  compatibilidade nos dois sentidos: payload antigo tem fallback, e os
  campos novos são aditivos para a Versão 4.
- **Deploy pendente:** a implantação ativa continua na Versão 4. Publicar a
  Versão 5 exige navegador autenticado em **conta-comercial** e confirmação em duas
  etapas pelo dono da conta.
- Depois do deploy, execute a sincronização e abra a planilha para conferir
  indicadores, `Visao Geral`, comparativos, gráficos, filtros, links, formatos
  numéricos e estados. Uma resposta JSON com `ok` não encerra essa validação.
