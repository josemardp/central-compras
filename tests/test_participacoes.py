"""Frente 5: produto reutilizado em projetos diferentes.

Cenario ancora: o MESMO produto_id participa de dois projetos com estados,
motivos, limites e requisitos independentes. Descarte, espera ou preco-alvo
num projeto nunca pode vazar para o outro - a ficha (`produto.yaml`) guarda
so identidade e dado tecnico; participacao (estado, descarte, preco-alvo/
teto, requisitos atendidos) mora em `projetos/<projeto>/participacoes/
<produto_id>.yaml`.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

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

    def _plantar_operacao_pendente_sobre_participacao(self, projeto, produto_id, op_id="decidir:outro"):
        """Journal `em_andamento`, de outra operacao (nunca a da migracao,
        que nao tem journal proprio), reivindicando o arquivo de
        participacao que a migracao criaria para `produto_id`."""
        journal_dir = projeto / cc._OPERATIONS_DIRNAME
        journal_dir.mkdir(parents=True, exist_ok=True)
        registro = {
            "op_id": op_id, "kind": "decidir", "situacao": "em_andamento", "passos": {},
            "assinatura_fingerprint": "x", "detalhe": {},
            "recursos": [str(cc.participation_path(projeto, produto_id).resolve())],
            "iniciado_em": cc.now_iso(), "atualizado_em": cc.now_iso(), "pid": 999999,
        }
        (journal_dir / f"{cc.slugify(op_id)}.json").write_text(
            json.dumps(registro, ensure_ascii=True, indent=2), encoding="utf-8"
        )

    def test_migracao_recusada_com_participacao_reivindicada(self):
        """Um journal valido (de OUTRA operacao) reivindicando o arquivo de
        participacao que a migracao criaria bloqueia a migracao: ela nao
        pode criar esse arquivo nem limpar a ficha por baixo dessa operacao
        pendente."""
        projeto = self.project()
        ficha_path = self._gravar_ficha_legada(projeto)
        antes = ficha_path.read_bytes()
        self._plantar_operacao_pendente_sobre_participacao(projeto, "legado")

        with self.assertRaises(SystemExit):
            self.cli("migrar-produtos", "--aplicar")

        self.assertEqual(ficha_path.read_bytes(), antes, "migracao escreveu a ficha apesar do journal pendente")
        self.assertFalse(
            cc.participation_path(projeto, "legado").exists(),
            "migracao criou a participacao reivindicada por outra operacao pendente",
        )

    def test_migracao_libera_apos_pendencia_resolvida(self):
        """Assim que o journal que reivindicava o arquivo e removido (a
        operacao concluiu ou foi resolvida a mao), a migracao volta a
        funcionar normalmente - a checagem le o estado ATUAL, nao guarda
        bloqueio permanente."""
        projeto = self.project()
        self._gravar_ficha_legada(projeto)
        self._plantar_operacao_pendente_sobre_participacao(projeto, "legado")
        for arquivo in (projeto / cc._OPERATIONS_DIRNAME).glob("*.json"):
            arquivo.unlink()

        self.cli("migrar-produtos", "--aplicar")

        self.assertTrue(cc.participation_path(projeto, "legado").exists())
        self.assertEqual(cc.read_participation(projeto, "legado")["estado"], "pesquisando")

    def test_migracao_bloqueia_so_o_candidato_reivindicado_no_lote(self):
        """Num lote com dois produtos legados, so o que tem operacao pendente
        reivindicando a propria participacao fica bloqueado - o outro migra
        normalmente. `--aplicar` ainda assim termina em erro (ha bloqueado),
        para o Josemar nao presumir que tudo passou."""
        projeto = self.project()
        self._gravar_ficha_legada(projeto, produto_id="legado-livre")
        self._gravar_ficha_legada(projeto, produto_id="legado-preso")
        self._plantar_operacao_pendente_sobre_participacao(projeto, "legado-preso")

        with self.assertRaises(SystemExit):
            self.cli("migrar-produtos", "--aplicar")

        self.assertTrue(cc.participation_path(projeto, "legado-livre").exists(),
                         "candidato sem conflito deveria ter migrado mesmo com outro bloqueado")
        self.assertFalse(cc.participation_path(projeto, "legado-preso").exists())


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


class RevisaoIndependenteFrente5Test(ambiente.RepoTestCase):
    """Regressao dos 6 achados da revisao independente (Astra) sobre o
    commit `e29c45c` - cada teste aqui reproduziu uma falha real contra o
    codigo daquele commit antes da correcao. Ver STATUS.md e
    docs/como-conferir-auditoria.md."""

    def _legado(self, project, **extra):
        path = cc.product_dir("fone", "legado") / "produto.yaml"
        data = dict(id="legado", categoria="fone", nome="Legado", marca="Marca", projeto=project.name,
                    estado="pesquisando", preco_alvo=100, preco_teto=300, requisitos_atendidos={"uso": True})
        data.update(extra)
        cc.write_yaml(path, data)
        return path

    def test_prompt_de_b_nao_pode_herdar_descarte_de_a(self):
        """Achado 1: `ai_prompt` chamava `find_product(pid)` sem projeto -
        o motivo de descarte de A vazava pro prompt-ia de B."""
        a = self.project("origem")
        b = self.project("destino")
        self._legado(a, estado="descartado", descartado_porque="EXCLUSAO_EXCLUSIVA_A")
        self.cli("vincular-produto", "--produto-id", "legado", "--projeto", str(b))

        prompt = self.cli("prompt-ia", str(b), "--etapa", "cotacao")

        self.assertNotIn("EXCLUSAO_EXCLUSIVA_A", prompt)

    def test_prompt_mostra_estado_de_produto_novo(self):
        """A mesma correcao do achado 1 tambem parou de omitir o estado de
        um produto recem-cadastrado (sem descarte, so `pesquisando`) do
        contexto do prompt - antes, `find_product(pid)` sem projeto nunca
        trazia NENHUM campo de participacao, nem para o proprio projeto."""
        a = self.project()
        self.product(a, pid="novo")

        prompt = self.cli("prompt-ia", str(a), "--etapa", "cotacao")

        self.assertIn("pesquisando", prompt)

    def test_validacao_de_b_nao_pode_herdar_descarte_de_a(self):
        """Achado 2: `validation_report` tinha o mesmo `find_product(pid)`
        sem projeto - produto ativo e cotado em B era acusado de "descartado
        sem motivo" por causa de um descarte (sem motivo) so em A."""
        a = self.project("origem")
        b = self.project("destino")
        self._legado(a, estado="descartado", descartado_porque=None)
        self.cli("vincular-produto", "--produto-id", "legado", "--projeto", str(b))
        self.quote(b, "legado")

        errors, _ = cc.validation_report(b)

        self.assertNotIn("legado: produto descartado sem motivo.", errors)

    def test_snapshot_congela_evidencia_da_participacao(self):
        """Achado 3: `_decide_writes` congelava a ficha mas nunca a
        participacao - um requisito gravado so na participacao passava por
        `auditar-decisoes --strict` sem aparecer em nenhum arquivo do
        snapshot, quebrando a rastreabilidade que a decisao promete."""
        a = self.project()
        self.product(a)
        p = cc.read_participation(a, "candidato")
        p["requisitos_atendidos"]["REQUISITO_EXCLUSIVO_DESTA_COMPRA"] = True
        cc.write_participation(a, "candidato", p)
        self.quote(a, "candidato", "--fonte", "manual")

        self.cli("decidir", str(a), "--produto-id", "candidato", "--porque", "unico",
                  "--sem-perdedores", "--comprado")
        snapshot = next((a / "snapshots").iterdir())
        self.cli("auditar-decisoes", "--strict")

        files = [f for f in snapshot.rglob("*") if f.is_file()]
        frozen = "\n".join(f.read_text(encoding="utf-8") for f in files)
        self.assertIn(
            "REQUISITO_EXCLUSIVO_DESTA_COMPRA", frozen,
            "Auditoria passa, mas o snapshot nao contem a evidencia de requisitos usada no score",
        )

    def test_snapshot_participacao_imutavel_apos_alteracao_posterior(self):
        """A evidencia congelada da participacao nao pode mudar se o mesmo
        produto for descartado, no MESMO projeto, depois da decisao fechada -
        mesmo principio ja valido para ranking.md/cotacoes.csv."""
        a = self.project()
        self.product(a)
        self.quote(a, "candidato", "--fonte", "manual")
        self.cli("decidir", str(a), "--produto-id", "candidato", "--porque", "unico",
                  "--sem-perdedores", "--comprado")
        snapshot = next((a / "snapshots").iterdir())
        participacao_congelada_antes = (snapshot / "participacoes" / "candidato.yaml").read_bytes()

        self.cli("novo-produto", str(a), "Outro", "--produto-id", "outro-produto")
        self.cli("descartar", "--produto-id", "outro-produto", "--porque", "mudanca depois da decisao")

        self.assertEqual(
            (snapshot / "participacoes" / "candidato.yaml").read_bytes(),
            participacao_congelada_antes,
        )

    def test_vinculo_interrompido_consegue_retomar(self):
        """Achado 4: `vincular-produto` gravava a participacao e so depois
        chamava `append_timeline`, sem journal proprio. Uma interrupcao entre
        os dois passos deixava a participacao gravada e a operacao
        incompleta; a retomada era recusada por "ja tem participacao",
        embora a operacao original nunca tivesse terminado."""
        a = self.project("origem")
        b = self.project("destino")
        self.product(a)
        args = ["vincular-produto", "--produto-id", "candidato", "--projeto", str(b)]
        before = (b / "processo.md").read_bytes()

        with patch.object(cc, "append_timeline", side_effect=RuntimeError("interrupcao antes da timeline")):
            with self.assertRaises(RuntimeError):
                self.cli(*args)

        self.assertTrue(cc.participation_path(b, "candidato").exists())
        self.assertEqual(before, (b / "processo.md").read_bytes())

        self.cli(*args)

        self.assertIn("Produto reaproveitado", (b / "processo.md").read_text(encoding="utf-8"))
        # A retomada nao duplicou a participacao nem reescreveu com outro
        # requisito - so completou o que faltava.
        self.assertEqual(cc.read_participation(b, "candidato")["requisitos_atendidos"], {})

    def test_vinculo_interrompido_por_crash_real_recupera_via_subprocesso(self):
        """Mesmo achado 4, mas com interrupcao dura (`os._exit`, sem
        excecao Python) num subprocesso real - nao so uma excecao mockada no
        mesmo processo. Confirma que a recuperacao tambem funciona quando o
        processo morre de verdade entre gravar a participacao e a timeline,
        e que `operacoes-pendentes --strict` fica limpo depois da retomada."""
        a = self.project("origem")
        b = self.project("destino")
        self.product(a)
        argv = ["vincular-produto", "--produto-id", "candidato", "--projeto", str(b)]
        injetado = (
            "import sys, os\n"
            "from scripts import central_compras as cc\n"
            "cc.append_timeline = lambda *a, **k: os._exit(70)\n"
            "cc.main(sys.argv[1:])\n"
        )
        primeira = subprocess.run(
            [sys.executable, "-c", injetado, *argv], cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(primeira.returncode, 70, primeira.stderr)

        retomada = subprocess.run(
            [sys.executable, "scripts/central_compras.py", *argv], cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(retomada.returncode, 0, retomada.stderr)

        pendencias = subprocess.run(
            [sys.executable, "scripts/central_compras.py", "operacoes-pendentes", "--strict"],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(pendencias.returncode, 0, pendencias.stdout + pendencias.stderr)
        self.assertTrue(cc.participation_path(b, "candidato").exists())
        self.assertIn("Produto reaproveitado", (b / "processo.md").read_text(encoding="utf-8"))

    def test_migracao_respeita_participacao_reivindicada(self):
        """Achado 5: `migrar-produtos` nao checava a checagem central de
        recursos conflitantes - um journal valido reivindicando o arquivo de
        participacao nao impedia a migracao de cria-lo e limpar a ficha."""
        a = self.project()
        ficha = self._legado(a)
        opid = "decidir:outro"
        journal = a / cc._OPERATIONS_DIRNAME / (cc.slugify(opid) + ".json")
        journal.parent.mkdir(parents=True, exist_ok=True)
        registro = dict(
            op_id=opid, kind="decidir", situacao="em_andamento", passos={},
            assinatura_fingerprint="x", detalhe={},
            recursos=[str(cc.participation_path(a, "legado").resolve())],
            iniciado_em=cc.now_iso(), atualizado_em=cc.now_iso(), pid=999999,
        )
        journal.write_text(json.dumps(registro), encoding="utf-8")
        before = ficha.read_bytes()

        self.assertEqual(len(cc.pending_operations([a])), 1)
        rejeitado = False
        try:
            self.cli("migrar-produtos", "--aplicar")
        except SystemExit:
            rejeitado = True

        self.assertTrue(
            rejeitado and ficha.read_bytes() == before and not cc.participation_path(a, "legado").exists(),
            "migrar-produtos escreveu recurso reivindicado e limpou ficha apesar do journal pendente",
        )

    def test_requisito_invalido_nao_deixa_ficha_orfa(self):
        """Achado 6: `novo-produto --requisito sem-separador` lancava
        `SystemExit` DEPOIS de gravar produto.yaml/pesquisa.md - a ficha
        ficava orfa, sem participacao, e sem caminho limpo de retomada."""
        a = self.project()
        with self.assertRaises(SystemExit):
            self.cli("novo-produto", str(a), "Invalido", "--produto-id", "invalido", "--requisito", "sem-separador")

        self.assertIsNone(
            cc.find_product_path("invalido"), "Entrada rejeitada deixou produto.yaml e pesquisa.md no disco",
        )

    def test_requisito_corrigido_apos_falha_funciona_normalmente(self):
        """Depois da entrada invalida ser rejeitada sem deixar rastro, a
        MESMA chamada com o requisito corrigido tem que funcionar - nada
        ficou preso pela tentativa anterior."""
        a = self.project()
        with self.assertRaises(SystemExit):
            self.cli("novo-produto", str(a), "Invalido", "--produto-id", "invalido", "--requisito", "sem-separador")

        self.cli("novo-produto", str(a), "Invalido", "--produto-id", "invalido", "--requisito", "uso=true")

        self.assertIsNotNone(cc.find_product_path("invalido"))
        self.assertEqual(cc.read_participation(a, "invalido")["requisitos_atendidos"], {"uso": True})


class SegundaRevisaoIndependenteFrente5Test(ambiente.RepoTestCase):
    """Regressao dos 3 achados da 2a revisao independente (Astra) sobre o
    commit `fcdb6f9` - cada teste aqui reproduziu uma falha real contra
    aquele codigo antes da correcao. Ver STATUS.md e
    docs/como-conferir-auditoria.md. Os 3 primeiros sao as falhas; os 3
    seguintes sao controles que ja passavam e continuam passando."""

    def _legado(self, project, **extra):
        path = cc.product_dir("fone", "legado") / "produto.yaml"
        data = dict(id="legado", categoria="fone", nome="Legado", marca="Marca", projeto=project.name,
                    estado="descartado", descartado_porque="nao atende", preco_alvo=100, preco_teto=300,
                    requisitos_atendidos={"uso": True})
        data.update(extra)
        cc.write_yaml(path, data)
        return path

    def _setup_vinculo(self):
        a = self.project("origem")
        b = self.project("destino")
        self.product(a)
        return a, b, ["vincular-produto", "--produto-id", "candidato", "--projeto", str(b)]

    def test_migracao_nao_perde_descarte_com_participacao_vazia(self):
        """Achado 1: um arquivo de participacao EXISTENTE mas vazio (0 bytes)
        era tratado como "ja tinha participacao" - a migracao limpava a
        ficha legada (unica fonte real do descarte) por cima de um arquivo
        sem nenhum dado recuperavel, e o candidato voltava a `pesquisando`."""
        a = self.project()
        ficha = self._legado(a)
        p = cc.participation_path(a, "legado")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")
        self.assertEqual(cc.read_participation(a, "legado")["estado"], "descartado")

        self.cli("migrar-produtos", "--aplicar")

        self.assertEqual(
            cc.read_participation(a, "legado")["estado"], "descartado",
            "Migracao limpou o unico estado recuperavel da ficha e o candidato voltou a pesquisando",
        )

    def test_falha_na_etapa_final_deixa_vinculo_recuperavel(self):
        """Achado 2: `mark_steps(project, [3])` rodava FORA do
        `tracked_operation` de `link_product`. Uma interrupcao depois da
        participacao/timeline gravadas mas antes de marcar a etapa 3 dava
        journal ja apagado (operacao "concluida") - nenhuma pendencia
        visivel para retomar, e a etapa 3 ficava presa sem marcar para
        sempre (retomada recusada por "ja tem participacao")."""
        a, b, args = self._setup_vinculo()
        with patch.object(cc, "mark_steps", side_effect=OSError("falha antes de marcar etapa 3")):
            with self.assertRaises(OSError):
                self.cli(*args)

        self.assertIn("- [ ] 3.", (b / "processo.md").read_text(encoding="utf-8"))
        self.assertTrue(
            cc.pending_operations([b]),
            "Journal apagado antes da ultima escrita: pendencia da etapa 3 ficou invisivel",
        )

        self.cli(*args)

        self.assertIn("- [x] 3.", (b / "processo.md").read_text(encoding="utf-8"))

    def test_retry_em_outro_dia_nao_duplica_timeline(self):
        """Achado 3: a assinatura do efeito de timeline era congelada com a
        data do dia em que a tentativa comecou, mas o `executar()` chamava
        `append_timeline` sem passar essa data - a linha realmente gravada
        saia com a data ATUAL, nunca batendo com a assinatura congelada.
        Cada retomada em outro dia reconciliava como "nunca aconteceu" e
        escrevia outra linha nova."""
        a, b, args = self._setup_vinculo()
        real_append = cc.append_timeline
        with patch.object(cc, "today", return_value="2026-09-08"):
            with patch.object(cc, "append_timeline", side_effect=OSError("antes de escrever timeline")):
                with self.assertRaises(OSError):
                    self.cli(*args)

        def append_then_crash(*args_, **kwargs):
            real_append(*args_, **kwargs)
            raise OSError("depois de escrever timeline, antes de confirmar")

        with patch.object(cc, "today", return_value="2026-09-09"):
            with patch.object(cc, "append_timeline", side_effect=append_then_crash):
                with self.assertRaises(OSError):
                    self.cli(*args)

        with patch.object(cc, "today", return_value="2026-09-10"):
            self.cli(*args)

        timeline = (b / "processo.md").read_text(encoding="utf-8")
        self.assertEqual(
            timeline.count("Produto reaproveitado:"), 1,
            "Retomadas em dias diferentes duplicaram a mesma operacao na timeline",
        )

    def test_retomada_com_argumentos_diferentes_recusa(self):
        """Controle: retomar `vincular-produto` com dado diferente da
        tentativa original continua recusado, sem tocar na participacao ja
        gravada pela tentativa interrompida."""
        a, b, args = self._setup_vinculo()
        with patch.object(cc, "append_timeline", side_effect=OSError("crash")):
            with self.assertRaises(OSError):
                self.cli(*args)
        before = cc.participation_path(b, "candidato").read_bytes()

        with self.assertRaises(SystemExit):
            self.cli(*args, "--preco-alvo", "75")
        self.assertEqual(cc.participation_path(b, "candidato").read_bytes(), before)

        self.cli(*args)

    def test_migracao_retomada_entre_duas_escritas_preserva_estado(self):
        """Controle: uma falha entre gravar a participacao e limpar a ficha
        legada nao perde o estado - a retomada nao sobrescreve a
        participacao ja valida com o dado legado de novo, so termina de
        limpar a ficha."""
        a = self.project()
        ficha = self._legado(a)
        real_write = cc.write_yaml

        def fail_cleanup(path, data):
            if path == ficha:
                raise OSError("falha antes de limpar ficha")
            return real_write(path, data)

        with patch.object(cc, "write_yaml", side_effect=fail_cleanup):
            with self.assertRaises(OSError):
                self.cli("migrar-produtos", "--aplicar")

        self.cli("migrar-produtos", "--aplicar")

        self.assertEqual(cc.read_participation(a, "legado")["estado"], "descartado")
        self.assertNotIn("estado", cc.read_yaml(ficha, {}))

    def test_snapshot_preserva_mesmo_produto_apos_alteracao_no_mesmo_projeto(self):
        """Controle: descartar o MESMO produto no mesmo projeto depois de
        uma decisao fechada nao muda 1 byte da evidencia ja congelada no
        snapshot, e `auditar-decisoes --strict` continua limpo."""
        a = self.project()
        self.product(a)
        self.quote(a, "candidato", "--fonte", "manual")
        self.cli("decidir", str(a), "--produto-id", "candidato", "--porque", "unico",
                  "--sem-perdedores", "--comprado")
        snap = next((a / "snapshots").iterdir())
        frozen = {str(p.relative_to(snap)): p.read_bytes() for p in snap.rglob("*") if p.is_file()}

        self.cli("descartar", "--produto-id", "candidato", "--projeto", str(a), "--porque", "mudou depois")

        after = {str(p.relative_to(snap)): p.read_bytes() for p in snap.rglob("*") if p.is_file()}
        self.assertEqual(frozen, after)
        self.cli("auditar-decisoes", "--strict")


class TerceiraRevisaoIndependenteFrente5Test(ambiente.RepoTestCase):
    """Regressao dos 3 achados da 3a revisao independente (Astra) sobre o
    commit `6669b9d` - cada teste aqui reproduziu uma falha real contra
    aquele codigo antes da correcao. Ver STATUS.md e
    docs/como-conferir-auditoria.md."""

    def _setup_vinculo(self):
        a = self.project("origem")
        b = self.project("destino")
        self.product(a)
        return a, b, ["vincular-produto", "--produto-id", "candidato", "--projeto", str(b)]

    def test_mapas_incompletos_ou_incoerentes_nao_autorizam_limpar_legado(self):
        """Achado 1: `isinstance(dados, dict) and bool(dados)` so provava
        que o arquivo tinha ALGUM conteudo, nunca que esse conteudo era uma
        participacao de verdade - um mapa so com `produto_id`, so com uma
        anotacao solta, com o `produto_id` de OUTRO produto, ou com `estado`
        fora do vocabulario conhecido, todos "passavam" e autorizavam a
        migracao a apagar o campo legado da ficha (unica evidencia real)
        por cima de lixo."""
        a = self.project()
        for index, kind in enumerate(["so_id", "so_anotacao", "id_divergente", "estado_desconhecido"]):
            with self.subTest(kind=kind):
                pid = f"legado-{index}"
                ficha = cc.product_dir("fone", pid) / "produto.yaml"
                original = dict(
                    id=pid, categoria="fone", nome="Legado", marca="Marca", projeto=a.name,
                    estado="descartado", descartado_porque="nao atende", preco_alvo=100, preco_teto=300,
                    requisitos_atendidos={"uso": True},
                )
                cc.write_yaml(ficha, original)
                part = cc.participation_path(a, pid)
                invalid = {
                    "so_id": {"produto_id": pid},
                    "so_anotacao": {"anotacao": "DADO_A_PRESERVAR"},
                    "id_divergente": cc.default_participation("outro-produto"),
                    "estado_desconhecido": dict(cc.default_participation(pid), estado="descartdao"),
                }[kind]
                cc.write_yaml(part, invalid)
                before = (ficha.read_bytes(), part.read_bytes())

                with self.assertRaises(SystemExit):
                    self.cli("migrar-produtos", "--projeto", str(a), "--aplicar")

                self.assertEqual(
                    (ficha.read_bytes(), part.read_bytes()), before,
                    f"{kind}: migracao aceitou participacao sem contrato valido e limpou/sobrescreveu arquivo",
                )

    def test_nome_do_produto_tambem_precisa_ser_estavel_na_retomada(self):
        """Achado 2: a data foi congelada na correcao anterior, mas
        `nome_produto` continuava sendo relido da ficha compartilhada a cada
        tentativa - um `novo-produto --force` rodado em OUTRO projeto entre
        a falha e a retomada muda o nome ali, e a retomada escrevia a linha
        com o nome NOVO, que nunca batia com a assinatura congelada (nome
        antigo), duplicando a cada retomada."""
        a, b, args = self._setup_vinculo()
        original_append = cc.append_timeline
        with patch.object(cc, "append_timeline", side_effect=OSError("antes de gravar timeline")):
            with self.assertRaises(OSError):
                self.cli(*args)

        # Alteracao permitida pelo CLI em OUTRO projeto, na ficha compartilhada.
        self.cli("novo-produto", str(a), "Nome atualizado", "--produto-id", "candidato", "--force")

        def write_then_fail(*args_, **kwargs):
            original_append(*args_, **kwargs)
            raise OSError("depois de gravar timeline, antes de confirmar")

        with patch.object(cc, "append_timeline", side_effect=write_then_fail):
            with self.assertRaises(OSError):
                self.cli(*args)

        self.cli(*args)

        text = (b / "processo.md").read_text(encoding="utf-8")
        self.assertEqual(
            text.count("Produto reaproveitado:"), 1,
            "Data foi congelada, mas nome foi recalculado: a assinatura antiga nao reconhece a linha nova",
        )

    def test_journal_real_da_versao_anterior_continua_retomavel(self):
        """Achado 3: `link_product` passou a exigir
        `op.detalhe["data_evento"]` (e depois tambem `nome_produto`), mas um
        journal `em_andamento` comecado por uma versao anterior do comando
        (antes desses campos existirem) nao tem essas chaves - a retomada
        quebrava com `KeyError` em vez de reconciliar. Reproduzido com o
        codigo real do commit `fcdb6f9` (versao anterior a esta correcao)
        via subprocesso, criando uma pendencia de verdade antes de trocar
        para o codigo atual."""
        a, b, args = self._setup_vinculo()
        sandbox_code = self.root / "scripts" / "central_compras.py"
        current = sandbox_code.read_bytes()
        old = subprocess.run(
            ["git", "show", "fcdb6f9:scripts/central_compras.py"],
            cwd=ambiente.ROOT, capture_output=True, check=True,
        ).stdout
        sandbox_code.write_bytes(old)
        codigo_injetado = (
            "import sys, os\n"
            "from scripts import central_compras as cc\n"
            "cc.append_timeline = lambda *a, **k: os._exit(70)\n"
            "cc.main(sys.argv[1:])\n"
        )
        crash = subprocess.run(
            [sys.executable, "-c", codigo_injetado, *args], cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(crash.returncode, 70, crash.stderr)
        journal = next((b / cc._OPERATIONS_DIRNAME).glob("*.json"))
        self.assertNotIn(
            "data_evento", json.loads(journal.read_text(encoding="utf-8"))["detalhe"],
            "journal antigo deveria mesmo estar sem a chave nova - senao o teste nao reproduz nada",
        )

        sandbox_code.write_bytes(current)
        retry = subprocess.run(
            [sys.executable, "scripts/central_compras.py", *args], cwd=self.root, capture_output=True, text=True,
        )

        self.assertEqual(retry.returncode, 0, retry.stderr)
        self.assertFalse(cc.pending_operations([b]))
        self.assertEqual(
            (b / "processo.md").read_text(encoding="utf-8").count("Produto reaproveitado:"), 1,
        )

    def test_nome_congelado_mesmo_quando_timeline_nunca_foi_tentada(self):
        """Achado 2, janela que `efeito_congelado` (achado 3) NAO cobre: se
        o processo cai logo depois de concluir a participacao mas ANTES de
        sequer tentar o passo da timeline pela primeira vez, nao ha nenhum
        `assinatura_efeito` persistido ainda pra reaproveitar - a retomada
        cai no ramo que monta a linha com dado atual. Esse ramo precisa usar
        o nome CONGELADO em `op.detalhe` na 1a tentativa, nao o nome atual
        da ficha (que pode ter mudado nesse meio-tempo via `novo-produto
        --force` em outro projeto) - senao a linha escrita e a errada (nao
        duplica, mas atribui o vinculo ao nome novo, que nao era o nome no
        momento em que a operacao comecou)."""
        a, b, args = self._setup_vinculo()
        env = dict(os.environ)
        env["CENTRAL_COMPRAS_TESTE_CRASH_APOS"] = "participacao"
        primeira = subprocess.run(
            [sys.executable, "scripts/central_compras.py", *args],
            cwd=self.root, env=env, capture_output=True, text=True,
        )
        self.assertEqual(primeira.returncode, 70, primeira.stderr)
        self.assertTrue(cc.participation_path(b, "candidato").exists())
        self.assertNotIn("Produto reaproveitado", (b / "processo.md").read_text(encoding="utf-8"))

        self.cli("novo-produto", str(a), "Nome atualizado", "--produto-id", "candidato", "--force")

        env.pop("CENTRAL_COMPRAS_TESTE_CRASH_APOS", None)
        retomada = subprocess.run(
            [sys.executable, "scripts/central_compras.py", *args],
            cwd=self.root, env=env, capture_output=True, text=True,
        )
        self.assertEqual(retomada.returncode, 0, retomada.stderr)

        texto = (b / "processo.md").read_text(encoding="utf-8")
        self.assertIn(
            "Produto reaproveitado: candidato", texto,
            "nome congelado na 1a tentativa deveria ter sido usado",
        )
        self.assertNotIn(
            "Produto reaproveitado: Nome atualizado", texto,
            "retomada usou o nome ATUAL da ficha em vez do nome congelado na 1a tentativa",
        )


class QuartaRevisaoIndependenteFrente5Test(ambiente.RepoTestCase):
    """Regressao dos 4 achados da 4a revisao independente (Astra) sobre o
    commit `f2d5cd1` - cada teste aqui reproduziu uma falha real contra
    aquele codigo antes da correcao (scripts em
    `astra_review_f2d5cd1.py`/`astra_review_f2d5cd1_details.py`). Ver
    STATUS.md e docs/como-conferir-auditoria.md.

    A raiz comum dos achados 1 e 3: `_participacao_invalida`/
    `participacao_vazia` tratavam "tem conteudo, mas nao e um mapa YAML
    utilizavel" como sinonimo de "arquivo vazio, seguro recuperar do
    legado" - uma lista com dado real e um mapa com identidade trocada sao
    conteudo, nunca ausencia. `_classificar_participacao` agora e o UNICO
    ponto que decide isso, usado por `read_participation` E
    `migrate_products`."""

    def test_identidade_divergente_nao_reabilita_descartado_sem_legado(self):
        """Achado 1 (sem legado concorrente): so alterar `produto_id` na
        participacao ja gravada nao pode reabilitar um candidato descartado
        - nem elegivel no ranking, nem some do erro de validacao, e
        `project_discarded_candidate_ids` tambem para de contar como
        descartado (nunca simultaneamente elegivel E descartado)."""
        a = self.project()
        self.product(a)
        self.quote(a, "candidato", "--fonte", "manual")
        self.cli("descartar", "--produto-id", "candidato", "--projeto", str(a), "--porque", "nao atende")
        self.assertEqual(cc.compute_ranking(a)[0], [])

        path = cc.participation_path(a, "candidato")
        dados = cc.read_yaml(path, {})
        dados["produto_id"] = "outro-produto"
        cc.write_yaml(path, dados)

        elegiveis, _ = cc.compute_ranking(a)
        self.assertEqual([item.produto_id for item in elegiveis], [])
        self.assertNotIn("candidato", cc.project_discarded_candidate_ids(a))
        self.assertNotIn("candidato", cc.project_candidate_ids(a))
        errors, _ = cc.validation_report(a)
        self.assertTrue(
            any("candidato" in erro and "invalido" in erro for erro in errors),
            f"validacao nao apontou a participacao invalida: {errors}",
        )

    def test_identidade_divergente_nao_reverte_para_legado_mais_antigo(self):
        """Achado 1 (com legado concorrente): mesmo quando a FICHA ainda tem
        um estado legado mais antigo (`pesquisando`) gravado antes do
        descarte, uma participacao com identidade incoerente nao pode cair
        de volta para esse legado - fabricaria reabilitacao por cima de um
        descarte real e mais recente."""
        a = self.project()
        self.product(a)
        self.quote(a, "candidato", "--fonte", "manual")
        ficha = cc.find_product_path("candidato")
        original = cc.read_yaml(ficha, {})
        original.update(projeto=a.name, estado="pesquisando", requisitos_atendidos={"uso": True})
        cc.write_yaml(ficha, original)
        self.cli("descartar", "--produto-id", "candidato", "--projeto", str(a), "--porque", "descarte mais recente")

        path = cc.participation_path(a, "candidato")
        dados = cc.read_yaml(path, {})
        dados["produto_id"] = "outro-produto"
        cc.write_yaml(path, dados)

        elegiveis, _ = cc.compute_ranking(a)
        self.assertEqual([item.produto_id for item in elegiveis], [])
        self.assertEqual(cc.read_participation(a, "candidato")["estado"], cc.ESTADO_PARTICIPACAO_INVALIDA)

    def _legado(self, project, pid):
        path = cc.product_dir("fone", pid) / "produto.yaml"
        cc.write_yaml(path, dict(
            id=pid, categoria="fone", nome=pid, marca="Marca", projeto=project.name,
            estado="pesquisando", preco_teto=100, requisitos_atendidos={"uso": True},
        ))
        return path

    def test_campos_opcionais_com_tipo_invalido_nao_autorizam_limpar_legado(self):
        """Achado 2: `_participacao_invalida` so checava identidade e
        estado - `requisitos_atendidos` como lista (quebraria `.items()` em
        `gate_eliminations`), `preco_teto` como texto e `preco_alvo` `NaN`
        passavam no contrato minimo e autorizavam `migrar-produtos` a apagar
        a ficha legada por cima de dado inutilizavel."""
        a = self.project()
        casos = [
            ("requisitos_atendidos", ["uso"]),
            ("preco_teto", "barato"),
            ("preco_alvo", float("nan")),
        ]
        for indice, (campo, valor) in enumerate(casos):
            with self.subTest(campo=campo):
                pid = f"legado-{indice}"
                ficha = self._legado(a, pid)
                dados = cc.default_participation(pid)
                dados[campo] = valor
                path = cc.participation_path(a, pid)
                cc.write_yaml(path, dados)
                before = (ficha.read_bytes(), path.read_bytes())

                with self.assertRaises(SystemExit):
                    self.cli("migrar-produtos", "--aplicar")

                self.assertEqual(
                    (ficha.read_bytes(), path.read_bytes()), before,
                    f"{campo} invalido passou no contrato minimo e autorizou apagar o legado",
                )

    def test_requisitos_lista_nao_derruba_gate_eliminations(self):
        """Efeito colateral do achado 2 que nao era so 'aceita dado ruim':
        `(product.get('requisitos_atendidos') or {}).items()` em
        `gate_eliminations` quebraria com `AttributeError` se o campo fosse
        uma lista nao-vazia. Validar o tipo em `read_participation` evita
        que esse dado chegue ali."""
        a = self.project()
        self.product(a)
        path = cc.participation_path(a, "candidato")
        dados = cc.read_yaml(path, {})
        dados["requisitos_atendidos"] = ["uso"]
        cc.write_yaml(path, dados)
        self.quote(a, "candidato", "--fonte", "manual")

        elegiveis, cortados = cc.compute_ranking(a)
        self.assertEqual(elegiveis, [])
        self.assertEqual([item.produto_id for item in cortados], ["candidato"])

    def test_lista_com_dados_nao_e_arquivo_vazio_para_migracao(self):
        """Achado 3: `participacao_vazia = not (isinstance(dados, dict) and
        bool(dados))` tratava QUALQUER conteudo nao-dicionario, mesmo uma
        lista YAML com estado e motivo de descarte reais, como "arquivo sem
        dado" - a migracao recuperava do legado por cima de evidencia de
        verdade, silenciosamente."""
        a = self.project()
        ficha = self._legado(a, "legado")
        path = cc.participation_path(a, "legado")
        cc.write_yaml(path, [{"estado": "descartado", "descartado_porque": "EVIDENCIA_NOVA_A_PRESERVAR"}])
        before = (ficha.read_bytes(), path.read_bytes())

        with self.assertRaises(SystemExit):
            self.cli("migrar-produtos", "--aplicar")

        self.assertEqual(
            (ficha.read_bytes(), path.read_bytes()), before,
            "Lista nao vazia foi sobrescrita como se nao contivesse dados; evidencia desapareceu",
        )

    def test_arquivo_realmente_vazio_continua_recuperando_do_legado(self):
        """Controle: a recuperacao de arquivo vazio de verdade (0 bytes),
        corrigida na 2a revisao independente, continua funcionando - a
        distincao nova (achado 3) e so entre "sem dado nenhum" e "tem
        conteudo, mesmo que nao seja mapa", nunca uma regressao da recuperacao
        ja validada."""
        a = self.project()
        ficha = self._legado(a, "legado")
        path = cc.participation_path(a, "legado")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

        self.cli("migrar-produtos", "--aplicar")

        self.assertEqual(cc.read_participation(a, "legado")["estado"], "pesquisando")
        self.assertNotIn("estado", cc.read_yaml(ficha, {}))

    def test_motivo_invalido_nunca_vaza_para_disco(self):
        """`read_participation` anexa `_motivo_invalido` (diagnostico interno)
        ao dict devolvido para participacao invalida - esse campo nunca pode
        ser persistido. `write_participation` (unico lugar que efetivamente
        grava um arquivo de participacao) filtra qualquer campo com prefixo
        `_` antes de escrever, defesa em profundidade independente de quem
        chama (mesmo um chamador hipotetico que nao passasse por
        `_recusar_se_participacao_invalida`)."""
        a = self.project()
        self.product(a)
        path = cc.participation_path(a, "candidato")
        dados = cc.default_participation("candidato")
        dados.update(estado="descartado", descartado_porque="motivo", _motivo_invalido="NUNCA_GRAVAR")
        cc.write_participation(a, "candidato", dados)
        self.assertNotIn("_motivo_invalido", cc.read_yaml(path, {}))

    def test_write_participation_recusa_estado_sintetico(self):
        """Defesa em profundidade: `write_participation` nunca aceita o
        estado sintetico `invalido` como dado persistente, mesmo chamada
        direto (sem passar pelos comandos que ja recusam antes)."""
        a = self.project()
        self.product(a)
        dados = cc.default_participation("candidato")
        dados["estado"] = cc.ESTADO_PARTICIPACAO_INVALIDA
        with self.assertRaises(SystemExit):
            cc.write_participation(a, "candidato", dados)


class QuintaRevisaoIndependenteFrente5Test(ambiente.RepoTestCase):
    """Regressao dos 2 achados da 5a revisao independente (Astra) sobre o
    commit `70c3df8` - cada teste aqui reproduziu uma falha real contra
    aquele codigo antes da correcao (scripts em
    `astra_review_70c3df8.py`/`astra_review_70c3df8_details.py`). Ver
    STATUS.md e docs/como-conferir-auditoria.md.

    Raiz comum: a correcao da 4a revisao criou um dict SINTETICO (so
    defaults + estado `invalido`) para os CONSUMIDORES de leitura
    (`gate_eliminations`, `validation_report`) saberem "nao decido
    sozinho" sobre participacao com conteudo incoerente. Mas dois outros
    lugares tambem chamavam `read_participation` e tratavam o resultado
    como se fosse DADO REAL a mutar/preservar: os comandos que alteram
    estado (`descartar`/`aguardar-preco`) e o snapshot de uma decisao."""

    def _quebrada(self, project, pid="candidato"):
        """Participacao com identidade divergente (invalida) mas CONTEUDO
        real reconhecivel nos demais campos - preco-alvo/teto, requisito
        negativo e um campo desconhecido, todos com marcador exclusivo pra
        provar se sobreviveram."""
        self.product(project, pid)
        path = cc.participation_path(project, pid)
        dados = cc.read_yaml(path, {})
        dados.update(
            produto_id="IDENTIDADE_DIVERGENTE", preco_alvo=75, preco_teto=100,
            requisitos_atendidos={"uso": False}, evidencia_extra="EVIDENCIA_REAL_EXCLUSIVA",
        )
        cc.write_yaml(path, dados)
        return path, dados

    def test_descartar_e_aguardar_preco_recusam_sobre_participacao_invalida(self):
        """Achado 1: `descartar`/`aguardar-preco` liam a participacao via
        `read_participation` (dict sintetico, so defaults + estado
        `invalido`), mudavam so o campo de estado, e regravavam o resto por
        cima com `write_participation` - apagando preco-alvo/teto,
        requisito e o campo desconhecido que so existiam no arquivo real.
        Corrigido: os dois comandos recusam ANTES de qualquer escrita."""
        for comando in ["descartar", "aguardar-preco"]:
            with self.subTest(comando=comando):
                a = self.project(comando)
                path, _ = self._quebrada(a, comando)
                before = path.read_bytes()

                with self.assertRaises(SystemExit):
                    self.cli(comando, "--produto-id", comando, "--projeto", str(a),
                              "--porque", "nova orientacao de estado")

                self.assertEqual(
                    path.read_bytes(), before,
                    f"{comando}: recusou mas alterou o arquivo de participacao mesmo assim",
                )

    def test_aguardar_preco_nao_apaga_requisito_negativo_e_nao_reabilita(self):
        """Efeito concreto do achado 1: sem a recusa, `aguardar-preco`
        perdia `requisitos_atendidos={'uso': False}` e `preco_teto=100` -
        uma oferta de R$200 (acima do teto, com requisito nao atendido)
        passava a ELEGIVEL depois do comando, mesmo ele so tendo pedido
        para esperar preco melhor."""
        a = self.project()
        self._quebrada(a)
        self.quote(a, "candidato", "--fonte", "manual")
        self.assertEqual(cc.compute_ranking(a)[0], [])

        with self.assertRaises(SystemExit):
            self.cli("aguardar-preco", "--produto-id", "candidato", "--projeto", str(a),
                      "--porque", "esperar oferta")

        self.assertEqual(
            cc.compute_ranking(a)[0], [],
            "aguardar-preco perdeu requisito uso=false e teto=100; oferta de 200 virou elegivel",
        )

    def test_participacao_valida_continua_preservando_campos_ao_alterar_estado(self):
        """Controle: a recusa e SO para participacao invalida - uma
        participacao valida (identidade e estado corretos) continua
        aceitando `aguardar-preco`/`descartar` normalmente, preservando
        preco-alvo/teto, requisitos e campo desconhecido nao mexidos pelo
        comando."""
        a = self.project()
        self.product(a)
        path = cc.participation_path(a, "candidato")
        dados = cc.read_yaml(path, {})
        dados.update(preco_alvo=75, preco_teto=100, requisitos_atendidos={"uso": False},
                     evidencia_extra="PRESERVAR")
        cc.write_yaml(path, dados)

        self.cli("aguardar-preco", "--produto-id", "candidato", "--projeto", str(a), "--porque", "esperar")

        after = cc.read_yaml(path, {})
        for key in ["preco_alvo", "preco_teto", "requisitos_atendidos", "evidencia_extra"]:
            self.assertEqual(after[key], dados[key], f"participacao valida perdeu {key} ao alterar estado")
        self.assertEqual(after["estado"], "aguardando_preco")

    def test_snapshot_preserva_arquivo_bruto_de_concorrente_com_participacao_invalida(self):
        """Achado 2: o snapshot de uma decisao gravava, para CADA produto do
        projeto (inclusive perdedores), o resultado INTERPRETADO de
        `read_participation` - para um concorrente com participacao
        invalida isso e o dict SINTETICO (defaults + estado `invalido`),
        nunca o conteudo real do arquivo. `auditar-decisoes --strict`
        passava, mas a decisao deixava de ser reconstruivel: nenhum arquivo
        congelado preservava preco-alvo/teto, requisito ou o campo
        desconhecido do concorrente perdedor."""
        a = self.project()
        _, dados_concorrente = self._quebrada(a, "concorrente")
        self.quote(a, "concorrente", "--fonte", "manual")
        self.product(a, "escolhido")
        self.quote(a, "escolhido", "--fonte", "manual")

        self.cli("decidir", str(a), "--produto-id", "escolhido", "--porque", "melhor candidato valido",
                  "--perdedores", "concorrente: participacao invalida", "--comprado")

        snapshot = next((a / "snapshots").iterdir())
        congelado = snapshot / "participacoes" / "concorrente.yaml"
        self.assertIn(
            "EVIDENCIA_REAL_EXCLUSIVA", congelado.read_text(encoding="utf-8"),
            "Snapshot nao preserva o conteudo bruto da participacao invalida do concorrente",
        )
        self.assertEqual(
            cc.read_yaml(congelado, {}).get("preco_alvo"), dados_concorrente["preco_alvo"],
            "preco_alvo real do concorrente nao sobreviveu no snapshot",
        )
        self.cli("auditar-decisoes", "--strict")

    def test_snapshot_participacao_invalida_imutavel_apos_alteracao_posterior(self):
        """Controle: a evidencia bruta congelada do concorrente invalido nao
        muda se o arquivo original for alterado DEPOIS da decisao fechada -
        mesmo principio ja valido para participacao valida."""
        a = self.project()
        self._quebrada(a, "concorrente")
        self.quote(a, "concorrente", "--fonte", "manual")
        self.product(a, "escolhido")
        self.quote(a, "escolhido", "--fonte", "manual")
        self.cli("decidir", str(a), "--produto-id", "escolhido", "--porque", "melhor candidato valido",
                  "--perdedores", "concorrente: participacao invalida", "--comprado")
        snapshot = next((a / "snapshots").iterdir())
        congelado_antes = (snapshot / "participacoes" / "concorrente.yaml").read_bytes()

        cc.write_yaml(cc.participation_path(a, "concorrente"), {"anotacao": "MUDOU_DEPOIS"})

        self.assertEqual((snapshot / "participacoes" / "concorrente.yaml").read_bytes(), congelado_antes)


class SextaRevisaoIndependenteFrente5Test(ambiente.RepoTestCase):
    """Regressao do achado da 6a revisao independente (Astra) sobre o
    commit `88ba7c2` - reproduzido contra aquele codigo antes da correcao
    (script `astra_review_88ba7c2.py`). Ver STATUS.md e
    docs/como-conferir-auditoria.md.

    Raiz: a correcao da 5a revisao passou a congelar o arquivo BRUTO da
    participacao invalida no snapshot, mas o loop que decide QUAIS
    produto_id entram nesse inventario usava `project_product_ids`
    (cotacoes + `project_candidate_ids` + `project_discarded_candidate_ids`).
    Um participante com participacao invalida e SEM NENHUMA cotacao fica de
    fora dos dois conjuntos de candidatos DE PROPOSITO (nao e "ativo" nem
    "descartado" confirmado - ver `project_candidate_ids`), e portanto
    tambem de `project_product_ids` - o loop nunca alcancava nem a ficha
    nem a participacao desse produto. `auditar-decisoes --strict` passava
    sem preservar NENHUM arquivo daquele participante."""

    def _quebrada_sem_cotacao(self, project, pid="sem-cotacao", invalida=True):
        self.product(project, pid)
        path = cc.participation_path(project, pid)
        dados = cc.read_yaml(path, {})
        dados.update(preco_teto=100, requisitos_atendidos={"uso": False},
                     evidencia_extra="EVIDENCIA_EXCLUSIVA_SEM_COTACAO")
        if invalida:
            dados["produto_id"] = "IDENTIDADE_DIVERGENTE"
        cc.write_yaml(path, dados)
        return path, dados

    def _decidir_com_terceiro(self, project, pid_terceiro):
        self.product(project, "escolhido")
        self.quote(project, "escolhido", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "escolhido",
                  "--porque", "unico candidato com cotacao manual",
                  "--sem-perdedores", "--comprado")
        return next((project / "snapshots").iterdir())

    def test_participante_invalido_sem_cotacao_preserva_evidencia_bruta(self):
        """Achado: sem nenhuma cotacao, o participante invalido sumia por
        completo da evidencia congelada - nem a ficha nem a participacao
        apareciam em nenhum arquivo do snapshot."""
        a = self.project()
        path, dados = self._quebrada_sem_cotacao(a)
        original = path.read_bytes()

        snapshot = self._decidir_com_terceiro(a, "sem-cotacao")

        congelado = snapshot / "participacoes" / "sem-cotacao.yaml"
        self.assertTrue(congelado.exists(), "Participacao invalida sem cotacao nao foi congelada no snapshot")
        self.assertEqual(
            congelado.read_bytes(), original,
            "Conteudo bruto congelado diverge do arquivo original",
        )
        ficha_congelada = snapshot / "produtos" / "sem-cotacao.yaml"
        self.assertTrue(ficha_congelada.exists(), "Ficha do participante sem cotacao nao foi congelada no snapshot")
        self.assertEqual(path.read_bytes(), original, "Arquivo original foi alterado pela captura do snapshot")

    def test_participante_invalido_sem_cotacao_entra_no_manifesto(self):
        """O arquivo preservado precisa estar listado (com hash) no
        `manifesto.json` - senao a evidencia existe mas nao e reconhecida
        como parte formal do que foi congelado."""
        a = self.project()
        self._quebrada_sem_cotacao(a)

        snapshot = self._decidir_com_terceiro(a, "sem-cotacao")

        manifesto = cc.read_yaml(snapshot / "manifesto.json", {})
        self.assertIn("participacoes/sem-cotacao.yaml", manifesto)
        self.assertIn("produtos/sem-cotacao.yaml", manifesto)
        congelado = snapshot / "participacoes" / "sem-cotacao.yaml"
        self.assertEqual(
            manifesto["participacoes/sem-cotacao.yaml"],
            hashlib.sha256(congelado.read_bytes()).hexdigest(),
        )
        self.cli("auditar-decisoes", "--strict")

    def test_participante_invalido_sem_cotacao_imutavel_apos_alteracao_posterior(self):
        """A evidencia bruta congelada nao pode mudar se o arquivo original
        for alterado DEPOIS da decisao fechada - mesmo principio ja valido
        para participacao invalida COM cotacao (revisao anterior)."""
        a = self.project()
        self._quebrada_sem_cotacao(a)
        snapshot = self._decidir_com_terceiro(a, "sem-cotacao")
        congelado_antes = (snapshot / "participacoes" / "sem-cotacao.yaml").read_bytes()

        cc.write_yaml(cc.participation_path(a, "sem-cotacao"), {"anotacao": "MUDOU_DEPOIS"})

        self.assertEqual((snapshot / "participacoes" / "sem-cotacao.yaml").read_bytes(), congelado_antes)

    def test_incluir_para_evidencia_nao_reabilita_nem_pontua_nem_descarta(self):
        """A distincao pedida pela Astra: `project_evidence_participant_ids`
        e um SUPERSET so pra fins de captura de snapshot - nunca pode
        vazar para ranking, regra de parada ou listagem de candidatos.
        Participante invalido sem cotacao continua fora de elegiveis,
        cortados, `project_candidate_ids`, `project_discarded_candidate_ids`
        e `sem_cotacao_candidates`, mesmo aparecendo em
        `project_evidence_participant_ids`."""
        a = self.project()
        self._quebrada_sem_cotacao(a)

        self.assertIn("sem-cotacao", cc.project_evidence_participant_ids(a))
        self.assertNotIn("sem-cotacao", cc.project_candidate_ids(a))
        self.assertNotIn("sem-cotacao", cc.project_discarded_candidate_ids(a))
        self.assertNotIn("sem-cotacao", cc.project_product_ids(a))
        elegiveis, cortados = cc.compute_ranking(a)
        self.assertEqual([i.produto_id for i in elegiveis], [])
        self.assertEqual([i.produto_id for i in cortados], [])
        sem_cotacao = cc.sem_cotacao_candidates(a, "fone", [])
        self.assertEqual([i.produto_id for i in sem_cotacao], [])

        self._decidir_com_terceiro(a, "sem-cotacao")

        # "escolhido" legitimamente entra em elegiveis (tem cotacao manual e
        # foi o proprio decidido) - o que importa e "sem-cotacao" nunca
        # aparecer em nenhuma das duas listas, nem depois da decisao.
        elegiveis, cortados = cc.compute_ranking(a)
        self.assertNotIn("sem-cotacao", [i.produto_id for i in elegiveis])
        self.assertNotIn("sem-cotacao", [i.produto_id for i in cortados])

    def test_participante_valido_sem_cotacao_continua_preservado(self):
        """Controle: uma participacao VALIDA sem cotacao ja era preservada
        antes desta correcao (esta no formato novo com arquivo proprio,
        `project_candidate_ids` ja a inclui) - a mudanca desta rodada nao
        pode regredir esse caso."""
        a = self.project()
        path, dados = self._quebrada_sem_cotacao(a, invalida=False)

        snapshot = self._decidir_com_terceiro(a, "sem-cotacao")

        congelado = snapshot / "participacoes" / "sem-cotacao.yaml"
        self.assertTrue(congelado.exists())
        self.assertEqual(
            cc.read_yaml(congelado, {})["evidencia_extra"], dados["evidencia_extra"],
        )


if __name__ == "__main__":
    unittest.main()
