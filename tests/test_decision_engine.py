import datetime as dt
import shutil
import tempfile
from pathlib import Path

import ambiente
import unittest

from scripts import central_compras


class DecisionEngineTest(unittest.TestCase):
    def test_adjusted_rating_shrinks_low_volume_perfect_score(self):
        # Com m=250, nota 5,0 com 4 avaliacoes quase nao sai da media da
        # categoria: volume e evidencia, e 4 avaliacoes nao sao evidencia.
        self.assertLess(central_compras.adjusted_rating(5.0, 4), 4.35)
        # Ja 6.000 avaliacoes dominam a ancora com folga.
        self.assertGreater(central_compras.adjusted_rating(4.7, 6000), 4.68)

    def test_risk_score_penalizes_alerts(self):
        row = {
            "vendedor_tipo": "oficial",
            "garantia_tipo": "nacional",
            "garantia_meses": "12",
        }
        clean = central_compras.risk_score(row, [])
        suspicious = central_compras.risk_score(row, ["AVAL_SUSPEITA", "ANCORA"])
        self.assertLess(suspicious, clean)

    def test_discarded_product_is_cut_by_gate(self):
        row = {
            "custo_total": "100",
            "nota_ajustada": "4.8",
            "n_avaliacoes": "1000",
            "garantia_tipo": "nacional",
            "garantia_meses": "12",
            "vendedor_tipo": "oficial",
        }
        product = {
            "categoria": "fone",
            "estado": "descartado",
            "descartado_porque": "Microfone ruim.",
            "requisitos_atendidos": {},
        }
        briefing = {"categoria": "fone", "preco_teto": 600}
        eliminations = central_compras.gate_eliminations(row, product, briefing)
        self.assertIn("produto descartado", eliminations[0])

    def test_tco_total_uses_monthly_cost_and_resale_value(self):
        total = central_compras.quote_tco_total(
            custo_total=100000,
            custo_operacional_mensal=1000,
            tco_meses=60,
            valor_revenda_estimado=50000,
        )
        self.assertEqual(total, 110000)


class CategoryBayesianAnchorTest(unittest.TestCase):
    """`nota_bayesiana` pode ser sobrescrito por categoria."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-bayes-"))
        ambiente.montar(self.tmpdir)
        self._orig_config = central_compras.CONFIG
        central_compras.CONFIG = self.tmpdir / "config"
        central_compras._PREFS_CACHE.clear()

    def tearDown(self):
        central_compras.CONFIG = self._orig_config
        central_compras._PREFS_CACHE.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_category_without_block_uses_global(self):
        sem_categoria = central_compras.adjusted_rating(4.8, 30)
        com_categoria = central_compras.adjusted_rating(4.8, 30, "generico")
        self.assertEqual(sem_categoria, com_categoria)

    def test_category_with_custom_anchor_uses_local_value(self):
        categorias = central_compras.read_yaml(self.tmpdir / "config" / "categorias.yaml", {})
        categorias["teste_bayes"] = {
            "atributos_obrigatorios": [],
            "nota_bayesiana": {"peso_ancora": 30},
            "gate": {},
        }
        central_compras.write_yaml(self.tmpdir / "config" / "categorias.yaml", categorias)

        global_ancora = central_compras.adjusted_rating(4.8, 30, "generico")
        local_ancora = central_compras.adjusted_rating(4.8, 30, "teste_bayes")
        # Ancora menor deixa a nota bruta pesar mais, aproximando do valor original.
        self.assertGreater(local_ancora, global_ancora)


class AuditScoreBayesianMergeTest(unittest.TestCase):
    """audit_score deve usar a mesma configuracao mesclada que adjusted_rating."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-audit-bayes-"))
        ambiente.montar(self.tmpdir, extras=["projetos", "produtos", "dashboard", "vereditos", "base-conhecimento"])
        self._orig = {
            k: getattr(central_compras, k)
            for k in ["ROOT", "CONFIG", "PROJETOS", "PRODUTOS", "TEMPLATES", "BASE", "VEREDITOS", "DASHBOARD"]
        }
        central_compras.ROOT = self.tmpdir
        central_compras.CONFIG = self.tmpdir / "config"
        central_compras.PROJETOS = self.tmpdir / "projetos"
        central_compras.PRODUTOS = self.tmpdir / "produtos"
        central_compras.TEMPLATES = self.tmpdir / "templates"
        central_compras.BASE = self.tmpdir / "base-conhecimento"
        central_compras.VEREDITOS = self.tmpdir / "vereditos"
        central_compras.DASHBOARD = self.tmpdir / "dashboard"
        central_compras._PREFS_CACHE.clear()

    def tearDown(self):
        for chave, valor in self._orig.items():
            setattr(central_compras, chave, valor)
        central_compras._PREFS_CACHE.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_audit_uses_global_media_when_category_has_only_anchor(self):
        # Altera media global para um valor distinto do default 4.3.
        preferencias = central_compras.read_yaml(self.tmpdir / "config" / "preferencias.yaml", {})
        preferencias["nota_bayesiana"]["media_categoria_padrao"] = 3.5
        central_compras.write_yaml(self.tmpdir / "config" / "preferencias.yaml", preferencias)
        central_compras._PREFS_CACHE.clear()

        # Categoria so com peso_ancora: media deve vir do global.
        categorias = central_compras.read_yaml(self.tmpdir / "config" / "categorias.yaml", {})
        categorias["teste_audit"] = {
            "atributos_obrigatorios": [],
            "nota_bayesiana": {"peso_ancora": 30},
            "gate": {},
        }
        central_compras.write_yaml(self.tmpdir / "config" / "categorias.yaml", categorias)

        import argparse
        central_compras.new_project(argparse.Namespace(
            nome="audit bayes", categoria="teste_audit", valor_estimado=400,
            preco_teto=600, necessidade="teste", force=False))
        projeto = central_compras.PROJETOS / f"{dt.date.today().year}-audit-bayes"
        central_compras.new_product(argparse.Namespace(
            projeto=str(projeto), nome="Produto A", marca="M", categoria="teste_audit",
            produto_id="prod-a", preco_alvo=None, preco_teto=None,
            atributo=[], requisito=["uso=true"], force=False))
        central_compras.add_quote(argparse.Namespace(
            projeto=str(projeto), produto_id="prod-a", loja="Amazon", vendedor="V",
            vendedor_tipo="oficial", anuncio_id=None, variacao=None, preco=299.0,
            preco_promocional=None, frete=0.0, frete_prazo_dias=3, custo_extra=0.0,
            custo_total=None, custo_operacional_mensal=0.0, tco_meses=None,
            valor_revenda_estimado=0.0, nota=4.8, avaliacoes=10, garantia_meses=12,
            garantia_tipo="nacional", link="https://ex.com/a", flag_suspeita="",
            fonte="web", data=None))
        central_compras.build_ranking(argparse.Namespace(projeto=str(projeto)))

        # Valor esperado pela funcao ajustada.
        nota_esperada = central_compras.adjusted_rating(4.8, 10, "teste_audit")

        import io
        import sys
        saida = io.StringIO()
        sys.stdout = saida
        try:
            central_compras.audit_score(argparse.Namespace(projeto=str(projeto), produto_id=None))
        finally:
            sys.stdout = sys.__stdout__

        memoria = (projeto / "memoria-calculo.md").read_text(encoding="utf-8")
        self.assertIn("3.5", memoria, "memoria de calculo nao usou a media global")
        self.assertIn(f"= **{nota_esperada}**", memoria, "nota ajustada da memoria diverge do calculo real")


if __name__ == "__main__":
    unittest.main()
