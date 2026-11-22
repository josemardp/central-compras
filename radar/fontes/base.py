"""Utilitarios comuns das fontes: HTTP com timeout/retry/backoff e erro padronizado."""

from __future__ import annotations

import html
import re
import time
import urllib.error
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)


class FonteErro(RuntimeError):
    pass


class FonteErroRede(FonteErro):
    """Sem conexao/DNS/timeout: as demais requisicoes da MESMA fonte falhariam igual, entao o laco para."""


def http_get(url: str, timeout: float = 15.0, tentativas: int = 2, espera: float = 2.0, max_bytes: int = 3_000_000) -> str:
    """GET simples. Retenta com backoff em erro de rede/5xx/429; 404 e outros 4xx nao sao repetidos."""
    ultimo = ""
    rede = False
    for n in range(1, tentativas + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(max_bytes).decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            ultimo = f"HTTP {exc.code}"
            if exc.code not in (429, 500, 502, 503, 504):
                raise FonteErro(f"{url}: {ultimo}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            ultimo = f"{type(exc).__name__}: {str(exc)[:80]}"
            rede = True
        if n < tentativas:
            time.sleep(espera * n)
    raise (FonteErroRede if rede else FonteErro)(f"{url}: {ultimo}")


def texto_visivel(fragmento_html: str) -> str:
    sem = re.sub(r"<script.*?</script>|<style.*?</style>", " ", fragmento_html, flags=re.S | re.I)
    sem = re.sub(r"<br\s*/?>", "\n", sem, flags=re.I)
    sem = re.sub(r"<[^>]+>", " ", sem)
    return re.sub(r"[ \t\r\f\v]+", " ", html.unescape(sem)).strip()


def preco_do_texto(txt: str) -> float | None:
    """Primeiro 'R$ 1.234,56' do texto."""
    m = re.search(r"R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)", txt)
    if not m:
        return None
    try:
        return float(m.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return None
