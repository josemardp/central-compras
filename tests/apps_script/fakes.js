// Fakes minimos do runtime do Apps Script para rodar o Code.gs de verdade
// sob Node, sem depender de rede/Google. So implementa comportamento real
// para o que os testes de tests/test_apps_script_execucao.py precisam
// (planilhas/abas/celulas, pasta/arquivo do Drive, PropertiesService, lock,
// digest). Qualquer metodo nao implementado vira um "chainable" universal:
// chamavel, encadeavel, sempre verdadeiro, nunca lanca - assim o resto do
// Code.gs (graficos, formatacao visual, protecao de aba) roda sem quebrar
// mesmo sem stub dedicado, porque nao afeta o comportamento sob teste.
//
// Ver docs/integracao-google-sheets.md ("Code.gs") para o codigo real que
// esses fakes carregam - eles nunca sao a fonte da verdade do
// comportamento, so o ambiente onde ele roda de verdade sob Node.
'use strict';
const crypto = require('crypto');

function chainable() {
  const fn = function (...args) {
    if (fn.__impl) return fn.__impl(...args);
    return proxy;
  };
  fn.__children = new Map();
  const proxy = new Proxy(fn, {
    get(target, prop) {
      if (prop === '__real') return undefined;
      if (prop === Symbol.toPrimitive) return undefined;
      if (prop === 'then') return undefined;
      if (target.__children.has(prop)) return target.__children.get(prop);
      const child = chainable();
      target.__children.set(prop, child);
      return child;
    },
    apply(target, _this, args) {
      return target(...args);
    },
  });
  return proxy;
}

function withAutoMock(real) {
  return new Proxy(real, {
    get(target, prop) {
      if (prop === '__real') return target;
      if (prop in target) {
        const v = target[prop];
        return typeof v === 'function' ? v.bind(target) : v;
      }
      return chainable();
    },
  });
}

class RealRange {
  constructor(sheet, row, col, numRows, numCols) {
    this.sheet = sheet;
    this.row = row;
    this.col = col;
    this.numRows = numRows;
    this.numCols = numCols;
  }
  getRow() { return this.row; }
  getColumn() { return this.col; }
  getNumRows() { return this.numRows; }
  getNumColumns() { return this.numCols; }
  setValue(v) { this.sheet._write(this.row, this.col, v); return withAutoMock(this); }
  setValues(vals) {
    for (let r = 0; r < vals.length; r += 1) {
      for (let c = 0; c < vals[r].length; c += 1) this.sheet._write(this.row + r, this.col + c, vals[r][c]);
    }
    return withAutoMock(this);
  }
  getValue() { return this.sheet._read(this.row, this.col); }
  getValues() {
    const out = [];
    for (let r = 0; r < this.numRows; r += 1) {
      const linha = [];
      for (let c = 0; c < this.numCols; c += 1) linha.push(this.sheet._read(this.row + r, this.col + c));
      out.push(linha);
    }
    return out;
  }
  merge() { return withAutoMock(this); }
}

class RealSheet {
  constructor(spreadsheet, name, id) {
    this.spreadsheet = spreadsheet;
    this.name = name;
    this.id = id;
    this.cells = new Map();
  }
  getName() { return this.name; }
  setName(n) { this.name = n; return withAutoMock(this); }
  getSheetId() { return this.id; }
  getRange(row, col, numRows, numCols) {
    return withAutoMock(new RealRange(this, row, col || 1, numRows || 1, numCols || 1));
  }
  getMaxRows() { return 1000; }
  getMaxColumns() { return 26; }
  clear() { this.cells.clear(); return withAutoMock(this); }
  isSheetHidden() { return false; }
  getBandings() { return []; }
  getCharts() { return []; }
  getFilter() { return null; }
  _write(row, col, value) {
    this.cells.set(row + ',' + col, value);
    this.spreadsheet.writeLog.push({ sheet: this.name, row, col, value });
  }
  _read(row, col) {
    return this.cells.has(row + ',' + col) ? this.cells.get(row + ',' + col) : '';
  }
}

let _nextId = 1;
class RealSpreadsheet {
  constructor(name) {
    this.name = name;
    this.id = 'ss-' + (_nextId += 1);
    this.sheets = [];
    this.writeLog = [];
    this._nextSheetId = 1;
  }
  getUrl() { return 'https://fake.local/spreadsheet/' + this.id; }
  getId() { return this.id; }
  getSheets() { return this.sheets.map((s) => withAutoMock(s)); }
  getSheetByName(name) {
    const s = this.sheets.find((x) => x.name === name);
    return s ? withAutoMock(s) : null;
  }
  insertSheet(name) {
    const s = new RealSheet(this, name, (this._nextSheetId += 1));
    this.sheets.push(s);
    this.writeLog.push({ event: 'insertSheet', name });
    return withAutoMock(s);
  }
  deleteSheet(abaProxy) {
    const real = abaProxy.__real || abaProxy;
    this.sheets = this.sheets.filter((s) => s !== real);
    this.writeLog.push({ event: 'deleteSheet', name: real.name });
    return withAutoMock(this);
  }
}

class RealFile {
  constructor(id, name) { this.id = id; this.name = name; }
  getId() { return this.id; }
  getName() { return this.name; }
}

class RealFolder {
  constructor(id) { this.id = id; this.files = []; }
  getFilesByType() {
    const files = this.files;
    let idx = 0;
    return {
      hasNext() { return idx < files.length; },
      next() { const f = files[idx]; idx += 1; return withAutoMock(f); },
    };
  }
  addFile(fileProxy) { this.files.push(fileProxy.__real || fileProxy); return withAutoMock(this); }
  removeFile(fileProxy) {
    const real = fileProxy.__real || fileProxy;
    this.files = this.files.filter((f) => f !== real);
    return withAutoMock(this);
  }
}

function makeGasEnvironment() {
  const spreadsheetsById = {};
  const filesById = {};
  const folders = {};
  const scriptProps = {};

  const SpreadsheetApp = withAutoMock({
    create(name) {
      const ss = new RealSpreadsheet(name);
      spreadsheetsById[ss.id] = ss;
      filesById[ss.id] = new RealFile(ss.id, name);
      return withAutoMock(ss);
    },
    openById(id) { return withAutoMock(spreadsheetsById[id]); },
    ProtectionType: withAutoMock({ SHEET: 'SHEET' }),
  });

  const DriveApp = withAutoMock({
    getFolderById(id) {
      if (!folders[id]) folders[id] = new RealFolder(id);
      return withAutoMock(folders[id]);
    },
    getFileById(id) { return withAutoMock(filesById[id]); },
    getRootFolder() {
      if (!folders.root) folders.root = new RealFolder('root');
      return withAutoMock(folders.root);
    },
  });

  const MimeType = withAutoMock({ GOOGLE_SHEETS: 'application/vnd.google-apps.spreadsheet' });

  const Utilities = withAutoMock({
    computeDigest(_algo, text) {
      const buf = crypto.createHash('sha256').update(String(text)).digest();
      return Array.from(buf).map((b) => (b > 127 ? b - 256 : b));
    },
    Charset: withAutoMock({ UTF_8: 'UTF-8' }),
    DigestAlgorithm: withAutoMock({ SHA_256: 'SHA_256' }),
  });

  const LockService = withAutoMock({
    getScriptLock() {
      return withAutoMock({ tryLock() { return true; }, releaseLock() {} });
    },
  });

  const PropertiesService = withAutoMock({
    // Este projeto do Apps Script e solto (nao container-bound, de
    // proposito). Na Apps Script real, getDocumentProperties() sem
    // documento vinculado devolve null - descoberto na V10 real em
    // producao, nao aqui (o fake antigo devolvia um objeto funcional pros
    // dois metodos, mascarando o bug). Continua devolvendo null de
    // proposito para essa classe de bug nao passar batido de novo.
    getDocumentProperties() { return null; },
    getScriptProperties() {
      return withAutoMock({
        getProperty(k) {
          return Object.prototype.hasOwnProperty.call(scriptProps, k) ? scriptProps[k] : null;
        },
        setProperty(k, v) { scriptProps[k] = v; return this; },
      });
    },
  });

  const ContentService = withAutoMock({
    MimeType: withAutoMock({ JSON: 'JSON' }),
    createTextOutput(texto) {
      return withAutoMock({
        _texto: texto,
        getContent() { return texto; },
        setMimeType() { return this; },
      });
    },
  });

  const Charts = chainable();

  return {
    SpreadsheetApp, DriveApp, MimeType, Utilities, LockService, PropertiesService, ContentService,
    Charts,
    spreadsheetsById, folders, scriptProps,
  };
}

module.exports = {
  makeGasEnvironment, withAutoMock, chainable, RealRange, RealSheet, RealSpreadsheet, RealFolder, RealFile,
};
