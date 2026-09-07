// Utilitario generico: carrega o Code.gs, envia UM payload (lido de um
// arquivo JSON) pro doPost, e imprime o estado resultante - resposta,
// se uma planilha chegou a ser criada, quantas mutacoes de celula
// aconteceram e quais abas existem no final. Usado pelo lado Python pra
// testar varios payloads (validos e invalidos, formato legado e tipado)
// sem precisar de um script Node novo pra cada caso.
// Uso: node rodar_payload.js <caminho-para-code.gs> <caminho-para-payload.json>
'use strict';
const fs = require('fs');
const { carregar, chamar } = require('../harness');

const caminhoCodeGs = process.argv[2];
const caminhoPayload = process.argv[3];
const { doPost, env } = carregar(caminhoCodeGs);
const payload = JSON.parse(fs.readFileSync(caminhoPayload, 'utf-8'));

const resposta = chamar(doPost, payload);
const planilha = Object.values(env.spreadsheetsById)[0];

const resultado = {
  resposta: resposta,
  planilha_criada: Boolean(planilha),
  mutacoes: planilha ? planilha.writeLog.length : 0,
  abas: planilha ? planilha.sheets.map(function (s) { return s.name; }) : [],
};

console.log('RESULTADO_JSON: ' + JSON.stringify(resultado));
