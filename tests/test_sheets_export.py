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

        self.assertEqual(len(payload["visao_geral"]), 1)
        visao = payload["visao_geral"][0]
        self.assertEqual(visao["projeto"], self.projeto.name)
        contagem = cc.project_counts(self.projeto)
        self.assertEqual(visao["categoria"], contagem["categoria"])
        self.assertEqual(visao["lider"], contagem["lider"])
        self.assertEqual(visao["score"], contagem["score"])

        self.assertEqual(len(payload["comparativos"]), 1)
        comp = payload["comparativos"][0]
        self.assertEqual(comp["projeto"], self.projeto.name)
        self.assertEqual(comp["colunas"], ["Boa", "Cara Demais"])
        self.assertEqual(comp["situacao"], ["elegivel", "cortado"])

    def test_price_row_is_never_starred(self):
        payload = cc.sheets_export_payload()
        linhas = payload["comparativos"][0]["linhas"]
        preco = next(linha for linha in linhas if linha["rotulo"] == "Preco")
        self.assertEqual(preco["tipo"], "texto")

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

    def test_non_json_response_does_not_crash_with_a_raw_traceback(self):
        url = self._sobe_servidor(_FakeNaoJsonServer)
        caminho = self._config(url, "qualquer-token")
        with self.assertRaises(SystemExit) as ctx:
            cc.sincronizar_planilha(argparse.Namespace(config=str(caminho)))
        self.assertIn("nao devolveu JSON valido", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
