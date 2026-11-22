"""MODO PILOTO: alertas reais restritos, para a primeira semana de uso. Tres modos, sem ambiguidade:

  SOMBRA    `alertas.enviar` false (ou sem `homologado_em`): coleta, classifica, registra e SIMULA; nada e enviado.
  PILOTO    `enviar` true + `homologado_em` + `piloto.ativo` true: envia SO o que passar em TODAS as barreiras abaixo.
  COMPLETO  `enviar` true + `homologado_em` + `piloto.ativo` false: politica de prioridade inteira (nao recomendado antes do piloto dar certo).

Barreiras do piloto (todas obrigatorias; o que nao passar vira `nao_selecionado` com o motivo, visivel em `radar prioridade`):
  produto EXATO da lista, sem nenhum aviso (modelo, voltagem, hora incerta, cupom nao confirmado), confianca minima exibida na mensagem,
  link da fonte presente, fonte REVALIDADA no momento do envio, destinatario confirmado POR VOCE, e limites diarios/por varredura bem menores.
Desligar a qualquer momento: `python -m radar ativacao --desligar`.
"""

from __future__ import annotations

import json
from typing import Any

ORDEM_CONFIANCA = {"BAIXA": 0, "MEDIA": 1, "ALTA": 2}

PADRAO: dict[str, Any] = {
    "ativo": False,
    "produtos_exatos": [],
    "confianca_minima": "MEDIA",
    "exigir_sem_avisos": True,
    "exigir_url": True,
    "revalidar_sempre": True,
    "destinatario_confirmado_em": None,
    "orcamento_diario": 2,
    "orcamento_critico_diario": 1,
    "orcamento_excecao_diario": 0,
    "max_por_ciclo": 1,
    "max_criticos_por_ciclo": 1,
    "intervalo_mesmo_produto_min": 240,
    "intervalo_critico_mesmo_produto_min": 120,
    "melhora_para_repetir_pct": 7,
}
LIMITES = ("orcamento_diario", "orcamento_critico_diario", "orcamento_excecao_diario", "max_por_ciclo", "max_criticos_por_ciclo",
           "intervalo_mesmo_produto_min", "intervalo_critico_mesmo_produto_min", "melhora_para_repetir_pct")
# Teto do que ainda se pode chamar de "conservador": acima disto a verificacao previa acusa.
TETO_CONSERVADOR = {"orcamento_diario": 3, "orcamento_critico_diario": 1, "orcamento_excecao_diario": 0, "max_por_ciclo": 1}


def config(regras: dict[str, Any]) -> dict[str, Any]:
    return {**PADRAO, **(regras.get("piloto") or {})}


def modo(regras: dict[str, Any]) -> str:
    al = regras.get("alertas", {})
    if not (al.get("enviar") and al.get("homologado_em")):
        return "SOMBRA"
    return "PILOTO" if config(regras).get("ativo") else "COMPLETO"


def limites_prioridade(pil: dict[str, Any]) -> dict[str, Any]:
    """So os limites que o piloto sobrescreve na politica de prioridade."""
    return {k: pil[k] for k in LIMITES if k in pil}


def avaliar_candidato(c: Any, pil: dict[str, Any]) -> tuple[bool, str]:
    """`c` e uma linha de candidatos_alerta. Devolve (passa, motivo). Pura: nao consulta rede (a revalidacao na fonte e do despachante)."""
    if not pil.get("destinatario_confirmado_em"):
        return False, "destinatario do WhatsApp ainda NAO confirmado por voce (piloto.destinatario_confirmado_em vazio)"
    if c["produto"] not in (pil.get("produtos_exatos") or []):
        return False, f"produto {c['produto']} fora da lista do piloto"
    try:
        comp = json.loads(c["componentes_json"] or "{}")
    except ValueError:
        comp = {}
    conf = (comp.get("confianca") or [None])[0]
    if conf is None:
        return False, "candidato sem nivel de confianca registrado"
    if ORDEM_CONFIANCA.get(conf, 0) < ORDEM_CONFIANCA.get(pil.get("confianca_minima", "MEDIA"), 1):
        return False, f"confianca {conf} abaixo da minima do piloto ({pil.get('confianca_minima')})"
    if pil.get("exigir_sem_avisos", True) and (comp.get("avisos") or []):
        return False, "ha avisos: " + ", ".join(comp["avisos"])
    if c["hora_incerta"]:
        return False, "hora da postagem incerta"
    if pil.get("exigir_url", True) and not c["url"]:
        return False, "sem link da fonte para conferir"
    return True, "dentro do piloto"


def painel(con: Any, regras: dict[str, Any], agora: Any, horas: float = 24.0) -> str:
    """Texto de acompanhamento dos primeiros envios do piloto."""
    import datetime as dt

    from . import latencia

    pil = config(regras)
    m = modo(regras)
    L = [f"== PILOTO | modo atual: {m}"]
    L.append(f"   limites: {pil['orcamento_diario']} comum + {pil['orcamento_critico_diario']} critico + {pil['orcamento_excecao_diario']} excecao por dia, "
             f"{pil['max_por_ciclo']} por varredura, mesmo produto a cada {pil['intervalo_mesmo_produto_min']} min ou melhora de {pil['melhora_para_repetir_pct']}%")
    L.append(f"   produtos do piloto: {len(pil['produtos_exatos'])} | confianca minima {pil['confianca_minima']} | destinatario confirmado por voce: "
             f"{pil['destinatario_confirmado_em'] or 'NAO'}")
    ini = (agora - dt.timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
    c = {r["estado"]: r["n"] for r in con.execute("SELECT estado, COUNT(*) n FROM candidatos_alerta WHERE criado_em >= ? GROUP BY estado", (ini,))}
    L.append(f"   candidatos {horas:.0f} h: {c or 'nenhum'}")
    fora = con.execute("SELECT produto, motivo FROM candidatos_alerta WHERE criado_em >= ? AND motivo LIKE 'fora do piloto%' ORDER BY id DESC LIMIT 5", (ini,)).fetchall()
    for r in fora:
        L.append(f"   fora do piloto: {r['produto']} | {r['motivo'][:110]}")
    env = [e for e in latencia.ler(horas, agora) if e.get("evento") == "envio_alerta"]
    ok = [e for e in env if e.get("ok")]
    L.append(f"   envios de alerta: {len(ok)} ok, {len(env) - len(ok)} com falha" + (f" | ultimo: {ok[-1]['ts']} ({ok[-1].get('duracao_s')} s)" if ok else ""))
    L.append("   Falso positivo recorrente (2 em 24 h, ou o mesmo padrao 2 vezes)? Desligue agora: python -m radar ativacao --desligar")
    return "\n".join(L)
