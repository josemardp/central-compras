"""Catalogo canonico e identificacao de produto por texto (titulo de oferta, mensagem, comentario).

Casamento deterministico, sem IA: SKU do fabricante ou conjunto de termos
obrigatorios, com exclusoes para variantes (Pro, Plus, Lite...), tensao,
capacidade em BTU, acessorios e produto importado.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import caminhos

ARQ_CATALOGO = caminhos.CONFIG_DIR / "radar_catalogo.yaml"

_RE_127 = re.compile(r"\b(127|110)\s*v\b")
_RE_220 = re.compile(r"\b(220|230)\s*v\b")
_RE_BIVOLT = re.compile(r"bivolt|\b127\s*/\s*220\b|\b110\s*/\s*220\b")
_RE_BTU = re.compile(
    r"\b(7|9|12|18|24|30|36)\s*\.?\s*000\b|\b(7|9|12|18|24|30|36)\s*k\b|\b(7|9|12|18|24|30|36)\s*mil\s*btu"
)


def normalizar(texto: str) -> str:
    """Minusculas, sem acento, espacos colapsados."""
    base = unicodedata.normalize("NFKD", texto or "")
    base = "".join(c for c in base if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", base).strip()


def _alnum(texto: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalizar(texto))


@dataclass
class Casamento:
    produto_id: str
    nome: str
    avisos: list[str] = field(default_factory=list)


def carregar(caminho: Path | None = None) -> dict[str, Any]:
    cfg = yaml.safe_load((caminho or ARQ_CATALOGO).read_text(encoding="utf-8")) or {}
    cfg.setdefault("produtos", {})
    return cfg


def _tensoes_mencionadas(t: str) -> set[int]:
    achadas: set[int] = set()
    if _RE_BIVOLT.search(t):
        return {127, 220}
    if _RE_127.search(t):
        achadas.add(127)
    if _RE_220.search(t):
        achadas.add(220)
    return achadas


def _btus_mencionados(t: str) -> set[int]:
    valores: set[int] = set()
    for m in _RE_BTU.finditer(t):
        n = int(m.group(1) or m.group(2) or m.group(3))
        valores.add(n * 1000)
    return valores


def _eh_acessorio(t: str, cat: dict[str, Any]) -> bool:
    """`t` ja normalizado. Acessorio so quando a palavra de acessorio e o nucleo do titulo ou o texto diz 'compativel'."""
    ini, comp = cat.get("acessorio_inicio_regex"), cat.get("acessorio_compat_regex")
    return bool((ini and re.search(ini, t)) or (comp and re.search(comp, t)))


def identificar(texto: str, catalogo: dict[str, Any] | None = None) -> Casamento | None:
    """Retorna o produto canonico que o texto descreve, ou None. Primeiro casamento valido vence."""
    cat = catalogo or carregar()
    t = normalizar(texto)
    if not t:
        return None
    alnum = _alnum(texto)
    if _eh_acessorio(t, cat):
        return None
    # SKU e evidencia mais forte que nome: se o texto traz o codigo de OUTRO produto, so esse outro pode casar.
    dono_do_sku = {
        pid for pid, p in (cat.get("produtos") or {}).items() if any(_alnum(s) in alnum for s in (p.get("skus") or []))
    }
    for pid, p in (cat.get("produtos") or {}).items():
        if dono_do_sku and pid not in dono_do_sku:
            continue
        nenhum = p.get("nenhum") or []
        if any(re.search(n, t) for n in nenhum):
            continue
        achou_sku = any(_alnum(s) in alnum for s in (p.get("skus") or []))
        todos = p.get("todos") or []
        achou_termos = bool(todos) and all(re.search(rx, t) for rx in todos)
        achou_alias = (not achou_sku and not achou_termos) and any(
            all(re.search(rx, t) for rx in alias) for alias in (p.get("aliases_fracos") or [])
        )
        if not (achou_sku or achou_termos or achou_alias):
            continue
        avisos: list[str] = []
        if achou_alias:
            avisos.append("nome_alternativo")  # casa fraco: pode ser o mesmo produto sob outro nome; limita a classificacao
        if p.get("skus") and not achou_sku:
            avisos.append("sku_nao_confirmado")  # informativo: o titulo nao traz o codigo do fabricante
        tensao = p.get("tensao")
        if tensao:
            citadas = _tensoes_mencionadas(t)
            if citadas and tensao not in citadas:
                continue  # oferta de outra tensao: nunca mistura 127V com 220V
            if citadas == {127, 220}:
                avisos.append("tensao_ambigua")
            elif not citadas and not achou_sku:
                avisos.append("tensao_nao_informada")  # o produto existe em outra tensao e o titulo nao diz qual
        btu = p.get("btu")
        if btu:
            citados = _btus_mencionados(t)
            if citados and btu not in citados:
                continue  # outra capacidade
        if p.get("origem") == "nacional" and cat.get("importado_regex") and re.search(cat["importado_regex"], t):
            avisos.append("possivel_importado")
        return Casamento(produto_id=pid, nome=p.get("nome", pid), avisos=avisos)
    return None


def motivo_recusa(texto: str, catalogo_cfg: dict[str, Any] | None = None) -> str | None:
    """Para texto que NAO casou: diz se ele 'quase casou' (mesma marca/linha, outro BTU, tensao, variante, acessorio).

    Serve so para o relatorio de efetividade. None = nada a ver com o catalogo.
    """
    cat = catalogo_cfg or carregar()
    t = normalizar(texto)
    achou_ancora = False
    for p in (cat.get("produtos") or {}).values():
        todos = p.get("todos") or []
        if not todos or not re.search(todos[0], t):
            continue
        if _eh_acessorio(t, cat):
            return "quase_casou:acessorio"
        achou_ancora = True
        if any(re.search(n, t) for n in (p.get("nenhum") or [])):
            return "quase_casou:variante_excluida"
        if p.get("btu"):
            citados = _btus_mencionados(t)
            if citados and p["btu"] not in citados:
                return "quase_casou:outra_capacidade_btu"
        if p.get("tensao"):
            citadas = _tensoes_mencionadas(t)
            if citadas and p["tensao"] not in citadas:
                return "quase_casou:outra_tensao"
    return "quase_casou:mesma_marca_outro_produto" if achou_ancora else None


def produtos_por_grupo(catalogo: dict[str, Any] | None = None) -> dict[str, list[str]]:
    cat = catalogo or carregar()
    grupos: dict[str, list[str]] = {}
    for pid, p in (cat.get("produtos") or {}).items():
        grupos.setdefault(p.get("grupo", "outros"), []).append(pid)
    return grupos
