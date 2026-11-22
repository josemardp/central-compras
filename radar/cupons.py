"""Motor de interpretacao de cupons e condicoes promocionais em texto livre.

Deterministico (regex), sem IA. Regras de seguranca:
- nao inventa valor: `70OFF` sozinho NAO vira "R$ 70" (so sinaliza `valor_inferido`);
- restricao desconhecida ou nao atendida pelo perfil do comprador => nao aplica o desconto;
- publicacao nao prova funcionamento: o status parte de NAO_CONFIRMADO;
- VALIDADO so existe por confirmacao explicita (carrinho/manual), nunca por inferencia.

Estados: VALIDADO, PROVAVEL, NAO_CONFIRMADO, EXPIRADO.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Any

from .catalogo import normalizar

VALIDADO, PROVAVEL, NAO_CONFIRMADO, EXPIRADO = "VALIDADO", "PROVAVEL", "NAO_CONFIRMADO", "EXPIRADO"

PALAVRAS_NAO_CODIGO = {
    "AMAZON", "KABUM", "MAGALU", "MAGAZINE", "PIX", "OFF", "FRETE", "APP", "CUPOM", "CUPONS", "BLACK", "FRIDAY",
    "NOVO", "NOVA", "HOJE", "LINK", "ONLINE", "VER", "USE", "COM", "SEM", "LOJA", "PRIME", "MELIUZ", "PROMO",
    "GRATIS", "ATIVO", "ATIVA", "REGRAS", "DESCONTO", "VALIDO", "COMPRA", "PRODUTO", "PRODUTOS", "CASHBACK",
    "ELETRO", "ELETRONICOS", "CARTAO", "CREDITO", "BRASIL", "CELULAR", "NOTEBOOK", "TELEFONE", "PEDIDO",
}
# Textos que paginas de cupom usam no lugar de um codigo ("ative no link", "resgate aqui"...).
PLACEHOLDER = re.compile(
    r"(NOLINK|AQUI|EGANHE|AUTOMATICO|JAATIVO|ATIVEAPROMO|APPCOMPRA|DESCONTAOAPP|RESGATE|CLIQUE|APROVEITE)"
)

_RE_PALAVRA_CHAVE = re.compile(
    r"(?:cupom|cupon|c[oó]digo|codigo|code|voucher|use|aplique|digite|insira)\s*(?:o|do|de|:|-|=)?\s*[:\-]?\s*[\"'`´“*_(\[]*"
    r"([A-Za-z0-9]{4,20})",
    re.I,
)
_RE_TOKEN_MAIUSCULO = re.compile(r"(?<![A-Za-z0-9])([A-Z0-9]{4,20})(?![A-Za-z0-9])")
_RE_BACKTICK = re.compile(r"[`´“\"']([A-Za-z0-9]{4,20})[`´”\"']")

_RE_REAL = r"r\$\s*([\d]{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)"

SINAIS_EXPIRADO = re.compile(
    r"expirou|expirad[oa]|encerrou|encerrad[oa]|acabou|esgotou|esgotad[oa]|nao funciona|nao funcionou|nao aplic|"
    r"nao consegui|nao pega|nao esta funcionando|invalid[oa]|saiu do ar|fora do ar|ja era|cupom caiu|nao vale"
)
SINAIS_FUNCIONA = re.compile(
    r"funcionando|funcionou|funciona(?! nao)|consegui|aplicou|aplicado|testei|testado|deu certo|pegou|valendo|"
    r"ainda vale|confirmado|ativo"
)


@dataclass
class Cupom:
    codigo: str | None
    loja: str | None = None
    tipo: str = "desconhecido"  # percentual | fixo | frete | cashback | desconhecido
    valor: float | None = None
    valor_inferido: bool = False
    minimo: float | None = None
    teto: float | None = None
    restricoes: list[str] = field(default_factory=list)
    acumulavel: bool | None = None
    validade: str | None = None
    cashback_pct: float | None = None
    frete_gratis: bool = False
    valor_maximo: bool = False  # "ate 50%" / "ate R$ 1.000": o numero e TETO da campanha, nao o desconto que voce vai ter
    status: str = NAO_CONFIRMADO
    confianca: float = 0.3
    evidencias: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- numeros

def _brl(txt: str) -> float | None:
    txt = txt.strip().replace(".", "").replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return None


def _valores_monetarios(janela: str) -> list[tuple[float, str, str]]:
    """Cada R$ da janela com o contexto antes/depois (para classificar: desconto, minimo, teto)."""
    out: list[tuple[float, str, str]] = []
    for m in re.finditer(_RE_REAL, janela, re.I):
        v = _brl(m.group(1))
        if v is None:
            continue
        antes = janela[max(0, m.start() - 28): m.start()].lower()
        depois = janela[m.end(): m.end() + 28].lower()
        out.append((v, antes, depois))
    return out


# ---------------------------------------------------------------- codigos

_RE_UNIDADE = re.compile(r"^\d{1,6}(V|W|K|X|GB|TB|MB|MM|CM|KG|G|L|ML|HZ|PA|MAH|BTU|BTUS|POL|PCS|UN|UND)$")
_RE_MODELO = re.compile(r"^[A-Z]{1,3}\d{2,4}[A-Z]{0,2}$")  # K800, F10, S40C, RV20, X10
_SKUS_CACHE: set[str] | None = None


def _skus_do_catalogo() -> set[str]:
    """Codigos de fabricante do catalogo (nunca sao cupom)."""
    global _SKUS_CACHE
    if _SKUS_CACHE is None:
        try:
            from . import catalogo

            _SKUS_CACHE = {
                re.sub(r"[^A-Z0-9]", "", s.upper())
                for p in catalogo.carregar().get("produtos", {}).values()
                for s in (p.get("skus") or []) + [p.get("sku_a_confirmar") or ""]
                if s
            }
        except Exception:  # noqa: BLE001 - catalogo ausente nao pode quebrar a leitura de cupons
            _SKUS_CACHE = set()
    return _SKUS_CACHE


def _eh_codigo_valido(token: str, depois_de_palavra_chave: bool) -> bool:
    t = token.upper()
    if t in PALAVRAS_NAO_CODIGO or PLACEHOLDER.search(t):
        return False
    if t.isdigit() or _RE_UNIDADE.match(t) or t in _skus_do_catalogo():
        return False
    if not depois_de_palavra_chave and _RE_MODELO.match(t):
        return False  # K800, F10, RV20: modelo de produto, nao cupom (so vale se vier logo apos "cupom"/"codigo")
    tem_letra, tem_digito = any(c.isalpha() for c in t), any(c.isdigit() for c in t)
    if tem_letra and tem_digito:
        return True
    # so letras (BLACKFRIDAY): aceita apenas se veio logo depois de "cupom/codigo/use" e esta escrito em maiusculas
    return depois_de_palavra_chave and token.isupper() and len(t) >= 5


def _candidatos_codigo(texto: str) -> list[tuple[str, int]]:
    vistos: dict[str, int] = {}
    for m in _RE_PALAVRA_CHAVE.finditer(texto):
        tok = m.group(1)
        # minusculas so valem se tiverem digito (evita "cupom funcionando" virar codigo)
        if tok.islower() and not any(c.isdigit() for c in tok):
            continue
        if _eh_codigo_valido(tok, True):
            vistos.setdefault(tok.upper(), m.start(1))
    for m in _RE_BACKTICK.finditer(texto):
        if _eh_codigo_valido(m.group(1), False):
            vistos.setdefault(m.group(1).upper(), m.start(1))
    for m in _RE_TOKEN_MAIUSCULO.finditer(texto):
        if _eh_codigo_valido(m.group(1), False):
            vistos.setdefault(m.group(1).upper(), m.start(1))
    return sorted(vistos.items(), key=lambda kv: kv[1])


# ---------------------------------------------------------------- condicoes

def extrair_condicoes(texto: str) -> dict[str, Any]:
    """Condicoes gerais do texto (restricoes, frete gratis, cashback, acumulacao)."""
    t = normalizar(texto)
    restr: list[str] = []
    if re.search(r"primeira compra|1a compra|primeiro pedido|novos? (clientes|usuarios)|1o pedido|cliente novo|primeira20|\bprimeir[oa]\b.{0,12}\bcompra", t):
        restr.append("primeira_compra")
    if re.search(r"(somente|apenas|so|exclusiv[oa]|valido|vale)\s+(no|pelo|via|para|em)?\s*(o\s+)?(app|aplicativo)|\b(no|pelo|via)\s+(o\s+)?(app|aplicativo)\b|\bapp\b\s+(da|do)\s+\w+", t):
        restr.append("app")
    if re.search(r"\b(no|via|pagando com|pagamento (no|via|com)|a vista no|a vista \()\s*pix\b|\bpix\b", t):
        restr.append("pix")
    if re.search(r"selecionad[oa]s?|alguns usuarios|nem todos|por convite|contas? elegiv", t):
        restr.append("selecionados")
    if re.search(r"vendid[oa]s?\s+(e entregues?\s+)?(por|pela|pelo)|vendedores? (selecionados|participantes)|apenas (a|o) (amazon|kabum|magalu|loja)", t):
        restr.append("vendedor_especifico")
    if re.search(r"categorias? selecionad|produtos? selecionad|itens? selecionad|em produtos? (da|do) |algumas categorias", t):
        restr.append("categoria_limitada")
    acum: bool | None = None
    if re.search(r"nao (e |eh )?cumulativ|nao acumula|nao pode ser (somado|acumulado)", t):
        acum = False
    elif re.search(r"cumulativ|acumula|somado com|soma com", t):
        acum = True
    cb = re.search(r"(\d{1,2}(?:[.,]\d)?)\s*%\s*(?:de\s*)?(?:cashback|de volta)|cashback\s*(?:de\s*)?(\d{1,2}(?:[.,]\d)?)\s*%", t)
    cashback = float((cb.group(1) or cb.group(2)).replace(",", ".")) if cb else None
    return {
        "restricoes": restr,
        "acumulavel": acum,
        "frete_gratis": bool(re.search(r"frete\s+gr[aá]tis|frete\s+gratis|sem frete", t)),
        "cashback_pct": cashback,
        "tem_sinal_expirado": bool(SINAIS_EXPIRADO.search(t)),
        "tem_sinal_funciona": bool(SINAIS_FUNCIONA.search(t)) and not SINAIS_EXPIRADO.search(t),
    }


def extrair_validade(texto: str, agora: dt.datetime | None = None) -> str | None:
    """'valido ate 27/11 as 23h' -> '2026-11-27 23:00'. Sem hora: fim do dia."""
    agora = agora or dt.datetime.now()
    t = normalizar(texto)
    m = re.search(
        r"(?:valid[oa]|ate|expira|vence|encerra|termina)\s*(?:ate|em|dia|o dia)?\s*(?:o dia\s*)?(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?"
        r"(?:\s*(?:as|a|ate)?\s*(\d{1,2})\s*(?:h|:)\s*(\d{2})?)?",
        t,
    )
    if not m:
        return None
    dia, mes = int(m.group(1)), int(m.group(2))
    ano = int(m.group(3)) if m.group(3) else agora.year
    ano = ano + 2000 if ano < 100 else ano
    hora = int(m.group(4)) if m.group(4) else 23
    minuto = int(m.group(5)) if m.group(5) else (59 if m.group(4) is None else 0)
    try:
        return dt.datetime(ano, mes, dia, hora, minuto).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return None


# ---------------------------------------------------------------- extracao

def _interpretar_janela(c: Cupom, janela: str, agora: dt.datetime | None) -> None:
    jn = normalizar(janela)
    # percentual
    m = re.search(r"(\d{1,2}(?:,\d)?)\s*%\s*(?:de\s*)?(?:desconto|off)|(?:desconto|off)\s*(?:de\s*)?(\d{1,2}(?:,\d)?)\s*%", jn)
    if m:
        c.tipo, c.valor = "percentual", float((m.group(1) or m.group(2)).replace(",", "."))
        if re.search(r"\bate\s*(?:de\s*)?$", jn[max(0, m.start() - 12): m.start()]):
            c.valor_maximo = True
    for v, antes, depois in _valores_monetarios(janela):
        antes_n, depois_n = normalizar(antes), normalizar(depois)
        if re.search(r"(acima de|a partir de|minim[oa]( de)?|compras? de|pedidos? de|acima)\s*$", antes_n) or depois_n.startswith("+"):
            c.minimo = c.minimo or v
        elif re.search(r"(ate|limitado a|maximo de|teto de|no maximo)\s*$", antes_n):
            c.teto = c.teto or v
            if c.valor is None and re.search(r"(ate)\s*$", antes_n):
                c.valor_maximo = True
            if re.match(r"\s*(de\s*)?(desconto|off)", depois_n) and c.tipo == "desconhecido":
                c.tipo = "fixo"  # "ate R$ X off": o teto e conhecido, o valor exato nao
        elif re.match(r"\s*(de\s*)?(desconto|off|de abatimento|abatimento|de volta)", depois_n) or re.search(
            r"(desconto de|off de|abatimento de|economize|ganhe)\s*$", antes_n
        ):
            if c.valor is None:
                c.tipo, c.valor = "fixo", v
    cond = extrair_condicoes(janela)
    c.restricoes = cond["restricoes"]
    c.acumulavel = cond["acumulavel"]
    c.frete_gratis = cond["frete_gratis"]
    c.cashback_pct = cond["cashback_pct"]
    c.validade = extrair_validade(janela, agora)
    if c.tipo == "desconhecido" and c.cashback_pct:
        c.tipo = "cashback"
    if c.tipo == "desconhecido" and c.frete_gratis:
        c.tipo = "frete"
    if c.valor is None and c.tipo == "desconhecido":
        # O proprio codigo as vezes carrega o numero (70OFF, 10OFFBF). E so pista: nunca entra em calculo.
        cod = re.match(r"^(\d{1,3})OFF", c.codigo or "") or re.search(r"(?:^|[A-Z])(\d{1,3})(?:OFF)?$", c.codigo or "")
        if cod:
            c.valor, c.valor_inferido = float(cod.group(1)), True
            c.evidencias.append("valor sugerido pelo proprio codigo (nao confirmado)")


def interpretar_regra(texto: str, loja: str | None = None, codigo: str | None = None, agora: dt.datetime | None = None) -> Cupom:
    """Interpreta a REGRA de desconto de um texto mesmo sem codigo (ex.: 'KaBuM!: R$ 300 de Desconto em produtos KaBuM!')."""
    c = Cupom(codigo=(codigo or "").upper() or None, loja=loja)
    _interpretar_janela(c, texto, agora)
    return c


def extrair_cupons(texto: str, loja: str | None = None, agora: dt.datetime | None = None) -> list[Cupom]:
    """Todos os cupons com codigo encontrados no texto, cada um interpretado na sua janela de contexto."""
    cupons: list[Cupom] = []
    for codigo, pos in _candidatos_codigo(texto):
        i = texto.upper().find(codigo, max(0, pos - 2))
        i = pos if i < 0 else i
        janela = texto[max(0, i - 150): i + len(codigo) + 220]
        c = Cupom(codigo=codigo, loja=loja)
        _interpretar_janela(c, janela, agora)
        cupons.append(c)
    return cupons


# ---------------------------------------------------------------- estado

def avaliar_status(
    cupom: Cupom,
    texto_e_comentarios: str = "",
    publicado_em: str | None = None,
    verificado_em: str | None = None,
    agora: dt.datetime | None = None,
    janela_horas: float = 6.0,
) -> Cupom:
    """Define status e confianca. Nunca devolve VALIDADO: isso exige `marcar_validado`."""
    agora = agora or dt.datetime.now()
    t = normalizar(texto_e_comentarios)
    negativos = len(SINAIS_EXPIRADO.findall(t))
    positivos = len(SINAIS_FUNCIONA.findall(t))

    def _dt(v: str | None) -> dt.datetime | None:
        try:
            return dt.datetime.strptime(v[:16], "%Y-%m-%d %H:%M") if v else None
        except ValueError:
            return None

    validade = _dt(cupom.validade)
    ref = _dt(verificado_em) or _dt(publicado_em)
    recente = ref is not None and (agora - ref).total_seconds() <= janela_horas * 3600
    confianca = 0.3

    if validade and validade < agora:
        cupom.status, cupom.confianca = EXPIRADO, 0.95
        cupom.evidencias.append(f"validade vencida em {cupom.validade}")
        return cupom
    if negativos and negativos >= positivos:
        cupom.status, cupom.confianca = EXPIRADO, min(0.9, 0.5 + 0.1 * negativos)
        cupom.evidencias.append(f"{negativos} sinal(is) de que parou de funcionar nos comentarios")
        return cupom
    if recente and (positivos or _dt(verificado_em)):
        cupom.status = PROVAVEL
        confianca = 0.55 + (0.1 if positivos else 0) + (0.1 if _dt(verificado_em) else 0) + 0.05 * min(positivos, 3)
        cupom.evidencias.append("evidencia recente de funcionamento" + (" (verificado pela fonte)" if _dt(verificado_em) else ""))
    else:
        cupom.status = NAO_CONFIRMADO
        if negativos and positivos > negativos:
            cupom.evidencias.append("comentarios divergem (alguns dizem que parou)")
    cupom.confianca = round(max(0.0, min(1.0, confianca)), 2)
    return cupom


def marcar_validado(cupom: Cupom, por: str, agora: dt.datetime | None = None) -> Cupom:
    cupom.status, cupom.confianca = VALIDADO, 0.98
    cupom.evidencias.append(f"validado por {por} em {(agora or dt.datetime.now()):%d/%m %H:%M}")
    return cupom


# ---------------------------------------------------------------- preco final

PERFIL_PADRAO = {"primeira_compra": False, "usa_app": False, "paga_no_pix": True}


def elegibilidade(cupom: Cupom, perfil: dict[str, bool] | None = None) -> tuple[bool | None, str]:
    """True/False quando da para decidir; None quando falta informacao (nao inventa)."""
    perfil = perfil or PERFIL_PADRAO
    # Restricao IMPEDITIVA conhecida vence a incerteza: "primeira compra via app para clientes selecionados" e inelegivel
    # para quem nao e primeira compra, mesmo que o resto dependa de selecao (bug da fase 1, achado com cupom real em 21/11/2026).
    if "primeira_compra" in cupom.restricoes and not perfil.get("primeira_compra"):
        return False, "exige primeira compra"
    if "app" in cupom.restricoes and not perfil.get("usa_app"):
        return False, "exige compra pelo aplicativo"
    if "pix" in cupom.restricoes and not perfil.get("paga_no_pix"):
        return False, "exige pagamento no Pix"
    if "selecionados" in cupom.restricoes or "vendedor_especifico" in cupom.restricoes or "categoria_limitada" in cupom.restricoes:
        return None, "depende de produto/vendedor/conta elegivel (nao verificavel pelo texto)"
    return True, "sem restricao conhecida impeditiva"


def calcular_preco_final(
    preco: float | None,
    frete: float | None,
    cupom: Cupom | None,
    perfil: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """preco anunciado - desconto efetivamente elegivel + frete obrigatorio. Cashback fica de fora."""
    res: dict[str, Any] = {
        "preco_anunciado": preco,
        "frete": frete,
        "frete_conhecido": frete is not None,
        "desconto_aplicado": 0.0,
        "cupom_aplicado": False,
        "elegivel": None,
        "motivo": "sem cupom",
        "estimado": True,
        "preco_final": None,
        "preco_sem_cupom": None,
        "cashback_pct": getattr(cupom, "cashback_pct", None),
    }
    if preco is None:
        res["motivo"] = "oferta sem preco"
        return res
    entrega = frete or 0.0
    res["preco_sem_cupom"] = round(preco + entrega, 2)
    res["preco_final"] = res["preco_sem_cupom"]
    if cupom is None:
        return res
    eleg, porque = elegibilidade(cupom, perfil)
    res["elegivel"], res["motivo"] = eleg, porque
    if cupom.status in (EXPIRADO, NAO_CONFIRMADO):
        res["motivo"] = f"cupom {cupom.status.lower()}: nao aplicado ({porque})"
        return res
    if eleg is not True:
        return res
    if cupom.valor is None or cupom.valor_inferido or cupom.valor_maximo or cupom.tipo not in ("percentual", "fixo", "frete"):
        res["motivo"] = ("valor do cupom e so o TETO da campanha (\"ate X\"): nao aplicado" if cupom.valor_maximo
                         else "valor do cupom nao confirmado: nao aplicado")
        return res
    if cupom.minimo and preco < cupom.minimo:
        res["motivo"] = f"compra minima de R$ {cupom.minimo:.2f} nao atingida"
        return res
    if cupom.tipo == "percentual":
        desc = preco * cupom.valor / 100.0
        if cupom.teto:
            desc = min(desc, cupom.teto)
    elif cupom.tipo == "fixo":
        desc = min(cupom.valor, preco)
    else:
        desc = 0.0
        entrega = 0.0
    res.update(
        desconto_aplicado=round(desc, 2),
        cupom_aplicado=True,
        preco_final=round(preco - desc + entrega, 2),
        estimado=cupom.status != VALIDADO,
        motivo="cupom aplicado" + ("" if cupom.status == VALIDADO else " (estimado: nao validado no carrinho)"),
    )
    return res


def melhor_cupom(
    preco: float | None, frete: float | None, cupons: list[Cupom], perfil: dict[str, bool] | None = None
) -> tuple[Cupom | None, dict[str, Any]]:
    """Escolhe UM cupom (o de menor preco final). Descontos nao sao somados: nao se presume acumulo."""
    melhor_c: Cupom | None = None
    melhor_r = calcular_preco_final(preco, frete, None, perfil)
    for c in cupons:
        r = calcular_preco_final(preco, frete, c, perfil)
        if r["cupom_aplicado"] and (melhor_r["preco_final"] is None or r["preco_final"] < melhor_r["preco_final"]):
            melhor_c, melhor_r = c, r
    if melhor_c is None and cupons:
        melhor_c = cupons[0]
        melhor_r = calcular_preco_final(preco, frete, melhor_c, perfil)
    return melhor_c, melhor_r
