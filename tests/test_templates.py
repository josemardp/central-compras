"""Templates nao podem divergir do que o codigo realmente escreve.

`templates/produto.yaml` nao e lido por nenhum comando: ele existe como
documentacao do schema. Sem um teste, ele envelhece calado e passa a mentir.
"""

import unittest
from pathlib import Path

import yaml

from scripts import central_compras as cc


ROOT = Path(__file__).resolve().parents[1]


class ProductTemplateTest(unittest.TestCase):
    def test_template_documents_every_field_the_cli_writes(self):
        template = yaml.safe_load((ROOT / "templates" / "produto.yaml").read_text(encoding="utf-8"))
        escritos = {
            "id",
            "categoria",
            "nome",
            "marca",
            "estado",
            "projeto",
            "preco_alvo",
            "preco_teto",
            "atributos",
            "requisitos_atendidos",
            "descartado_porque",
            "aguardando_preco_desde",
            "aguardando_preco_porque",
        }
        faltando = escritos - set(template)
        self.assertFalse(faltando, f"template desatualizado, faltam campos: {sorted(faltando)}")


class BriefingTemplateTest(unittest.TestCase):
    def test_stop_rule_placeholders_match_what_the_code_replaces(self):
        # `novo-projeto` substitui esse bloco pela regra da faixa de valor.
        # Se o template mudar, a substituicao falha em silencio.
        texto = (ROOT / "templates" / "briefing.md").read_text(encoding="utf-8")
        self.assertIn(
            "- Tempo maximo de pesquisa:\n- Numero maximo de candidatos:\n- Cotacoes minimas por candidato:",
            texto,
        )


class VerdictTemplateTest(unittest.TestCase):
    def test_verdict_has_the_bullets_the_learning_export_reads(self):
        texto = (ROOT / "templates" / "veredito.md").read_text(encoding="utf-8")
        for rotulo in ["- Marca:", "- Loja:", "- Categoria:", "- Projeto:", "- Produto:", "- Vendedor:"]:
            self.assertIn(rotulo, texto, f"veredito sem o campo {rotulo}")


class CategoryConfigTest(unittest.TestCase):
    def test_every_declared_gate_is_actually_enforced(self):
        """Gate declarado em categorias.yaml e nunca lido e falsa seguranca."""
        categorias = yaml.safe_load((ROOT / "config" / "categorias.yaml").read_text(encoding="utf-8"))
        codigo = (ROOT / "scripts" / "central_compras.py").read_text(encoding="utf-8")
        declarados = {
            campo
            for definicao in categorias.values()
            for campo in (definicao.get("gate") or {})
        }
        nao_aplicados = [campo for campo in sorted(declarados) if f'"{campo}"' not in codigo]
        self.assertFalse(nao_aplicados, f"gates declarados mas nunca aplicados: {nao_aplicados}")

    def test_score_weights_sum_to_one(self):
        pesos = cc.preferences()["score"]
        self.assertAlmostEqual(sum(pesos.values()), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
