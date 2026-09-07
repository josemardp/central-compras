// Cenario: o registro de propriedade estava no formato ANTIGO (ate a V11,
// so { nome: true }, sem sheetId). Confere que a migracao adota o sheetId
// atual pra um nome ja conhecido do registro antigo (uma unica vez), sem
// duplicar a aba nem tratar o projeto legitimo como colisao com aba
// estranha.
// Uso: node migracao_registro_legado.js <caminho-para-code.gs>
'use strict';
const { carregar, chamar } = require('../harness');

const caminho = process.argv[2];
const { doPost, env } = carregar(caminho);
const { PropertiesService } = env;

const payload = {
  token: '...', schema_versao: 3, gerado_em: 'x',
  visao_geral_colunas: ['projeto'], metricas_colunas: ['projeto'],
  visao_geral: [],
  comparativos: [{
    projeto: '2026-legado', categoria: 'fone', colunas: [], situacao: [], linhas: [], metricas: [],
  }],
};

// 1a sincronizacao "normal": cria a aba e registra nome+sheetId de verdade.
chamar(doPost, payload);
const planilha = Object.values(env.spreadsheetsById)[0];
const idReal = planilha.getSheetByName('2026-legado').getSheetId();

// Simula o registro antigo (pre-sheetId) tomando o lugar do novo -
// exatamente o formato que a V11 real deixou gravado em ScriptProperties.
PropertiesService.getScriptProperties().setProperty(
  'abas_geradas_pelo_script', JSON.stringify({ '2026-legado': true })
);

// 2a sincronizacao: o registro legado precisa ser migrado (adotar o
// sheetId atual) em vez de tratar a aba como estranha.
const r2 = chamar(doPost, payload);
const abas = planilha.sheets.map(function (s) { return s.name; });

const resultado = {
  sync2_ok: r2.ok === true,
  sem_duplicata: abas.length === 2 && abas.filter(function (n) { return n === '2026-legado'; }).length === 1,
  sem_aviso_de_colisao: !(r2.avisos || []).some(function (a) { return a.indexOf('nao pertence a este script') >= 0; }),
  sheetId_preservado: planilha.getSheetByName('2026-legado').getSheetId() === idReal,
  abas: abas,
  avisos_sync2: r2.avisos || [],
};
resultado.passou = resultado.sync2_ok && resultado.sem_duplicata
  && resultado.sem_aviso_de_colisao && resultado.sheetId_preservado;

console.log('RESULTADO_JSON: ' + JSON.stringify(resultado));
