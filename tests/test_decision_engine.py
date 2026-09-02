import datetime as dt
import argparse
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


class RankingProcessStepsTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-ranking-steps-"))
        ambiente.montar(self.tmpdir)
        self._orig = {
            key: getattr(central_compras, key)
            for key in ["ROOT", "CONFIG", "PROJETOS", "PRODUTOS", "TEMPLATES", "BASE", "VEREDITOS", "DASHBOARD"]
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

        import argparse
        central_compras.new_project(argparse.Namespace(
            nome="ranking etapas", categoria="generico", valor_estimado=400,
            preco_teto=600, necessidade="teste", force=False))
        self.projeto = central_compras.PROJETOS / f"{dt.date.today().year}-ranking-etapas"
        for produto_id, nome in [("prod-a", "Produto A"), ("prod-b", "Produto B")]:
            central_compras.new_product(argparse.Namespace(
                projeto=str(self.projeto), nome=nome, marca="M", categoria="generico",
                produto_id=produto_id, preco_alvo=None, preco_teto=None,
                atributo=[], requisito=["uso=true"], force=False))

    def tearDown(self):
        for key, value in self._orig.items():
            setattr(central_compras, key, value)
        central_compras._PREFS_CACHE.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def add_quote(self, produto_id, preco):
        import argparse
        central_compras.add_quote(argparse.Namespace(
            projeto=str(self.projeto), produto_id=produto_id, loja="Loja", vendedor="V",
            vendedor_tipo="oficial", anuncio_id=None, variacao=None, preco=preco,
            preco_promocional=None, frete=0.0, frete_prazo_dias=3, custo_extra=0.0,
            custo_total=None, custo_operacional_mensal=0.0, tco_meses=None,
            valor_revenda_estimado=0.0, nota=4.8, avaliacoes=1000, garantia_meses=12,
            garantia_tipo="nacional", link=f"https://example.com/{produto_id}",
            flag_suspeita="", fonte="web", data=None))

    def test_ranking_without_quotes_keeps_gate_and_comparison_unchecked(self):
        import argparse
        args = argparse.Namespace(projeto=str(self.projeto))

        central_compras.build_ranking(args)
        central_compras.build_ranking(args)

        processo = (self.projeto / "processo.md").read_text(encoding="utf-8")
        self.assertIn("- [ ] 5. Aplicar gates eliminatorios", processo)
        self.assertIn("- [ ] 6. Comparar finalistas", processo)

    def test_ranking_with_two_eligible_quotes_marks_gate_and_comparison(self):
        import argparse
        self.add_quote("prod-a", 299.0)
        self.add_quote("prod-b", 349.0)

        central_compras.build_ranking(argparse.Namespace(projeto=str(self.projeto)))

        processo = (self.projeto / "processo.md").read_text(encoding="utf-8")
        self.assertIn("- [x] 5. Aplicar gates eliminatorios", processo)
        self.assertIn("- [x] 6. Comparar finalistas", processo)

    def test_ranking_with_one_quote_marks_gate_but_not_comparison(self):
        import argparse
        self.add_quote("prod-a", 299.0)

        central_compras.build_ranking(argparse.Namespace(projeto=str(self.projeto)))

        processo = (self.projeto / "processo.md").read_text(encoding="utf-8")
        self.assertIn("- [x] 5. Aplicar gates eliminatorios", processo)
        self.assertIn("- [ ] 6. Comparar finalistas", processo)


class RankingGateAwareQuoteSelectionTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-camera-gate-"))
        ambiente.montar(self.tmpdir, extras=["dashboard", "vereditos"])
        self._orig = {
            key: getattr(central_compras, key)
            for key in ["ROOT", "CONFIG", "PROJETOS", "PRODUTOS", "TEMPLATES", "BASE", "VEREDITOS", "DASHBOARD"]
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

        categorias = central_compras.read_yaml(central_compras.CONFIG / "categorias.yaml", {})
        categorias["camera"] = {
            "atributos_obrigatorios": ["resolucao", "visao_noturna", "ip_rating", "conexao", "armazenamento_tipo"],
            "gate": {
                "nota_minima_ajustada": 4.2,
                "minimo_avaliacoes": 150,
                "garantia_tipo_aceita": ["nacional", "vendedor"],
            },
        }
        central_compras.write_yaml(central_compras.CONFIG / "categorias.yaml", categorias)

    def tearDown(self):
        for key, value in self._orig.items():
            setattr(central_compras, key, value)
        central_compras._PREFS_CACHE.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def add_quote(self, *, loja: str, preco: float, nota: float, avaliacoes: int, garantia_tipo: str) -> None:
        central_compras.add_quote(argparse.Namespace(
            projeto=str(self.projeto), produto_id="intelbras-im5-sc", loja=loja, vendedor=loja,
            vendedor_tipo="oficial", anuncio_id=None, variacao=None, preco=preco,
            preco_promocional=None, frete=0.0, frete_prazo_dias=2, custo_extra=0.0,
            custo_total=None, custo_operacional_mensal=0.0, tco_meses=None,
            valor_revenda_estimado=0.0, nota=nota, avaliacoes=avaliacoes, garantia_meses=12,
            garantia_tipo=garantia_tipo, link=f"https://example.com/{loja}", flag_suspeita="",
            fonte="manual", data="2026-08-31",
        ))

    def test_same_day_quote_without_accepted_warranty_does_not_hide_valid_quote(self):
        central_compras.new_project(argparse.Namespace(
            nome="camera de monitoramento externa", categoria="camera", valor_estimado=800,
            preco_teto=800, necessidade="camera externa", force=False,
        ))
        self.projeto = central_compras.PROJETOS / f"{dt.date.today().year}-camera-de-monitoramento-externa"
        central_compras.new_product(argparse.Namespace(
            projeto=str(self.projeto), nome="Intelbras iM5 SC", marca="Intelbras",
            categoria="camera", produto_id="intelbras-im5-sc", preco_alvo=None, preco_teto=None,
            atributo=[
                "resolucao=1080p",
                "visao_noturna=true",
                "ip_rating=IP67",
                "conexao=wifi",
                "armazenamento_tipo=microSD",
            ],
            requisito=["app_qualidade=true"], force=False,
        ))

        self.add_quote(loja="Mercado Livre", preco=329.63, nota=4.9, avaliacoes=9112, garantia_tipo="nacional")
        self.add_quote(loja="Amazon", preco=253.71, nota=4.8, avaliacoes=1608, garantia_tipo="nenhuma")

        elegiveis, cortados = central_compras.compute_ranking(self.projeto)

        self.assertEqual([item.produto_id for item in elegiveis], ["intelbras-im5-sc"])
        self.assertEqual(cortados, [])
        self.assertEqual(elegiveis[0].quote["loja"], "Mercado Livre")
        self.assertEqual(elegiveis[0].quote["garantia_tipo"], "nacional")


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

    def test_material_construcao_uses_lower_anchor_than_global(self):
        # material_construcao tem peso_ancora proprio, menor que o global 250.
        # Com 30 avaliacoes e nota 4.8, o global esmaga perto de 4.35; o local
        # deve ficar bem acima disso, sem chegar a 4.8.
        global_anchor = central_compras.adjusted_rating(4.8, 30, "generico")
        material_anchor = central_compras.adjusted_rating(4.8, 30, "material_construcao")
        self.assertLess(material_anchor, 4.8)
        self.assertGreater(material_anchor, global_anchor)


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
