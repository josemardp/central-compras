"""Painel local: a grade editavel da Central, no navegador.

Tres camadas separadas de proposito:

- `estado()`  calcula o que a tela mostra. Funcao pura, testavel sem servidor.
- `acao()`    grava. Chama os MESMOS caminhos do CLI, com a mesma trava e o
              mesmo append-only. O painel nao pode ser porta dos fundos: se o
              `decidir` recusa no terminal, tem que recusar aqui.
- `servir()`  casca HTTP fina, presa em 127.0.0.1.

O `artifact()` gera a versao so-leitura, para consultar do celular.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:  # importado como pacote (`from scripts import painel`), nos testes
    from scripts import central_compras as cc
except ImportError:  # rodando como script solto: `python scripts/central_compras.py`
    import central_compras as cc


def _linha_ranking(item: Any, campo_valor: str, rotulo_valor: str) -> dict[str, Any]:
    quote = item.quote
    return {
        "produto_id": item.produto_id,
        "nome": item.product.get("nome") or item.produto_id,
        "marca": item.product.get("marca") or "",
        "score": item.score,
        "confianca": item.confianca,
        "eixos": item.axes,
        "sem_dado": item.eixos_sem_dado,
        "cortes": item.eliminations,
        "alertas": item.alerts,
        "custo": cc.quote_float(quote.get("custo_total")),
        "custo_texto": cc.brl(quote.get("custo_total")),
        "base_valor": rotulo_valor,
        "valor_comparado": cc.brl(quote.get(campo_valor) or quote.get("custo_total")),
        "loja": quote.get("loja") or "",
        "vendedor": quote.get("vendedor") or "",
        "vendedor_tipo": quote.get("vendedor_tipo") or "",
        "fonte": quote.get("fonte") or "",
        "prazo": quote.get("frete_prazo_dias") or "",
        "nota": quote.get("nota") or "",
        "avaliacoes": quote.get("n_avaliacoes") or "",
        "garantia_meses": quote.get("garantia_meses") or "",
        "garantia_tipo": quote.get("garantia_tipo") or "",
        "idade_dias": item.idade_dias,
        "vencida": item.vencida,
        "espera": cc.waiting_gap(item.product, quote),
        "estado": item.product.get("estado") or "",
    }


def estado(project: Path) -> dict[str, Any]:
    """Tudo que a tela mostra, calculado com o motor. Nao escreve nada."""
    briefing, _ = cc.load_frontmatter(project / "briefing.md")
    elegiveis, cortados = cc.compute_ranking(project)
    campo_valor, rotulo_valor = cc.value_field_for(briefing)
    erros, avisos = cc.validation_report(project)
    cotacoes = cc.read_quotes(project)
    regra = cc.stop_rule_status(project)
    escolhido, porque = cc.project_decision_summary(project)

    return {
        "projeto": project.name,
        "categoria": briefing.get("categoria") or "",
        "estado": briefing.get("estado") or "",
        "preco_teto": cc.brl(briefing.get("preco_teto"), ""),
        "valor_estimado": cc.quote_float(briefing.get("valor_estimado")),
        "base_valor": rotulo_valor,
        "confianca_minima": cc.minimum_confidence(briefing),
        "eixos_obrigatorios": list(cc.preferences().get("eixos_obrigatorios_para_decidir") or []),
        "pesos": cc.preferences().get("score", {}),
        "elegiveis": [_linha_ranking(i, campo_valor, rotulo_valor) for i in elegiveis],
        "cortados": [_linha_ranking(i, campo_valor, rotulo_valor) for i in cortados],
        "erros": erros,
        "avisos": avisos,
        "total_cotacoes": len(cotacoes),
        "manuais": len({r.get("produto_id") for r in cotacoes if r.get("fonte") == "manual"}),
        "regra": regra,
        "escolhido": escolhido,
        "porque": porque,
        "historico": cc.price_history(project),
        "ultimas": [
            {
                "data": r.get("data_coleta", "")[:16].replace("T", " "),
                "produto_id": r.get("produto_id", ""),
                "loja": r.get("loja", ""),
                "custo": cc.brl(r.get("custo_total")),
                "fonte": r.get("fonte", ""),
                "confirmacao": r.get("confirmacao", ""),
            }
            for r in cotacoes[-12:][::-1]
        ],
    }


#: Acoes que o painel oferece. Cada uma aponta para o comando equivalente do
#: CLI, para nao existir regra que so vale aqui.
ACOES = {
    "ranking": "ranking",
    "validar": "validar",
    "auditar": "auditar",
    "historico": "historico",
    "cotar": "cotar",
    "regenerar": "regenerar",
}


def acao(project: Path, nome: str, dados: dict[str, Any]) -> dict[str, Any]:
    """Executa uma acao. Sempre pelos caminhos do CLI, sempre sob a trava."""
    if nome not in ACOES:
        return {"ok": False, "erro": f"Acao desconhecida: {nome}"}

    # As funcoes do CLI imprimem no terminal. Aqui a resposta vai pelo JSON,
    # entao o print vira ruido no console de quem subiu o servidor.
    try:
        with cc.project_lock(project), contextlib.redirect_stdout(io.StringIO()):
            if nome == "cotar":
                return _gravar_cotacao(project, dados)
            alvo = argparse.Namespace(projeto=str(project), produto_id=None, strict=False)
            if nome == "ranking":
                cc.build_ranking(alvo)
            elif nome == "validar":
                cc.validate(alvo)
            elif nome == "auditar":
                cc.audit_score(alvo)
            elif nome == "historico":
                cc.show_history(alvo)
            elif nome == "regenerar":
                cc.regenerate(argparse.Namespace(projeto=str(project)))
        return {"ok": True, "mensagem": f"`{ACOES[nome]}` executado."}
    except SystemExit as erro:
        return {"ok": False, "erro": str(erro)}


CAMPOS_COTACAO = [
    "produto_id", "loja", "vendedor", "vendedor_tipo", "anuncio_id", "variacao",
    "preco", "preco_promocional", "frete", "frete_prazo_dias", "custo_extra",
    "custo_operacional_mensal", "valor_revenda_estimado",
    "nota", "avaliacoes", "garantia_meses", "garantia_tipo", "link", "fonte",
]


def _gravar_cotacao(project: Path, dados: dict[str, Any]) -> dict[str, Any]:
    """Uma cotacao nova, com a mesma validacao de entrada do CLI.

    Nao existe "editar cotacao" no painel de proposito: o `cotacoes.csv` e
    append-only, e a serie historica e o que desmascara preco ancora.
    """
    if not (dados.get("produto_id") or "").strip():
        return {"ok": False, "erro": "Escolha o produto."}
    if not (dados.get("loja") or "").strip():
        return {"ok": False, "erro": "Informe a loja."}

    numericos = {
        "preco": None, "preco_promocional": None, "frete": 0.0, "custo_extra": 0.0,
        "custo_operacional_mensal": 0.0, "valor_revenda_estimado": 0.0, "nota": 0.0,
    }
    valores: dict[str, Any] = {}
    for campo, padrao in numericos.items():
        bruto = str(dados.get(campo) or "").strip()
        if not bruto:
            valores[campo] = padrao
            continue
        try:
            valores[campo] = cc.real_number(bruto)
        except argparse.ArgumentTypeError as erro:
            return {"ok": False, "erro": f"{campo}: {erro}"}
    if valores["preco"] is None:
        return {"ok": False, "erro": "Informe o preco."}

    inteiros: dict[str, Any] = {}
    for campo in ["frete_prazo_dias", "avaliacoes", "garantia_meses"]:
        bruto = str(dados.get(campo) or "").strip()
        if not bruto:
            inteiros[campo] = None
            continue
        try:
            inteiros[campo] = int(cc.real_number(bruto))
        except (argparse.ArgumentTypeError, ValueError) as erro:
            return {"ok": False, "erro": f"{campo}: {erro}"}

    fonte = dados.get("fonte") or "manual"
    if fonte not in {"web", "manual"}:
        return {"ok": False, "erro": "fonte deve ser `web` ou `manual`."}
    vendedor_tipo = dados.get("vendedor_tipo") or "terceiro"
    if vendedor_tipo not in {"oficial", "terceiro", "fisica"}:
        return {"ok": False, "erro": "vendedor_tipo invalido."}
    garantia_tipo = dados.get("garantia_tipo") or "nenhuma"
    if garantia_tipo not in {"nacional", "importada", "vendedor", "nenhuma"}:
        return {"ok": False, "erro": "garantia_tipo invalido."}

    alvo = argparse.Namespace(
        projeto=str(project),
        produto_id=str(dados["produto_id"]).strip(),
        loja=str(dados["loja"]).strip(),
        vendedor=str(dados.get("vendedor") or "").strip(),
        vendedor_tipo=vendedor_tipo,
        anuncio_id=str(dados.get("anuncio_id") or "").strip() or None,
        variacao=str(dados.get("variacao") or "").strip() or None,
        preco=valores["preco"],
        preco_promocional=valores["preco_promocional"],
        frete=valores["frete"],
        frete_prazo_dias=inteiros["frete_prazo_dias"],
        custo_extra=valores["custo_extra"],
        custo_total=None,
        custo_operacional_mensal=valores["custo_operacional_mensal"],
        tco_meses=None,
        valor_revenda_estimado=valores["valor_revenda_estimado"],
        nota=valores["nota"],
        avaliacoes=inteiros["avaliacoes"] or 0,
        garantia_meses=inteiros["garantia_meses"],
        garantia_tipo=garantia_tipo,
        link=str(dados.get("link") or "").strip() or None,
        flag_suspeita="",
        fonte=fonte,
        data=None,
    )
    try:
        cc.add_quote(alvo)
    except SystemExit as erro:
        return {"ok": False, "erro": str(erro)}

    cc.build_ranking(argparse.Namespace(projeto=str(project)))
    cc.validate(argparse.Namespace(projeto=str(project), strict=False))
    return {"ok": True, "mensagem": f"Cotacao `{fonte}` gravada e ranking refeito."}


def projetos_disponiveis() -> list[str]:
    return [p.name for p in cc.project_dirs()]


# --------------------------------------------------------------------------- #
# Pagina
# --------------------------------------------------------------------------- #

ESTILO = """
:root{color-scheme:light dark;
--bg:#f6f5f1;--sup:#fff;--ink:#1c1c1a;--fraco:#6b6862;--linha:#ddd7cb;
--teal:#0f766e;--verde:#2f7d32;--ambar:#b7791f;--coral:#b45342;
--edit:#fffbe8;--edit-b:#e0c97a;--barra:#e0dbcd;--zebra:#faf8f4}
@media (prefers-color-scheme:dark){:root{
--bg:#14140f;--sup:#1e1e19;--ink:#f0ece2;--fraco:#a09b90;--linha:#35342c;
--teal:#5eead4;--verde:#86e08a;--ambar:#f0c674;--coral:#f0a08c;
--edit:#2c2716;--edit-b:#6b5a2a;--barra:#2c2b24;--zebra:#1a1a15}}
*{box-sizing:border-box;margin:0;padding:0}
body{font:14px/1.5 "Segoe UI",system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--ink)}
.wrap{max-width:1180px;margin:0 auto;padding:18px}
h1{font-size:19px;line-height:1.2}
.sub{color:var(--fraco);font-size:12.5px;margin:2px 0 14px}
.acts{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:14px}
button{font:inherit;font-size:12.5px;padding:6px 12px;border-radius:6px;cursor:pointer;
background:var(--sup);border:1px solid var(--linha);color:var(--ink)}
button:hover{border-color:var(--teal)}
button.p{background:var(--teal);border-color:var(--teal);color:#04201d;font-weight:600}
button:disabled{opacity:.5;cursor:wait}
.card{background:var(--sup);border:1px solid var(--linha);border-radius:9px;margin-bottom:12px;overflow:hidden}
.card h2{font-size:13px;padding:11px 13px;border-bottom:1px solid var(--linha);color:var(--fraco);
text-transform:uppercase;letter-spacing:.5px}
.card .in{padding:13px}
table{width:100%;border-collapse:collapse}
th{background:var(--zebra);text-align:left;padding:8px 11px;font-size:11px;color:var(--fraco);font-weight:600}
td{padding:9px 11px;border-top:1px solid var(--linha);vertical-align:middle;font-size:13px}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tr.cut td{color:var(--fraco);background:var(--zebra)}
.nm{font-weight:600}
.mini{color:var(--fraco);font-size:11px}
.bars{display:flex;gap:2px}
.b{width:15px;height:6px;border-radius:2px;background:var(--barra)}
.b.f{background:var(--teal)}.b.n{background:var(--linha)}
.pill{display:inline-block;border-radius:99px;padding:2px 8px;font-size:10.5px;font-weight:600;background:var(--barra);color:var(--ink)}
.pill.ok{background:#dff0df;color:#2f7d32}.pill.bad{background:#f5d7d1;color:#b45342}
.pill.warn{background:#faedcc;color:#8a6516}
@media (prefers-color-scheme:dark){.pill.ok{background:#1e3a1f;color:#86e08a}
.pill.bad{background:#43231c;color:#f0a08c}.pill.warn{background:#3d3218;color:#f0c674}}
.form{display:grid;grid-template-columns:repeat(auto-fit,minmax(115px,1fr));gap:9px}
label{font-size:10.5px;color:var(--fraco);display:block;margin-bottom:3px}
input,select{width:100%;padding:6px 8px;border:1px solid var(--linha);border-radius:5px;
font:inherit;font-size:12.5px;background:var(--edit);color:var(--ink)}
input:focus,select:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 2px color-mix(in srgb,var(--teal) 22%,transparent)}
.aviso{border-left:3px solid var(--ambar);background:color-mix(in srgb,var(--ambar) 12%,transparent);
padding:8px 11px;font-size:12px;border-radius:0 5px 5px 0;margin-bottom:6px}
.aviso.e{border-left-color:var(--coral);background:color-mix(in srgb,var(--coral) 12%,transparent)}
.msg{padding:9px 12px;border-radius:6px;font-size:12.5px;margin-bottom:12px;display:none}
.msg.ok{display:block;background:color-mix(in srgb,var(--verde) 15%,transparent);border:1px solid var(--verde)}
.msg.err{display:block;background:color-mix(in srgb,var(--coral) 15%,transparent);border:1px solid var(--coral);white-space:pre-wrap}
.nota{font-size:11.5px;color:var(--fraco);margin-top:9px;line-height:1.55}
code{background:var(--barra);padding:1px 5px;border-radius:3px;font-size:11.5px}
.grid4{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:9px;margin-bottom:12px}
.kpi{background:var(--sup);border:1px solid var(--linha);border-radius:9px;padding:11px}
.kpi b{display:block;font-size:22px;line-height:1.1}
.kpi span{color:var(--fraco);font-size:11px}
@media(max-width:820px){.card{overflow-x:auto}table{min-width:640px}}
"""

PAGINA = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel &mdash; Central de Compras</title><style>__ESTILO__</style></head>
<body><div class="wrap" id="app">Carregando...</div>
<script>
const $ = s => document.querySelector(s);
let E = null, PROJ = new URLSearchParams(location.search).get("projeto") || "";

const brl = v => (v||v===0) ? v : "-";
const esc = s => String(s==null?"":s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

function barras(l){
  const ordem=["qualidade","valor","risco","aderencia","conveniencia"];
  return '<div class="bars">'+ordem.map(e=>{
    if(l.sem_dado.includes(e)) return '<span class="b n" title="'+e+': sem dado"></span>';
    const v=l.eixos[e]||0;
    return '<span class="b'+(v>=.5?' f':'')+'" style="opacity:'+(0.35+v*0.65).toFixed(2)+'" title="'+e+' '+v.toFixed(2)+'"></span>';
  }).join("")+'</div>';
}

function linha(l, cortado){
  const sit = cortado
    ? '<span class="pill bad">'+esc(l.cortes[0]||"cortado")+'</span>'
    : (l.espera ? '<span class="pill warn">aguardando preco</span>'
               : (l.vencida ? '<span class="pill warn">cotacao vencida</span>'
                            : '<span class="pill ok">elegivel</span>'));
  return '<tr'+(cortado?' class="cut"':'')+'>'
    +'<td><span class="nm">'+esc(l.nome)+'</span><br><span class="mini">'+esc(l.loja)+(l.vendedor?' &middot; '+esc(l.vendedor):'')+'</span></td>'
    +'<td class="n"><b>'+(cortado?0:l.score.toFixed(1))+'</b></td>'
    +'<td>'+(cortado?'&mdash;':barras(l))+'</td>'
    +'<td class="n">'+Math.round(l.confianca*100)+'%</td>'
    +'<td class="n">'+esc(l.custo_texto)+'</td>'
    +'<td class="n">'+(l.prazo||'&mdash;')+'</td>'
    +'<td><span class="pill">'+esc(l.fonte)+'</span></td>'
    +'<td>'+sit+'</td></tr>';
}

function desenha(){
  const todos=[...E.elegiveis,...E.cortados];
  const opts=todos.map(l=>'<option value="'+esc(l.produto_id)+'">'+esc(l.nome)+'</option>').join("");
  const r=E.regra||{};
  $("#app").innerHTML = `
  <h1>${esc(E.projeto)}</h1>
  <div class="sub">${esc(E.categoria)} &middot; ${esc(E.estado)} &middot; teto ${esc(E.preco_teto||"sem teto")}
   &middot; compara por <b>${esc(E.base_valor)}</b> &middot; confianca minima ${Math.round(E.confianca_minima*100)}%</div>
  <div id="msg" class="msg"></div>
  <div class="acts">
    <button class="p" data-a="ranking">Recalcular ranking</button>
    <button data-a="validar">Validar</button>
    <button data-a="auditar">Memoria de calculo</button>
    <button data-a="historico">Historico de preco</button>
    <button data-a="regenerar">Regenerar tudo</button>
  </div>
  <div class="grid4">
    <div class="kpi"><b>${E.total_cotacoes}</b><span>cotacoes</span></div>
    <div class="kpi"><b>${E.manuais}</b><span>produtos com cotacao manual</span></div>
    <div class="kpi"><b>${E.erros.length}</b><span>erros</span></div>
    <div class="kpi"><b>${E.avisos.length}</b><span>avisos</span></div>
  </div>
  <div class="card"><h2>Ranking</h2>
    <table><thead><tr><th>Produto</th><th class="n">Score</th><th>Eixos</th>
    <th class="n">Conf.</th><th class="n">${esc(E.base_valor)}</th><th class="n">Prazo</th>
    <th>Fonte</th><th>Situacao</th></tr></thead><tbody>
    ${todos.length? E.elegiveis.map(l=>linha(l,false)).join("")+E.cortados.map(l=>linha(l,true)).join("")
      : '<tr><td colspan="8">Nenhum candidato ainda.</td></tr>'}
    </tbody></table>
    <div class="in nota">Barra cinza no fim = eixo <b>sem dado</b>, que fica fora da conta.
     Por isso a confianca nao e 100%. Score so e comparavel dentro deste projeto.</div>
  </div>
  <div class="card"><h2>Nova cotacao</h2><div class="in">
    <div class="form">
      <div><label>Produto</label><select id="f_produto_id">${opts}</select></div>
      <div><label>Fonte</label><select id="f_fonte"><option value="manual">manual (conferi no site)</option><option value="web">web (estimativa)</option></select></div>
      <div><label>Loja</label><input id="f_loja" placeholder="Amazon"></div>
      <div><label>Vendedor</label><input id="f_vendedor"></div>
      <div><label>Tipo</label><select id="f_vendedor_tipo"><option>oficial</option><option selected>terceiro</option><option>fisica</option></select></div>
      <div><label>Preco</label><input id="f_preco" placeholder="289"></div>
      <div><label>Frete</label><input id="f_frete" placeholder="0"></div>
      <div><label>Prazo (dias)</label><input id="f_frete_prazo_dias" placeholder="3"></div>
      <div><label>Nota</label><input id="f_nota" placeholder="4.8"></div>
      <div><label>Avaliacoes</label><input id="f_avaliacoes" placeholder="5360"></div>
      <div><label>Garantia (meses)</label><input id="f_garantia_meses" placeholder="12"></div>
      <div><label>Garantia</label><select id="f_garantia_tipo"><option>nacional</option><option>importada</option><option>vendedor</option><option selected>nenhuma</option></select></div>
      <div style="grid-column:span 2"><label>Link</label><input id="f_link" placeholder="https://..."></div>
      <div><label>Anuncio</label><input id="f_anuncio_id" placeholder="MLB..."></div>
      <div style="display:flex;align-items:flex-end"><button class="p" id="salvar" style="width:100%">Gravar cotacao</button></div>
    </div>
    <div class="nota"><b>Grava uma linha nova</b> no <code>cotacoes.csv</code>. Nunca sobrescreve:
     a serie historica e o que desmascara preco ancora. Editar cotacao antiga nao existe aqui, de proposito.</div>
  </div></div>
  ${(E.erros.length||E.avisos.length)? '<div class="card"><h2>Precisa da sua mao</h2><div class="in">'
    + E.erros.map(t=>'<div class="aviso e">'+esc(t)+'</div>').join("")
    + E.avisos.map(t=>'<div class="aviso">'+esc(t)+'</div>').join("")
    + (r.faixa? '<div class="nota">Regra de parada ('+esc(r.faixa)+'): ate '+esc(r.tempo_maximo)
      +', '+r.candidatos+' candidatos, '+esc(r.cotacoes_minimas_texto)+' cotacao(oes) cada. Hoje: '
      +r.candidatos_atuais+' candidatos, '+(r.dias_em_pesquisa==null?'?':r.dias_em_pesquisa)+' dias.</div>':'')
    + '</div></div>' : ''}
  <div class="card"><h2>Ultimas cotacoes</h2>
    <table><thead><tr><th>Data</th><th>Produto</th><th>Loja</th><th class="n">Custo</th><th>Fonte</th><th>Confirmacao</th></tr></thead><tbody>
    ${E.ultimas.length? E.ultimas.map(u=>'<tr><td class="mini">'+esc(u.data)+'</td><td>'+esc(u.produto_id)
      +'</td><td>'+esc(u.loja)+'</td><td class="n">'+esc(u.custo)+'</td><td><span class="pill">'+esc(u.fonte)
      +'</span></td><td class="mini">'+esc(u.confirmacao)+'</td></tr>').join("")
      : '<tr><td colspan="6">Sem cotacoes.</td></tr>'}
    </tbody></table></div>`;

  document.querySelectorAll("[data-a]").forEach(b=>b.onclick=()=>executa(b.dataset.a,{},b));
  $("#salvar").onclick = e => {
    const d={};
    ["produto_id","fonte","loja","vendedor","vendedor_tipo","preco","frete","frete_prazo_dias",
     "nota","avaliacoes","garantia_meses","garantia_tipo","link","anuncio_id"]
      .forEach(k => d[k] = ($("#f_"+k)||{}).value || "");
    executa("cotar", d, e.target);
  };
}

function aviso(txt, ok){
  const m=$("#msg"); m.className="msg "+(ok?"ok":"err"); m.textContent=txt;
  if(ok) setTimeout(()=>{m.className="msg";}, 4000);
}

async function executa(nome, dados, botao){
  if(botao) botao.disabled=true;
  try{
    const r = await fetch("/api/acao", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({projeto:PROJ, acao:nome, dados})});
    const j = await r.json();
    await carrega();
    aviso(j.ok ? j.mensagem : j.erro, j.ok);
  }catch(err){ aviso(String(err), false); }
  finally{ if(botao) botao.disabled=false; }
}

async function carrega(){
  const r = await fetch("/api/estado?projeto="+encodeURIComponent(PROJ));
  const j = await r.json();
  if(j.erro){ $("#app").textContent = j.erro; return; }
  E = j; PROJ = j.projeto; desenha();
}
carrega();
</script></body></html>
"""


def pagina() -> str:
    return PAGINA.replace("__ESTILO__", ESTILO)


# --------------------------------------------------------------------------- #
# Servidor
# --------------------------------------------------------------------------- #


def _resolver(nome: str | None) -> Path:
    disponiveis = cc.project_dirs()
    if not disponiveis:
        raise SystemExit("Nenhum projeto em `projetos/`. Crie um com `novo-projeto`.")
    if not nome:
        return disponiveis[-1]
    return cc.project_path(nome)


class _Handler(BaseHTTPRequestHandler):
    server_version = "CentralCompras"

    def log_message(self, *_):  # silencia o log de cada request
        pass

    def _json(self, dados: dict[str, Any], status: int = 200) -> None:
        corpo = json.dumps(dados, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self) -> None:
        from urllib.parse import parse_qs, urlparse

        rota = urlparse(self.path)
        if rota.path in {"/", "/index.html"}:
            corpo = pagina().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        if rota.path == "/api/estado":
            pedido = parse_qs(rota.query).get("projeto", [""])[0]
            try:
                self._json(estado(_resolver(pedido)))
            except SystemExit as erro:
                self._json({"erro": str(erro)}, 404)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/api/acao":
            self.send_error(404)
            return
        content_type = self.headers.get("Content-Type") or ""
        parts = [p.strip() for p in content_type.split(";")]
        if not parts or parts[0].lower() != "application/json":
            self._json({"ok": False, "erro": "Content-Type precisa ser application/json."}, 415)
            return
        raw_length = self.headers.get("Content-Length")
        if raw_length is not None:
            try:
                tamanho = int(raw_length)
                if tamanho < 0:
                    raise ValueError()
            except ValueError:
                self._json({"ok": False, "erro": "Content-Length invalido."}, 400)
                return
        else:
            tamanho = 0
        if tamanho > 1_000_000:
            self._json({"ok": False, "erro": "Pedido grande demais."}, 413)
            return
        try:
            pedido = json.loads(self.rfile.read(tamanho) or b"{}")
        except json.JSONDecodeError:
            self._json({"ok": False, "erro": "JSON invalido."}, 400)
            return
        try:
            project = _resolver(pedido.get("projeto"))
        except SystemExit as erro:
            self._json({"ok": False, "erro": str(erro)}, 404)
            return
        self._json(acao(project, pedido.get("acao", ""), pedido.get("dados") or {}))


def servir(args: argparse.Namespace) -> None:
    """Sobe o painel. Preso em 127.0.0.1: ele escreve no repo."""
    project = _resolver(getattr(args, "projeto", None))
    servidor = ThreadingHTTPServer(("127.0.0.1", args.porta), _Handler)
    url = f"http://127.0.0.1:{args.porta}/?projeto={project.name}"
    print(f"Painel de `{project.name}` em {url}")
    print("No VS Code: Ctrl+Shift+P > Simple Browser: Show > cole a URL.")
    print("Ctrl+C para encerrar.")
    if not getattr(args, "sem_navegador", False):
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nPainel encerrado.")
    finally:
        servidor.server_close()


# --------------------------------------------------------------------------- #
# Artifact: a versao so-leitura, para consultar do celular
# --------------------------------------------------------------------------- #

ARTIFACT_ESTILO = ESTILO + """
.wrap{max-width:820px}
.rowc{background:var(--sup);border:1px solid var(--linha);border-radius:9px;padding:12px;margin-bottom:8px}
.rowc.cut{opacity:.62}
.top{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.sc{font-size:20px;font-weight:700;color:var(--teal);font-variant-numeric:tabular-nums}
.sc.z{color:var(--coral);font-size:14px}
.eixos{display:flex;gap:3px;margin-top:9px}
.eixos .b{flex:1;width:auto}
.leg{display:flex;gap:3px;margin-top:4px;font-size:9.5px;color:var(--fraco)}
.leg span{flex:1;text-align:center}
.foot{color:var(--fraco);font-size:11.5px;text-align:center;padding:18px 0;line-height:1.7}
"""


def _bloco_produto(linha: dict[str, Any], cortado: bool) -> str:
    from html import escape as esc

    ordem = ["qualidade", "valor", "risco", "aderencia", "conveniencia"]
    if cortado:
        barras = ""
    else:
        pedacos = []
        for eixo in ordem:
            if eixo in linha["sem_dado"]:
                pedacos.append('<span class="b n"></span>')
            else:
                v = linha["eixos"].get(eixo, 0)
                pedacos.append(f'<span class="b{" f" if v >= 0.5 else ""}" style="opacity:{0.35 + v * 0.65:.2f}"></span>')
        barras = (
            '<div class="eixos">' + "".join(pedacos) + "</div>"
            '<div class="leg"><span>qual</span><span>valor</span><span>risco</span>'
            "<span>ader</span><span>conv</span></div>"
        )
    marca = ""
    if cortado and linha["cortes"]:
        marca = f'<span class="pill bad">{esc(linha["cortes"][0])}</span>'
    elif linha["espera"]:
        marca = '<span class="pill warn">aguardando preco</span>'
    elif linha["vencida"]:
        marca = '<span class="pill warn">cotacao vencida</span>'
    return (
        f'<div class="rowc{" cut" if cortado else ""}">'
        f'<div class="top"><span class="nm">{esc(linha["nome"])}</span>'
        f'<span class="sc{" z" if cortado else ""}">{"cortado" if cortado else f"{linha['score']:.1f}"}</span></div>'
        f'<div class="mini">{esc(linha["custo_texto"])} &middot; {esc(linha["loja"])} '
        f'&middot; confianca {linha["confianca"]:.0%}</div>'
        f"{barras}"
        + (f'<div style="margin-top:8px">{marca}</div>' if marca else "")
        + "</div>"
    )


def artifact_fragmento() -> str:
    """A pagina sem o esqueleto do documento.

    Publicar como artifact do claude.ai exige o conteudo direto: o `<!doctype>`,
    `<html>`, `<head>` e `<body>` sao postos pela plataforma. Gerar aqui, e nao
    remover na mao depois, mantem as duas versoes sempre iguais.
    """
    completa = artifact_html()
    corpo = completa.split("<body>", 1)[1].rsplit("</body>", 1)[0]
    estilo = completa.split("<style>", 1)[1].split("</style>", 1)[0]
    return (
        "<title>Central de Compras</title>\n"
        f"<style>{estilo}</style>\n"
        f"{corpo}\n"
    )


def artifact_html() -> str:
    """Foto do repositorio inteiro, so leitura, boa de ler no celular."""
    from html import escape as esc

    partes: list[str] = []
    total_projetos = 0
    total_cotacoes = 0
    total_manuais = 0
    total_pendencias = 0

    for project in cc.project_dirs():
        e = estado(project)
        total_projetos += 1
        total_cotacoes += e["total_cotacoes"]
        total_manuais += e["manuais"]
        total_pendencias += len(e["erros"]) + len(e["avisos"])
        partes.append(f'<h2>{esc(e["projeto"])}</h2>')
        if e["escolhido"]:
            partes.append(f'<div class="rowc"><b>Escolhido: {esc(e["escolhido"])}</b>'
                          f'<div class="mini">{esc(e["porque"])}</div></div>')
        for linha in e["elegiveis"]:
            partes.append(_bloco_produto(linha, False))
        for linha in e["cortados"]:
            partes.append(_bloco_produto(linha, True))
        for texto in e["erros"]:
            partes.append(f'<div class="aviso e">{esc(texto)}</div>')
        for texto in e["avisos"]:
            partes.append(f'<div class="aviso">{esc(texto)}</div>')

    aguardando = len(cc.waiting_price_rows())
    cabecalho = (
        f'<h1>Central de Compras</h1>'
        f'<div class="sub">foto do repositorio &middot; {cc.now_iso()[:16].replace("T", " ")}</div>'
        '<div class="grid4">'
        f'<div class="kpi"><b>{total_projetos}</b><span>compras</span></div>'
        f'<div class="kpi"><b>{total_manuais}</b><span>cotacoes confirmadas</span></div>'
        f'<div class="kpi"><b>{aguardando}</b><span>aguardando preco</span></div>'
        f'<div class="kpi"><b>{total_pendencias}</b><span>pendencias</span></div>'
        "</div>"
    )
    rodape = (
        '<div class="foot">So leitura. Cotar e decidir e no painel local,<br>'
        "onde o repositorio e a verdade.<br>"
        f"<code>python scripts/central_compras.py painel</code></div>"
    )
    return (
        "<!doctype html>\n<html lang=\"pt-BR\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Central de Compras</title><style>"
        + ARTIFACT_ESTILO
        + '</style></head><body><div class="wrap">'
        + cabecalho
        + "".join(partes)
        + rodape
        + "</div></body></html>\n"
    )


def gerar_artifact(args: argparse.Namespace) -> None:
    destino = cc.DASHBOARD / "artifact.html"
    cc.atomic_write_text(destino, artifact_html())
    print(destino)
    if getattr(args, "fragmento", None):
        alvo = Path(args.fragmento)
        cc.atomic_write_text(alvo, artifact_fragmento())
        print(alvo)
    print("Pagina unica, so leitura. Pronta para publicar como artifact.")
