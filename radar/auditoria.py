"""Auditoria do historico bruto: acha leituras suspeitas sem alterar nada.

Sinais (heuristicos, para REVISAO humana; nada e corrigido automaticamente):
- `isolado`: o melhor preco e muito menor que todos os demais valores da MESMA coleta (como o R$ 60,65 da Leroy);
- `salto`: o melhor preco mudou mais que `LIMITE_SALTO` em relacao a ultima coleta boa do mesmo modelo;
- `degradada`: rodada com timeouts/perdas (ja excluida das estatisticas);
- `abaixo_do_historico`: abaixo de metade do menor valor das outras coletas boas (candidato a erro de leitura OU a oferta real: confira).
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

from . import correcoes, historico

LIMITE_SALTO = 0.35
LIMITE_ISOLADO = 0.6
CHAVES_PRECO = {"preco", "total", "preco_avista", "menor_preco", "preco_pix", "preco_novo", "menor_novo", "menor_grandes", "menor_geral"}


def _valores_da_coleta(mod: dict[str, Any]) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []

    def rec(o: Any, caminho: str) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if k in CHAVES_PRECO and isinstance(v, (int, float)) and v >= 20:
                    out.append((f"{caminho}/{k}".lstrip("/"), float(v)))
                elif isinstance(v, (dict, list)) and k not in ("promobit",):  # promobit traz preco de oferta de 3os: nao e coleta de loja
                    rec(v, f"{caminho}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                rec(v, f"{caminho}[{i}]")

    rec(mod, "")
    return out


def auditar(origem: str, caminho_jsonl: Path) -> list[dict[str, Any]]:
    """Retorna achados; le o JSONL BRUTO (sem correcoes) para que o achado seja o dado original."""
    registros = historico.carregar_jsonl(caminho_jsonl)
    corrigidos = {(c["produto"], str(c["coletado_em"])) for c in correcoes.carregar() if c.get("origem") == origem}
    achados: list[dict[str, Any]] = []
    bom: dict[str, Any] | None = None
    precos_bons: dict[str, list[float]] = {}
    for reg in registros:
        degr, motivo = historico.esta_degradada(reg, bom) if bom else (False, "")
        for chave, mod in (reg.get("modelos") or {}).items():
            melhor = mod.get("melhor_preco")
            ja = (chave, str(reg.get("coletado_em"))) in corrigidos
            base = {"origem": origem, "produto": chave, "coletado_em": reg.get("coletado_em"), "melhor_preco": melhor, "ja_corrigido": ja}
            if degr:
                achados.append({**base, "sinal": "degradada", "detalhe": motivo})
                continue
            if not isinstance(melhor, (int, float)):
                continue
            outros = [v for caminho, v in _valores_da_coleta(mod) if abs(v - melhor) > 0.01]
            if len(outros) >= 2 and melhor < LIMITE_ISOLADO * statistics.median(outros):
                achados.append({**base, "sinal": "isolado",
                                "detalhe": f"melhor R$ {melhor:.2f} vs mediana dos demais valores da coleta R$ {statistics.median(outros):.2f}"})
            if ja:  # o achado ja foi corrigido: a serie de comparacao usa o valor corrigido, nao o bruto
                corr = next((c.get("melhor_preco") for c in correcoes.carregar()
                             if c.get("origem") == origem and c.get("produto") == chave and str(c.get("coletado_em")) == str(reg.get("coletado_em"))), None)
                if corr is None:
                    continue
                melhor = corr
            anteriores = precos_bons.get(chave) or []
            if anteriores:
                ref = anteriores[-1]
                if abs(melhor - ref) / ref >= LIMITE_SALTO:
                    achados.append({**base, "sinal": "salto", "detalhe": f"R$ {ref:.2f} -> R$ {melhor:.2f} ({(melhor - ref) / ref * 100:+.0f}%)"})
                if len(anteriores) >= 3 and melhor < 0.5 * min(anteriores):
                    achados.append({**base, "sinal": "abaixo_do_historico", "detalhe": f"menor anterior R$ {min(anteriores):.2f}"})
            precos_bons.setdefault(chave, []).append(float(melhor))
        if not degr:
            bom = reg
    return achados
