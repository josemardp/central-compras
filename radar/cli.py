"""Linha de comando do radar: `python -m radar <comando>`.

Comandos principais:
  status               visao geral: jobs, tarefas do Windows, fontes, fila, ultimas ofertas
  executar <job>       roda um job de config/radar_jobs.yaml (trava, timeout, log, registro)
  agendar              --status | --aplicar | --mostrar | --restaurar | --remover
  migrar               aplica/reverte migracoes do banco (--reverter N) e importa o historico antigo
  estatisticas [prod]  menor/maior preco validado em 7/30/90 dias
  produtos             catalogo canonico e rastreadores ligados
  varrer               um ciclo de descoberta de ofertas e cupons (fontes publicas)
  cupom "<texto>"      mostra como o motor interpreta um texto promocional
  fila                 mensagens pendentes de reenvio (WhatsApp)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from . import agenda_windows, caminhos, db, historico, jobs, outbox

TRACKERS = ("rastreador-robos", "rastreador-ares", "rastreador-chuveiro")


def _imprimir(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def cmd_executar(args) -> int:
    return jobs.executar_job(args.job)


def cmd_migrar(args) -> int:
    destino = caminhos.db_path()
    if args.reverter is not None:
        copia = db.backup(destino, motivo="pre-rollback")
        con = db.abrir(migrar_automatico=False)
        desfeitas = db.reverter(con, args.reverter)
        print(f"backup: {copia}\nrevertidas: {desfeitas}\nversao atual: {db.versao_aplicada(con)}")
        con.close()
        return 0
    con = db.abrir()
    print(f"banco: {destino}\nversao do esquema: {db.versao_aplicada(con)} (mais nova: {db.VERSAO_ATUAL})")
    if args.importar_historico or args.reconstruir:
        for nome in TRACKERS:
            arq = caminhos.tracker_dir(nome) / "historico.jsonl"
            r = historico.reconstruir_observacoes(con, nome, arq) if args.reconstruir else historico.importar_para_db(con, nome, arq)
            print(f"{nome}: {r}")
    con.close()
    return 0


def cmd_auditar(args) -> int:
    from . import auditoria

    total = 0
    for nome in TRACKERS:
        for a in auditoria.auditar(nome, caminhos.tracker_dir(nome) / "historico.jsonl"):
            if a["sinal"] == "degradada":
                continue
            total += 1
            print(f"{nome:22s} {a['produto']:24s} {a['coletado_em']} {a['sinal']:20s} {a['detalhe']}"
                  + ("  [corrigido em config/radar_correcoes.yaml]" if a["ja_corrigido"] else "  [SEM CORRECAO]"))
    print(f"{total} leitura(s) suspeita(s) (rodadas degradadas nao contam: ja ficam fora das estatisticas)")
    return 0


def cmd_agendar(args) -> int:
    cfg = jobs.carregar_config()
    if args.job:
        cfg["agendamentos"] = [a for a in cfg.get("agendamentos", []) if a["job"] == args.job]
    nomes = [a["tarefa"] for a in cfg.get("agendamentos", [])]
    if args.mostrar:
        for r in agenda_windows.aplicar(cfg, so_mostrar=True):
            print(f"# --- {r['tarefa']}\n{r['script']}")
        return 0
    if args.aplicar:
        _imprimir(agenda_windows.aplicar(cfg))
        return 0
    if args.restaurar:
        _imprimir(agenda_windows.restaurar_backup(args.restaurar))
        return 0
    if args.remover:
        _imprimir(agenda_windows.remover(args.remover))
        return 0
    real = agenda_windows.estado_tarefas(nomes)
    for ag in cfg.get("agendamentos", []):
        r = real.get(ag["tarefa"], {})
        prox = jobs.proxima_execucao(ag)
        print(f"- {ag['tarefa']} -> job {ag['job']} | desejado: "
              f"{ag.get('horarios') or 'a cada ' + str(ag.get('a_cada_min')) + ' min'}, limite {ag.get('limite_execucao_min')} min")
        if not r.get("existe"):
            print("    no Windows: NAO EXISTE (use: python -m radar agendar --aplicar)")
        else:
            print(f"    no Windows: {r.get('estado')} | limite {r.get('limite')} | ultima {r.get('ultima')} "
                  f"(resultado {r.get('resultado')}) | proxima {r.get('proxima')} | gatilhos {r.get('gatilhos')}")
            print(f"    acao: {r.get('acao')}")
        print(f"    proximo disparo previsto no YAML: {prox:%d/%m %H:%M}" if prox else "")
    return 0


def cmd_fila(args) -> int:
    con = db.abrir()
    for row in outbox.pendentes(con, limite=50):
        print(f"#{row['id']} criado {row['criado_em']} tentativas {row['tentativas']} origem {row['origem']} "
              f"erro: {row['ultimo_erro']}")
    print(f"pendentes: {outbox.contar_pendentes(con)}")
    con.close()
    return 0


def cmd_estatisticas(args) -> int:
    con = db.abrir()
    chaves = [args.produto] if args.produto else [
        r["produto"] for r in con.execute("SELECT DISTINCT produto FROM observacoes ORDER BY produto")
    ]
    if not chaves:
        print("sem observacoes: rode `python -m radar migrar --importar-historico`")
    for k in chaves:
        _imprimir(historico.estatisticas(con, k))
    con.close()
    return 0


def cmd_status(args) -> int:
    from . import status

    return status.imprimir()


def cmd_produtos(args) -> int:
    from . import catalogo

    cat = catalogo.carregar()
    for pid, p in cat["produtos"].items():
        print(f"{pid:26s} {p.get('grupo', ''):10s} {p.get('nome')}  [{p.get('origem', '')}]")
    return 0


def cmd_varrer(args) -> int:
    from . import varredura

    return varredura.executar(enviar=not args.sem_enviar, persistir=not args.sem_persistir, verbose=args.verbose,
                              so_fontes=[f.strip() for f in args.so.split(',')] if args.so else None)


def cmd_testar_envio(args) -> int:
    if not args.confirmo:
        print("Este comando envia UMA mensagem real ao seu WhatsApp. Repita com --confirmo para enviar.")
        return 2
    from . import canais

    texto = f"🧪 *Radar de compras:* teste de envio ({dt.datetime.now():%d/%m %H:%M}). Pode ignorar."
    ok, info = canais.enviar_whatsapp(texto)
    print(f"ok={ok} | {info}")
    return 0 if ok else 1


def cmd_alertas(args) -> int:
    con = db.abrir()
    for r in con.execute(
        "SELECT enviado_em, modo, classe, produto, preco, cupom, status_cupom, detalhe FROM alertas ORDER BY id DESC LIMIT ?", (args.limite,)
    ):
        print(f"{r['enviado_em']} [{r['modo']}] {r['classe']} {r['produto']} R$ {r['preco']} {r['cupom'] or ''} {r['status_cupom']} | {r['detalhe'][:90]}")
    con.close()
    return 0


def cmd_ofertas(args) -> int:
    con = db.abrir()
    filtro, params = ("WHERE produto IS NOT NULL", []) if not args.todas else ("", [])
    for r in con.execute(
        f"SELECT id, detectado_em, fonte, produto, classe, loja, preco_anunciado, preco_final, cupom_codigo, status_cupom, motivo, titulo "
        f"FROM ofertas {filtro} ORDER BY id DESC LIMIT ?", params + [args.limite]
    ):
        print(f"#{r['id']} {r['detectado_em']} {r['fonte']} [{r['classe']}] {r['produto'] or '(cupom de loja)'} {r['loja']} "
              f"anunciado {r['preco_anunciado']} final {r['preco_final']} cupom {r['cupom_codigo'] or '-'} {r['status_cupom'] or ''} | {r['motivo']} | {r['titulo'][:60]}")
    con.close()
    return 0


def cmd_validar(args) -> int:
    """Marca uma oferta como VALIDADA depois de voce conferir no carrinho (unico caminho para VALIDADO)."""
    con = db.abrir()
    row = con.execute("SELECT id, preco_final FROM ofertas WHERE id=?", (args.oferta_id,)).fetchone()
    if not row:
        print("oferta nao encontrada")
        return 2
    con.execute("UPDATE ofertas SET status_cupom='VALIDADO', final_estimado=0, motivo=? WHERE id=?",
                (f"validado por {args.por} em {dt.datetime.now():%d/%m %H:%M}", args.oferta_id))
    # Persistente: o ciclo seguinte recalcula a oferta; sem esta tabela a validacao seria sobrescrita e nunca geraria alerta VALIDADO.
    con.execute("INSERT OR REPLACE INTO validacoes_manuais (oferta_id, por, em, preco_validado) VALUES (?,?,?,?)",
                (args.oferta_id, args.por, db.agora(), row["preco_final"]))
    con.commit()
    print(f"oferta #{args.oferta_id} marcada como VALIDADO ({args.por})")
    con.close()
    return 0


def cmd_whatsapp_grupos(args) -> int:
    from . import whatsapp_grupos as wg

    if args.verificar:
        ok, motivo = wg.verificar(args.verificar)
        print(f"{'AUTORIZADO' if ok else 'RECUSADO'}: {motivo}")
        return 0 if ok else 1
    print(wg.resumo())
    return 0


def cmd_equivalentes(args) -> int:
    from . import cruzamento, equivalentes
    from .fontes import FONTES
    from .varredura import carregar_fontes

    cfg = carregar_fontes()
    ofertas = []
    for fid in ("promobit", "gatry", "pelando", "hardmob"):
        try:
            ofertas += FONTES[fid](cfg.get(fid, {}))
        except Exception as exc:  # noqa: BLE001
            print(f"[{fid}] ERRO: {str(exc)[:100]}")
    precos, _ = cruzamento.carregar_precos_atuais()
    melhores = {}
    for classe, ids in {"ares_12k": ("elgin_12k", "agratto_12k", "midea_lite_12k", "midea_ecomaster_12k"), "ares_18k": ("philco_18k", "elgin_18k")}.items():
        v = [min(p["preco"] for p in precos[i]) for i in ids if i in precos]
        if v:
            melhores[classe] = min(v)
    res = equivalentes.levantar(ofertas, melhores)
    print(f"seu melhor preco atual por classe: {melhores}")
    print(f"equivalentes encontrados agora: {len(res)} (informativo, NUNCA gera alerta)")
    for r in res:
        marca = "MAIS BARATO" if r["mais_barato_que_o_seu"] else "nao e mais barato"
        print(f"  [{marca}] {r['classe']}: R$ {r['preco']:.2f} na {r['loja']} (seu melhor: R$ {r['seu_melhor_preco']}; "
              f"diferenca {r['economia']} = {r['economia_pct']}%) | visto em {r['n_fontes']} fonte(s): {', '.join(r['fontes'])} | {r['publicado_em']}\n      {r['titulo']}\n      {r['url']}\n      ! {r['aviso']}")
    return 0


def cmd_qualidade(args) -> int:
    from . import qualidade
    from .fontes import FONTES
    from .varredura import carregar_fontes

    cfg = carregar_fontes()
    nomes = ("promobit", "gatry", "pelando", "hardmob", "meliuz")
    vivo = qualidade.medir_ao_vivo({n: FONTES[n] for n in nomes}, cfg)
    con = db.abrir()
    est = qualidade.estabilidade(con, args.horas)
    con.close()
    if args.json:
        print(json.dumps({"ao_vivo": vivo, "estabilidade": est}, ensure_ascii=False, indent=2, default=str))
        return 0
    print("== QUALIDADE DOS COLETORES (medida ao vivo agora + historico de ciclos)")
    print("(completude medida so sobre OFERTAS DE PRODUTO; cupons de loja contados a parte)")
    print(f"{'fonte':10s} {'ofertas':>7s} {'cupons':>6s} {'preco%':>7s} {'url%':>6s} {'hora%':>6s} {'loja%':>6s} {'frescas6h%':>10s} {'idade_med':>9s} {'cobertura':>9s} {'lat_s':>6s}")
    for f in nomes:
        c = vivo["completude"][f]
        if not c.get("total_itens"):
            print(f"{f:10s} sem itens | erro: {vivo['erros'].get(f)}")
            continue
        if not c.get("n"):
            print(f"{f:10s} {0:7d} {c['cupons_de_loja']:6d}   (so cupons de loja)")
            continue
        print(f"{f:10s} {c['n']:7d} {c['cupons_de_loja']:6d} {c['preco_pct']:7.1f} {c['url_pct']:6.1f} {c['hora_pct']:6.1f} {c['loja_pct']:6.1f} "
              f"{str(c['frescas_6h_pct']):>10s} {str(c['idade_mediana_min']):>9s} {str(c['cobertura_min']):>9s} {vivo['latencia_s'][f]:6.1f}")
    print("  idade_med e cobertura em minutos; cobertura = ate onde a lista alcanca (tem que ser MAIOR que o intervalo entre ciclos, senao ha buracos)")
    print("\nValor marginal (itens que so aquela fonte traz; Meliuz fora por ser so cupom de loja):")
    for f, s in vivo["sobreposicao"].items():
        print(f"  {f:10s} {s['itens']:3d} itens, {s['unicos']:3d} unicos ({s['unicos_pct']}%)")
    print(f"\nEstabilidade (ultimas {args.horas:.0f} h, de coletas_ciclo):")
    for f, s in est.items():
        print(f"  {f:17s} ciclos {s['ciclos']:3d} | disponibilidade {s['disponibilidade_pct']}% | erros {s['erros']} | itens media {s['itens_media']} "
              f"min/max {s['itens_min_max']} | variacao {s['variacao_itens_pct']}%")
    return 0


def cmd_telegram_status(args) -> int:
    from . import telegram_conta as tc
    from .varredura import carregar_fontes

    canais = (carregar_fontes().get("telegram_usuario") or {}).get("canais") or []
    print(f"credenciais (api_id/api_hash) gravadas: {'SIM' if tc.arq_credenciais().exists() else 'NAO'}  (o valor nunca e exibido)")
    print(f"sessao autenticada (arquivo .session):   {'SIM' if Path(str(tc.arq_sessao()) + '.session').exists() else 'NAO'}")
    print(f"canais autorizados em radar_fontes.yaml:  {len(canais)}")
    positivos = [c for c in canais if int(c.get("id", -1)) >= 0]
    if positivos:
        print(f"ATENCAO: {len(positivos)} id(s) positivo(s) na lista = conversa privada. O radar RECUSA esses ids; remova-os de radar_fontes.yaml.")
    print(f"checkpoints (ultimo id lido por canal):   {tc.ler_checkpoints() or 'nenhum'}")
    try:
        import telethon
        print(f"biblioteca telethon: {telethon.__version__}")
    except ImportError:
        print("biblioteca telethon: NAO instalada neste Python (python -m pip install --user telethon)")
    if not tc.tem_credenciais():
        print("\nProximo passo (seu): docs/ecossistema/12-telegram-passo-a-passo.md")
    elif not canais:
        print("\nProximo passo: python -m radar telegram-listar  e colar so os canais desejados em config/radar_fontes.yaml")
    return 0


def cmd_git_escopo(args) -> int:
    from . import git_escopo as ge

    if args.baseline:
        p = ge.gravar_baseline()
        print(f"foto (SHA-256) dos arquivos de OUTRA sessao: {p}\n(a primeira foto nunca e trocada; use --verificar para comparar)")
        return 0
    if args.verificar:
        v = ge.verificar_alheios()
        print(json.dumps(v, ensure_ascii=False, indent=1))
        return 0 if v["intacto"] else 1
    if args.backup_completo:
        z1, z2 = ge.backup_codigo(), ge.backup_alheios()
        print(f"backup do codigo do radar: {z1} ({z1.stat().st_size // 1024} KB)\ncopia (leitura) dos arquivos de outra sessao: {z2} ({z2.stat().st_size // 1024} KB)")
        t = ge.testar_restauracao(z1)
        print(f"teste de restauracao do backup do radar: zip integro={t['zip_integro']} arquivos={t['arquivos']} testes={t['modulos_de_teste']} saida={t['codigo_saida']} | {' '.join(t['resumo'])}")
        return 0 if t["codigo_saida"] == 0 and t["zip_integro"] else 1
    if args.manifesto:
        m = ge.manifesto()
        print(f"HEAD {m['head']}\n\n== ENTRA NO COMMIT DO RADAR ({len(m['entra_no_commit'])} arquivos)")
        for c in m["entra_no_commit"]:
            print(f"   {c}")
        print(f"\n== STATUS.md (arquivo compartilhado): entram SO estas secoes ({m['status_md']['linhas_adicionadas']} linhas): ")
        for s in m["status_md"]["secoes_do_radar"]:
            print(f"   + {s}")
        print("   NAO entram (de outra sessao):", m["status_md"]["secoes_de_outra_sessao_excluidas"])
        print(f"\n== NAO ENTRA (outra sessao: {len(m['nao_entra_outra_sessao'])} arquivos)")
        for c in m["nao_entra_outra_sessao"]:
            print(f"   {c}")
        print(f"\n== sem dono claro: {m['sem_dono_claro'] or 'nenhum'}")
        print(f"\nvalidacao do patch do STATUS.md (so --check, nada aplicado): {m['validacao_patch']}")
        arq = caminhos.backups_dir() / "STATUS.radar.patch"
        arq.write_text(m["patch_status"], encoding="utf-8", newline="")
        print(f"patch salvo (fora do repositorio): {arq}")
        return 0
    if args.backup:
        z = ge.backup_codigo()
        print(f"backup do codigo do radar (fora do Git): {z} ({z.stat().st_size // 1024} KB)")
        return 0
    r = ge.levantar()
    print(f"HEAD {r['head']} | stash: {r['stash']} | (somente leitura: nada foi alterado)")
    for rotulo, chave in (("DO RADAR", "radar"), ("DE OUTRA SESSAO (nao tocar)", "outra_sessao"), ("MISTO (arquivo compartilhado)", "misto"),
                          ("SEM DONO CLARO (revisar)", "desconhecido")):
        print(f"\n-- {rotulo}: {len(r[chave])}")
        for c in r[chave][:60]:
            print(f"   {c}")
    if r["secoes_status"]:
        print("\n-- Secoes adicionadas ao STATUS.md:")
        for s in r["secoes_status"]:
            print(f"   [{s['dono']}] {s['secao'][:90]}")
    print("\n-- Comandos sugeridos para o SEU commit do radar (nada executado):")
    for c in ge.comandos_sugeridos(r):
        print(f"   {c}")
    return 0


def cmd_piloto(args) -> int:
    from . import piloto, ranking

    con = db.abrir()
    try:
        print(piloto.painel(con, ranking.carregar_regras(), dt.datetime.now(), args.horas))
    finally:
        con.close()
    return 0


def cmd_conferir(args) -> int:
    from . import lojas

    con = db.abrir()
    try:
        r = lojas.conferir_oferta(con, args.oferta_id)
    except ValueError as exc:
        print(str(exc))
        return 2
    finally:
        con.close()
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str) if args.json else lojas.formatar_conferencia(r))
    return 0


def cmd_teste_entrega(args) -> int:
    from . import ativacao

    r = ativacao.teste_entrega(confirmo=args.confirmo, de_novo=args.de_novo)
    if not r["enviado"] and "info" not in r:
        print(r["previa"])
        print(f"\n[{r['chars']} caracteres] {r['motivo']}")
        if not args.confirmo:
            print("Para ENVIAR este teste UNICO ao seu WhatsApp (e medir a latencia real): python -m radar teste-entrega --confirmo")
        return 0 if not args.confirmo else 1
    print(f"enviado={r['enviado']} | confirmado no chat={r['confirmado_no_chat']} | criacao->inicio {r['espera_s']} s | envio {r['duracao_s']} s | ponta a ponta {r['ponta_a_ponta_s']} s")
    print(f"canal: {r['info']}")
    return 0 if r["enviado"] else 1


def cmd_ativacao(args) -> int:
    from . import ativacao

    if args.ensaio_kill_switch:
        itens = ativacao.ensaio_kill_switch()
        for i in itens:
            print(f"  [{i['status']:6s}] {i['id']} {i['nome']}: {i['detalhe']}")
        return 0 if all(i["status"] == "OK" for i in itens) else 1
    if args.desligar:
        ok, info = ativacao.desligar()
        print(f"{'DESLIGADO' if ok else 'FALHOU'}: {info}")
        return 0 if ok else 1
    itens = ativacao.verificar()
    print(ativacao.formatar(itens))
    return 0 if ativacao.veredito(itens).startswith("APTO") else 1


def cmd_latencia(args) -> int:
    from . import latencia
    import yaml

    con = db.abrir()
    fontes_cfg = (yaml.safe_load((caminhos.RAIZ / "config" / "radar_fontes.yaml").read_text(encoding="utf-8")) or {}).get("fontes") or {}
    a = latencia.analisar(con, args.horas, dt.datetime.now(), fontes_cfg)
    con.close()
    print(latencia.formatar(a))
    return 0


def cmd_simular_prioridade(args) -> int:
    from . import simulacao

    res = simulacao.simular(historico_real=not args.sintetico)
    print(simulacao.formatar(res, detalhe=not args.resumo))
    print(f"\n{'TODAS AS SITUACOES COMO ESPERADO' if res['todas_ok'] else 'HA SITUACAO FORA DO ESPERADO'} ({sum(1 for s in res['situacoes'] if s['ok'])}/{len(res['situacoes'])})")
    return 0 if res["todas_ok"] else 1


def cmd_lacunas(args) -> int:
    from . import qualidade
    import yaml

    con = db.abrir()
    fontes_cfg = (yaml.safe_load((caminhos.RAIZ / "config" / "radar_fontes.yaml").read_text(encoding="utf-8")) or {}).get("fontes") or {}
    res = qualidade.lacunas_historicas(con, args.horas, dt.datetime.now(), fontes_cfg)
    con.close()
    print(f"== LACUNAS DE COLETA nas ultimas {args.horas:.0f} h (janela sem ler a fonte maior que o alcance da lista dela)")
    if not res:
        print("  sem ciclos registrados no periodo")
    for fonte, d in res.items():
        print(f"  {fonte:18s} {d['ciclos']:3d} ciclos | maior intervalo sem ler {d['maior_intervalo_min']} min | lacunas {len(d['lacunas'])} | ate ~{d['perdido_total_min']} min de ofertas podem ter ficado de fora")
        for j in d["lacunas"]:
            print(f"      {j['de'][5:16]} -> {j['ate'][5:16]}: sem ler {j['sem_ler_min']} min, a lista alcancava {j['alcance_min']} min -> {j['situacao']}"
                  + (f" (~{j['perdido_min']} min perdidos)" if j["perdido_min"] else ""))
    return 0


def cmd_prioridade(args) -> int:
    from . import prioridade, ranking

    con = db.abrir()
    regras = ranking.carregar_regras()
    p = prioridade.config(regras)
    usados = prioridade._usados_hoje(con, dt.datetime.now())
    al = regras.get("alertas", {})
    print(f"Alertas: {'LIGADOS e homologados em ' + str(al['homologado_em']) if al.get('enviar') and al.get('homologado_em') else 'EM SOMBRA (selecionado_sombra = o que SERIA enviado)'}")
    print(f"Orcamento de hoje: comum {usados['comum']}/{p['orcamento_diario']} | critico {usados['critico']}/{p['orcamento_critico_diario']} | "
          f"excecao {usados['excecao']}/{p['orcamento_excecao_diario']} | max por ciclo {p['max_por_ciclo']} | pontuacao minima {p['score_minimo']}")
    linhas = prioridade.painel(con, horas=args.horas)
    print(f"\nCandidatos das ultimas {args.horas:.0f} h: {len(linhas)}")
    for r in linhas[:args.limite]:
        print(f"  #{r['id']:<4d} {r['criado_em'][5:16]} {r['produto']:24s} {r['classe']:7s} pontuacao {r['score']:5.1f} R$ {r['preco_final']:>8.2f} "
              f"{'(hora incerta) ' if r['hora_incerta'] else ''}-> {r['estado']}: {str(r['motivo'] or '')[:70]}")
    con.close()
    return 0


def cmd_homologar(args) -> int:
    from . import cenarios

    if args.reais:
        res = cenarios.demonstrar_ofertas_reais()
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
            return 0
        print("== OFERTAS REAIS (historico/documentadas) REENCENADAS pela cadeia | historico REAL de precos | alertas so em memoria | nada enviado")
        for o in res["ofertas"]:
            print(f"  {o['id']} {o['loja'] or '-':14s} R$ {o['preco']:>8.2f} | reconheceu {str(o['produto']):24s} esperado {str(o['esperado']):24s} | "
                  f"classe {str(o['classe']):6s} {str(o['validacao']):14s} | min. historico {o['minimo_historico']} ({o['obs_historico']} obs) | {str(o['acao'])[:48]}")
        print(f"\nmensagens que SAIRIAM (se os alertas estivessem homologados): {res['mensagens_que_sairiam']}")
        return 0
    if args.enviar_teste_whatsapp and not args.confirmo:
        print("Isto envia UMA mensagem, claramente marcada como TESTE, ao seu WhatsApp. Repita com --confirmo.")
        return 2
    res = cenarios.executar_cenarios(enviar_teste_whatsapp=args.enviar_teste_whatsapp)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
        return 0 if res["ok"] else 1
    print(f"== HOMOLOGACAO DA CADEIA (cenarios sinteticos, banco temporario, alertas reais DESLIGADOS) | {res['aprovados']}/{res['total']} ok")
    for c in res["cenarios"]:
        print(f"  [{'OK ' if c['ok'] else 'ERRO'}] {c['id']} {c['cenario']}\n        esperado: {c['esperado']}\n        obtido:   {c['obtido']}")
    if res["envio_teste"] is not None:
        print(f"\nenvio de teste ao seu WhatsApp: {res['envio_teste']}")
    return 0 if res["ok"] else 1


def cmd_cruzar(args) -> int:
    """Busca AO VIVO os cupons de loja nas fontes e cruza com os precos atuais (ultima coleta boa) dos 12 produtos."""
    from . import cruzamento, ranking
    from .fontes import FONTES

    precos, datas = cruzamento.carregar_precos_atuais()
    cfg_fontes = __import__("radar.varredura", fromlist=["carregar_fontes"]).carregar_fontes()
    ofertas = []
    for fid in ("promobit", "gatry", "meliuz", "pelando"):
        try:
            ofertas += FONTES[fid](cfg_fontes.get(fid, {}))
        except Exception as exc:  # noqa: BLE001
            print(f"[{fid}] ERRO: {str(exc)[:100]}")
    perfil = ranking.carregar_regras().get("perfil_comprador")
    res = cruzamento.cruzar(ofertas, precos, perfil=perfil)
    rs = cruzamento.resumo(res)
    if args.json:
        print(json.dumps({"resumo": {k: v for k, v in rs.items() if k != "oportunidades"}, "pares": res}, ensure_ascii=False, indent=2, default=str))
        return 0
    print(f"publicacoes lidas: {len(ofertas)} | pares cupom-de-loja x produto-com-preco-na-loja: {rs['pares_cupom_produto']} (sem duplicatas)")
    print(f"  CANDIDATO (vale testar no carrinho): {rs[cruzamento.CANDIDATO]} | indeterminado: {rs[cruzamento.INDETERMINADO]} | inaplicavel: {rs[cruzamento.INAPLICAVEL]}")
    e = rs["estagios"]
    print(f"  ESTAGIOS: descoberto {e['descoberto']} | potencialmente elegivel {e['potencialmente_elegivel']} (economia so ESTIMADA) | "
          f"validado {e['validado']} (so via `radar validar`) | expirado {e['expirado']}")
    for m, n in sorted(rs["motivos_inaplicavel"].items(), key=lambda kv: -kv[1]):
        print(f"    inaplicavel x{n}: {m}")
    for m, n in sorted(rs["motivos_indeterminado"].items(), key=lambda kv: -kv[1]):
        print(f"    indeterminado x{n}: {m}")
    print("\nPrecos usados (ultima coleta boa):", {k: v for k, v in datas.items()})
    print("\n-- CANDIDATOS A TESTE (preco com cupom ESTIMADO; NADA confirmado em carrinho)")
    for r in rs["candidatos"]:
        print(f"  {r['produto']} na {r['loja']}: R$ {r['preco_atual_na_loja']:.2f} -> ~R$ {r['preco_com_cupom_estimado']:.2f} "
              f"(economia ~R$ {r['economia_estimada']:.2f}; melhor atual R$ {r['melhor_preco_atual']:.2f}; "
              f"{'MELHOR QUE O ATUAL' if r['melhor_que_atual'] else 'nao supera o melhor atual'}) | cupom {r['cupom']} [{r['status_cupom']}] | {r['titulo']}\n      {r['motivo']}")
    if not rs["candidatos"]:
        print("  nenhum")
    if args.todos:
        print("\n-- TODOS OS PARES")
        for r in res:
            print(f"  [{r['aplicabilidade']}] {r['produto']}/{r['loja']} x {r['cupom']} ({r['cupom_loja']}): {r['motivo'][:100]}")
    return 0


def cmd_avaliar(args) -> int:
    from . import avaliacao

    rel = avaliacao.avaliar()
    print(json.dumps(rel, ensure_ascii=False, indent=2, default=str) if args.json else avaliacao.formatar(rel))
    return 0


def cmd_efetividade(args) -> int:
    from . import efetividade

    con = db.abrir()
    rel = efetividade.gerar(con, args.horas)
    print(json.dumps(rel, ensure_ascii=False, indent=2, default=str) if args.json else efetividade.formatar(rel))
    con.close()
    return 0


def cmd_recuperar(args) -> int:
    from . import recuperacao

    cfg = jobs.carregar_config()
    if args.simular:
        con = db.abrir()
        for a in recuperacao.atrasados(cfg, con):
            print(f"atrasado: {a['job']} slot {a['slot']:%d/%m %H:%M} ({a['atraso_min']} min) -> tarefa {a['tarefa']}")
        con.close()
        return 0
    feitos = recuperacao.recuperar(cfg)
    for f in feitos:
        print(f"[recuperar] {f['job']} slot {f['slot']:%d/%m %H:%M} atrasado {f['atraso_min']} min: "
              f"{'tarefa disparada' if f['disparado'] else 'FALHOU'} ({f['info']})")
    if not feitos:
        print("[recuperar] nenhum relatorio atrasado")
    return 0


def cmd_cupom(args) -> int:
    from . import cupons

    cs = cupons.extrair_cupons(args.texto)
    _imprimir([c.__dict__ for c in cs])
    _imprimir(cupons.extrair_condicoes(args.texto))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="radar", description="Radar de compras da Central de Compras")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="visao geral").set_defaults(fn=cmd_status)

    p = sub.add_parser("executar", help="roda um job")
    p.add_argument("job")
    p.set_defaults(fn=cmd_executar)

    p = sub.add_parser("agendar", help="tarefas do Windows")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--aplicar", action="store_true", help="cria/atualiza as tarefas conforme o YAML")
    g.add_argument("--mostrar", action="store_true", help="mostra o script PowerShell sem aplicar")
    g.add_argument("--restaurar", metavar="TAREFA", help="reimporta o XML original salvo antes do cutover")
    g.add_argument("--remover", metavar="TAREFA", help="remove uma tarefa")
    p.add_argument("--job", help="limita a operacao aos agendamentos deste job")
    p.set_defaults(fn=cmd_agendar)

    p = sub.add_parser("migrar", help="esquema do banco e importacao do historico")
    p.add_argument("--reverter", type=int, metavar="VERSAO", help="rollback ate a versao indicada")
    p.add_argument("--importar-historico", action="store_true")
    p.add_argument("--reconstruir", action="store_true", help="recria `observacoes` a partir dos JSONL brutos (+ correcoes)")
    p.set_defaults(fn=cmd_migrar)

    p = sub.add_parser("auditar", help="varre o historico bruto atras de leituras suspeitas (nao altera nada)")
    p.set_defaults(fn=cmd_auditar)

    p = sub.add_parser("estatisticas")
    p.add_argument("produto", nargs="?")
    p.set_defaults(fn=cmd_estatisticas)

    sub.add_parser("produtos").set_defaults(fn=cmd_produtos)
    sub.add_parser("fila").set_defaults(fn=cmd_fila)

    p = sub.add_parser("varrer", help="um ciclo de descoberta de ofertas")
    p.add_argument("--sem-enviar", action="store_true", help="classifica e registra, mas nao envia ao WhatsApp")
    p.add_argument("--sem-persistir", action="store_true", help="nao grava nada no banco")
    p.add_argument("--so", metavar="FONTES", help="le SO estas fontes (ex.: promobit); as outras nao sao tocadas (tarefa dedicada da Black Friday)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=cmd_varrer)

    p = sub.add_parser("alertas", help="alertas enviados, em sombra ou com falha")
    p.add_argument("--limite", type=int, default=20)
    p.set_defaults(fn=cmd_alertas)

    p = sub.add_parser("ofertas", help="ofertas casadas com o catalogo")
    p.add_argument("--limite", type=int, default=20)
    p.add_argument("--todas", action="store_true", help="inclui cupons de loja")
    p.set_defaults(fn=cmd_ofertas)

    p = sub.add_parser("validar", help="marca oferta como VALIDADA apos conferir no carrinho")
    p.add_argument("oferta_id", type=int)
    p.add_argument("--por", required=True, help='ex.: "carrinho Amazon 21/11"')
    p.set_defaults(fn=cmd_validar)

    p = sub.add_parser("testar-envio", help="envia UMA mensagem de teste ao seu WhatsApp (exige --confirmo)")
    p.add_argument("--confirmo", action="store_true")
    p.set_defaults(fn=cmd_testar_envio)

    sub.add_parser("telegram-login", help="PASSO SEU: autentica a sessao Telegram do radar (rode no seu PowerShell)").set_defaults(
        fn=lambda a: __import__("radar.telegram_conta", fromlist=["login"]).login())
    p = sub.add_parser("telegram-listar", help="lista os CANAIS (nunca conversas privadas; sem ler mensagens) para montar a lista de autorizados")
    p.add_argument("--grupos", action="store_true", help="inclui tambem grupos (so os nomes; o radar so le o que voce colar na lista)")
    p.set_defaults(fn=lambda a: __import__("radar.telegram_conta", fromlist=["listar"]).listar(incluir_grupos=a.grupos))

    p = sub.add_parser("whatsapp-grupos", help="mostra a lista de autorizacao de grupos (o radar nao le nenhum por padrao)")
    p.add_argument("--verificar", metavar="NOME", help="diz se um nome de grupo seria autorizado")
    p.set_defaults(fn=cmd_whatsapp_grupos)

    sub.add_parser("equivalentes", help="ofertas de splits EQUIVALENTES (outra marca) mais baratas que o seu melhor preco; so informativo").set_defaults(fn=cmd_equivalentes)

    p = sub.add_parser("qualidade-fontes", help="completude, frescor, valor marginal, latencia e estabilidade dos coletores")
    p.add_argument("--horas", type=float, default=24.0)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_qualidade)

    sub.add_parser("telegram-status", help="estado da integracao Telegram (sem mostrar segredos)").set_defaults(fn=cmd_telegram_status)

    p = sub.add_parser("git-escopo", help="separa (so lendo o Git) o que e do radar e o que e de outra sessao; --backup salva o codigo fora do Git")
    p.add_argument("--backup", action="store_true")
    p.add_argument("--backup-completo", action="store_true", help="zip do radar + copia (leitura) do que e de outra sessao + TESTE de restauracao")
    p.add_argument("--baseline", action="store_true", help="grava a foto SHA-256 dos arquivos de OUTRA sessao (a primeira nunca e trocada)")
    p.add_argument("--verificar", action="store_true", help="compara agora com a foto: prova que nada de outra sessao foi alterado")
    p.add_argument("--manifesto", action="store_true", help="lista EXATA do que entra no commit do radar + patch do STATUS.md (nada executado)")
    p.set_defaults(fn=cmd_git_escopo)

    p = sub.add_parser("piloto", help="acompanhamento do MODO PILOTO: modo atual, limites, candidatos, o que ficou fora e os envios")
    p.add_argument("--horas", type=float, default=24.0)
    p.set_defaults(fn=cmd_piloto)

    p = sub.add_parser("conferir", help="inspecao de UMA oferta registrada: fonte, loja e os tres niveis de preco (anunciado, confirmado, entregue)")
    p.add_argument("oferta_id", type=int)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_conferir)

    p = sub.add_parser("teste-entrega", help="UM teste de entrega ao SEU WhatsApp com medicao de latencia; sem --confirmo so mostra a previa")
    p.add_argument("--confirmo", action="store_true", help="autoriza o envio de 1 mensagem rotulada TESTE ao seu proprio chat")
    p.add_argument("--de-novo", action="store_true", help="permite um segundo teste no mesmo dia")
    p.set_defaults(fn=cmd_teste_entrega)

    p = sub.add_parser("ativacao", help="verificacao PREVIA da ativacao dos alertas reais (somente leitura); --desligar e o kill switch")
    p.add_argument("--desligar", action="store_true", help="poe enviar=false e homologado_em=null em config/radar_regras.yaml (so desliga)")
    p.add_argument("--ensaio-kill-switch", action="store_true", help="ensaia o desligamento e a limpeza da fila em copias temporarias (nada real e tocado)")
    p.set_defaults(fn=cmd_ativacao)

    p = sub.add_parser("latencia", help="latencia da publicacao ate o WhatsApp (separa MEDIDO de ESTIMADO) e chance de ler promocao curta")
    p.add_argument("--horas", type=float, default=24.0)
    p.set_defaults(fn=cmd_latencia)

    p = sub.add_parser("simular-prioridade", help="simula a politica de prioridade com ofertas documentadas (banco temporario, nada enviado)")
    p.add_argument("--sintetico", action="store_true", help="usa historico sintetico em vez do historico real desta maquina")
    p.add_argument("--resumo", action="store_true", help="so o resultado de cada situacao, sem a linha do tempo")
    p.set_defaults(fn=cmd_simular_prioridade)

    p = sub.add_parser("lacunas", help="janelas em que uma fonte ficou sem ser lida por mais tempo do que a lista dela alcanca")
    p.add_argument("--horas", type=float, default=24.0)
    p.set_defaults(fn=cmd_lacunas)

    p = sub.add_parser("prioridade", help="fila de candidatos a alerta, pontuacao e orcamento de notificacoes de hoje")
    p.add_argument("--horas", type=float, default=24.0)
    p.add_argument("--limite", type=int, default=30)
    p.set_defaults(fn=cmd_prioridade)

    p = sub.add_parser("homologar", help="roda a cadeia de alerta com cenarios sinteticos (banco temporario; nada enviado por padrao)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--reais", action="store_true", help="reencena ofertas REAIS (corpus) com o seu historico real de precos; nada enviado")
    p.add_argument("--enviar-teste-whatsapp", action="store_true", help="envia UMA mensagem rotulada como TESTE ao seu proprio chat")
    p.add_argument("--confirmo", action="store_true")
    p.set_defaults(fn=cmd_homologar)

    p = sub.add_parser("cruzar", help="cruza cupons de loja (ao vivo) com os precos atuais dos 12 produtos; so estimativa")
    p.add_argument("--json", action="store_true")
    p.add_argument("--todos", action="store_true", help="lista tambem os pares inaplicaveis/indeterminados")
    p.set_defaults(fn=cmd_cruzar)

    p = sub.add_parser("avaliar", help="precisao/recuperacao do reconhecimento sobre a amostra rotulada")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_avaliar)

    p = sub.add_parser("efetividade", help="relatorio: publicacoes, ofertas dos 12 produtos, cupons e motivos de descarte")
    p.add_argument("--horas", type=float, default=24.0)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_efetividade)

    p = sub.add_parser("recuperar", help="dispara relatorio programado que ficou sem execucao")
    p.add_argument("--simular", action="store_true", help="so mostra o que seria recuperado")
    p.set_defaults(fn=cmd_recuperar)

    p = sub.add_parser("cupom", help="interpreta um texto promocional")
    p.add_argument("texto")
    p.set_defaults(fn=cmd_cupom)

    args = ap.parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
