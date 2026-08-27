"""Regressao dos achados da segunda auditoria.

Tres deles sao correcoes anteriores que tinham ficado pela metade: o mesmo
defeito, corrigido num comando e vivo no vizinho.
"""

import datetime as dt
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import ambiente
from scripts import central_compras as cc


ROOT = Path(__file__).resolve().parents[1]
ANO = dt.date.today().year


class Base(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-aud2-"))
        ambiente.montar(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def cli(self, *args, check=True):
        return subprocess.run(
            [sys.executable, "scripts/central_compras.py", *args],
            cwd=self.tmpdir, text=True, capture_output=True, check=check,
        )

    def candidato_fone(self, projeto, produto_id="fone-a", fonte="manual", **kw):
        self.cli("novo-produto", projeto, kw.get("nome", "Fone A"), "--marca", "M",
                 "--categoria", "fone", "--produto-id", produto_id, "--requisito", "uso=true")
        self.cli("cotar", projeto, "--produto-id", produto_id, "--loja", "Amazon",
                 "--vendedor", "V", "--vendedor-tipo", "oficial", "--preco", str(kw.get("preco", 299)),
                 "--nota", "4.6", "--avaliacoes", "900", "--garantia-meses", "12",
                 "--garantia-tipo", "nacional", "--fonte", fonte,
                 "--link", f"https://exemplo.com/{produto_id}")


class HistoryUsesRankingBaseTest(Base):
    """Achado 1: `historico` mostrava preco de etiqueta enquanto o ranking
    comparava por TCO. Mesmo defeito ja corrigido no `auditar`."""

    def test_history_reports_tco_when_the_ranking_ranks_by_tco(self):
        projeto = f"projetos/{ANO}-carro-hist"
        self.cli("novo-projeto", "carro hist", "--categoria", "carro",
                 "--valor-estimado", "150000", "--preco-teto", "200000")
        for pid, preco, mensal, revenda in [("ca", 160000, 200, 95000), ("cb", 140000, 1200, 55000)]:
            self.cli("novo-produto", projeto, pid.upper(), "--marca", "M", "--categoria", "carro",
                     "--produto-id", pid, "--atributo", "rede_assistencia=true",
                     "--requisito", "uso=true")
            self.cli("cotar", projeto, "--produto-id", pid, "--loja", "C", "--vendedor", "V",
                     "--vendedor-tipo", "fisica", "--preco", str(preco), "--nota", "4.7",
                     "--avaliacoes", "1000", "--garantia-meses", "36", "--garantia-tipo", "nacional",
                     "--fonte", "manual", "--link", "https://ex.com/a", "--frete-prazo-dias", "30",
                     "--custo-operacional-mensal", str(mensal), "--valor-revenda-estimado", str(revenda))

        saida = self.cli("historico", projeto).stdout
        historico = (self.tmpdir / projeto / "historico.md").read_text(encoding="utf-8")

        self.assertIn("Base de comparacao: **TCO**", historico)
        # TCO do CA: 160000 + 200*60 - 95000 = 77000. Etiqueta seria 160000.
        self.assertIn("77.000,00", historico)
        self.assertNotIn("160.000,00", historico)
        self.assertIn("[TCO]", saida)

    def test_history_reports_sticker_price_on_a_cheap_purchase(self):
        projeto = f"projetos/{ANO}-fone-hist"
        self.cli("novo-projeto", "fone hist", "--categoria", "fone", "--valor-estimado", "400")
        self.candidato_fone(projeto, "f")
        self.cli("historico", projeto)
        historico = (self.tmpdir / projeto / "historico.md").read_text(encoding="utf-8")
        self.assertIn("Base de comparacao: **custo total**", historico)


class NumericInputTest(Base):
    """Achado 2: `NaN`, `Infinity` e `1e309` eram aceitos pelo CLI e viravam
    0,0 em silencio. A validacao nao tinha o que reclamar: 0,0 e valido."""

    def test_cli_refuses_pathological_numbers(self):
        import argparse
        for ruim in ["NaN", "nan", "Infinity", "inf", "1e309", "-5"]:
            with self.assertRaises(argparse.ArgumentTypeError, msg=ruim):
                cc.real_number(ruim)

    def test_cli_accepts_ordinary_numbers(self):
        self.assertEqual(cc.real_number("296.64"), 296.64)
        self.assertEqual(cc.real_number("296,64"), 296.64)
        self.assertEqual(cc.real_number("0"), 0.0)

    def test_quoting_with_nan_is_rejected_at_the_door(self):
        projeto = f"projetos/{ANO}-nan"
        self.cli("novo-projeto", "nan", "--categoria", "fone", "--valor-estimado", "400")
        self.cli("novo-produto", projeto, "N", "--marca", "M", "--categoria", "fone",
                 "--produto-id", "n", "--requisito", "uso=true")
        for ruim in ["NaN", "Infinity", "1e309"]:
            r = self.cli("cotar", projeto, "--produto-id", "n", "--loja", "A", "--vendedor", "V",
                         "--vendedor-tipo", "oficial", "--preco", ruim, "--nota", "4.6",
                         "--avaliacoes", "900", "--garantia-meses", "12",
                         "--garantia-tipo", "nacional", "--fonte", "manual",
                         "--link", "https://ex.com/n", check=False)
            self.assertNotEqual(r.returncode, 0, ruim)
        self.assertEqual(len(cc.read_quotes(self.tmpdir / projeto)), 0, "lixo entrou no livro-razao")

    def test_a_quote_without_a_usable_cost_is_cut_by_the_gate(self):
        """Custo zerado virava eixo valor sem dado e o produto seguia elegivel."""
        row = {"custo_total": "0", "nota": "4.8", "n_avaliacoes": "900",
               "garantia_tipo": "nacional", "garantia_meses": "12", "vendedor_tipo": "oficial"}
        produto = {"categoria": "fone", "estado": "pesquisando", "requisitos_atendidos": {"a": True}}
        cortes = cc.gate_eliminations(row, produto, {"categoria": "fone"})
        self.assertTrue(any("sem custo utilizavel" in c for c in cortes))


class KnowledgeBaseConcurrencyTest(Base):
    """Achado 3: a base de conhecimento perdia dado em silencio.

    Medido antes da correcao: 20 licoes em paralelo viravam 7 gravadas, com
    zero erro. Mesma corrida ja corrigida no cotacoes.csv.
    """

    def test_parallel_lessons_are_all_recorded(self):
        import concurrent.futures as cf

        def registra(i):
            return self.cli("registrar-licao", f"licao numero {i}", "--categoria", "fone",
                            check=False).returncode

        with cf.ThreadPoolExecutor(max_workers=8) as pool:
            erros = sum(1 for r in pool.map(registra, range(20)) if r)

        texto = (self.tmpdir / "base-conhecimento" / "licoes.md").read_text(encoding="utf-8")
        gravadas = sum(1 for l in texto.splitlines() if "licao numero" in l)
        self.assertEqual(erros, 0)
        self.assertEqual(gravadas, 20, f"perdeu licao em silencio: {gravadas} de 20")

    def test_parallel_brand_notes_are_all_recorded(self):
        import concurrent.futures as cf

        def registra(i):
            return self.cli("registrar-marca", "QCY", "--resumo", f"nota {i}",
                            "--categoria", "fone", check=False).returncode

        with cf.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(registra, range(15)))

        texto = (self.tmpdir / "base-conhecimento" / "marcas" / "qcy.md").read_text(encoding="utf-8")
        self.assertEqual(sum(1 for l in texto.splitlines() if l.startswith("- Resumo:")), 15)
        self.assertEqual(texto.count("# QCY"), 1, "cabecalho duplicado por corrida")


class DashboardShowsConfidenceTest(Base):
    """Achado 4: o dashboard nao publicava `confianca` e lia o ranking.csv do
    disco, entao podia mostrar numero velho."""

    def montar(self):
        projeto = f"projetos/{ANO}-fone-dash"
        self.cli("novo-projeto", "fone dash", "--categoria", "fone",
                 "--valor-estimado", "400", "--preco-teto", "600")
        self.candidato_fone(projeto)
        return projeto

    def test_dashboard_publishes_confidence(self):
        self.montar()
        self.cli("dashboard")
        home = (self.tmpdir / "dashboard" / "index.html").read_text(encoding="utf-8")
        pagina = (self.tmpdir / "dashboard" / "projetos" / f"{ANO}-fone-dash.html").read_text(encoding="utf-8")
        self.assertIn("Confianca", home)
        self.assertIn("Confianca", pagina)

    def test_dashboard_does_not_depend_on_a_stale_ranking_csv(self):
        projeto = self.montar()
        self.cli("ranking", projeto)
        # Envelhece o derivado de proposito.
        (self.tmpdir / projeto / "ranking.csv").write_text(
            "produto_id,nome,score,status\nfone-a,NOME VELHO,1.0,elegivel\n",
            encoding="utf-8", newline="")
        self.cli("dashboard")
        home = (self.tmpdir / "dashboard" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("NOME VELHO", home)
        self.assertIn("Fone A", home)


class RegenerateDoesNotTouchSourcesTest(Base):
    """Achado 5: `regenerar` marcava etapas e reescrevia a proxima acao no
    `processo.md`, que e fonte, enquanto imprimia que nao tocava em nada."""

    def montar(self, nome):
        projeto = f"projetos/{ANO}-{cc.slugify(nome)}"
        self.cli("novo-projeto", nome, "--categoria", "fone",
                 "--valor-estimado", "400", "--preco-teto", "600")
        self.candidato_fone(projeto)
        return projeto

    def test_regenerate_leaves_processo_md_untouched(self):
        projeto = self.montar("fone reg")
        antes = (self.tmpdir / projeto / "processo.md").read_text(encoding="utf-8")
        self.cli("regenerar", "--projeto", projeto)
        depois = (self.tmpdir / projeto / "processo.md").read_text(encoding="utf-8")
        self.assertEqual(antes, depois, "`regenerar` mexeu numa fonte")

    def test_ranking_still_advances_the_process_when_run_directly(self):
        """Congelar a fonte vale so dentro do `regenerar`: `ranking` continua
        marcando etapa, que e o comportamento util no dia a dia."""
        projeto = self.montar("fone reg2")
        antes = (self.tmpdir / projeto / "processo.md").read_text(encoding="utf-8")
        self.cli("ranking", projeto)
        depois = (self.tmpdir / projeto / "processo.md").read_text(encoding="utf-8")
        self.assertNotEqual(antes, depois)


class ConfirmationProvenanceTest(Base):
    """Achado 6: `--sem-alteracao` nao deixava rastro. A linha promovida ficava
    indistinguivel de uma conferencia em que algo mudou."""

    def montar(self, nome):
        projeto = f"projetos/{ANO}-{cc.slugify(nome)}"
        self.cli("novo-projeto", nome, "--categoria", "fone",
                 "--valor-estimado", "400", "--preco-teto", "600")
        self.candidato_fone(projeto, fonte="web")
        return projeto

    def linhas(self, projeto):
        return cc.read_quotes(self.tmpdir / projeto)

    def test_a_reconfirmation_says_so_in_the_ledger(self):
        projeto = self.montar("fone conf")
        self.cli("promover-cotacao", projeto, "--produto-id", "fone-a", "--sem-alteracao")
        manual = [l for l in self.linhas(projeto) if l["fonte"] == "manual"][0]
        self.assertEqual(manual["confirmacao"], "reconfirmado sem alteracao")

    def test_a_confirmation_with_changes_records_which_fields(self):
        projeto = self.montar("fone conf2")
        self.cli("promover-cotacao", projeto, "--produto-id", "fone-a", "--preco", "289")
        manual = [l for l in self.linhas(projeto) if l["fonte"] == "manual"][0]
        self.assertIn("conferido", manual["confirmacao"])
        self.assertIn("preco", manual["confirmacao"])

    def test_a_plain_quote_is_marked_as_a_collection(self):
        projeto = self.montar("fone conf3")
        self.assertEqual(self.linhas(projeto)[0]["confirmacao"], "coleta")


class ConfidenceCalibrationTest(unittest.TestCase):
    """Achado 7: o limite de 75% coincidia com o caso mais comum de dado
    faltando, e a comparacao estrita deixava passar raspando."""

    def test_the_common_missing_case_now_blocks(self):
        pesos = cc.preferences()["score"]
        faltando_os_dois = 1 - pesos["aderencia"] - pesos["conveniencia"]
        self.assertAlmostEqual(faltando_os_dois, 0.75, places=6)
        self.assertLess(faltando_os_dois, cc.minimum_confidence({"valor_estimado": 400}))

    def test_a_transparent_product_is_not_beaten_by_a_silent_one(self):
        """O silencioso vencia o transparente: score 85,8 com 75% de confianca
        contra 71,8 com 100%. Agora o silencioso nem chega a decidir."""
        self.assertGreaterEqual(cc.minimum_confidence({"valor_estimado": 400}), 0.90)

    def test_missing_only_the_softest_axis_still_passes(self):
        pesos = cc.preferences()["score"]
        confianca = 1 - pesos["conveniencia"]
        self.assertGreaterEqual(confianca, cc.minimum_confidence({"valor_estimado": 400}))

    def test_value_and_adherence_are_mandatory_regardless_of_confidence(self):
        """Elevar o limite nao basta: omitir um eixo ruim ainda subia o score.
        `valor` e `aderencia` nao podem simplesmente faltar numa decisao."""
        obrigatorios = cc.preferences()["eixos_obrigatorios_para_decidir"]
        self.assertIn("valor", obrigatorios)
        self.assertIn("aderencia", obrigatorios)

    def test_an_expensive_purchase_is_stricter(self):
        self.assertGreater(
            cc.minimum_confidence({"valor_estimado": 150000}),
            cc.minimum_confidence({"valor_estimado": 400}),
        )

    def test_criticality_comes_from_the_axis_weight_itself(self):
        """Nao ha segunda tabela de criticidade: o peso do eixo ja e ela."""
        pesos = cc.preferences()["score"]
        self.assertGreater(pesos["qualidade"], pesos["conveniencia"])


class PasswordPatternTest(unittest.TestCase):
    """Achado 8: a fronteira de palavra a esquerda cegava `database_password` e
    `MINHA_SENHA`, exatamente como cegava `api_key` antes."""

    def casou(self, linha):
        return {c for c, p, _ in cc.SENSITIVE_PATTERNS if re.search(p, linha)}

    def test_prefixed_password_keys_are_detected(self):
        exemplos = ["database_password: x", "db_senha: y", "MINHA_SENHA=z",  # central-compras:exemplo-nao-e-segredo
                    "user_passwd=w", "senha: v"]  # central-compras:exemplo-nao-e-segredo
        for linha in exemplos:
            self.assertIn("SENHA", self.casou(linha), linha)

    def test_ordinary_prose_is_not_flagged(self):
        for linha in ["token de estacionamento do predio",
                      "o secret ingredient da receita e alecrim"]:
            self.assertNotIn("SENHA", self.casou(linha), linha)


class TestIsolationTest(unittest.TestCase):
    """Achado 9: fixtures copiavam a base real, com as datas reais. O teste de
    reaproveitamento passou no dia em que foi escrito e falhou no seguinte."""

    def test_the_helper_builds_an_empty_knowledge_base(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-iso-"))
        try:
            ambiente.montar(tmpdir)
            self.assertEqual(list((tmpdir / "base-conhecimento" / "marcas").glob("*.md")), [])
            self.assertEqual(list((tmpdir / "base-conhecimento" / "lojas").glob("*.md")), [])
            licoes = (tmpdir / "base-conhecimento" / "licoes.md").read_text(encoding="utf-8")
            self.assertNotIn("20", licoes, "data real vazou para o ambiente de teste")
            self.assertTrue((tmpdir / "config" / "preferencias.yaml").exists())
        finally:
            shutil.rmtree(tmpdir)

    def test_no_fixture_copies_the_real_knowledge_base(self):
        # Montado em tempo de execucao para a assercao nao encontrar a si mesma.
        agulha = '"' + "base-conhecimento" + '",'
        for arquivo in (ROOT / "tests").glob("test_*.py"):
            if arquivo.name == Path(__file__).name:
                continue
            setup = arquivo.read_text(encoding="utf-8").split("def tearDown")[0]
            self.assertNotIn(
                agulha, setup,
                f"{arquivo.name} ainda copia a base de conhecimento real no setUp",
            )


if __name__ == "__main__":
    unittest.main()
