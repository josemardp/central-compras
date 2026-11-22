"""Alertas urgentes: deduplicacao persistente, anti-spam, mensagem e registro.

Chave de deduplicacao: produto + loja + vendedor + cupom + preco + link normalizado. Um alerta equivalente
nas ultimas 24 h e suprimido, salvo preco significativamente menor, cupom diferente, status melhor
ou retorno de promocao que havia expirado.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import sqlite3
from typing import Any

from . import db
from .cupons import EXPIRADO, VALIDADO

TEXTO_AVISO = {
    "tensao_nao_informada": "o anúncio não informa a voltagem (o produto existe em mais de uma): confirme antes de pagar",
    "tensao_ambigua": "anúncio bivolt/127V e 220V: confirme a voltagem do seu pedido",
    "sku_nao_confirmado": "o título não traz o código do fabricante: confira o modelo",
    "nome_alternativo": "nome diferente do catálogo (sem o código do fabricante): pode ser outro modelo",
    "possivel_importado": "possível produto importado (garantia pode não ser nacional)",
    "hora_incerta": "a fonte não informa quando a oferta foi postada; não é possível dizer que é recente",
    "preco_depende_de_cupom_nao_confirmado": "o preço anunciado só vale COM o cupom, que NÃO foi confirmado no carrinho; sem ele a loja cobra mais",
}

_BLOQUEIOS_CONFIANCA = ("sku_nao_confirmado", "tensao_nao_informada", "nome_alternativo", "tensao_ambigua", "possivel_importado")


def nivel_confianca(*, validacao: str, avisos: list[str], loja: dict[str, Any] | None, relacao: str | None, cupom_proprio: str | None) -> tuple[str, list[str]]:
    """Confianca do alerta, sempre com os motivos. ALTA exige produto exato (sem aviso de modelo/voltagem) E preco conferido na loja
    (ou validado por voce no carrinho). Cupom nao confirmado, loja nao conferivel ou hora incerta limitam a MEDIA."""
    avisos = avisos or []
    bloqueios = [a for a in avisos if a in _BLOQUEIOS_CONFIANCA]
    if bloqueios:
        return "BAIXA", ["modelo ou voltagem sem confirmacao (" + ", ".join(b.replace("_", " ") for b in bloqueios) + ")"]
    if validacao == "VALIDADO":
        return "ALTA", ["preco validado por voce no carrinho"]
    motivos: list[str] = []
    nivel = "ALTA"
    if loja and loja.get("status") == "indisponivel":
        return "BAIXA", ["a loja mostra o produto INDISPONIVEL"]
    if loja and loja.get("status") == "confirmado":
        if relacao == "depende_de_cupom":
            nivel = "MEDIA"
            motivos.append(f"o preço na loja é {_brl(loja['preco_loja'])} sem cupom; o anunciado exige o cupom, não confirmado no carrinho")
        elif relacao == "loja_mais_cara":
            nivel = "MEDIA"
            motivos.append(f"a loja mostra {_brl(loja['preco_loja'])}, acima do anunciado, sem cupom que explique")
        else:
            motivos.append("preço conferido na loja")
    else:
        nivel = "MEDIA"
        motivos.append("preço não conferido na loja (sem verificação pública)")
    if cupom_proprio and relacao not in ("igual", "loja_mais_barata"):
        nivel = "MEDIA"
        if not any("cupom" in m for m in motivos):
            motivos.append(f"depende do cupom {cupom_proprio}, não confirmado no carrinho")
    if "hora_incerta" in avisos:
        nivel = "MEDIA"
        motivos.append("a fonte não informa a hora da postagem")
    return nivel, motivos

ESTADOS_ORDEM = {"EXPIRADO": 0, "NAO_CONFIRMADO": 1, "PROVAVEL": 2, "VALIDADO": 3}


def normalizar_url(url: str | None) -> str:
    if not url:
        return ""
    u = re.sub(r"^https?://(www\.)?", "", url.strip().lower())
    u = re.sub(r"[?#].*$", "", u)
    return u.rstrip("/")


def chave_familia(produto: str, loja: str | None, vendedor: str | None) -> str:
    """Identifica o 'mesmo item' (para comparar preco/cupom entre alertas)."""
    return hashlib.sha1(f"{produto}|{(loja or '').lower()}|{(vendedor or '').lower()}".encode()).hexdigest()[:16]


def chave_exata(produto: str, loja: str | None, vendedor: str | None, cupom: str | None, preco: float | None, url: str | None) -> str:
    base = f"{chave_familia(produto, loja, vendedor)}|{(cupom or '').upper()}|{round(preco or 0)}|{normalizar_url(url)}"
    return hashlib.sha1(base.encode()).hexdigest()[:20]


def _agora_str(agora: dt.datetime) -> str:
    return agora.strftime("%Y-%m-%d %H:%M:%S")


def gates(
    con: sqlite3.Connection, *, produto: str, loja: str | None, vendedor: str | None, cupom: str | None, preco: float,
    status: str, classe: str, regras: dict[str, Any], agora: dt.datetime | None = None,
) -> tuple[str, str]:
    """Portoes de ELEGIBILIDADE de um candidato (nada de orcamento/horario/homologacao: isso e do despachante).
    Retorna ('ok', motivo) ou ('suprimir', motivo): classe, expirado, status enviavel e duplicidade de 24 h."""
    agora = agora or dt.datetime.now()
    cfg = regras.get("alertas", {})
    if classe not in cfg.get("classes_enviaveis", ["CRITICA", "ALTA"]):
        return "suprimir", f"classe {classe} nao gera alerta urgente"
    if status == EXPIRADO:
        return "suprimir", "expirado"
    if status not in cfg.get("status_enviaveis", ["PROVAVEL", "VALIDADO"]):
        return "suprimir", f"status {status} nao enviavel como alerta urgente"
    fam = chave_familia(produto, loja, vendedor)
    janela = _agora_str(agora - dt.timedelta(hours=cfg.get("janela_dedup_horas", 24)))
    anteriores = con.execute(
        "SELECT preco, cupom, status_cupom FROM alertas WHERE chave LIKE ? AND enviado_em >= ? AND modo IN ('real','sombra') ORDER BY id DESC",
        (fam + "%", janela)).fetchall()
    if anteriores:
        ult = anteriores[0]
        melhora = float(cfg.get("melhora_minima_pct", 3))
        preco_menor = ult["preco"] is not None and preco <= ult["preco"] * (1 - melhora / 100)
        cupom_novo = bool(cupom) and (cupom or "").upper() != (ult["cupom"] or "").upper()
        status_melhor = ESTADOS_ORDEM.get(status, 0) > ESTADOS_ORDEM.get(ult["status_cupom"] or "NAO_CONFIRMADO", 0) and status == VALIDADO
        if not (preco_menor or cupom_novo or status_melhor):
            return "suprimir", "equivalente a alerta das ultimas 24h"
    return "ok", "elegivel"


def decidir(
    con: sqlite3.Connection,
    *,
    produto: str,
    loja: str | None,
    vendedor: str | None,
    cupom: str | None,
    preco: float,
    status: str,
    fonte: str,
    classe: str,
    regras: dict[str, Any],
    agora: dt.datetime | None = None,
) -> tuple[str, str]:
    """Retorna (acao, motivo): 'enviar' | 'sombra' | 'suprimir'. Caminho IMEDIATO (sem prioridade); o fluxo da varredura usa
    `gates` + `radar.prioridade.despachar`."""
    agora = agora or dt.datetime.now()
    cfg = regras.get("alertas", {})
    if classe not in cfg.get("classes_enviaveis", ["CRITICA", "ALTA"]):
        return "suprimir", f"classe {classe} nao gera alerta urgente"
    if status == EXPIRADO:
        return "suprimir", "expirado"

    fam = chave_familia(produto, loja, vendedor)
    janela = _agora_str(agora - dt.timedelta(hours=cfg.get("janela_dedup_horas", 24)))
    anteriores = con.execute(
        "SELECT preco, cupom, status_cupom, modo FROM alertas WHERE chave LIKE ? AND enviado_em >= ? "
        "AND modo IN ('real','sombra') ORDER BY id DESC",
        (fam + "%", janela),
    ).fetchall()
    if anteriores:
        ult = anteriores[0]
        melhora = float(cfg.get("melhora_minima_pct", 3))
        preco_menor = ult["preco"] is not None and preco <= ult["preco"] * (1 - melhora / 100)
        cupom_novo = bool(cupom) and (cupom or "").upper() != (ult["cupom"] or "").upper()
        status_melhor = ESTADOS_ORDEM.get(status, 0) > ESTADOS_ORDEM.get(ult["status_cupom"] or "NAO_CONFIRMADO", 0) and status == VALIDADO
        if not (preco_menor or cupom_novo or status_melhor):
            return "suprimir", "equivalente a alerta das ultimas 24h"

    inicio, fim = (cfg.get("horario") or {}).get("inicio", "07:00"), (cfg.get("horario") or {}).get("fim", "23:00")
    hora = agora.strftime("%H:%M")
    if not (inicio <= hora <= fim):
        return "sombra", f"fora do horario de alertas ({inicio}-{fim}): aguarda o relatorio programado"
    hoje = agora.strftime("%Y-%m-%d")
    enviados_hoje = con.execute(
        "SELECT COUNT(*) FROM alertas WHERE modo='real' AND enviado_em >= ?", (hoje + " 00:00:00",)
    ).fetchone()[0]
    if classe != "CRITICA" and enviados_hoje >= int(cfg.get("limite_diario", 6)):  # CRITICA (validada por voce) nunca e barrada pelo limite
        return "sombra", f"limite diario de {cfg.get('limite_diario', 6)} alertas atingido"
    if not cfg.get("enviar", False):
        return "sombra", "envio desligado em config/radar_regras.yaml"
    if not cfg.get("homologado_em"):
        return "sombra", "alertas nao homologados (preencha homologado_em depois de revisar `radar alertas`)"
    if status not in cfg.get("status_enviaveis", ["PROVAVEL", "VALIDADO"]):
        return "sombra", f"status {status} nao enviavel como alerta urgente"
    if fonte in (cfg.get("fontes_so_sombra") or []):
        return "sombra", f"fonte {fonte} configurada so para registro"
    return "enviar", "ok"


def registrar(
    con: sqlite3.Connection, *, oferta_id: int | None, produto: str, loja: str | None, vendedor: str | None,
    cupom: str | None, preco: float, url: str | None, classe: str, status: str, modo: str, detalhe: str,
    agora: dt.datetime | None = None,
) -> None:
    chave = chave_familia(produto, loja, vendedor) + "|" + chave_exata(produto, loja, vendedor, cupom, preco, url)
    con.execute(
        "INSERT INTO alertas (oferta_id, chave, produto, enviado_em, classe, preco, cupom, status_cupom, modo, detalhe) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (oferta_id, chave, produto, _agora_str(agora or dt.datetime.now()), classe, preco, cupom, status, modo, detalhe[:300]),
    )
    con.commit()


def _brl(v: float | None) -> str:
    return "n/d" if v is None else f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def montar_mensagem(
    *, nome_produto: str, loja: str | None, preco_anunciado: float | None, cupom: str | None,
    preco_final: float | None, estimado: bool, stats: dict[str, Any] | None, fonte: str, canal: str,
    detectado_em: str, status: str, url: str | None, classe: str, motivo: str, avisos: list[str] | None = None,
    frete_conhecido: bool = True, hora_incerta: bool = False, prioridade: str | None = None,
    niveis_preco: dict[str, Any] | None = None, confianca: tuple[str, list[str]] | None = None,
) -> str:
    stats = stats or {}
    minimo = (stats.get("historico_total") or {}).get("menor")
    economia = (preco_anunciado - preco_final) if preco_anunciado is not None and preco_final is not None else None
    if minimo is None or preco_final is None:
        comp = "sem historico validado suficiente para comparar"
    elif preco_final <= minimo:
        comp = "igual ou abaixo do menor preco validado"
    else:
        comp = f"{_brl(preco_final - minimo)} acima do menor validado"
    # "RELAMPAGO" so quando a HORA da postagem e confiavel; com hora incerta (HardMOB) nunca se afirma que e relampago.
    relampago = classe == "CRITICA" and not hora_incerta
    linhas = [
        "🚨 *RADAR CENTRAL-COMPRAS | OFERTA RELÂMPAGO*" if relampago else "🔔 *RADAR CENTRAL-COMPRAS | OFERTA EM DESTAQUE*",
        "",
        f"🛒 *{nome_produto}*",
        "",
        f"🏪 Loja: {loja or 'n/d'}",
        f"💰 Preço anunciado: {_brl(preco_anunciado)}",
    ]
    if cupom:
        linhas.append(f"🏷️ Cupom: `{cupom}`" + (" (já embutido no preço anunciado; NÃO confirmado no carrinho)" if (niveis_preco or {}).get("cupom_incluso") else ""))
    if niveis_preco is not None:
        lj = niveis_preco.get("loja") or {}
        if lj.get("status") == "confirmado":
            linhas.append(f"🏬 Confirmado na loja: {_brl(lj['preco_loja'])} sem cupom (vendedor {lj.get('vendedor') or 'n/d'}, conferido {lj.get('verificado_em', '')[-5:]})")
        else:
            linhas.append("🏬 Confirmado na loja: não (" + str(lj.get("nota") or "sem verificação pública") + ")")
        linhas.append("📦 Preço entregue (com frete): não confirmado (frete e prazo só no carrinho)")
    # "entregue" so quando o frete e conhecido; a maioria das ofertas de comunidade nao informa frete (nao se afirma o que nao foi verificado)
    rotulo_preco = "Preço final entregue" if frete_conhecido else "Preço final SEM frete (a fonte não informa o frete)"
    linhas.append(f"💵 {rotulo_preco}: {_brl(preco_final)}" + (" (estimado)" if estimado else ""))
    if economia and economia > 0.5:
        linhas.append(f"📉 Economia: {_brl(economia)}")
    linhas += [
        "",
        f"📊 Menor histórico validado: {_brl(minimo)}",
        f"🎯 Comparação: {comp}",
        f"💡 Por que: {motivo}",
        "",
        f"📍 Fonte: {fonte}{(' / ' + canal) if canal and not canal.startswith(('recentes', 'loja-', 'cupom')) else ''}",
        f"🕒 Detectado pelo radar: {detectado_em}" + (" (a fonte NÃO informa a hora da postagem: pode ser mais antiga)" if hora_incerta else ""),
    ]
    if prioridade:
        linhas.append(f"🏅 Prioridade: {prioridade}")
    if confianca:
        linhas.append(f"🔒 Confiança: {confianca[0]} ({'; '.join(confianca[1])})")
    linhas += ["", f"✅ Status: {status}"]
    if avisos:
        linhas.append("⚠️ Atenção: " + "; ".join(TEXTO_AVISO.get(a, a.replace("_", " ")) for a in avisos))
    if url:
        linhas.append(f"🔗 {url}")
    linhas += ["", "⚡ *ALERTA FORA DO HORÁRIO PROGRAMADO*", "_Confirme preço, voltagem e vendedor no carrinho antes de pagar._"]
    return "\n".join(linhas)
