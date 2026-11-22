"""Cruzamento de cupons de LOJA (sem produto na publicacao) com os produtos do catalogo.

Pergunta: "este cupom da Amazon/KaBuM/Magalu... poderia baixar o preco de algum dos meus 12 produtos naquela loja?"
O radar anterior so alertava quando o PRODUTO aparecia na publicacao; cupom de loja era registrado e esquecido.

Calibrado com os cupons REAIS de 21/11/2026 (137 distintos nas 4 grandes lojas). O que se viu:
- cartoes genericos do Promobit ("Amazon: 20% de Desconto em produtos Amazon") vem SEM nenhuma regra;
- KaBuM: "itens selecionados", "processadores", "notebooks", "jogos";  Amazon: primeira compra no app, iPhone, jogos, bebidas;
- so um e irrestrito de verdade (BLACK150: R$ 150 em compras acima de R$ 1.499).
Por isso a regra e ESTRITA. Resultados:
  CANDIDATO      tem CODIGO, valor conhecido, nenhuma restricao/limitador de escopo no texto, minimo atingido => vale TESTAR no carrinho
  INDETERMINADO  falta regra (sem codigo/instrucao), escopo "selecionado"/desconhecido, ou so o teto da campanha ("ate X")
  INAPLICAVEL    restricao conhecida impeditiva (primeira compra, app, Pix, vendedor, categoria, minimo, expirado)
NUNCA e confirmacao de funcionamento: todo valor e estimativa, o status do cupom e preservado.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

from . import caminhos, catalogo, cupons, historico
from .catalogo import normalizar
from .modelos import Oferta

CANDIDATO, INDETERMINADO, INAPLICAVEL = "CANDIDATO", "INDETERMINADO", "INAPLICAVEL"

ALIAS_LOJA = {
    "amazon": "amazon", "amazoncombr": "amazon", "kabum": "kabum", "magalu": "magalu", "magazineluiza": "magalu",
    "mercadolivre": "mercadolivre", "leroy": "leroy", "leroymerlin": "leroy", "dufrio": "dufrio",
    "webcontinental": "webcontinental", "frigelar": "frigelar", "shopee": "shopee", "casasbahia": "casasbahia",
    "americanas": "americanas",
}
# chave do bloco no estado do rastreador -> loja
BLOCOS_LOJA = {"amazon": "amazon", "amazon_127v": "amazon", "kabum": "kabum", "kabum_preto": "kabum", "kabum_branco": "kabum",
               "dufrio": "dufrio", "webcontinental": "webcontinental", "frigelar": "frigelar", "ml_18x": "mercadolivre", "leroy": "leroy"}
CAMPOS_PRECO = ("total", "preco", "preco_pix", "menor_preco", "preco_avista")

# Categoria explicitamente COMPATIVEL com o produto (palavra inteira; "eletronicos"/"tecnologia" sao ambiguos e ficam de fora)
COMPATIVEL = {
    "robo_aspirador": re.compile(r"\b(eletrodomestic\w+|eletroportatei\w+|robos?|aspiradores?|casa inteligente|smart home)\b"),
    "ar_condicionado": re.compile(r"\b(eletrodomestic\w+|ar[- ]condicionado\w*|climatizacao|refrigeracao)\b"),
    "chuveiro": re.compile(r"\b(construcao|ferramentas?|banheiro|chuveiros?|material de construcao)\b"),
}
# Categoria/produto explicitamente OUTRO (vence a compativel: "eletronicos ... Iphone 18" e iPhone)
INCOMPATIVEL = re.compile(
    r"\b(livros?|celulares?|smartphones?|iphones?|moda|roupas?|calcados?|tenis|beleza|perfum\w*|farmacia|supermercado|pets?|games?|"
    r"jogos?|consoles?|playstation|xbox|kindle|alexa|fire tv|assinatura|ifood|delivery|viagens?|processadores?|placas? de video|"
    r"notebooks?|volantes?|fontes?|bebidas?|vinho|whisky|licor|gta|cerveja|cafe|hardware|perifericos?|monitores?|memorias?|"
    r"ssd|cadeiras? gamer|televisor\w*|tvs?|smart ?tvs?)\b"
)
ESCOPO_AMPLO = re.compile(r"\b(toda a loja|todo o site|todo site|site todo|todos os produtos|todas as categorias|em tudo|qualquer produto)\b")
# Estrutura "desconto em <algo>" onde <algo> nao e "compras/tudo/todos os produtos": delimita um subconjunto (bikes, volantes...)
LIMITADOR = re.compile(
    r"\b(?:desconto|off)\s+(?:de\s+\d+%?\s+)?(?:em|nas?|nos?|para)\s+(?!compras\b|todo\b|toda\b|todos\b|todas\b|tudo\b|produtos?\s+(?:da|do)\b|"
    r"pedidos?\b|seu\b|sua\b|seus\b|suas\b|cima\b|acima\b|a partir\b)(\w{4,})"
)
SELETIVO = re.compile(r"\b(selecionad\w+|selecao|veja se|confira|teste o cupom|aplicavel aos seus itens|elegiv\w+|participantes?|alguns|nem todos)\b")
INSTRUCAO = re.compile(r"\b(aplique|aplicar|use o cupom|insira|digite|cole o codigo)\b")
# O proprio CODIGO as vezes denuncia a categoria (TV200, NOTE15OFF, GAMER10...): sugere, nao prova => INDETERMINADO.
CODIGO_SUGESTIVO = re.compile(r"(?:^|[^A-Z])(TV|NOTE|NOTEBOOK|GAME|GAMER|GTA|PLACA|FONTE|CPU|SSD|MONITOR|CELL|IPHONE|LIVRO|IMPRESSORAS?|TECLADO|MOUSE|CADEIRA|TABLET|CELULAR|SMARTPHONE|GELADEIRA|FOGAO|LAVADORA|CAMERA|BIKE|BICICLETA|PERFUME|BELEZA|BRINQUEDO|HEADSET|FONE|PS5|XBOX|CONSOLE|COMPUTADOR)(?:\d|[A-Z]|$)")
# HEURISTICA (nao dado): cupom de loja inteira com percentual muito alto e sem teto/regra costuma ser limitado a categoria,
# vendedor ou primeira compra. Acima disto o cupom so vira candidato se o texto trouxer um TETO.
PERCENTUAL_SUSPEITO = 20.0


def loja_norm(nome: str | None) -> str:
    n = re.sub(r"[^a-z0-9]", "", normalizar(nome or ""))
    return ALIAS_LOJA.get(n, n)


# ------------------------------------------------------------------ precos atuais por produto e loja

def _melhor_campo(d: dict[str, Any]) -> float | None:
    for k in CAMPOS_PRECO:
        v = d.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    return None


def precos_por_loja(estado: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """{produto: [{loja, preco, vendedor, frete_incluso}]} a partir de um estado.json (ultima coleta boa)."""
    saida: dict[str, list[dict[str, Any]]] = {}
    for pid, mod in (estado.get("modelos") or {}).items():
        itens: list[dict[str, Any]] = []
        for bloco, loja in BLOCOS_LOJA.items():
            d = mod.get(bloco)
            if isinstance(d, dict):
                p = _melhor_campo(d)
                if p:
                    itens.append({"loja": loja, "preco": p, "vendedor": d.get("vendedor"), "frete_incluso": d.get("total") is not None})
        z = mod.get("zoom")
        if isinstance(z, dict) and isinstance(z.get("menor_preco"), (int, float)) and z.get("loja"):
            itens.append({"loja": loja_norm(z["loja"]), "preco": float(z["menor_preco"]), "vendedor": z["loja"], "frete_incluso": False})
        if itens:
            saida[pid] = itens
    return saida


def carregar_precos_atuais(base: Path | None = None) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    """Le a ultima coleta BOA (com correcoes) de cada rastreador. Retorna (precos, data_da_coleta_por_produto)."""
    precos: dict[str, list[dict[str, Any]]] = {}
    datas: dict[str, str] = {}
    for nome in ("rastreador-robos", "rastreador-ares", "rastreador-chuveiro"):
        arq = (base / nome / "historico.jsonl") if base else (caminhos.tracker_dir(nome) / "historico.jsonl")
        bom = historico.ultimo_estado_bom(historico.carregar_jsonl(arq, nome))
        if not bom:
            continue
        for pid, itens in precos_por_loja(bom).items():
            precos[pid] = itens
            datas[pid] = bom.get("coletado_em", "")
    return precos, datas


# ------------------------------------------------------------------ cruzamento

def _escopo(texto_n: str, categoria: str) -> tuple[str, str]:
    """('incompativel'|'compativel'|'amplo'|'seletivo'|'irrestrito'|'curto', motivo)."""
    m = INCOMPATIVEL.search(texto_n)
    if m:
        return "incompativel", f"o texto limita a outra categoria/produto ('{m.group(0)}')"
    pat = COMPATIVEL.get(categoria)
    if pat and pat.search(texto_n):
        return "compativel", "o texto cita categoria compativel com o produto"
    if ESCOPO_AMPLO.search(texto_n):
        return "amplo", "escopo declarado amplo no texto"
    if SELETIVO.search(texto_n):
        return "seletivo", "o texto diz 'selecionados'/'veja se e elegivel': depende do produto"
    lim = LIMITADOR.search(texto_n)
    if lim:
        alvo = lim.group(1)
        return "seletivo", ("o texto diz so 'em produtos da loja', sem dizer quais" if alvo.startswith("produto")
                            else f"o texto restringe o desconto a '{alvo}'")
    if len(texto_n) < 45:
        return "curto", "publicacao sem regra (so titulo generico)"
    return "irrestrito", "o texto nao cita limite de categoria nem selecao"


ESTAGIOS = ("descoberto", "potencialmente_elegivel", "validado", "expirado")


def estagio(r: dict[str, Any], cupom: cupons.Cupom) -> str:
    """Quatro estagios, sempre separados: DESCOBERTO (existe na fonte; ainda nao se sabe se serve), POTENCIALMENTE ELEGIVEL (regra completa e sem
    restricao conhecida: vale testar; economia so ESTIMADA), VALIDADO (alguem conferiu no carrinho: so via `radar validar`) e EXPIRADO."""
    if cupom.status == cupons.EXPIRADO or "expirado" in r["motivo"] or "validade vencida" in r["motivo"]:
        return "expirado"
    if r["aplicabilidade"] == CANDIDATO:
        return "validado" if cupom.status == cupons.VALIDADO else "potencialmente_elegivel"
    return "descoberto"


def avaliar_par(*args: Any, **kw: Any) -> dict[str, Any]:
    cupom = args[1] if len(args) > 1 else kw["cupom"]
    r = _avaliar_par(*args, **kw)
    r["estagio"] = estagio(r, cupom)
    return r


def _avaliar_par(
    oferta: Oferta, cupom: cupons.Cupom, produto_id: str, produto: dict[str, Any], preco_loja: dict[str, Any],
    melhor_atual: float, perfil: dict[str, bool] | None = None, agora: dt.datetime | None = None,
) -> dict[str, Any]:
    agora = agora or dt.datetime.now()
    texto_n = normalizar(f"{oferta.titulo} {oferta.texto}")
    preco = float(preco_loja["preco"])
    r: dict[str, Any] = {
        "cupom": cupom.codigo or "(sem codigo)", "cupom_loja": oferta.loja, "fonte": oferta.fonte, "titulo": oferta.titulo[:90],
        "produto": produto_id, "loja": preco_loja["loja"], "preco_atual_na_loja": preco, "melhor_preco_atual": melhor_atual,
        "status_cupom": cupom.status, "restricoes": list(cupom.restricoes), "aplicabilidade": INDETERMINADO, "motivo": "",
        "preco_com_cupom_estimado": None, "economia_estimada": None, "teto_da_campanha": None, "melhor_que_atual": False,
        "url": oferta.url, "confirmado": False, "regra_do_desconto": f"{cupom.tipo} {cupom.valor} min {cupom.minimo} teto {cupom.teto}",
    }
    if cupom.status == cupons.EXPIRADO:
        r.update(aplicabilidade=INAPLICAVEL, motivo="cupom expirado")
        return r
    if cupom.validade and cupom.validade < agora.strftime("%Y-%m-%d %H:%M"):
        r.update(aplicabilidade=INAPLICAVEL, motivo=f"validade vencida em {cupom.validade}")
        return r
    eleg, porque = cupons.elegibilidade(cupom, perfil)
    if eleg is False:
        r.update(aplicabilidade=INAPLICAVEL, motivo=porque)
        return r
    escopo, escopo_motivo = _escopo(texto_n, produto.get("categoria", ""))
    if escopo == "incompativel":
        r.update(aplicabilidade=INAPLICAVEL, motivo=escopo_motivo)
        return r
    vend = preco_loja.get("vendedor")
    if "vendedor_especifico" in cupom.restricoes and loja_norm(vend) not in (preco_loja["loja"], ""):
        r.update(aplicabilidade=INAPLICAVEL,
                 motivo=f"cupom vale para vendido/entregue pela loja; o preco monitorado e do vendedor '{vend}'")
        return r
    if cupom.minimo and preco < cupom.minimo:
        r.update(aplicabilidade=INAPLICAVEL, motivo=f"compra minima R$ {cupom.minimo:.2f} nao atingida (preco R$ {preco:.2f})")
        return r
    if cupom.valor_maximo:
        teto = cupom.teto or (preco * cupom.valor / 100.0 if cupom.tipo == "percentual" and cupom.valor else None)
        r.update(aplicabilidade=INDETERMINADO, teto_da_campanha=round(teto, 2) if teto else None,
                 motivo="o texto diz 'ate X': so o TETO da campanha e conhecido; o desconto real depende do produto")
        return r
    desconto = None
    if cupom.tipo == "percentual" and cupom.valor and not cupom.valor_inferido:
        desconto = preco * cupom.valor / 100.0
        if cupom.teto:
            desconto = min(desconto, cupom.teto)
    elif cupom.tipo == "fixo" and cupom.valor and not cupom.valor_inferido:
        desconto = min(cupom.valor, preco)
    if desconto is None:
        r.update(motivo="valor do desconto nao identificado com seguranca")
        return r
    final = round(preco - desconto, 2)
    r.update(preco_com_cupom_estimado=final, economia_estimada=round(desconto, 2), melhor_que_atual=final < melhor_atual - 0.5)
    tem_regra = bool(cupom.codigo)
    sugestivo = CODIGO_SUGESTIVO.search((cupom.codigo or "").upper())
    pct_alto = cupom.tipo == "percentual" and (cupom.valor or 0) >= PERCENTUAL_SUSPEITO and not cupom.teto
    if sugestivo and escopo != "compativel":
        r.update(aplicabilidade=INDETERMINADO, motivo=f"o codigo '{cupom.codigo}' sugere outra categoria ('{sugestivo.group(1)}'); o texto nao esclarece")
    elif pct_alto and escopo != "compativel":
        r.update(aplicabilidade=INDETERMINADO,
                 motivo=f"{cupom.valor:.0f}% sem teto nem regra: cupom de loja inteira acima de {PERCENTUAL_SUSPEITO:.0f}% costuma ser limitado "
                        "(categoria, vendedor ou primeira compra) [heuristica]")
    elif escopo in ("compativel", "amplo", "irrestrito") and tem_regra and eleg is True:
        aviso_teto = "; percentual sem teto informado: a economia e um LIMITE SUPERIOR" if cupom.tipo == "percentual" and not cupom.teto else ""
        r.update(aplicabilidade=CANDIDATO, motivo=f"{escopo_motivo}; sem restricao conhecida; vale TESTAR no carrinho (nada confirmado){aviso_teto}")
    else:
        falta = []
        if not tem_regra:
            falta.append("sem codigo do cupom")
        if escopo in ("seletivo", "curto"):
            falta.append(escopo_motivo)
        if eleg is None:
            falta.append(porque)
        r.update(aplicabilidade=INDETERMINADO, motivo="; ".join(falta) or "regra incompleta")
    return r


def cruzar(
    ofertas: list[Oferta], precos: dict[str, list[dict[str, Any]]], cat: dict[str, Any] | None = None,
    perfil: dict[str, bool] | None = None, agora: dt.datetime | None = None,
) -> list[dict[str, Any]]:
    """Cruza cada cupom de loja (oferta sem produto) com cada produto que tem preco naquela loja. Sem duplicatas."""
    cat = cat or catalogo.carregar()
    agora = agora or dt.datetime.now()
    saida: list[dict[str, Any]] = []
    vistos: set[tuple] = set()
    for of in ofertas:
        eh_cupom = (of.extras or {}).get("tipo") == "cupom_loja" or (of.canal or "").startswith("cupom_loja")
        loja = loja_norm(of.loja)
        if not eh_cupom or not loja:
            continue
        chave_cupom = (loja, re.sub(r"\s+", " ", of.titulo).strip().lower(), (of.cupom_codigo or "").upper(), re.sub(r"\s+", " ", of.texto)[:120])
        if chave_cupom in vistos:
            continue  # o mesmo cupom aparece na home, na pagina da loja e em outra fonte
        vistos.add(chave_cupom)
        texto = f"{of.titulo}. {of.texto}"
        cupom = cupons.interpretar_regra(texto, loja=of.loja, codigo=of.cupom_codigo, agora=agora)
        cupons.avaliar_status(cupom, texto, of.publicado_em, of.verificado_em, agora)
        for pid, pcat in (cat.get("produtos") or {}).items():
            if pcat.get("moeda") not in (None, "BRL"):
                continue
            na_loja = [p for p in precos.get(pid, []) if p["loja"] == loja]
            if not na_loja:
                continue
            melhor_atual = min(p["preco"] for p in precos.get(pid, []))
            for pl in na_loja:
                par = (chave_cupom, pid, pl["loja"], pl["preco"])
                if par in vistos:
                    continue  # K800 preto e branco (mesmo preco) geram o mesmo par
                vistos.add(par)
                saida.append(avaliar_par(of, cupom, pid, pcat, pl, melhor_atual, perfil, agora))
    return saida


def resumo(res: list[dict[str, Any]]) -> dict[str, Any]:
    cont = {CANDIDATO: 0, INDETERMINADO: 0, INAPLICAVEL: 0}
    motivos: dict[str, int] = {}
    indet: dict[str, int] = {}
    for r in res:
        cont[r["aplicabilidade"]] += 1
        chave = re.sub(r"R\$ [\d.]+", "R$ X", r["motivo"]).split(" (")[0][:70]
        if r["aplicabilidade"] == INAPLICAVEL:
            motivos[chave] = motivos.get(chave, 0) + 1
        elif r["aplicabilidade"] == INDETERMINADO:
            indet[chave] = indet.get(chave, 0) + 1
    por_estagio = {e: sum(1 for r in res if r.get("estagio") == e) for e in ESTAGIOS}
    return {"pares_cupom_produto": len(res), **cont, "estagios": por_estagio, "motivos_inaplicavel": motivos, "motivos_indeterminado": indet,
            "candidatos": [r for r in res if r["aplicabilidade"] == CANDIDATO],
            "oportunidades": [r for r in res if r["aplicabilidade"] == CANDIDATO and r["melhor_que_atual"]]}
