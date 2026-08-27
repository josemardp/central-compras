"""Regressoes do pacote final de estabilizacao."""

import datetime as dt
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import ambiente
from scripts import central_compras as cc


class Sprint14Test(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-s14-"))
        ambiente.montar(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def cli(self, *args, check=True):
        return subprocess.run(
            [sys.executable, "scripts/central_compras.py", *args],
            cwd=self.tmpdir,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_operating_system_releases_lock_when_owner_dies(self):
        project = self.tmpdir / "projetos" / "crash"
        project.mkdir(parents=True)
        code = (
            "import time; from pathlib import Path; "
            "from scripts import central_compras as cc; "
            "lock=cc.project_lock(Path('projetos/crash')); lock.__enter__(); "
            "print('LOCKED', flush=True); time.sleep(60)"
        )
        child = subprocess.Popen(
            [sys.executable, "-c", code],
            cwd=self.tmpdir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            self.assertEqual(child.stdout.readline().strip(), "LOCKED")
            child.terminate()
            child.wait(timeout=5)
            started = time.monotonic()
            with cc.project_lock(project):
                pass
            self.assertLess(time.monotonic() - started, 2)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            if child.stdout:
                child.stdout.close()
            if child.stderr:
                child.stderr.close()

    def test_append_preserves_extra_header_and_repairs_missing_newline(self):
        project = self.tmpdir / "projetos" / "csv"
        project.mkdir(parents=True)
        header = [*cc.COTACOES_HEADER, "observacao_manual"]
        first = {field: "" for field in header}
        first.update({"data_coleta": "2026-01-01", "produto_id": "a", "custo_total": "100"})
        first["observacao_manual"] = "nao perder"
        import csv
        import io

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerow(first)
        (project / "cotacoes.csv").write_text(buffer.getvalue().rstrip("\n"), encoding="utf-8")

        cc.append_quote(
            project,
            {"data_coleta": "2026-01-02", "produto_id": "a", "custo_total": "90"},
        )
        rows = cc.read_quotes(project)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["observacao_manual"], "nao perder")
        self.assertIn("observacao_manual", (project / "cotacoes.csv").read_text(encoding="utf-8").splitlines()[0])

    def test_dashboard_distinguishes_pending_and_overdue_verdicts(self):
        verdicts = self.tmpdir / "vereditos"
        verdicts.mkdir(parents=True, exist_ok=True)
        yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        (verdicts / "teste.md").write_text(
            "# Veredito\n\n- Projeto: teste\n- Produto: Item\n"
            f"- Veredito D+30 previsto: {yesterday}\n"
            f"- Veredito D+180 previsto: {tomorrow}\n"
            "- D+30 preenchido em:\n- D+180 preenchido em:\n"
            "- D+30 nota arrependimento:\n- D+180 nota arrependimento:\n",
            encoding="utf-8",
        )
        self.cli("dashboard")
        page = (self.tmpdir / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertIn("atrasado 1 dia(s)", page)
        self.assertIn("pendente, faltam 1 dia(s)", page)
        self.assertIn("Fases de veredito atrasadas</td><td class=\"num\">1", page)

    def test_new_project_prints_an_executable_next_command(self):
        result = self.cli("novo-projeto", "cafeteira", "--categoria", "generico")
        self.assertIn("Proximo comando: python scripts/central_compras.py prompt-ia", result.stdout)
        self.assertIn("--etapa modelo", result.stdout)


if __name__ == "__main__":
    unittest.main()
