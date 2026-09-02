"""O varredor de dado sensivel precisa achar o que importa e calar no resto.

Scanner que nunca acha nada da falsa seguranca; scanner que acusa tudo e
desligado na primeira semana.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import central_compras as cc


class SecretScanTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-sec-"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def escrever(self, nome, conteudo):
        caminho = self.tmpdir / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(conteudo, encoding="utf-8")

    def codigos(self):
        return {codigo for _, _, codigo, _ in cc.scan_sensitive(self.tmpdir)}

    def test_finds_a_formatted_cpf(self):
        self.escrever("nota.md", "Dados para nota: 000.000.001-91\n")  # central-compras:exemplo-nao-e-segredo
        self.assertIn("CPF", self.codigos())

    def test_finds_a_cep(self):
        self.escrever("endereco.html", "Entrega em 01310-100\n")  # central-compras:exemplo-nao-e-segredo
        self.assertIn("CEP", self.codigos())

    def test_finds_a_card_number(self):
        # Numero de teste publico (Visa), valido no Luhn.
        self.escrever("pagamento.md", "cartao usado: 4111 1111 1111 1111\n")  # central-compras:exemplo-nao-e-segredo
        self.assertIn("CARTAO", self.codigos())

    def test_finds_password_and_token(self):
        self.escrever("config.yaml", "senha: minhaSenhaSecreta\napi_key: abcdef1234567890xyz\n")  # central-compras:exemplo-nao-e-segredo
        codigos = self.codigos()
        self.assertIn("SENHA", codigos)
        self.assertIn("TOKEN", codigos)

    def test_finds_a_github_token(self):
        self.escrever("notas.md", "ghp_" + "A1b2C3d4E5f6G7h8I9j0" + "\n")
        self.assertIn("GITHUB", self.codigos())

    def test_does_not_flag_ordinary_purchase_data(self):
        # Numeros que aparecem o tempo todo num repositorio de compras e que
        # NAO podem virar alarme: anuncio, CEP, preco, EAN, data.
        self.escrever(
            "cotacoes.csv",
            "data_coleta,anuncio_id,cep,preco,ean\n"
            "2026-08-26T13:48:20,MLB63419175,16700000,296.64,7891234567895\n"
            "2026-08-26T13:48:21,B0CZ6J92ML,15810000,499.00,1234567890123\n",
        )
        self.assertEqual(self.codigos(), set(), "alarme falso em dado normal de compra")

    def test_ignores_the_private_data_folder(self):
        self.escrever("dados-privados/endereco.md", "CPF: 000.000.001-91\n")  # central-compras:exemplo-nao-e-segredo
        self.assertEqual(self.codigos(), set())

    def test_real_repository_is_clean(self):
        raiz = Path(__file__).resolve().parents[1]
        achados = cc.scan_sensitive(raiz)
        self.assertEqual(achados, [], f"dado sensivel na arvore versionada: {achados}")


if __name__ == "__main__":
    unittest.main()
