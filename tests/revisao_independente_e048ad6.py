"""Revisao adversarial independente do commit `e048ad6` (frente 6, correcao
do achado da 4a revisao: `_veredito_existente_para` passou a localizar o
veredito de uma decisao pela IDENTIDADE gravada no conteudo - `Projeto`/
`Produto ID` - em vez do nome do arquivo).

Nao faz parte da suite oficial de proposito (nome do arquivo nao comeca com
`test_`, entao `python -m unittest discover -s tests` NAO coleta isto - os
achados aqui ainda nao foram corrigidos em producao, e a suite oficial tem
que continuar 100% verde). Rodar manualmente com:

    python -m unittest tests.revisao_independente_e048ad6 -v

Guardado em caminho persistente do repositorio (nao em %TEMP%) a pedido
explicito desta rodada de revisao. Ver STATUS.md e a secao 6 de
docs/plano-pendencias-auditoria-2026-09-06.md para o relato completo.
"""

import datetime as dt
import unittest
from unittest.mock import patch

import ambiente
from scripts import central_compras as cc


class IdentidadeAtravesDeDecisaoIntermediariaTest(ambiente.RepoTestCase):
    """Foco 1 do roteiro de revisao: projeto+produto distingue o veredito da
    decisao ATUAL de uma decisao ANTERIOR? Exercita decidir A, decidir B,
    decidir A de novo (o mesmo projeto, produto A reconsiderado depois de
    uma decisao B ter acontecido no meio do caminho - cenario real: o
    Josemar decide A, muda de ideia e decide B, B nao funciona, ele volta a
    decidir A de verdade, com uma cotacao NOVA, dias/semanas depois)."""

    def test_redecidir_produto_apos_decisao_intermediaria_complementa_veredito_antigo_com_preco_obsoleto(self):
        dia1 = "2026-01-01"
        dia2 = "2026-01-02"
        dia3 = "2026-01-20"

        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            self.product(project, "candidato-a")
            self.product(project, "candidato-b")
            self.quote(project, "candidato-a", "--fonte", "manual")
            self.cli("decidir", str(project), "--produto-id", "candidato-a",
                      "--porque", "primeira escolha", "--sem-perdedores")

        veredito_a = next(p for p in cc.VEREDITOS.glob("*.md")
                           if cc.extract_bullet(p.read_text(encoding="utf-8"), "Produto ID") == "candidato-a")
        preco_original = cc.extract_bullet(veredito_a.read_text(encoding="utf-8"), "Valor pago")
        self.assertEqual(preco_original, cc.brl(200.0))

        # Decisao intermediaria: troca para B (decisao.md do projeto passa a
        # apontar para B; A fica com veredito orfao, mas ainda EXISTENTE).
        with patch.object(cc, "today", return_value=dia2):
            self.quote(project, "candidato-b", "--fonte", "manual")
            self.cli("decidir", str(project), "--produto-id", "candidato-b", "--porque",
                      "troquei de ideia", "--perdedores", "candidato-a: desisti por enquanto")

        # Semanas depois: reconsiderou, decide A de NOVO - preco mudou desde
        # a 1a vez (cenario real: cotacao antiga venceria, tem que recotar).
        with patch.object(cc, "today", return_value=dia3):
            self.quote(project, "candidato-a", "--fonte", "manual", "--preco", "999",
                       "--loja", "LojaNova")
            self.cli("decidir", str(project), "--produto-id", "candidato-a", "--porque",
                      "reconsiderei, escolhi A de novo com cotacao nova", "--comprado",
                      "--perdedores", "candidato-b: nao entregou")

        vereditos_a = [p for p in cc.VEREDITOS.glob("*.md")
                        if cc.extract_bullet(p.read_text(encoding="utf-8"), "Produto ID") == "candidato-a"]

        # ACHADO: nenhum veredito NOVO e criado para a redecisao - o mesmo
        # arquivo da 1a escolha (dia1) e reaproveitado/complementado, mesmo
        # havendo uma decisao B inteira no meio e uma cotacao NOVA (preco/
        # loja diferentes) na redecisao de A.
        self.assertEqual(len(vereditos_a), 1,
                          "identidade projeto+produto encontrou o veredito certo (nao duplicou)")
        self.assertEqual(vereditos_a[0], veredito_a)

        texto_final = veredito_a.read_text(encoding="utf-8")
        # "Data da compra" e complementada corretamente (dia3, a data real).
        self.assertEqual(cc.extract_bullet(texto_final, "Data da compra"), dia3)
        # ACHADO REAL: "Valor pago"/"Vendedor" continuam com o preco/loja da
        # 1a escolha (dia1, R$200/Amazon) - NUNCA atualizados para a cotacao
        # que efetivamente foi decidida e paga em dia3 (R$999/LojaNova).
        # `create_verdict` so complementa "Data da compra" quando o arquivo
        # ja existe; todo o resto (Valor pago, Vendedor, Loja) fica
        # congelado com os dados da PRIMEIRA vez que este produto+projeto
        # foi decidido, nao da decisao que de fato foi paga.
        self.assertEqual(
            cc.extract_bullet(texto_final, "Valor pago"), preco_original,
            "Valor pago ficou com o preco OBSOLETO da 1a decisao (dia1), nao o preco real pago (dia3)",
        )
        self.assertNotEqual(
            cc.extract_bullet(texto_final, "Valor pago"), cc.brl(999.0),
            "confirma que o preco real da compra (R$999) NUNCA chega ao veredito",
        )

    def test_controle_decidir_produto_diferente_no_meio_nao_confunde_identidade(self):
        """Controle: o achado acima NAO e por causa de A/B se confundirem -
        os vereditos de A e B continuam distintos e corretos o tempo todo."""
        project = self.project()
        self.product(project, "candidato-a")
        self.product(project, "candidato-b")
        self.quote(project, "candidato-a", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato-a",
                  "--porque", "unico ate agora", "--sem-perdedores")
        self.quote(project, "candidato-b", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato-b", "--porque",
                  "troquei", "--perdedores", "candidato-a: motivo")

        veredito_a = next(p for p in cc.VEREDITOS.glob("*.md")
                           if cc.extract_bullet(p.read_text(encoding="utf-8"), "Produto ID") == "candidato-a")
        veredito_b = next(p for p in cc.VEREDITOS.glob("*.md")
                           if cc.extract_bullet(p.read_text(encoding="utf-8"), "Produto ID") == "candidato-b")
        self.assertNotEqual(veredito_a, veredito_b)
        self.assertEqual(len(list(cc.VEREDITOS.glob("*.md"))), 2)


class ForceVereditoRegressaoTest(ambiente.RepoTestCase):
    """Foco 4 do roteiro: --force-veredito em dia diferente agora reseta o
    MESMO veredito encontrado por identidade, em vez de criar outro arquivo
    (comportamento antigo). Isso significa que, se o veredito antigo ja
    tinha uma fase D+30/D+180 preenchida e EXPORTADA para a base de
    conhecimento (`aprender-veredito`), o --force-veredito agora DESTROI
    esse historico (que antes, criando um 2o arquivo, ficava intacto no
    arquivo original) - e reabre a porta para exportar a MESMA licao duas
    vezes, porque o marcador "ja exportado" tambem e apagado."""

    def test_force_veredito_em_dia_diferente_apaga_d30_ja_exportado_e_permite_duplicar_licao(self):
        dia1 = "2026-02-01"
        dia_entrega = "2026-02-03"
        dia_inicio_uso = "2026-02-05"
        dia_d30 = "2026-03-10"
        dia_force = "2026-06-01"  # meses depois - force-veredito por outro motivo

        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            self.product(project, "candidato")
            self.quote(project, "candidato", "--fonte", "manual")
            self.cli("decidir", str(project), "--produto-id", "candidato",
                      "--porque", "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))

        with patch.object(cc, "today", return_value=dia_entrega):
            self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        with patch.object(cc, "today", return_value=dia_inicio_uso):
            self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")

        with patch.object(cc, "today", return_value=dia_d30):
            self.cli("preencher-veredito", str(veredito), "--fase", "d30",
                      "--nota-arrependimento", "9", "--compraria-de-novo", "sim",
                      "--resumo", "Otimo produto, avaliacao real de 30 dias de uso.")
            self.cli("aprender-veredito", str(veredito), "--fase", "d30",
                      "--licao", "Marca A entrega no prazo e o produto funciona bem.")

        texto_com_d30 = veredito.read_text(encoding="utf-8")
        self.assertIn("Aprendizado exportado D+30", texto_com_d30)
        self.assertIn("Otimo produto, avaliacao real de 30 dias de uso.", texto_com_d30)
        licoes_apos_1a_exportacao = (cc.BASE / "licoes.md").read_text(encoding="utf-8")
        self.assertEqual(
            licoes_apos_1a_exportacao.count("Marca A entrega no prazo e o produto funciona bem."), 1,
        )

        # Meses depois, --force-veredito por outro motivo qualquer (ex.: o
        # Josemar quer refazer o veredito do zero por engano ou por outro
        # produto reaproveitando o mesmo produto_id neste projeto). Sem
        # `--comprado` aqui de proposito: com `--comprado` junto, a checagem
        # de cronologia do achado 4 compara a nova data contra o conteudo
        # AINDA NAO substituido do veredito antigo (entrega/inicio de uso
        # registrados na 1a rodada) e recusa antes mesmo do reset acontecer -
        # ver `test_force_veredito_com_comprado_e_bloqueado_pela_cronologia_do_veredito_que_esta_prestes_a_apagar`
        # abaixo, achado separado sobre essa interacao.
        with patch.object(cc, "today", return_value=dia_force):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "refazendo do zero", "--sem-perdedores", "--force-veredito")

        # Ainda e o MESMO arquivo (identidade), nao um novo.
        vereditos = list(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(len(vereditos), 1)
        self.assertEqual(vereditos[0], veredito)

        texto_apos_force = veredito.read_text(encoding="utf-8")
        # ACHADO: a avaliacao real de D+30 (nota, resumo, marcador de
        # exportado) foi APAGADA - historico honesto do Josemar sobre o
        # produto, perdido sem aviso nenhum.
        self.assertNotIn("Aprendizado exportado D+30", texto_apos_force,
                          "o marcador de exportacao ja nao existe mais - a evidencia de que a licao "
                          "ja tinha sido exportada foi destruida pelo --force-veredito")
        self.assertNotIn("Otimo produto, avaliacao real de 30 dias de uso.", texto_apos_force,
                          "o resumo real do D+30 foi perdido")

        # Consequencia: como o marcador sumiu, um novo preencher+aprender
        # para a MESMA fase (d30) nao e barrado como reexportacao - grava
        # uma 2a linha em licoes.md para o que e, na pratica, a MESMA
        # avaliacao/decisao original, sem nenhum aviso de duplicidade.
        with patch.object(cc, "today", return_value=dia_force):
            self.cli("registrar-evento", str(veredito), "--evento", "entrega")
            self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")
            self.cli("preencher-veredito", str(veredito), "--fase", "d30",
                      "--nota-arrependimento", "9", "--compraria-de-novo", "sim",
                      "--resumo", "Otimo produto, avaliacao real de 30 dias de uso.")
            self.cli("aprender-veredito", str(veredito), "--fase", "d30",
                      "--licao", "Marca A entrega no prazo e o produto funciona bem.")

        licoes_final = (cc.BASE / "licoes.md").read_text(encoding="utf-8")
        self.assertEqual(
            licoes_final.count("Marca A entrega no prazo e o produto funciona bem."), 2,
            "ACHADO: a mesma licao foi exportada 2 vezes para a base de conhecimento, sem aviso, "
            "porque --force-veredito apagou o marcador que preveniria a reexportacao",
        )

    def test_controle_force_veredito_no_mesmo_dia_ja_tinha_esse_comportamento_antes_da_correcao(self):
        """Controle: o wipe de --force-veredito em si NAO e novo - no MESMO
        dia ele sempre reescreveu o arquivo inteiro. O achado acima e
        especificamente sobre o RAIO DE ALCANCE ter aumentado para
        qualquer dia (por causa de `_veredito_existente_para`), nao sobre
        force-veredito ter passado a apagar coisas que antes preservava no
        mesmo dia."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato",
                  "--porque", "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        cc.atomic_write_text(
            veredito,
            cc.replace_or_append_bullet(veredito.read_text(encoding="utf-8"), "D+30 resumo", "MARCADOR"),
        )
        self.cli("decidir", str(project), "--produto-id", "candidato",
                  "--porque", "de novo", "--sem-perdedores", "--force-veredito")
        self.assertNotIn("MARCADOR", veredito.read_text(encoding="utf-8"))

    def test_force_veredito_com_comprado_e_bloqueado_pela_cronologia_do_veredito_que_esta_prestes_a_apagar(self):
        """Observacao separada (nao necessariamente um bug, mas uma
        interacao nao coberta por teste nenhum ate agora): `decidir
        --comprado --force-veredito` roda a checagem de cronologia do
        achado 4 ANTES do reset acontecer, comparando a nova `Data da
        compra` contra entrega/inicio_uso do veredito ANTIGO - o mesmo
        conteudo que `--force-veredito` esta prestes a descartar. O efeito
        e recusar um reset legitimo (`--force-veredito` serve exatamente
        para descartar dados antigos considerados errados) por causa dos
        proprios dados que vao ser descartados."""
        dia1 = "2026-02-01"
        dia_entrega = "2026-02-03"
        dia_inicio_uso = "2026-02-05"
        dia_force = "2026-06-01"

        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            self.product(project, "candidato")
            self.quote(project, "candidato", "--fonte", "manual")
            self.cli("decidir", str(project), "--produto-id", "candidato",
                      "--porque", "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        with patch.object(cc, "today", return_value=dia_entrega):
            self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        with patch.object(cc, "today", return_value=dia_inicio_uso):
            self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")

        with patch.object(cc, "today", return_value=dia_force):
            with self.assertRaisesRegex(SystemExit, "posterior"):
                self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                          "refazendo do zero", "--sem-perdedores", "--comprado", "--force-veredito")
        # Nada foi alterado pela recusa - mas o reset que o Josemar pediu
        # tambem nao aconteceu, mesmo passando --force-veredito. (Foco 6 do
        # roteiro: recusa nao pode deixar journal novo nem tocar em outros
        # arquivos do projeto.)
        self.assertIn("Data de entrega", veredito.read_text(encoding="utf-8"))
        self.assertFalse(cc.pending_operations([project]), "recusa nao pode deixar journal pendente")


class BuscaPorConteudoTest(ambiente.RepoTestCase):
    """Foco 5 do roteiro: `_veredito_existente_para` busca por CONTEUDO
    (bullets Projeto/Produto ID), nunca pelo nome do arquivo - exercita
    arquivo renomeado, identidade divergente e veredito standalone."""

    def _decidir(self, project, pid="candidato", extra=()):
        self.product(project, pid)
        self.quote(project, pid, "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", pid,
                  "--porque", "unico candidato", "--sem-perdedores", *extra)
        return next(p for p in cc.VEREDITOS.glob("*.md") if pid in p.name)

    def test_veredito_renomeado_manualmente_ainda_e_encontrado_por_identidade(self):
        """Controle POSITIVO: renomear o arquivo a mao (algo que o Josemar
        faz de vez em quando para organizar) nao quebra o complemento - a
        busca e por conteudo, nao pelo nome."""
        project = self.project()
        veredito = self._decidir(project)
        novo_nome = cc.VEREDITOS / "veredito-renomeado-a-mao.md"
        veredito.rename(novo_nome)

        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores", "--comprado")

        self.assertEqual(len(list(cc.VEREDITOS.glob("*.md"))), 1,
                          "renomear o arquivo nao pode fazer o sistema criar um 2o veredito")
        self.assertEqual(
            cc.extract_bullet(novo_nome.read_text(encoding="utf-8"), "Data da compra"), cc.today(),
        )

    def test_veredito_com_produto_id_divergente_do_conteudo_nao_e_confundido(self):
        """Um veredito cujo `Produto ID` no CONTEUDO nao bate com o produto
        desta decisao nunca pode ser usado, mesmo que o Projeto bata e o
        nome do arquivo pareca relacionado."""
        project = self.project()
        veredito_outro = self._decidir(project, pid="outro-produto")

        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--comprado",
                  "--perdedores", "outro-produto: motivo")

        vereditos = list(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(len(vereditos), 2, "produto_id diferente tem que gerar um veredito PROPRIO")
        veredito_candidato = next(p for p in vereditos if p != veredito_outro)
        self.assertEqual(
            cc.extract_bullet(veredito_candidato.read_text(encoding="utf-8"), "Produto ID"), "candidato",
        )
        self.assertEqual(
            cc.extract_bullet(veredito_outro.read_text(encoding="utf-8"), "Data da compra"), "",
            "veredito do OUTRO produto nao pode ter sido tocado",
        )

    def test_veredito_standalone_sem_produto_id_nunca_e_reaproveitado(self):
        """`novo-veredito` (caminho standalone, sem `Produto ID` gravado)
        nunca pode ser confundido com o veredito de uma decisao real, mesmo
        que o `Projeto` bata."""
        project = self.project()
        self.cli("novo-veredito", str(project))
        veredito_standalone = next(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(cc.extract_bullet(veredito_standalone.read_text(encoding="utf-8"), "Produto ID"), "")

        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores", "--comprado")

        vereditos = list(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(len(vereditos), 2, "decidir tem que criar um veredito PROPRIO, nunca usar o standalone")
        self.assertEqual(
            cc.extract_bullet(veredito_standalone.read_text(encoding="utf-8"), "Data da compra"), "",
            "o veredito standalone nao pode ter sido tocado por decidir",
        )

    def test_mensagem_de_ambiguidade_nomeia_os_arquivos_reais_para_resolucao_manual(self):
        """A mensagem de erro de ambiguidade precisa realmente permitir
        resolver o problema a mao - conferindo que ela cita os NOMES REAIS
        dos arquivos envolvidos, nao um texto generico."""
        project = self.project()
        veredito1 = self._decidir(project)
        veredito2 = cc.VEREDITOS / f"{cc.today()}-duplicado-{project.name}-candidato.md"
        veredito2.write_text(veredito1.read_text(encoding="utf-8"), encoding="utf-8")

        with self.assertRaises(SystemExit) as ctx:
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "unico candidato", "--sem-perdedores", "--comprado")

        mensagem = str(ctx.exception)
        self.assertIn(veredito1.name, mensagem)
        self.assertIn(veredito2.name, mensagem)


if __name__ == "__main__":
    unittest.main()
