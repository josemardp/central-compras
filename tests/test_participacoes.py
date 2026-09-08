"""Frente 5: produto reutilizado em projetos diferentes.

Cenario ancora: o MESMO produto_id participa de dois projetos com estados,
motivos, limites e requisitos independentes. Descarte, espera ou preco-alvo
num projeto nunca pode vazar para o outro - a ficha (`produto.yaml`) guarda
so identidade e dado tecnico; participacao (estado, descarte, preco-alvo/
teto, requisitos atendidos) mora em `projetos/<projeto>/participacoes/
<produto_id>.yaml`.
"""

import argparse
import json
import unittest

import ambiente
from scripts import central_compras as cc


class ParticipacaoIsoladaTest(ambiente.RepoTestCase):
    """Criterios 1, 2 e 3: isolamento nos dois sentidos."""

    def setUp(self):
        super().setUp()
        self.projeto_a = self.project(name="projeto-a", category="fone", value=400)
        self.cli("novo-produto", str(self.projeto_a), "Fone Reaproveitado",
                  "--produto-id", "fone-comum", "--marca", "Marca X",
                  "--requisito", "bluetooth=true")
        self.projeto_b = self.project(name="projeto-b", category="fone", value=400)

    def _vincular_b(self, **extra):
        argv = ["vincular-produto", "--produto-id", "fone-comum", "--projeto", str(self.projeto_b)]
        for chave, valor in extra.items():
            argv.extend([f"--{chave.replace('_', '-')}", str(valor)])
        return self.cli(*argv)

    def test_ficha_unica_participacao_por_projeto(self):
        """Vincular a B cria uma segunda participacao sem duplicar a ficha."""
        fichas = list(cc.PRODUTOS.glob("*/fone-comum/produto.yaml"))
        self.assertEqual(len(fichas), 1, "vincular-produto nao pode criar segunda ficha")

        self._vincular_b()
        self.assertTrue((self.projeto_a / "participacoes" / "fone-comum.yaml").exists())
        self.assertTrue((self.projeto_b / "participacoes" / "fone-comum.yaml").exists())

    def test_descarte_em_a_nao_afeta_b(self):
        self._vincular_b(preco_alvo=150)
        self.cli("descartar", "--produto-id", "fone-comum", "--porque", "nao serve mais",
                  "--projeto", str(self.projeto_a))

        participacao_a = cc.read_participation(self.projeto_a, "fone-comum")
        participacao_b = cc.read_participation(self.projeto_b, "fone-comum")
        self.assertEqual(participacao_a["estado"], "descartado")
        self.assertEqual(participacao_a["descartado_porque"], "nao serve mais")
        self.assertEqual(participacao_b["estado"], "pesquisando")
        self.assertIsNone(participacao_b["descartado_porque"])
        self.assertEqual(participacao_b["preco_alvo"], 150)

    def test_descarte_em_a_nao_muda_regra_de_parada_de_b(self):
        self._vincular_b()
        self.assertIn("fone-comum", cc.project_candidate_ids(self.projeto_b))
        self.cli("descartar", "--produto-id", "fone-comum", "--porque", "caro",
                  "--projeto", str(self.projeto_a))

        self.assertNotIn("fone-comum", cc.project_candidate_ids(self.projeto_a))
        self.assertIn("fone-comum", cc.project_candidate_ids(self.projeto_b))
        self.assertIn("fone-comum", cc.project_discarded_candidate_ids(self.projeto_a))
        self.assertNotIn("fone-comum", cc.project_discarded_candidate_ids(self.projeto_b))

    def test_aguardar_preco_e_requisitos_independentes(self):
        self._vincular_b(requisito="bluetooth=false")
        self.cli("aguardar-preco", "--produto-id", "fone-comum", "--porque", "esperar promocao",
                  "--preco-alvo", "99", "--projeto", str(self.projeto_a))

        participacao_a = cc.read_participation(self.projeto_a, "fone-comum")
        participacao_b = cc.read_participation(self.projeto_b, "fone-comum")
        self.assertEqual(participacao_a["estado"], "aguardando_preco")
        self.assertEqual(participacao_a["preco_alvo"], 99)
        self.assertEqual(participacao_b["estado"], "pesquisando")
        self.assertEqual(participacao_a["requisitos_atendidos"], {"bluetooth": True})
        self.assertEqual(participacao_b["requisitos_atendidos"], {"bluetooth": False})

    def test_candidato_sem_cotacao_sem_estrela_respeita_projeto(self):
        """Preserva 6b48a51: sem cotacao nunca ganha estrela, e descarte so
        vale no projeto onde foi descartado."""
        self.cli("novo-produto", str(self.projeto_a), "Fone com atributo",
                  "--produto-id", "fone-atributo", "--marca", "Marca Y",
                  "--atributo", "bateria_horas=30")
        self._vincular_produto_atributo_em_b = None  # noop, so legibilidade

        categoria, atributos, itens = cc.spec_comparison_rows(self.projeto_a)
        item = next(i for i in itens if i.produto_id == "fone-atributo")
        self.assertTrue(item.sem_cotacao)
        texto, estrelas = cc.atributo_valor(categoria, item, "bateria_horas")
        self.assertEqual(texto, "30")
        self.assertIsNone(estrelas)

        self.cli("vincular-produto", "--produto-id", "fone-atributo", "--projeto", str(self.projeto_b))
        self.cli("descartar", "--produto-id", "fone-atributo", "--porque", "fora do orcamento",
                  "--projeto", str(self.projeto_a))

        _, _, itens_a = cc.spec_comparison_rows(self.projeto_a)
        self.assertFalse(any(i.produto_id == "fone-atributo" for i in itens_a),
                          "descartado sem cotacao nao deve aparecer no proprio projeto")
        _, _, itens_b = cc.spec_comparison_rows(self.projeto_b)
        self.assertTrue(any(i.produto_id == "fone-atributo" for i in itens_b),
                         "descarte em A nao pode esconder o candidato em B")

    def test_descartado_com_cotacao_e_cortado_pelo_gate_so_no_proprio_projeto(self):
        """Ancora com cotacao: `compute_ranking` (motor do ranking, dashboard
        e Sheets) tem que ler a participacao MESCLADA por projeto - nao a
        ficha crua - para eliminar pelo gate no projeto certo e so nele."""
        self._vincular_b()
        for projeto in (self.projeto_a, self.projeto_b):
            self.cli("cotar", str(projeto), "--produto-id", "fone-comum", "--loja", "Amazon",
                      "--vendedor", "V", "--vendedor-tipo", "oficial", "--preco", "150",
                      "--nota", "4.7", "--avaliacoes", "800", "--frete-prazo-dias", "3",
                      "--garantia-tipo", "nacional", "--garantia-meses", "12",
                      "--link", "https://example.invalid/fone-comum", "--fonte", "manual")

        self.cli("descartar", "--produto-id", "fone-comum", "--porque", "vendedor sumiu",
                  "--projeto", str(self.projeto_a))

        elegiveis_a, cortados_a = cc.compute_ranking(self.projeto_a)
        self.assertEqual(elegiveis_a, [])
        self.assertEqual(len(cortados_a), 1)
        self.assertTrue(any("descartado" in motivo for motivo in cortados_a[0].eliminations))

        elegiveis_b, cortados_b = cc.compute_ranking(self.projeto_b)
        self.assertEqual(cortados_b, [])
        self.assertEqual([item.produto_id for item in elegiveis_b], ["fone-comum"])


class VincularProdutoTest(ambiente.RepoTestCase):
    def setUp(self):
        super().setUp()
        self.projeto_a = self.project(name="origem", category="fone", value=400)
        self.projeto_b = self.project(name="destino", category="fone", value=400)

    def test_vincular_produto_inexistente_recusa(self):
        with self.assertRaises(SystemExit):
            self.cli("vincular-produto", "--produto-id", "fantasma", "--projeto", str(self.projeto_b))
        self.assertFalse((self.projeto_b / "participacoes").exists())

    def test_novo_produto_com_ficha_existente_orienta_vincular(self):
        self.product(self.projeto_a, pid="candidato")
        with self.assertRaises(SystemExit) as ctx:
            self.cli("novo-produto", str(self.projeto_b), "Candidato", "--produto-id", "candidato")
        self.assertIn("vincular-produto", str(ctx.exception))

    def test_vincular_de_novo_no_mesmo_projeto_e_seguro(self):
        self.product(self.projeto_a, pid="candidato")
        self.cli("vincular-produto", "--produto-id", "candidato", "--projeto", str(self.projeto_b))
        self.cli("descartar", "--produto-id", "candidato", "--porque", "motivo b",
                  "--projeto", str(self.projeto_b))

        with self.assertRaises(SystemExit) as ctx:
            self.cli("vincular-produto", "--produto-id", "candidato", "--projeto", str(self.projeto_b))
        self.assertIn("ja tem participacao", str(ctx.exception))

        # Nada foi sobrescrito: continua descartado com o motivo original.
        participacao = cc.read_participation(self.projeto_b, "candidato")
        self.assertEqual(participacao["estado"], "descartado")
        self.assertEqual(participacao["descartado_porque"], "motivo b")

    def test_ambiguidade_sem_projeto_recusa_sem_escrever(self):
        self.product(self.projeto_a, pid="candidato")
        self.cli("vincular-produto", "--produto-id", "candidato", "--projeto", str(self.projeto_b))

        antes_a = cc.read_participation(self.projeto_a, "candidato")
        antes_b = cc.read_participation(self.projeto_b, "candidato")
        with self.assertRaises(SystemExit) as ctx:
            self.cli("descartar", "--produto-id", "candidato", "--porque", "motivo qualquer")
        self.assertIn("mais de um projeto", str(ctx.exception))

        depois_a = cc.read_participation(self.projeto_a, "candidato")
        depois_b = cc.read_participation(self.projeto_b, "candidato")
        self.assertEqual(antes_a, depois_a)
        self.assertEqual(antes_b, depois_b)

    def test_ambiguidade_com_projeto_explicito_funciona(self):
        self.product(self.projeto_a, pid="candidato")
        self.cli("vincular-produto", "--produto-id", "candidato", "--projeto", str(self.projeto_b))
        self.cli("descartar", "--produto-id", "candidato", "--porque", "so em b",
                  "--projeto", str(self.projeto_b))
        self.assertEqual(cc.read_participation(self.projeto_b, "candidato")["estado"], "descartado")
        self.assertEqual(cc.read_participation(self.projeto_a, "candidato")["estado"], "pesquisando")


class MigracaoParticipacaoTest(ambiente.RepoTestCase):
    """Registro antigo (estado/preco/requisitos direto na ficha, campo
    `projeto` unico) migra para participacao, de forma idempotente."""

    def _gravar_ficha_legada(self, projeto, produto_id="legado", **extra):
        path = cc.product_dir("fone", produto_id)
        path.mkdir(parents=True, exist_ok=True)
        dados = {
            "id": produto_id, "categoria": "fone", "nome": "Fone Legado", "marca": "Marca Z",
            "projeto": projeto.name, "estado": "pesquisando",
            "preco_alvo": 100.0, "preco_teto": 200.0,
            "requisitos_atendidos": {"bluetooth": True}, "descartado_porque": None,
        }
        dados.update(extra)
        cc.write_yaml(path / "produto.yaml", dados)
        return path / "produto.yaml"

    def test_preview_sem_aplicar_nao_escreve_nada(self):
        projeto = self.project()
        ficha_path = self._gravar_ficha_legada(projeto)
        antes = ficha_path.read_text(encoding="utf-8")

        self.cli("migrar-produtos")

        self.assertEqual(ficha_path.read_text(encoding="utf-8"), antes)
        self.assertFalse((projeto / "participacoes" / "legado.yaml").exists())

    def test_aplicar_migra_e_preserva_leitura(self):
        projeto = self.project()
        self._gravar_ficha_legada(projeto)

        leitura_antes = cc.find_product("legado", projeto)
        self.cli("migrar-produtos", "--aplicar")
        leitura_depois = cc.find_product("legado", projeto)

        self.assertEqual(leitura_antes["estado"], leitura_depois["estado"])
        self.assertEqual(leitura_antes["preco_alvo"], leitura_depois["preco_alvo"])
        self.assertEqual(leitura_antes["requisitos_atendidos"], leitura_depois["requisitos_atendidos"])

        ficha = cc.read_yaml(cc.find_product_path("legado"), {})
        self.assertNotIn("projeto", ficha)
        self.assertNotIn("estado", ficha)
        self.assertNotIn("preco_alvo", ficha)
        self.assertTrue((projeto / "participacoes" / "legado.yaml").exists())

    def test_aplicar_duas_vezes_e_idempotente(self):
        projeto = self.project()
        self._gravar_ficha_legada(projeto)
        self.cli("migrar-produtos", "--aplicar")

        participacao_path = projeto / "participacoes" / "legado.yaml"
        conteudo_apos_1a = participacao_path.read_text(encoding="utf-8")
        ficha_apos_1a = cc.find_product_path("legado").read_text(encoding="utf-8")

        self.cli("migrar-produtos", "--aplicar")

        self.assertEqual(participacao_path.read_text(encoding="utf-8"), conteudo_apos_1a)
        self.assertEqual(cc.find_product_path("legado").read_text(encoding="utf-8"), ficha_apos_1a)

    def test_participacao_mais_fresca_nunca_e_sobrescrita_pela_ficha_legada(self):
        """`descartar` ja rodou sobre o registro legado (grava participacao
        nova, ficha legada intocada) antes da migracao em lote acontecer -
        migrar nao pode voltar o estado pra tras usando o dado velho da ficha."""
        projeto = self.project()
        self._gravar_ficha_legada(projeto)
        self.cli("descartar", "--produto-id", "legado", "--porque", "descartado antes de migrar")

        self.cli("migrar-produtos", "--aplicar")

        participacao = cc.read_participation(projeto, "legado")
        self.assertEqual(participacao["estado"], "descartado")
        self.assertEqual(participacao["descartado_porque"], "descartado antes de migrar")

    def test_uso_cruzado_e_relatado_nao_adivinhado(self):
        """Ficha legada aponta pra projeto A, mas ha cotacao em B tambem -
        migracao nao decide sozinha qual e a legada, so relata."""
        projeto_a = self.project(name="projeto-a")
        projeto_b = self.project(name="projeto-b")
        self._gravar_ficha_legada(projeto_a)
        self.cli("cotar", str(projeto_b), "--produto-id", "legado", "--loja", "Amazon",
                  "--vendedor", "V", "--vendedor-tipo", "oficial", "--preco", "150",
                  "--nota", "4.5", "--avaliacoes", "500", "--frete-prazo-dias", "3",
                  "--garantia-tipo", "nacional", "--garantia-meses", "12",
                  "--link", "https://example.invalid/x", "--fonte", "web")

        saida = self.cli("migrar-produtos", "--aplicar")

        self.assertIn("uso cruzado", saida.lower())
        self.assertFalse((projeto_a / "participacoes" / "legado.yaml").exists())
        # ficha permanece intocada (nao migrada) - decisao fica com o Josemar.
        ficha = cc.read_yaml(cc.find_product_path("legado"), {})
        self.assertEqual(ficha.get("projeto"), projeto_a.name)


class ProtecaoDeOperacaoPendenteTest(ambiente.RepoTestCase):
    """Criterio 7: arquivo de participacao entra no mesmo mecanismo de
    recursos pendentes que ja protege decisao.md/processo.md/veredito."""

    def _plantar_operacao_pendente(self, projeto, produto_id, op_id="decidir:outro"):
        caminho_participacao = cc.participation_path(projeto, produto_id)
        journal_dir = projeto / cc._OPERATIONS_DIRNAME
        journal_dir.mkdir(parents=True, exist_ok=True)
        registro = {
            "op_id": op_id, "kind": "decidir", "situacao": "em_andamento", "passos": {},
            "assinatura_fingerprint": "x", "detalhe": {},
            "recursos": [str(caminho_participacao.resolve())],
            "iniciado_em": cc.now_iso(), "atualizado_em": cc.now_iso(), "pid": 999999,
        }
        (journal_dir / f"{cc.slugify(op_id)}.json").write_text(
            json.dumps(registro, ensure_ascii=True, indent=2), encoding="utf-8"
        )

    def test_descartar_recusado_com_participacao_reivindicada(self):
        projeto = self.project()
        self.product(projeto, pid="candidato")
        self._plantar_operacao_pendente(projeto, "candidato")

        with self.assertRaises(SystemExit):
            self.cli("descartar", "--produto-id", "candidato", "--porque", "x", "--projeto", str(projeto))

        participacao = cc.read_participation(projeto, "candidato")
        self.assertEqual(participacao["estado"], "pesquisando", "nada pode ter sido escrito")

    def test_descartar_funciona_apos_pendencia_resolvida(self):
        projeto = self.project()
        self.product(projeto, pid="candidato")
        self._plantar_operacao_pendente(projeto, "candidato")
        (projeto / cc._OPERATIONS_DIRNAME).glob("*.json")
        for arquivo in (projeto / cc._OPERATIONS_DIRNAME).glob("*.json"):
            arquivo.unlink()

        self.cli("descartar", "--produto-id", "candidato", "--porque", "liberado", "--projeto", str(projeto))
        self.assertEqual(cc.read_participation(projeto, "candidato")["estado"], "descartado")


if __name__ == "__main__":
    unittest.main()
