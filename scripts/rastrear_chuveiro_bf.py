"""Rastreador diario de precos do chuveiro Lorenzetti Loren Shower Eletronico 6800W 220V.

Coleta precos em fontes publicas (Amazon, Leroy Merlin, Zoom e Promobit) usando
o CEP configurado fora do Git, compara com a rodada anterior e com a referencia
inicial de 19/11/2026, salva historico em
~/.central-compras/dados-privados/rastreador-chuveiro/ e opcionalmente envia o
resumo pelo WhatsApp das IAs (nav-zap, CDP 9230).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

try:
    from scripts import rastrear_ares_bf as ra
    from scripts import rastrear_robos_bf as rr
except ImportError:
    import rastrear_ares_bf as ra
    import rastrear_robos_bf as rr

PRIVADO_ROOT = Path.home() / ".central-compras" / "dados-privados"
PRIVADO_DIR = PRIVADO_ROOT / "rastreador-chuveiro"
CONFIG_PATH = PRIVADO_DIR / "config.json"
ARES_CONFIG_PATH = PRIVADO_ROOT / "rastreador-ares" / "config.json"
ENDERECO_PATH = PRIVADO_ROOT / "endereco.md"
ESTADO_PATH = PRIVADO_DIR / "estado.json"
HIST_PATH = PRIVADO_DIR / "historico.jsonl"

MODELO_CHUVEIRO = {
    "chave": "loren_shower_6800_220v",
    "nome": "Lorenzetti Loren Shower Eletronico 6800W 220V",
    "sku": "7510157",
    "ref_data": "19/11",
    "preco_base": 111.89,
    "nota_base": "Amazon.com.br (frete gratis)",
    "url_amazon": "https://www.amazon.com.br/dp/B095V215YN",
    "url_leroy": (
        "https://www.leroymerlin.com.br/"
        "chuveiro-eletrico-eletronico-220v-6800w-branco-quadrado-loren-shower-lorenzetti_91697823"
    ),
    "url_zoom": "https://www.zoom.com.br/chuveiro-ducha/chuveiro-lorenzetti-loren-shower-eletronica-220v-6800w",
}


def carregar_cep(cli_cep: str | None = None) -> str | None:
    """Resolve o CEP de entrega a partir da CLI ou dos arquivos privados locais."""
    if cli_cep:
        return ra.normalizar_cep(cli_cep)

    for path, keys in [
        (CONFIG_PATH, ("cep", "cep_entrega")),
        (ARES_CONFIG_PATH, ("cep", "cep_12k", "cep_18k")),
    ]:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for k in keys:
                        val = data.get(k)
                        if val:
                            return ra.normalizar_cep(str(val))
            except Exception:
                pass

    if ENDERECO_PATH.exists():
        try:
            txt = ENDERECO_PATH.read_text(encoding="utf-8")
            m = re.search(r"CEP:\s*(\d{5}-?\d{3})", txt, re.I)
            if m:
                return ra.normalizar_cep(m.group(1))
        except Exception:
            pass
    return None


def _parse_leroy_texto(body_txt: str) -> dict[str, Any]:
    """Extrai preco principal e eventual frete do texto visivel da Leroy Merlin."""
    out: dict[str, Any] = {
        "preco_avista": None,
        "frete_valor": None,
        "frete_texto": None,
        "total": None,
    }
    if not body_txt:
        return out

    # Bloco principal antes de "Mais opcoes" / "Ver estoque"
    corte = re.split(r"Mais op[çc][õo]es a partir de|Ver estoque nas lojas", body_txt, maxsplit=1, flags=re.I)[0]
    precos = re.findall(r"R\$\s*[\d\.]+,\d{2}", corte)
    valores = [v for v in (ra.parse_brl_flex(p) for p in precos) if v is not None and v >= 50.0]
    if valores:
        out["preco_avista"] = min(valores)

    m_frete = re.search(
        r"(?:Receba em casa|Entrega|Frete)[^\n]{0,60}?(Gr[áa]tis|R\$\s*[\d\.]+,\d{2})",
        body_txt,
        re.I,
    )
    if m_frete:
        ft = m_frete.group(1).strip()
        out["frete_texto"] = ft
        if "gr" in ft.lower():
            out["frete_valor"] = 0.0
        else:
            out["frete_valor"] = ra.parse_brl_flex(ft)

    if out["preco_avista"] is not None and out["frete_valor"] is not None:
        out["total"] = round(out["preco_avista"] + out["frete_valor"], 2)
    return out


def extrair_leroy(page: Any, url: str, cep: str | None = None) -> dict[str, Any]:
    """Coleta preco e tentativa de frete na Leroy Merlin."""
    res: dict[str, Any] = {
        "url": url,
        "preco_avista": None,
        "frete_valor": None,
        "frete_texto": None,
        "total": None,
    }
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(3000)
        if cep:
            cep_inp = page.locator("input[placeholder*='CEP' i]").first
            if cep_inp.count():
                try:
                    cep_inp.scroll_into_view_if_needed()
                    cep_inp.fill(cep)
                    cep_inp.press("Enter")
                    page.wait_for_timeout(2500)
                except Exception:
                    pass
        body_txt = page.locator("body").inner_text()
        parsed = _parse_leroy_texto(body_txt)
        res.update(parsed)
    except Exception as exc:
        res["erro"] = str(exc)[:180]
    return res


def coletar_precos(cep: str | None = None) -> dict[str, Any]:
    agora = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    dados: dict[str, Any] = {"coletado_em": agora, "modelos": {}}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="pt-BR",
            user_agent=rr.USER_AGENT,
        )
        page = ctx.new_page()

        if cep:
            ra.definir_cep_amazon(page, cep)

        amz = ra.extrair_amazon_ar(page, MODELO_CHUVEIRO["url_amazon"])
        leroy = extrair_leroy(page, MODELO_CHUVEIRO["url_leroy"], cep=cep)
        zoom = rr.extrair_zoom(page, MODELO_CHUVEIRO["url_zoom"])
        promobit = rr.extrair_promobit(
            page,
            "loren+shower+eletronico+6800w",
            r"loren\s*shower.*eletr[oô]nic[oa].*6800|6800.*eletr[oô]nic[oa]",
        )
        browser.close()

    # Candidatos com frete conhecido ou referencia direta
    candidatos: list[tuple[float, str, str | None]] = []
    if amz.get("total") is not None:
        vend = amz.get("vendedor") or "n/d"
        frete_txt = amz.get("frete") or "n/d"
        candidatos.append(
            (
                amz["total"],
                f"Amazon ({vend}, frete {frete_txt})",
                ra._parcela_loja_texto(amz),
            )
        )
    elif amz.get("preco") is not None:
        vend = amz.get("vendedor") or "n/d"
        candidatos.append(
            (
                amz["preco"],
                f"Amazon ({vend}, checar frete)",
                ra._parcela_loja_texto(amz),
            )
        )

    if leroy.get("total") is not None:
        candidatos.append(
            (
                leroy["total"],
                f"Leroy Merlin ({rr.fmt_brl(leroy.get('preco_avista'))} + frete {leroy.get('frete_texto')})",
                None,
            )
        )

    if zoom.get("menor_preco") is not None:
        candidatos.append(
            (
                zoom["menor_preco"],
                f"Zoom/{zoom.get('loja') or 'loja'} (s/ frete)",
                None,
            )
        )

    if candidatos:
        melhor = min(candidatos, key=lambda item: item[0])
        melhor_preco, melhor_onde, melhor_parc = melhor
    else:
        melhor_preco, melhor_onde, melhor_parc = None, "indisponivel", None

    dados["modelos"][MODELO_CHUVEIRO["chave"]] = {
        "nome": MODELO_CHUVEIRO["nome"],
        "sku": MODELO_CHUVEIRO["sku"],
        "amazon": amz,
        "leroy": leroy,
        "zoom": zoom,
        "promobit": promobit,
        "melhor_preco": melhor_preco,
        "melhor_onde": melhor_onde,
        "melhor_parcelamento": melhor_parc,
    }
    return dados


def detectar_alteracoes(atual: dict[str, Any], anterior: dict[str, Any] | None) -> list[str]:
    if not anterior:
        return []
    mudancas: list[str] = []
    ant_mods = anterior.get("modelos", {})
    atu_mods = atual.get("modelos", {})
    for key, mod in atu_mods.items():
        ant = ant_mods.get(key)
        if not ant:
            continue
        p_ant = ant.get("melhor_preco")
        p_atu = mod.get("melhor_preco")
        if p_ant != p_atu and (p_ant is not None or p_atu is not None):
            if p_ant is not None and p_atu is not None:
                diff = p_atu - p_ant
                if abs(diff) >= 0.01:
                    icone = "🟢 *BAIXOU*" if diff < 0 else "🔴 *SUBIU*"
                    mudancas.append(
                        f"{icone} *{mod['nome']}:* {rr.fmt_brl(p_ant)} -> *{rr.fmt_brl(p_atu)}* ({mod['melhor_onde']})"
                    )
            else:
                mudancas.append(
                    f"🟡 *{mod['nome']}:* era {rr.fmt_brl(p_ant)}, agora *{rr.fmt_brl(p_atu)}* ({mod['melhor_onde']})"
                )
    return mudancas


def montar_mensagem(atual: dict[str, Any], anterior: dict[str, Any] | None, primeira_vez: bool = False) -> str:
    agora_fmt = dt.datetime.strptime(atual["coletado_em"], "%Y-%m-%d %H:%M").strftime("%d/%m %H:%M")
    mudancas = detectar_alteracoes(atual, anterior)

    linhas = [f"🚿 *RASTREIO CHUVEIRO • {rr.periodo_dia().upper()} ({agora_fmt})*", ""]

    if anterior is None:
        linhas.append(f"📌 *Primeira checagem* (base {MODELO_CHUVEIRO['ref_data']})")
    elif not mudancas:
        ant_fmt = dt.datetime.strptime(anterior["coletado_em"], "%Y-%m-%d %H:%M").strftime("%d/%m %H:%M")
        linhas.append(f"✅ *Sem alteracoes* desde {ant_fmt}")
    else:
        ant_fmt = dt.datetime.strptime(anterior["coletado_em"], "%Y-%m-%d %H:%M").strftime("%d/%m %H:%M")
        linhas.append(f"🚨 *ALTEROU DESDE {ant_fmt}:*")
        linhas.extend(mudancas)

    mod = (atual.get("modelos") or {}).get(MODELO_CHUVEIRO["chave"]) or {}
    p = mod.get("melhor_preco")
    onde = mod.get("melhor_onde") or "indisponivel"
    base = MODELO_CHUVEIRO["preco_base"]
    ref_data = MODELO_CHUVEIRO["ref_data"]

    if p is None:
        bola = "⚪"
        comp = f"ref {ref_data} {rr.fmt_brl(base)}"
    else:
        diff_base = p - base
        if abs(diff_base) < 0.50:
            bola = "🟢"
            comp = f"igual a ref ({ref_data})"
        elif diff_base < 0:
            bola = "🟢"
            comp = f"*{rr.fmt_brl(abs(diff_base))} mais barato* vs {ref_data} ({rr.fmt_brl(base)})"
        else:
            bola = "🔴"
            comp = f"+{rr.fmt_brl(diff_base)} vs {ref_data} ({rr.fmt_brl(base)})"

    linhas.append("")
    linhas.append(f"🚿 *{MODELO_CHUVEIRO['nome']}* (`{MODELO_CHUVEIRO['sku']}`)")
    linhas.append(f"{bola} *{rr.fmt_brl(p)}* · {onde}")
    if mod.get("melhor_parcelamento"):
        linhas.append(f"💳 {mod['melhor_parcelamento']}")
    linhas.append(f"📊 {comp}")

    amz = mod.get("amazon") or {}
    cupons = amz.get("cupons") or []
    if cupons:
        linhas.append(f"🏷️ Cupons Amazon: *{' · '.join(cupons[:3])}*")

    outras: list[str] = []
    leroy = mod.get("leroy") or {}
    if leroy.get("preco_avista") is not None:
        if leroy.get("total") is not None:
            outras.append(f"Leroy Merlin: {rr.fmt_brl(leroy['total'])} entregue")
        else:
            outras.append(f"Leroy Merlin: {rr.fmt_brl(leroy['preco_avista'])} + frete")
    zoom = mod.get("zoom") or {}
    if zoom.get("menor_preco") is not None:
        outras.append(f"Zoom/{zoom.get('loja') or 'loja'}: {rr.fmt_brl(zoom['menor_preco'])}")
    if outras:
        linhas.append("🏪 Outras lojas: " + " | ".join(outras))

    proms = [pr for pr in (mod.get("promobit") or []) if pr.get("preco")]
    if proms:
        linhas.append(f"🔥 Alerta Promobit: *{rr.fmt_brl(proms[0]['preco'])}* (checar voltagem/6800W)")

    linhas.append("")
    linhas.append(f"⏰ Proxima checagem: *{rr.proxima_checagem()}*")

    if primeira_vez:
        linhas.append("")
        linhas.append("💡 *Obs:* conferir na pagina que e a versao *Eletronica 6800W 220V* (nao Multitemperaturas nem 7500W).")

    return "\n".join(linhas)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rastreador de precos do Lorenzetti Loren Shower Eletronico 6800W 220V."
    )
    parser.add_argument("--cep", help="CEP de entrega (sobrescreve config local).")
    parser.add_argument("--enviar-zap", action="store_true", help="Envia o resumo pelo nav-zap.")
    parser.add_argument("--primeira-vez", action="store_true", help="Inclui nota inicial.")
    args = parser.parse_args()

    cep = carregar_cep(args.cep)
    PRIVADO_DIR.mkdir(parents=True, exist_ok=True)
    anterior = None
    if ESTADO_PATH.exists():
        try:
            anterior = json.loads(ESTADO_PATH.read_text(encoding="utf-8"))
        except Exception:
            anterior = None

    atual = coletar_precos(cep=cep)
    mensagem = montar_mensagem(atual, anterior, primeira_vez=args.primeira_vez)
    print(mensagem)

    with HIST_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(atual, ensure_ascii=False) + "\n")

    ESTADO_PATH.write_text(json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.enviar_zap:
        ok, info = rr.enviar_whatsapp(mensagem)
        print(f"[ZAP] ok={ok} | {info}")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
