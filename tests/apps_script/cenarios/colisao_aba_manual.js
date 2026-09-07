// Cenario: uma aba manual "2026-a" existe na planilha (criada a mao, com
// uma anotacao do usuario, sem registro de propriedade pelo gerador).
// Sincroniza um comparativo do projeto "2026-a" e confere que a aba manual
// - conteudo e identidade (sheetId) - sobrevive intacta, e que o projeto
// ainda assim e escrito (em outra aba).
// Uso: node colisao_aba_manual.js <caminho-para-code.gs>
'use strict';
const { carregar, chamar } = require('../harness');

const caminho = process.argv[2];
const { doPost, env } = carregar(caminho);

// Monta a planilha primeiro com um sync vazio, so pra existir o objeto.
chamar(doPost, {
  token: '...', schema_versao: 3, gerado_em: 'boot',
  visao_geral_colunas: ['projeto'], metricas_colunas: ['projeto'],
  visao_geral: [], comparativos: [],
});
const planilha = Object.values(env.spreadsheetsById)[0];

const abaManual = planilha.insertSheet('2026-a');
abaManual._write(1, 1, 'NAO MEXA - dados pessoais do Josemar');
const conteudoAntes = abaManual._read(1, 1);
const idAntes = abaManual.getSheetId();

const r = chamar(doPost, {
  token: '...', schema_versao: 3, gerado_em: 'sync',
  visao_geral_colunas: ['projeto'], metricas_colunas: ['projeto'],
  visao_geral: [],
  comparativos: [{
    projeto: '2026-a', categoria: 'fone', colunas: ['X'], situacao: ['elegivel'], linhas: [], metricas: [],
  }],
});

const abaDepois = planilha.getSheetByName('2026-a');
const conteudoDepois = abaDepois ? abaDepois._read(1, 1) : null;
const idDepois = abaDepois ? abaDepois.getSheetId() : null;
const nomesAbas = planilha.sheets.map((s) => s.name);

const resultado = {
  sync_ok: r.ok === true,
  identidade_preservada: idAntes === idDepois,
  conteudo_preservado: conteudoAntes === conteudoDepois,
  projeto_foi_escrito_em_outra_aba: nomesAbas.length === 3, // Visao Geral + manual + redirecionada
  abas: nomesAbas,
  avisos: r.avisos || [],
};
resultado.passou = resultado.sync_ok && resultado.identidade_preservada
  && resultado.conteudo_preservado && resultado.projeto_foi_escrito_em_outra_aba;

console.log('RESULTADO_JSON: ' + JSON.stringify(resultado));
