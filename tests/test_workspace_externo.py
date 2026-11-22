"""Casa de trabalho externa (`--base`): mesmo motor, dados em outra pasta."""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.ambiente import RepoTestCase


class WorkspaceExternoTest(RepoTestCase):
    def setUp(self):
        super().setUp()
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.casa = Path(stack.enter_context(tempfile.TemporaryDirectory()))

    def _cc(self):
        from scripts import central_compras as cc
        return cc

    def test_novo_projeto_vai_para_a_casa_e_nao_toca_o_motor(self):
        cc = self._cc()
        saida = self.cli("--base", str(self.casa), "novo-projeto", "sacolas",
                         "--categoria", "generico", "--valor-estimado", "100")
        criados = list((self.casa / "projetos").glob("*-sacolas"))
        self.assertEqual(len(criados), 1)
        self.assertTrue((criados[0] / "processo.md").exists())
        self.assertFalse(list((self.root / "projetos").glob("*-sacolas")))
        # Caminho mostrado e relativo a casa, nao absoluto do sistema.
        self.assertIn(f"projetos{os.sep}{criados[0].name}", saida)
        self.assertNotIn(str(self.casa), saida)

    def test_globais_sao_restauradas_depois_do_comando(self):
        cc = self._cc()
        antes = (cc.WORKSPACE, cc.PROJETOS, cc.PRODUTOS, cc.BASE, cc.VEREDITOS, cc.DASHBOARD)
        self.cli("--base", str(self.casa), "init")
        depois = (cc.WORKSPACE, cc.PROJETOS, cc.PRODUTOS, cc.BASE, cc.VEREDITOS, cc.DASHBOARD)
        self.assertEqual(antes, depois)
        self.assertIsNone(cc.WORKSPACE)

    def test_globais_sao_restauradas_mesmo_com_erro(self):
        cc = self._cc()
        antes = cc.PROJETOS
        with self.assertRaises(SystemExit):
            self.cli("--base", str(self.casa), "status", "projeto-que-nao-existe")
        self.assertEqual(cc.PROJETOS, antes)
        self.assertIsNone(cc.WORKSPACE)

    def test_variavel_de_ambiente(self):
        with patch.dict(os.environ, {"CENTRAL_COMPRAS_BASE": str(self.casa)}):
            self.cli("novo-projeto", "via-ambiente", "--categoria", "generico",
                     "--valor-estimado", "50")
        self.assertEqual(len(list((self.casa / "projetos").glob("*-via-ambiente"))), 1)
        self.assertFalse(list((self.root / "projetos").glob("*-via-ambiente")))

    def test_opcao_vence_a_variavel(self):
        outra = self.casa / "outra"
        outra.mkdir()
        with patch.dict(os.environ, {"CENTRAL_COMPRAS_BASE": str(outra)}):
            self.cli("--base", str(self.casa), "novo-projeto", "opcao-manda",
                     "--categoria", "generico", "--valor-estimado", "50")
        self.assertEqual(len(list((self.casa / "projetos").glob("*-opcao-manda"))), 1)
        self.assertFalse(list((outra / "projetos").glob("*")) if (outra / "projetos").exists() else [])

    def test_alias_workspace(self):
        self.cli("--workspace", str(self.casa), "novo-projeto", "alias",
                 "--categoria", "generico", "--valor-estimado", "50")
        self.assertEqual(len(list((self.casa / "projetos").glob("*-alias"))), 1)

    def test_base_inexistente_da_erro_claro_sem_criar_nada(self):
        fantasma = self.casa / "nao-existe"
        with self.assertRaises(SystemExit) as erro:
            self.cli("--base", str(fantasma), "init")
        self.assertIn("--base", str(erro.exception))
        self.assertFalse(fantasma.exists())

    def test_base_que_e_arquivo_da_erro(self):
        arquivo = self.casa / "arquivo.txt"
        arquivo.write_text("x", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.cli("--base", str(arquivo), "init")

    def test_sem_base_nada_muda(self):
        self.cli("novo-projeto", "padrao", "--categoria", "generico", "--valor-estimado", "50")
        self.assertEqual(len(list((self.root / "projetos").glob("*-padrao"))), 1)
        self.assertEqual(list(self.casa.iterdir()), [])

    def test_ciclo_completo_na_casa_e_projeto_por_nome_parcial(self):
        self.cli("--base", str(self.casa), "novo-projeto", "ciclo", "--categoria", "fone",
                 "--valor-estimado", "400")
        projeto = next((self.casa / "projetos").glob("*-ciclo"))
        self.cli("--base", str(self.casa), "novo-produto", "ciclo", "cand",
                 "--produto-id", "cand", "--marca", "Marca A", "--requisito", "uso=true")
        self.assertTrue((self.casa / "produtos").exists())
        self.assertFalse((self.root / "produtos" / "cand").exists())
        self.assertTrue((projeto / "cotacoes.csv").exists())

    def test_base_de_conhecimento_fica_separada_por_casa(self):
        self.cli("--base", str(self.casa), "init")
        self.assertTrue((self.casa / "base-conhecimento" / "marcas").is_dir())
        self.assertTrue((self.casa / "base-conhecimento" / "lojas").is_dir())

    def test_checar_segredos_varre_tambem_a_casa(self):
        cpf_falso = ".".join(["123", "456", "789"]) + "-09"  # montado em runtime: nao vira CPF literal no repo
        (self.casa / "nota.md").write_text(f"cpf {cpf_falso}\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.cli("--base", str(self.casa), "checar-segredos", "--strict")
        # Sem --base a casa nao e varrida.
        self.cli("checar-segredos", "--strict")

    def test_display_path_cai_no_absoluto_fora_das_duas_raizes(self):
        cc = self._cc()
        estranho = Path(tempfile.gettempdir()).resolve() / "fora" / "x"
        self.assertEqual(cc.display_path(estranho), estranho)


if __name__ == "__main__":
    unittest.main()
