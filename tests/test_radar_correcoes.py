"""Correcoes versionadas do historico: aplicam em memoria e nao alteram o arquivo original."""

import json
import tempfile
import unittest
from pathlib import Path

from radar import correcoes, historico


class CorrecoesTest(unittest.TestCase):
    REGRA = {
        "origem": "rastreador-teste", "produto": "x", "coletado_em": "2026-11-20 08:03",
        "melhor_preco": 122.45, "melhor_onde": "Amazon", "motivo": "teste",
    }

    def _reg(self, hora, preco):
        return {"coletado_em": hora, "modelos": {"x": {"melhor_preco": preco, "melhor_onde": "Leroy"}}}

    def test_aplica_so_na_coleta_e_na_origem_certas_sem_mutar_a_lista_original(self):
        regs = [self._reg("2026-11-20 08:03", 60.65), self._reg("2026-11-20 14:00", 111.89)]
        novos = correcoes.aplicar(regs, "rastreador-teste", [self.REGRA])
        self.assertEqual(novos[0]["modelos"]["x"]["melhor_preco"], 122.45)
        self.assertEqual(novos[0]["modelos"]["x"]["melhor_preco_original"], 60.65)
        self.assertEqual(novos[1]["modelos"]["x"]["melhor_preco"], 111.89)
        self.assertEqual(regs[0]["modelos"]["x"]["melhor_preco"], 60.65)  # original intacto
        outra = correcoes.aplicar(regs, "rastreador-outro", [self.REGRA])
        self.assertEqual(outra[0]["modelos"]["x"]["melhor_preco"], 60.65)

    def test_carregar_jsonl_aplica_correcao_mas_nao_reescreve_o_arquivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = Path(tmp) / "historico.jsonl"
            conteudo = json.dumps(self._reg("2026-11-20 08:03", 60.65)) + "\n"
            arq.write_text(conteudo, encoding="utf-8")
            orig = correcoes.carregar
            correcoes.carregar = lambda caminho=None: [self.REGRA]
            try:
                lido = historico.carregar_jsonl(arq, "rastreador-teste")
            finally:
                correcoes.carregar = orig
            self.assertEqual(lido[0]["modelos"]["x"]["melhor_preco"], 122.45)
            self.assertEqual(arq.read_text(encoding="utf-8"), conteudo)

    def test_correcao_real_do_chuveiro_esta_registrada_com_motivo(self):
        regras = correcoes.carregar()
        chuveiro = [c for c in regras if c["origem"] == "rastreador-chuveiro"]
        self.assertTrue(chuveiro)
        self.assertEqual(chuveiro[0]["coletado_em"], "2026-11-20 08:03")
        self.assertIn("VERIFICAR", chuveiro[0]["motivo"])  # a causa exata e inferida: fica declarado


if __name__ == "__main__":
    unittest.main()
