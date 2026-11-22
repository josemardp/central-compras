"""Ofertas de produtos EQUIVALENTES (mesma classe tecnica, outra marca/modelo) mais baratas que o seu melhor preco atual.

So para splits (classe bem definida por capacidade, inverter, so frio, 220V). SEMPRE informativo, NUNCA alerta:
o equivalente nao passou pelo seu gate de qualidade (reputacao da marca, assistencia, garantia nacional, nota), entao
"mais barato" nao quer dizer "melhor compra". Serve para voce decidir se vale abrir uma pesquisa.
"""

from __future__ import annotations

import re
from typing import Any

from . import catalogo
from .catalogo import normalizar
from .modelos import Oferta

CLASSES = {
    "ares_12k": {"btu": 12000, "rotulo": "split 12.000 BTU inverter so frio 220V"},
    "ares_18k": {"btu": 18000, "rotulo": "split 18.000 BTU inverter so frio 220V"},
}


def classe_do_texto(texto: str) -> str | None:
    t = normalizar(texto)
    if not re.search(r"\b(ar[- ]?condicionado|split)\b", t) or not re.search(r"\binverter\b", t):
        return None
    if re.search(r"quente|portatil|janela|\bpiso\b|cassete|\bk7\b|multi\b", t):
        return None
    if not re.search(r"\bfrio\b", t):
        return None
    tensoes = catalogo._tensoes_mencionadas(t)
    if tensoes != {220}:
        return None  # sem voltagem ou 127V/bivolt: nao e equivalente do SEU (220V)
    btus = catalogo._btus_mencionados(t)
    for nome, esp in CLASSES.items():
        if btus == {esp["btu"]}:
            return nome
    return None


def levantar(ofertas: list[Oferta], melhores: dict[str, float], cat: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """`melhores`: {classe: seu melhor preco atual}. Junta o mesmo anuncio vindo de varias fontes."""
    cat = cat or catalogo.carregar()
    grupos: dict[str, dict[str, Any]] = {}
    for o in ofertas:
        if (o.extras or {}).get("tipo") == "cupom_loja" or (o.canal or "").startswith("cupom_loja") or not o.preco_anunciado:
            continue
        if catalogo.identificar(f"{o.titulo} {o.texto}", cat) is not None:
            continue  # e um dos seus 12 produtos: o fluxo normal cuida
        classe = classe_do_texto(o.titulo)
        if not classe:
            continue
        # Mesmo anuncio em varias fontes: mesma classe + mesma loja + preco ate R$ 2 de diferenca (os titulos variam: um traz o codigo do modelo).
        base = f"{classe}|{normalizar(o.loja or '')}|"
        achada = next((k for k, g in grupos.items() if k.startswith(base) and abs(g["precos"][0] - float(o.preco_anunciado)) <= 2.0
                       and len(set(re.findall(r"[a-z]{4,}", normalizar(g["titulo"]))) & set(re.findall(r"[a-z]{4,}", normalizar(o.titulo)))) >= 3), None)
        chave = achada or f"{base}{len(grupos)}"
        g = grupos.setdefault(chave, {"classe": classe, "titulo": o.titulo[:90], "loja": o.loja, "fontes": set(), "precos": [], "publicado_em": o.publicado_em, "url": o.url})
        g["fontes"].add(o.fonte)
        g["precos"].append(float(o.preco_anunciado))
        if o.url and ("amazon" in o.url or not g["url"]):
            g["url"] = o.url
    saida = []
    for g in grupos.values():
        preco = min(g["precos"])
        nosso = melhores.get(g["classe"])
        saida.append({**g, "fontes": sorted(g["fontes"]), "n_fontes": len(g["fontes"]), "preco": preco, "seu_melhor_preco": nosso,
                      "economia": round(nosso - preco, 2) if nosso else None,
                      "economia_pct": round(100.0 * (nosso - preco) / nosso, 1) if nosso else None,
                      "mais_barato_que_o_seu": bool(nosso and preco < nosso - 0.5),
                      "aviso": "nao passou pelo seu gate de qualidade (marca, assistencia, garantia nacional, nota): so uma pista"})
    return sorted(saida, key=lambda r: -(r["economia"] or 0))
