"""Rastreador diario de precos dos robos aspiradores (4 no Brasil + S40 Pro Paraguai).

Coleta precos e cupons em fontes publicas (Amazon, KaBuM, Zoom, Promobit e
Compras Paraguai), compara com a rodada anterior e com a referencia inicial,
salva historico fora do Git (~/.central-compras/dados-privados/rastreador-robos/)
e opcionalmente envia o resumo pelo WhatsApp das IAs (nav-zap, CDP 9230).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

_RAIZ_REPO = Path(__file__).resolve().parents[1]
if str(_RAIZ_REPO) not in sys.path:
    sys.path.insert(0, str(_RAIZ_REPO))
from radar import ciclo, correcoes, trava  # noqa: E402

PRIVADO_DIR = Path.home() / ".central-compras" / "dados-privados" / "rastreador-robos"
CONFIG_PATH = PRIVADO_DIR / "config.json"
ESTADO_PATH = PRIVADO_DIR / "estado.json"
HIST_PATH = PRIVADO_DIR / "historico.jsonl"
ZAP_VIVO_JS = Path(r"C:\projetos\skills-pessoais\zap-vivo.mjs")
CDP_URL = "http://127.0.0.1:9230"

BASELINE_14_11 = {
    "dreame_f10": {"nome": "Dreame F10", "preco": 1102.00, "nota": "Amazon (Dreame Ltda)"},
    "k800_pro_127v": {"nome": "KaBuM K800 Pro 127V", "preco": 1199.99, "nota": "KaBuM Pix"},
    "tapo_rv20_max": {"nome": "Tapo RV20 Max", "preco": 854.05, "nota": "Amazon (TNTinfoLoja)"},
    "xiaomi_s40c": {"nome": "Xiaomi S40C", "preco": 912.63, "nota": "ML (urbantechcia)"},
    "xiaomi_s40_pro_py": {
        "nome": "Xiaomi S40 Pro (Paraguai)",
        "preco": 1327.50,
        "ref_label": "19/11",
        "nota": "Compras PY US$ 225,00 (lojas CDE)",
    },
    "xiaomi_s40_pro_br": {
        "nome": "Xiaomi S40 Pro (Brasil)",
        "preco": 1870.00,
        "ref_label": "26/11",
        "nota": "ML Pix (vitrine) / Amazon R$ 1.935,15",
    },
}

LOJAS_GRANDES_PY = (
    "madrid center",
    "mega eletronicos",
    "mega eletrônicos",
    "nissei",
    "shopping china",
    "cellshop",
    "new zone",
    "atacado connect",
)

CP_S40_PRO_URL = "https://www.comprasparaguai.com.br/robo-de-limpeza-xiaomi-robot-vacuum-s40-pro-bivolt_66296/"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def parse_brl(texto: str) -> float | None:
    m = re.search(r"R\$\s*([\d\.]+,\d{2})", texto or "")
    if not m:
        return None
    val = m.group(1).replace(".", "").replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return None


def fmt_brl(val: float | None) -> str:
    if val is None:
        return "indisponivel"
    s = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def parse_usd(texto: str) -> float | None:
    m = re.search(r"US\$\s*([\d\.]+,\d{2})", texto or "")
    if not m:
        return None
    val = m.group(1).replace(".", "").replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return None


def fmt_usd(val: float | None) -> str:
    if val is None:
        return "US$ n/d"
    s = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"US$ {s}"


def extrair_amazon(page: Any, url: str) -> dict[str, Any]:
    res: dict[str, Any] = {"url": url, "preco": None, "frete": None, "vendedor": None, "cupons": [], "estoque": None}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(2200)
        buybox_txt = page.locator("#desktop_buybox").inner_text() if page.locator("#desktop_buybox").count() else ""
        core_txt = page.locator("#corePrice_feature_div").first.inner_text() if page.locator("#corePrice_feature_div").count() else ""
        preco = parse_brl(core_txt) or parse_brl(buybox_txt)
        vendedor = None
        if "Vendido por" in buybox_txt:
            m = re.search(r"Vendido por\s*\n?\s*([^\n]+)", buybox_txt)
            if m:
                vendedor = m.group(1).lstrip(": ").strip()
        elif "Enviado / Vendido" in buybox_txt:
            m = re.search(r"Enviado / Vendido\s*\n?\s*([^\n]+)", buybox_txt)
            if m:
                vendedor = m.group(1).lstrip(": ").strip()

        promo_texts = page.locator(
            "#promoPriceBlockMessage_feature_div, #couponBadgeRegularVpc, .promoPriceBlockMessage"
        ).all_inner_texts()
        cupons = sorted(set(re.findall(r"\b(?:[A-Z0-9]{4,14})\b", " ".join(promo_texts))))
        cupons = [
            c
            for c in cupons
            if not c.isdigit() and (any(ch.isdigit() for ch in c) or "BF" in c or "OFF" in c or "PRIME" in c)
        ]

        # Se nao houver preco no buybox principal, abre "Ver todas as opcoes de compra" (AOD)
        if preco is None and page.locator("#buybox-see-all-buying-choices a").count():
            page.locator("#buybox-see-all-buying-choices a").first.click()
            page.wait_for_timeout(2500)
            if page.locator("#aod-offer-list").count():
                aod_txt = page.locator("#aod-offer-list").inner_text()
                preco = parse_brl(aod_txt)
                m_vend = re.search(r"Vendido por\s*\n?\s*([^\n]+)", aod_txt)
                if m_vend:
                    vendedor = m_vend.group(1).strip()
                m_frete = re.search(r"Entrega\s+(GRÁTIS|R\$\s*[\d\.]+,\d{2})", aod_txt)
                if m_frete:
                    res["frete"] = m_frete.group(1).strip()

        if res["frete"] is None:
            if "Entrega GRÁTIS" in buybox_txt:
                res["frete"] = "Gratis"
            else:
                mf = re.search(r"Entrega\s+(R\$\s*[\d\.]+,\d{2})", buybox_txt)
                if mf:
                    res["frete"] = mf.group(1).strip()

        if "Em estoque" in buybox_txt:
            res["estoque"] = "Em estoque"
        else:
            me = re.search(r"Somente \d+ em estoque", buybox_txt)
            if me:
                res["estoque"] = me.group(0)

        res["preco"] = preco
        res["vendedor"] = vendedor
        res["cupons"] = cupons
    except Exception as exc:
        res["erro"] = str(exc)[:180]
    return res


def extrair_kabum(page: Any, url: str) -> dict[str, Any]:
    res: dict[str, Any] = {"url": url, "preco_pix": None, "preco_10x": None, "vendedor": None, "cupom": None, "disponivel": None}
    try:
        page.goto(url, wait_until="load", timeout=25000)
        page.wait_for_timeout(2500)
        next_data = page.evaluate("""() => {
            const el = document.querySelector('#__NEXT_DATA__');
            let prod = null;
            if (el) {
                const d = JSON.parse(el.textContent);
                const p = d?.props?.pageProps?.product;
                if (p) {
                    prod = {
                        available: p.available,
                        price: p.price,
                        sellerName: p.sellerName,
                        offer: p.offer || null
                    };
                }
            }
            let pixValue = null;
            const nf = document.querySelector('number-flow-react');
            if (nf) {
                try {
                    const dataAttr = JSON.parse(nf.getAttribute('data') || '{}');
                    if (typeof dataAttr.value === 'number') pixValue = dataAttr.value;
                } catch {}
            }
            return { prod, pixValue };
        }""")
        body = page.inner_text("body")
        cupom = None
        m_cup = re.search(r"Use o cupom\s+([A-Z0-9]+)", body)
        if m_cup:
            cupom = m_cup.group(1)
        else:
            m_cup2 = re.search(r"CUPOM\s*\n\s*([A-Z0-9]{4,20})", body)
            if m_cup2:
                cupom = m_cup2.group(1)

        prod = next_data.get("prod") if next_data else None
        pix_val = next_data.get("pixValue") if next_data else None
        if prod:
            res["disponivel"] = bool(prod.get("available"))
            res["preco_10x"] = prod.get("price")
            res["vendedor"] = prod.get("sellerName")
            if isinstance(prod.get("offer"), dict):
                res["estoque_oferta"] = prod["offer"].get("quantity")
        res["preco_pix"] = pix_val or (prod.get("price") if prod else None)
        res["cupom"] = cupom
    except Exception as exc:
        res["erro"] = str(exc)[:180]
    return res


def extrair_zoom(page: Any, url: str) -> dict[str, Any]:
    res: dict[str, Any] = {"url": url, "menor_preco": None, "loja": None}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.inner_text("body")
        m = re.search(
            r"Menor preço.*?R\$\s*([\d\.]+,\d{2})à vista.*?(?:Ir à loja|Comprar)\s*\|\s*|Menor preço\s*\n(?:[^\n]*\n){0,4}?R\$\s*([\d\.]+,\d{2})",
            body,
        )
        m2 = re.search(r"Menor preço[\s\S]{0,200}?R\$\s*([\d\.]+,\d{2})à vista([\s\S]{0,160}?)(?:Ir à loja|Comprar)", body)
        if m2:
            res["menor_preco"] = parse_brl("R$ " + m2.group(1))
            tail = [l.strip() for l in m2.group(2).splitlines() if l.strip()]
            if tail:
                res["loja"] = tail[-1]
        elif m:
            raw = m.group(1) or m.group(2)
            res["menor_preco"] = parse_brl("R$ " + raw)
    except Exception as exc:
        res["erro"] = str(exc)[:180]
    return res


def extrair_promobit(page: Any, query: str, termo_filtro: str) -> list[dict[str, Any]]:
    ofertas: list[dict[str, Any]] = []
    try:
        url = f"https://www.promobit.com.br/buscar/?q={query}"
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1800)
        raw_items = page.evaluate(
            """(kw) => {
            const out = [];
            const re = new RegExp(kw, 'i');
            for (const a of document.querySelectorAll('a[href*="/oferta/"]')) {
                let node = a;
                for (let step = 0; step < 4 && node.parentElement; step++) {
                    const t = (node.parentElement.innerText || '').trim();
                    if (t.length > 360) break;
                    node = node.parentElement;
                }
                const txt = (node.innerText || a.innerText || '').replace(/\\s+/g, ' ').trim();
                if (!re.test(txt) && !re.test(a.href)) continue;
                out.push({ href: a.href, text: txt.slice(0, 260) });
            }
            return out;
        }""",
            termo_filtro,
        )
        seen = set()
        for it in raw_items:
            if it["href"] in seen:
                continue
            seen.add(it["href"])
            precos_raw = re.findall(r"R\$\s*([\d\.]+,\d{2})", it["text"])
            precos = [parse_brl("R$ " + p_str) for p_str in precos_raw]
            precos_validos = [pv for pv in precos if pv is not None]
            preco = min(precos_validos) if precos_validos else None
            ofertas.append({"href": it["href"], "preco": preco, "texto": it["text"][:180]})
            if len(ofertas) >= 3:
                break
    except Exception as exc:
        ofertas.append({"erro": str(exc)[:150]})
    return ofertas


def _resumir_ofertas_cp(
    ofertas_raw: list[dict[str, Any]],
    dolar_hoje: float | None = None,
) -> dict[str, Any]:
    """Normaliza e seleciona menor oferta nova, geral e das grandes lojas CDE."""
    ofertas: list[dict[str, Any]] = []
    for item in ofertas_raw:
        texto = item.get("text") or ""
        loja = (item.get("loja") or "").strip() or "loja n/d"
        usd = parse_usd(texto)
        brl = parse_brl(texto)
        if brl is None and usd is not None and dolar_hoje is not None:
            brl = round(usd * dolar_hoje, 2)
        if brl is None:
            continue
        avaria = bool(
            re.search(
                r"recondicionad|refurbished|usad[oa]|vitrine|caixa\s*(feia|danificada)",
                texto,
                re.I,
            )
        )
        ofertas.append(
            {
                "loja": loja,
                "preco_usd": usd,
                "preco_brl": brl,
                "avaria_ou_recond": avaria,
                "titulo": texto.split("Código:")[0].strip()[:120],
            }
        )

    novas = [o for o in ofertas if not o["avaria_ou_recond"]]
    grandes = [o for o in novas if o["loja"].lower() in LOJAS_GRANDES_PY]
    return {
        "qtd_ofertas": len(ofertas),
        "menor_novo": min(novas, key=lambda o: o["preco_brl"]) if novas else None,
        "menor_geral": min(ofertas, key=lambda o: o["preco_brl"]) if ofertas else None,
        "menor_grandes": min(grandes, key=lambda o: o["preco_brl"]) if grandes else None,
    }


def extrair_compras_paraguai(page: Any, url: str) -> dict[str, Any]:
    """Coleta cotacoes no Compras Paraguai (dolar, menor novo, recondicionado e grandes lojas)."""
    res: dict[str, Any] = {
        "url": url,
        "dolar_hoje": None,
        "qtd_ofertas": 0,
        "menor_novo": None,
        "menor_geral": None,
        "menor_grandes": None,
    }
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(2500)
        body = page.inner_text("body")
        m_dol = re.search(r"Dólar hoje:\s*\n?\s*R\$\s*([\d\.]+,\d{2})", body)
        dolar_hoje = parse_brl("R$ " + m_dol.group(1)) if m_dol else None
        raw = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('.promocao-produtos-item.tem-linha-de-acoes').forEach(el => {
                const text = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                const imgs = Array.from(el.querySelectorAll('img')).map(i => i.alt || i.title || '').filter(Boolean);
                const loja = imgs.length ? imgs[imgs.length - 1] : '';
                out.push({loja, text});
            });
            return out;
        }""")
        resumo = _resumir_ofertas_cp(raw or [], dolar_hoje=dolar_hoje)
        res["dolar_hoje"] = dolar_hoje
        res.update(resumo)
    except Exception as exc:
        res["erro"] = str(exc)[:180]
    return res


def extrair_ml_vitrine_s40_pro(page: Any) -> dict[str, Any]:
    """Coleta menor preco a vista/Pix do Xiaomi S40 Pro na vitrine publica do ML (sem quebrar se o ML pedir login)."""
    res: dict[str, Any] = {"url": "https://meli.la/2xCjJ3p", "preco": None}
    try:
        page.goto(res["url"], wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        textos = page.evaluate("""() => {
            const sels = ['.poly-card', '.ui-recommendations-card', '.andes-card', 'li', 'article'];
            const out = [];
            for (const sel of sels) {
                document.querySelectorAll(sel).forEach(el => {
                    const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                    if (t.length >= 30 && t.length <= 500 && /s40\\s*pro/i.test(t)) out.push(t);
                });
                if (out.length) break;
            }
            return out;
        }""")
        precos_cards: list[float] = []
        for txt in textos or []:
            if re.search(r"s40c|10\.?000\s*pa|filtro|escova|pano|refil|kit|acess[oó]rio", txt, re.I):
                continue
            # Extrai valores com ou sem centavos ("R$ 1.870" ou "R$ 1.870,00"), ignorando parcelas (< 950)
            brutos = re.findall(r"R\$\s*([\d\.]+(?:,\d{2})?)", txt)
            candidatos_card: list[float] = []
            for b in brutos:
                s = b.replace(".", "").replace(",", ".")
                try:
                    v = float(s)
                except ValueError:
                    continue
                if 950.0 <= v <= 4500.0:
                    candidatos_card.append(v)
            if candidatos_card:
                precos_cards.append(min(candidatos_card))
        if precos_cards:
            res["preco"] = min(precos_cards)
    except Exception as exc:
        # Usa chave `aviso_ml` em vez de `erro` para bloqueio/timeout do ML nao marcar a rodada inteira como degradada
        res["aviso_ml"] = str(exc)[:140]
    return res


def coletar_precos() -> dict[str, Any]:
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
            user_agent=USER_AGENT,
        )
        page = ctx.new_page()

        # 1. Dreame F10
        f10_amz = extrair_amazon(page, "https://www.amazon.com.br/dp/B0GYZ4NHB3")
        f10_prom = extrair_promobit(page, "dreame+f10", r"dreame\s*f10")
        dados["modelos"]["dreame_f10"] = {
            "nome": "Dreame F10",
            "amazon": f10_amz,
            "promobit": f10_prom,
            "melhor_preco": f10_amz.get("preco"),
            "melhor_onde": f"Amazon ({f10_amz.get('vendedor') or 'n/d'})",
        }

        # 2. KaBuM K800 Pro 127V
        k800_preto = extrair_kabum(
            page,
            "https://www.kabum.com.br/produto/1007406/robo-aspirador-kabum-smart-k800-pro-mapeamento-laser-autolimpante-13000pa-127v-preto-ksar81010pt",
        )
        k800_branco = extrair_kabum(
            page,
            "https://www.kabum.com.br/produto/1007407/robo-aspirador-e-passa-pano-kabum-smart-k800-pro-mapeia-a-laser-autolimpante-recarga-automatica-13000pa-app-127v-branco-ksar81010br",
        )
        k800_amz = extrair_amazon(page, "https://www.amazon.com.br/dp/B0HCZVJ6M1")
        k800_prom = extrair_promobit(page, "k800+pro", r"k800\s*pro")
        cand_k800 = []
        if k800_preto.get("preco_pix"):
            cand_k800.append((k800_preto["preco_pix"], f"KaBuM Preto 127V Pix (cupom {k800_preto.get('cupom') or 'sem'})"))
        if k800_branco.get("preco_pix"):
            cand_k800.append((k800_branco["preco_pix"], f"KaBuM Branco 127V Pix (cupom {k800_branco.get('cupom') or 'sem'})"))
        if k800_amz.get("preco"):
            frete_amz = parse_brl(k800_amz.get("frete") or "") or 0.0
            cand_k800.append((k800_amz["preco"] + frete_amz, f"Amazon 127V ({k800_amz.get('vendedor') or 'n/d'} + frete {k800_amz.get('frete') or 'n/d'})"))
        melhor_k800 = min(cand_k800, key=lambda x: x[0]) if cand_k800 else (None, "indisponivel")
        dados["modelos"]["k800_pro_127v"] = {
            "nome": "KaBuM K800 Pro 127V",
            "kabum_preto": k800_preto,
            "kabum_branco": k800_branco,
            "amazon_127v": k800_amz,
            "promobit": k800_prom,
            "melhor_preco": melhor_k800[0],
            "melhor_onde": melhor_k800[1],
        }

        # 3. Tapo RV20 Max
        tapo_amz = extrair_amazon(page, "https://www.amazon.com.br/dp/B0DQYJRS5R")
        tapo_kbm = extrair_kabum(
            page,
            "https://www.kabum.com.br/produto/885340/robo-aspirador-de-po-e-mop-tp-link-tapo-rv20-max-aspira-passa-pano-hiper-succao-smart-bivolt-preto",
        )
        tapo_zoom = extrair_zoom(page, "https://www.zoom.com.br/aspirador-po-agua/aspirador-de-po-portatil-robo-tp-link")
        cand_tapo = []
        if tapo_amz.get("preco"):
            cand_tapo.append((tapo_amz["preco"], f"Amazon ({tapo_amz.get('vendedor') or 'n/d'})"))
        if tapo_kbm.get("preco_pix"):
            cand_tapo.append((tapo_kbm["preco_pix"], f"KaBuM ({tapo_kbm.get('vendedor') or 'n/d'})"))
        melhor_tapo = min(cand_tapo, key=lambda x: x[0]) if cand_tapo else (None, "indisponivel")
        dados["modelos"]["tapo_rv20_max"] = {
            "nome": "Tapo RV20 Max",
            "amazon": tapo_amz,
            "kabum": tapo_kbm,
            "zoom": tapo_zoom,
            "melhor_preco": melhor_tapo[0],
            "melhor_onde": melhor_tapo[1],
        }

        # 4. Xiaomi S40C
        s40c_amz = extrair_amazon(page, "https://www.amazon.com.br/dp/B0F4K1H6X5")
        s40c_kbm = extrair_kabum(
            page,
            "https://www.kabum.com.br/produto/1047128/robo-aspirador-xiaomi-robot-vacuum-s40c-e101-520-ml-com-30-watts-bivolt-branco",
        )
        s40c_zoom = extrair_zoom(page, "https://www.zoom.com.br/aspirador-po-agua/robo-aspirador-xiaomi-s40c-robot-5000pa-mop-smart")
        cand_s40c = []
        if s40c_amz.get("preco"):
            cand_s40c.append((s40c_amz["preco"], f"Amazon ({s40c_amz.get('vendedor') or 'n/d'})"))
        if s40c_kbm.get("preco_pix"):
            cand_s40c.append((s40c_kbm["preco_pix"], f"KaBuM ({s40c_kbm.get('vendedor') or 'n/d'})"))
        if s40c_zoom.get("menor_preco"):
            cand_s40c.append((s40c_zoom["menor_preco"], f"Zoom/{s40c_zoom.get('loja') or 'loja'}"))
        melhor_s40c = min(cand_s40c, key=lambda x: x[0]) if cand_s40c else (None, "indisponivel")
        dados["modelos"]["xiaomi_s40c"] = {
            "nome": "Xiaomi S40C",
            "amazon": s40c_amz,
            "kabum": s40c_kbm,
            "zoom": s40c_zoom,
            "melhor_preco": melhor_s40c[0],
            "melhor_onde": melhor_s40c[1],
        }

        # 5. Xiaomi S40 Pro (Paraguai)
        s40p_cp = extrair_compras_paraguai(page, CP_S40_PRO_URL)
        melhor_cp = s40p_cp.get("menor_novo") or s40p_cp.get("menor_geral")
        if melhor_cp:
            onde_cp = f"Compras PY/{melhor_cp['loja']} ({fmt_usd(melhor_cp.get('preco_usd'))})"
            if melhor_cp.get("avaria_ou_recond"):
                onde_cp += " [recond.]"
            preco_cp = melhor_cp.get("preco_brl")
        else:
            onde_cp = "indisponivel"
            preco_cp = None
        dados["modelos"]["xiaomi_s40_pro_py"] = {
            "nome": "Xiaomi S40 Pro (Paraguai)",
            "compras_paraguai": s40p_cp,
            "melhor_preco": preco_cp,
            "melhor_onde": onde_cp,
        }

        # 6. Xiaomi S40 Pro (Brasil)
        s40p_amz = extrair_amazon(page, "https://www.amazon.com.br/dp/B0FD9CXF2W")
        s40p_kbm = extrair_kabum(
            page,
            "https://www.kabum.com.br/produto/1069144/robo-de-limpeza-xiaomi-robot-vacuum-s40-pro-bivolt",
        )
        s40p_ml = extrair_ml_vitrine_s40_pro(page)
        s40p_prom = [
            pr
            for pr in extrair_promobit(page, "xiaomi+s40+pro", r"s40\s*pro")
            if not re.search(r"s40c|10\.?000\s*pa", pr.get("texto") or "", re.I)
        ]
        cand_s40p_br: list[tuple[float, str]] = []
        if s40p_ml.get("preco"):
            cand_s40p_br.append((s40p_ml["preco"], "Mercado Livre (Pix)"))
        if s40p_amz.get("preco"):
            frete_s40p = parse_brl(s40p_amz.get("frete") or "") or 0.0
            cand_s40p_br.append(
                (
                    round(s40p_amz["preco"] + frete_s40p, 2),
                    f"Amazon ({s40p_amz.get('vendedor') or 'n/d'} + frete {s40p_amz.get('frete') or 'n/d'})",
                )
            )
        if s40p_kbm.get("disponivel") and s40p_kbm.get("preco_pix"):
            cand_s40p_br.append((s40p_kbm["preco_pix"], f"KaBuM ({s40p_kbm.get('vendedor') or 'n/d'})"))
        melhor_s40p_br = min(cand_s40p_br, key=lambda x: x[0]) if cand_s40p_br else (None, "indisponivel")
        dados["modelos"]["xiaomi_s40_pro_br"] = {
            "nome": "Xiaomi S40 Pro (Brasil)",
            "amazon": s40p_amz,
            "kabum": s40p_kbm,
            "ml_vitrine": s40p_ml,
            "promobit": s40p_prom,
            "melhor_preco": melhor_s40p_br[0],
            "melhor_onde": melhor_s40p_br[1],
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
                icone = "🟢 *BAIXOU*" if diff < 0 else "🔴 *SUBIU*"
                mudancas.append(
                    f"{icone} *{mod['nome']}:* {fmt_brl(p_ant)} -> *{fmt_brl(p_atu)}* ({mod['melhor_onde']})"
                )
            else:
                mudancas.append(
                    f"🟡 *{mod['nome']}:* era {fmt_brl(p_ant)}, agora *{fmt_brl(p_atu)}* ({mod['melhor_onde']})"
                )
        if key == "k800_pro_127v":
            cup_ant = (ant.get("kabum_preto") or {}).get("cupom")
            cup_atu = (mod.get("kabum_preto") or {}).get("cupom")
            if cup_ant != cup_atu:
                mudancas.append(f"🏷️ *K800 Pro cupom mudou:* {cup_ant or 'nenhum'} -> *{cup_atu or 'nenhum'}*")
    return mudancas


def periodo_dia() -> str:
    h = dt.datetime.now().hour
    if h < 12:
        return "Manha"
    if h < 18:
        return "Tarde"
    return "Noite"


def proxima_checagem() -> str:
    h = dt.datetime.now().hour
    if h < 8:
        return "08:00"
    if h < 14:
        return "14:00"
    if h < 20:
        return "20:00"
    return "08:00 de amanha"


def carregar_historico_jsonl(hist_path: Path) -> list[dict[str, Any]]:
    """Carrega registros validos de um arquivo historico.jsonl."""
    if not hist_path.exists():
        return []
    registros: list[dict[str, Any]] = []
    for linha in hist_path.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            registros.append(json.loads(linha))
        except Exception:
            continue
    # Leituras sabidamente erradas sao corrigidas em memoria (config/radar_correcoes.yaml);
    # o arquivo do historico segue intacto.
    return correcoes.aplicar(registros, hist_path.parent.name)


def calcular_extremos_historico(
    historico: list[dict[str, Any]],
    atual: dict[str, Any],
    key: str,
    baseline_preco: float | None = None,
) -> tuple[float | None, float | None]:
    """Retorna (menor_preco, maior_preco) ja registrados para o item."""
    precos: list[float] = []
    if baseline_preco is not None:
        precos.append(float(baseline_preco))
    for reg in historico:
        p = ((reg.get("modelos") or {}).get(key) or {}).get("melhor_preco")
        if p is not None:
            precos.append(float(p))
    p_atual = ((atual.get("modelos") or {}).get(key) or {}).get("melhor_preco")
    if p_atual is not None:
        precos.append(float(p_atual))
    if not precos:
        return None, None
    return min(precos), max(precos)


def formatar_comparacao_extremos(
    preco_atual: float | None,
    menor: float | None,
    maior: float | None,
) -> str:
    """Formata a comparacao do preco atual com o menor e o maior ja registrados."""
    if menor is None or maior is None:
        return "Hist.: sem registros"
    base_txt = f"Hist.: menor *{fmt_brl(menor)}* · maior *{fmt_brl(maior)}*"
    if preco_atual is None:
        return base_txt
    if abs(maior - menor) < 0.01:
        return f"{base_txt} (estavel)"
    diff_min = preco_atual - menor
    diff_max = maior - preco_atual
    parte_min = "no menor preco" if diff_min < 0.01 else f"+{fmt_brl(diff_min)} vs menor"
    parte_max = "no maior preco" if diff_max < 0.01 else f"-{fmt_brl(diff_max)} vs maior"
    return f"{base_txt} ({parte_min} | {parte_max})"


def montar_mensagem(
    atual: dict[str, Any],
    anterior: dict[str, Any] | None,
    primeira_vez: bool = False,
    historico: list[dict[str, Any]] | None = None,
) -> str:
    agora_fmt = dt.datetime.strptime(atual["coletado_em"], "%Y-%m-%d %H:%M").strftime("%d/%m %H:%M")
    mudancas = detectar_alteracoes(atual, anterior)
    hist = historico if historico is not None else carregar_historico_jsonl(HIST_PATH)

    linhas = [f"🤖 *RASTREIO ROBOS • {periodo_dia().upper()} ({agora_fmt})*", ""]

    if anterior is None:
        linhas.append("📌 *Primeira checagem* (base 14/11)")
    elif not mudancas:
        ant_fmt = dt.datetime.strptime(anterior["coletado_em"], "%Y-%m-%d %H:%M").strftime("%d/%m %H:%M")
        linhas.append(f"✅ *Sem alteracoes* desde {ant_fmt}")
    else:
        ant_fmt = dt.datetime.strptime(anterior["coletado_em"], "%Y-%m-%d %H:%M").strftime("%d/%m %H:%M")
        linhas.append(f"🚨 *ALTEROU DESDE {ant_fmt}:*")
        linhas.extend(mudancas)

    ordem = [
        ("dreame_f10", "🥇"),
        ("k800_pro_127v", "🥈"),
        ("tapo_rv20_max", "🥉"),
        ("xiaomi_s40c", "4️⃣"),
        ("xiaomi_s40_pro_py", "5️⃣"),
        ("xiaomi_s40_pro_br", "6️⃣"),
    ]
    resumo_itens: list[tuple[float, str, float | None, float | None, float | None]] = []
    for key, medalha in ordem:
        mod = atual.get("modelos", {}).get(key)
        if not mod:
            continue
        base_info = BASELINE_14_11[key]
        base = base_info["preco"]
        ref_label = base_info.get("ref_label", "14/11")
        p = mod.get("melhor_preco")
        onde = mod.get("melhor_onde")
        menor, maior = calcular_extremos_historico(hist, atual, key, baseline_preco=base)
        comp_extremos = formatar_comparacao_extremos(p, menor, maior)
        resumo_itens.append((p if p is not None else 999999.0, mod["nome"], p, menor, maior))

        if p is None:
            bola = "⚪"
            comp = f"ref {ref_label} {fmt_brl(base)}"
        else:
            diff_base = p - base
            if abs(diff_base) < 0.50:
                bola = "🟢"
                comp = f"igual a {ref_label}"
            elif diff_base < 0:
                bola = "🟢"
                comp = f"*{fmt_brl(abs(diff_base))} mais barato* que {ref_label} (era {fmt_brl(base)})"
            else:
                bola = "🔴"
                comp = f"+{fmt_brl(diff_base)} vs {ref_label} (era {fmt_brl(base)})"

        linhas.append("")
        linhas.append(f"{medalha} *{mod['nome']}*")
        linhas.append(f"{bola} *{fmt_brl(p)}* · {onde}")
        linhas.append(f"📊 {comp}")
        linhas.append(f"📈 {comp_extremos}")

        if key == "dreame_f10":
            proms = [pr for pr in mod.get("promobit", []) if pr.get("preco")]
            if proms:
                p0 = proms[0]
                linhas.append(f"🔥 Alerta Promobit: *{fmt_brl(p0['preco'])}* (checar se ativo)")
        elif key == "k800_pro_127v":
            cup = (mod.get("kabum_preto") or {}).get("cupom")
            if cup == "CASATECH10" and p:
                linhas.append(f"🏷️ Cupom *{cup}* (10%): *~{fmt_brl(p * 0.90)}*")
        elif key == "tapo_rv20_max":
            cupons = (mod.get("amazon") or {}).get("cupons") or []
            if cupons:
                linhas.append(f"🏷️ Cupons na pagina: *{' · '.join(cupons[:3])}*")
        elif key == "xiaomi_s40_pro_py":
            cp = mod.get("compras_paraguai") or {}
            detalhes_cp: list[str] = []
            if cp.get("dolar_hoje"):
                detalhes_cp.append(f"Dolar CP: {fmt_brl(cp['dolar_hoje'])}")
            if cp.get("qtd_ofertas"):
                detalhes_cp.append(f"{cp['qtd_ofertas']} ofertas")
            mg = cp.get("menor_grandes")
            if mg and mg.get("preco_brl") and mg.get("preco_brl") != p:
                detalhes_cp.append(
                    f"Grandes CDE: *{fmt_brl(mg['preco_brl'])}* ({mg['loja']} · {fmt_usd(mg.get('preco_usd'))})"
                )
            mger = cp.get("menor_geral")
            if mger and mger.get("avaria_ou_recond") and mger.get("preco_brl") and (p is None or mger["preco_brl"] < p):
                detalhes_cp.append(
                    f"Recond.: {fmt_brl(mger['preco_brl'])} ({mger['loja']} · {fmt_usd(mger.get('preco_usd'))})"
                )
            if detalhes_cp:
                linhas.append("💱 " + " · ".join(detalhes_cp))
        elif key == "xiaomi_s40_pro_br":
            outras: list[str] = []
            amz = mod.get("amazon") or {}
            ml = mod.get("ml_vitrine") or {}
            if amz.get("preco") and "Amazon" not in (onde or ""):
                outras.append(f"Amazon: {fmt_brl(amz['preco'])} ({amz.get('vendedor') or 'n/d'})")
            elif ml.get("preco") and "Mercado Livre" not in (onde or ""):
                outras.append(f"Mercado Livre: {fmt_brl(ml['preco'])}")
            if outras:
                linhas.append("🏪 Outras lojas: " + " | ".join(outras))
            proms = [pr for pr in mod.get("promobit", []) if pr.get("preco")]
            if proms:
                p0 = proms[0]
                linhas.append(f"🔥 Alerta Promobit: *{fmt_brl(p0['preco'])}* (checar se ativo)")

    linhas.append("")
    linhas.append("🏆 *RESUMO (MENOR / MAIOR HISTORICO)*")
    for _, nome, p, menor, maior in sorted(resumo_itens, key=lambda item: item[0]):
        linhas.append(f"• *{nome}:* *{fmt_brl(p)}* | {formatar_comparacao_extremos(p, menor, maior)}")

    linhas.append("")
    linhas.append(f"⏰ Proxima checagem: *{proxima_checagem()}*")

    if primeira_vez:
        linhas.append("")
        linhas.append("💡 *Pre-Black Friday (27/11):* vale esperar pelos 3 que subiram ou tem cupom (Dreame F10, K800 Pro 127V e S40C). So o Tapo RV20 Max ja esta no piso de 40 dias.")

    return "\n".join(linhas)


def garantir_zap_vivo() -> None:
    if ZAP_VIVO_JS.exists():
        subprocess.run(["node", str(ZAP_VIVO_JS), "josemardp"], check=False, timeout=90)


def carregar_destino_config() -> str | None:
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return cfg.get("chat_title")
        except Exception:
            return None
    return None


def _enviar_uma_vez(linhas: list[str]) -> tuple[bool, str]:
    """Uma tentativa de envio pela aba do WhatsApp Web. So aperta Enter com o texto conferido."""
    norm = lambda x: x.replace("*", "").strip()

    with sync_playwright() as p:
        br = p.chromium.connect_over_cdp(CDP_URL)
        pg = next((x for c in br.contexts for x in c.pages if "web.whatsapp.com" in x.url), None)
        if pg is None:
            return False, "Aba web.whatsapp.com nao encontrada na porta 9230."

        destino = carregar_destino_config()
        if not destino:
            wid = pg.evaluate("() => localStorage.getItem('last-wid-md')")
            if wid:
                num = re.sub(r"\D", "", wid.split(":")[0])
                if len(num) == 13 and num.startswith("55"):
                    destino = f"+{num[:2]} {num[2:4]} {num[4:9]}-{num[9:]}"
        if not destino:
            return False, "Titulo do chat proprio nao configurado nem detectado."

        titulo_atual = lambda: (
            pg.locator("#main header").inner_text().split("\n")[0].strip()
            if pg.locator("#main header").count()
            else ""
        )

        if titulo_atual() != destino:
            busca = pg.locator('#side input[role="textbox"]').first
            busca.click()
            pg.keyboard.press("Control+A")
            pg.keyboard.press("Backspace")
            pg.keyboard.insert_text(destino)
            time.sleep(2.0)

            alvo = pg.locator(f'#pane-side span[title="{destino}"]')
            if not alvo.count():
                # Fallback pelo final do numero sem formatacao
                digitos = re.sub(r"\D", "", destino)[-4:]
                busca.click()
                pg.keyboard.press("Control+A")
                pg.keyboard.press("Backspace")
                pg.keyboard.insert_text(digitos)
                time.sleep(2.0)
                alvo = pg.locator(f'#pane-side span[title="{destino}"]')
            if not alvo.count():
                return False, f"Conversa '{destino}' nao encontrada na barra lateral."
            alvo.first.click()
            time.sleep(2.0)
            busca.click()
            pg.keyboard.press("Control+A")
            pg.keyboard.press("Backspace")

        if titulo_atual() != destino:
            return False, f"Cabecalho aberto '{titulo_atual()}' difere de '{destino}'."

        try:
            pg.wait_for_selector('#main footer div[contenteditable="true"]', state="visible", timeout=20000)
        except Exception:
            return False, "Caixa de mensagem do WhatsApp nao ficou pronta em 20s."
        box = pg.locator('#main footer div[contenteditable="true"]').first
        box.click()
        pg.keyboard.press("Control+A")
        pg.keyboard.press("Backspace")

        for i, linha in enumerate(linhas):
            if linha:
                pg.keyboard.insert_text(linha)
            if i < len(linhas) - 1:
                pg.keyboard.press("Shift+Enter")
            if i % 8 == 7:
                pg.wait_for_timeout(150)  # respiro: o WhatsApp perdia linhas quando a aba estava lenta
        time.sleep(0.8)

        obtido = [norm(t) for t in box.locator("p, div[dir]").all_inner_texts() if t.strip()]
        esperado = [norm(l) for l in linhas if l.strip()]
        if obtido != esperado:
            box.click()
            pg.keyboard.press("Control+A")
            pg.keyboard.press("Backspace")  # nao deixa rascunho pela metade na conversa
            return False, f"Texto digitado divergiu do esperado ({len(obtido)} vs {len(esperado)} linhas)."

        pg.keyboard.press("Enter")
        time.sleep(3.0)
        ultima = pg.locator("#main [data-id]").last.inner_text()[:80].replace("\n", " ")
        caixa_vazia = not box.inner_text().strip()
        return True, f"Enviado para '{destino}' | caixa_vazia={caixa_vazia} | ultima='{ultima}'"


# Erros de configuracao nao se resolvem repetindo a tentativa.
_ERROS_SEM_RETENTATIVA = ("nao encontrada", "nao configurado", "difere de")


def enviar_whatsapp(mensagem: str, tentativas: int = 3) -> tuple[bool, str]:
    """Envia ao chat proprio com ate `tentativas` tentativas (so envia texto conferido, sem duplicar)."""
    try:
        # Um envio por vez na aba compartilhada: relatorio e alerta urgente nao podem digitar ao mesmo tempo.
        with trava.aguardar("whatsapp-envio", espera_max_s=300):
            return _enviar_com_retentativas(mensagem, tentativas)
    except trava.TravaOcupada:
        return False, "WhatsApp ocupado por outro envio ha mais de 5 min"


def _enviar_com_retentativas(mensagem: str, tentativas: int) -> tuple[bool, str]:
    garantir_zap_vivo()
    linhas = mensagem.rstrip("\n").split("\n")
    info = "sem tentativa"
    feitas = 0
    for n in range(1, tentativas + 1):
        feitas = n
        try:
            ok, info = _enviar_uma_vez(linhas)
        except Exception as exc:  # noqa: BLE001 - conexao CDP caida, aba recarregando etc.
            ok, info = False, f"excecao no envio: {str(exc)[:160]}"
        if ok:
            return True, info + (f" | tentativa {n}" if n > 1 else "")
        if any(t in info.lower() for t in _ERROS_SEM_RETENTATIVA):
            break
        if n < tentativas:
            time.sleep(8 * n)
    return False, f"{info} (apos {feitas} tentativa(s))"


def main() -> int:
    parser = argparse.ArgumentParser(description="Rastreador de precos dos 4 robos aspiradores.")
    parser.add_argument("--enviar-zap", action="store_true", help="Envia o resumo pelo nav-zap.")
    parser.add_argument("--primeira-vez", action="store_true", help="Inclui analise pre-Black Friday.")
    parser.add_argument("--sem-persistir", action="store_true", help="Teste: nao grava estado, historico nem banco.")
    args = parser.parse_args()

    PRIVADO_DIR.mkdir(parents=True, exist_ok=True)
    return ciclo.executar_ciclo(
        rotulo="robos",
        origem="rastreador-robos",
        coletar=coletar_precos,
        montar_mensagem=montar_mensagem,
        estado_path=ESTADO_PATH,
        hist_path=HIST_PATH,
        enviar_zap=args.enviar_zap,
        enviar_fn=enviar_whatsapp,
        primeira_vez=args.primeira_vez,
        persistir=not args.sem_persistir,
    )


if __name__ == "__main__":
    sys.exit(main())
