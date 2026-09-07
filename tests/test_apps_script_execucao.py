"""Executa de verdade, sob Node, o JavaScript documentado em
docs/integracao-google-sheets.md - nao so confere presenca de string.

Motivo: revisao do Codex sobre o commit d6246b6 apontou que
AppsScriptDocumentadoTest (asserts de string) nao prova comportamento -
achou 3 lacunas reais (colisao com aba manual, payload invalido causando
escrita parcial, diagnostico de falha incompleto) que nenhum assert de
presenca de texto pegaria. Estes testes carregam o Code.gs de fato (extraido
do doc) num ambiente Node com fakes minimos do runtime do Apps Script
(tests/apps_script/fakes.js) e chamam doPost() de ponta a ponta.

Pula (nao falha) se o executavel `node` nao existir na maquina - mesmo
padrao de tolerancia a ambiente que o resto do repo usa para dependencias
opcionais, mas o motivo do skip fica bem visivel no relatorio da suite.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENARIOS = ROOT / "tests" / "apps_script" / "cenarios"
NODE = shutil.which("node")


def _extrair_code_gs() -> str:
    doc = (ROOT / "docs" / "integracao-google-sheets.md").read_text(encoding="utf-8")
    return doc.split("```javascript", 1)[1].split("```", 1)[0]


@unittest.skipUnless(NODE, "node nao encontrado no PATH - pulando testes que executam o Code.gs de verdade")
class AppsScriptExecucaoTest(unittest.TestCase):
    """Cada teste roda um cenario Node contra o Code.gs real e le o
    RESULTADO_JSON que o cenario imprime. Ver tests/apps_script/cenarios/
    para o que cada um monta e verifica."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-apps-script-"))
        cls.code_gs = cls.tmpdir / "Code.gs"
        cls.code_gs.write_text(_extrair_code_gs(), encoding="utf-8", newline="\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _rodar_cenario(self, nome_arquivo, *args_extra):
        script = CENARIOS / nome_arquivo
        resultado = subprocess.run(
            [NODE, str(script), str(self.code_gs), *args_extra],
            capture_output=True, text=True, timeout=30,
        )
        linhas = [l for l in resultado.stdout.splitlines() if l.startswith("RESULTADO_JSON: ")]
        self.assertTrue(
            linhas,
            f"{nome_arquivo} nao imprimiu RESULTADO_JSON.\n"
            f"stdout:\n{resultado.stdout}\nstderr:\n{resultado.stderr}",
        )
        return json.loads(linhas[-1][len("RESULTADO_JSON: "):])

    def _rodar_payload(self, payload):
        arquivo = self.tmpdir / "payload.json"
        arquivo.write_text(json.dumps(payload), encoding="utf-8")
        return self._rodar_cenario("rodar_payload.js", str(arquivo))

    def test_aba_manual_sobrevive_a_colisao_de_nome(self):
        r = self._rodar_cenario("colisao_aba_manual.js")
        self.assertTrue(r["sync_ok"], r)
        self.assertTrue(r["identidade_preservada"], "sheetId da aba manual mudou - foi recriada")
        self.assertTrue(r["conteudo_preservado"], "conteudo da aba manual foi sobrescrito")
        self.assertTrue(r["projeto_foi_escrito_em_outra_aba"], r)

    def test_visao_geral_manual_sobrevive_a_colisao_de_nome(self):
        # A mesma protecao de propriedade (nome + sheetId) tem que valer
        # tambem pra "Visao Geral" - nao e um nome reservado automatico.
        # Reproduzido de verdade contra o commit c5018dc antes da correcao:
        # doPost excluia esse nome da checagem de abas estranhas e abaLimpa
        # adotava/limpava a aba manual.
        r = self._rodar_cenario("colisao_aba_visao_geral_manual.js")
        self.assertTrue(r["sync2_ok"], r)
        self.assertTrue(r["sync3_ok"], r)
        self.assertTrue(r["aba_manual_identidade_preservada"], "sheetId da Visao Geral manual mudou")
        self.assertTrue(r["aba_manual_conteudo_preservado"], "conteudo da Visao Geral manual foi apagado")
        self.assertTrue(r["script_escreveu_em_outro_lugar"], "o script nao redirecionou para outro destino")
        self.assertTrue(r["destino_estavel_entre_syncs"], "o destino redirecionado mudou entre sincronizacoes")

    def test_payload_com_estrelas_negativas_formato_legado_zero_mutacoes(self):
        payload = {
            "token": "...", "schema_versao": 3, "gerado_em": "x",
            "visao_geral_colunas": ["projeto"], "metricas_colunas": ["projeto"], "visao_geral": [],
            "comparativos": [
                {
                    "projeto": "2026-a", "categoria": "fone", "colunas": ["A"], "situacao": ["elegivel"],
                    "linhas": [{
                        "rotulo": "Preco", "tipo": "texto", "secao": "precos", "valores": ["R$ 100"],
                        "valores_tipados": [{"tipo": "moeda", "valor": 100, "texto": "R$ 100"}],
                    }],
                    "metricas": [],
                },
                {
                    "projeto": "2026-b", "colunas": ["Produto B"], "metricas": [],
                    "linhas": [{"tipo": "estrela", "rotulo": "Nota", "valores": [{"texto": "ruim", "estrelas": -2}]}],
                },
            ],
        }
        r = self._rodar_payload(payload)
        self.assertFalse(r["resposta"]["ok"])
        self.assertIn("estrelas", r["resposta"]["detalhe"])
        self.assertFalse(r["planilha_criada"], "payload invalido nao pode chegar a criar/abrir a planilha")
        self.assertEqual(r["mutacoes"], 0, "payload invalido tem que resultar em zero mutacoes de celula")

    def test_payload_com_estrelas_fracionarias_formato_tipado_zero_mutacoes(self):
        # Mesmo contrato (inteiro 0-5), formato TIPADO desta vez - o campo
        # tipado nao chega a crashar sozinho (so vira nota de texto), mas o
        # contrato tem que valer pros dois formatos, nao so pro que quebrava.
        payload = {
            "token": "...", "schema_versao": 3, "gerado_em": "x",
            "visao_geral_colunas": ["projeto"], "metricas_colunas": ["projeto"], "visao_geral": [],
            "comparativos": [{
                "projeto": "2026-a", "colunas": ["A"], "metricas": [],
                "linhas": [{"tipo": "texto", "rotulo": "Nota", "valores_tipados": [{"tipo": "nota", "valor": 4.5, "estrelas": 2.5}]}],
            }],
        }
        r = self._rodar_payload(payload)
        self.assertFalse(r["resposta"]["ok"])
        self.assertIn("valores_tipados", r["resposta"]["detalhe"])
        self.assertEqual(r["mutacoes"], 0)

    def test_estrelas_no_limite_do_contrato_continua_valido(self):
        # 0 e 5 sao os limites validos (0-5 estrelas) - a validacao nao pode
        # rejeitar payload legitimo por excesso de zelo.
        for valor in (0, 5):
            with self.subTest(estrelas=valor):
                payload = {
                    "token": "...", "schema_versao": 3, "gerado_em": "x",
                    "visao_geral_colunas": ["projeto"], "metricas_colunas": ["projeto"], "visao_geral": [],
                    "comparativos": [{
                        "projeto": "2026-a", "colunas": ["A"], "metricas": [],
                        "linhas": [{"tipo": "texto", "rotulo": "Nota", "valores_tipados": [{"tipo": "nota", "valor": 4.5, "estrelas": valor}]}],
                    }],
                }
                r = self._rodar_payload(payload)
                self.assertTrue(r["resposta"]["ok"], r["resposta"])

    def test_falha_operacional_apos_clear_identifica_aba_parcial_no_diagnostico(self):
        r = self._rodar_cenario("falha_operacional_diagnostico.js")
        self.assertTrue(r["sync_falhou"], r)
        self.assertTrue(r["primeira_aba_concluida"], "aba que terminou de verdade sumiu do diagnostico")
        self.assertTrue(r["segunda_aba_marcada_parcial"], "aba limpa mas nao reescrita nao aparece como parcial")
        self.assertTrue(r["segunda_aba_nao_aparece_como_concluida"], "aba parcial nao pode aparecer como concluida")

    def test_duas_sincronizacoes_validas_sem_duplicar_aba(self):
        r = self._rodar_cenario("duas_sincronizacoes_idempotentes.js")
        self.assertTrue(r["sync1_ok"], r)
        self.assertTrue(r["sync2_ok"], r)
        self.assertTrue(r["sem_duplicata"], r["abas"])

    def test_registro_legado_sem_sheet_id_e_migrado_sem_duplicar(self):
        r = self._rodar_cenario("migracao_registro_legado.js")
        self.assertTrue(r["sync2_ok"], r)
        self.assertTrue(r["sem_duplicata"], r["abas"])
        self.assertTrue(r["visao_geral_sem_duplicata"], "Visao Geral duplicou no upgrade V11->V13")
        self.assertTrue(r["sem_aviso_de_colisao"], r["avisos_sync2"])
        self.assertTrue(r["sheetId_preservado"], r)


if __name__ == "__main__":
    unittest.main()
