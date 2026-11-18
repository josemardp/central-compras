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


def _extrair_parcelas_texto(texto: str) -> dict[str, Any]:
    """Extrai quantidade de parcelas e valor da parcela sem juros de um trecho."""
    out: dict[str, Any] = {"parcelas_qtd": None, "parcela_valor": None, "preco_parcelado": None}
    if not texto:
        return out
    m_full = re.search(
        r"(?:ou\s*)?(R\$\s*[\d\.]+,\d{2})\s*(?:\([^)]*\)\s*)?em\s+at[ée]\s+(\d+)x\s+de\s+(R\$\s*[\d\.]+,\d{2})\s*sem\s+juros",
        texto,
        re.I,
    )
    if m_full:
        out["preco_parcelado"] = parse_brl_flex(m_full.group(1))
        out["parcelas_qtd"] = int(m_full.group(2))
        out["parcela_valor"] = parse_brl_flex(m_full.group(3))
        return out
    m = re.search(
        r"(\d+)\s*x\s*(?:de\s*)?(R\$\s*[\d\.]+,\d{2})\s*(?:sem juros|/m[eê]s)?",
        texto,
        re.I,
    )
    if m:
        out["parcelas_qtd"] = int(m.group(1))
        out["parcela_valor"] = parse_brl_flex(m.group(2))
    m_tot = re.search(r"total\s+parcelado\s*(R\$\s*[\d\.]+,\d{2})", texto, re.I)
    if m_tot:
        out["preco_parcelado"] = parse_brl_flex(m_tot.group(1))
    elif out["parcelas_qtd"] and out["parcela_valor"]:
        out["preco_parcelado"] = round(out["parcelas_qtd"] * out["parcela_valor"], 2)
    return out


def formatar_parcelas(qtd: int | None, val_parcela: float | None, total: float | None) -> str | None:
    if not qtd or val_parcela is None:
        return None
    base = f"{qtd}x de {rr.fmt_brl(val_parcela)} s/ juros"
    if total is not None:
        return f"{rr.fmt_brl(total)} em ate {base}"
    return base


def extrair_amazon_ar(page: Any, url: str) -> dict[str, Any]:
    res = rr.extrair_amazon(page, url)
    res["frete_valor"] = None
    res["prazo"] = None
    res["total"] = None
    res["parcelas_qtd"] = None
    res["parcela_valor"] = None
    res["preco_parcelado"] = None
    res["total_parcelado"] = None
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
        core_txt = (
            page.locator("#corePrice_feature_div").first.inner_text()
            if page.locator("#corePrice_feature_div").count()
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

        apex_txt = (
            page.locator("#apex_desktop").first.inner_text()
            if page.locator("#apex_desktop").count()
            else ""
        )
        parc = _extrair_parcelas_texto(apex_txt + "\n" + core_txt + "\n" + buybox_txt)
        res["parcelas_qtd"] = parc["parcelas_qtd"]
        res["parcela_valor"] = parc["parcela_valor"]
        res["preco_parcelado"] = parc["preco_parcelado"]
        if res["preco_parcelado"] is not None and res["frete_valor"] is not None:
            res["total_parcelado"] = round(res["preco_parcelado"] + res["frete_valor"], 2)
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
        "parcelas_qtd": None,
        "parcela_valor": None,
        "preco_parcelado": None,
        "total_parcelado": None,
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

        inst_loc = page.locator(".installment-price, .product-pricing")
        if inst_loc.count():
            parc = _extrair_parcelas_texto(inst_loc.first.inner_text())
            res["parcelas_qtd"] = parc["parcelas_qtd"]
            res["parcela_valor"] = parc["parcela_valor"]
            res["preco_parcelado"] = parc["preco_parcelado"]

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
        if res["preco_parcelado"] is not None and res["frete_valor"] is not None:
            res["total_parcelado"] = round(res["preco_parcelado"] + res["frete_valor"], 2)
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
        "parcelas_qtd": None,
        "parcela_valor": None,
        "preco_parcelado": None,
        "total_parcelado": None,
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

        body_txt = page.locator("body").inner_text()
        m_wc_parc = re.search(
            r"Ou\s+(R\$\s*[\d\.]+,\d{2})\s+at[ée]\s+(\d+)x\s+de\s+(R\$\s*[\d\.]+,\d{2})",
            body_txt[:3000],
            re.I,
        )
        if m_wc_parc:
            res["preco_parcelado"] = parse_brl_flex(m_wc_parc.group(1))
            res["parcelas_qtd"] = int(m_wc_parc.group(2))
            res["parcela_valor"] = parse_brl_flex(m_wc_parc.group(3))

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
        if res["preco_parcelado"] is not None and res["frete_valor"] is not None:
            res["total_parcelado"] = round(res["preco_parcelado"] + res["frete_valor"], 2)
    except Exception as exc:
        res["erro"] = str(exc)[:180]
    return res


def extrair_frigelar_ar(page: Any, url: str, cep: str) -> dict[str, Any]:
    dig = normalizar_cep(cep)
    res: dict[str, Any] = {
        "url": url,
        "preco_pix": None,
        "frete_valor": None,
        "prazo": None,
        "total": None,
        "parcelas_qtd": None,
        "parcela_valor": None,
        "preco_parcelado": None,
        "total_parcelado": None,
    }
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3500)
        body = page.locator("body").inner_text()
        m_pix = re.search(r"(R\$\s*[\d\.]+,\d{2})\s*(?:\n|\r|\s)*[ÀA]\s+vista\s+no\s+PIX", body, re.I)
        if m_pix:
            res["preco_pix"] = parse_brl_flex(m_pix.group(1))
        m_parc = re.search(
            r"ou\s+(R\$\s*[\d\.]+,\d{2})\s+em\s+at[ée]\s+(\d+)x\s+de\s+(R\$\s*[\d\.]+,\d{2})\s+sem\s+juros",
            body,
            re.I,
        )
        if m_parc:
            res["preco_parcelado"] = parse_brl_flex(m_parc.group(1))
            res["parcelas_qtd"] = int(m_parc.group(2))
            res["parcela_valor"] = parse_brl_flex(m_parc.group(3))

        try:
            page.evaluate("window.scrollBy(0, 450)")
            page.wait_for_selector("#cepInput, input[placeholder*='CEP' i]", timeout=12000)
            inp = page.locator("#cepInput, input[placeholder*='CEP' i]").first
            inp.scroll_into_view_if_needed()
            inp.fill(dig)
            page.wait_for_timeout(400)
            page.locator("button:has-text('Calcular'), button:has-text('OK')").first.click()
            for _ in range(14):
                page.wait_for_timeout(500)
                ship_txt = page.evaluate("""() => {
                    const inp = document.querySelector('#cepInput') || document.querySelector('input[placeholder*="CEP" i]');
                    let el = inp;
                    for (let i = 0; i < 6 && el; i++) el = el.parentElement;
                    return el ? el.innerText : '';
                }""")
                m_f = re.search(r"(R\$\s*[\d\.]+,\d{2})", ship_txt)
                if m_f:
                    res["frete_valor"] = parse_brl_flex(m_f.group(1))
                    m_p = re.search(r"(\d+\s*dias?\s*[úu]teis)", ship_txt, re.I)
                    if m_p:
                        res["prazo"] = m_p.group(1).strip()
                    break
        except Exception as exc:
            res["erro_frete"] = str(exc)[:120]

        if res["preco_pix"] is not None and res["frete_valor"] is not None:
            res["total"] = round(res["preco_pix"] + res["frete_valor"], 2)
        if res["preco_parcelado"] is not None and res["frete_valor"] is not None:
            res["total_parcelado"] = round(res["preco_parcelado"] + res["frete_valor"], 2)
    except Exception as exc:
        res["erro"] = str(exc)[:180]
    return res


def extrair_ml_ar(page: Any, url: str) -> dict[str, Any]:
    res: dict[str, Any] = {
        "url": url,
        "preco": None,
        "frete_gratis": False,
        "vendedor": None,
        "parcelas_mp_qtd": None,
        "parcelas_mp_valor": None,
        "parcelas_outros_qtd": None,
        "parcelas_outros_valor": None,
    }
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(2800)
        if not page.locator("h1").count():
            res["erro"] = "sem h1 (possivel bloqueio temporario ML)"
            return res
        body = page.locator("body").inner_text()
        # Preco principal exibido perto do titulo / buybox
        m_pr = re.search(r"(?:R\$\s*[\d\.]+(?:,\d{2})?)\s*\n\s*(\d+)x\s*(?:R\$\s*[\d\.]+,\d{2}|de\s*R\$)", body)
        price_el = page.locator(".ui-pdp-price__second-line .andes-money-amount__fraction").first
        if price_el.count():
            cents_el = page.locator(".ui-pdp-price__second-line .andes-money-amount__cents").first
            frac = price_el.inner_text().strip()
            cents = cents_el.inner_text().strip() if cents_el.count() else "00"
            res["preco"] = parse_brl_flex(f"R$ {frac},{cents}")
        elif m_pr:
            res["preco"] = parse_brl_flex(m_pr.group(0))

        m_mp = re.search(
            r"(\d+)x\s*(?:de\s*)?(R\$\s*[\d\.]+,\d{2})\s*sem juros",
            body,
            re.I,
        )
        if m_mp:
            qtd = int(m_mp.group(1))
            val = parse_brl_flex(m_mp.group(2))
            if qtd > 12:
                res["parcelas_mp_qtd"] = qtd
                res["parcelas_mp_valor"] = val
            else:
                res["parcelas_outros_qtd"] = qtd
                res["parcelas_outros_valor"] = val

        m_out = re.search(
            r"em\s+at[ée]\s+(\d+)x\s+de\s+(R\$\s*[\d\.]+,\d{2})\s+sem juros",
            body,
            re.I,
        )
        if m_out:
            res["parcelas_outros_qtd"] = int(m_out.group(1))
            res["parcelas_outros_valor"] = parse_brl_flex(m_out.group(2))

        res["frete_gratis"] = "frete grátis" in body.lower() or "chegará grátis" in body.lower()
        m_vend = re.search(r"Vendido por\s+([^\n]+)", body)
        if m_vend:
            res["vendedor"] = m_vend.group(1).strip()[:40]
    except Exception as exc:
        res["erro"] = str(exc)[:180]
    return res


def _parcela_loja_texto(loja_dict: dict[str, Any]) -> str | None:
    qtd = loja_dict.get("parcelas_qtd")
    val = loja_dict.get("parcela_valor")
    tot = loja_dict.get("total_parcelado") or loja_dict.get("preco_parcelado")
    if not qtd or val is None:
        return None
    if loja_dict.get("frete_valor") and not loja_dict.get("total_parcelado") and tot is not None:
        tot = round(tot + loja_dict["frete_valor"], 2)
    return formatar_parcelas(qtd, val, tot)


def _resumo_ml_18x(ml_data: dict[str, Any] | None) -> tuple[float | None, str | None]:
    if not ml_data or ml_data.get("preco") is None:
        return None, None
    p = ml_data["preco"]
    partes = []
    if ml_data.get("parcelas_mp_qtd") and ml_data.get("parcelas_mp_valor") is not None:
        partes.append(f"{ml_data['parcelas_mp_qtd']}x de {rr.fmt_brl(ml_data['parcelas_mp_valor'])} s/ juros Cartao MP")
    if ml_data.get("parcelas_outros_qtd") and ml_data.get("parcelas_outros_valor") is not None:
        partes.append(f"{ml_data['parcelas_outros_qtd']}x de {rr.fmt_brl(ml_data['parcelas_outros_valor'])} outros")
    frete = "frete gratis" if ml_data.get("frete_gratis") else "checar frete"
    vend = ml_data.get("vendedor") or "ML"
    desc_parc = " / ".join(partes) if partes else "parcelado"
    return p, f"ML ({vend}): *{rr.fmt_brl(p)}* em {desc_parc}, {frete}"


def _escolher_melhor(opcoes: list[tuple[float | None, str, str | None]]) -> tuple[float | None, str, str | None]:
    validas = [(val, desc, parc) for val, desc, parc in opcoes if val is not None]
    if not validas:
        return None, "indisponivel", None
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
            "melhor_parcelamento": _parcela_loja_texto(agratto12_duf),
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
            "melhor_parcelamento": _parcela_loja_texto(midea_lite_duf),
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
            "melhor_parcelamento": _parcela_loja_texto(midea_eco_amz),
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

        elgin18_wc = extrair_webcontinental_ar(p18, "https://www.webcontinental.com.br/010101006l30812222/p", cep_18k)
        elgin18_prom = rr.extrair_promobit(p18, "hjfc18c2whch", r"(?:hjfc18|elgin.*18000)")
        ctx18.close()

        # Contexto dedicado Frigelar
        ctx_frig = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="pt-BR",
            user_agent=rr.USER_AGENT,
        )
        p_frig = ctx_frig.new_page()
        elgin12_frig = extrair_frigelar_ar(
            p_frig,
            "https://www.frigelar.com.br/ar-condicionado-split-inverter-elgin-eco-iii-12000-btus-frio-220v-hjfc12c2wgcg/p/kit20403",
            cep_12k,
        )
        elgin18_frig = extrair_frigelar_ar(
            p_frig,
            "https://www.frigelar.com.br/ar-condicionado-split-inverter-elgin-eco-iii-18000-btus-frio-220v-hjfc18c2whch/p/kit20405",
            cep_18k,
        )
        ctx_frig.close()

        # Contexto dedicado Mercado Livre (18x sem juros)
        ctx_ml = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="pt-BR",
            user_agent=rr.USER_AGENT,
        )
        p_ml = ctx_ml.new_page()
        elgin12_ml = extrair_ml_ar(
            p_ml,
            "https://www.mercadolivre.com.br/ar-condicionado-split-hi-wall-inverter-elgin-eco-iii-wifi-12000-btus-frio-220v/p/MLB62516603",
        )
        p_ml.wait_for_timeout(1200)
        philco18_ml = extrair_ml_ar(
            p_ml,
            "https://www.mercadolivre.com.br/ar-condicionado-split-inverter-philco-18000-btus-frio-220v/p/MLB48269925",
        )
        p_ml.wait_for_timeout(1200)
        elgin18_ml = extrair_ml_ar(
            p_ml,
            "https://www.mercadolivre.com.br/ar-condicionado-split-hi-wall-inverter-elgin-eco-iii-wifi-18000-btus-so-frio-220v/p/MLB54457219",
        )
        ctx_ml.close()

        cand_elgin12 = [
            (
                elgin12_amz.get("total"),
                f"Amazon ({elgin12_amz.get('vendedor') or 'n/d'}, frete {elgin12_amz.get('frete') or 'n/d'})",
                _parcela_loja_texto(elgin12_amz),
            ),
            (
                elgin12_frig.get("total"),
                f"Frigelar ({rr.fmt_brl(elgin12_frig.get('preco_pix'))} + frete {rr.fmt_brl(elgin12_frig.get('frete_valor'))})",
                _parcela_loja_texto(elgin12_frig),
            ),
            (
                elgin12_kbm.get("preco_pix"),
                f"KaBuM Pix s/ frete ({elgin12_kbm.get('vendedor') or 'n/d'})",
                f"10x s/ juros ({rr.fmt_brl(elgin12_kbm.get('preco_10x'))})" if elgin12_kbm.get("preco_10x") else None,
            ),
        ]
        m_elgin12 = _escolher_melhor(cand_elgin12)
        ml12_p, ml12_txt = _resumo_ml_18x(elgin12_ml)
        dados["modelos"]["elgin_12k"] = {
            "nome": BASELINE_18_11["elgin_12k"]["nome"],
            "sku": BASELINE_18_11["elgin_12k"]["sku"],
            "grupo": "12k",
            "amazon": elgin12_amz,
            "frigelar": elgin12_frig,
            "kabum": elgin12_kbm,
            "ml_18x": elgin12_ml,
            "promobit": elgin12_prom,
            "melhor_preco": m_elgin12[0],
            "melhor_onde": m_elgin12[1],
            "melhor_parcelamento": m_elgin12[2],
            "melhor_18x_preco": ml12_p,
            "melhor_18x_txt": ml12_txt,
        }

        cand_philco18 = [
            (
                philco18_amz.get("total"),
                f"Amazon ({philco18_amz.get('vendedor') or 'n/d'}, frete {philco18_amz.get('frete') or 'n/d'})",
                _parcela_loja_texto(philco18_amz),
            ),
            (
                philco18_wc.get("total"),
                f"WebContinental ({rr.fmt_brl(philco18_wc.get('preco_pix'))} + frete {rr.fmt_brl(philco18_wc.get('frete_valor'))})",
                _parcela_loja_texto(philco18_wc),
            ),
        ]
        m_philco18 = _escolher_melhor(cand_philco18)
        ml_p18, ml_p18_txt = _resumo_ml_18x(philco18_ml)
        dados["modelos"]["philco_18k"] = {
            "nome": BASELINE_18_11["philco_18k"]["nome"],
            "sku": BASELINE_18_11["philco_18k"]["sku"],
            "grupo": "18k",
            "amazon": philco18_amz,
            "webcontinental": philco18_wc,
            "ml_18x": philco18_ml,
            "promobit": philco18_prom,
            "melhor_preco": m_philco18[0],
            "melhor_onde": m_philco18[1],
            "melhor_parcelamento": m_philco18[2],
            "melhor_18x_preco": ml_p18,
            "melhor_18x_txt": ml_p18_txt,
        }

        cand_elgin18 = [
            (
                elgin18_frig.get("total"),
                f"Frigelar ({rr.fmt_brl(elgin18_frig.get('preco_pix'))} + frete {rr.fmt_brl(elgin18_frig.get('frete_valor'))})",
                _parcela_loja_texto(elgin18_frig),
            ),
            (
                elgin18_wc.get("total"),
                f"WebContinental ({rr.fmt_brl(elgin18_wc.get('preco_pix'))} + frete {rr.fmt_brl(elgin18_wc.get('frete_valor'))})",
                _parcela_loja_texto(elgin18_wc),
            ),
        ]
        m_elgin18 = _escolher_melhor(cand_elgin18)
        ml_e18, ml_e18_txt = _resumo_ml_18x(elgin18_ml)
        dados["modelos"]["elgin_18k"] = {
            "nome": BASELINE_18_11["elgin_18k"]["nome"],
            "sku": BASELINE_18_11["elgin_18k"]["sku"],
            "grupo": "18k",
            "frigelar": elgin18_frig,
            "webcontinental": elgin18_wc,
            "ml_18x": elgin18_ml,
            "promobit": elgin18_prom,
            "melhor_preco": m_elgin18[0],
            "melhor_onde": m_elgin18[1],
            "melhor_parcelamento": m_elgin18[2],
            "melhor_18x_preco": ml_e18,
            "melhor_18x_txt": ml_e18_txt,
        }
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
                if abs(diff) >= 0.01:
                    icone = "🟢 *BAIXOU*" if diff < 0 else "🔴 *SUBIU*"
                    mudancas.append(
                        f"{icone} *{mod['nome']}:* {rr.fmt_brl(p_ant)} -> *{rr.fmt_brl(p_atu)}* ({mod['melhor_onde']})"
                    )
            else:
                mudancas.append(
                    f"🟡 *{mod['nome']}:* era {rr.fmt_brl(p_ant)}, agora *{rr.fmt_brl(p_atu)}* ({mod['melhor_onde']})"
                )

        p18_ant = ant.get("melhor_18x_preco")
        p18_atu = mod.get("melhor_18x_preco")
        if p18_ant is not None and p18_atu is not None and abs(p18_ant - p18_atu) >= 0.01:
            icone = "🟢 *BAIXOU 18x*" if p18_atu < p18_ant else "🔴 *SUBIU 18x*"
            mudancas.append(
                f"{icone} *{mod['nome']}:* {rr.fmt_brl(p18_ant)} -> *{rr.fmt_brl(p18_atu)}* (ML 18x)"
            )
    return mudancas


def _ordenar_grupo(modelos: dict[str, Any], grupo: str) -> list[tuple[str, dict[str, Any]]]:
    itens = [(k, v) for k, v in modelos.items() if v.get("grupo") == grupo]
    itens.sort(key=lambda kv: (kv[1].get("melhor_preco") is None, kv[1].get("melhor_preco") or 999999.0))
    return itens


def _linha_vencedor_resumo(titulo_grupo: str, mod: dict[str, Any]) -> list[str]:
    out = [
        f"*{titulo_grupo}:* {mod['nome']} (`{mod['sku']}`)",
        f"   💵 A vista: *{rr.fmt_brl(mod.get('melhor_preco'))}* · {mod.get('melhor_onde')}",
    ]
    parc = mod.get("melhor_parcelamento")
    if parc:
        out.append(f"   💳 Parcelado na loja: *{parc}*")
    ml_txt = mod.get("melhor_18x_txt")
    if ml_txt:
        out.append(f"   💳 >12x ({ml_txt})")
    return out


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
    vencedores: dict[str, dict[str, Any]] = {}
    for titulo, grupo in [("🔹 *12.000 BTU (220V, entregue)*", "12k"), ("🔹 *18.000 BTU (220V, entregue)*", "18k")]:
        linhas.append("")
        linhas.append(titulo)
        ordenados = _ordenar_grupo(atual.get("modelos", {}), grupo)
        if ordenados:
            vencedores[grupo] = ordenados[0][1]
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
            if mod.get("melhor_parcelamento"):
                linhas.append(f"💳 {mod['melhor_parcelamento']}")
            if mod.get("melhor_18x_txt"):
                linhas.append(f"💳 {mod['melhor_18x_txt']}")
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
    linhas.append("🏆 *RESUMO DOS 2 VENCEDORES*")
    if "12k" in vencedores:
        linhas.extend(_linha_vencedor_resumo("12.000 BTU", vencedores["12k"]))
    if "18k" in vencedores:
        linhas.extend(_linha_vencedor_resumo("18.000 BTU", vencedores["18k"]))
        elg18 = (atual.get("modelos", {}) or {}).get("elgin_18k") or {}
        if elg18.get("melhor_18x_txt") and vencedores["18k"].get("sku") != elg18.get("sku"):
            linhas.append(f"   🔄 Alt. 18k Elgin (`HJFC18C2WHCH`): {rr.fmt_brl(elg18.get('melhor_preco'))} a vista · {elg18['melhor_18x_txt']}")

    linhas.append("")
    linhas.append(f"⏰ Proxima checagem: *{rr.proxima_checagem()}*")

    if primeira_vez:
        linhas.append("")
        linhas.append(
            "💡 *Obs:* Shopee/Casas Bahia bloqueiam busca automatica e TikTok Shop busca so no app (conferir manual no celular)."
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
