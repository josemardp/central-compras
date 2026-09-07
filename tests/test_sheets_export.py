"""Export pra Google Sheets: payload puro e o POST pro Web App.

`comercial_valor`/`atributo_valor` sao a MESMA fonte que o HTML do dashboard
usa (spec_comparison_section) - aqui so confere que o dado puro (sem markup)
segue a mesma regra: cortado nunca ganha estrela, nota ausente nunca vira
1 estrela, Preco nunca ganha estrela.

O servidor de teste (fake Web App) e um HTTP real em 127.0.0.1, mesmo padrao
de tests/test_painel.py - nada nesse repo usa biblioteca de mock.
"""

import argparse
import datetime as dt
import json
import shutil
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import ambiente

from scripts import central_compras as cc


class SheetsPayloadTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-sheets-export-"))
        ambiente.montar(self.tmpdir, extras=["dashboard", "vereditos"])
        self._orig = {
            key: getattr(cc, key)
            for key in ["ROOT", "CONFIG", "PROJETOS", "PRODUTOS", "TEMPLATES", "BASE", "VEREDITOS", "DASHBOARD"]
        }
        cc.ROOT = self.tmpdir
        cc.CONFIG = self.tmpdir / "config"
        cc.PROJETOS = self.tmpdir / "projetos"
        cc.PRODUTOS = self.tmpdir / "produtos"
        cc.TEMPLATES = self.tmpdir / "templates"
        cc.BASE = self.tmpdir / "base-conhecimento"
        cc.VEREDITOS = self.tmpdir / "vereditos"
        cc.DASHBOARD = self.tmpdir / "dashboard"
        cc._PREFS_CACHE.clear()

        categorias = cc.read_yaml(cc.CONFIG / "categorias.yaml", {})
        categorias["camera"] = {
            "atributos_obrigatorios": ["resolucao"],
            "gate": {"garantia_tipo_aceita": ["nacional", "vendedor", "nenhuma"]},
            "estrelas": {
                "resolucao": {"faixas": [{"min": 3, "estrelas": 4}, {"min": 0, "estrelas": 3}]}
            },
        }
        cc.write_yaml(cc.CONFIG / "categorias.yaml", categorias)

        cc.new_project(argparse.Namespace(
            nome="camera export", categoria="camera", valor_estimado=500,
            preco_teto=800, necessidade="teste", force=False,
        ))
        self.projeto = cc.PROJETOS / f"{dt.date.today().year}-camera-export"

        cc.new_product(argparse.Namespace(
            projeto=str(self.projeto), nome="Boa", marca="M", categoria="camera",
            produto_id="cam-boa", preco_alvo=None, preco_teto=None,
            atributo=["resolucao=4K"], requisito=[], force=False,
        ))
        path = cc.find_product_path("cam-boa")
        data = cc.read_yaml(path, {})
        data["atributos_classificacao"] = {"resolucao": 4}
        cc.write_yaml(path, data)
        cc.add_quote(argparse.Namespace(
            projeto=str(self.projeto), produto_id="cam-boa", loja="Loja", vendedor="Loja",
            vendedor_tipo="oficial", anuncio_id=None, variacao=None, preco=300.0,
            preco_promocional=None, frete=0.0, frete_prazo_dias=2, custo_extra=0.0,
            custo_total=None, custo_operacional_mensal=0.0, tco_meses=None,
            valor_revenda_estimado=0.0, nota=4.8, avaliacoes=500,
            garantia_meses=24, garantia_tipo="nacional",
            link="https://example.com", flag_suspeita="",
            fonte="manual", data="2026-08-31",
        ))

        cc.new_product(argparse.Namespace(
            projeto=str(self.projeto), nome="Cara Demais", marca="M", categoria="camera",
            produto_id="cam-cortada", preco_alvo=None, preco_teto=None,
            atributo=["resolucao=4K"], requisito=[], force=False,
        ))
        path = cc.find_product_path("cam-cortada")
        data = cc.read_yaml(path, {})
        data["atributos_classificacao"] = {"resolucao": 4}
        cc.write_yaml(path, data)
        cc.add_quote(argparse.Namespace(
            projeto=str(self.projeto), produto_id="cam-cortada", loja="Loja", vendedor="Loja",
            vendedor_tipo="oficial", anuncio_id=None, variacao=None, preco=999999.0,
            preco_promocional=None, frete=0.0, frete_prazo_dias=2, custo_extra=0.0,
            custo_total=None, custo_operacional_mensal=0.0, tco_meses=None,
            valor_revenda_estimado=0.0, nota=4.9, avaliacoes=900,
            garantia_meses=24, garantia_tipo="nacional",
            link="https://example.com", flag_suspeita="",
            fonte="manual", data="2026-08-31",
        ))

    def tearDown(self):
        for key, value in self._orig.items():
            setattr(cc, key, value)
        cc._PREFS_CACHE.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_payload_matches_dashboard_counts_and_comparison(self):
        payload = cc.sheets_export_payload()

        self.assertEqual(payload["schema_versao"], 3)
        self.assertEqual(
            payload["visao_geral_colunas"],
            cc.SHEETS_OVERVIEW_COLUMNS,
        )
        self.assertEqual(
            payload["metricas_colunas"],
            ["projeto", *cc.SHEETS_METRIC_FIELDS],
        )
        self.assertEqual(len(payload["visao_geral"]), 1)
        visao = payload["visao_geral"][0]
        self.assertEqual(visao["projeto"], self.projeto.name)
        contagem = cc.project_counts(self.projeto)
        self.assertEqual(visao["categoria"], contagem["categoria"])
        self.assertEqual(visao["lider"], contagem["lider"])
        self.assertEqual(visao["score"], contagem["score"])
        self.assertIn("data_decisao", visao)
        self.assertIn("cotacoes_vencidas", visao)
        self.assertIn("abaixo_confianca_minima", visao)
        self.assertFalse(visao["empate_tecnico"])

        self.assertEqual(len(payload["comparativos"]), 1)
        comp = payload["comparativos"][0]
        self.assertEqual(comp["projeto"], self.projeto.name)
        self.assertEqual(comp["categoria"], "camera")
        self.assertEqual(comp["escolhido"], "")
        self.assertEqual(comp["data_decisao"], "")
        self.assertEqual(comp["colunas"], ["Boa", "Cara Demais"])
        self.assertEqual(comp["situacao"], ["elegivel", "cortado"])
        self.assertEqual(comp["metricas"][0]["produto"], "Boa")
        self.assertEqual(comp["metricas"][0]["custo_total"], 300.0)
        self.assertIsInstance(comp["metricas"][0]["score"], float)
        self.assertEqual(comp["metricas"][0]["fonte"], "manual")
        self.assertIsInstance(comp["metricas"][0]["vencida"], bool)
        self.assertEqual(comp["metricas"][0]["motivos_corte"], [])
        self.assertTrue(comp["metricas"][1]["motivos_corte"])

    def test_technical_tie_includes_exactly_three_points(self):
        primeiro = _item_falso()
        primeiro.score = 91.0
        segundo = _item_falso()
        segundo.score = 88.0
        self.assertTrue(cc.is_technical_tie([primeiro, segundo]))
        segundo.score = 87.99
        self.assertFalse(cc.is_technical_tie([primeiro, segundo]))

    def test_price_row_is_never_starred(self):
        payload = cc.sheets_export_payload()
        linhas = payload["comparativos"][0]["linhas"]
        preco = next(linha for linha in linhas if linha["rotulo"] == "Preco")
        self.assertEqual(preco["tipo"], "texto")
        self.assertEqual(preco["secao"], "precos")
        self.assertIsInstance(preco["valores"][0], str)  # contrato legado da versao 4
        self.assertEqual(preco["valores_tipados"][0]["tipo"], "moeda")
        self.assertEqual(preco["valores_tipados"][0]["valor"], 300.0)

    def test_note_keeps_legacy_text_and_adds_numeric_value(self):
        payload = cc.sheets_export_payload()
        linhas = payload["comparativos"][0]["linhas"]
        nota = next(linha for linha in linhas if linha["rotulo"] == "Nota")
        self.assertEqual(nota["tipo"], "estrela")
        self.assertEqual(nota["valores"][0]["texto"], "4.8 (500 aval.)")
        self.assertEqual(nota["valores_tipados"][0]["tipo"], "nota")
        self.assertEqual(nota["valores_tipados"][0]["valor"], 4.8)
        self.assertEqual(nota["valores_tipados"][0]["detalhe"], "500 avaliacoes")

    def test_typed_value_does_not_turn_decimal_text_into_a_number(self):
        texto = cc._valor_tipado("11.7", "11.7")
        numero = cc._valor_tipado(11.7, "11.7")
        self.assertEqual(texto["tipo"], "texto")
        self.assertEqual(texto["valor"], "11.7")
        self.assertEqual(numero["tipo"], "numero")
        self.assertEqual(numero["valor"], 11.7)

    def test_cut_candidate_has_no_star_anywhere(self):
        payload = cc.sheets_export_payload()
        linhas = payload["comparativos"][0]["linhas"]
        for linha in linhas:
            if linha["tipo"] != "estrela":
                continue
            valor_cortado = linha["valores"][1]  # cam-cortada e a 2a coluna
            self.assertIsNone(
                valor_cortado["estrelas"],
                f"'{linha['rotulo']}' nao pode ter estrela pro candidato cortado",
            )

    def test_eligible_candidate_keeps_its_star(self):
        payload = cc.sheets_export_payload()
        linhas = payload["comparativos"][0]["linhas"]
        resolucao = next(linha for linha in linhas if linha["rotulo"] == "Resolucao")
        self.assertEqual(resolucao["valores"][0]["estrelas"], 4)
        self.assertEqual(resolucao["secao"], "atributos")


class ComercialAtributoValorTest(unittest.TestCase):
    """Casos de fronteira das funcoes puras, sem precisar montar projeto inteiro."""

    def test_preco_never_has_a_star(self):
        item = _item_falso(quote={"custo_total": "100"})
        texto, estrelas = cc.comercial_valor(item, "preco")
        self.assertIsNone(estrelas)
        self.assertIn("100", texto)

    def test_nota_missing_axis_has_no_star(self):
        item = _item_falso(quote={"nota": "4.8", "n_avaliacoes": "10"}, eixos_sem_dado=["qualidade"])
        _, estrelas = cc.comercial_valor(item, "nota")
        self.assertIsNone(estrelas)

    def test_cut_item_never_stars_garantia(self):
        item = _item_falso(
            quote={"garantia_tipo": "nacional", "garantia_meses": "24"},
            eliminations=["preco acima do teto"],
        )
        _, estrelas = cc.comercial_valor(item, "garantia")
        self.assertIsNone(estrelas)

    def test_atributo_missing_display_value_is_dash_without_crashing(self):
        item = _item_falso(product={"atributos": {}, "atributos_classificacao": {}})
        texto, estrelas = cc.atributo_valor("camera", item, "resolucao")
        self.assertEqual(texto, "-")
        self.assertIsNone(estrelas)


def _item_falso(*, quote=None, product=None, eliminations=None, eixos_sem_dado=None):
    return cc.Ranked(
        produto_id="x",
        quote=quote or {},
        product=product or {},
        axes={},
        score=0.0,
        eliminations=eliminations or [],
        alerts=[],
        eixos_sem_dado=eixos_sem_dado or [],
        idade_dias=None,
        vencida=False,
        confianca=1.0,
        breakdown=None,
    )


class _FakeAppsScript(BaseHTTPRequestHandler):
    """Imita o contrato do Web App: confere o token, devolve ok/erro em JSON."""

    token_esperado = "senha-de-teste"

    def log_message(self, *_):
        pass

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        corpo = json.loads(self.rfile.read(tamanho) or b"{}")
        if corpo.get("token") != self.token_esperado:
            resposta = {"ok": False, "error": "token invalido"}
        else:
            resposta = {"ok": True, "mensagem": "sincronizado"}
        dados = json.dumps(resposta).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)


class _FakeNaoJsonServer(BaseHTTPRequestHandler):
    """Imita o Web App respondendo algo que nao e JSON (ex.: pagina de erro)."""

    def log_message(self, *_):
        pass

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        self.rfile.read(tamanho)
        corpo = b"<html>nao sou json</html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)


class _FakeAppsScriptComDetalhe(BaseHTTPRequestHandler):
    """Devolve uma falha capturada pelo Apps Script com diagnostico util."""

    def log_message(self, *_):
        pass

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        self.rfile.read(tamanho)
        resposta = {
            "ok": False,
            "error": "falha na sincronizacao",
            "detalhe": "Range not found",
        }
        dados = json.dumps(resposta).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)


class _FakeAppsScriptComFalhaParcial(BaseHTTPRequestHandler):
    """Falha no meio da escrita: a Versao 10 do Code.gs informa quais abas
    ja tinham sido gravadas antes da excecao (docs/integracao-google-sheets.md,
    secao "Code.gs (versao 10 - DEPLOY PENDENTE)")."""

    def log_message(self, *_):
        pass

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        self.rfile.read(tamanho)
        resposta = {
            "ok": False,
            "error": "falha na sincronizacao",
            "detalhe": "RangeError: Invalid array length",
            "abas_escritas_antes_da_falha": ["2026-primeiro"],
        }
        dados = json.dumps(resposta).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)


class _FakeAppsScriptComFalhaParcialEConcluida(BaseHTTPRequestHandler):
    """Uma sincronizacao com abas concluidas E abas so parcialmente
    alteradas ao mesmo tempo - reproducao exata pedida pelo Codex apos o
    commit c5018dc: sincronizar-planilha informava so 2026-a e omitia
    2026-b (abas_parcialmente_alteradas nunca era lido)."""

    def log_message(self, *_):
        pass

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        self.rfile.read(tamanho)
        resposta = {
            "ok": False,
            "error": "falha na sincronizacao",
            "detalhe": "timeout",
            "abas_escritas_antes_da_falha": ["2026-a"],
            "abas_parcialmente_alteradas": ["2026-b"],
        }
        dados = json.dumps(resposta).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)


class SincronizarPlanilhaTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-sync-"))
        ambiente.montar(self.tmpdir, extras=["dashboard", "vereditos"])
        self._orig = {
            key: getattr(cc, key)
            for key in ["ROOT", "CONFIG", "PROJETOS", "PRODUTOS", "TEMPLATES", "BASE", "VEREDITOS", "DASHBOARD"]
        }
        cc.ROOT = self.tmpdir
        cc.CONFIG = self.tmpdir / "config"
        cc.PROJETOS = self.tmpdir / "projetos"
        cc.PRODUTOS = self.tmpdir / "produtos"
        cc.TEMPLATES = self.tmpdir / "templates"
        cc.BASE = self.tmpdir / "base-conhecimento"
        cc.VEREDITOS = self.tmpdir / "vereditos"
        cc.DASHBOARD = self.tmpdir / "dashboard"
        cc._PREFS_CACHE.clear()

    def tearDown(self):
        for key, value in self._orig.items():
            setattr(cc, key, value)
        cc._PREFS_CACHE.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _sobe_servidor(self, handler):
        servidor = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        porta = servidor.server_address[1]
        thread = threading.Thread(target=servidor.serve_forever, daemon=True)
        thread.start()

        def encerrar():
            servidor.shutdown()
            thread.join(timeout=5)  # espera o loop sair do select() antes de fechar o socket
            servidor.server_close()

        self.addCleanup(encerrar)
        return f"http://127.0.0.1:{porta}"

    def _config(self, url, token):
        caminho = self.tmpdir / "integracao_sheets.json"
        caminho.write_text(json.dumps({"url": url, "token": token}), encoding="utf-8")
        return caminho

    def test_missing_config_file_raises_clear_error(self):
        caminho = self.tmpdir / "nao-existe.json"
        with self.assertRaises(SystemExit) as ctx:
            cc.sincronizar_planilha(argparse.Namespace(config=str(caminho)))
        self.assertIn("Configuracao nao encontrada", str(ctx.exception))

    def test_config_missing_fields_raises_clear_error(self):
        caminho = self.tmpdir / "incompleto.json"
        caminho.write_text(json.dumps({"url": "http://x"}), encoding="utf-8")
        with self.assertRaises(SystemExit) as ctx:
            cc.sincronizar_planilha(argparse.Namespace(config=str(caminho)))
        self.assertIn("'url' e 'token'", str(ctx.exception))

    def test_successful_sync_against_a_real_local_server(self):
        url = self._sobe_servidor(_FakeAppsScript)
        caminho = self._config(url, _FakeAppsScript.token_esperado)
        cc.sincronizar_planilha(argparse.Namespace(config=str(caminho)))  # nao levanta

    def test_wrong_token_is_reported_not_silently_ignored(self):
        url = self._sobe_servidor(_FakeAppsScript)
        caminho = self._config(url, "token-errado")
        with self.assertRaises(SystemExit) as ctx:
            cc.sincronizar_planilha(argparse.Namespace(config=str(caminho)))
        self.assertIn("token invalido", str(ctx.exception))

    def test_apps_script_error_includes_captured_detail(self):
        url = self._sobe_servidor(_FakeAppsScriptComDetalhe)
        caminho = self._config(url, "qualquer-token")
        with self.assertRaises(SystemExit) as ctx:
            cc.sincronizar_planilha(argparse.Namespace(config=str(caminho)))
        mensagem = str(ctx.exception)
        self.assertIn("falha na sincronizacao", mensagem)
        self.assertIn("Range not found", mensagem)

    def test_partial_failure_reports_which_tabs_were_already_written(self):
        url = self._sobe_servidor(_FakeAppsScriptComFalhaParcial)
        caminho = self._config(url, "qualquer-token")
        with self.assertRaises(SystemExit) as ctx:
            cc.sincronizar_planilha(argparse.Namespace(config=str(caminho)))
        mensagem = str(ctx.exception)
        self.assertIn("falha na sincronizacao", mensagem)
        self.assertIn("2026-primeiro", mensagem)

    def test_partial_and_completed_tabs_are_both_reported_distinctly(self):
        url = self._sobe_servidor(_FakeAppsScriptComFalhaParcialEConcluida)
        caminho = self._config(url, "qualquer-token")
        with self.assertRaises(SystemExit) as ctx:
            cc.sincronizar_planilha(argparse.Namespace(config=str(caminho)))
        mensagem = str(ctx.exception)
        self.assertIn("2026-a", mensagem)
        self.assertIn("2026-b", mensagem)
        # Nao pode misturar as duas listas numa unica frase generica - tem
        # que dar pra saber qual aba terminou de verdade e qual so foi
        # limpa (pode estar em branco).
        pos_a = mensagem.index("2026-a")
        pos_b = mensagem.index("2026-b")
        self.assertNotEqual(pos_a, pos_b)

    def test_token_stays_hidden_even_with_partial_diagnostics_present(self):
        # Ocultar o token na mensagem de erro nao pode depender de quais
        # campos vieram na resposta - continua valendo com
        # abas_parcialmente_alteradas presente.
        class _FakeComTokenNoDetalhe(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                tamanho = int(self.headers.get("Content-Length", 0))
                self.rfile.read(tamanho)
                resposta = {
                    "ok": False,
                    "error": "falha na sincronizacao",
                    "detalhe": "token-secreto-123 rejeitado",
                    "abas_escritas_antes_da_falha": ["2026-a"],
                    "abas_parcialmente_alteradas": ["2026-b"],
                }
                dados = json.dumps(resposta).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

        url = self._sobe_servidor(_FakeComTokenNoDetalhe)
        caminho = self._config(url, "token-secreto-123")
        with self.assertRaises(SystemExit) as ctx:
            cc.sincronizar_planilha(argparse.Namespace(config=str(caminho)))
        mensagem = str(ctx.exception)
        self.assertNotIn("token-secreto-123", mensagem)
        self.assertIn("[oculto]", mensagem)

    def test_response_without_partial_field_stays_compatible(self):
        # Resposta antiga (antes do Code.gs V13) nao tem
        # abas_parcialmente_alteradas - sincronizar_planilha nao pode
        # quebrar nem inventar a linha quando o campo simplesmente nao vem.
        url = self._sobe_servidor(_FakeAppsScriptComFalhaParcial)
        caminho = self._config(url, "qualquer-token")
        with self.assertRaises(SystemExit) as ctx:
            cc.sincronizar_planilha(argparse.Namespace(config=str(caminho)))
        mensagem = str(ctx.exception)
        self.assertIn("2026-primeiro", mensagem)
        self.assertNotIn("parcialmente alteradas", mensagem)

    def test_non_json_response_does_not_crash_with_a_raw_traceback(self):
        url = self._sobe_servidor(_FakeNaoJsonServer)
        caminho = self._config(url, "qualquer-token")
        with self.assertRaises(SystemExit) as ctx:
            cc.sincronizar_planilha(argparse.Namespace(config=str(caminho)))
        self.assertIn("nao devolveu JSON valido", str(ctx.exception))

    def test_legacy_web_app_response_remains_accepted(self):
        payload = {"visao_geral": [{}], "comparativos": [{}, {}]}
        self.assertEqual(cc.validar_resposta_sheets({"ok": True}, payload), [])

    def test_v2_response_returns_warnings_without_rejecting_sync(self):
        payload = {"visao_geral": [{}], "comparativos": [{}, {}]}
        resultado = {
            "ok": True,
            "schema_versao": 2,
            "linhas_visao": 1,
            "projetos_escritos": 2,
            "avisos": ["campo futuro ignorado"],
        }
        self.assertEqual(
            cc.validar_resposta_sheets(resultado, payload),
            ["campo futuro ignorado"],
        )

    def test_v2_response_with_wrong_counts_is_not_a_false_ok(self):
        payload = {"visao_geral": [{}], "comparativos": [{}, {}]}
        resultado = {
            "ok": True,
            "schema_versao": 2,
            "linhas_visao": 1,
            "projetos_escritos": 1,
        }
        with self.assertRaises(SystemExit) as ctx:
            cc.validar_resposta_sheets(resultado, payload)
        self.assertIn("respondeu ok", str(ctx.exception))
        self.assertIn("projetos_escritos", str(ctx.exception))


class ConfigDivididaTest(unittest.TestCase):
    """A URL e versionada, o token nao.

    O que motivou: em 04/09/2026 tres agentes concluiram que a integracao
    nunca tinha sido ativada, porque a prova (URL + token) morava so em
    dados-privados, que nao viaja no git pull. Com a URL versionada, `git
    pull` deixa a maquina nova a um comando de distancia.
    """

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-cfg-"))
        (self.tmpdir / "config").mkdir(parents=True, exist_ok=True)
        self._orig_config = cc.CONFIG
        cc.CONFIG = self.tmpdir / "config"
        self.privado = self.tmpdir / "privado" / "integracao_sheets.json"
        self._orig_path = cc.sheets_config_path
        cc.sheets_config_path = lambda: self.privado

    def tearDown(self):
        cc.CONFIG = self._orig_config
        cc.sheets_config_path = self._orig_path
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _versionado(self, url):
        (cc.CONFIG / "integracao_sheets.yaml").write_text(f'url: "{url}"\n', encoding="utf-8")

    def _local(self, dados):
        self.privado.parent.mkdir(parents=True, exist_ok=True)
        self.privado.write_text(json.dumps(dados), encoding="utf-8")

    def test_url_versionada_mais_token_local_bastam(self):
        self._versionado("https://exemplo/exec")
        self._local({"token": "abc123"})
        self.assertEqual(cc.carregar_config_sheets(), ("https://exemplo/exec", "abc123"))

    def test_sem_token_o_erro_ensina_o_comando(self):
        self._versionado("https://exemplo/exec")
        with self.assertRaises(SystemExit) as ctx:
            cc.carregar_config_sheets()
        mensagem = str(ctx.exception)
        self.assertIn("configurar-sheets", mensagem)
        self.assertIn("nao vai pelo Git", mensagem)

    def test_sem_url_versionada_o_erro_aponta_o_arquivo(self):
        self._local({"token": "abc123"})
        with self.assertRaises(SystemExit) as ctx:
            cc.carregar_config_sheets()
        self.assertIn("integracao_sheets.yaml", str(ctx.exception))

    def test_url_local_sobrepoe_a_versionada(self):
        self._versionado("https://producao/exec")
        self._local({"url": "https://teste/exec", "token": "abc123"})
        url, _ = cc.carregar_config_sheets()
        self.assertEqual(url, "https://teste/exec")

    def test_configurar_sheets_grava_token_e_descarta_url_velha(self):
        # A armadilha real: apos um redeploy, URL velha no arquivo local
        # continuava valendo sobre a versionada e a maquina tomava 404.
        self._versionado("https://nova/exec")
        self._local({"url": "https://velha/exec", "token": "antigo"})
        cc.configurar_sheets(argparse.Namespace(token="novo", url=None))
        self.assertEqual(cc.carregar_config_sheets(), ("https://nova/exec", "novo"))

    def test_configurar_sheets_respeita_url_explicita(self):
        self._versionado("https://nova/exec")
        cc.configurar_sheets(argparse.Namespace(token="t", url="https://teste/exec"))
        self.assertEqual(cc.carregar_config_sheets(), ("https://teste/exec", "t"))


class AppsScriptDocumentadoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        doc = (
            Path(__file__).parents[1] / "docs" / "integracao-google-sheets.md"
        ).read_text(encoding="utf-8")
        cls.doc = doc
        cls.code = doc.split("```javascript", 1)[1].split("```", 1)[0]

    def test_deploy_ativo_esta_documentado(self):
        self.assertIn("versão 13 ativa", self.doc)
        self.assertIn("VERSÃO 9 IMPLANTADA E VERIFICADA", self.doc)
        self.assertIn("VERSÃO 11 IMPLANTADA E VERIFICADA", self.doc)
        self.assertIn("VERSÃO 12 IMPLANTADA E VERIFICADA", self.doc)
        self.assertIn("VERSÃO 13 IMPLANTADA E VERIFICADA", self.doc)
        self.assertNotIn("DEPLOY PENDENTE", self.doc)

    def test_properties_do_projeto_solto_usa_script_nao_document(self):
        # PropertiesService.getDocumentProperties() e null num projeto solto
        # (nao container-bound) - quebrou de verdade em producao na V10. O
        # nome pode aparecer em comentario explicando a licao, mas nunca
        # como chamada de verdade.
        self.assertNotIn("PropertiesService.getDocumentProperties(", self.code)
        self.assertIn("PropertiesService.getScriptProperties()", self.code)

    def test_payload_e_validado_por_inteiro_antes_de_escrever_qualquer_aba(self):
        # Frente 3 / gap 1: null em visao_geral ou dentro de comparativos
        # nao pode deixar a planilha parcialmente escrita.
        self.assertIn("function validarPayload", self.code)
        self.assertIn("function validarListaDeObjetos", self.code)
        self.assertIn("function validarObjeto", self.code)
        # validarPayload tem que rodar ANTES de qualquer escrita real
        # (pastaCentral/escreverComparativo/escreverVisaoGeral).
        pos_validacao = self.code.index("validarPayload(dados)")
        pos_pasta = self.code.index("pastaCentral()")
        pos_comparativo = self.code.index("escreverComparativo(planilha")
        pos_visao = self.code.index("escreverVisaoGeral(")
        self.assertLess(pos_validacao, pos_pasta)
        self.assertLess(pos_validacao, pos_comparativo)
        self.assertLess(pos_validacao, pos_visao)

    def test_limpeza_de_abas_orfas_rastreia_o_que_o_proprio_script_escreveu(self):
        # Frente 3 / gap 2 (1a rodada): nao pode confiar so em padrao de
        # nome (uma aba criada a mao com nome parecido nao pode ser
        # candidata a remocao).
        self.assertNotIn("/^20\\d\\d-/.test(nome)", self.code)
        self.assertIn("PropertiesService.getScriptProperties", self.code)
        self.assertIn("function abasGeradasRegistradas", self.code)
        self.assertIn("function salvarAbasGeradas", self.code)

    def test_falha_no_meio_da_escrita_informa_o_que_ja_foi_gravado(self):
        # Frente 3 / gap 3 (1a rodada): resposta de erro precisa dar ao
        # cliente algo verificavel alem da mensagem da excecao.
        self.assertIn("abas_escritas_antes_da_falha", self.code)
        self.assertIn("estadoAbas[nomeAba] = 'concluida'", self.code)

    def test_aba_manual_nunca_e_confundida_com_aba_do_script_so_pelo_nome(self):
        # Frente 3 (2a rodada, Codex sobre d6246b6): abaLimpa() sobrescrevia
        # qualquer aba com o nome certo, mesmo criada a mao - reproduzido de
        # verdade em tests/test_apps_script_execucao.py
        # (test_aba_manual_sobrevive_a_colisao_de_nome). Propriedade agora e
        # nome + sheetId, nunca so o nome.
        self.assertIn("function abaEhDoScript", self.code)
        self.assertIn("registro[aba.getName()] === aba.getSheetId()", self.code)
        self.assertIn("function migrarRegistroLegado", self.code)
        # abaLimpa reivindica a aba ANTES de limpar - nao so no final.
        pos_abalimpa = self.code.index("function abaLimpa")
        pos_registro = self.code.index("registro[nome] = aba.getSheetId()")
        pos_clear = self.code.index("aba.clear()")
        self.assertLess(pos_abalimpa, pos_registro)
        self.assertLess(pos_registro, pos_clear)

    def test_estrelas_fora_do_contrato_e_barrado_antes_de_qualquer_escrita(self):
        # Frente 3 (2a rodada): estrelas: -2 no formato legado derrubava
        # estrelas()/Array() DEPOIS que abaLimpa ja tinha rodado. Validado
        # de verdade em test_apps_script_execucao.py (payload legado E
        # tipado). Aqui so confere que a checagem existe e roda dentro de
        # validarPayload (antes de qualquer abaLimpa).
        self.assertIn("function validarEstrelas", self.code)
        pos_validar_payload = self.code.index("function validarPayload")
        pos_validar_estrelas_chamada = self.code.index("validarEstrelas(")
        pos_primeiro_abalimpa_chamado = self.code.index("abaLimpa(planilha,")
        self.assertLess(pos_validar_payload, pos_validar_estrelas_chamada)
        self.assertLess(pos_validar_estrelas_chamada, pos_primeiro_abalimpa_chamado)

    def test_aba_parcialmente_alterada_aparece_no_diagnostico(self):
        # Frente 3 (2a rodada): abas onde abaLimpa rodou mas a escrita nao
        # terminou ficavam de fora de abas_escritas_antes_da_falha - a
        # resposta parecia dizer que so a 1a aba tinha sido tocada, quando a
        # 2a tambem tinha sido limpa. Validado de verdade em
        # test_apps_script_execucao.py
        # (test_falha_operacional_apos_clear_identifica_aba_parcial_no_diagnostico).
        self.assertIn("abas_parcialmente_alteradas", self.code)
        self.assertIn("estadoAbas[nomeAba] = 'iniciada'", self.code)

    def test_visao_geral_tambem_e_propriedade_verificada(self):
        # Frente 3 (3a rodada, Codex sobre o commit c5018dc): a 2a rodada
        # protegeu abas de comparativo por nome+sheetId mas excluiu "Visao
        # Geral" da checagem de propria vontade (`nome !== 'Visao Geral'`) -
        # uma aba manual com esse nome era adotada e limpa. Validado de
        # verdade em test_apps_script_execucao.py
        # (test_visao_geral_manual_sobrevive_a_colisao_de_nome +
        # test_registro_legado_sem_sheet_id_e_migrado_sem_duplicar, que
        # tambem prova o bootstrap do upgrade V11/V12 -> V13).
        self.assertNotIn("nome !== 'Visao Geral'", self.code)
        self.assertIn("const nomeVisao = nomeAbaProjeto('Visao Geral', nomesUsados)", self.code)
        self.assertIn("__visao_migrada__", self.code)
        # abaVisao/abaLimpa/escreverVisaoGeral/limparAbasOrfas tem que usar
        # a variavel resolvida, nao o literal fixo - senao a protecao vira
        # so decoracao que nunca influencia o nome de verdade usado.
        self.assertIn("planilha.getSheetByName(nomeVisao)", self.code)
        self.assertIn("escreverVisaoGeral(\n      planilha, Array.isArray(dados.visao_geral) ? dados.visao_geral : [],\n      camposVisao, dados.gerado_em, avisos, comparativos, destinos, registro, nomeVisao\n    )", self.code)
        self.assertIn("limparAbasOrfas(planilha, destinos, registro, nomeVisao)", self.code)

    def test_renderizacao_e_em_lote_e_tem_lock(self):
        self.assertNotIn(".appendRow(", self.code)
        self.assertNotIn("setNumberFormat('@')", self.code)
        self.assertIn("setValues", self.code)
        self.assertIn("setNumberFormats", self.code)
        self.assertIn("LockService.getScriptLock", self.code)

    def test_payload_antigo_tem_fallback_e_campos_novos_geram_aviso(self):
        self.assertIn("CAMPOS_VISAO_FALLBACK", self.code)
        self.assertIn("colunasOuFallback", self.code)
        self.assertIn("campo ignorado", self.code)
        self.assertIn("avisos", self.code)

    def test_visual_premium_e_dados_tipados_estao_documentados(self):
        self.assertIn("function escreverVisaoGeral", self.code)
        self.assertIn("function inserirGraficoPendencias", self.code)
        self.assertIn("function inserirGraficosComparativo", self.code)
        self.assertIn("function formatoTipo", self.code)

    def test_visao_geral_nao_compara_scores_de_projetos(self):
        self.assertNotIn("function inserirGraficoVisao", self.code)
        self.assertIn("Pendencias por projeto (contagem)", self.code)
        self.assertIn("score total nao e comparavel entre projetos", self.code)

    def test_congelamento_nao_corta_celulas_mescladas(self):
        self.assertNotIn("setFrozenColumns(1)", self.code)
        self.assertGreaterEqual(self.code.count("setFrozenColumns(0)"), 3)
        self.assertNotIn("setFrozenRows(linhaCabecalho)", self.code)
        self.assertIn("aba.setFrozenRows(3)", self.code)

    def test_graficos_comparativos_usam_fontes_contiguas(self):
        self.assertNotIn("setTransposeRowsAndColumns", self.code)
        self.assertIn("const rankingDados = [['Produto', 'Lider', 'Demais']]", self.code)
        self.assertIn("const eixosDados = [['Eixo'].concat(colunas)]", self.code)
        self.assertIn(".addRange(rankingFonte).setNumHeaders(1)", self.code)
        self.assertIn(".addRange(eixosFonte).setNumHeaders(1)", self.code)

    def test_visual_segue_a_paleta_e_as_interacoes_aprovadas(self):
        for cor in ("#2a78d6", "#eaf2fd", "#fab219", "#d03b3b", "#f9f9f7"):
            self.assertIn(cor, self.code)
        self.assertNotIn("Google Sans", self.code)
        self.assertIn("setFontFamily('Inter')", self.code)
        self.assertIn("Empate tecnico", self.code)
        self.assertIn("setRichTextValue", self.code)
        self.assertIn("setWarningOnly(true)", self.code)
        self.assertIn("getProtections(SpreadsheetApp.ProtectionType.SHEET)", self.code)
        self.assertIn("sem dado", self.code)

    def test_payload_legado_nao_produz_veredito_nan(self):
        self.assertIn("Score indisponivel neste payload", self.code)
        self.assertIn("const metrica = metricas[indice] || {}", self.code)

    def test_timeout_de_sincronizacao_continua_em_120_segundos(self):
        script = (
            Path(__file__).parents[1] / "scripts" / "central_compras.py"
        ).read_text(encoding="utf-8")
        self.assertIn("urlopen(requisicao, timeout=120)", script)


if __name__ == "__main__":
    unittest.main()
