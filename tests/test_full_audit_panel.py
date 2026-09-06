"""Reproducoes HTTP e de apresentacao, usando servidor local descartavel."""

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import ambiente
from scripts import central_compras as cc
from scripts import painel


class PanelAuditTest(ambiente.RepoTestCase):
    def setUp(self):
        super().setUp()
        self.projeto = self.project()
        self.product(self.projeto)
        self.quote(self.projeto)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), painel._Handler)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def request(self, data, headers=None):
        req = urllib.request.Request(self.url + "/api/acao", data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def test_json_arrays_and_wrong_field_types_return_a_controlled_error(self):
        for payload in ([], None, 42, {"projeto": []}, {"acao": []}, {"dados": [1]}):
            with self.subTest(payload=payload):
                status, result = self.request(payload)
                self.assertEqual(status, 400)
                self.assertFalse(result["ok"])

    def test_foreign_origin_cannot_write_with_json(self):
        before = (self.projeto / "ranking.md").read_bytes()
        status, _ = self.request({"projeto": self.projeto.name, "acao": "ranking"},
                                 {"Origin": "https://foreign.example"})
        self.assertEqual(status, 403)
        self.assertEqual((self.projeto / "ranking.md").read_bytes(), before)

    def test_foreign_host_is_refused(self):
        status, _ = self.request({"projeto": self.projeto.name, "acao": "ranking"},
                                 {"Host": "foreign.example"})
        self.assertEqual(status, 403)

    def test_same_origin_still_works(self):
        status, result = self.request({"projeto": self.projeto.name, "acao": "ranking"},
                                      {"Origin": self.url})
        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])

    def test_fractional_or_negative_integer_is_not_silently_truncated(self):
        for value in ("3.5", "-1"):
            result = painel.acao(self.projeto, "cotar", {
                "produto_id": "candidato", "loja": "A", "preco": "100",
                "frete_prazo_dias": value,
            })
            self.assertFalse(result["ok"], result)
        self.assertEqual(len(cc.read_quotes(self.projeto)), 1)

    def test_numeric_json_price_zero_is_not_mistaken_for_missing(self):
        result = painel.acao(self.projeto, "cotar", {
            "produto_id": "candidato", "loja": "A", "preco": 0,
        })
        # Zero pode ser registrado, mas e cortado pelo gate; nao e campo ausente.
        self.assertTrue(result["ok"], result)

    def test_artifact_uses_tco_when_that_is_the_comparison_base(self):
        item = cc.compute_ranking(self.projeto)[0][0]
        item.quote["tco_total"] = "80"
        line = painel._linha_ranking(item, "tco_total", "TCO")
        rendered = painel._bloco_produto(line, False)
        self.assertIn("R$ 80,00", rendered)
        self.assertIn("TCO", rendered)


if __name__ == "__main__":
    unittest.main()
