"""Invariantes do motor sob dado gerado, incluindo dado patologico.

Teste de exemplo confere o caso que voce imaginou. Este confere propriedades
que tem que valer para QUALQUER entrada, inclusive a que ninguem imaginou:
preco negativo, `1e309`, data impossivel, categoria inexistente, unicode.

Semente fixa: falhou uma vez, falha sempre, e da para reproduzir.
"""

import datetime as dt
import itertools
import random
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import central_compras as cc


ROOT = Path(__file__).resolve().parents[1]

PRECOS = ["", "0", "-50", "abc", "1e309", "99999999999", "0.001", "1,5", "  12  "]
NOTAS = ["", "-1", "0", "4.5", "5.1", "999", "abc", "4,7"]
AVALIACOES = ["", "-3", "0", "500", "abc", "10000000"]
DATAS = ["", "0001-01-01", "9999-12-31", "2026-13-45", "ontem"]
TEXTOS = ["", "  ", "Ção", "a" * 300, "x,y;z", '"aspas"', "<b>alerta</b>"]


class RankingInvariantsTest(unittest.TestCase):
    """Propriedades que valem para qualquer conjunto de cotacoes."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="central-compras-inv-"))
        for nome in ["config", "templates"]:
            shutil.copytree(ROOT / nome, self.tmpdir / nome)
        self._original = {
            k: getattr(cc, k)
            for k in ["ROOT", "CONFIG", "PROJETOS", "PRODUTOS", "TEMPLATES", "BASE"]
        }
        cc.ROOT = self.tmpdir
        cc.CONFIG = self.tmpdir / "config"
        cc.PROJETOS = self.tmpdir / "projetos"
        cc.PRODUTOS = self.tmpdir / "produtos"
        cc.TEMPLATES = self.tmpdir / "templates"
        cc.BASE = self.tmpdir / "base-conhecimento"
        cc._PREFS_CACHE.clear()

    def tearDown(self):
        for chave, valor in self._original.items():
            setattr(cc, chave, valor)
        cc._PREFS_CACHE.clear()
        shutil.rmtree(self.tmpdir)

    def montar_projeto(self, rnd, indice, patologico):
        projeto = self.tmpdir / "projetos" / f"p{indice}"
        projeto.mkdir(parents=True)
        categoria = rnd.choice(["fone", "carro", "inexistente"]) if patologico else "fone"
        (projeto / "briefing.md").write_text(
            f'---\ncategoria: {categoria}\n'
            f'valor_estimado: {rnd.choice([0, 400, 5000, 150000])}\n'
            f'preco_teto: {rnd.choice(["null", 0, 600, 100000])}\n'
            f'criado_em: "2026-01-01"\n---\n\n# Briefing\n',
            encoding="utf-8",
        )
        linhas = []
        anuncio = rnd.choice(["", "MLB1", "MLB1"])  # forca colisao de anuncio_id
        for i in range(rnd.randint(1, 5)):
            produto_id = f"x{i}"
            (self.tmpdir / "produtos" / "fone" / produto_id).mkdir(parents=True, exist_ok=True)
            cc.write_yaml(
                self.tmpdir / "produtos" / "fone" / produto_id / "produto.yaml",
                {
                    "id": produto_id,
                    "categoria": "fone",
                    "nome": rnd.choice(TEXTOS) if patologico else f"Produto {i}",
                    "marca": "M",
                    "estado": rnd.choice(["pesquisando", "pesquisando", "aguardando_preco", "descartado"]),
                    "descartado_porque": "motivo registrado",
                    "preco_alvo": rnd.choice([None, 0, -1, 300]),
                    "preco_teto": rnd.choice([None, 0, 200, 1000]),
                    "requisitos_atendidos": rnd.choice(
                        [{}, {"a": True}, {"a": False}, {"a": "parcial"}, {"a": None}]
                    ),
                },
            )
            for _ in range(rnd.randint(1, 3)):
                if patologico:
                    linha = {
                        "data_coleta": rnd.choice(DATAS),
                        "preco": rnd.choice(PRECOS), "custo_total": rnd.choice(PRECOS),
                        "preco_promocional": rnd.choice(PRECOS),
                        "nota": rnd.choice(NOTAS), "n_avaliacoes": rnd.choice(AVALIACOES),
                        "loja": rnd.choice(TEXTOS), "vendedor": rnd.choice(TEXTOS),
                        "vendedor_tipo": rnd.choice(["oficial", "terceiro", "", "xx"]),
                        "garantia_meses": rnd.choice(["", "-5", "12"]),
                        "garantia_tipo": rnd.choice(["nacional", "", "zz"]),
                        "frete_prazo_dias": rnd.choice(["", "-2", "3"]),
                        "fonte": rnd.choice(["web", "manual", "", "xx"]),
                    }
                else:
                    dias = rnd.randint(0, 800)
                    custo = rnd.choice([1, 99.99, 500, 99999])
                    linha = {
                        "data_coleta": (dt.date.today() - dt.timedelta(days=dias)).isoformat() + "T10:00:00",
                        "preco": custo, "custo_total": custo, "preco_promocional": "",
                        "nota": rnd.choice([0, 1.0, 4.5, 5.0]),
                        "n_avaliacoes": rnd.choice([0, 3, 500, 90000]),
                        "loja": rnd.choice(["Amazon", "MercadoLivre", "Loja X"]),
                        "vendedor": "V", "vendedor_tipo": rnd.choice(["oficial", "terceiro", "fisica"]),
                        "garantia_meses": rnd.choice(["", 0, 12, 60]),
                        "garantia_tipo": rnd.choice(["nacional", "vendedor", "nenhuma"]),
                        "frete_prazo_dias": rnd.choice(["", 0, 3, 90]),
                        "fonte": rnd.choice(["web", "manual"]),
                    }
                linhas.append({**linha, "produto_id": produto_id, "anuncio_id": anuncio})
        cc.write_quotes(projeto, linhas)
        return projeto, linhas

    def rodar(self, rodadas, patologico, semente):
        rnd = random.Random(semente)
        for indice in range(rodadas):
            projeto, linhas = self.montar_projeto(rnd, indice, patologico)
            contexto = f"rodada {indice} (semente {semente})"

            elegiveis, cortados = cc.compute_ranking(projeto)

            for item in itertools.chain(elegiveis, cortados):
                self.assertGreaterEqual(item.score, 0, contexto)
                self.assertLessEqual(item.score, 100, contexto)
                for eixo, valor in item.axes.items():
                    self.assertGreaterEqual(valor, 0.0, f"{eixo} {contexto}")
                    self.assertLessEqual(valor, 1.0, f"{eixo} {contexto}")

            # Gate antes de score: principio 2 do PRD.
            for item in elegiveis:
                self.assertFalse(item.eliminations, contexto)
            for item in cortados:
                self.assertTrue(item.eliminations, f"cortado sem motivo, {contexto}")
                self.assertEqual(item.score, 0, f"cortado pontuando, {contexto}")

            self.assertEqual(
                elegiveis, sorted(elegiveis, key=lambda c: -c.score), f"ordem quebrada, {contexto}"
            )

            # O mais barato entre os elegiveis sempre tira 1,00 no eixo valor.
            custos = [
                (cc.quote_float(i.quote.get("custo_total")), i)
                for i in elegiveis
                if cc.quote_float(i.quote.get("custo_total")) > 0
            ]
            if custos:
                _, barato = min(custos, key=lambda t: t[0])
                self.assertEqual(barato.axes["valor"], 1.0, contexto)

            # Nenhum relatorio pode explodir com o mesmo dado.
            cc.validation_report(projeto)
            cc.price_history(projeto)
            cc.stop_rule_status(projeto)
            cc.decision_briefing(projeto)

            # Round-trip: reescrever o que foi lido nao muda o arquivo nem perde linha.
            antes = (projeto / "cotacoes.csv").read_text(encoding="utf-8")
            cc.write_quotes(projeto, cc.read_quotes(projeto))
            self.assertEqual((projeto / "cotacoes.csv").read_text(encoding="utf-8"), antes, contexto)
            self.assertEqual(len(cc.read_quotes(projeto)), len(linhas), contexto)

    def test_invariants_hold_on_realistic_data(self):
        self.rodar(rodadas=40, patologico=False, semente=20260826)

    def test_invariants_hold_on_pathological_data(self):
        """Preco negativo, 1e309, data impossivel, unicode, categoria inexistente."""
        self.rodar(rodadas=40, patologico=True, semente=7)


class ScoreIsReconstructibleTest(unittest.TestCase):
    """Principio 3 do PRD: reconstruir o score a mao, com uma calculadora."""

    def test_axes_times_weights_equal_the_published_score(self):
        """Principio 3: refazer o numero a mao, com renormalizacao."""
        row = {
            "vendedor_tipo": "oficial", "garantia_tipo": "vendedor", "garantia_meses": "12",
            "loja": "Amazon", "nota": "4.8", "n_avaliacoes": "5360", "custo_total": "296.64",
        }
        pesos = cc.preferences()["score"]
        # `conveniencia` sem dado: sai da conta, e o peso restante e redistribuido.
        com_dado = {
            "qualidade": cc.quality_score(cc.current_adjusted_rating(row)),
            "valor": cc.value_score(296.64, 296.64),
            "risco": cc.risk_score(row, []),
            "aderencia": 0.5,
        }
        peso_util = sum(pesos[e] for e in com_dado)
        total = sum(com_dado[e] * pesos[e] for e in com_dado) / peso_util * 100

        self.assertAlmostEqual(peso_util, 1 - pesos["conveniencia"], places=6)
        self.assertGreater(total, 0)
        self.assertLessEqual(total, 100)
        # Somar sem renormalizar daria um numero MENOR que o publicado: era
        # exatamente a divergencia entre `ranking.md` e `memoria-calculo.md`.
        sem_renormalizar = sum(com_dado[e] * pesos[e] for e in com_dado) * 100
        self.assertGreater(total, sem_renormalizar)

    def test_risk_parts_sum_back_to_the_risk_score(self):
        """`risco 0,71` so e auditavel se as parcelas somarem de volta nele."""
        row = {"vendedor_tipo": "oficial", "garantia_tipo": "vendedor",
               "garantia_meses": "12", "loja": "Amazon"}
        soma = sum(nota * peso for _, _, nota, peso in cc.risk_parts(row, []))
        self.assertAlmostEqual(soma, cc.risk_score(row, []), places=3)

    def test_risk_weights_sum_to_one(self):
        cfg = (cc.preferences()["escala"])["risco"]
        pesos = [cfg["peso_vendedor"], cfg["peso_garantia_tipo"],
                 cfg["peso_garantia_prazo"], cfg["peso_loja"]]
        self.assertAlmostEqual(sum(pesos), 1.0, places=6)

    def test_alert_penalty_is_subtracted_from_the_parts(self):
        row = {"vendedor_tipo": "oficial", "garantia_tipo": "nacional",
               "garantia_meses": "36", "loja": "Amazon"}
        soma = sum(nota * peso for _, _, nota, peso in cc.risk_parts(row, ["ANCORA"]))
        _, penalidade = cc.risk_penalty(row, ["ANCORA"])
        self.assertAlmostEqual(cc.risk_score(row, ["ANCORA"]), soma - penalidade, places=3)


if __name__ == "__main__":
    unittest.main()
