// Cenario: duas sincronizacoes validas seguidas com o MESMO payload.
// Confere resultado estavel (ok nas duas) e sem duplicacao de aba - o
// registro de propriedade (nome + sheetId) precisa reconhecer a aba da
// 1a sincronizacao como do script na 2a, sem recriar nem redirecionar.
// Uso: node duas_sincronizacoes_idempotentes.js <caminho-para-code.gs>
'use strict';
const { carregar, chamar } = require('../harness');

const caminho = process.argv[2];
const { doPost, env } = carregar(caminho);

const payload = {
  token: '...', schema_versao: 3, gerado_em: 'x',
  visao_geral_colunas: ['projeto'], metricas_colunas: ['projeto'],
  visao_geral: [{ projeto: '2026-teste', cotacoes_vencidas: 0 }],
  comparativos: [{
    projeto: '2026-teste', categoria: 'fone', colunas: [], situacao: [], linhas: [], metricas: [],
  }],
};

const r1 = chamar(doPost, payload);
const r2 = chamar(doPost, payload);
const planilha = Object.values(env.spreadsheetsById)[0];
const abas = planilha.sheets.map(function (s) { return s.name; });

const resultado = {
  sync1_ok: r1.ok === true,
  sync2_ok: r2.ok === true,
  sem_duplicata: abas.length === 2 && abas.filter(function (n) { return n === '2026-teste'; }).length === 1,
  abas: abas,
  avisos_sync2: r2.avisos || [],
};
resultado.passou = resultado.sync1_ok && resultado.sync2_ok && resultado.sem_duplicata;

console.log('RESULTADO_JSON: ' + JSON.stringify(resultado));
