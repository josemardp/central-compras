"""Conferencia do PRECO na propria loja (so leitura, API publica de catalogo VTEX) e relacao com o preco anunciado pela comunidade.

Tres niveis de preco que NUNCA se misturam:
  anunciado   o que a fonte (Promobit, Gatry...) publicou; pode ja embutir um cupom
  confirmado  o que a PAGINA/API da loja mostra agora, SEM cupom (so para lojas configuradas em config/radar_lojas.yaml)
  entregue    com frete e prazo para o seu CEP: so o carrinho sabe; o radar nunca inventa (CEP e dado pessoal e nao e usado)

Esta consulta nao segue o link da oferta (que passa pelo rastreador de afiliado da comunidade): consulta o catalogo da loja pelo SKU do catalogo.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, Callable

import yaml

from . import caminhos, catalogo
from .fontes.base import FonteErro, http_get

ARQ = caminhos.CONFIG_DIR / "radar_lojas.yaml"
TOLERANCIA_REAIS = 1.0


def carregar(caminho: Path | None = None) -> dict[str, Any]:
    try:
        return (yaml.safe_load((caminho or ARQ).read_text(encoding="utf-8")) or {}).get("lojas") or {}
    except OSError:
        return {}


def _norm(t: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", catalogo.normalizar(t or ""))


def _agora(agora: dt.datetime | None) -> str:
    return (agora or dt.datetime.now()).strftime("%Y-%m-%d %H:%M")


def _vazio(status: str, nota: str, agora: dt.datetime | None = None) -> dict[str, Any]:
    return {"status": status, "preco_loja": None, "preco_lista": None, "vendedor": None, "proprio": False, "disponivel": None,
            "link": None, "ean": None, "verificado_em": _agora(agora), "nota": nota}


def verificar(
    produto_id: str, pcat: dict[str, Any], loja_nome: str | None, cat: dict[str, Any] | None = None, *,
    lojas: dict[str, Any] | None = None, baixar: Callable[[str], str] = http_get, agora: dt.datetime | None = None,
) -> dict[str, Any]:
    """Preco do produto EXATO na loja, do vendedor proprio. `status`: confirmado | indisponivel | nao_encontrado | nao_verificavel | erro."""
    cat = cat or catalogo.carregar()
    lojas = lojas if lojas is not None else carregar()
    chave = _norm(loja_nome)
    cfg = lojas.get(chave)
    if not cfg or cfg.get("tipo") != "vtex":
        return _vazio("nao_verificavel", "loja sem verificacao publica configurada: preco NAO conferido na loja", agora)
    skus = [s for s in (pcat.get("skus") or []) if s]
    if not skus:
        return _vazio("nao_verificavel", "produto sem SKU no catalogo: nao ha como buscar o produto exato", agora)
    achados: list[dict[str, Any]] = []
    try:
        for sku in skus[:2]:
            url = f"{cfg['base']}/api/catalog_system/pub/products/search?ft={urllib.parse.quote(sku)}"
            for p in json.loads(baixar(url)):
                c = catalogo.identificar(str(p.get("productName") or ""), cat)
                if not c or c.produto_id != produto_id:
                    continue  # outro modelo/variante: nao e o produto exato
                for it in p.get("items") or []:
                    for s in it.get("sellers") or []:
                        co = s.get("commertialOffer") or {}
                        if co.get("Price") is None:
                            continue
                        achados.append({"preco": float(co["Price"]), "lista": float(co.get("ListPrice") or 0) or None, "qtd": int(co.get("AvailableQuantity") or 0),
                                        "vendedor": str(s.get("sellerName") or ""), "ean": it.get("ean"), "link": p.get("link"),
                                        "proprio": _norm(cfg.get("vendedor_contem")) in _norm(s.get("sellerName"))})
    except (FonteErro, ValueError, KeyError, TypeError) as exc:
        return _vazio("erro", f"consulta a loja falhou ({type(exc).__name__}): {str(exc)[:80]}", agora)
    proprios = [a for a in achados if a["proprio"]]
    if not proprios:
        return _vazio("nao_encontrado", "produto exato nao encontrado no estoque PROPRIO da loja (so terceiros ou nada)", agora)
    com_estoque = [a for a in proprios if a["qtd"] > 0]
    melhor = min(com_estoque or proprios, key=lambda a: a["preco"])
    return {"status": "confirmado" if com_estoque else "indisponivel", "preco_loja": melhor["preco"], "preco_lista": melhor["lista"],
            "vendedor": melhor["vendedor"], "proprio": True, "disponivel": bool(com_estoque), "link": melhor["link"], "ean": melhor["ean"],
            "verificado_em": _agora(agora), "nota": "preco da API publica da loja, SEM cupom, sem frete"}


def relacionar(preco_anunciado: float | None, loja: dict[str, Any] | None, cupom_proprio: str | None) -> dict[str, Any]:
    """Compara o anunciado com o confirmado na loja. `relacao`: igual | depende_de_cupom | loja_mais_cara | loja_mais_barata | sem_confirmacao."""
    if not loja or loja.get("status") != "confirmado" or preco_anunciado is None or loja.get("preco_loja") is None:
        return {"relacao": "sem_confirmacao", "diferenca": None}
    dif = round(float(loja["preco_loja"]) - float(preco_anunciado), 2)
    if abs(dif) <= max(TOLERANCIA_REAIS, 0.005 * float(preco_anunciado)):
        return {"relacao": "igual", "diferenca": dif}
    if dif > 0:
        return {"relacao": "depende_de_cupom" if cupom_proprio else "loja_mais_cara", "diferenca": dif}
    return {"relacao": "loja_mais_barata", "diferenca": dif}


def conferir_oferta(con, oferta_id: int, cat: dict[str, Any] | None = None, agora: dt.datetime | None = None) -> dict[str, Any]:
    """Inspecao completa de UMA oferta registrada (somente leitura): produto exato, fonte, loja e os tres niveis de preco."""
    from . import varredura

    cat = cat or catalogo.carregar()
    o = con.execute("SELECT * FROM ofertas WHERE id=?", (oferta_id,)).fetchone()
    if o is None:
        raise ValueError(f"oferta {oferta_id} nao encontrada")
    ativa, motivo_fonte = varredura.revalidar_oferta(con, oferta_id)
    c = catalogo.identificar(o["titulo"], cat)
    pcat = cat["produtos"].get(o["produto"] or "", {})
    loja = verificar(o["produto"], pcat, o["loja"], cat, agora=agora) if o["produto"] else _vazio("nao_verificavel", "oferta sem produto do catalogo", agora)
    rel = relacionar(o["preco_anunciado"], loja, o["cupom_codigo"])
    return {
        "oferta_id": oferta_id, "titulo": o["titulo"], "produto": o["produto"], "modelo": pcat.get("nome"), "skus_catalogo": pcat.get("skus"),
        "voltagem_catalogo": pcat.get("tensao"), "avisos_do_titulo": list(c.avisos) if c else None, "loja": o["loja"], "vendedor_na_fonte": o["vendedor"],
        "fonte": {"nome": o["fonte"], "ativa": ativa, "detalhe": motivo_fonte, "url": o["url"], "publicado_em": o["publicado_em"]},
        "cupom": {"codigo": o["cupom_codigo"], "status": o["status_cupom"], "regra": "valor NAO informado pela fonte (so o codigo)" if o["cupom_codigo"] else None},
        "precos": {"anunciado": o["preco_anunciado"], "confirmado_na_loja": loja.get("preco_loja"), "lista_na_loja": loja.get("preco_lista"),
                   "entregue": None, "frete": "nao informado (frete e prazo dependem do CEP; so o carrinho sabe)"},
        "loja_conferida": loja, "relacao": rel,
    }


def formatar_conferencia(r: dict[str, Any]) -> str:
    def brl(v):
        return "n/d" if v is None else f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    p, lj, rel = r["precos"], r["loja_conferida"], r["relacao"]
    L = [f"== CONFERENCIA DA OFERTA #{r['oferta_id']} (somente leitura)",
         f"Produto: {r['modelo']} ({r['produto']}) | SKU do catalogo {r['skus_catalogo']} | voltagem {r['voltagem_catalogo']}V | avisos do titulo: {r['avisos_do_titulo'] or 'nenhum'}",
         f"Titulo: {r['titulo']}",
         f"Fonte: {r['fonte']['nome']} | {'ATIVA' if r['fonte']['ativa'] else 'NAO ATIVA'} ({r['fonte']['detalhe']}) | publicada {r['fonte']['publicado_em']}",
         f"Loja: {r['loja']} | vendedor na fonte: {r['vendedor_na_fonte'] or 'nao informado'} | na loja: {lj.get('vendedor') or 'n/d'} ({'estoque PROPRIO' if lj.get('proprio') else 'nao confirmado'}) | disponivel: {lj.get('disponivel')}",
         f"Cupom: {r['cupom']['codigo'] or 'nenhum'} [{r['cupom']['status'] or '-'}] {r['cupom']['regra'] or ''}",
         "", "PRECOS (nunca se misturam):",
         f"  anunciado (fonte)      {brl(p['anunciado'])}",
         f"  confirmado (loja)      {brl(p['confirmado_na_loja'])}  sem cupom, lista {brl(p['lista_na_loja'])}  [{lj['status']}: {lj['nota']}]",
         f"  entregue (com frete)   n/d  {p['frete']}",
         "", f"RELACAO: {rel['relacao']}" + (f" (diferenca {brl(rel['diferenca'])})" if rel["diferenca"] is not None else "")]
    if rel["relacao"] == "depende_de_cupom":
        L.append(f"  => O anunciado ({brl(p['anunciado'])}) so vale COM o cupom {r['cupom']['codigo']}; sem ele a loja cobra {brl(p['confirmado_na_loja'])}. "
                 "O cupom NAO esta confirmado: o preco garantido hoje e o da loja.")
    return "\n".join(L)
