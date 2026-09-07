// Carrega um Code.gs real (o caminho de um arquivo temporario com o bloco
// extraido de docs/integracao-google-sheets.md) num escopo com os fakes do
// Apps Script, e devolve { doPost, env } para os cenarios chamarem.
//
// SEM 'use strict' de proposito: eval direto so deixa vazar as declaracoes
// de function do Code.gs pro escopo de carregar() em modo sloppy (Apps
// Script tambem roda em modo sloppy).
const fs = require('fs');
const { makeGasEnvironment } = require('./fakes');

function carregar(caminhoCodeGs) {
  const env = makeGasEnvironment();
  const {
    SpreadsheetApp, DriveApp, MimeType, Utilities, LockService, PropertiesService, ContentService, Charts,
  } = env;
  const codigo = fs.readFileSync(caminhoCodeGs, 'utf-8');
  eval(codigo); // eslint-disable-line no-eval
  // eslint-disable-next-line no-undef
  return { doPost, env };
}

function chamar(doPost, dados) {
  const resp = doPost({ postData: { contents: JSON.stringify(dados) } });
  return JSON.parse(resp.getContent());
}

module.exports = { carregar, chamar };
