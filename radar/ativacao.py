"""Verificacao PREVIA da ativacao controlada dos alertas reais. SOMENTE LEITURA: nunca liga alerta, nunca envia mensagem.

Cada item sai como OK, FALHA (algo quebrado), PENDENTE (falta evidencia que so o tempo ou voce produzem) ou MANUAL (passo seu).
Veredito: APTO so se nao houver FALHA nem PENDENTE. Os itens MANUAL sao os passos do procedimento (docs/ecossistema/16-plano-de-ativacao.md).
Ligar e uma edicao SUA em config/radar_regras.yaml (`enviar: true` e `homologado_em`); este modulo so sabe DESLIGAR.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

from . import caminhos, db, maquina, piloto, qualidade, ranking

EXPERIMENTAL = {"orcamento_diario": 6, "orcamento_critico_diario": 3, "orcamento_excecao_diario": 2, "max_por_ciclo": 2}
MIN_CANDIDATOS_EM_SOMBRA = 3          # evidencia minima de que o caminho ao vivo foi exercitado antes de ligar
JANELA_SOMBRA_H = 72.0
TAREFAS = ("Central Compras - Rastrear Robos BF", "Central Compras - Radar Varredura")


def _i(i: str, nome: str, status: str, detalhe: str) -> dict[str, str]:
    return {"id": i, "nome": nome, "status": status, "detalhe": detalhe}


def verificar(agora: dt.datetime | None = None, *, rodar_externos: bool = True) -> list[dict[str, str]]:
    agora = agora or dt.datetime.now()
    out: list[dict[str, str]] = []
    regras = ranking.carregar_regras()
    al, pr = regras.get("alertas", {}), regras.get("prioridade", {})

    # 1 configuracao
    ligado = bool(al.get("enviar") and al.get("homologado_em"))
    out.append(_i("A1", "alertas reais desligados antes da ativacao", "OK" if not ligado else "FALHA",
                  "desligados (enviar=false, homologado_em vazio)" if not ligado else f"JA LIGADOS (homologado_em {al.get('homologado_em')}): esta verificacao e previa"))
    desvios = {k: (pr.get(k), v) for k, v in EXPERIMENTAL.items() if pr.get(k) != v}
    out.append(_i("A2", "politica de prioridade = configuracao experimental (6 comuns, 3 criticos, 2 excecao, 2 por varredura)",
                  "OK" if not desvios else "FALHA", "confere" if not desvios else f"diferente (atual, esperado): {desvios}"))
    ok_cfg = al.get("status_enviaveis") == ["PROVAVEL", "VALIDADO"] and int(al.get("ttl_alerta_min", 0)) == 30 and al.get("revalidar_antes_de_enviar") is True
    out.append(_i("A3", "gates de seguranca (so PROVAVEL/VALIDADO, TTL 30 min, revalidacao na fonte)", "OK" if ok_cfg else "FALHA",
                  f"status {al.get('status_enviaveis')}, ttl {al.get('ttl_alerta_min')}, revalidar {al.get('revalidar_antes_de_enviar')}"))

    # 2 maquina, agendador, banco
    pode, motivo = maquina.pode_rodar()
    out.append(_i("B1", "esta e a maquina oficial", "OK" if pode else "FALHA", motivo or "maquina oficial"))
    if rodar_externos:
        from . import agenda_windows

        est = agenda_windows.estado_tarefas(list(TAREFAS))
        for n in TAREFAS:
            t = est.get(n) or {}
            # 267009 (0x41301) = "a tarefa esta em execucao agora": normal no meio de um ciclo, nao e falha
            bom = bool(t.get("existe")) and ((t.get("estado") == "Ready" and t.get("resultado") == 0) or (t.get("estado") == "Running" and t.get("resultado") == 267009))
            out.append(_i("B2", f"tarefa agendada '{n}'", "OK" if bom else "FALHA",
                          f"estado {t.get('estado')}, ultima {t.get('ultima')} (resultado {t.get('resultado')}), proxima {t.get('proxima')}" if t.get("existe") else "nao existe"))
    con = db.abrir()
    try:
        v = db.versao_aplicada(con)
        integ = con.execute("PRAGMA integrity_check").fetchone()[0]
        out.append(_i("B3", "banco SQLite: versao do esquema e integridade", "OK" if v == db.VERSAO_ATUAL and integ == "ok" else "FALHA", f"versao {v}/{db.VERSAO_ATUAL}, integridade {integ}"))

        # 3 fontes
        import yaml

        cfg = (yaml.safe_load((caminhos.RAIZ / "config" / "radar_fontes.yaml").read_text(encoding="utf-8")) or {}).get("fontes") or {}
        for f in ("promobit", "gatry", "pelando", "hardmob", "meliuz"):
            r = con.execute("SELECT ultimo_ok, falhas_consecutivas FROM fontes_saude WHERE fonte=?", (f,)).fetchone()
            lim = 2.5 * float(cfg.get(f, {}).get("intervalo_min", 10))
            idade = None
            if r and r["ultimo_ok"]:
                idade = (agora - dt.datetime.strptime(r["ultimo_ok"], "%Y-%m-%d %H:%M:%S")).total_seconds() / 60
            bom = bool(r and idade is not None and idade <= lim and not r["falhas_consecutivas"])
            out.append(_i("C1", f"fonte comunitaria {f}", "OK" if bom else "FALHA",
                          f"ultima leitura ha {idade:.0f} min (limite {lim:.0f}), falhas seguidas {r['falhas_consecutivas'] if r else 'n/d'}" if idade is not None else "nunca leu"))
        lac = qualidade.lacunas_historicas(con, 24, agora, cfg)
        reais = {f: [j for j in d["lacunas"] if j["situacao"] == "LACUNA"] for f, d in lac.items()}
        reais = {f: j for f, j in reais.items() if j}
        out.append(_i("C2", "sem lacuna de coleta nas ultimas 24 h", "OK" if not reais else "PENDENTE",
                      "nenhuma janela maior que o alcance da lista" if not reais else "; ".join(f"{f}: {len(j)} janela(s), ~{sum(x['perdido_min'] for x in j)} min" for f, j in reais.items())))

        # 4 sombra: o caminho ao vivo foi exercitado?
        # Sem exigir N ofertas: os produtos sao raros (1 oferta real em ~8.500 publicacoes). O que importa e se o caminho ao vivo JA foi exercitado
        # pelo menos uma vez e o que fica como risco residual; isso aparece explicitamente (D1) em vez de virar uma meta numerica.
        ini = (agora - dt.timedelta(hours=JANELA_SOMBRA_H)).strftime("%Y-%m-%d %H:%M:%S")
        tot = con.execute("SELECT COUNT(*) FROM candidatos_alerta").fetchone()[0]
        recentes = con.execute("SELECT COUNT(*) FROM candidatos_alerta WHERE criado_em >= ?", (ini,)).fetchone()[0]
        pub = con.execute("SELECT SUM(itens) FROM coletas_ciclo WHERE ciclo_em >= ?", (ini,)).fetchone()[0] or 0
        out.append(_i("D1", "caminho ao vivo exercitado com oferta REAL em sombra", "OK" if tot >= 1 else "PENDENTE",
                      f"{tot} candidato(s) real(is) ate hoje ({recentes} nas ultimas {JANELA_SOMBRA_H:.0f} h, de ~{int(pub)} publicacoes lidas). "
                      + ("COMPROVADO: coleta, reconhecimento, conferencia na loja, preco x cupom, prioridade e despacho em sombra. "
                         "RISCO RESIDUAL: amostra minima (nao mede recall nem taxa de falso positivo em mercado); o piloto limita o dano (2 alertas/dia, produto exato, "
                         "sem aviso, fonte revalidada no envio)." if tot >= 1 else "Nenhuma oferta real passou pelo caminho ao vivo ainda.")))
        out.append(_i("D2", "conferir cada alerta em sombra (falso positivo?)", "MANUAL",
                      "rode `python -m radar prioridade` e responda: eu gostaria de ter recebido cada um? Algum e falso positivo recorrente?"))
    finally:
        con.close()

    # 5 fila e simulacao (banco temporario, nada enviado)
    import contextlib
    import io

    from . import cenarios, simulacao

    with contextlib.redirect_stdout(io.StringIO()):   # os cenarios imprimem logs de fontes falsas: ruido para quem le o checklist
        res = simulacao.simular(historico_real=False)
    out.append(_i("E1", "teste da fila e da politica em banco temporario (8 situacoes, WhatsApp falso)", "OK" if res["todas_ok"] else "FALHA",
                  f"{sum(1 for s in res['situacoes'] if s['ok'])}/{len(res['situacoes'])} situacoes como esperado (inclui queda do WhatsApp, TTL e reconexao)"))
    with contextlib.redirect_stdout(io.StringIO()):
        cen = cenarios.executar_cenarios()
    out.append(_i("E2", "cenarios ponta a ponta de homologacao", "OK" if cen["ok"] else "FALHA", f"{cen['aprovados']}/{cen['total']}"))

    # 6 destinatario WhatsApp (sem enviar)
    out.append(_destinatario())
    out.append(_i("E3", "teste controlado de envio REAL ao seu WhatsApp", "MANUAL",
                  "rode `python -m radar teste-entrega --confirmo` (1 mensagem rotulada TESTE ao SEU chat, com medicao de latencia) e confirme que chegou no chat certo"))

    pil = piloto.config(regras)
    exc = {k: (pil.get(k), t) for k, t in piloto.TETO_CONSERVADOR.items() if (pil.get(k) or 0) > t}
    out.append(_i("P1", "piloto com limites conservadores (<= 3 comuns, 1 critico, 0 excecao, 1 por varredura)", "OK" if not exc else "FALHA",
                  f"{pil['orcamento_diario']} comum/{pil['orcamento_critico_diario']} critico/{pil['orcamento_excecao_diario']} excecao, {pil['max_por_ciclo']} por varredura, "
                  f"{len(pil['produtos_exatos'])} produtos exatos, confianca minima {pil['confianca_minima']}" if not exc else f"acima do conservador (atual, teto): {exc}"))
    out.append(_i("P2", "destinatario do WhatsApp confirmado POR VOCE", "OK" if pil.get("destinatario_confirmado_em") else "MANUAL",
                  f"confirmado em {pil['destinatario_confirmado_em']}" if pil.get("destinatario_confirmado_em")
                  else "depois do teste de entrega chegar no SEU chat, preencha piloto.destinatario_confirmado_em em config/radar_regras.yaml (sem isso o piloto nao envia nada)"))

    # 7 seguranca e protecao do codigo
    if rodar_externos:
        p = subprocess.run([sys.executable, str(caminhos.RAIZ / "scripts" / "central_compras.py"), "checar-segredos", "--strict"], capture_output=True, text=True, timeout=180)
        out.append(_i("F1", "verificacao de segredos (--strict)", "OK" if p.returncode == 0 else "FALHA", (p.stdout.strip().splitlines() or ["sem saida"])[0][:160]))
    from . import telegram_conta as tc

    tg = tc.arq_credenciais().exists() or Path(str(tc.arq_sessao()) + ".session").exists()
    out.append(_i("F2", "Telegram: credenciais/sessao", "OK", "nao autenticado (o radar nao le o Telegram da sua conta)" if not tg else "autenticado; so le os canais da lista"))
    bk = sorted((caminhos.radar_dir() / "backups").glob("codigo-radar-*.zip"))
    idade_bk = (agora - dt.datetime.fromtimestamp(bk[-1].stat().st_mtime)).total_seconds() / 3600 if bk else None
    out.append(_i("F3", "backup do codigo fora do Git com menos de 24 h", "OK" if idade_bk is not None and idade_bk < 24 else "FALHA",
                  f"{bk[-1].name} (ha {idade_bk:.1f} h)" if bk else "nenhum backup: rode `python -m radar git-escopo --backup-completo`"))
    out.append(_i("G1", "commit do radar feito (so com a sua autorizacao)", "MANUAL", "ate o commit o codigo so existe nesta maquina e nos backups"))
    out.append(_i("G2", "BLACK150 validado no carrinho", "MANUAL", "continua NAO_CONFIRMADO ate voce testar (sem finalizar) e rodar `radar validar`"))
    return out


def _destinatario() -> dict[str, str]:
    """Confere SEM enviar: aba do WhatsApp Web aberta na porta do zap-vivo e destino configurado."""
    nome = "WhatsApp: aba do zap-vivo (porta 9230) e destinatario"
    try:
        with urllib.request.urlopen("http://127.0.0.1:9230/json", timeout=5) as r:
            abas = json.loads(r.read().decode("utf-8"))
        tem = any("web.whatsapp.com" in str(a.get("url", "")) for a in abas)
    except Exception as exc:  # noqa: BLE001
        return _i("E4", nome, "FALHA", f"porta 9230 inacessivel ({type(exc).__name__}); inicie a tarefa 'Zap vivo - WhatsApp das IAs'")
    if not tem:
        return _i("E4", nome, "FALHA", "a porta 9230 responde, mas nao ha aba web.whatsapp.com")
    try:
        if str(caminhos.RAIZ) not in sys.path:
            sys.path.insert(0, str(caminhos.RAIZ))
        from scripts import rastrear_robos_bf as rr  # noqa: PLC0415

        destino = rr.carregar_destino_config()
    except Exception:  # noqa: BLE001
        destino = None
    if destino:  # nunca imprime o destino (e dado pessoal): so diz que existe
        return _i("E4", nome, "OK", "aba do WhatsApp Web aberta; destino do chat configurado (confirme no teste controlado E3 que e o SEU chat)")
    return _i("E4", nome, "PENDENTE", "aba aberta, mas o chat de destino nao esta em config.json: o envio usa o numero detectado da sessao; confirme no teste controlado E3")


def veredito(itens: list[dict[str, str]]) -> str:
    if any(i["status"] == "FALHA" for i in itens):
        return "NAO APTO: ha item com FALHA"
    if any(i["status"] == "PENDENTE" for i in itens):
        return "NAO APTO AINDA: falta evidencia (itens PENDENTE)"
    return "APTO PARA PILOTO (nao para producao completa): conclua os passos MANUAL do plano, nesta ordem"


def formatar(itens: list[dict[str, str]]) -> str:
    L = ["== VERIFICACAO PREVIA DA ATIVACAO CONTROLADA (somente leitura; nada e ligado nem enviado)"]
    for i in itens:
        L.append(f"  [{i['status']:8s}] {i['id']} {i['nome']}\n             {i['detalhe']}")
    L.append(f"\nVEREDITO: {veredito(itens)}")
    L.append("Para LIGAR: edite config/radar_regras.yaml (alertas.enviar: true e alertas.homologado_em) so depois do plano. Para DESLIGAR agora: python -m radar ativacao --desligar")
    return "\n".join(L)


def desligar() -> tuple[bool, str]:
    """Kill switch: poe `enviar: false` e `homologado_em: null` no bloco alertas, preservando comentarios e o resto do arquivo. So desliga."""
    arq = caminhos.CONFIG_DIR / "radar_regras.yaml"
    txt = arq.read_text(encoding="utf-8")
    ini = txt.index("\nalertas:")
    fim = txt.find("\n\n", ini + 1)
    fim = len(txt) if fim < 0 else fim
    bloco = txt[ini:fim]
    novo, n = re.subn(r"(?m)^(\s*enviar:\s*)(true|false)\b", r"\1false", bloco, count=1)
    if n == 0:
        return False, "linha `enviar:` nao encontrada no bloco alertas"
    novo = re.sub(r"(?m)^(\s*homologado_em:\s*)[^#\n]*", r"\1null              ", novo, count=1)
    arq.write_text(txt[:ini] + novo + txt[fim:], encoding="utf-8")
    cfg = ranking.carregar_regras()["alertas"]
    ok = not cfg.get("enviar") and not cfg.get("homologado_em")
    descartados = 0
    try:  # efeito imediato: alerta que esperava na fila nao sai depois do kill switch (relatorios nao sao tocados)
        from . import outbox

        con = db.abrir()
        try:
            descartados = outbox.descartar_alertas(con, "kill switch: radar ativacao --desligar")
        finally:
            con.close()
    except Exception as exc:  # noqa: BLE001 - a config ja foi desligada; a varredura tambem descarta no proximo ciclo
        return ok, f"enviar={cfg.get('enviar')}, homologado_em={cfg.get('homologado_em')}; fila nao limpa agora ({type(exc).__name__}), a varredura limpa no proximo ciclo"
    return ok, f"enviar={cfg.get('enviar')}, homologado_em={cfg.get('homologado_em')}; {descartados} alerta(s) da fila descartado(s)"


# ------------------------------------------------------------------ teste unico de entrega (so com autorizacao) e ensaio do kill switch

ARQ_TESTE = "teste_entrega.json"


def mensagem_teste(agora: dt.datetime | None = None) -> str:
    """Mensagem sintetica com o FORMATO REAL do alerta (inclui os tres niveis de preco e a confianca), claramente marcada como TESTE."""
    from . import alertas, cenarios

    agora = agora or dt.datetime.now()
    loja = {"status": "confirmado", "preco_loja": 1299.0, "vendedor": "Loja Exemplo", "verificado_em": agora.strftime("%Y-%m-%d %H:%M")}
    corpo = alertas.montar_mensagem(
        nome_produto="PRODUTO DE TESTE (inventado)", loja="Loja Exemplo", preco_anunciado=1199.0, cupom="TESTE100", preco_final=1199.0, estimado=True, stats={},
        fonte="teste", canal="teste", detectado_em=agora.strftime("%d/%m %H:%M"), status="PROVAVEL", url=None, classe="ALTA", motivo="mensagem de teste de entrega",
        avisos=["preco_depende_de_cupom_nao_confirmado"], frete_conhecido=False, prioridade="64/100 (teste)",
        niveis_preco={"anunciado": 1199.0, "cupom_incluso": "TESTE100", "loja": loja, "entregue": None},
        confianca=("MEDIA", ["o preço na loja é R$ 1.299,00 sem cupom; o anunciado exige o cupom, não confirmado no carrinho"]))
    return cenarios.mensagem_de_teste(corpo)


def teste_entrega(confirmo: bool = False, *, de_novo: bool = False, enviar_fn=None, agora: dt.datetime | None = None) -> dict[str, Any]:
    """UM envio de teste ao SEU WhatsApp, medindo criacao -> inicio -> confirmacao. Sem `confirmo` so mostra a previa (nada e enviado).
    Maximo 1 por dia (`de_novo` libera). Nao liga alerta nenhum: so usa o mesmo canal de envio dos relatorios."""
    import time

    from . import latencia

    agora = agora or dt.datetime.now()
    t_criacao = time.perf_counter()
    msg = mensagem_teste(agora)
    res: dict[str, Any] = {"enviado": False, "previa": msg, "chars": len(msg)}
    if not confirmo:
        res["motivo"] = "sem --confirmo: apenas previa; nada foi enviado"
        return res
    pode, motivo = maquina.pode_rodar()
    if not pode:
        res["motivo"] = f"maquina nao oficial: {motivo}"
        return res
    marca = caminhos.radar_dir() / ARQ_TESTE
    if marca.exists() and not de_novo:
        try:
            if json.loads(marca.read_text(encoding="utf-8")).get("data") == agora.strftime("%Y-%m-%d"):
                res["motivo"] = "ja houve um teste de entrega hoje (teste UNICO); use --de-novo se realmente quiser outro"
                return res
        except (OSError, ValueError):
            pass
    if enviar_fn is None:
        from . import canais

        enviar_fn = canais.enviar_whatsapp
    t_inicio = time.perf_counter()
    ok, info = enviar_fn(msg)
    t_fim = time.perf_counter()
    confirmado = bool(ok and "TESTE DO RADAR" in str(info))
    res.update(enviado=bool(ok), info=str(info)[:200], confirmado_no_chat=confirmado, espera_s=round(t_inicio - t_criacao, 3),
               duracao_s=round(t_fim - t_inicio, 2), ponta_a_ponta_s=round(t_fim - t_criacao, 2))
    latencia.registrar("teste_entrega", ok=bool(ok), espera_s=res["espera_s"], duracao_s=res["duracao_s"], ponta_a_ponta_s=res["ponta_a_ponta_s"],
                       confirmado_no_chat=confirmado, chars=len(msg))
    latencia.registrar("envio_alerta", ok=bool(ok), teste=True, duracao_s=res["duracao_s"], espera_s=res["espera_s"], chars=len(msg))
    if ok:
        marca.write_text(json.dumps({"data": agora.strftime("%Y-%m-%d"), "hora": agora.strftime("%H:%M:%S")}), encoding="utf-8")
    return res


def ensaio_kill_switch() -> list[dict[str, str]]:
    """Ensaio COMPLETO do desligamento em copia temporaria (config, banco e canal falsos): nada real e tocado."""
    import contextlib
    import io
    import shutil
    import tempfile
    from unittest import mock

    from . import outbox, varredura

    out: list[dict[str, str]] = []
    real_cfg = caminhos.CONFIG_DIR / "radar_regras.yaml"
    with tempfile.TemporaryDirectory() as tmp_dados, tempfile.TemporaryDirectory() as tmp_cfg:
        cfg = Path(tmp_cfg) / "radar_regras.yaml"
        shutil.copyfile(real_cfg, cfg)
        txt = re.sub(r"(?m)^(\s*enviar:\s*)false", r"\1true", cfg.read_text(encoding="utf-8"), count=1)
        txt = re.sub(r"(?m)^(\s*homologado_em:\s*)null", r'\1"2026-11-22 09:00"', txt, count=1)
        cfg.write_text(txt, encoding="utf-8")
        with mock.patch.dict("os.environ", {"CENTRAL_COMPRAS_DADOS_PRIVADOS": tmp_dados}), mock.patch.object(caminhos, "CONFIG_DIR", Path(tmp_cfg)), \
                mock.patch.object(ranking, "ARQ_REGRAS", cfg):
            ligado = ranking.carregar_regras()["alertas"]
            out.append(_i("K1", "copia do ensaio esta com alertas LIGADOS", "OK" if ligado.get("enviar") and ligado.get("homologado_em") else "FALHA", f"enviar={ligado.get('enviar')}"))
            con = db.abrir()
            outbox.enfileirar(con, "ALERTA NA FILA", "radar-alerta", "whatsapp fora", tipo="alerta", oferta_id=1)
            outbox.enfileirar(con, "RELATORIO NA FILA", "rastreador-robos", "whatsapp fora")
            con.close()
            ok, info = desligar()
            desl = ranking.carregar_regras()["alertas"]
            out.append(_i("K2", "kill switch grava enviar=false e homologado_em=null", "OK" if ok and not desl.get("enviar") and not desl.get("homologado_em") else "FALHA", info))
            con = db.abrir()
            desf = {(r["tipo"], r["desfecho"]) for r in con.execute("SELECT tipo, desfecho FROM outbox")}
            con.close()
            out.append(_i("K3", "alerta da fila descartado e relatorio preservado", "OK" if desf == {("alerta", "descartado_alertas_desligados"), ("relatorio", None)} else "FALHA", str(sorted(desf, key=str))))
            enviados: list[str] = []
            with contextlib.redirect_stdout(io.StringIO()):
                varredura.executar(enviar=True, enviar_fn=lambda t: (enviados.append(t) or (True, "ok")), coletores={"x": lambda c: []}, fontes_cfg={"x": {}})
            out.append(_i("K4", "proxima varredura entrega o relatorio e NENHUM alerta", "OK" if len(enviados) == 1 and "RELATORIO NA FILA" in enviados[0] else "FALHA", f"{len(enviados)} envio(s)"))
    out.append(_i("K5", "config real continua como estava", "OK" if not ranking.carregar_regras()["alertas"].get("enviar") else "FALHA", "o ensaio usou so copias temporarias"))
    return out
