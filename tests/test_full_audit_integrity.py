"""Entradas validas, promocao e limites de arquivo da auditoria completa."""

import argparse
import unittest
from unittest.mock import patch

import ambiente
from scripts import central_compras as cc
from scripts import instalar_skill


class IntegrityAuditTest(ambiente.RepoTestCase):
    def test_frontmatter_dashes_inside_a_value_are_not_delimiters(self):
        path = self.root / "briefing.md"
        path.write_text('---\nnota: "antes---depois"\n---\n\nCorpo\n', encoding="utf-8")
        meta, body = cc.load_frontmatter(path)
        self.assertEqual(meta["nota"], "antes---depois")
        self.assertEqual(body, "Corpo\n")

    def test_invalid_frontmatter_reports_the_file(self):
        path = self.root / "briefing.md"
        for data in ('---\nx: [\n---\n', '---\n- lista\n---\n', '---\nx: 1\n'):
            with self.subTest(data=data):
                path.write_text(data, encoding="utf-8")
                with self.assertRaisesRegex(SystemExit, "briefing.md"):
                    cc.load_frontmatter(path)

    def test_infinite_integer_in_legacy_csv_is_reported_without_crashing(self):
        self.assertEqual(cc.quote_int("Infinity"), 0)
        self.assertTrue(cc.numeric_problems({"nota": "4.8", "n_avaliacoes": "Infinity"}))

    def test_product_id_cannot_escape_its_directory(self):
        project = self.project()
        with self.assertRaisesRegex(SystemExit, "produto_id"):
            self.product(project, "../../escape")
        self.assertFalse((self.root / "escape").exists())

    def test_project_lookup_rejects_container_and_nested_directories(self):
        project = self.project()
        nested = project / "snapshots"
        nested.mkdir()
        for path in (cc.PROJETOS, nested):
            with self.subTest(path=path), self.assertRaises(SystemExit):
                cc.project_path(str(path))

    def test_negative_integer_fields_are_rejected_before_append(self):
        project = self.project()
        self.product(project)
        before = (project / "cotacoes.csv").read_bytes()
        for flag in ("--frete-prazo-dias", "--avaliacoes", "--garantia-meses", "--tco-meses"):
            with self.subTest(flag=flag), self.assertRaises(SystemExit):
                self.quote(project, "candidato", flag, "-1")
            self.assertEqual((project / "cotacoes.csv").read_bytes(), before)

    def test_promotion_of_link_alone_cannot_refresh_the_price(self):
        project = self.project()
        self.product(project)
        self.quote(project)
        with self.assertRaisesRegex(SystemExit, "preco"):
            self.cli("promover-cotacao", str(project), "--produto-id", "candidato",
                     "--link", "https://example.invalid/novo")
        self.assertEqual(len(cc.read_quotes(project)), 1)

    def test_new_price_cannot_silently_keep_an_old_promotion(self):
        project = self.project()
        self.product(project)
        self.quote(project, "candidato", "--preco", "300", "--preco-promocional", "200")
        # O campo --preco e preco de etiqueta: nao adivinhar se a promocao acabou.
        with self.assertRaisesRegex(SystemExit, "preco-promocional"):
            self.cli("promover-cotacao", str(project), "--produto-id", "candidato", "--preco", "250")
        self.cli("promover-cotacao", str(project), "--produto-id", "candidato",
                 "--preco", "250", "--preco-promocional", "0")
        self.assertEqual(cc.read_quotes(project)[-1]["custo_total"], "250.0")

    def test_promotion_only_price_is_a_price_confirmation(self):
        project = self.project()
        self.product(project)
        self.quote(project, "candidato", "--preco", "300", "--preco-promocional", "200")
        self.cli("promover-cotacao", str(project), "--produto-id", "candidato",
                 "--preco-promocional", "190")
        row = cc.read_quotes(project)[-1]
        self.assertEqual(row["custo_total"], "190.0")
        self.assertIn("preco-promocional", row["confirmacao"])

    def test_unknown_gate_is_refused_before_any_knowledge_write(self):
        config = (cc.CONFIG / "categorias.yaml").read_bytes()
        lessons = (cc.BASE / "licoes.md").read_bytes()
        with self.assertRaisesRegex(SystemExit, "gate"):
            self.cli("registrar-licao", "Exigir geracao atual", "--categoria", "fone",
                     "--gate", "fone.exige_geracao_atual=true")
        self.assertEqual((cc.CONFIG / "categorias.yaml").read_bytes(), config)
        self.assertEqual((cc.BASE / "licoes.md").read_bytes(), lessons)

    def test_learning_rejects_nonfinite_or_out_of_range_scores(self):
        parser = cc.build_parser()
        for value in ("NaN", "Infinity", "11", "-1"):
            with self.subTest(value=value), self.assertRaises(SystemExit):
                parser.parse_args(["aprender-veredito", "v.md", "--nota-arrependimento", value])

    def test_invalid_gate_types_are_refused(self):
        for gate in ('fone.exige_vendedor_oficial="false"', 'fone.minimo_avaliacoes=-1',
                     'fone.nota_minima_ajustada=6', 'fone.garantia_tipo_aceita=nacional'):
            with self.subTest(gate=gate), self.assertRaises(SystemExit):
                cc.parse_lesson_gate(gate)

    def test_failed_skill_copy_preserves_previous_installation(self):
        source = self.root / "skill-fonte"
        source.mkdir()
        (source / "SKILL.md").write_text("nova", encoding="utf-8")
        destination = self.root / ".codex" / "skills" / "central-compras"
        destination.mkdir(parents=True)
        (destination / "SKILL.md").write_text("anterior", encoding="utf-8")
        with patch.object(instalar_skill.shutil, "copytree", side_effect=OSError("sem espaco")):
            with self.assertRaises(OSError):
                instalar_skill.instalar(source, self.root)
        self.assertEqual((destination / "SKILL.md").read_text(encoding="utf-8"), "anterior")

    def test_source_freeze_does_not_disable_other_threads(self):
        from concurrent.futures import ThreadPoolExecutor
        project = self.project()
        with cc.sources_frozen(), ThreadPoolExecutor(max_workers=1) as pool:
            cc.set_process_state(project, proxima_acao="nao deve gravar")
            pool.submit(cc.set_process_state, project, proxima_acao="acao de outra thread").result()
        self.assertIn("acao de outra thread", (project / "processo.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
