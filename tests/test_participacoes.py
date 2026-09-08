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


if __name__ == "__main__":
    unittest.main()
