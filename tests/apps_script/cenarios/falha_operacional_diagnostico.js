// Cenario: uma falha OPERACIONAL (nao um payload invalido - esse caso e
// barrado por validarPayload antes de qualquer escrita) no meio da escrita
// de um comparativo. Simula isso injetando uma falha no setValues() da 2a
// aba, como um erro real da API do Sheets (timeout/quota) aconteceria -
// depois que abaLimpa ja rodou (a aba ja foi limpa) mas antes da escrita
// nova terminar. Confere que o diagnostico distingue a aba que terminou
// (abas_escritas_antes_da_falha) da que ficou so parcialmente alterada
// (abas_parcialmente_alteradas) - nao promete atomicidade por aba.
// Uso: node falha_operacional_diagnostico.js <caminho-para-code.gs>
'use strict';
const { carregar, chamar } = require('../harness');
const { RealRange } = require('../fakes');

const caminho = process.argv[2];
const { doPost, env } = carregar(caminho);

const original = RealRange.prototype.setValues;
RealRange.prototype.setValues = function (vals) {
  if (this.sheet.name === '2026-b') {
    throw new Error('Simulado: erro transiente da API do Sheets (timeout)');
  }
  return original.call(this, vals);
};

let resposta;
try {
  resposta = chamar(doPost, {
    token: '...', schema_versao: 3, gerado_em: 'x',
    visao_geral_colunas: ['projeto'], metricas_colunas: ['projeto'],
    visao_geral: [],
    comparativos: [
      {
        projeto: '2026-a', categoria: 'fone', colunas: ['A'], situacao: ['elegivel'],
        linhas: [{ rotulo: 'Preco', tipo: 'texto', secao: 'precos', valores: ['R$ 100'] }],
        metricas: [],
      },
      {
        projeto: '2026-b', categoria: 'fone', colunas: ['B'], situacao: ['elegivel'],
        linhas: [{ rotulo: 'Preco', tipo: 'texto', secao: 'precos', valores: ['R$ 200'] }],
        metricas: [],
      },
    ],
  });
} finally {
  RealRange.prototype.setValues = original;
}

const planilha = Object.values(env.spreadsheetsById)[0];
const abaB = planilha && planilha.getSheetByName('2026-b');

const concluidas = Array.isArray(resposta.abas_escritas_antes_da_falha) ? resposta.abas_escritas_antes_da_falha : [];
const parciais = Array.isArray(resposta.abas_parcialmente_alteradas) ? resposta.abas_parcialmente_alteradas : [];

const resultado = {
  sync_falhou: resposta.ok === false,
  primeira_aba_concluida: concluidas.indexOf('2026-a') >= 0,
  segunda_aba_marcada_parcial: parciais.indexOf('2026-b') >= 0,
  segunda_aba_nao_aparece_como_concluida: concluidas.indexOf('2026-b') < 0,
  aba_b_existe_mas_em_branco: Boolean(abaB) && abaB.cells.size === 0,
  resposta: resposta,
};
resultado.passou = resultado.sync_falhou && resultado.primeira_aba_concluida
  && resultado.segunda_aba_marcada_parcial && resultado.segunda_aba_nao_aparece_como_concluida;

console.log('RESULTADO_JSON: ' + JSON.stringify(resultado));
