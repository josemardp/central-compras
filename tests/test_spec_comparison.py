"""Quadro comparativo (spec_comparison_section) e as estrelas nas linhas comerciais.

Ambiente isolado de proposito (mesmo padrao de RankingGateAwareQuoteSelectionTest
em test_decision_engine.py): categoria `camera` propria neste tmpdir, nao a
config/categorias.yaml real do repositorio.
"""

import argparse
import datetime as dt
import re
import shutil
import tempfile
from pathlib import Path

import ambiente
import unittest

from scripts import central_compras as cc


def _linha_da_tabela(html: str, rotulo: str) -> str:
    """Isola o `<tr>...</tr>` de uma linha pelo rotulo da 1a celula.

    As linhas do quadro comparativo sao concatenadas sem quebra entre si
    (spec_rows/comercial_rows sao uma unica string), entao `splitlines()`
    devolve o bloco inteiro de uma vez - isso isola so a linha pedida.
    """
    match = re.search(rf"<tr><td>{re.escape(rotulo)}</td>.*?</tr>", html)
    assert match, f"linha '{rotulo}' nao encontrada no HTML"
    return match.group(0)


class SpecComparisonTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-spec-comparison-"))
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
            "atributos_obrigatorios": ["resolucao", "conexao", "armazenamento_tipo"],
            "gate": {"garantia_tipo_aceita": ["nacional", "vendedor", "nenhuma"]},
            "estrelas": {
                "resolucao": {
                    "faixas": [
                        {"min": 8, "estrelas": 5},
                        {"min": 3, "estrelas": 4},
                        {"min": 1.9, "estrelas": 3},
                        {"min": 0, "estrelas": 1},
                    ]
                }
            },
        }
        cc.write_yaml(cc.CONFIG / "categorias.yaml", categorias)

        cc.new_project(argparse.Namespace(
            nome="camera de teste", categoria="camera", valor_estimado=500,
            preco_teto=800, necessidade="teste", force=False,
        ))
        self.projeto = cc.PROJETOS / f"{dt.date.today().year}-camera-de-teste"

    def tearDown(self):
        for key, value in self._orig.items():
            setattr(cc, key, value)
        cc._PREFS_CACHE.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _novo_produto(self, produto_id: str, *, resolucao_display: str, resolucao_classificacao) -> None:
        cc.new_product(argparse.Namespace(
            projeto=str(self.projeto), nome=produto_id, marca="Marca",
            categoria="camera", produto_id=produto_id, preco_alvo=None, preco_teto=None,
            atributo=[
                f"resolucao={resolucao_display}",
                "conexao=wifi",
                "armazenamento_tipo=sd",
            ],
            requisito=[], force=False,
        ))
        path = cc.find_product_path(produto_id)
        data = cc.read_yaml(path, {})
        data["atributos_classificacao"] = {"resolucao": resolucao_classificacao}
        cc.write_yaml(path, data)

    def _cotar(self, produto_id: str, *, preco: float, nota=None, avaliacoes=0,
               garantia_tipo="nacional", garantia_meses=12) -> None:
        cc.add_quote(argparse.Namespace(
            projeto=str(self.projeto), produto_id=produto_id, loja="Loja", vendedor="Loja",
            vendedor_tipo="oficial", anuncio_id=None, variacao=None, preco=preco,
            preco_promocional=None, frete=0.0, frete_prazo_dias=2, custo_extra=0.0,
            custo_total=None, custo_operacional_mensal=0.0, tco_meses=None,
            valor_revenda_estimado=0.0, nota=nota, avaliacoes=avaliacoes,
            garantia_meses=garantia_meses, garantia_tipo=garantia_tipo,
            link="https://example.com", flag_suspeita="",
            fonte="manual", data="2026-08-31",
        ))

    def test_starred_row_shows_star_glyphs_in_html(self):
        self._novo_produto("cam-a", resolucao_display="1080p", resolucao_classificacao=2)
        self._cotar("cam-a", preco=200, nota=4.5, avaliacoes=500)

        html = cc.spec_comparison_section(self.projeto)

        self.assertIn("★", html)
        self.assertIn("1080p", html)  # texto original continua visivel ao lado da estrela

    def test_field_without_rubric_never_shows_a_star(self):
        self._novo_produto("cam-a", resolucao_display="1080p", resolucao_classificacao=2)
        self._cotar("cam-a", preco=200, nota=4.5, avaliacoes=500)

        html = cc.spec_comparison_section(self.projeto)
        # `conexao` e `armazenamento_tipo` nao tem regua de estrela nesta categoria
        # de teste. Isola so a linha da Conexao e confere que ela nao carrega o glifo.
        self.assertNotIn("★", _linha_da_tabela(html, "Conexao"))

    def test_candidate_missing_classification_shows_raw_text_without_crashing(self):
        # cam-b tem atributo de exibicao mas nunca recebeu atributos_classificacao.
        cc.new_product(argparse.Namespace(
            projeto=str(self.projeto), nome="cam-b", marca="Marca",
            categoria="camera", produto_id="cam-b", preco_alvo=None, preco_teto=None,
            atributo=["resolucao=720p", "conexao=wifi", "armazenamento_tipo=sd"],
            requisito=[], force=False,
        ))
        self._cotar("cam-b", preco=150, nota=4.0, avaliacoes=200)

        html = cc.spec_comparison_section(self.projeto)
        self.assertIn("720p", html)

    def test_tied_absolute_values_render_the_same_stars(self):
        self._novo_produto("cam-a", resolucao_display="1080p", resolucao_classificacao=2)
        self._novo_produto("cam-b", resolucao_display="1080p (outra marca)", resolucao_classificacao=2)
        self._cotar("cam-a", preco=200, nota=4.5, avaliacoes=500)
        self._cotar("cam-b", preco=250, nota=4.5, avaliacoes=500)

        html = cc.spec_comparison_section(self.projeto)
        linha_resolucao = _linha_da_tabela(html, "Resolucao")
        self.assertEqual(linha_resolucao.count("★★★☆☆"), 2, "mesmo valor absoluto tem que empatar na mesma estrela")


class NotaStarGuardTest(unittest.TestCase):
    """Nota sem dado (eixo qualidade fora da conta) nunca pode virar 1 estrela por tabela."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-nota-star-"))
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

        cc.new_project(argparse.Namespace(
            nome="fone de teste", categoria="fone", valor_estimado=300,
            preco_teto=500, necessidade="teste", force=False,
        ))
        self.projeto = cc.PROJETOS / f"{dt.date.today().year}-fone-de-teste"
        cc.new_product(argparse.Namespace(
            projeto=str(self.projeto), nome="fone-sem-nota", marca="Marca",
            categoria="fone", produto_id="fone-sem-nota", preco_alvo=None, preco_teto=None,
            atributo=["tipo=intra", "conexao=bluetooth", "microfone=true",
                      "bateria_horas=8", "garantia_meses=12"],
            requisito=[], force=False,
        ))
        cc.add_quote(argparse.Namespace(
            projeto=str(self.projeto), produto_id="fone-sem-nota", loja="Loja", vendedor="Loja",
            vendedor_tipo="oficial", anuncio_id=None, variacao=None, preco=100.0,
            preco_promocional=None, frete=0.0, frete_prazo_dias=2, custo_extra=0.0,
            custo_total=None, custo_operacional_mensal=0.0, tco_meses=None,
            valor_revenda_estimado=0.0, nota=None, avaliacoes=0,
            garantia_meses=12, garantia_tipo="nacional",
            link="https://example.com", flag_suspeita="",
            fonte="manual", data="2026-08-31",
        ))

    def tearDown(self):
        for key, value in self._orig.items():
            setattr(cc, key, value)
        cc._PREFS_CACHE.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_rating_shows_no_star_not_one_star(self):
        elegiveis, cortados = cc.compute_ranking(self.projeto)
        item = (elegiveis + cortados)[0]
        self.assertIn("qualidade", item.eixos_sem_dado)

        html = cc.spec_comparison_section(self.projeto)
        self.assertNotIn("★", _linha_da_tabela(html, "Nota"), "nota ausente nao pode renderizar estrela nenhuma")


if __name__ == "__main__":
    unittest.main()
