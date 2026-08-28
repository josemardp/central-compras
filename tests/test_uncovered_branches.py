"""Ramos que a analise de cobertura mostrou sem teste nenhum.

Nao sao todos: aqui estao so os que produziriam uma RESPOSTA ERRADA em
silencio, nao apenas uma mensagem feia.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import central_compras as cc


class ParseScalarTest(unittest.TestCase):
    """`--atributo x=true` e `--requisito r=false` viram gate eliminatorio."""

    def test_booleans_in_portuguese_and_english(self):
        for verdadeiro in ["true", "True", "sim", "yes", "SIM"]:
            self.assertIs(cc.parse_scalar(verdadeiro), True, verdadeiro)
        for falso in ["false", "nao", "não", "no", "FALSE"]:
            self.assertIs(cc.parse_scalar(falso), False, falso)

    def test_null_forms(self):
        for vazio in ["null", "none", "", "   "]:
            self.assertIsNone(cc.parse_scalar(vazio), vazio)

    def test_numbers_and_text(self):
        self.assertEqual(cc.parse_scalar("70"), 70)
        self.assertEqual(cc.parse_scalar("4.5"), 4.5)
        self.assertEqual(cc.parse_scalar("4,5"), 4.5)
        self.assertEqual(cc.parse_scalar("8 anos / 150.000 km"), "8 anos / 150.000 km")

    def test_a_false_requirement_becomes_a_deal_breaker(self):
        produto = {
            "categoria": "fone", "estado": "pesquisando",
            "requisitos_atendidos": cc.parse_pairs(["microfone=false"]),
        }
        row = {"custo_total": "100", "nota": "4.8", "n_avaliacoes": "900",
               "garantia_tipo": "nacional", "garantia_meses": "12", "vendedor_tipo": "oficial"}
        cortes = cc.gate_eliminations(row, produto, {"categoria": "fone"})
        self.assertTrue(any("microfone" in c for c in cortes))


class AdherenceScoreTest(unittest.TestCase):
    """Os quatro produtos reais do Josemar usam `parcial`: esse ramo pesa."""

    def test_partial_counts_half(self):
        self.assertEqual(cc.adherence_score({"requisitos_atendidos": {"a": "parcial"}}), 0.5)
        self.assertEqual(
            cc.adherence_score({"requisitos_atendidos": {"a": True, "b": "parcial"}}), 0.75
        )

    def test_true_counts_full_and_false_counts_zero(self):
        self.assertEqual(cc.adherence_score({"requisitos_atendidos": {"a": True, "b": True}}), 1.0)
        self.assertEqual(cc.adherence_score({"requisitos_atendidos": {"a": False}}), 0.0)

    def test_no_requirements_is_neutral_not_zero(self):
        self.assertEqual(cc.adherence_score({}), 0.5)
        self.assertEqual(cc.adherence_score({"requisitos_atendidos": {}}), 0.5)


class YamlScalarTest(unittest.TestCase):
    """`--gate categoria.campo=valor` grava por este caminho."""

    def test_writes_yaml_literals_not_python_repr(self):
        self.assertEqual(cc.yaml_scalar(True), "true")
        self.assertEqual(cc.yaml_scalar(False), "false")
        self.assertEqual(cc.yaml_scalar(None), "null")
        self.assertEqual(cc.yaml_scalar(150), "150")
        self.assertEqual(cc.yaml_scalar(4.2), "4.2")

    def test_round_trips_through_the_gate_writer(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-ys-"))
        try:
            alvo = tmpdir / "categorias.yaml"
            alvo.write_text("fone:\n  gate:\n    minimo_avaliacoes: 150\n", encoding="utf-8")
            for campo, valor in [("exige_vendedor_oficial", True), ("nota_minima_ajustada", 4.2),
                                 ("garantia_minima_meses", 36), ("desativado", None)]:
                cc.set_category_gate(alvo, "fone", campo, valor)
            import yaml
            gate = yaml.safe_load(alvo.read_text(encoding="utf-8"))["fone"]["gate"]
            self.assertIs(gate["exige_vendedor_oficial"], True)
            self.assertEqual(gate["nota_minima_ajustada"], 4.2)
            self.assertEqual(gate["garantia_minima_meses"], 36)
            self.assertIsNone(gate["desativado"])
        finally:
            shutil.rmtree(tmpdir)


class WaitingWithoutTargetTest(unittest.TestCase):
    def test_waiting_without_a_target_still_says_it_is_waiting(self):
        aviso = cc.waiting_gap(
            {"estado": "aguardando_preco", "aguardando_preco_desde": "2026-01-01"},
            {"custo_total": "300"},
        )
        self.assertIn("aguardando preco", aviso)
        self.assertIn("sem preco_alvo", aviso)


class ProjectLookupTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-look-"))
        self._orig = (cc.ROOT, cc.PROJETOS)
        cc.ROOT = self.tmpdir
        cc.PROJETOS = self.tmpdir / "projetos"
        cc.PROJETOS.mkdir(parents=True)

    def tearDown(self):
        cc.ROOT, cc.PROJETOS = self._orig
        shutil.rmtree(self.tmpdir)

    def criar(self, nome):
        caminho = cc.PROJETOS / nome
        caminho.mkdir()
        (caminho / "briefing.md").write_text("---\ncategoria: fone\n---\n\n# B\n", encoding="utf-8")
        return caminho

    def test_partial_name_resolves_when_unambiguous(self):
        self.criar("2026-fone-bluetooth")
        self.assertEqual(cc.project_path("fone-bluetooth").name, "2026-fone-bluetooth")

    def test_ambiguous_partial_name_says_so_instead_of_guessing(self):
        self.criar("2026-fone-bluetooth")
        self.criar("2026-fone-com-fio")
        with self.assertRaises(SystemExit) as ctx:
            cc.project_path("fone")
        self.assertIn("mais de um projeto", str(ctx.exception))

    def test_unknown_project_lists_what_exists(self):
        self.criar("2026-fone-bluetooth")
        with self.assertRaises(SystemExit) as ctx:
            cc.project_path("carro")
        self.assertIn("2026-fone-bluetooth", str(ctx.exception))

    def test_project_path_traversal_is_blocked(self):
        with self.assertRaises(SystemExit) as ctx:
            cc.project_path(str(cc.CONFIG.resolve()))
        self.assertIn("Projeto nao encontrado", str(ctx.exception))


class VerdictBulletTest(unittest.TestCase):
    """`preencher-veredito` grava campo que o template pode nao ter."""

    def test_replaces_an_existing_bullet(self):
        texto = "# V\n\n- D+30 resumo:\n- Outro: mantem\n"
        novo = cc.replace_or_append_bullet(texto, "D+30 resumo", "chegou certo")
        self.assertIn("- D+30 resumo: chegou certo", novo)
        self.assertIn("- Outro: mantem", novo)

    def test_appends_when_the_bullet_does_not_exist(self):
        texto = "# V\n\n- Outro: mantem\n"
        novo = cc.replace_or_append_bullet(texto, "D+180 licao", "aprendi X")
        self.assertIn("- D+180 licao: aprendi X", novo)
        self.assertIn("- Outro: mantem", novo)

    def test_does_not_duplicate_on_a_second_write(self):
        texto = "# V\n\n- D+30 resumo:\n"
        uma = cc.replace_or_append_bullet(texto, "D+30 resumo", "primeiro")
        duas = cc.replace_or_append_bullet(uma, "D+30 resumo", "segundo")
        self.assertEqual(duas.count("D+30 resumo"), 1)
        self.assertIn("segundo", duas)


if __name__ == "__main__":
    unittest.main()
