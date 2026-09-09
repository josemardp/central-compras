"""Frente 6: datas e vereditos.

Contrato (docs/plano-pendencias-auditoria-2026-09-06.md, secao 6): decisao,
compra/pagamento, entrega e inicio de uso sao FATOS DATADOS independentes.
`decidir` fecha so a escolha - cotacao manual e evidencia de uma oferta
conferida, nunca prova de pagamento, entrega ou uso. D+30/D+180 contam a
partir do INICIO DE USO explicitamente registrado (`registrar-evento`);
sem essa data, os lembretes ficam pendentes ("aguardando inicio de uso"),
nunca fabricados a partir de hoje/decisao/compra/entrega.

Cada evento (comprado, entrega, inicio_uso) e gravado uma unica vez - fato
datado nao e sobrescrito silenciosamente (principio 1 do
docs/como-conferir-auditoria.md).
"""

import datetime as dt
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import ambiente
from scripts import central_compras as cc

REPO = Path(__file__).resolve().parents[1]


class SeparacaoDeDatasTest(ambiente.RepoTestCase):
    """`decidir` nunca comprova pagamento, entrega ou uso - so a propria
    escolha. `--comprado` e a UNICA coisa que autoriza `Data da compra`."""

    def _decidir(self, project, pid="candidato", extra=()):
        self.product(project, pid)
        self.quote(project, pid, "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", pid,
                  "--porque", "unico candidato", "--sem-perdedores", *extra)
        return next(p for p in cc.VEREDITOS.glob("*.md") if pid in p.name)

    def test_decidir_sem_comprado_deixa_data_da_compra_em_branco(self):
        """Cotacao MANUAL (a mesma que antes disparava `Data da compra`
        sozinha) nao basta mais - decidir sem `--comprado` nunca afirma
        pagamento."""
        project = self.project()
        veredito = self._decidir(project)
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), "")

    def test_decidir_comprado_grava_data_da_compra_hoje(self):
        project = self.project()
        veredito = self._decidir(project, extra=["--comprado"])
        self.assertEqual(
            cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today()
        )

    def test_decidir_comprado_com_cotacao_web_ainda_grava_data_compra(self):
        """Prova que `Data da compra` agora depende de `--comprado`, nunca
        de `fonte == manual` (o acoplamento errado que causava o bug: uma
        cotacao web marcada comprada nao registrava data nenhuma antes)."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "web")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque", "unico",
                  "--sem-perdedores", "--permitir-web", "--comprado")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today())

    def test_decidir_comprado_com_data_compra_explicita(self):
        project = self.project()
        ontem = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        veredito = self._decidir(project, extra=["--comprado", "--data-compra", ontem])
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), ontem)

    def test_data_compra_sem_comprado_e_recusada(self):
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        with self.assertRaisesRegex(SystemExit, "--data-compra so faz sentido"):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque", "unico",
                      "--sem-perdedores", "--data-compra", cc.today())
        self.assertEqual(
            (project / "decisao.md").read_text(encoding="utf-8"), cc.render_template("decisao.md"),
            "recusa tem que vir ANTES de qualquer escrita - decisao.md nao pode ter sido tocado",
        )

    def test_data_compra_futura_e_recusada_pelo_parser(self):
        with self.assertRaises(SystemExit):
            self.cli("decidir", "qualquer", "--produto-id", "x", "--porque", "y",
                      "--comprado", "--data-compra", "2099-01-01")


class PrevistoAncoradoEmInicioDeUsoTest(ambiente.RepoTestCase):
    """D+30/D+180 previsto so existem depois do inicio de uso registrado -
    nunca fabricados a partir de hoje/decisao/compra na criacao do
    veredito."""

    def _decidir(self, project, pid="candidato", extra=()):
        self.product(project, pid)
        self.quote(project, pid, "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", pid,
                  "--porque", "unico candidato", "--sem-perdedores", *extra)
        return next(p for p in cc.VEREDITOS.glob("*.md") if pid in p.name)

    def test_veredito_criado_por_decidir_comeca_sem_previsto(self):
        project = self.project()
        veredito = self._decidir(project, extra=["--comprado"])
        texto = veredito.read_text(encoding="utf-8")
        self.assertEqual(cc.extract_bullet(texto, "Veredito D+30 previsto"), "")
        self.assertEqual(cc.extract_bullet(texto, "Veredito D+180 previsto"), "")

    def test_novo_veredito_standalone_tambem_comeca_sem_previsto(self):
        """Controle: `novo-veredito` (caminho fora de `decidir`) ja nao
        preenchia previsto antes desta correcao - continua assim, os dois
        caminhos de criacao ficam consistentes agora."""
        project = self.project()
        self.cli("novo-veredito", str(project))
        veredito = next(cc.VEREDITOS.glob("*.md"))
        texto = veredito.read_text(encoding="utf-8")
        self.assertEqual(cc.extract_bullet(texto, "Veredito D+30 previsto"), "")
        self.assertEqual(cc.extract_bullet(texto, "Veredito D+180 previsto"), "")

    def test_registrar_evento_inicio_uso_calcula_d30_e_d180(self):
        """Datas relativas ao dia real do teste (nunca literais fixas), pra
        nao quebrar conforme o calendario avanca."""
        project = self.project()
        veredito = self._decidir(project)
        inicio = dt.date.today() - dt.timedelta(days=5)
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso", "--data", inicio.isoformat())
        texto = veredito.read_text(encoding="utf-8")
        self.assertEqual(cc.extract_bullet(texto, "Data de inicio de uso"), inicio.isoformat())
        self.assertEqual(
            cc.extract_bullet(texto, "Veredito D+30 previsto"), (inicio + dt.timedelta(days=30)).isoformat()
        )
        self.assertEqual(
            cc.extract_bullet(texto, "Veredito D+180 previsto"), (inicio + dt.timedelta(days=180)).isoformat()
        )

    def test_registrar_evento_inicio_uso_default_hoje(self):
        project = self.project()
        veredito = self._decidir(project)
        with patch.object(cc, "today", return_value="2026-03-01"):
            self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")
        texto = veredito.read_text(encoding="utf-8")
        self.assertEqual(cc.extract_bullet(texto, "Data de inicio de uso"), "2026-03-01")
        self.assertEqual(cc.extract_bullet(texto, "Veredito D+30 previsto"), "2026-03-31")

    def test_dashboard_mostra_aguardando_inicio_de_uso_sem_data(self):
        project = self.project()
        self._decidir(project, extra=["--comprado"])
        rows = cc.verdict_summaries()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["d30_status"], "aguardando inicio de uso")
        self.assertEqual(rows[0]["d180_status"], "aguardando inicio de uso")

    def test_dashboard_html_renderiza_aguardando_inicio_de_uso(self):
        project = self.project()
        self._decidir(project, extra=["--comprado"])
        self.cli("dashboard")
        pagina = (cc.DASHBOARD / "index.html").read_text(encoding="utf-8")
        self.assertIn("aguardando inicio de uso", pagina)

    def test_phase_status_pendente_quando_previsto_e_no_futuro(self):
        """Testa `phase_status` diretamente com um veredito sintetico (mesmo
        padrao de `tests/test_sprint14.py`) - datas relativas ao dia real
        do teste, nunca literais fixas, pra nao quebrar conforme o
        calendario avanca."""
        previsto = dt.date.today() + dt.timedelta(days=11)
        (cc.VEREDITOS).mkdir(parents=True, exist_ok=True)
        (cc.VEREDITOS / "teste.md").write_text(
            "# Veredito\n\n- Projeto: teste\n- Produto: Item\n"
            f"- Veredito D+30 previsto: {previsto.isoformat()}\n"
            "- D+30 preenchido em:\n- D+180 preenchido em:\n",
            encoding="utf-8",
        )
        rows = cc.verdict_summaries()
        self.assertEqual(rows[0]["d30_status"], "pendente, faltam 11 dia(s)")

    def test_phase_status_atrasado_quando_previsto_e_no_passado(self):
        previsto = dt.date.today() - dt.timedelta(days=6)
        (cc.VEREDITOS).mkdir(parents=True, exist_ok=True)
        (cc.VEREDITOS / "teste.md").write_text(
            "# Veredito\n\n- Projeto: teste\n- Produto: Item\n"
            f"- Veredito D+30 previsto: {previsto.isoformat()}\n"
            "- D+30 preenchido em:\n- D+180 preenchido em:\n",
            encoding="utf-8",
        )
        rows = cc.verdict_summaries()
        self.assertEqual(rows[0]["d30_status"], "atrasado 6 dia(s)")


class RegistrarEventoIntegridadeTest(ambiente.RepoTestCase):
    """`registrar-evento`: fato datado nunca e sobrescrito, ordem
    cronologica obvia e recusada, veredito ja preenchido e preservado."""

    def _decidir(self, project, pid="candidato", extra=()):
        self.product(project, pid)
        self.quote(project, pid, "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", pid,
                  "--porque", "unico candidato", "--sem-perdedores", *extra)
        return next(p for p in cc.VEREDITOS.glob("*.md") if pid in p.name)

    def test_registrar_evento_recusa_sobrescrever_evento_ja_registrado(self):
        project = self.project()
        veredito = self._decidir(project, extra=["--comprado"])
        antes = veredito.read_bytes()
        with self.assertRaisesRegex(SystemExit, "ja esta registrada"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado", "--data",
                      (dt.date.today() - dt.timedelta(days=1)).isoformat())
        self.assertEqual(veredito.read_bytes(), antes)

    def test_registrar_evento_ordem_cronologica_invalida_e_recusada(self):
        project = self.project()
        veredito = self._decidir(project, extra=["--comprado"])
        antes = veredito.read_bytes()
        ontem = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(SystemExit, "e anterior a Data da compra"):
            self.cli("registrar-evento", str(veredito), "--evento", "entrega", "--data", ontem)
        self.assertEqual(veredito.read_bytes(), antes)

    def test_registrar_evento_ordem_cronologica_valida_e_aceita(self):
        project = self.project()
        veredito = self._decidir(project, extra=["--comprado"])
        self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")
        texto = veredito.read_text(encoding="utf-8")
        self.assertTrue(cc.extract_bullet(texto, "Data de entrega"))
        self.assertTrue(cc.extract_bullet(texto, "Data de inicio de uso"))

    def test_registrar_evento_sem_evento_anterior_e_aceito(self):
        """Registrar entrega sem NUNCA ter registrado comprado e permitido -
        o Josemar pode ter esquecido de marcar `--comprado` na hora, e o
        sistema nao deve bloquear o resto do fluxo por causa disso."""
        project = self.project()
        veredito = self._decidir(project)
        self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        self.assertTrue(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data de entrega"))

    def test_registrar_evento_preserva_fase_ja_preenchida(self):
        """Preencher D+30 ANTES de registrar o inicio de uso (janela
        estreita, mas possivel) - registrar o inicio de uso depois nao pode
        sobrescrever o `previsto` de uma fase ja respondida."""
        project = self.project()
        veredito = self._decidir(project, extra=["--comprado"])
        self.cli("preencher-veredito", str(veredito), "--fase", "d30",
                  "--nota-arrependimento", "8", "--compraria-de-novo", "sim",
                  "--resumo", "Chegou rapido, gostei.")
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")
        texto = veredito.read_text(encoding="utf-8")
        self.assertEqual(cc.extract_bullet(texto, "Veredito D+30 previsto"), "")
        self.assertTrue(cc.extract_bullet(texto, "Veredito D+180 previsto"))
        self.assertEqual(cc.extract_bullet(texto, "D+30 resumo"), "Chegou rapido, gostei.")

    def test_registrar_evento_veredito_inexistente_recusa(self):
        with self.assertRaisesRegex(SystemExit, "Veredito nao encontrado"):
            self.cli("registrar-evento", str(cc.VEREDITOS / "nao-existe.md"), "--evento", "comprado")

    def test_registrar_evento_data_formato_invalido_recusa(self):
        with self.assertRaises(SystemExit):
            self.cli("registrar-evento", "v.md", "--evento", "comprado", "--data", "09/09/2026")

    def test_registrar_evento_bloqueado_enquanto_decidir_pendente_no_mesmo_veredito(self):
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")

        real_hook = cc._crash_de_teste_se_pedido

        def hook(ponto):
            if ponto == "timeline_veredito:iniciado":
                raise RuntimeError("crash simulado")
            return real_hook(ponto)

        with patch.object(cc, "_crash_de_teste_se_pedido", hook):
            with self.assertRaises(RuntimeError):
                self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                          "unico candidato", "--sem-perdedores", "--comprado")

        veredito = next(cc.VEREDITOS.glob("*.md"))
        antes = veredito.read_text(encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "ja reivindica"):
            self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        self.assertEqual(veredito.read_text(encoding="utf-8"), antes)

        # Retomando decidir, o veredito volta a ficar livre para o resto do fluxo.
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores", "--comprado")
        self.cli("registrar-evento", str(veredito), "--evento", "entrega")


class FluxoCompletoTest(ambiente.RepoTestCase):
    """Fluxo completo, ponta a ponta, com datas controladas: decisao sem
    compra -> compra depois -> entrega depois -> inicio de uso depois ->
    D+30 -> D+180, preservando vereditos ja preenchidos a cada etapa."""

    def test_ciclo_completo_decisao_ate_d180(self):
        with patch.object(cc, "today", return_value="2026-01-01"):
            project = self.project()
            self.product(project, "candidato")
            self.quote(project, "candidato", "--fonte", "manual")
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "unico candidato valido", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        texto = veredito.read_text(encoding="utf-8")
        self.assertEqual(cc.extract_bullet(texto, "Data da compra"), "")
        self.assertEqual(cc.extract_bullet(texto, "Veredito D+30 previsto"), "")

        with patch.object(cc, "today", return_value="2026-01-03"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado")
        texto = veredito.read_text(encoding="utf-8")
        self.assertEqual(cc.extract_bullet(texto, "Data da compra"), "2026-01-03")

        with patch.object(cc, "today", return_value="2026-01-08"):
            self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        texto = veredito.read_text(encoding="utf-8")
        self.assertEqual(cc.extract_bullet(texto, "Data de entrega"), "2026-01-08")
        # Ainda sem inicio de uso: D+30/D+180 continuam pendentes, nao fabricados.
        self.assertEqual(cc.extract_bullet(texto, "Veredito D+30 previsto"), "")

        with patch.object(cc, "today", return_value="2026-01-10"):
            self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")
        texto = veredito.read_text(encoding="utf-8")
        self.assertEqual(cc.extract_bullet(texto, "Data de inicio de uso"), "2026-01-10")
        self.assertEqual(cc.extract_bullet(texto, "Veredito D+30 previsto"), "2026-02-09")
        self.assertEqual(cc.extract_bullet(texto, "Veredito D+180 previsto"), "2026-07-09")

        self.cli("preencher-veredito", str(veredito), "--fase", "d30",
                  "--nota-arrependimento", "9", "--compraria-de-novo", "sim",
                  "--resumo", "Otimo produto, uso diario sem problema.")
        self.cli("aprender-veredito", str(veredito), "--fase", "d30")
        texto = veredito.read_text(encoding="utf-8")
        self.assertIn("Aprendizado exportado D+30", texto)
        self.assertEqual(cc.extract_bullet(texto, "Veredito D+180 previsto"), "2026-07-09",
                          "D+180 previsto nao pode mudar so porque D+30 foi exportado")

        self.cli("preencher-veredito", str(veredito), "--fase", "d180",
                  "--nota-arrependimento", "9", "--compraria-de-novo", "sim",
                  "--resumo", "Continua otimo depois de 6 meses.", "--ainda-usa", "sim")
        self.cli("aprender-veredito", str(veredito), "--fase", "d180")
        texto = veredito.read_text(encoding="utf-8")
        self.assertIn("Aprendizado exportado D+180", texto)
        # As duas fases sao observacoes independentes - as duas sobrevivem juntas.
        self.assertIn("D+30 resumo: Otimo produto, uso diario sem problema.", texto)
        self.assertIn("D+180 resumo: Continua otimo depois de 6 meses.", texto)

        self.cli("auditar-decisoes", "--strict")
        self.cli("operacoes-pendentes", "--strict")


class RegistroAntigoCompatibilidadeTest(ambiente.RepoTestCase):
    """Veredito no formato ANTIGO (D+30/D+180 previsto ja fabricados na
    criacao, antes desta correcao) continua funcionando sem reescrita nem
    reinterpretacao - nunca inventamos `inicio_uso` a partir de `Data da
    compra` de um registro legado."""

    def test_veredito_legado_com_previsto_antigo_continua_calculando_status(self):
        project = self.project()
        self.cli("novo-veredito", str(project))
        veredito = next(cc.VEREDITOS.glob("*.md"))
        texto = veredito.read_text(encoding="utf-8")
        ontem = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        texto = cc.replace_or_append_bullet(texto, "Data da compra", "2025-01-01")
        texto = cc.replace_or_append_bullet(texto, "Veredito D+30 previsto", ontem)
        veredito.write_text(texto, encoding="utf-8")

        rows = cc.verdict_summaries()
        self.assertEqual(rows[0]["d30_status"], "atrasado 1 dia(s)")
        # Nada reescreveu o arquivo so por causa da leitura do dashboard.
        self.assertEqual(veredito.read_text(encoding="utf-8"), texto)

    def test_registrar_evento_sobre_veredito_legado_nao_inventa_inicio_de_uso(self):
        """`Data da compra` de um registro antigo nunca vira `Data de
        inicio de uso` por inferencia - so um `registrar-evento --evento
        inicio_uso` explicito grava esse campo."""
        project = self.project()
        self.cli("novo-veredito", str(project))
        veredito = next(cc.VEREDITOS.glob("*.md"))
        texto = cc.replace_or_append_bullet(
            veredito.read_text(encoding="utf-8"), "Data da compra", "2025-01-01"
        )
        veredito.write_text(texto, encoding="utf-8")

        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data de inicio de uso"), "")
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso", "--data", "2025-01-15")
        self.assertEqual(
            cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data de inicio de uso"), "2025-01-15"
        )
        # A data da compra legada continua intocada.
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), "2025-01-01")


class SegundaRevisaoIndependenteFrente6Test(ambiente.RepoTestCase):
    """Regressao dos 5 achados da 2a revisao independente (Astra) sobre o
    commit `e564618` - cada teste aqui reproduziu uma falha real contra
    aquele codigo antes da correcao (script `astra_review_e564618.py`).
    Ver STATUS.md e docs/como-conferir-auditoria.md.

    Raiz comum: a correcao anterior tratava `decidir` e `registrar-evento`
    como dois comandos isolados - nao sincronizava o veredito de volta pro
    estado operacional do projeto (achado 1), nao complementava um
    veredito ja existente numa segunda `decidir --comprado` (achado 2), nao
    congelava a data efetiva contra retomada em outro dia (achado 3), a
    assinatura de `decidir` nao tolerava a evolucao do proprio schema
    (achado 4), e a checagem de cronologia so olhava pra tras, nunca pra
    frente (achado 5)."""

    def _decidir(self, project, pid="candidato", extra=()):
        self.product(project, pid)
        self.quote(project, pid, "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", pid,
                  "--porque", "unico candidato", "--sem-perdedores", *extra)
        return next(p for p in cc.VEREDITOS.glob("*.md") if pid in p.name)

    def _status(self, project):
        return self.cli("status", str(project))

    # ---- achado 1: registrar-evento --evento comprado nao sincronizava --

    def test_comprado_registrado_por_evento_atualiza_estado_operacional(self):
        project = self.project()
        veredito = self._decidir(project)
        self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        status = self._status(project)
        self.assertIn("Estado: comprado", status)
        self.assertNotIn("comprar ou marcar como comprado", status)
        self.assertIn("acompanhar entrega e preencher veredito D+30", status)

    def test_comprado_sem_decisao_correspondente_nao_mexe_no_estado(self):
        """Controle da verificacao de associacao: um veredito standalone
        (`novo-veredito`, sem `Produto ID`) nunca tem como corresponder a
        UMA decisao aberta - o evento e gravado, mas o estado do projeto
        fica intocado, so um aviso e impresso."""
        project = self.project()
        self.cli("novo-veredito", str(project))
        veredito = next(cc.VEREDITOS.glob("*.md"))

        saida = self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today())
        self.assertIn("NAO foi alterado", saida)
        status = self._status(project)
        self.assertNotIn("Estado: comprado", status)

    def test_comprado_de_decisao_substituida_nao_mexe_no_estado_da_nova(self):
        """Controle mais forte: o projeto TEM uma decisao aberta, mas para
        OUTRO produto (esta decisao substituiu a anterior) - o veredito
        antigo confirmando compra nao pode sincronizar estado que agora
        pertence a uma decisao diferente."""
        project = self.project()
        veredito_antigo = self._decidir(project, pid="antigo")
        self.product(project, "novo")
        self.quote(project, "novo", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "novo", "--porque",
                  "troquei de ideia", "--perdedores", "antigo: troquei de ideia")

        self.cli("registrar-evento", str(veredito_antigo), "--evento", "comprado")

        status = self._status(project)
        self.assertNotIn("Estado: comprado", status)

    # ---- achado 2: 2a chamada de decidir --comprado nao complementava ----

    def test_decidir_comprado_depois_complementa_veredito_existente(self):
        project = self.project()
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores"]
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli(*args)
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), "")

        self.cli(*args, "--comprado")

        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today())
        status = self._status(project)
        self.assertIn("Estado: comprado", status)

    def test_decidir_comprado_depois_nao_sobrescreve_data_ja_registrada(self):
        """Controle: se a compra ja tinha sido registrada por outro caminho
        (`registrar-evento`) ANTES da 2a chamada de `decidir --comprado`,
        o complemento nao pode pisar em cima - fato datado nao e
        sobrescrito, nem por este caminho."""
        project = self.project()
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores"]
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli(*args)
        veredito = next(cc.VEREDITOS.glob("*.md"))
        ontem = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        self.cli("registrar-evento", str(veredito), "--evento", "comprado", "--data", ontem)

        self.cli(*args, "--comprado")

        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), ontem)

    def test_decidir_comprado_depois_nao_exige_force_veredito(self):
        """O veredito nao pode ser reescrito do zero so pra registrar a
        confirmacao - `--force-veredito` continua sendo so pra descartar o
        conteudo inteiro de proposito."""
        project = self.project()
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores"]
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli(*args)
        veredito = next(cc.VEREDITOS.glob("*.md"))
        cc.atomic_write_text(
            veredito,
            cc.replace_or_append_bullet(veredito.read_text(encoding="utf-8"), "D+30 resumo", "MARCADOR_PRESERVAR"),
        )

        self.cli(*args, "--comprado")

        self.assertIn("MARCADOR_PRESERVAR", veredito.read_text(encoding="utf-8"))

    # ---- achado 3: retomada em outro dia trocava a data da compra --------

    def test_retomada_em_outro_dia_nao_troca_data_de_compra_congelada(self):
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores", "--comprado"]
        primeiro_dia = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        segundo_dia = dt.date.today().isoformat()

        def crash(ponto):
            if ponto == "veredito:iniciado":
                raise OSError("falha antes de criar veredito")

        with patch.object(cc, "today", return_value=primeiro_dia), \
                patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli(*args)

        with patch.object(cc, "today", return_value=segundo_dia):
            self.cli(*args)

        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(
            cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), primeiro_dia,
            f"Retomada no dia {segundo_dia} nao pode trocar a data da confirmacao original ({primeiro_dia})",
        )

    def test_controle_data_compra_explicita_sobrevive_retomada_em_outro_dia(self):
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        primeiro_dia = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores", "--comprado", "--data-compra", primeiro_dia]

        def crash(ponto):
            if ponto == "veredito:iniciado":
                raise OSError("falha antes de criar veredito")

        with patch.object(cc, "today", return_value=primeiro_dia), \
                patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli(*args)

        self.cli(*args)

        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), primeiro_dia)

    def test_controle_retomada_mesma_versao_com_comprado_funciona(self):
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores", "--comprado"]

        def crash(ponto):
            if ponto == "veredito:iniciado":
                raise OSError("falha antes de criar veredito")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli(*args)

        self.cli(*args)

        self.assertFalse(cc.pending_operations([project]))
        self.assertEqual(
            cc.extract_bullet(next(cc.VEREDITOS.glob("*.md")).read_text(encoding="utf-8"), "Data da compra"),
            cc.today(),
        )

    # ---- achado 4: assinatura de decidir perdia compatibilidade ----------

    def test_journal_de_versao_anterior_a_data_compra_continua_retomavel(self):
        """Journal real criado pelo codigo do commit `5998a15` (a versao
        anterior a frente 6 inteira - sem `--data-compra`, sem os campos
        `data_compra`/`data_compra_efetiva` na assinatura/detalhe),
        interrompido em `veredito:iniciado`, tem que continuar retomavel
        com o MESMO comando depois do upgrade - sem exigir apagar o
        journal, sem enfraquecer a recusa pra argumento realmente
        diferente (ver teste de controle abaixo)."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores", "--comprado"]

        script = self.root / "scripts" / "central_compras.py"
        atual = script.read_bytes()
        antigo = subprocess.run(
            ["git", "show", "5998a15:scripts/central_compras.py"],
            cwd=REPO, capture_output=True, check=True,
        ).stdout
        script.write_bytes(antigo)
        env = os.environ.copy()
        env["CENTRAL_COMPRAS_TESTE_CRASH_APOS"] = "veredito:iniciado"
        crash = subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, env=env, capture_output=True, text=True,
        )
        self.assertEqual(crash.returncode, 70, crash.stderr)

        script.write_bytes(atual)
        retry = subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(
            retry.returncode, 0,
            "MESMO comando e argumentos recusados como 'dados diferentes' so por causa da "
            "evolucao do schema da assinatura:\n" + retry.stderr,
        )
        self.assertFalse(cc.pending_operations([project]))

    def test_controle_assinatura_realmente_diferente_continua_recusada(self):
        """A tolerancia a evolucao de schema (achado 4) nao pode abrir mao
        de recusar um argumento genuinamente diferente - aqui a PROPRIA
        versao atual comeca a operacao sem `--data-compra` e a retomada
        tenta completar com uma `--data-compra` explicita: isso e dado
        novo de verdade, tem que continuar recusado."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores", "--comprado"]

        def crash(ponto):
            if ponto == "veredito:iniciado":
                raise OSError("falha antes de criar veredito")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli(*args)

        ontem = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(SystemExit, "dados diferentes"):
            self.cli(*args, "--data-compra", ontem)

    # ---- achado 5: cronologia so validava pra tras ------------------------

    def test_cronologia_bidirecional_recusa_entrega_apos_inicio_de_uso(self):
        project = self.project()
        veredito = self._decidir(project)
        ontem = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso", "--data", ontem)
        antes = veredito.read_bytes()

        with self.assertRaisesRegex(SystemExit, "e posterior a Data de inicio de uso"):
            self.cli("registrar-evento", str(veredito), "--evento", "entrega", "--data", cc.today())

        self.assertEqual(veredito.read_bytes(), antes)

    def test_controle_uso_depois_da_entrega_calcula_lembretes(self):
        project = self.project()
        veredito = self._decidir(project)
        self.cli("registrar-evento", str(veredito), "--evento", "entrega", "--data", cc.today())
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso", "--data", cc.today())

        texto = veredito.read_text(encoding="utf-8")
        esperado = (dt.date.today() + dt.timedelta(days=30)).isoformat()
        self.assertEqual(cc.extract_bullet(texto, "Veredito D+30 previsto"), esperado)

    # ---- cobertura adicional: multiplos arquivos, travas, recuperacao ----

    def test_recursos_reivindicados_por_decidir_pendente_bloqueiam_evento_comprado(self):
        """`registrar-evento --evento comprado` grava `processo.md`/
        `briefing.md` do projeto associado, alem do veredito - por isso
        precisa reivindicar os dois como recurso. Um `decidir` interrompido
        (journal pendente reivindicando `processo.md` do MESMO projeto)
        bloqueia `registrar-evento` ate ser resolvido."""
        project = self.project()
        veredito_path = self._decidir(project)
        self.assertEqual(cc.extract_bullet(veredito_path.read_text(encoding="utf-8"), "Data da compra"), "")

        # 2a chamada, agora com --comprado, interrompida ANTES de tocar em
        # qualquer arquivo (a captura ainda nem comecou) - o journal fica
        # pendente reivindicando decisao.md/processo.md/o proprio veredito,
        # mas o conteudo do veredito continua exatamente como o da 1a
        # chamada (Data da compra ainda em branco).
        def crash(ponto):
            if ponto == "captura:iniciado":
                raise OSError("falha antes de qualquer escrita da 2a chamada")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                          "unico candidato", "--sem-perdedores", "--comprado")

        self.assertEqual(cc.extract_bullet(veredito_path.read_text(encoding="utf-8"), "Data da compra"), "")
        with self.assertRaisesRegex(SystemExit, "ja reivindica"):
            self.cli("registrar-evento", str(veredito_path), "--evento", "comprado")
        self.assertEqual(cc.extract_bullet(veredito_path.read_text(encoding="utf-8"), "Data da compra"), "")

        # Retomando `decidir`, o registro do evento volta a funcionar.
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores", "--comprado")
        self.assertFalse(cc.pending_operations([project]))

    def test_falha_entre_gravar_evento_e_sincronizar_projeto_e_retomavel(self):
        """Uma falha DEPOIS do evento ja estar gravado no veredito, mas
        ANTES de `processo.md`/`briefing.md` serem atualizados, nao pode
        deixar o projeto preso em 'pesquisando' pra sempre - repetir o
        MESMO comando completa so o que faltou, sem duplicar nem recusar
        como 'ja registrado'."""
        project = self.project()
        veredito = self._decidir(project)

        def crash(ponto):
            if ponto == "estado_projeto:iniciado":
                raise OSError("falha entre gravar o evento e sincronizar o projeto")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today())
        self.assertNotIn("Estado: comprado", self._status(project))
        self.assertTrue(cc.pending_operations([project]) or cc.pending_operations([cc.BASE]))

        self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.assertIn("Estado: comprado", self._status(project))
        self.assertFalse(cc.pending_operations([cc.BASE]))

    def test_falha_apos_gravar_evento_nao_duplica_bullet(self):
        """Mesmo cenario da falha intermediaria, mas confirmando que a
        retomada nao duplica a linha `Data da compra` no veredito (o passo
        `evento` e reconhecido como ja concluido, `executar_uma_vez` nao
        roda `_gravar_evento` de novo)."""
        project = self.project()
        veredito = self._decidir(project)

        def crash(ponto):
            if ponto == "estado_projeto:iniciado":
                raise OSError("falha entre gravar o evento e sincronizar o projeto")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        texto = veredito.read_text(encoding="utf-8")
        self.assertEqual(texto.count("- Data da compra:"), 1)


class TerceiraRevisaoIndependenteFrente6Test(ambiente.RepoTestCase):
    """Regressao dos 4 achados da 2a revisao independente (Astra) sobre o
    commit `3acc96a` - cada teste aqui reproduziu uma falha real contra
    aquele codigo antes da correcao (script `astra_review_3acc96a.py`).
    Ver STATUS.md e docs/como-conferir-auditoria.md.

    Raiz comum, registrada explicitamente porque e uma REGRESSAO
    TRANSVERSAL: `_assinaturas_compativeis` (introduzida na 1a revisao,
    usada por TODO `tracked_operation` - `decidir`, `registrar-evento`,
    `vincular-produto`, `aprender-veredito`) comparava valores com `==` do
    Python, que confunde `False` com `0` (achado 1) mesmo dentro de
    estruturas aninhadas como `requisitos_atendidos`. Os achados 2 e 3 sao
    o mesmo padrao de fundo dos pacotes anteriores (congelar o dado
    EFETIVO, nao recriar journal para entrada invalida) reaberto por
    detalhes finos que as rodadas anteriores nao cobriam; o achado 4 e o
    contrato de cronologia de `registrar-evento` que nao tinha sido
    replicado pro OUTRO caminho que grava `Data da compra`."""

    def _decidir(self, project, pid="candidato", extra=()):
        self.product(project, pid)
        self.quote(project, pid, "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", pid,
                  "--porque", "unico candidato", "--sem-perdedores", *extra)
        return next(p for p in cc.VEREDITOS.glob("*.md") if pid in p.name)

    # ---- achado 1: == confundia False com 0, inclusive aninhado ---------

    def test_valores_equivalentes_distingue_bool_de_inteiro(self):
        """Teste direto da funcao corrigida - False/0 e True/1 nunca sao
        equivalentes, no topo nem dentro de dict/list aninhados (onde o
        bug real acontecia, via `requisitos_atendidos`)."""
        self.assertFalse(cc._valores_equivalentes(False, 0))
        self.assertFalse(cc._valores_equivalentes(True, 1))
        self.assertTrue(cc._valores_equivalentes(False, False))
        self.assertTrue(cc._valores_equivalentes(0, 0))
        self.assertFalse(cc._valores_equivalentes({"uso": False}, {"uso": 0}))
        self.assertFalse(cc._valores_equivalentes(["a", False], ["a", 0]))
        self.assertTrue(cc._valores_equivalentes({"uso": False, "n": 3}, {"uso": False, "n": 3}))

    def test_vincular_produto_retomada_nao_confunde_requisito_false_com_zero(self):
        """Achado 1, reproduzido no caminho real: `vincular-produto
        --requisito uso=false` interrompido antes de gravar a participacao,
        retomado com `uso=0` (int, nao bool) - tem que ser recusado como
        argumento diferente, nunca aceito como "mesma retomada". Sem a
        correcao, a participacao gravada tinha `uso=0` (nao corta o gate,
        que so elimina com `is False`), reabilitando o candidato."""
        origin, dest = self.project("origem"), self.project("destino")
        self.product(origin)
        args = ["vincular-produto", "--produto-id", "candidato", "--projeto", str(dest), "--requisito"]

        def crash(ponto):
            if ponto == "participacao:iniciado":
                raise OSError("falha antes de gravar participacao")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli(*args, "uso=false")

        with self.assertRaisesRegex(SystemExit, "dados diferentes"):
            self.cli(*args, "uso=0")
        self.assertFalse(cc.participation_path(dest, "candidato").exists())

    def test_controle_vincular_produto_retomada_com_mesmo_requisito_funciona(self):
        """Controle: retomar com o MESMO requisito (`uso=false` de novo)
        continua funcionando normalmente, e o gate continua cortando o
        candidato (prova que a correcao nao afeta o caminho legitimo)."""
        origin, dest = self.project("origem"), self.project("destino")
        self.product(origin)
        args = ["vincular-produto", "--produto-id", "candidato", "--projeto", str(dest), "--requisito"]

        def crash(ponto):
            if ponto == "participacao:iniciado":
                raise OSError("falha antes de gravar participacao")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli(*args, "uso=false")

        self.cli(*args, "uso=false")
        self.quote(dest, "candidato", "--fonte", "manual")
        self.assertEqual(cc.compute_ranking(dest)[0], [])

    # ---- achado 2: complemento nao usava a data-compra explicita persistida --

    def test_upgrade_preserva_data_compra_explicita_de_journal_sem_campo_congelado(self):
        """Journal real criado pelo codigo do commit `e564618` (que ja
        tinha `--data-compra`, mas ainda nao `data_compra_efetiva`
        congelado em `op.detalhe` - esse campo so existe desde a rodada
        anterior), interrompido em `veredito:iniciado`, tem que preservar
        a data EXPLICITA na retomada apos o upgrade - ela e o proprio dado
        de entrada da chamada, nao depende de ter sido congelada."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        esperado = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores", "--comprado", "--data-compra", esperado]

        script = self.root / "scripts" / "central_compras.py"
        atual = script.read_bytes()
        antigo = subprocess.run(
            ["git", "show", "e564618:scripts/central_compras.py"],
            cwd=REPO, capture_output=True, check=True,
        ).stdout
        script.write_bytes(antigo)
        env = os.environ.copy()
        env["CENTRAL_COMPRAS_TESTE_CRASH_APOS"] = "veredito:iniciado"
        crash = subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, env=env, capture_output=True, text=True,
        )
        self.assertEqual(crash.returncode, 70, crash.stderr)

        script.write_bytes(atual)
        retry = subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(retry.returncode, 0, retry.stderr)
        self.assertFalse(cc.pending_operations([project]))
        texto = next(cc.VEREDITOS.glob("*.md")).read_text(encoding="utf-8")
        self.assertEqual(
            cc.extract_bullet(texto, "Data da compra"), esperado,
            "Upgrade completou a retomada mas perdeu a data explicita da compra",
        )

    # ---- achado 3: recusa por cronologia deixava journal pendente -------

    def test_recusa_por_cronologia_com_data_default_nao_deixa_pendencia(self):
        project = self.project()
        veredito = self._decidir(project)
        ontem = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso", "--data", ontem)
        antes = veredito.read_bytes()

        with self.assertRaisesRegex(SystemExit, "posterior"):
            self.cli("registrar-evento", str(veredito), "--evento", "entrega")

        self.assertEqual(veredito.read_bytes(), antes)
        self.assertFalse(cc.pending_operations([cc.BASE]))

    def test_corrigir_data_apos_recusa_por_cronologia_funciona(self):
        """Consequencia direta do achado 3: como a recusa nao deixa
        journal pendente, corrigir a data numa chamada seguinte (com
        `--data` explicita e valida) e uma operacao NOVA normal, nunca
        recusada como 'argumento diferente' contra uma pendencia que nao
        deveria existir."""
        project = self.project()
        veredito = self._decidir(project)
        ontem = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso", "--data", ontem)

        with self.assertRaisesRegex(SystemExit, "posterior"):
            self.cli("registrar-evento", str(veredito), "--evento", "entrega")

        self.cli("registrar-evento", str(veredito), "--evento", "entrega", "--data", ontem)

        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data de entrega"), ontem)
        self.assertFalse(cc.pending_operations([cc.BASE]))

    # ---- achado 4: complemento de compra nao aplicava a cronologia ------

    def test_decidir_comprado_complementar_recusa_cronologia_impossivel(self):
        project = self.project()
        veredito = self._decidir(project)
        ontem = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso", "--data", ontem)
        caminhos = [veredito, project / "decisao.md", project / "processo.md", project / "briefing.md"]
        antes = {p: p.read_bytes() for p in caminhos}

        with self.assertRaisesRegex(SystemExit, "posterior"):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "unico candidato", "--sem-perdedores", "--comprado", "--data-compra", cc.today())

        self.assertEqual({p: p.read_bytes() for p in caminhos}, antes,
                          "decidir recusado por cronologia nao pode ter alterado nenhum arquivo")
        status = self.cli("status", str(project))
        self.assertNotIn("Estado: comprado", status)

    def test_controle_decidir_comprado_complementar_cronologia_valida_funciona(self):
        """Controle: quando a data da compra e cronologicamente VALIDA
        (anterior ao inicio de uso ja registrado), o complemento continua
        funcionando normalmente - a correcao do achado 4 nao pode ter
        travado o caminho legitimo."""
        project = self.project()
        veredito = self._decidir(project)
        ontem = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        self.cli("registrar-evento", str(veredito), "--evento", "entrega", "--data", ontem)
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso", "--data", cc.today())

        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores", "--comprado", "--data-compra", ontem)

        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), ontem)
        status = self.cli("status", str(project))
        self.assertIn("Estado: comprado", status)


if __name__ == "__main__":
    unittest.main()
