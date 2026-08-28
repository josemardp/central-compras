"""Regressao dos achados da auditoria externa (Codex).

Cada teste aqui corresponde a um furo que uma revisao independente encontrou
depois de cinco rodadas internas. Todos foram reproduzidos antes de corrigidos.
"""

import datetime as dt
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


class BaseCli(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-aud-"))
        ambiente.montar(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def cli(self, *args, check=True):
        return subprocess.run(
            [sys.executable, "scripts/central_compras.py", *args],
            cwd=self.tmpdir, text=True, capture_output=True, check=check,
        )

    def projeto(self, nome, **kw):
        args = ["novo-projeto", nome, "--categoria", kw.get("categoria", "fone"),
                "--valor-estimado", str(kw.get("valor", 400))]
        if kw.get("teto") is not None:
            args += ["--preco-teto", str(kw["teto"])]
        self.cli(*args)
        return f"projetos/{ANO}-{cc.slugify(nome)}"

    def candidato(self, projeto, produto_id, nome, **kw):
        self.cli("novo-produto", projeto, nome, "--marca", kw.get("marca", "M"),
                 "--categoria", "fone", "--produto-id", produto_id,
                 *([] if kw.get("sem_requisitos") else ["--requisito", "uso=true"]))
        prazo = kw.get("prazo", 3)
        extra = ["--frete-prazo-dias", str(prazo)] if prazo is not None else []
        self.cli("cotar", projeto, "--produto-id", produto_id,
                 "--loja", kw.get("loja", "Amazon"), "--vendedor", "V",
                 "--vendedor-tipo", kw.get("vendedor_tipo", "oficial"),
                 "--preco", str(kw.get("preco", 299)), *extra,
                 "--nota", str(kw.get("nota", 4.6)),
                 "--avaliacoes", str(kw.get("avaliacoes", 900)),
                 "--garantia-meses", str(kw.get("garantia", 12)),
                 "--garantia-tipo", kw.get("garantia_tipo", "nacional"),
                 "--fonte", kw.get("fonte", "manual"),
                 "--link", f"https://exemplo.com/{produto_id}")


class GateAtDecisionTest(BaseCli):
    """Achado 1: `decidir` fechava compra de produto cortado pelo gate.

    O principio 2 do PRD valia no ranking e era ignorado exatamente no momento
    que importa. Era possivel comprar o que o sistema tinha reprovado.
    """

    def montar(self):
        projeto = self.projeto("fone gate", teto=600)
        # Reprovado no gate da categoria fone: minimo_avaliacoes 150.
        self.candidato(projeto, "fone-ruim", "Fone Ruim", avaliacoes=1,
                       garantia_tipo="nenhuma", garantia=0)
        return projeto

    def test_buying_a_gated_out_product_is_refused(self):
        projeto = self.montar()
        r = self.cli("decidir", projeto, "--produto-id", "fone-ruim",
                     "--porque", "quero assim mesmo", "--sem-perdedores",
                     "--comprado", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("cortado pelos gates", r.stderr)
        self.assertIn("avaliacoes insuficientes", r.stderr)

    def test_a_deliberate_exception_is_still_possible(self):
        projeto = self.montar()
        self.cli("decidir", projeto, "--produto-id", "fone-ruim",
                 "--porque", "excecao consciente", "--sem-perdedores",
                 "--permitir-cortado", "--permitir-incompleto", "--comprado")
        self.assertIn("Fone Ruim", (self.tmpdir / projeto / "decisao.md").read_text(encoding="utf-8"))


class PromotionLaunderingTest(BaseCli):
    """Achado 2: promover-cotacao carimbava web antiga como manual de hoje.

    `manual` significa "abri o site e conferi agora". Promover sem informar nada
    copiava o preco antigo com a data de hoje.
    """

    def test_promotion_requires_saying_what_was_confirmed(self):
        projeto = self.projeto("fone lavagem", teto=600)
        self.candidato(projeto, "fone-web", "Fone Web", fonte="web")
        r = self.cli("promover-cotacao", projeto, "--produto-id", "fone-web", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("o que voce conferiu", r.stderr)

    def test_informing_a_confirmed_field_works(self):
        projeto = self.projeto("fone lavagem2", teto=600)
        self.candidato(projeto, "fone-web", "Fone Web", fonte="web")
        self.cli("promover-cotacao", projeto, "--produto-id", "fone-web", "--preco", "289")
        texto = (self.tmpdir / projeto / "cotacoes.csv").read_text(encoding="utf-8")
        self.assertIn("manual", texto)
        self.assertIn("289", texto)

    def test_declaring_nothing_changed_is_explicit(self):
        projeto = self.projeto("fone lavagem3", teto=600)
        self.candidato(projeto, "fone-web", "Fone Web", fonte="web")
        self.cli("promover-cotacao", projeto, "--produto-id", "fone-web", "--sem-alteracao")
        linhas = (self.tmpdir / projeto / "cotacoes.csv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(sum(1 for l in linhas if ",manual," in l), 1)

    def test_promotion_and_add_quote_have_identical_tco_calculation(self):
        projeto = self.projeto("fone tco", teto=600)
        self.candidato(projeto, "fone-web", "Fone Web", fonte="web")
        self.cli("cotar", projeto, "--produto-id", "fone-web", "--loja", "Amazon",
                 "--preco", "289.456", "--frete", "10.123", "--custo-extra", "5.789",
                 "--custo-operacional-mensal", "2.345", "--tco-meses", "12",
                 "--valor-revenda-estimado", "50.123", "--fonte", "web")
        self.cli("promover-cotacao", projeto, "--produto-id", "fone-web", "--sem-alteracao")
        quotes = cc.read_quotes(self.tmpdir / projeto)
        self.assertEqual(len(quotes), 3)
        q_web = quotes[1]
        q_manual = quotes[2]
        self.assertEqual(q_web["custo_total"], q_manual["custo_total"])
        self.assertEqual(q_web["tco_total"], q_manual["tco_total"])


class NotANumberTest(unittest.TestCase):
    """Achado 5: `NaN` e infinito passavam porque toda comparacao com NaN e falsa."""

    def test_nan_and_infinity_never_become_a_ranking_number(self):
        self.assertEqual(cc.quote_float("NaN"), 0.0)
        self.assertEqual(cc.quote_float("nan"), 0.0)
        self.assertEqual(cc.quote_float("1e309"), 0.0)
        self.assertEqual(cc.quote_float("-1e309"), 0.0)
        self.assertEqual(cc.quote_float("inf"), 0.0)

    def test_validation_reports_them_as_errors(self):
        self.assertTrue(any("nao e numero" in p for p in cc.numeric_problems({"preco": "NaN"})))
        self.assertTrue(any("infinito" in p for p in cc.numeric_problems({"custo_total": "1e309"})))

    def test_an_ordinary_number_still_passes(self):
        self.assertEqual(cc.quote_float("296.64"), 296.64)
        self.assertEqual(cc.numeric_problems({"preco": "296.64"}), [])


class FutureDateTest(BaseCli):
    """Achado 4: data futura passava e a cotacao nunca vencia."""

    def test_cli_refuses_a_future_collection_date(self):
        import argparse
        futuro = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        with self.assertRaises(argparse.ArgumentTypeError):
            cc.iso_datetime(futuro)
        with self.assertRaises(argparse.ArgumentTypeError):
            cc.iso_datetime("2099-01-01")

    def test_today_is_accepted(self):
        self.assertTrue(cc.iso_datetime(cc.today()).startswith(cc.today()))

    def test_a_hand_edited_future_date_is_reported_as_an_error(self):
        projeto = self.projeto("fone futuro", teto=600)
        self.candidato(projeto, "fone-a", "Fone A")
        csv_path = self.tmpdir / projeto / "cotacoes.csv"
        csv_path.write_text(
            csv_path.read_text(encoding="utf-8").replace(cc.today(), "2099-01-01", 1),
            encoding="utf-8", newline="",
        )
        self.cli("validar", projeto)
        validacao = (self.tmpdir / projeto / "validacao.md").read_text(encoding="utf-8")
        self.assertIn("no futuro", validacao)


class AuditMatchesRankingTest(BaseCli):
    """Achado 3: `auditar` explicava o eixo valor por custo_total mesmo quando o
    ranking comparava por TCO. A conta publicada nao fechava na compra cara."""

    def test_audit_explains_the_same_number_the_ranking_used(self):
        projeto = self.projeto("carro auditoria", categoria="carro", valor=150000, teto=200000)
        for pid, nome, preco, mensal, revenda in [
            ("carro-a", "Carro A", 150000, 300, 85000),
            ("carro-b", "Carro B", 145000, 900, 70000),
        ]:
            self.cli("novo-produto", projeto, nome, "--marca", "M", "--categoria", "carro",
                     "--produto-id", pid, "--atributo", "rede_assistencia=true")
            self.cli("cotar", projeto, "--produto-id", pid, "--loja", "Concessionaria",
                     "--vendedor", "V", "--vendedor-tipo", "fisica", "--preco", str(preco),
                     "--nota", "4.7", "--avaliacoes", "1000", "--garantia-meses", "36",
                     "--garantia-tipo", "nacional", "--fonte", "manual",
                     "--link", f"https://exemplo.com/{pid}",
                     "--custo-operacional-mensal", str(mensal),
                     "--valor-revenda-estimado", str(revenda))
        self.cli("ranking", projeto)
        self.cli("auditar", projeto)
        memoria = (self.tmpdir / projeto / "memoria-calculo.md").read_text(encoding="utf-8")

        self.assertIn("base de comparacao: **TCO**", memoria)
        # O TCO do Carro A: 150000 + 300*60 - 85000 = 83000.
        self.assertIn("83.000,00", memoria)
        # E nao pode explicar usando o preco de etiqueta como base.
        self.assertNotIn("menor custo total entre os elegiveis", memoria)


class ConfidenceTest(BaseCli):
    """Achado de julgamento: o 0,50 neutro premiava o silencio.

    "nao sei o prazo" valia 5 pontos a mais que "o prazo e pessimo e eu sei".
    """

    def test_missing_data_no_longer_beats_known_bad_data(self):
        projeto = self.projeto("fone silencio", teto=600)
        self.candidato(projeto, "sem-prazo", "Sem Prazo", prazo=None)
        # Remove o prazo da linha, simulando campo nao preenchido.
        csv_path = self.tmpdir / projeto / "cotacoes.csv"
        self.candidato(projeto, "prazo-ruim", "Prazo Ruim", prazo=90)
        self.cli("ranking", projeto)

        import csv as _csv
        with (self.tmpdir / projeto / "ranking.csv").open(encoding="utf-8", newline="") as f:
            linhas = {r["produto_id"]: r for r in _csv.DictReader(f)}
        confianca_sem = float(linhas["sem-prazo"]["confianca"])
        confianca_ruim = float(linhas["prazo-ruim"]["confianca"])

        # Quem informou o prazo tem mais peso do score apoiado em dado real.
        # Antes, omitir o campo era invisivel no numero publicado.
        self.assertLess(confianca_sem, confianca_ruim)
        # E a diferenca e exatamente o peso do eixo conveniencia.
        peso = cc.preferences()["score"]["conveniencia"]
        self.assertAlmostEqual(confianca_ruim - confianca_sem, peso, places=2)

        # O eixo ausente saiu da conta em vez de entrar como 0,50 inventado.
        # (Ambos tambem estao sem requisitos, entao `aderencia` falta nos dois.)
        self.assertIn("conveniencia", linhas["sem-prazo"]["eixos_sem_dado"])
        self.assertNotIn("conveniencia", linhas["prazo-ruim"]["eixos_sem_dado"])

    def test_confidence_is_published_in_the_ranking(self):
        projeto = self.projeto("fone confianca", teto=600)
        self.candidato(projeto, "fone-a", "Fone A", prazo=3)
        self.cli("ranking", projeto)
        ranking = (self.tmpdir / projeto / "ranking.md").read_text(encoding="utf-8")
        self.assertIn("confianca", ranking.lower())

    def test_the_gate_is_checked_before_confidence(self):
        """Sem nota, o produto e cortado no gate. Gate antes de tudo, inclusive
        antes da confianca: e a ordem certa."""
        projeto = self.projeto("fone incerto", teto=600)
        self.cli("novo-produto", projeto, "Fone Incerto", "--marca", "M",
                 "--categoria", "fone", "--produto-id", "fone-x")
        self.cli("cotar", projeto, "--produto-id", "fone-x", "--loja", "Amazon",
                 "--vendedor", "V", "--vendedor-tipo", "oficial", "--preco", "299",
                 "--garantia-meses", "12", "--garantia-tipo", "nacional",
                 "--fonte", "manual", "--link", "https://exemplo.com/x")
        r = self.cli("decidir", projeto, "--produto-id", "fone-x", "--porque", "vai",
                     "--sem-perdedores", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("cortado pelos gates", r.stderr)

    def test_deciding_on_a_low_confidence_score_is_refused(self):
        """Passa no gate, mas sem requisitos e sem prazo de frete a confianca
        fica em 75%, abaixo do minimo de 80%."""
        projeto = self.projeto("fone incerto2", teto=600)
        self.candidato(projeto, "fone-y", "Fone Incerto", sem_requisitos=True, prazo=None)

        r = self.cli("decidir", projeto, "--produto-id", "fone-y", "--porque", "vai",
                     "--sem-perdedores", check=False)
        self.assertNotEqual(r.returncode, 0)
        # `aderencia` e eixo obrigatorio: a mensagem diz isso antes de falar
        # em confianca, porque nenhum limite cobre um eixo que simplesmente falta.
        self.assertIn("aderencia", r.stderr)
        self.assertIn("nao podem faltar", r.stderr)

        # Declarando que aceita decidir sobre dado incompleto, fecha.
        self.cli("decidir", projeto, "--produto-id", "fone-y", "--porque", "vai",
                 "--sem-perdedores", "--permitir-incompleto")

    def test_an_expensive_purchase_demands_more_confidence(self):
        """Faltar so o prazo (confianca 90%) passa numa compra barata e barra
        numa compra cara, onde o minimo e 90%."""
        import yaml as _yaml
        cfg = _yaml.safe_load((self.tmpdir / "config" / "preferencias.yaml").read_text(encoding="utf-8"))
        minimos = cfg["confianca_minima_para_decidir"]
        self.assertGreater(minimos["acima_de_20000"], minimos["padrao"])
        self.assertEqual(cc.minimum_confidence({"valor_estimado": 400}), minimos["padrao"])
        self.assertEqual(cc.minimum_confidence({"valor_estimado": 150000}), minimos["acima_de_20000"])


class NoLosersFlagTest(BaseCli):
    """Achado relevante: `--sem-perdedores` burlava o principio 4 mesmo havendo
    concorrente. A flag declara que nao houve concorrente; usa-la com
    concorrente na mesa e mentira registrada em disco."""

    def test_the_flag_is_refused_when_competitors_exist(self):
        projeto = self.projeto("fone concorrente", teto=600)
        self.candidato(projeto, "fone-a", "Fone A", preco=299)
        self.candidato(projeto, "fone-b", "Fone B", preco=399)
        r = self.cli("decidir", projeto, "--produto-id", "fone-a",
                     "--porque", "mais barato", "--sem-perdedores", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fone-b", r.stderr)

    def test_the_flag_works_when_there_really_was_no_competitor(self):
        projeto = self.projeto("fone sozinho", teto=600)
        self.candidato(projeto, "fone-a", "Fone A")
        self.cli("decidir", projeto, "--produto-id", "fone-a",
                 "--porque", "unico candidato", "--sem-perdedores")
        self.assertIn("Fone A", (self.tmpdir / projeto / "decisao.md").read_text(encoding="utf-8"))


class SecretScanGapsTest(unittest.TestCase):
    """Achado 6: falsos-negativos no varredor de segredos."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-sec2-"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def codigos(self, nome, conteudo):
        (self.tmpdir / nome).write_text(conteudo, encoding="utf-8")
        return {c for _, _, c, _ in cc.scan_sensitive(self.tmpdir)}

    def test_finds_an_unpunctuated_cpf_when_labelled(self):
        self.assertIn("CPF", self.codigos("v.md", "CPF: 00000000191\n"))  # central-compras:exemplo-nao-e-segredo

    def test_finds_a_card_with_underscores(self):
        self.assertIn("CARTAO", self.codigos("v.md", "cartao: 4111_1111_1111_1111\n"))  # central-compras:exemplo-nao-e-segredo

    def test_scans_env_files(self):
        codigos = self.codigos(".env", "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrs\n")  # central-compras:exemplo-nao-e-segredo
        self.assertIn("TOKEN", codigos)

    def test_an_ordinary_eleven_digit_number_is_not_flagged_as_cpf(self):
        # Codigo de rastreio, EAN e telefone nao podem virar alarme.
        self.assertEqual(self.codigos("c.csv", "rastreio,ean\n00000000191,7891234567895\n"), set())


if __name__ == "__main__":
    unittest.main()


class LostUpdateTest(BaseCli):
    """Achado proprio, surgido ao preparar a segunda auditoria.

    Escrita atomica protege contra arquivo pela metade, nao contra leitura
    velha. Enquanto `cotar` relia e reescrevia o arquivo inteiro, duas cotacoes
    concorrentes faziam uma observacao sumir em silencio: violacao direta do
    principio 1, que a atomicidade nao cobre.
    """

    def test_two_concurrent_quotes_do_not_erase_each_other(self):
        projeto = self.projeto("fone corrida", teto=600)
        self.cli("novo-produto", projeto, "Fone A", "--marca", "M",
                 "--categoria", "fone", "--produto-id", "fone-a")
        caminho = self.tmpdir / projeto

        # Os dois "processos" leem a mesma base e gravam cada um a sua linha.
        cc.read_quotes(caminho)
        cc.append_quote(caminho, {"data_coleta": "2026-01-01T10:00:00",
                                  "produto_id": "fone-a", "custo_total": "100", "fonte": "manual"})
        cc.append_quote(caminho, {"data_coleta": "2026-01-02T10:00:00",
                                  "produto_id": "fone-a", "custo_total": "200", "fonte": "manual"})

        custos = {r.get("custo_total") for r in cc.read_quotes(caminho)}
        self.assertIn("100", custos, "observacao perdida por leitura velha")
        self.assertIn("200", custos)

    def test_parallel_cotar_processes_keep_every_observation(self):
        import concurrent.futures as cf
        projeto = self.projeto("fone paralelo", teto=600)
        self.cli("novo-produto", projeto, "Fone A", "--marca", "M",
                 "--categoria", "fone", "--produto-id", "fone-a")

        def cotar(indice):
            return self.cli("cotar", projeto, "--produto-id", "fone-a", "--loja", "Amazon",
                            "--vendedor", "V", "--vendedor-tipo", "oficial",
                            "--preco", str(100 + indice), "--nota", "4.6", "--avaliacoes", "900",
                            "--garantia-meses", "12", "--garantia-tipo", "nacional",
                            "--fonte", "web", "--link", "https://exemplo.com/a", check=False)

        with cf.ThreadPoolExecutor(max_workers=8) as pool:
            resultados = list(pool.map(cotar, range(12)))

        falhas = [
            f"rc={r.returncode}\nstdout={r.stdout}\nstderr={r.stderr}"
            for r in resultados if r.returncode != 0
        ]
        self.assertFalse(falhas, "subprocessos de cotacao falharam:\n" + "\n".join(falhas))

        linhas = cc.read_quotes(self.tmpdir / projeto)
        self.assertEqual(len(linhas), 12, f"esperava 12 observacoes, ficaram {len(linhas)}")
        self.assertEqual(
            {float(linha["preco"]) for linha in linhas},
            {float(100 + indice) for indice in range(12)},
            "alguma observacao foi duplicada ou substituida",
        )

    def test_appending_refuses_a_stale_header_instead_of_rewriting_it(self):
        projeto = self.projeto("fone header", teto=600)
        caminho = self.tmpdir / projeto
        (caminho / "cotacoes.csv").write_text("data_coleta,produto_id\n", encoding="utf-8", newline="")
        with self.assertRaises(SystemExit) as ctx:
            cc.append_quote(caminho, {"data_coleta": "2026-01-01", "produto_id": "a", "custo_total": "1"})
        self.assertIn("migrar-cotacoes", str(ctx.exception))
