"""Integridade da serie historica.

Principio 1 do PRD: fato datado nunca e sobrescrito. Como `cotacoes.csv` e
reescrito inteiro a cada gravacao, qualquer coluna que o schema nao conheca
precisa sobreviver a ida e volta.
"""

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import central_compras as cc


class CsvIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-csv-"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def write_csv(self, header, rows):
        with (self.tmpdir / "cotacoes.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

    def test_unknown_column_survives_read_and_write(self):
        self.write_csv(
            ["data_coleta", "produto_id", "custo_total", "observacao_minha"],
            [["2026-01-01", "x", "100", "anotacao que eu escrevi a mao"]],
        )
        rows = cc.read_quotes(self.tmpdir)
        cc.write_quotes(self.tmpdir, rows)
        texto = (self.tmpdir / "cotacoes.csv").read_text(encoding="utf-8")

        self.assertIn("observacao_minha", texto)
        self.assertIn("anotacao que eu escrevi a mao", texto)

    def test_old_schema_is_upgraded_without_losing_rows(self):
        header_antigo = [c for c in cc.COTACOES_HEADER if not c.startswith("tco") and "operacional" not in c and "revenda" not in c]
        self.write_csv(header_antigo, [["v" for _ in header_antigo]])
        rows = cc.read_quotes(self.tmpdir)
        cc.write_quotes(self.tmpdir, rows)

        novo = cc.quotes_header(self.tmpdir)
        recarregado = cc.read_quotes(self.tmpdir)
        self.assertIn("tco_total", novo)
        self.assertIn("custo_operacional_mensal", novo)
        self.assertEqual(len(recarregado), 1)

    def test_row_longer_than_header_is_not_silently_truncated(self):
        with (self.tmpdir / "cotacoes.csv").open("w", encoding="utf-8", newline="") as f:
            f.write("data_coleta,produto_id\n2026-01-01,x,valor-perdido\n")
        rows = cc.read_quotes(self.tmpdir)
        self.assertIn("valor-perdido", "".join(rows[0].values()))


class NumericValidationTest(unittest.TestCase):
    def test_malformed_price_is_reported_instead_of_becoming_zero(self):
        problems = cc.numeric_problems({"preco": "1.2.3", "nota": "4.5", "n_avaliacoes": "100"})
        self.assertTrue(any("preco" in p for p in problems))

    def test_inconsistent_total_is_reported(self):
        problems = cc.numeric_problems(
            {"preco": "100", "frete_valor": "10", "custo_extra": "0", "custo_total": "100"}
        )
        self.assertTrue(any("custo_total" in p for p in problems))

    def test_rating_without_volume_is_reported(self):
        problems = cc.numeric_problems({"nota": "4.8", "n_avaliacoes": "0"})
        self.assertTrue(any("n_avaliacoes" in p for p in problems))

    def test_consistent_row_has_no_problem(self):
        self.assertEqual(
            cc.numeric_problems(
                {
                    "preco": "100",
                    "frete_valor": "10",
                    "custo_extra": "0",
                    "custo_total": "110",
                    "nota": "4.5",
                    "n_avaliacoes": "300",
                }
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
