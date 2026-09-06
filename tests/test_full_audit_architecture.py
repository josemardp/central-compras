"""Contratos de auditoria: evidencia, conhecimento, fontes e cache isolado."""
import argparse
import io
import json
from unittest.mock import patch

import ambiente
from scripts import central_compras as cc


class ArchitectureAuditTest(ambiente.RepoTestCase):
    def setUp(self):
        super().setUp()
        self.projeto = self.project()
        self.product(self.projeto)

    def test_permanent_lessons_and_category_history_reach_new_research(self):
        cc.append_text(cc.BASE / "licoes.md", "2000-01-01 - geral - Regra antiga permanente\n")
        for i in range(15):
            cc.append_text(cc.BASE / "licoes.md", f"2026-01-01 - fone - Observacao {i}\n")
        cc.atomic_write_text(cc.BASE / "marcas" / "outra.md", "# Outra marca\n- Categoria: fone\n- Resumo: Falha recorrente\n")
        cc.atomic_write_text(self.projeto / "01-definir-modelo.md", "Necessario microfone removivel.")
        prompt = self.cli("prompt-ia", str(self.projeto), "--etapa", "modelo")
        for expected in ("Regra antiga permanente", "Falha recorrente", "microfone removivel", "geracoes", "fonte=web", "candidato"):
            self.assertIn(expected, prompt)

    def test_promotion_is_not_an_independent_offer(self):
        self.quote(self.projeto)
        self.cli("promover-cotacao", str(self.projeto), "--produto-id", "candidato", "--preco", "200")
        rule = cc.stop_rule_status(self.projeto)
        self.assertEqual(rule["ofertas_distintas_atuais"]["candidato"], 1)
        self.assertIn("candidato", rule["produtos_sem_cotacoes_suficientes"])
        self.quote(self.projeto, "candidato", "--loja", "Outra")
        self.assertNotIn("candidato", cc.stop_rule_status(self.projeto)["produtos_sem_cotacoes_suficientes"])

    def test_bypass_is_recorded_and_frozen_inputs_detect_tampering(self):
        self.quote(self.projeto)
        self.cli("decidir", str(self.projeto), "--produto-id", "candidato", "--porque", "simulacao consciente",
                 "--sem-perdedores", "--permitir-web", "--permitir-vencida")
        snap = next((self.projeto / "snapshots").iterdir())
        meta = json.loads((snap / "metadados.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["excecoes"], ["--permitir-web"])
        for name in ("motor.py", "cotacoes.csv", "preferencias.yaml", "categorias.yaml", "briefing.md", "decisao.md", "produtos/candidato.yaml"):
            self.assertTrue((snap / name).exists(), name)
        self.assertIn("EXCECAO fone --permitir-web: 1", self.cli("auditar-decisoes", "--strict"))
        cc.atomic_write_text(snap / "preferencias.yaml", "score: adulterado\n")
        with self.assertRaises(SystemExit):
            self.cli("auditar-decisoes", "--strict")

    def test_preferences_refresh_and_cached_results_cannot_be_mutated(self):
        path = cc.CONFIG / "preferencias.yaml"
        before = cc.preferences()
        before["score"] = {}
        self.assertTrue(cc.preferences()["score"])
        actual = cc.read_yaml(path, {})
        actual["score"]["valor"] = 0.123
        cc.write_yaml(path, actual)
        self.assertEqual(cc.preferences()["score"]["valor"], 0.123)

    def test_a_read_session_parses_each_unchanged_yaml_only_once(self):
        self.quote(self.projeto)
        with patch.object(cc.yaml, "safe_load", wraps=cc.yaml.safe_load) as parser:
            @cc.read_session
            def operation():
                for _ in range(20):
                    cc.find_product("candidato")
                    cc.category_definition("fone")
            operation()
        self.assertEqual(parser.call_count, 2)

    def test_windows_path_is_preserved_in_verdict_text(self):
        value = r"C:\novo\teste\1"
        self.assertEqual(cc.replace_or_append_bullet("- Resumo: antigo", "Resumo", value), "- Resumo: " + value)


class SheetsResponseAuditTest(ambiente.RepoTestCase):
    def sync(self, value):
        response = io.BytesIO(value)
        with patch.object(cc, "carregar_config_sheets", return_value=("https://example.invalid", "segredo-sintetico")), \
             patch.object(cc, "sheets_export_payload", return_value={"visao_geral": [], "comparativos": []}), \
             patch.object(cc.urllib.request, "urlopen", return_value=response):
            cc.sincronizar_planilha(argparse.Namespace(config=None))

    def test_wrong_json_shape_and_truthy_nonboolean_success_are_refused(self):
        for value in (b"[]", b"null", b'{"ok":"false"}'):
            with self.subTest(value=value), self.assertRaises(SystemExit):
                self.sync(value)

    def test_server_response_does_not_reflect_credentials(self):
        for value in (b"<html>segredo-sintetico</html>", b'{"ok":false,"error":"segredo-sintetico"}'):
            with self.assertRaises(SystemExit) as ctx:
                self.sync(value)
            self.assertNotIn("segredo-sintetico", str(ctx.exception))

    def test_timeout_is_a_controlled_error(self):
        with patch.object(cc, "carregar_config_sheets", return_value=("https://example.invalid", "segredo-sintetico")), \
             patch.object(cc, "sheets_export_payload", return_value={"visao_geral": [], "comparativos": []}), \
             patch.object(cc.urllib.request, "urlopen", side_effect=TimeoutError):
            with self.assertRaises(SystemExit):
                cc.sincronizar_planilha(argparse.Namespace(config=None))
