import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from radar import jobs, maquina, varredura


def yaml_com(tmp, oficial):
    p = Path(tmp) / "m.yaml"
    p.write_text(f"maquina_oficial: {oficial}\n" if oficial is not None else "", encoding="utf-8")
    return p


class MaquinaOficialTest(unittest.TestCase):
    def test_oficial_passa_outra_e_barrada_vazio_nao_tem_trava(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("radar.maquina.hostname", return_value="PC-A"):
            self.assertTrue(maquina.pode_rodar(yaml_com(tmp, "pc-a"))[0])          # sem diferenciar caixa
            ok, motivo = maquina.pode_rodar(yaml_com(tmp, "PC-B"))
            self.assertFalse(ok)
            self.assertIn("nao e a oficial", motivo)
            self.assertTrue(maquina.pode_rodar(yaml_com(tmp, ""))[0])
            self.assertTrue(maquina.pode_rodar(Path(tmp) / "nao_existe.yaml")[0])

    def test_forcar_manual_libera(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("radar.maquina.hostname", return_value="PC-A"), \
                mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_FORCAR_MAQUINA": "1"}):
            ok, motivo = maquina.pode_rodar(yaml_com(tmp, "PC-B"))
            self.assertTrue(ok)
            self.assertIn("forcado", motivo)

    def test_job_e_varredura_noutra_maquina_nao_fazem_nada(self):
        with mock.patch("radar.maquina.pode_rodar", return_value=(False, "outra maquina")), mock.patch("builtins.print"), \
                mock.patch("radar.jobs.db.abrir", side_effect=AssertionError("nao deveria abrir o banco")), \
                mock.patch("radar.varredura.db.abrir", side_effect=AssertionError("nao deveria abrir o banco")):
            self.assertEqual(jobs.executar_job("relatorios"), 0)
            self.assertEqual(varredura.executar(enviar=False), 0)

    def test_configuracao_real_aponta_uma_maquina_oficial(self):
        self.assertTrue(maquina.oficial())


if __name__ == "__main__":
    unittest.main()
