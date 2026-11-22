"""Varredura incremental: coleta nas fontes publicas, identifica produtos, interpreta cupons,
classifica, deduplica e (se permitido) envia alerta urgente.

Cada fonte e isolada: falha numa nao afeta as outras (nem os relatorios programados, que sao outro job).
"""

from __future__ import annotations

import datetime as dt
import json
import time
from typing import Any, Callable

from . import alertas, catalogo, cupons, db, historico, latencia, lojas, maquina, outbox, prioridade, qualidade, ranking
from .cupons import EXPIRADO, NAO_CONFIRMADO, PROVAVEL, VALIDADO
from .fontes import FONTES
from .fontes.base import FonteErro
from .modelos import Oferta

import yaml

from . import caminhos

ARQ_FONTES = caminhos.CONFIG_DIR / "radar_fontes.yaml"


def carregar_fontes() -> dict[str, Any]:
    return (yaml.safe_load(ARQ_FONTES.read_text(encoding="utf-8")) or {}).get("fontes", {})


def _idade_horas(publicado_em: str | None, agora: dt.datetime) -> float | None:
    try:
        return (agora - dt.datetime.strptime(publicado_em[:16], "%Y-%m-%d %H:%M")).total_seconds() / 3600 if publicado_em else None
    except ValueError:
        return None


def cfg_efetiva(fcfg: dict[str, Any], agora: dt.datetime) -> tuple[dict[str, Any], bool]:
    """Configuracao da fonte NESTE instante. Dentro de `janela_intensiva` (de/ate, por DATA) valem os valores da janela (ex.: Promobit a cada
    5 min na Black Friday); fora dela, ou apos `ate`, volta sozinha ao normal: nao ha estado para desligar."""
    j = fcfg.get("janela_intensiva")
    if not j:
        return fcfg, False
    try:
        ini = dt.datetime.strptime(str(j["de"]), "%Y-%m-%d %H:%M")
        fim = dt.datetime.strptime(str(j["ate"]), "%Y-%m-%d %H:%M")
    except (KeyError, ValueError):
        return fcfg, False
    if ini <= agora <= fim:
        return {**{k: v for k, v in fcfg.items() if k != "janela_intensiva"}, **{k: v for k, v in j.items() if k not in ("de", "ate")}}, True
    return fcfg, False


def _vencida(con, fonte: str, intervalo_min: float, agora: dt.datetime) -> bool:
    row = con.execute("SELECT ultima_tentativa FROM fontes_saude WHERE fonte=?", (fonte,)).fetchone()
    if not row or not row["ultima_tentativa"]:
        return True
    ultima = dt.datetime.strptime(row["ultima_tentativa"], "%Y-%m-%d %H:%M:%S")
    return (agora - ultima).total_seconds() >= intervalo_min * 60 - 20  # folga: a tarefa dispara de 10 em 10 min


def _saude(con, fonte: str, ok: bool, itens: int, erro: str | None, agora: dt.datetime) -> None:
    s = agora.strftime("%Y-%m-%d %H:%M:%S")
    con.execute(
        "INSERT INTO fontes_saude (fonte, ultimo_ok, ultimo_erro, erro_msg, falhas_consecutivas, itens_ultima, ultima_tentativa) "
        "VALUES (?,?,?,?,?,?,?) ON CONFLICT(fonte) DO UPDATE SET "
        "ultimo_ok=COALESCE(excluded.ultimo_ok, fontes_saude.ultimo_ok), "
        "ultimo_erro=COALESCE(excluded.ultimo_erro, fontes_saude.ultimo_erro), erro_msg=excluded.erro_msg, "
        "falhas_consecutivas=CASE WHEN excluded.falhas_consecutivas=0 THEN 0 ELSE fontes_saude.falhas_consecutivas+1 END, "
        "itens_ultima=excluded.itens_ultima, ultima_tentativa=excluded.ultima_tentativa",
        (fonte, s if ok else None, None if ok else s, erro, 0 if ok else 1, itens, s),
    )
    con.commit()


def _cupons_da_oferta(of: Oferta, agora: dt.datetime) -> list[cupons.Cupom]:
    texto = of.texto_completo
    lista = cupons.extrair_cupons(texto, loja=of.loja, agora=agora)
    if of.cupom_codigo and of.cupom_codigo.upper() not in {c.codigo for c in lista}:
        c = cupons.Cupom(codigo=of.cupom_codigo.upper(), loja=of.loja)
        cupons._interpretar_janela(c, texto, agora)
        lista.append(c)
    contexto = texto + " " + " ".join(of.comentarios)
    for c in lista:
        cupons.avaliar_status(c, contexto, of.publicado_em, of.verificado_em, agora)
    return lista


def _upsert_oferta(con, of: Oferta, produto: str | None, cupom: cupons.Cupom | None, calc: dict[str, Any],
                   classe: str, score: float, motivo: str, agora: dt.datetime) -> tuple[int, bool]:
    s = agora.strftime("%Y-%m-%d %H:%M:%S")
    antes = con.execute(
        "SELECT id, preco_anunciado, cupom_codigo, status_cupom, classe FROM ofertas WHERE fonte=? AND canal=? AND id_externo=?",
        (of.fonte, of.canal, of.id_externo),
    ).fetchone()
    cupom_json = json.dumps(cupom.__dict__, ensure_ascii=False) if cupom else None
    valores = (
        of.titulo[:300], of.url, alertas.normalizar_url(of.url), of.loja, of.vendedor, produto, of.preco_anunciado, of.frete,
        cupom.codigo if cupom else None, cupom_json, cupom.status if cupom else None, calc.get("preco_final"),
        int(calc.get("estimado", True)), of.publicado_em, s, classe, score, motivo[:300],
    )
    tempos = (of.primeira_vista_em, of.coletado_em or agora.strftime("%Y-%m-%d %H:%M"), int(of.hora_incerta))
    if antes is None:
        cur = con.execute(
            "INSERT INTO ofertas (titulo, url, url_norm, loja, vendedor, produto, preco_anunciado, frete, cupom_codigo, cupom_json, "
            "status_cupom, preco_final, final_estimado, publicado_em, ultima_vista_em, classe, score, motivo, fonte, canal, id_externo, detectado_em, "
            "primeira_vista_em, coletado_em, hora_incerta) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            valores + (of.fonte, of.canal, of.id_externo, s) + tempos,
        )
        con.commit()
        return int(cur.lastrowid), True
    mudou = (antes["preco_anunciado"], antes["cupom_codigo"], antes["status_cupom"], antes["classe"]) != (
        of.preco_anunciado, cupom.codigo if cupom else None, cupom.status if cupom else None, classe)
    con.execute(
        "UPDATE ofertas SET titulo=?, url=?, url_norm=?, loja=?, vendedor=?, produto=?, preco_anunciado=?, frete=?, cupom_codigo=?, "
        "cupom_json=?, status_cupom=?, preco_final=?, final_estimado=?, publicado_em=?, ultima_vista_em=?, classe=?, score=?, motivo=?, "
        "primeira_vista_em=COALESCE(primeira_vista_em, ?), coletado_em=?, hora_incerta=? WHERE id=?",
        valores + tempos + (antes["id"],),
    )
    con.commit()
    return int(antes["id"]), mudou


def processar_oferta(
    con, of: Oferta, cat: dict[str, Any], regras: dict[str, Any], enviar_fn: Callable[[str], tuple[bool, str]] | None,
    agora: dt.datetime, persistir: bool = True, diferir: bool = False,
    verificar_loja: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Interpreta uma oferta. Retorna um resumo (para logs e testes).

    `diferir=False` (testes e cenarios simples): decide e envia NA HORA. `diferir=True` (varredura real): a oferta que passa nos
    portoes vira um CANDIDATO com pontuacao e o despachante (`prioridade.despachar`) decide ao fim do ciclo."""
    _t0 = time.perf_counter()
    resumo: dict[str, Any] = {"id_externo": of.id_externo, "produto": None, "classe": None, "acao": None}
    texto = of.texto_completo
    lista = _cupons_da_oferta(of, agora)

    resumo["cupons"] = len(lista)
    perfil = regras.get("perfil_comprador")
    # Elegivel = nenhuma restricao conhecida impede o SEU perfil e o cupom nao esta expirado (nao prova que funciona).
    resumo["cupons_elegiveis"] = sum(1 for c in lista if cupons.elegibilidade(c, perfil)[0] is True and c.status != EXPIRADO)
    if (of.extras or {}).get("tipo") == "cupom_loja":
        c = lista[0] if lista else None
        if persistir:
            _upsert_oferta(con, of, None, c, {"preco_final": None, "estimado": True}, "BAIXA", 0.0, "cupom de loja (sem produto)", agora)
        resumo.update(classe="BAIXA", acao="registrado", descarte="cupom_de_loja_sem_produto")
        return resumo

    casamento = catalogo.identificar(texto, cat)
    if casamento is None:
        resumo["descarte"] = catalogo.motivo_recusa(texto, cat) or "fora_do_catalogo"
        return resumo  # fora do catalogo: nao guardamos (o banco seria um deposito de promocoes alheias)
    produto = casamento.produto_id
    resumo["produto"] = produto
    pcat = cat["produtos"][produto]
    frete = of.frete if of.frete is not None else (0.0 if cupons.extrair_condicoes(texto)["frete_gratis"] else None)
    # Cupom que a PROPRIA publicacao traz (campo da fonte) ja esta embutido no preco anunciado (conferido em 21/11/2026: Philco PAC18FTW,
    # loja R$ 2.579 menos PHI200 = R$ 2.379 anunciado). NUNCA se desconta de novo; fica como "necessario para este preco", NAO CONFIRMADO.
    cupom_proprio = (of.cupom_codigo or "").upper() or None
    cupom, calc = cupons.melhor_cupom(of.preco_anunciado, frete, [c for c in lista if not (cupom_proprio and c.codigo == cupom_proprio)], perfil)
    cupom_dep = next((c for c in lista if cupom_proprio and c.codigo == cupom_proprio), None)
    cupom_exib = cupom or cupom_dep
    cod_cupom = cupom_exib.codigo if cupom_exib else None
    if cupom_dep is not None and not calc.get("cupom_aplicado"):
        calc = {**calc, "cupom_incluso": cupom_proprio}

    # TRES horas: so `publicado_em` (published_at) e a hora da POSTAGEM. Sem ela (hora incerta) a oferta nunca e tratada como relampago
    # e so e considerada recente se foi vista pela 1a vez agora e a coleta nao teve lacuna (senao pode ser antiga).
    hora_incerta = of.hora_incerta
    idade = _idade_horas(of.publicado_em, agora)
    idade_ref = idade
    if idade is None and hora_incerta and not (of.extras or {}).get("lacuna_antes"):
        idade_ref = _idade_horas(of.primeira_vista_em, agora)
    avisos = list(casamento.avisos) + (["hora_incerta"] if hora_incerta else [])
    limite_h = float(regras.get("alertas", {}).get("idade_maxima_horas", 6))
    status_preco = PROVAVEL if (idade_ref is not None and idade_ref <= limite_h) else NAO_CONFIRMADO
    validacao = status_preco
    if cupom and calc.get("cupom_aplicado"):
        validacao = min((status_preco, cupom.status), key=lambda e: alertas.ESTADOS_ORDEM.get(e, 0))
    if cupom_exib and cupom_exib.status == EXPIRADO and "cupom" in texto.lower():
        validacao = EXPIRADO
    # Validacao manual (`radar validar`) vale enquanto o preco anunciado nao piorar mais de 2% e a oferta nao expirar.
    if validacao != EXPIRADO and calc.get("preco_final") is not None:
        vm = con.execute(
            "SELECT v.preco_validado FROM validacoes_manuais v JOIN ofertas o ON o.id = v.oferta_id "
            "WHERE o.fonte=? AND o.canal=? AND o.id_externo=?", (of.fonte, of.canal, of.id_externo)).fetchone()
        if vm is not None and (vm["preco_validado"] is None or calc["preco_final"] <= float(vm["preco_validado"]) * 1.02):
            validacao = VALIDADO
            calc = {**calc, "estimado": False}

    # Preco CONFIRMADO na loja (so lojas com API publica configurada; nunca o link de afiliado). Se a loja cobra mais que o anunciado e a
    # oferta traz cupom nao validado, o preco anunciado depende do cupom: sem confirmacao no carrinho isso limita a classe a MEDIA.
    loja_info: dict[str, Any] | None = None
    if verificar_loja is not None and persistir and pcat.get("moeda") in (None, "BRL"):
        try:
            loja_info = verificar_loja(produto, pcat, of.loja)
        except Exception as exc:  # noqa: BLE001 - conferir a loja e um extra: nunca derruba a varredura
            loja_info = {"status": "erro", "nota": f"{type(exc).__name__}: {str(exc)[:60]}", "preco_loja": None}
    relacao = lojas.relacionar(of.preco_anunciado, loja_info, cupom_proprio)
    if relacao["relacao"] == "depende_de_cupom" and cupom_dep is not None and validacao != VALIDADO:
        avisos.append("preco_depende_de_cupom_nao_confirmado")
    confianca = alertas.nivel_confianca(validacao=validacao, avisos=avisos, loja=loja_info, relacao=relacao["relacao"], cupom_proprio=cupom_proprio)
    niveis_preco = {"anunciado": of.preco_anunciado, "cupom_incluso": cupom_proprio if calc.get("cupom_incluso") else None,
                    "loja": loja_info, "relacao": relacao, "entregue": None}
    resumo.update(confianca=confianca[0], loja=(loja_info or {}).get("status"), relacao_loja=relacao["relacao"])

    stats: dict[str, Any] = {}
    ref = None
    if pcat.get("moeda") not in (None, "BRL"):
        classe, score, motivo = "BAIXA", 0.0, f"produto em {pcat['moeda']}: comparacao de preco fora do escopo desta fonte"
    else:
        stats = historico.estatisticas(con, produto, agora)
        ref = historico.preco_referencia(con, produto, agora)
        classe, score, motivo = ranking.classificar(calc.get("preco_final"), validacao, stats, regras, avisos, idade_ref, preco_ref=ref)
    resumo.update(classe=classe, preco_final=calc.get("preco_final"), validacao=validacao, motivo=motivo,
                  cupons_aplicados=1 if calc.get("cupom_aplicado") else 0)
    if not persistir:
        return resumo

    oferta_id, mudou = _upsert_oferta(con, of, produto, cupom_exib, calc, classe, score, motivo, agora)
    fresca = idade_ref is not None and idade_ref <= limite_h
    if not (mudou and fresca) or calc.get("preco_final") is None:
        resumo["acao"] = "sem_alerta"
        resumo["descarte"] = ("sem_preco_final" if calc.get("preco_final") is None
                              else ("hora_incerta_sem_evidencia_de_novidade" if hora_incerta else "oferta_antiga") if not fresca
                              else "sem_mudanca_desde_a_ultima_vez")
        return resumo
    _t1 = time.perf_counter()
    resumo["t_classif_ms"] = round((_t1 - _t0) * 1000, 2)
    if diferir:
        gate, gate_motivo = alertas.gates(con, produto=produto, loja=of.loja, vendedor=of.vendedor, cupom=cod_cupom,
                                          preco=calc["preco_final"], status=validacao, classe=classe, regras=regras, agora=agora)
        resumo["acao"] = f"{gate}: {gate_motivo}"
        if gate == "suprimir":
            resumo["descarte"] = gate_motivo
            return resumo
        score_p, comp = prioridade.pontuar(
            preco_final=calc["preco_final"], preco_ref=ref, stats=stats, validacao=validacao, avisos=avisos, idade_horas=idade,
            hora_incerta=hora_incerta, repeticoes_24h=prioridade.repeticoes_24h(con, produto, agora), regras=regras)
        msg = alertas.montar_mensagem(
            nome_produto=pcat["nome"], loja=of.loja, preco_anunciado=of.preco_anunciado, cupom=cod_cupom,
            preco_final=calc["preco_final"], estimado=calc.get("estimado", True), stats=stats, fonte=of.fonte, canal=of.canal,
            detectado_em=agora.strftime("%d/%m %H:%M"), status=validacao, url=of.url, classe=classe, motivo=motivo, avisos=avisos,
            frete_conhecido=bool(calc.get("frete_conhecido", True)), hora_incerta=hora_incerta,
            prioridade=prioridade.texto_prioridade(score_p, comp), niveis_preco=niveis_preco, confianca=confianca)
        comp = {**comp, "niveis_preco": niveis_preco, "confianca": list(confianca), "avisos": list(avisos)}
        cid = prioridade.registrar_candidato(
            con, oferta_id=oferta_id, produto=produto, loja=of.loja, vendedor=of.vendedor, classe=classe, score=score_p, componentes=comp,
            preco_final=calc["preco_final"], status_cupom=validacao, cupom=cod_cupom, fonte=of.fonte,
            hora_incerta=hora_incerta, mensagem=msg, url=of.url, regras=regras, agora=agora)
        resumo.update(acao=f"candidato: pontuacao {score_p:.0f}", score=score_p, candidato_id=cid,
                      t_candidato_ms=round((time.perf_counter() - _t1) * 1000, 2))
        return resumo
    acao, porque = alertas.decidir(
        con, produto=produto, loja=of.loja, vendedor=of.vendedor, cupom=cod_cupom,
        preco=calc["preco_final"], status=validacao, fonte=of.fonte, classe=classe, regras=regras, agora=agora,
    )
    resumo["acao"] = f"{acao}: {porque}"
    if acao == "suprimir":
        resumo["descarte"] = porque
        return resumo
    msg = alertas.montar_mensagem(
        nome_produto=pcat["nome"], loja=of.loja, preco_anunciado=of.preco_anunciado, cupom=cod_cupom,
        preco_final=calc["preco_final"], estimado=calc.get("estimado", True), stats=historico.estatisticas(con, produto, agora),
        fonte=of.fonte, canal=of.canal, detectado_em=agora.strftime("%d/%m %H:%M"), status=validacao, url=of.url,
        classe=classe, motivo=motivo, avisos=avisos, frete_conhecido=bool(calc.get("frete_conhecido", True)), hora_incerta=hora_incerta,
        niveis_preco=niveis_preco, confianca=confianca,
    )
    modo = "sombra"
    if acao == "enviar" and enviar_fn is not None:
        ok, info = enviar_fn(msg)
        modo, porque = ("real", info) if ok else ("falha", info)
        if not ok:
            # Nao se perde alerta por falha do canal, mas ele so sera entregue dentro do TTL ou se revalidado na fonte.
            outbox.enfileirar(con, msg, "radar-alerta", info, tipo="alerta", oferta_id=oferta_id, agora_dt=agora,
                              ttl_min=float(regras.get("alertas", {}).get("ttl_alerta_min", outbox.TTL_ALERTA_MIN)))
    alertas.registrar(
        con, oferta_id=oferta_id, produto=produto, loja=of.loja, vendedor=of.vendedor, cupom=cod_cupom,
        preco=calc["preco_final"], url=of.url, classe=classe, status=validacao, modo=modo, detalhe=f"{porque} | {msg[:120]}", agora=agora,
    )
    resumo["acao"] = f"{modo}: {porque}"
    return resumo


def executar(enviar: bool = True, persistir: bool = True, verbose: bool = False, *,
             coletores: dict[str, Callable] | None = None, enviar_fn: Callable | None = None,
             agora: dt.datetime | None = None, fontes_cfg: dict[str, Any] | None = None, so_fontes: list[str] | None = None) -> int:
    _tc = time.perf_counter()
    agora = agora or dt.datetime.now()
    if fontes_cfg is None and coletores is None:  # uso real (nao teste): respeita a maquina oficial
        pode, motivo = maquina.pode_rodar()
        if not pode:
            print(f"[varredura] {motivo}")
            return 0
    con = db.abrir()
    cat, regras = catalogo.carregar(), ranking.carregar_regras()
    fontes = fontes_cfg if fontes_cfg is not None else carregar_fontes()
    usar_lojas = coletores is None   # em teste (coletores injetados) nunca consulta a rede das lojas
    coletores = coletores or FONTES
    cache_lojas: dict[tuple, tuple[dt.datetime, dict[str, Any]]] = {}

    def _verificar_loja(produto: str, pcat: dict[str, Any], loja: str | None) -> dict[str, Any]:
        chave = (produto, lojas._norm(loja))
        hit = cache_lojas.get(chave)
        if hit and (agora - hit[0]).total_seconds() < 600:
            return hit[1]
        info = lojas.verificar(produto, pcat, loja, cat, agora=agora)
        cache_lojas[chave] = (agora, info)
        return info
    if enviar and enviar_fn is None:
        from . import canais

        enviar_fn = canais.enviar_whatsapp
    if not enviar:
        enviar_fn = None
    total = {"fontes_ok": 0, "fontes_erro": 0, "ofertas": 0, "casadas": 0, "alertas": 0}
    tentou = 0

    # Alertas desligados (kill switch ou nunca ativados): o que esperava na fila NAO pode sair. So relatorios continuam sendo reenviados.
    al = regras.get("alertas", {})
    if persistir and not (al.get("enviar") and al.get("homologado_em")):
        n_desc = outbox.descartar_alertas(con, "alertas desligados na configuracao")
        if n_desc:
            print(f"[fila] {n_desc} alerta(s) que esperavam envio foram descartados: alertas desligados")
    # Alertas que ficaram na fila: entrega dentro do TTL, ou revalida na fonte, ou descarta.
    if enviar_fn is not None and persistir:
        revalidar = revalidar_oferta if regras.get("alertas", {}).get("revalidar_antes_de_enviar", True) else None
        for _id, ok_r, info_r in outbox.drenar(con, enviar_fn, revalidar=lambda oid: revalidar(con, oid) if revalidar else (False, "revalidacao desligada"), agora_dt=agora):
            print(f"[fila] id={_id} ok={ok_r} | {info_r}")

    for fid, fcfg in fontes.items():
        if not fcfg.get("habilitada", True) or fid not in coletores:
            continue
        if so_fontes and fid not in so_fontes:
            continue  # tarefa dedicada (ex.: Promobit na Black Friday): as outras fontes nao sao tocadas
        fcfg, em_janela = cfg_efetiva(fcfg, agora)
        if not _vencida(con, fid, float(fcfg.get("intervalo_min", 10)), agora):
            if verbose:
                print(f"[{fid}] ainda no intervalo; pulando")
            continue
        sem_config = "canais" in fcfg and not fcfg["canais"]
        if not sem_config:
            tentou += 1
        prev_ok = _ultimo_ok(con, fid)  # antes de _saude atualizar: mede a JANELA em que a fonte ficou sem ser lida
        _tf = time.perf_counter()
        try:
            ofertas = coletores[fid](fcfg)
        except (FonteErro, Exception) as exc:  # noqa: BLE001 - nenhuma fonte derruba as demais
            _saude(con, fid, False, 0, str(exc)[:300], agora)
            _telemetria(con, agora, fid, "erro", 0, {}, str(exc)[:300])
            total["fontes_erro"] += 1
            print(f"[{fid}] ERRO: {str(exc)[:160]}")
            continue
        t_coleta = round(time.perf_counter() - _tf, 2)
        _saude(con, fid, True, len(ofertas), None, agora)
        for of_ in ofertas:
            of_.coletado_em = agora.strftime("%Y-%m-%d %H:%M")  # collected_at
        transbordo = False
        if fcfg.get("hora_por_primeira_vista"):
            _n, transbordo = hora_por_primeira_vista(fid, ofertas, agora, persistir)
        # LACUNA: se a fonte ficou sem ser lida por MAIS tempo do que a lista alcanca para tras, ofertas foram perdidas.
        cob = qualidade.cobertura_min(ofertas, agora) if ofertas else None
        gap = _minutos_entre(prev_ok, agora)
        alcance = cob if cob is not None else (float(fcfg["cobertura_estimada_min"]) if fcfg.get("cobertura_estimada_min") else None)
        lacuna = bool(gap is not None and alcance is not None and gap > alcance and not fcfg.get("lista_estatica"))
        perdido = round(gap - alcance, 0) if lacuna else 0
        if lacuna or transbordo:
            print(f"[{fid}] LACUNA: {'sem ler por %.0f min com a lista cobrindo %.0f min (~%.0f min podem ter ficado de fora)' % (gap, alcance, perdido) if lacuna else 'lista transbordou entre dois ciclos'}")
            for of_ in ofertas:  # sem como saber quando as sem-hora foram postadas: nunca tratadas como "novas"
                of_.extras = {**(of_.extras or {}), "lacuna_antes": True}
        if not sem_config:  # fonte sem canais configurados nao conta como "ok" (nada foi lido)
            total["fontes_ok"] += 1
        total["ofertas"] += len(ofertas)
        cont: dict[str, int] = {"casadas": 0, "cupons_extraidos": 0, "cupons_aplicados": 0, "cupons_elegiveis": 0}
        descartes: dict[str, int] = {}
        t_classif: list[float] = []
        t_cand: list[float] = []
        for of in ofertas:
            _to = time.perf_counter()
            try:
                r = processar_oferta(con, of, cat, regras, enviar_fn, agora, persistir, diferir=persistir,
                                    verificar_loja=_verificar_loja if (usar_lojas and persistir) else None)
                _tot = (time.perf_counter() - _to) * 1000
                t_classif.append(max(_tot - (r.get("t_candidato_ms") or 0.0), 0.0))
                if r.get("t_candidato_ms") is not None:
                    t_cand.append(r["t_candidato_ms"])
            except Exception as exc:  # noqa: BLE001
                print(f"[{fid}] oferta {of.id_externo} ignorada: {type(exc).__name__}: {exc}")
                descartes["erro_ao_processar"] = descartes.get("erro_ao_processar", 0) + 1
                continue
            cont["cupons_extraidos"] += r.get("cupons", 0)
            cont["cupons_aplicados"] += r.get("cupons_aplicados", 0)
            cont["cupons_elegiveis"] += r.get("cupons_elegiveis", 0)
            if r.get("descarte"):
                descartes[r["descarte"]] = descartes.get(r["descarte"], 0) + 1
            if r.get("produto"):
                total["casadas"] += 1
                cont["casadas"] += 1
                if verbose or (r.get("acao") or "").startswith(("real", "sombra", "falha", "candidato")):
                    print(f"[{fid}] {r['produto']} {r.get('classe')} {r.get('preco_final')} -> {r.get('acao')} | {of.titulo[:70]}")
            if (r.get("acao") or "").startswith("real"):
                total["alertas"] += 1
        if sem_config:
            status = "sem_configuracao"  # nada a ler: nenhum canal habilitado (nao e falha nem ausencia de ofertas)
        else:
            status = "vazia" if not ofertas else "ok"  # "vazia": a fonte respondeu e nao trouxe nada (nao e erro)
        # Cobertura: ate onde a lista alcanca. Menor que o intervalo entre ciclos = ha oferta que sai da lista sem ser vista.
        buraco = cob is not None and cob < float(fcfg.get("intervalo_min", 10))
        if buraco:
            print(f"[{fid}] ATENCAO: a lista cobre so {cob:.0f} min e o ciclo e de {fcfg.get('intervalo_min', 10)} min: pode perder ofertas")
        _telemetria(con, agora, fid, status, len(ofertas),
                    {**cont, "descartes": descartes, "cobertura_min": cob, "buraco": buraco, "lacuna": lacuna, "lacuna_min": gap,
                     "perdido_min": perdido, "transbordo": transbordo, "janela_intensiva": em_janela,
                     "intervalo_efetivo_min": float(fcfg.get("intervalo_min", 10))}, None)
        print(f"[{fid}] {len(ofertas)} itens")
        latencia.registrar("fonte", fonte=fid, t_coleta_s=t_coleta, n=len(ofertas), t_classif_ms_med=_med(t_classif), t_classif_ms_max=round(max(t_classif), 2) if t_classif else None,
                           n_candidatos=len(t_cand), t_candidato_ms_med=_med(t_cand))

    # DESPACHO: rankeia todos os candidatos pendentes e aplica orcamento, anti-rajada, anti-repeticao e substituicao.
    if persistir:
        _td = time.perf_counter()
        revalidar_ligada = regras.get("alertas", {}).get("revalidar_antes_de_enviar", True)
        decisoes = prioridade.despachar(con, regras, enviar_fn, agora,
                                        revalidar=(lambda oid: revalidar_oferta(con, oid)) if revalidar_ligada else None)
        for d in decisoes:
            if d.get("id"):
                print(f"[prioridade] #{d['id']} {d['produto']} {d['classe']} pontuacao {d['score']:.0f} -> {d['estado']}: {d['motivo']}")
        total["alertas"] += sum(1 for d in decisoes if d.get("estado") == "enviado")
        latencia.registrar("despacho", t_despacho_s=round(time.perf_counter() - _td, 3), decisoes=len([d for d in decisoes if d.get("id")]))
        latencia.registrar("ciclo", t_ciclo_s=round(time.perf_counter() - _tc, 2), fontes=tentou)
    print(f"[varredura] {total}")
    con.close()
    return 1 if tentou and total["fontes_ok"] == 0 else 0


def _med(v: list[float]) -> float | None:
    if not v:
        return None
    v = sorted(v)
    return round(v[len(v) // 2], 2)


def _ultimo_ok(con, fonte: str) -> str | None:
    r = con.execute("SELECT ultimo_ok FROM fontes_saude WHERE fonte=?", (fonte,)).fetchone()
    return r["ultimo_ok"] if r and r["ultimo_ok"] else None


def _minutos_entre(antes: str | None, agora: dt.datetime) -> float | None:
    try:
        return round((agora - dt.datetime.strptime(antes, "%Y-%m-%d %H:%M:%S")).total_seconds() / 60.0, 1) if antes else None
    except ValueError:
        return None


def hora_por_primeira_vista(fonte: str, ofertas: list[Oferta], agora: dt.datetime, persistir: bool = True) -> tuple[int, bool]:
    """Fonte SEM hora de publicacao (HardMOB): registra `primeira_vista_em` (first_seen_at) so para ids NUMERICOS maiores que a
    marca-d'agua. `publicado_em` (published_at) CONTINUA VAZIO: a hora em que o radar viu nao e a hora em que foi postado (a postagem
    pode ter passado por moderacao ou o radar pode ter ficado fora do ar). O 1o ciclo so grava a marca.
    Retorna (novos, transbordo): transbordo = todos os itens nao fixos da lista sao novos, ou seja, o ciclo pode ter perdido itens."""
    arq = caminhos.radar_dir() / "marcas_fontes.json"
    try:
        marcas = json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        marcas = {}
    ids = [int(o.id_externo) for o in ofertas if str(o.id_externo).isdigit()]
    if not ids:
        return 0, False
    marca = marcas.get(fonte)
    n = 0
    if marca is not None:
        for o in ofertas:
            if str(o.id_externo).isdigit() and int(o.id_externo) > int(marca):
                o.primeira_vista_em = agora.strftime("%Y-%m-%d %H:%M")
                n += 1
    transbordo = marca is not None and n >= max(1, len(ids) - 2)  # -2: topicos fixos (FAQ etc.) ficam sempre na lista
    if persistir:
        marcas[fonte] = max(max(ids), int(marca or 0))
        arq.write_text(json.dumps(marcas), encoding="utf-8")
    return n, transbordo


def _telemetria(con, agora: dt.datetime, fonte: str, status: str, itens: int, dados: dict[str, Any], erro: str | None) -> None:
    con.execute(
        "INSERT INTO coletas_ciclo (ciclo_em, fonte, status, itens, casadas, cupons_extraidos, cupons_aplicados, descartes_json, erro) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (agora.strftime("%Y-%m-%d %H:%M:%S"), fonte, status, itens, dados.get("casadas", 0), dados.get("cupons_extraidos", 0),
         dados.get("cupons_aplicados", 0),
         json.dumps({"elegiveis": dados.get("cupons_elegiveis", 0), "cobertura_min": dados.get("cobertura_min"), "buraco": bool(dados.get("buraco")),
                     "lacuna": bool(dados.get("lacuna")), "lacuna_min": dados.get("lacuna_min"), "perdido_min": dados.get("perdido_min"),
                     "transbordo": bool(dados.get("transbordo")), "janela_intensiva": bool(dados.get("janela_intensiva")),
                     "intervalo_efetivo_min": dados.get("intervalo_efetivo_min"), **(dados.get("descartes") or {})}, ensure_ascii=False), erro),
    )
    con.commit()


def revalidar_oferta(con, oferta_id: int, baixar=None) -> tuple[bool, str]:
    """Reconsulta a oferta na fonte. So Promobit e revalidavel (pagina individual com status e preco)."""
    row = con.execute("SELECT fonte, url, id_externo, preco_final, preco_anunciado FROM ofertas WHERE id=?", (oferta_id,)).fetchone()
    if not row:
        return False, "oferta nao encontrada"
    from .fontes import gatry, promobit

    kw = {"baixar": baixar} if baixar else {}
    if row["fonte"] == "promobit" and row["url"]:
        return promobit.revalidar(row["url"], row["preco_anunciado"], **kw)
    if row["fonte"] == "gatry":
        return gatry.revalidar(row["id_externo"], row["preco_anunciado"], **kw)
    return False, f"fonte {row['fonte']} nao permite revalidar"
