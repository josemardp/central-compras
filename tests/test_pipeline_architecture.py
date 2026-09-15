"""Regressoes reproduzidas na auditoria do pipeline, sem dados de compras reais."""

import contextlib
import datetime as dt
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ambiente
from scripts import central_compras as cc


class PipelineArchitectureTest(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        ambiente.montar(root)
        directories = {
            key: getattr(cc, key).relative_to(cc.ROOT)
            for key in ("ROOT", "CONFIG", "PROJETOS", "PRODUTOS", "TEMPLATES",
                        "BASE", "VEREDITOS", "DASHBOARD")
        }
        for key, directory in directories.items():
            self.stack.enter_context(patch.object(cc, key, root / directory))
        self.stack.enter_context(patch.object(cc, "_PREFS_CACHE", {}))
        self.cli("novo-projeto", "auditoria", "--categoria", "fone",
                 "--valor-estimado", "400", "--preco-teto", "600")
        self.project = cc.PROJETOS / f"{dt.date.today().year}-auditoria"
        self.cli("novo-produto", str(self.project), "Candidato",
                 "--produto-id", "candidato", "--marca", "Marca A",
                 "--requisito", "uso=true")

    def cli(self, *argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            cc.main(list(argv))
        return output.getvalue()

    def quote(self, store, price, *extra):
        self.cli(
            "cotar", str(self.project), "--produto-id", "candidato",
            "--loja", store, "--preco", str(price), "--data", cc.today(),
            "--fonte", "manual", "--vendedor", "V", "--vendedor-tipo", "oficial",
            "--nota", "4.8", "--avaliacoes", "1000", "--frete-prazo-dias", "2",
            "--garantia-tipo", "nacional", "--garantia-meses", "12",
            "--link", "https://example.invalid/item", *extra,
        )

    def decide(self, *extra):
        return self.cli("decidir", str(self.project), "--produto-id", "candidato",
                        "--porque", "criterio registrado", "--sem-perdedores", *extra)

    def assert_snapshot_matches_quote(self, expected):
        snapshot = next((self.project / "snapshots").glob("*/metadados.json"))
        metadata = json.loads(snapshot.read_text(encoding="utf-8"))
        self.assertEqual(metadata["cotacao"], expected)
        canonical = json.dumps(expected, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        self.assertEqual(metadata["cotacao_sha256"], hashlib.sha256(canonical.encode()).hexdigest())
        rows = cc.read_csv_file(snapshot.parent / "ranking.csv")
        chosen = next(row for row in rows if row["produto_id"] == "candidato")
        self.assertEqual(chosen["custo_total"], expected["custo_total"])

    def test_decision_freezes_the_same_offer_as_ranking_in_a_date_tie(self):
        self.quote("A", 200)
        self.quote("B", 300)
        expected = cc.read_quotes(self.project)[0]
        self.assertEqual(cc.compute_ranking(self.project)[0][0].quote, expected)
        before = (self.project / "cotacoes.csv").read_bytes()
        self.decide()
        self.assert_snapshot_matches_quote(expected)
        decision = (self.project / "decisao.md").read_text(encoding="utf-8")
        self.assertIn("Custo total confirmado: R$ 200,00", decision)
        self.assertEqual((self.project / "cotacoes.csv").read_bytes(), before)

    def test_later_rejected_offer_does_not_force_a_bypass_for_an_eligible_one(self):
        yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        self.quote("A", 200, "--data", yesterday)
        self.quote("B", 300, "--garantia-tipo", "nenhuma")
        expected = cc.read_quotes(self.project)[0]
        self.assertEqual(cc.compute_ranking(self.project)[0][0].quote, expected)
        self.decide()
        self.assert_snapshot_matches_quote(expected)

    def test_web_bypass_does_not_describe_an_estimate_as_confirmed(self):
        self.quote("A", 200, "--fonte", "web")
        with self.assertRaisesRegex(SystemExit, "nao e manual"):
            self.decide()
        self.decide("--permitir-web")
        decision = (self.project / "decisao.md").read_text(encoding="utf-8")
        self.assertIn("Custo total estimado (fonte=web): R$ 200,00", decision)
        self.assertNotIn("Custo total confirmado", decision)

    def test_new_lessons_do_not_erase_knowledge_that_predated_a_purchase(self):
        yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        path = cc.BASE / "licoes.md"
        path.write_text(
            f"{yesterday} - geral - Regra geral anterior.\n"
            f"{yesterday} - carro - Outra categoria nao deve contar.\n",
            encoding="utf-8",
        )
        self.assertEqual(cc.knowledge_predating(self.project)["licoes"], 1)
        with path.open("a", encoding="utf-8") as stream:
            stream.writelines(f"{cc.today()} - fone - Nova licao {i}.\n" for i in range(10))
        self.assertEqual(len(cc.lesson_lines_for_category("fone")), 10)
        self.assertEqual(cc.knowledge_predating(self.project)["licoes"], 1)
        self.assertTrue(cc.reuse_stats()[0][0]["reaproveitou"])

    def test_dashboard_ignores_orphan_project_directories(self):
        orphan = cc.PROJETOS / f"{dt.date.today().year}-projeto-removido"
        orphan.mkdir()

        rows, total, _, _ = cc.reuse_stats()
        self.assertEqual(total, 1)
        self.assertNotIn(orphan.name, {row["projeto"] for row in rows})

        self.cli("dashboard")
        self.assertTrue((cc.DASHBOARD / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
