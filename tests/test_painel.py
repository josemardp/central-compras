"""O painel nao pode ser porta dos fundos.

Se o CLI recusa, o painel tem que recusar igual. Cada teste aqui existe para
impedir que a grade no navegador vire um caminho paralelo que ignora gate,
append-only ou validacao de entrada.
"""

import datetime as dt
import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import ambiente
from scripts import central_compras as cc
from scripts import painel


ROOT = Path(__file__).resolve().parents[1]
ANO = dt.date.today().year


class Base(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-painel-"))
        ambiente.montar(self.tmpdir)
        self._orig = {
            k: getattr(cc, k)
            for k in ["ROOT", "CONFIG", "PROJETOS", "PRODUTOS", "TEMPLATES", "BASE", "VEREDITOS", "DASHBOARD"]
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
        self.projeto = self.montar_projeto()

    def tearDown(self):
        for chave, valor in self._orig.items():
            setattr(cc, chave, valor)
        cc._PREFS_CACHE.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def montar_projeto(self):
        import argparse
        cc.new_project(argparse.Namespace(
            nome="fone painel", categoria="fone", valor_estimado=400,
            preco_teto=600, necessidade="teste", force=False))
        project = cc.PROJETOS / f"{ANO}-fone-painel"
        cc.new_product(argparse.Namespace(
            projeto=str(project), nome="Fone A", marca="M", categoria="fone",
            produto_id="fone-a", preco_alvo=None, preco_teto=None,
            atributo=[], requisito=["uso=true"], force=False))
        cc.add_quote(argparse.Namespace(
            projeto=str(project), produto_id="fone-a", loja="Amazon", vendedor="V",
            vendedor_tipo="oficial", anuncio_id=None, variacao=None, preco=299.0,
            preco_promocional=None, frete=0.0, frete_prazo_dias=3, custo_extra=0.0,
            custo_total=None, custo_operacional_mensal=0.0, tco_meses=None,
            valor_revenda_estimado=0.0, nota=4.6, avaliacoes=900, garantia_meses=12,
            garantia_tipo="nacional", link="https://ex.com/a", flag_suspeita="",
            fonte="web", data=None))
        cc.build_ranking(argparse.Namespace(projeto=str(project)))
        return project


class EstadoTest(Base):
    """`estado()` e funcao pura: calcula com o motor e nao escreve nada."""

    def test_reports_what_the_engine_says(self):
        e = painel.estado(self.projeto)
        self.assertEqual(e["projeto"], self.projeto.name)
        self.assertEqual(len(e["elegiveis"]), 1)
        self.assertEqual(e["elegiveis"][0]["produto_id"], "fone-a")
        self.assertEqual(e["total_cotacoes"], 1)
        self.assertEqual(e["manuais"], 0)

    def test_exposes_the_same_comparison_base_as_the_ranking(self):
        e = painel.estado(self.projeto)
        self.assertEqual(e["base_valor"], "custo total")
        self.assertEqual(e["confianca_minima"], cc.minimum_confidence({"valor_estimado": 400}))

    def test_marks_the_axis_without_data(self):
        """A barra cinza da tela vem daqui: sem requisito nenhum o eixo sai da conta."""
        e = painel.estado(self.projeto)
        linha = e["elegiveis"][0]
        self.assertLessEqual(linha["confianca"], 1.0)
        self.assertIsInstance(linha["sem_dado"], list)

    def test_does_not_write_anything(self):
        antes = {p: p.read_bytes() for p in self.projeto.glob("*") if p.is_file()}
        painel.estado(self.projeto)
        for caminho, conteudo in antes.items():
            self.assertEqual(caminho.read_bytes(), conteudo, f"`estado()` escreveu em {caminho.name}")


class AcaoTest(Base):
    def test_unknown_action_is_refused(self):
        r = painel.acao(self.projeto, "apagar_tudo", {})
        self.assertFalse(r["ok"])
        self.assertIn("desconhecida", r["erro"])

    def test_every_offered_action_maps_to_a_real_cli_command(self):
        """Regra que so vale no painel e regra que ninguem auditou."""
        parser = cc.build_parser()
        comandos = set(parser._subparsers._group_actions[0].choices)
        for equivalente in painel.ACOES.values():
            self.assertIn(equivalente, comandos, equivalente)

    def test_ranking_action_regenerates_the_file(self):
        alvo = self.projeto / "ranking.md"
        alvo.write_text("apagado", encoding="utf-8")
        r = painel.acao(self.projeto, "ranking", {})
        self.assertTrue(r["ok"], r)
        self.assertIn("Fone A", alvo.read_text(encoding="utf-8"))


class GravarCotacaoTest(Base):
    def linhas(self):
        return cc.read_quotes(self.projeto)

    def base(self, **extra):
        dados = {"produto_id": "fone-a", "loja": "Amazon", "vendedor": "V",
                 "vendedor_tipo": "oficial", "preco": "289", "frete": "0",
                 "frete_prazo_dias": "3", "nota": "4.6", "avaliacoes": "900",
                 "garantia_meses": "12", "garantia_tipo": "nacional",
                 "link": "https://ex.com/a", "fonte": "manual"}
        dados.update(extra)
        return dados

    def test_appends_instead_of_overwriting(self):
        """Principio 1: preco novo e linha nova."""
        antes = len(self.linhas())
        r = painel.acao(self.projeto, "cotar", self.base())
        self.assertTrue(r["ok"], r)
        depois = self.linhas()
        self.assertEqual(len(depois), antes + 1)
        self.assertEqual(depois[0]["preco"], "299.0", "a cotacao antiga foi alterada")
        self.assertEqual(depois[-1]["fonte"], "manual")

    def test_refuses_nan_and_infinity_like_the_cli(self):
        for ruim in ["NaN", "Infinity", "1e309", "-5"]:
            r = painel.acao(self.projeto, "cotar", self.base(preco=ruim))
            self.assertFalse(r["ok"], ruim)
            self.assertIn("preco", r["erro"])
        self.assertEqual(len(self.linhas()), 1, "lixo entrou no livro-razao")

    def test_requires_product_price_and_store(self):
        self.assertFalse(painel.acao(self.projeto, "cotar", self.base(produto_id=""))["ok"])
        self.assertFalse(painel.acao(self.projeto, "cotar", self.base(loja=""))["ok"])
        self.assertFalse(painel.acao(self.projeto, "cotar", self.base(preco=""))["ok"])

    def test_refuses_an_invalid_enum(self):
        for campo, valor in [("fonte", "inventada"), ("vendedor_tipo", "amigo"),
                             ("garantia_tipo", "eterna")]:
            r = painel.acao(self.projeto, "cotar", self.base(**{campo: valor}))
            self.assertFalse(r["ok"], campo)

    def test_accepts_brazilian_decimal_comma(self):
        r = painel.acao(self.projeto, "cotar", self.base(preco="296,64"))
        self.assertTrue(r["ok"], r)
        self.assertEqual(cc.quote_float(self.linhas()[-1]["custo_total"]), 296.64)

    def test_recomputes_the_ranking_after_writing(self):
        painel.acao(self.projeto, "cotar", self.base(preco="199"))
        ranking = (self.projeto / "ranking.md").read_text(encoding="utf-8")
        self.assertIn("199", ranking.replace(".", "").replace(",", ""))


class ServidorTest(Base):
    """A casca HTTP nao pode contornar nada, e nao pode escutar fora da maquina."""

    def setUp(self):
        super().setUp()
        from http.server import ThreadingHTTPServer
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), painel._Handler)
        self.porta = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def url(self, caminho):
        return f"http://127.0.0.1:{self.porta}{caminho}"

    def post(self, payload):
        pedido = urllib.request.Request(
            self.url("/api/acao"), data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(pedido, timeout=15).read())

    def test_binds_only_to_localhost(self):
        """Ele escreve no repo: nao pode aceitar conexao de fora."""
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")

    def test_serves_the_page(self):
        corpo = urllib.request.urlopen(self.url("/"), timeout=15).read().decode("utf-8")
        self.assertIn("Nova cotacao", corpo)
        self.assertIn("prefers-color-scheme", corpo, "sem tema escuro")
        self.assertIn("viewport", corpo, "sem meta viewport, quebra no celular")

    def test_state_endpoint_returns_the_engine_numbers(self):
        dados = json.loads(urllib.request.urlopen(
            self.url(f"/api/estado?projeto={self.projeto.name}"), timeout=15).read())
        self.assertEqual(dados["projeto"], self.projeto.name)
        self.assertEqual(len(dados["elegiveis"]), 1)

    def test_unknown_project_is_404_not_a_crash(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.url("/api/estado?projeto=nao-existe"), timeout=15)
        self.assertEqual(ctx.exception.code, 404)

    def test_guards_hold_through_http(self):
        self.assertFalse(self.post({"projeto": self.projeto.name, "acao": "apagar_tudo", "dados": {}})["ok"])
        r = self.post({"projeto": self.projeto.name, "acao": "cotar",
                       "dados": {"produto_id": "fone-a", "loja": "Amazon", "preco": "NaN"}})
        self.assertFalse(r["ok"])
        self.assertIn("nao e numero", r["erro"])

    def test_post_refuses_invalid_content_type(self):
        pedido = urllib.request.Request(
            self.url("/api/acao"),
            data=json.dumps({"projeto": self.projeto.name, "acao": "ranking"}).encode(),
            headers={"Content-Type": "text/plain"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(pedido, timeout=15)
        self.assertEqual(ctx.exception.code, 415)
        corpo = ctx.exception.read().decode("utf-8")
        dados = json.loads(corpo)
        self.assertFalse(dados["ok"])
        self.assertEqual(dados["erro"], "Content-Type precisa ser application/json.")

    def test_post_refuses_invalid_content_length(self):
        pedido = urllib.request.Request(
            self.url("/api/acao"),
            data=json.dumps({"projeto": self.projeto.name, "acao": "ranking"}).encode(),
            headers={"Content-Type": "application/json", "Content-Length": "abc"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(pedido, timeout=15)
        self.assertEqual(ctx.exception.code, 400)
        corpo = ctx.exception.read().decode("utf-8")
        dados = json.loads(corpo)
        self.assertFalse(dados["ok"])
        self.assertEqual(dados["erro"], "Content-Length invalido.")

    def test_post_refuses_negative_content_length(self):
        pedido = urllib.request.Request(
            self.url("/api/acao"),
            data=json.dumps({"projeto": self.projeto.name, "acao": "ranking"}).encode(),
            headers={"Content-Type": "application/json", "Content-Length": "-5"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(pedido, timeout=15)
        self.assertEqual(ctx.exception.code, 400)
        corpo = ctx.exception.read().decode("utf-8")
        dados = json.loads(corpo)
        self.assertFalse(dados["ok"])
        self.assertEqual(dados["erro"], "Content-Length invalido.")

    def test_unknown_route_is_404(self):
        for rota in ["/api/qualquer", "/etc/passwd", "/../config/preferencias.yaml"]:
            with self.assertRaises(urllib.error.HTTPError, msg=rota):
                urllib.request.urlopen(self.url(rota), timeout=15)


class ArtifactTest(Base):
    """A pagina so-leitura, para consultar do celular."""

    def test_it_is_a_single_self_contained_page(self):
        pagina = painel.artifact_html()
        self.assertNotIn("<script", pagina, "artifact nao precisa de script")
        self.assertIn("viewport", pagina)
        self.assertIn("prefers-color-scheme", pagina, "sem tema escuro")

    def test_it_shows_the_engine_numbers(self):
        pagina = painel.artifact_html()
        self.assertIn("Fone A", pagina)
        self.assertIn("R$ 299,00", pagina)
        self.assertIn("confianca", pagina)

    def test_it_says_out_loud_that_it_does_not_write(self):
        """A pagina precisa deixar claro que e foto, nao a verdade."""
        pagina = painel.artifact_html()
        self.assertIn("So leitura", pagina)
        self.assertIn("painel", pagina)

    def test_it_escapes_hostile_content(self):
        import argparse
        cc.new_product(argparse.Namespace(
            projeto=str(self.projeto), nome="<img src=x onerror=alert(1)>", marca="M",
            categoria="fone", produto_id="hostil", preco_alvo=None, preco_teto=None,
            atributo=[], requisito=["uso=true"], force=False))
        cc.add_quote(argparse.Namespace(
            projeto=str(self.projeto), produto_id="hostil", loja="<script>alert(1)</script>",
            vendedor="V", vendedor_tipo="oficial", anuncio_id=None, variacao=None,
            preco=100.0, preco_promocional=None, frete=0.0, frete_prazo_dias=3,
            custo_extra=0.0, custo_total=None, custo_operacional_mensal=0.0, tco_meses=None,
            valor_revenda_estimado=0.0, nota=4.6, avaliacoes=900, garantia_meses=12,
            garantia_tipo="nacional", link="https://ex.com/h", flag_suspeita="",
            fonte="web", data=None))
        pagina = painel.artifact_html()
        self.assertNotIn("<img src=x", pagina)
        self.assertNotIn("<script>alert", pagina)
        self.assertIn("&lt;img src=x", pagina)

    def test_the_command_writes_the_file(self):
        import argparse
        painel.gerar_artifact(argparse.Namespace())
        destino = cc.DASHBOARD / "artifact.html"
        self.assertTrue(destino.exists())
        self.assertIn("Central de Compras", destino.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
