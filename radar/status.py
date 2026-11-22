"""Painel de texto: tudo que o radar sabe sobre si mesmo, num comando."""

from __future__ import annotations

import datetime as dt

from . import agenda_windows, caminhos, catalogo, db, jobs, maquina, outbox, ranking


def imprimir() -> int:
    con = db.abrir()
    cfg = jobs.carregar_config()
    cat = catalogo.carregar()
    print(f"== RADAR DE COMPRAS | {dt.datetime.now():%d/%m/%Y %H:%M} | banco v{db.versao_aplicada(con)} | {caminhos.db_path()}")
    pode, motivo = maquina.pode_rodar()
    print(f"Maquina: {maquina.hostname()} | oficial: {maquina.oficial() or '(sem trava)'} | {'ATIVA' if pode else 'INATIVA'}: {motivo}")
    alr = ranking.carregar_regras().get("alertas", {})
    print(f"Alertas urgentes: {'LIGADOS e homologados em ' + str(alr['homologado_em']) if alr.get('enviar') and alr.get('homologado_em') else 'EM SOMBRA (so registram; ativacao explicita pendente)'}")

    print("\n-- Produtos monitorados (catalogo)")
    grupos = catalogo.produtos_por_grupo(cat)
    for g, ids in grupos.items():
        print(f"  {g}: {', '.join(ids)}")

    print("\n-- Jobs")
    for jid, j in cfg["jobs"].items():
        e = con.execute("SELECT * FROM jobs_estado WHERE job=?", (jid,)).fetchone()
        ag = next((a for a in cfg["agendamentos"] if a["job"] == jid), None)
        prox = jobs.proxima_execucao(ag) if ag else None
        print(f"  {jid}: ultima {e['ultima_execucao'] if e else 'nunca'} ({e['ultimo_status'] if e else '-'}), "
              f"ultimo sucesso {e['ultimo_sucesso'] if e else '-'}, falhas seguidas {e['falhas_consecutivas'] if e else 0}"
              f" | proxima {prox:%d/%m %H:%M}" if prox else f"  {jid}: sem agendamento")

    print("\n-- Tarefas no Windows")
    real = agenda_windows.estado_tarefas([a["tarefa"] for a in cfg["agendamentos"]])
    for nome, r in real.items():
        ag = next((a for a in cfg["agendamentos"] if a["tarefa"] == nome), {})
        if not r.get("existe") and ag.get("inicio"):
            print(f"  {nome}: AINDA NAO CRIADA (janela {ag['inicio']} ate {ag.get('fim')}; para criar: python -m radar agendar --aplicar --job varredura_promobit_bf)")
        elif not r.get("existe"):
            print(f"  {nome}: NAO EXISTE no Windows")
        else:
            print(f"  {nome}: {r.get('estado')} | proxima {r.get('proxima')} | ultima {r.get('ultima')} (resultado {r.get('resultado')}) | limite {r.get('limite')}")

    print("\n-- Fontes (varredura)")
    linhas = con.execute("SELECT * FROM fontes_saude ORDER BY fonte").fetchall()
    for f in linhas:
        print(f"  {f['fonte']}: ultimo ok {f['ultimo_ok']} | itens {f['itens_ultima']} | falhas seguidas {f['falhas_consecutivas']}"
              + (f" | erro: {f['erro_msg'][:80]}" if f["erro_msg"] else ""))
    if not linhas:
        print("  (nenhuma varredura executada ainda)")

    from . import varredura

    pb = varredura.carregar_fontes().get("promobit") or {}
    jb = pb.get("janela_intensiva")
    if jb:
        _, ativa = varredura.cfg_efetiva(pb, dt.datetime.now())
        print(f"  janela intensiva do Promobit ({jb['de']} ate {jb['ate']}, a cada {jb.get('intervalo_min')} min, {pb.get('paginas_recentes')} paginas): "
              f"{'ATIVA AGORA' if ativa else 'fora da janela (leitura normal)'}; volta sozinha ao normal depois do fim")

    print(f"\n-- Fila de reenvio do WhatsApp: {outbox.contar_pendentes(con)} pendente(s)")

    print("\n-- Execucoes recentes")
    for r in con.execute("SELECT job, passo, inicio, status FROM execucoes ORDER BY id DESC LIMIT 6"):
        print(f"  {r['inicio']} {r['job']}/{r['passo'] or '-'}: {r['status']}")

    print("\n-- Alertas de hoje")
    hoje = dt.datetime.now().strftime("%Y-%m-%d")
    n = {m: c for m, c in con.execute("SELECT modo, COUNT(*) FROM alertas WHERE enviado_em >= ? GROUP BY modo", (hoje,))}
    print(f"  enviados {n.get('real', 0)} | em sombra {n.get('sombra', 0)} | falhas {n.get('falha', 0)}")

    print("\n-- Melhores ofertas vistas (ultimas 24h, por classe)")
    corte = (dt.datetime.now() - dt.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    for r in con.execute(
        "SELECT produto, classe, loja, preco_final, status_cupom, titulo FROM ofertas WHERE produto IS NOT NULL AND detectado_em >= ? "
        "ORDER BY CASE classe WHEN 'CRITICA' THEN 4 WHEN 'ALTA' THEN 3 WHEN 'MEDIA' THEN 2 ELSE 1 END DESC, score DESC LIMIT 6", (corte,)):
        print(f"  [{r['classe']}] {r['produto']} {r['loja']} R$ {r['preco_final']} {r['status_cupom'] or ''} | {r['titulo'][:60]}")
    con.close()
    return 0
