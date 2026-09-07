// Cenario: a aba "Visao Geral" gerada pelo script e excluida, e uma aba
// manual chamada "Visao Geral" (sheetId diferente, nunca escrito pelo
// script) toma o lugar, com uma anotacao do usuario. Confere que a proxima
// sincronizacao NAO adota nem sobrescreve essa aba manual - a Visao Geral
// real do script tem que ir para outro destino, com link e nome estaveis
// entre sincronizacoes.
// Uso: node colisao_aba_visao_geral_manual.js <caminho-para-code.gs>
'use strict';
const { carregar, chamar } = require('../harness');

const caminho = process.argv[2];
const { doPost, env } = carregar(caminho);

const payloadComProjeto = {
  token: '...', schema_versao: 3, gerado_em: 'boot',
  visao_geral_colunas: ['projeto'], metricas_colunas: ['projeto'],
  visao_geral: [{ projeto: '2026-teste', cotacoes_vencidas: 0 }],
  comparativos: [{
    projeto: '2026-teste', categoria: 'fone', colunas: [], situacao: [], linhas: [], metricas: [],
  }],
};

// 1o sync: cria a Visao Geral e a aba do projeto normalmente.
chamar(doPost, payloadComProjeto);
const planilha = Object.values(env.spreadsheetsById)[0];

// Cria outra aba antes de excluir a Visao Geral, pra nunca ficar com uma
// planilha de aba unica (Sheets nao deixa excluir a ultima aba).
planilha.insertSheet('Rascunho');

// Exclui a Visao Geral gerada pelo script.
const visaoGerada = planilha.getSheetByName('Visao Geral');
const idVisaoGerada = visaoGerada.getSheetId();
planilha.deleteSheet(visaoGerada);

// Usuario cria a mao uma aba manual chamada "Visao Geral", com anotacao.
const visaoManual = planilha.insertSheet('Visao Geral');
visaoManual._write(1, 1, 'ANOTACAO MANUAL - nao mexer');
const idVisaoManual = visaoManual.getSheetId();
const conteudoAntes = visaoManual._read(1, 1);

// 2a sincronizacao.
const r2 = chamar(doPost, payloadComProjeto);

const visaoDepois = planilha.getSheetByName('Visao Geral');
const conteudoDepois = visaoDepois ? visaoDepois._read(1, 1) : null;
const idDepois = visaoDepois ? visaoDepois.getSheetId() : null;

// Onde a Visao Geral DE VERDADE (do script) foi parar? E a aba (que nao a
// manual, nem a do projeto, nem o rascunho) cujo sheetId esta no registro
// de propriedade do script.
const registroBruto = env.scriptProps['abas_geradas_pelo_script'];
const registro = registroBruto ? JSON.parse(registroBruto) : {};

const abaRealDoScript = planilha.sheets.find(function (s) {
  return Object.values(registro).indexOf(s.id) >= 0 && s.id !== idVisaoManual && s.name !== '2026-teste' && s.name !== 'Rascunho';
});

// Terceira sincronizacao: confere ESTABILIDADE do destino (mesmo nome de
// novo, nao um novo redirecionamento a cada retry).
const r3 = chamar(doPost, payloadComProjeto);
const abaRealDoScriptDepoisDoRetry = planilha.sheets.find(function (s) {
  return Object.values(JSON.parse(env.scriptProps['abas_geradas_pelo_script'])).indexOf(s.id) >= 0
    && s.id !== idVisaoManual && s.name !== '2026-teste' && s.name !== 'Rascunho';
});

const resultado = {
  sync2_ok: r2.ok === true,
  sync3_ok: r3.ok === true,
  aba_manual_identidade_preservada: idVisaoManual === idDepois,
  aba_manual_conteudo_preservado: conteudoAntes === conteudoDepois,
  script_escreveu_em_outro_lugar: Boolean(abaRealDoScript),
  nome_do_destino_real: abaRealDoScript ? abaRealDoScript.name : null,
  destino_estavel_entre_syncs: Boolean(abaRealDoScriptDepoisDoRetry)
    && abaRealDoScript && (abaRealDoScriptDepoisDoRetry.name === abaRealDoScript.name)
    && (abaRealDoScriptDepoisDoRetry.id === abaRealDoScript.id),
  abas: planilha.sheets.map(function (s) { return s.name; }),
  avisos_sync2: r2.avisos || [],
};
resultado.passou = resultado.sync2_ok && resultado.sync3_ok
  && resultado.aba_manual_identidade_preservada && resultado.aba_manual_conteudo_preservado
  && resultado.script_escreveu_em_outro_lugar && resultado.destino_estavel_entre_syncs;

console.log('RESULTADO_JSON: ' + JSON.stringify(resultado));
