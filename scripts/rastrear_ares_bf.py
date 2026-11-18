"""Rastreador diario de precos dos splits inverter 12.000 e 18.000 BTU (pre-Black Friday 2026).

Coleta precos e fretes para os CEPs configurados fora do Git
(~/.central-compras/dados-privados/rastreador-ares/config.json) na Amazon,
Dufrio, WebContinental, KaBuM e Promobit, compara com a rodada anterior e com
a referencia de 18/11/2026 (manha), salva historico fora do Git e opcionalmente
envia o resumo pelo WhatsApp das IAs (nav-zap, CDP 9230).
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
    from scripts import rastrear_robos_bf as rr
except ImportError:
    import rastrear_robos_bf as rr

PRIVADO_DIR = Path.home() / ".central-compras" / "dados-privados" / "rastreador-ares"
CONFIG_PATH = PRIVADO_DIR / "config.json"
ESTADO_PATH = PRIVADO_DIR / "estado.json"
HIST_PATH = PRIVADO_DIR / "historico.jsonl"

BASELINE_18_11 = {
    "elgin_12k": {
        "nome": "Elgin Eco Inverter III 12k",
        "sku": "HJFC12C2WGCG",
        "grupo": "12k",
        "preco_total": 1799.90,
        "nota": "Amazon Refricril (frete gratis)",
    },
    "agratto_12k": {
        "nome": "Agratto Kyn Top 12k",
        "sku": "KNICST12F-02",
        "grupo": "12k",
        "preco_total": 1832.02,
        "nota": "Dufrio (R$ 1.699,01 + R$ 133,01)",
    },
    "midea_lite_12k": {
        "nome": "Midea AirVolution Lite 12k",
        "sku": "42EBVCB12M5",
        "grupo": "12k",
        "preco_total": 1982.93,
        "nota": "Dufrio (R$ 1.849,00 + R$ 133,93)",
    },
    "midea_ecomaster_12k": {
        "nome": "Midea AI Ecomaster 12k",
        "sku": "42EZVCA12M5",
        "grupo": "12k",
        "preco_total": 2304.90,
        "nota": "Amazon (R$ 2.114,90 + R$ 190,00)",
    },
    "philco_18k": {
        "nome": "Philco Eco Inverter 18k",
        "sku": "PAC18FTW",
        "grupo": "18k",
        "preco_total": 2438.01,
        "nota": "WebContinental (R$ 2.299,01 + R$ 139,00)",
    },
    "elgin_18k": {
        "nome": "Elgin Eco Inverter III 18k",
        "sku": "HJFC18C2WHCH",
        "grupo": "18k",
        "preco_total": 2758.54,
        "nota": "WebContinental (R$ 2.599,01 + R$ 159,53)",
    },
}


def parse_brl_flex(texto: str) -> float | None:
    """Aceita 'R$ 1.799,90' ou 'R$ 190' (sem centavos)."""
    val = rr.parse_brl(texto)
    if val is not None:
        return val
    m = re.search(r"R\$\s*([\d\.]+)(?!,\d)", texto or "")
    if not m:
        return None
    raw = m.group(1).replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def carregar_config() -> dict[str, str]:
    cfg: dict[str, str] = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg = {str(k): str(v) for k, v in data.items() if v is not None}
        except Exception:
            cfg = {}
    return cfg


def normalizar_cep(cep: str) -> str:
    dig = re.sub(r"\D", "", cep or "")
    if len(dig) != 8:
        raise ValueError(f"CEP invalido (esperado 8 digitos): {cep!r}")
    return dig


def definir_cep_amazon(page: Any, cep: str) -> str:
    dig = normalizar_cep(cep)
    try:
        page.goto("https://www.amazon.com.br/", wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(1500)
        loc_btn = page.locator("#nav-global-location-popover-link")
        if loc_btn.count():
            loc_btn.click()
            page.wait_for_timeout(1200)
            i1 = page.locator("#GLUXZipUpdateInput_0")
            i2 = page.locator("#GLUXZipUpdateInput_1")
            if i1.count() and i2.count():
                i1.fill(dig[:5])
                i2.fill(dig[5:])
                page.locator("#GLUXZipUpdate input[type='submit'], #GLUXZipUpdate").first.click()
                page.wait_for_timeout(2000)
                for sel in ["#GLUXConfirmClose", "button[name='glowDoneButton']"]:
                    if page.locator(sel).count():
                        try:
                            page.locator(sel).first.click(timeout=1500)
                            page.wait_for_timeout(800)
                        except Exception:
                            pass
        if page.locator("#glow-ingress-line2").count():
            return page.locator("#glow-ingress-line2").inner_text().strip()
    except Exception as exc:
        return f"erro: {str(exc)[:100]}"
    return "n/d"


def extrair_amazon_ar(page: Any, url: str) -> dict[str, Any]:
    res = rr.extrair_amazon(page, url)
    res["frete_valor"] = None
    res["prazo"] = None
    res["total"] = None
    try:
        delivery_txt = (
            page.locator("#mir-layout-DELIVERY_BLOCK").inner_text()
            if page.locator("#mir-layout-DELIVERY_BLOCK").count()
            else ""
        )
        buybox_txt = (
            page.locator("#desktop_buybox").inner_text()
            if page.locator("#desktop_buybox").count()
            else ""
        )
        blob = delivery_txt or buybox_txt
        if "Entrega GRÁTIS" in blob or "Entrega GRATIS" in blob or res.get("frete") == "Gratis":
            res["frete"] = "Gratis"
            res["frete_valor"] = 0.0
        else:
            mf = re.search(r"Entrega\s+(R\$\s*[\d\.]+(?:,\d{2})?)", blob)
            if mf:
                res["frete"] = mf.group(1).strip()
                res["frete_valor"] = parse_brl_flex(mf.group(1))
        mp = re.search(r"(\d+\s*(?:-\s*\d+\s*)?de\s+[A-Za-zçÇ]+(?:\s*-\s*\d+\s*de\s+[A-Za-zçÇ]+)?)", blob)
        if mp:
            res["prazo"] = mp.group(1).strip()
        if res.get("preco") is not None and res["frete_valor"] is not None:
            res["total"] = round(res["preco"] + res["frete_valor"], 2)
    except Exception as exc:
        res["erro_frete"] = str(exc)[:120]
    return res


def extrair_dufrio_ar(page: Any, url: str, cep: str) -> dict[str, Any]:
    dig = normalizar_cep(cep)
    res: dict[str, Any] = {
        "url": url,
        "preco_pix": None,
        "frete_valor": None,
        "prazo": None,
        "total": None,
        "disponivel": None,
    }
    try:
        page.goto(url, wait_until="load", timeout=30000)
        page.wait_for_timeout(2200)
        pix_loc = page.locator(".product-pricing__cash-price")
        if pix_loc.count():
            res["preco_pix"] = parse_brl_flex(pix_loc.first.inner_text())
        if res["preco_pix"] is None:
            body_head = page.locator("main").inner_text()[:800] if page.locator("main").count() else ""
            res["preco_pix"] = parse_brl_flex(body_head)

        page.wait_for_selector(".shipping-calculator", timeout=10000)
        ship = page.locator(".shipping-calculator")
        if ship.count():
            ship_txt = ship.first.inner_text()
            if "Informar CEP" in ship_txt:
                btn = page.locator(".shipping-calculator__link-button, .shipping-calculator__header").first
                btn.scroll_into_view_if_needed()
                btn.click()
                page.wait_for_selector(".common-dialog__content input[type='tel']", timeout=8000)
                dlg = page.locator(".common-dialog__content")
                inp = dlg.locator("input[type='tel']").first
                inp.click()
                inp.type(dig, delay=40)
                page.wait_for_timeout(400)
                dlg.locator("button:has-text('Procurar')").first.click()
                for _ in range(24):
                    page.wait_for_timeout(500)
                    if dlg.count():
                        conf_btn = dlg.locator("button:has-text('Confirmar')")
                        if conf_btn.count() and conf_btn.first.is_visible():
                            try:
                                conf_btn.first.click(timeout=2000)
                                page.wait_for_timeout(800)
                            except Exception:
                                pass
                    ship_txt = ship.first.inner_text()
                    if "R$" in ship_txt or "Grátis" in ship_txt or "Gratis" in ship_txt:
                        break
            else:
                for _ in range(10):
                    if "R$" in ship_txt or "Grátis" in ship_txt or "Gratis" in ship_txt:
                        break
                    page.wait_for_timeout(500)
                    ship_txt = ship.first.inner_text()
            res["frete_valor"] = parse_brl_flex(ship_txt)
            mp = re.search(r"(\d+\s*dias?\s*úteis)", ship_txt, re.I)
            if mp:
                res["prazo"] = mp.group(1).strip()

        res["disponivel"] = res["preco_pix"] is not None
        if res["preco_pix"] is not None and res["frete_valor"] is not None:
            res["total"] = round(res["preco_pix"] + res["frete_valor"], 2)
    except Exception as exc:
        res["erro"] = str(exc)[:180]
    return res


def extrair_webcontinental_ar(page: Any, url: str, cep: str) -> dict[str, Any]:
    dig = normalizar_cep(cep)
    res: dict[str, Any] = {
        "url": url,
        "preco_pix": None,
        "frete_valor": None,
        "prazo": None,
        "total": None,
        "vendedor": None,
        "cupom_banner": None,
    }
    try:
        page.goto(url, wait_until="load", timeout=30000)
        page.wait_for_timeout(2500)

        pix_loc = page.locator(
            ".vtex-product-price-1-x-spotPrice--boletopixtext, .vtex-product-price-1-x-spotPrice--product-spot-price"
        )
        if pix_loc.count():
            res["preco_pix"] = parse_brl_flex(pix_loc.first.inner_text())

        vend_loc = page.locator(".lojawebcontinental-app-front-1-x-customSellerLinkLink")
        if vend_loc.count() >= 2:
            res["vendedor"] = vend_loc.nth(1).inner_text().strip()
        elif vend_loc.count() == 1:
            res["vendedor"] = vend_loc.first.inner_text().strip()

        body_txt = page.locator("body").inner_text()
        mc = re.search(r"Aplicar cupom de\s+(R\$\s*[\d\.]+(?:,\d{2})?)", body_txt, re.I)
        if mc:
            res["cupom_banner"] = mc.group(1).strip()

        try:
            page.wait_for_selector("input[name='postalCode']", timeout=12000)
            inp = page.locator("input[name='postalCode']").first
            inp.scroll_into_view_if_needed()
            inp.fill(dig)
            page.wait_for_timeout(400)
            page.locator("button:has-text('Calcular')").first.click()
            for _ in range(12):
                page.wait_for_timeout(500)
                body_now = page.locator("body").inner_text()
                m_ship = re.search(
                    r"ENTREGA\s+PADR[ÃA]O[\s\S]{0,120}?Em\s+at[ée]\s+(\d+\s*dias?\s*[úu]teis)[\s\S]{0,80}?(R\$\s*[\d\.]+,\d{2})",
                    body_now,
                    re.I,
                )
                if m_ship:
                    res["prazo"] = m_ship.group(1).strip()
                    res["frete_valor"] = parse_brl_flex(m_ship.group(2))
                    break
        except Exception as exc:
            res["erro_frete"] = str(exc)[:120]

        if res["preco_pix"] is not None and res["frete_valor"] is not None:
            res["total"] = round(res["preco_pix"] + res["frete_valor"], 2)
    except Exception as exc:
        res["erro"] = str(exc)[:180]
    return res


def _escolher_melhor(opcoes: list[tuple[float | None, str]]) -> tuple[float | None, str]:
    validas = [(val, desc) for val, desc in opcoes if val is not None]
    if not validas:
        return None, "indisponivel"
    return min(validas, key=lambda x: x[0])


def coletar_precos(cep_12k: str, cep_18k: str) -> dict[str, Any]:
    agora = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    dados: dict[str, Any] = {"coletado_em": agora, "modelos": {}}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

        # Contexto 12.000 BTU
        ctx12 = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="pt-BR",
            user_agent=rr.USER_AGENT,
        )
        p12 = ctx12.new_page()
        definir_cep_amazon(p12, cep_12k)

        elgin12_amz = extrair_amazon_ar(p12, "https://www.amazon.com.br/dp/B0H6Y153G3")
        elgin12_kbm = rr.extrair_kabum(
            p12,
            "https://www.kabum.com.br/produto/1040358/ar-condicionado-12000-btus-split-hi-wall-inverter-elgin-frio-eco-iii-220v",
        )
        elgin12_prom = rr.extrair_promobit(p12, "elgin+12000+inverter", r"(?:elgin|hjfc12)")
        cand_elgin12 = [
            (
                elgin12_amz.get("total"),
                f"Amazon ({elgin12_amz.get('vendedor') or 'n/d'}, frete {elgin12_amz.get('frete') or 'n/d'})",
            ),
            (
                elgin12_kbm.get("preco_pix"),
                f"KaBuM Pix s/ frete ({elgin12_kbm.get('vendedor') or 'n/d'})",
            ),
        ]
        m_elgin12 = _escolher_melhor(cand_elgin12)
        dados["modelos"]["elgin_12k"] = {
            "nome": BASELINE_18_11["elgin_12k"]["nome"],
            "sku": BASELINE_18_11["elgin_12k"]["sku"],
            "grupo": "12k",
            "amazon": elgin12_amz,
            "kabum": elgin12_kbm,
            "promobit": elgin12_prom,
            "melhor_preco": m_elgin12[0],
            "melhor_onde": m_elgin12[1],
        }

        agratto12_duf = extrair_dufrio_ar(
            p12,
            "https://www.dufrio.com.br/ar-condicionado-split-inverter-12000-btus-agrato-kyn-top-frio-knicst12f-02-220v.html",
            cep_12k,
        )
        dados["modelos"]["agratto_12k"] = {
            "nome": BASELINE_18_11["agratto_12k"]["nome"],
            "sku": BASELINE_18_11["agratto_12k"]["sku"],
            "grupo": "12k",
            "dufrio": agratto12_duf,
            "melhor_preco": agratto12_duf.get("total"),
            "melhor_onde": (
                f"Dufrio ({rr.fmt_brl(agratto12_duf.get('preco_pix'))} + frete {rr.fmt_brl(agratto12_duf.get('frete_valor'))})"
                if agratto12_duf.get("total") is not None
                else "Dufrio (indisponivel)"
            ),
        }

        midea_lite_duf = extrair_dufrio_ar(
            p12,
            "https://www.dufrio.com.br/ar-condicionado-split-inverter-12000-btus-midea-air-volution-lite-frio-42ebvcb12m5-220v.html",
            cep_12k,
        )
        dados["modelos"]["midea_lite_12k"] = {
            "nome": BASELINE_18_11["midea_lite_12k"]["nome"],
            "sku": BASELINE_18_11["midea_lite_12k"]["sku"],
            "grupo": "12k",
            "dufrio": midea_lite_duf,
            "melhor_preco": midea_lite_duf.get("total"),
            "melhor_onde": (
                f"Dufrio ({rr.fmt_brl(midea_lite_duf.get('preco_pix'))} + frete {rr.fmt_brl(midea_lite_duf.get('frete_valor'))})"
                if midea_lite_duf.get("total") is not None
                else "Dufrio (indisponivel)"
            ),
        }

        midea_eco_amz = extrair_amazon_ar(p12, "https://www.amazon.com.br/dp/B0F9LJT26T")
        dados["modelos"]["midea_ecomaster_12k"] = {
            "nome": BASELINE_18_11["midea_ecomaster_12k"]["nome"],
            "sku": BASELINE_18_11["midea_ecomaster_12k"]["sku"],
            "grupo": "12k",
            "amazon": midea_eco_amz,
            "melhor_preco": midea_eco_amz.get("total"),
            "melhor_onde": (
                f"Amazon ({midea_eco_amz.get('vendedor') or 'n/d'}, frete {midea_eco_amz.get('frete') or 'n/d'})"
                if midea_eco_amz.get("total") is not None
                else "Amazon (indisponivel)"
            ),
        }
        ctx12.close()

        # Contexto 18.000 BTU
        ctx18 = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="pt-BR",
            user_agent=rr.USER_AGENT,
        )
        p18 = ctx18.new_page()
        definir_cep_amazon(p18, cep_18k)

        philco18_amz = extrair_amazon_ar(p18, "https://www.amazon.com.br/dp/B0HKPT8XSY")
        philco18_wc = extrair_webcontinental_ar(p18, "https://www.webcontinental.com.br/010101015m31812221/p", cep_18k)
        philco18_prom = rr.extrair_promobit(p18, "pac18ftw", r"pac18ftw")
        cand_philco18 = [
            (
                philco18_amz.get("total"),
                f"Amazon ({philco18_amz.get('vendedor') or 'n/d'}, frete {philco18_amz.get('frete') or 'n/d'})",
            ),
            (
                philco18_wc.get("total"),
                f"WebContinental ({rr.fmt_brl(philco18_wc.get('preco_pix'))} + frete {rr.fmt_brl(philco18_wc.get('frete_valor'))})",
            ),
        ]
        m_philco18 = _escolher_melhor(cand_philco18)
        dados["modelos"]["philco_18k"] = {
            "nome": BASELINE_18_11["philco_18k"]["nome"],
            "sku": BASELINE_18_11["philco_18k"]["sku"],
            "grupo": "18k",
            "amazon": philco18_amz,
            "webcontinental": philco18_wc,
            "promobit": philco18_prom,
            "melhor_preco": m_philco18[0],
            "melhor_onde": m_philco18[1],
        }

        elgin18_wc = extrair_webcontinental_ar(p18, "https://www.webcontinental.com.br/010101006l30812222/p", cep_18k)
        elgin18_prom = rr.extrair_promobit(p18, "hjfc18c2whch", r"(?:hjfc18|elgin.*18000)")
        dados["modelos"]["elgin_18k"] = {
            "nome": BASELINE_18_11["elgin_18k"]["nome"],
            "sku": BASELINE_18_11["elgin_18k"]["sku"],
            "grupo": "18k",
            "webcontinental": elgin18_wc,
            "promobit": elgin18_prom,
            "melhor_preco": elgin18_wc.get("total"),
            "melhor_onde": (
                f"WebContinental ({rr.fmt_brl(elgin18_wc.get('preco_pix'))} + frete {rr.fmt_brl(elgin18_wc.get('frete_valor'))})"
                if elgin18_wc.get("total") is not None
                else "WebContinental (indisponivel)"
            ),
        }
        ctx18.close()
        browser.close()

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
                if abs(diff) < 0.01:
                    continue
                icone = "🟢 *BAIXOU*" if diff < 0 else "🔴 *SUBIU*"
                mudancas.append(
                    f"{icone} *{mod['nome']}:* {rr.fmt_brl(p_ant)} -> *{rr.fmt_brl(p_atu)}* ({mod['melhor_onde']})"
                )
            else:
                mudancas.append(
                    f"🟡 *{mod['nome']}:* era {rr.fmt_brl(p_ant)}, agora *{rr.fmt_brl(p_atu)}* ({mod['melhor_onde']})"
                )
    return mudancas


def _ordenar_grupo(modelos: dict[str, Any], grupo: str) -> list[tuple[str, dict[str, Any]]]:
    itens = [(k, v) for k, v in modelos.items() if v.get("grupo") == grupo]
    itens.sort(key=lambda kv: (kv[1].get("melhor_preco") is None, kv[1].get("melhor_preco") or 999999.0))
    return itens


def montar_mensagem(atual: dict[str, Any], anterior: dict[str, Any] | None, primeira_vez: bool = False) -> str:
    agora_fmt = dt.datetime.strptime(atual["coletado_em"], "%Y-%m-%d %H:%M").strftime("%d/%m %H:%M")
    mudancas = detectar_alteracoes(atual, anterior)

    linhas = [f"❄️ *RASTREIO ARES • {rr.periodo_dia().upper()} ({agora_fmt})*", ""]

    if anterior is None:
        linhas.append("📌 *Primeira checagem* (base 18/11 manha)")
    elif not mudancas:
        ant_fmt = dt.datetime.strptime(anterior["coletado_em"], "%Y-%m-%d %H:%M").strftime("%d/%m %H:%M")
        linhas.append(f"✅ *Sem alteracoes* desde {ant_fmt}")
    else:
        ant_fmt = dt.datetime.strptime(anterior["coletado_em"], "%Y-%m-%d %H:%M").strftime("%d/%m %H:%M")
        linhas.append(f"🚨 *ALTEROU DESDE {ant_fmt}:*")
        linhas.extend(mudancas)

    medalhas = ["🥇", "🥈", "🥉", "4️⃣"]
    for titulo, grupo in [("🔹 *12.000 BTU (220V, entregue)*", "12k"), ("🔹 *18.000 BTU (220V, entregue)*", "18k")]:
        linhas.append("")
        linhas.append(titulo)
        ordenados = _ordenar_grupo(atual.get("modelos", {}), grupo)
        for idx, (key, mod) in enumerate(ordenados):
            medalha = medalhas[idx] if idx < len(medalhas) else "•"
            base = BASELINE_18_11[key]["preco_total"]
            p = mod.get("melhor_preco")
            onde = mod.get("melhor_onde")

            if p is None:
                bola = "⚪"
                comp = f"ref manha {rr.fmt_brl(base)}"
            else:
                diff_base = p - base
                if abs(diff_base) < 0.50:
                    bola = "🟢"
                    comp = "igual a manha (18/11)"
                elif diff_base < 0:
                    bola = "🟢"
                    comp = f"*{rr.fmt_brl(abs(diff_base))} mais barato* vs manha ({rr.fmt_brl(base)})"
                else:
                    bola = "🔴"
                    comp = f"+{rr.fmt_brl(diff_base)} vs manha ({rr.fmt_brl(base)})"

            linhas.append("")
            linhas.append(f"{medalha} *{mod['nome']}* (`{mod['sku']}`)")
            linhas.append(f"{bola} *{rr.fmt_brl(p)}* · {onde}")
            linhas.append(f"📊 {comp}")

            if key == "elgin_12k":
                cupons = (mod.get("amazon") or {}).get("cupons") or []
                if cupons:
                    linhas.append(f"🏷️ Cupom Amazon: *{' · '.join(cupons[:3])}*")
            elif key == "philco_18k":
                cup_wc = (mod.get("webcontinental") or {}).get("cupom_banner")
                if cup_wc:
                    linhas.append(f"🏷️ WebContinental exibe cupom *{cup_wc}* (conferir no carrinho)")

        if grupo == "18k":
            p_phi = (atual.get("modelos", {}).get("philco_18k") or {}).get("melhor_preco")
            p_elg = (atual.get("modelos", {}).get("elgin_18k") or {}).get("melhor_preco")
            if p_phi is not None and p_elg is not None:
                diff_18 = p_elg - p_phi
                if diff_18 > 0:
                    linhas.append("")
                    linhas.append(
                        f"⚖️ *Elgin 18k vs Philco:* +{rr.fmt_brl(diff_18)} por 101 kWh/ano a menos e garantia 36m/10a"
                    )

    linhas.append("")
    linhas.append(f"⏰ Proxima checagem: *{rr.proxima_checagem()}*")

    if primeira_vez:
        linhas.append("")
        linhas.append(
            "💡 *Resumo:* nos 12k o *Elgin HJFC12C2WGCG* segue campeao com frete gratis na Amazon; nos 18k o *Philco PAC18FTW* subiu na WebContinental e apareceu na Amazon como menor total entregue."
        )

    return "\n".join(linhas)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rastreador de precos dos splits 12.000 e 18.000 BTU.")
    parser.add_argument("--cep-12k", help="CEP de entrega para o 12.000 BTU (sobrescreve config.json).")
    parser.add_argument("--cep-18k", help="CEP de entrega para o 18.000 BTU (sobrescreve config.json).")
    parser.add_argument("--enviar-zap", action="store_true", help="Envia o resumo pelo nav-zap.")
    parser.add_argument("--primeira-vez", action="store_true", help="Inclui analise inicial.")
    args = parser.parse_args()

    cfg = carregar_config()
    cep_12k = args.cep_12k or cfg.get("cep_12k")
    cep_18k = args.cep_18k or cfg.get("cep_18k")
    if not cep_12k or not cep_18k:
        print(
            f"ERRO: configure cep_12k e cep_18k em {CONFIG_PATH} ou informe --cep-12k e --cep-18k.",
            file=sys.stderr,
        )
        return 2

    PRIVADO_DIR.mkdir(parents=True, exist_ok=True)
    anterior = None
    if ESTADO_PATH.exists():
        try:
            anterior = json.loads(ESTADO_PATH.read_text(encoding="utf-8"))
        except Exception:
            anterior = None

    atual = coletar_precos(cep_12k, cep_18k)
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
