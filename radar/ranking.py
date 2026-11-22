"""Classificacao de oportunidades: CRITICA, ALTA, MEDIA, BAIXA.

Deterministico e configuravel (config/radar_regras.yaml). Ofertas comunitarias nunca chegam a CRITICA:
isso exige confirmacao (VALIDADO). Sem historico suficiente nao se afirma "minimo historico".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from . import caminhos
from .cupons import EXPIRADO, NAO_CONFIRMADO, PROVAVEL, VALIDADO

ARQ_REGRAS = caminhos.CONFIG_DIR / "radar_regras.yaml"
ORDEM = {"CRITICA": 4, "ALTA": 3, "MEDIA": 2, "BAIXA": 1}


def arquivo_operacao() -> Path:
    """Estado OPERACIONAL local (ligado/desligado), FORA do Git: <dados-privados>/radar/operacao.yaml. Nao cria a pasta."""
    return caminhos.privado_dir() / "radar" / "operacao.yaml"


def _operacao_valida(bruto: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Aceita SO as 3 chaves da ativacao e SO com o tipo certo. O resto e ignorado e avisado: o arquivo local nunca altera politica."""
    ok: dict[str, dict[str, Any]] = {}
    avisos: list[str] = []
    if not isinstance(bruto, dict):
        return ok, ["conteudo nao e um mapa"]
    for bloco, chave, tipo in (("alertas", "enviar", bool), ("alertas", "homologado_em", (str, type(None))), ("piloto", "ativo", bool)):
        sec = bruto.get(bloco)
        if isinstance(sec, dict) and chave in sec:
            v = sec[chave]
            if chave == "homologado_em" and hasattr(v, "strftime"):   # "2026-11-22 09:03:00" sem aspas vira data no YAML: aceita e normaliza
                v = v.strftime("%Y-%m-%d %H:%M")
            if isinstance(v, tipo):
                ok.setdefault(bloco, {})[chave] = v
            else:
                avisos.append(f"{bloco}.{chave} com tipo invalido ({type(v).__name__}): ignorado")
    extras = {b: [k for k in (s or {}) if k not in ("enviar", "homologado_em", "ativo")] for b, s in bruto.items() if isinstance(s, dict) and b in ("alertas", "piloto")}
    outros = [b for b in bruto if b not in ("alertas", "piloto") and not str(b).startswith(("ativado", "autorizado", "desligado", "commit", "nota"))]
    if any(extras.values()) or outros:
        avisos.append("chaves fora da lista permitida ignoradas")
    return ok, avisos


def carregar_regras(caminho: Path | None = None, *, operacao: bool = True) -> dict[str, Any]:
    """Regras versionadas (config/radar_regras.yaml) + camada OPERACIONAL local (operacao.yaml: enviar, homologado_em, piloto.ativo).

    Sem o arquivo local (instalacao nova, `git pull`, `git restore`) vale o versionado, que e SOMBRA. Arquivo ilegivel = o versionado
    (seguro: nao liga nada). `operacao=False` ou `caminho` explicito ignoram a camada local (cenarios sinteticos, ensaios e testes).
    O resultado traz `_operacao` (origem e avisos) para os paineis mostrarem de onde veio o estado."""
    regras = yaml.safe_load((caminho or ARQ_REGRAS).read_text(encoding="utf-8")) or {}
    info: dict[str, Any] = {"arquivo": None, "presente": False, "aplicado": [], "avisos": []}
    if caminho is None and operacao:
        arq = arquivo_operacao()
        info["arquivo"] = str(arq)
        if arq.exists():
            info["presente"] = True
            try:
                bruto = yaml.safe_load(arq.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as exc:
                bruto = None
                info["avisos"].append(f"operacao.yaml ilegivel ({type(exc).__name__}): vale o versionado (sombra)")
            else:
                valido, avisos = _operacao_valida(bruto)
                info["avisos"] += avisos
                for bloco, chaves in valido.items():
                    regras.setdefault(bloco, {})
                    if not isinstance(regras[bloco], dict):
                        regras[bloco] = {}
                    for k, v in chaves.items():
                        regras[bloco][k] = v
                        info["aplicado"].append(f"{bloco}.{k}")
    regras["_operacao"] = info
    return regras


def gravar_operacao(valores: dict[str, dict[str, Any]], extras: dict[str, Any] | None = None) -> Path:
    """Grava o estado operacional local de forma ATOMICA (arquivo temporario + replace) para o agendador nunca ler pela metade.
    Preserva o que ja existia (metadados e chaves nao mencionadas); `extras` sao so metadados (ativado_em, autorizado_por...)."""
    import os
    import tempfile

    arq = arquivo_operacao()
    arq.parent.mkdir(parents=True, exist_ok=True)
    atual: dict[str, Any] = {}
    if arq.exists():
        try:
            atual = yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            atual = {}
        if not isinstance(atual, dict):
            atual = {}
    for bloco, chaves in valores.items():
        atual.setdefault(bloco, {})
        atual[bloco].update(chaves)
    atual.update(extras or {})
    texto = ("# ESTADO OPERACIONAL LOCAL do radar. NAO versionado (fica fora do Git). Valem so: alertas.enviar, alertas.homologado_em, piloto.ativo.\n"
             "# Sem este arquivo o radar roda em SOMBRA. Desligar: python -m radar ativacao --desligar\n"
             + yaml.safe_dump(atual, allow_unicode=True, sort_keys=False, default_flow_style=False))
    fd, tmp = tempfile.mkstemp(prefix=".operacao-", suffix=".tmp", dir=str(arq.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        os.replace(tmp, arq)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return arq


def classificar(
    preco_final: float | None,
    validacao: str,
    stats: dict[str, Any] | None,
    regras: dict[str, Any],
    avisos: list[str] | None = None,
    idade_horas: float | None = None,
    preco_ref: float | None = None,
) -> tuple[str, float, str]:
    """Retorna (classe, score 0-100, motivo). `validacao` e o pior estado entre preco e cupom usados."""
    cl = regras.get("classificacao", {})
    avisos = avisos or []
    if preco_final is None:
        return "BAIXA", 0.0, "sem preco final calculavel"
    if validacao == EXPIRADO:
        return "BAIXA", 0.0, "promocao/cupom expirado"
    stats = stats or {}
    total, mes = stats.get("historico_total") or {}, stats.get("ultimos_30_dias") or {}
    n, dias = int(stats.get("observacoes_validas") or 0), int(stats.get("cobertura_dias") or 0)
    historico_ok = n >= int(cl.get("min_observacoes_historico", 3)) and dias >= int(cl.get("min_dias_historico", 1))
    if not historico_ok:
        return "MEDIA" if validacao in (PROVAVEL, VALIDADO) else "BAIXA", 10.0, (
            f"historico insuficiente ({n} observacoes em {dias} dia(s)): sem base para afirmar minimo"
        )
    minimo, mediana = total.get("menor"), mes.get("mediana") or total.get("mediana")
    queda = (mediana - preco_final) / mediana * 100.0 if mediana else 0.0
    perto_do_minimo = minimo is not None and preco_final <= minimo * (1 + cl.get("alta", {}).get("ate_pct_acima_do_minimo", 3) / 100)
    novo_minimo = minimo is not None and preco_final <= minimo
    score = max(0.0, min(100.0, queda * 3 + (20 if novo_minimo else 0) + {VALIDADO: 20, PROVAVEL: 8}.get(validacao, 0)))
    if idade_horas is not None and idade_horas > 6:
        score -= 10

    # Avisos que impedem CRITICA/ALTA. Dois deles (anuncio sem voltagem; nome alternativo sem SKU) o proprio comprador
    # resolve ao conferir o anuncio e marcar `radar validar`; os demais (bivolt, importado) nao.
    bloqueantes = {"tensao_ambigua", "possivel_importado", "tensao_nao_informada", "nome_alternativo", "preco_depende_de_cupom_nao_confirmado"}
    if validacao == VALIDADO:
        bloqueantes -= {"tensao_nao_informada", "nome_alternativo", "preco_depende_de_cupom_nao_confirmado"}
    if bloqueantes & set(avisos):
        so_cupom = (bloqueantes & set(avisos)) == {"preco_depende_de_cupom_nao_confirmado"}
        return ("MEDIA" if validacao in (PROVAVEL, VALIDADO) and (novo_minimo or queda >= 5) else "BAIXA"), score, (
            "o preco anunciado so vale com um cupom NAO confirmado (a loja cobra mais sem ele): confirme no carrinho (radar validar) antes de contar como oferta"
            if so_cupom else "aviso de voltagem/modelo/importacao: confira o anuncio antes de decidir"
        )
    # NOVIDADE: o seu historico e feito dos precos ATUAIS que os relatorios ja mostram, entao uma oferta igual a eles parece "no minimo".
    # Alerta urgente exige MELHORA real sobre o melhor preco atual conhecido (achado ao reencenar 24 ofertas reais em 21/11/2026:
    # 8 delas, todas no preco que ja monitoramos, seriam ALTA).
    min_melhora = float(cl.get("alta", {}).get("melhora_vs_atual_pct", 3))
    melhora = (preco_ref - preco_final) / preco_ref * 100.0 if preco_ref else None
    if melhora is not None and melhora < min_melhora:
        return ("MEDIA" if validacao in (PROVAVEL, VALIDADO) and (perto_do_minimo or queda >= 5) else "BAIXA"), score, (
            f"sem novidade: so {melhora:.1f}% abaixo do melhor preco atual ja monitorado (R$ {preco_ref:.2f}); exige {min_melhora:.0f}%" if melhora >= 0
            else f"mais caro que o melhor preco atual ja monitorado (R$ {preco_ref:.2f})")
    if validacao == VALIDADO and (novo_minimo or queda >= cl.get("critica", {}).get("queda_vs_mediana_pct", 25)):
        return "CRITICA", score, ("preco abaixo do menor valor do seu historico; oferta validada no carrinho" if novo_minimo
                                  else f"{queda:.0f}% abaixo da mediana de 30 dias; oferta validada no carrinho")
    if validacao in (PROVAVEL, VALIDADO) and (perto_do_minimo or queda >= cl.get("alta", {}).get("queda_vs_mediana_pct", 15)):
        base = ("preco no menor valor do seu historico (ou ate 3% dele)" if perto_do_minimo
                else f"{queda:.0f}% abaixo da mediana de 30 dias")
        if melhora is not None:
            base += f"; {melhora:.0f}% abaixo do melhor preco atual (R$ {preco_ref:.2f})"
        return "ALTA", score, base + ("; oferta validada no carrinho" if validacao == VALIDADO else "; oferta ainda NAO validada no carrinho")
    if validacao != NAO_CONFIRMADO and queda >= cl.get("media", {}).get("queda_vs_mediana_pct", 5):
        return "MEDIA", score, f"{queda:.0f}% abaixo da mediana de 30 dias"
    return "BAIXA", score, "sem vantagem de preco demonstrada" if queda < 5 else "vantagem sem confirmacao"
