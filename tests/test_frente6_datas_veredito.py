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
import json
import os
import re
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
    commit `8e86884` - cada teste aqui reproduziu uma falha real contra
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
        """Journal real criado pelo codigo do commit `6d3e334` (a versao
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
            ["git", "show", "6d3e334:scripts/central_compras.py"],
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
    commit `c117cee` - cada teste aqui reproduziu uma falha real contra
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
        """Journal real criado pelo codigo do commit `8e86884` (que ja
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
            ["git", "show", "8e86884:scripts/central_compras.py"],
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


class QuartaRevisaoIndependenteFrente6Test(ambiente.RepoTestCase):
    """Regressao dos 2 achados da 3a revisao independente (Astra) sobre o
    commit `ad6a04a`.

    Os dois casos sao de retomada apos upgrade: journal antigo nao pode virar
    autorizacao para inventar data nova nem para executar uma entrada que a
    propria versao antiga ja tinha recusado."""

    def _decidir(self, project, pid="candidato", extra=()):
        self.product(project, pid)
        self.quote(project, pid, "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", pid,
                  "--porque", "unico candidato", "--sem-perdedores", *extra)
        return next(p for p in cc.VEREDITOS.glob("*.md") if pid in p.name)

    def test_upgrade_preserva_data_compra_implicita_de_journal_antigo(self):
        """Journal real criado pelo commit `8e86884` com `--comprado` e sem
        `--data-compra`, interrompido antes de criar o veredito, nao tinha
        `data_compra_efetiva`. A retomada atual deve recuperar a data da
        tentativa original pela evidencia persistida (`veredito_nome`), nunca
        cair em `today()` do dia da retomada."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores", "--comprado"]

        script = self.root / "scripts" / "central_compras.py"
        atual = script.read_bytes()
        antigo = subprocess.run(
            ["git", "show", "8e86884:scripts/central_compras.py"],
            cwd=REPO, capture_output=True, check=True,
        ).stdout
        script.write_bytes(antigo)
        env = os.environ.copy()
        env["CENTRAL_COMPRAS_TESTE_CRASH_APOS"] = "veredito:iniciado"
        crash = subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, env=env, capture_output=True, text=True,
        )
        self.assertEqual(crash.returncode, 70, crash.stderr)

        journal = next((project / ".operacoes").glob("*.json"))
        registro = json.loads(journal.read_text(encoding="utf-8"))
        veredito_nome = registro["detalhe"]["veredito_nome"]
        data_original = veredito_nome[:10]
        data_retomada = (dt.date.fromisoformat(data_original) + dt.timedelta(days=1)).isoformat()

        script.write_bytes(atual)
        with patch.object(cc, "today", return_value=data_retomada):
            self.cli(*args)

        self.assertFalse(cc.pending_operations([project]))
        texto = (cc.VEREDITOS / veredito_nome).read_text(encoding="utf-8")
        self.assertEqual(
            cc.extract_bullet(texto, "Data da compra"), data_original,
            "Retomada em outro dia nao pode transformar compra implicita antiga na data do retry",
        )

    def test_upgrade_recusa_journal_antigo_de_evento_sem_passos_e_cronologia_invalida(self):
        """No commit `c117cee`, `registrar-evento --evento entrega` sem
        `--data` podia recusar tarde demais e deixar journal pendente vazio.
        Retomar esse journal na versao atual precisa validar a data congelada
        real da tentativa, nao tratar `passos: {}` como prova de validacao."""
        project = self.project()
        veredito = self._decidir(project)
        ontem = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso", "--data", ontem)
        antes = veredito.read_bytes()

        script = self.root / "scripts" / "central_compras.py"
        atual = script.read_bytes()
        antigo = subprocess.run(
            ["git", "show", "c117cee:scripts/central_compras.py"],
            cwd=REPO, capture_output=True, check=True,
        ).stdout
        script.write_bytes(antigo)
        recusa_antiga = subprocess.run(
            [sys.executable, str(script), "registrar-evento", str(veredito), "--evento", "entrega"],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertNotEqual(recusa_antiga.returncode, 0, recusa_antiga.stderr)
        script.write_bytes(atual)

        pendentes = cc.pending_operations([cc.BASE])
        self.assertEqual(len(pendentes), 1)
        self.assertEqual(pendentes[0]["op_id"], f"registrar-evento:{veredito.name}:entrega")
        self.assertEqual(pendentes[0]["passos"], {}, "pre-condicao: journal antigo ficou sem efeito tentado")

        with self.assertRaisesRegex(SystemExit, "posterior"):
            self.cli("registrar-evento", str(veredito), "--evento", "entrega")

        self.assertEqual(veredito.read_bytes(), antes)

        journal = next((cc.BASE / ".operacoes").glob("*.json"))
        journal.unlink()
        self.cli("registrar-evento", str(veredito), "--evento", "entrega", "--data", ontem)
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data de entrega"), ontem)


class QuintaRevisaoIndependenteFrente6Test(ambiente.RepoTestCase):
    """Achado da 4a revisao independente (sessao 25, commit 825d945):
    `decidir --comprado` como "2a chamada" (achado 2 da 1a revisao, pra
    complementar um veredito ja criado em vez de recusar) so funcionava
    quando as duas chamadas caiam no MESMO dia. `veredito_nome_candidato`
    era sempre recalculado com `today()`; em outro dia isso nao batia com
    o veredito real - criava um segundo veredito orfao e pulava a
    checagem de cronologia do achado 4 (ela olhava para um arquivo que
    nao existia). Reproduzido antes da correcao em
    `%TEMP%\\revisao_frente6_ee1c21d.py`. Corrigido com
    `_veredito_existente_para`: localiza o veredito pela IDENTIDADE
    (bullets `Projeto`/`Produto ID`), nunca pelo nome do arquivo."""

    def _decidir(self, project, pid="candidato", extra=()):
        self.product(project, pid)
        self.quote(project, pid, "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", pid,
                  "--porque", "unico candidato", "--sem-perdedores", *extra)
        return next(p for p in cc.VEREDITOS.glob("*.md") if pid in p.name)

    def _status(self, project):
        return self.cli("status", str(project))

    # ---- complemento em dia diferente: cria 2 vereditos em vez de 1 ------

    def test_complemento_em_dia_diferente_localiza_e_complementa_o_veredito_real(self):
        dia1 = "2026-01-01"
        dia2 = "2026-01-05"
        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            self._decidir(project)
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), "")

        with patch.object(cc, "today", return_value=dia2):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "unico candidato", "--sem-perdedores", "--comprado")

        vereditos = list(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(len(vereditos), 1,
                          f"BUG: criou {len(vereditos)} vereditos em vez de complementar o existente")
        self.assertEqual(vereditos[0].name, veredito.name)
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), dia2)
        self.assertIn("Estado: comprado", self._status(project))

    def test_complemento_em_dia_diferente_com_data_compra_explicita(self):
        dia1 = "2026-04-01"
        dia2 = "2026-04-10"
        data_compra_real = "2026-04-08"
        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            self._decidir(project)
        veredito = next(cc.VEREDITOS.glob("*.md"))

        with patch.object(cc, "today", return_value=dia2):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "unico candidato", "--sem-perdedores", "--comprado",
                      "--data-compra", data_compra_real)

        self.assertEqual(len(list(cc.VEREDITOS.glob("*.md"))), 1)
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), data_compra_real)

    def test_complemento_em_dia_diferente_preserva_avaliacoes_existentes(self):
        """So `Data da compra` em branco e preenchida - D+30/D+180 ja
        respondidos (ou qualquer outro conteudo humano) continuam
        intactos, sem exigir `--force-veredito`, mesmo com o complemento
        acontecendo dias depois."""
        dia1 = "2026-05-01"
        dia2 = "2026-05-20"
        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            self._decidir(project)
        veredito = next(cc.VEREDITOS.glob("*.md"))
        cc.atomic_write_text(
            veredito,
            cc.replace_or_append_bullet(veredito.read_text(encoding="utf-8"), "D+30 resumo", "MARCADOR_PRESERVAR"),
        )

        with patch.object(cc, "today", return_value=dia2):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "unico candidato", "--sem-perdedores", "--comprado")

        texto = veredito.read_text(encoding="utf-8")
        self.assertIn("MARCADOR_PRESERVAR", texto)
        self.assertEqual(cc.extract_bullet(texto, "Data da compra"), dia2)
        self.assertEqual(len(list(cc.VEREDITOS.glob("*.md"))), 1)

    # ---- complemento em dia diferente: pulava a cronologia do achado 4 ---

    def test_complemento_em_dia_diferente_recusa_cronologia_impossivel_sem_efeitos(self):
        dia1 = "2026-02-01"
        d_entrega = "2026-02-02"
        d_inicio_uso = "2026-02-03"
        d_compra_tardia = "2026-02-10"  # posterior ao inicio de uso - impossivel

        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            self._decidir(project)
        veredito = next(cc.VEREDITOS.glob("*.md"))
        with patch.object(cc, "today", return_value=d_entrega):
            self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        with patch.object(cc, "today", return_value=d_inicio_uso):
            self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")

        texto_antes = veredito.read_text(encoding="utf-8")
        decisao_antes = (project / "decisao.md").read_bytes()
        processo_antes = (project / "processo.md").read_bytes()
        status_antes = self._status(project)

        with patch.object(cc, "today", return_value=d_compra_tardia):
            with self.assertRaisesRegex(SystemExit, "posterior"):
                self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                          "unico candidato", "--sem-perdedores", "--comprado")

        self.assertEqual(len(list(cc.VEREDITOS.glob("*.md"))), 1, "nao pode ter criado um 2o veredito")
        self.assertEqual(veredito.read_text(encoding="utf-8"), texto_antes)
        self.assertEqual((project / "decisao.md").read_bytes(), decisao_antes)
        self.assertEqual((project / "processo.md").read_bytes(), processo_antes)
        self.assertEqual(self._status(project), status_antes)
        self.assertFalse(cc.pending_operations([project]))

    # ---- ambiguidade: nunca escolher um veredito arbitrariamente ---------

    def test_ambiguidade_entre_vereditos_recusa_antes_de_qualquer_escrita(self):
        project = self.project()
        veredito1 = self._decidir(project)
        veredito2 = cc.VEREDITOS / f"{cc.today()}-duplicado-{project.name}-candidato.md"
        veredito2.write_text(veredito1.read_text(encoding="utf-8"), encoding="utf-8")

        veredito1_antes = veredito1.read_bytes()
        veredito2_antes = veredito2.read_bytes()
        decisao_antes = (project / "decisao.md").read_bytes()
        processo_antes = (project / "processo.md").read_bytes()

        with self.assertRaisesRegex(SystemExit, "Mais de um veredito"):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "unico candidato", "--sem-perdedores", "--comprado")

        self.assertEqual(veredito1.read_bytes(), veredito1_antes)
        self.assertEqual(veredito2.read_bytes(), veredito2_antes)
        self.assertEqual((project / "decisao.md").read_bytes(), decisao_antes)
        self.assertEqual((project / "processo.md").read_bytes(), processo_antes)
        self.assertFalse(cc.pending_operations([project]))

    # ---- --force-veredito continua descartando o conteudo de proposito ---

    def test_force_veredito_em_dia_diferente_reseta_o_mesmo_veredito_sem_duplicar(self):
        dia1 = "2026-06-01"
        dia2 = "2026-06-15"
        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            self._decidir(project)
        veredito = next(cc.VEREDITOS.glob("*.md"))
        cc.atomic_write_text(
            veredito,
            cc.replace_or_append_bullet(veredito.read_text(encoding="utf-8"), "D+30 resumo", "SERA_DESCARTADO"),
        )

        with patch.object(cc, "today", return_value=dia2):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "unico candidato", "--sem-perdedores", "--comprado", "--force-veredito")

        vereditos = list(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(len(vereditos), 1, "force-veredito em outro dia nao pode criar um segundo arquivo")
        self.assertEqual(vereditos[0].name, veredito.name, "tem que resetar o MESMO veredito, nao criar outro")
        texto = veredito.read_text(encoding="utf-8")
        self.assertNotIn("SERA_DESCARTADO", texto, "force-veredito tem que descartar o conteudo antigo")
        self.assertEqual(cc.extract_bullet(texto, "Data da compra"), dia2)

    # ---- falha intermediaria no complemento e retomada em outro dia ------

    def test_falha_intermediaria_no_complemento_e_retomada_em_outro_dia_preserva_veredito_correto(self):
        """Falha durante um complemento de compra (2a chamada, em dia
        diferente da 1a decisao) tem que retomar mirando o MESMO veredito
        real - nunca recalcular um novo pelo dia da retomada - e
        preservar a data CONGELADA na tentativa que falhou, nunca a do
        dia em que a retomada acontece."""
        dia1 = "2026-03-01"
        dia2 = "2026-03-05"
        dia3 = "2026-03-09"

        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            self._decidir(project)
        veredito_original = next(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(cc.extract_bullet(veredito_original.read_text(encoding="utf-8"), "Data da compra"), "")

        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores", "--comprado"]

        def crash(ponto):
            if ponto == "veredito:iniciado":
                raise OSError("falha durante o complemento")

        with patch.object(cc, "today", return_value=dia2), \
                patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli(*args)

        journal = next((project / ".operacoes").glob("*.json"))
        registro = json.loads(journal.read_text(encoding="utf-8"))
        self.assertEqual(
            registro["detalhe"]["veredito_nome"], veredito_original.name,
            "o journal da tentativa que falhou tem que ter congelado o veredito REAL (dia1), nao um novo (dia2)",
        )
        self.assertEqual(registro["detalhe"]["data_compra_efetiva"], dia2)

        with patch.object(cc, "today", return_value=dia3):
            self.cli(*args)

        self.assertFalse(cc.pending_operations([project]))
        vereditos = sorted(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(len(vereditos), 1, "retomada em outro dia nao pode criar um segundo veredito")
        self.assertEqual(
            cc.extract_bullet(veredito_original.read_text(encoding="utf-8"), "Data da compra"), dia2,
            "a retomada tem que gravar a data CONGELADA da tentativa que falhou (dia2), "
            "nunca a do dia em que a retomada de fato acontece (dia3)",
        )

    # ---- controle: complemento no MESMO dia continua funcionando ---------

    def test_controle_complemento_no_mesmo_dia_continua_funcionando(self):
        project = self.project()
        self._decidir(project)
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores", "--comprado")
        self.assertEqual(len(list(cc.VEREDITOS.glob("*.md"))), 1)
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today())


class SextaRevisaoIndependenteFrente6Test(ambiente.RepoTestCase):
    """Regressao dos 2 achados confirmados da 5a revisao independente
    (sessao 26, sobre o commit `6e613d7`) - reproduzidos primeiro em
    `tests/revisao_independente_e048ad6.py` (script externo daquela
    sessao, removido depois de incorporado aqui). Os testes daquele
    arquivo PASSAVAM com o defeito presente; aqui eles exigem o
    comportamento CORRETO (recusa antes de qualquer escrita).

    Raiz comum: `_veredito_existente_para` (`6e613d7`) acha o veredito
    certo por IDENTIDADE (Projeto/Produto ID) em qualquer dia, mas nao
    confere se a decisao que o criou ainda e a mesma que esta chamada -
    uma decisao intermediaria de OUTRO produto no mesmo projeto nao
    invalida o veredito antigo aos olhos dela."""

    def _decidir(self, project, pid="candidato", extra=()):
        self.product(project, pid)
        self.quote(project, pid, "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", pid,
                  "--porque", "unico candidato", "--sem-perdedores", *extra)
        return next(p for p in cc.VEREDITOS.glob("*.md") if pid in p.name)

    # ---- achado 1: complemento com dados financeiros divergentes --------

    def test_redecidir_apos_decisao_intermediaria_com_cotacao_nova_e_recusado(self):
        """Cenario real: decide A, muda de ideia e decide B, reconsidera e
        decide A de novo semanas depois - com uma cotacao NOVA (preco/loja
        diferentes). Antes da correcao, isso complementava silenciosamente
        o veredito antigo de A com `Data da compra` certa e `Valor pago`/
        `Vendedor`/`Loja` obsoletos da 1a vez. Agora tem que recusar antes
        de qualquer escrita."""
        dia1, dia2, dia3 = "2026-01-01", "2026-01-02", "2026-01-20"

        # `data_coleta` da cotacao vem do relogio real (`now_iso()`, nunca
        # mockado por `patch.object(cc, "today", ...)`) - fixado
        # explicitamente com `--data` (horarios distintos no mesmo dia real)
        # para a ordem entre as duas cotacoes de candidato-a nunca depender
        # da velocidade real de execucao do teste.
        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            self.product(project, "candidato-a")
            self.product(project, "candidato-b")
            self.quote(project, "candidato-a", "--fonte", "manual", "--data", self._hora_hoje("09:00:00"))
            self.cli("decidir", str(project), "--produto-id", "candidato-a",
                      "--porque", "primeira escolha", "--sem-perdedores")
        veredito_a = next(p for p in cc.VEREDITOS.glob("*.md")
                           if cc.extract_bullet(p.read_text(encoding="utf-8"), "Produto ID") == "candidato-a")
        texto_antes = veredito_a.read_bytes()

        with patch.object(cc, "today", return_value=dia2):
            self.quote(project, "candidato-b", "--fonte", "manual", "--data", self._hora_hoje("09:30:00"))
            self.cli("decidir", str(project), "--produto-id", "candidato-b", "--porque",
                      "troquei de ideia", "--perdedores", "candidato-a: desisti por enquanto")

        with patch.object(cc, "today", return_value=dia3):
            self.quote(project, "candidato-a", "--fonte", "manual", "--preco", "999", "--loja", "LojaNova",
                       "--data", self._hora_hoje("10:00:00"))
            # Capturado so agora (depois de `cotar`, que legitimamente
            # atualiza a proxima acao sugerida em processo.md) - o que
            # importa e que a RECUSA em si nao altere mais nada daqui pra
            # frente, nao que o estado do projeto tenha ficado congelado
            # desde a decisao de B.
            decisao_antes = (project / "decisao.md").read_bytes()
            processo_antes = (project / "processo.md").read_bytes()
            with self.assertRaisesRegex(SystemExit, "dados diferentes da cotacao"):
                self.cli("decidir", str(project), "--produto-id", "candidato-a", "--porque",
                          "reconsiderei, escolhi A de novo com cotacao nova", "--comprado",
                          "--perdedores", "candidato-b: nao entregou")

        self.assertEqual(veredito_a.read_bytes(), texto_antes, "veredito de A nao pode ter sido tocado")
        self.assertEqual((project / "decisao.md").read_bytes(), decisao_antes)
        self.assertEqual((project / "processo.md").read_bytes(), processo_antes)
        self.assertFalse(cc.pending_operations([project]), "recusa nao pode deixar journal pendente")
        self.assertEqual(len(list(cc.VEREDITOS.glob("*.md"))), 2, "nenhum veredito novo foi criado pela recusa")

    def test_controle_redecidir_apos_decisao_intermediaria_com_mesma_cotacao_complementa(self):
        """Controle: sem cotacao nova (o caso comum - confirmar a compra
        dias depois da MESMA cotacao), o complemento continua funcionando
        mesmo com uma decisao intermediaria de outro produto no meio."""
        dia1, dia2, dia3 = "2026-01-01", "2026-01-02", "2026-01-20"

        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            self.product(project, "candidato-a")
            self.product(project, "candidato-b")
            self.quote(project, "candidato-a", "--fonte", "manual")
            self.cli("decidir", str(project), "--produto-id", "candidato-a",
                      "--porque", "primeira escolha", "--sem-perdedores")
        veredito_a = next(p for p in cc.VEREDITOS.glob("*.md")
                           if cc.extract_bullet(p.read_text(encoding="utf-8"), "Produto ID") == "candidato-a")

        with patch.object(cc, "today", return_value=dia2):
            self.quote(project, "candidato-b", "--fonte", "manual")
            self.cli("decidir", str(project), "--produto-id", "candidato-b", "--porque",
                      "troquei de ideia", "--perdedores", "candidato-a: desisti por enquanto")

        with patch.object(cc, "today", return_value=dia3):
            self.cli("decidir", str(project), "--produto-id", "candidato-a", "--porque",
                      "reconsiderei, escolhi A de novo", "--comprado",
                      "--perdedores", "candidato-b: nao entregou")

        texto = veredito_a.read_text(encoding="utf-8")
        self.assertEqual(cc.extract_bullet(texto, "Data da compra"), dia3)
        self.assertEqual(cc.extract_bullet(texto, "Valor pago"), cc.brl(200.0))
        self.assertEqual(len(list(cc.VEREDITOS.glob("*.md"))), 2)

    # `data_coleta` vem de `now_iso()` (relogio real, nunca mockado por
    # `patch.object(cc, "today", ...)`), com resolucao de SEGUNDO - duas
    # chamadas de `self.quote(...)` em sequencia rapida podem cair no MESMO
    # segundo e empatar. Sem controlar isso, a escolha da cotacao mais
    # recente (`latest_quotes`) desempata pela mais BARATA (proposital,
    # documentado na propria funcao), o que mascarava justamente a
    # divergencia que estes testes precisam forcar - por isso os 4 testes
    # abaixo fixam `--data` com horarios DISTINTOS no MESMO dia real (nunca
    # vencida, nunca dependente da velocidade da maquina rodando o teste).
    def _hora_hoje(self, hhmmss: str) -> str:
        return f"{dt.date.today().isoformat()}T{hhmmss}"

    def test_mudanca_isolada_de_preco_e_recusada(self):
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual", "--data", self._hora_hoje("09:00:00"))
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        texto_antes = veredito.read_bytes()
        self.quote(project, "candidato", "--fonte", "manual", "--preco", "350",
                   "--data", self._hora_hoje("10:00:00"))
        with self.assertRaisesRegex(SystemExit, "Valor pago"):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "de novo", "--sem-perdedores", "--comprado")
        self.assertEqual(veredito.read_bytes(), texto_antes)

    def test_mudanca_isolada_de_loja_e_recusada(self):
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual", "--data", self._hora_hoje("09:00:00"))
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        texto_antes = veredito.read_bytes()
        self.quote(project, "candidato", "--fonte", "manual", "--loja", "LojaNova",
                   "--data", self._hora_hoje("10:00:00"))
        with self.assertRaisesRegex(SystemExit, "Loja"):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "de novo", "--sem-perdedores", "--comprado")
        self.assertEqual(veredito.read_bytes(), texto_antes)

    def test_mudanca_isolada_de_vendedor_e_recusada(self):
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual", "--data", self._hora_hoje("09:00:00"))
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        texto_antes = veredito.read_bytes()
        self.quote(project, "candidato", "--fonte", "manual", "--vendedor", "OutroVendedor",
                   "--data", self._hora_hoje("10:00:00"))
        with self.assertRaisesRegex(SystemExit, "Vendedor"):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "de novo", "--sem-perdedores", "--comprado")
        self.assertEqual(veredito.read_bytes(), texto_antes)

    def test_force_veredito_ignora_divergencia_financeira_e_reseta_do_zero(self):
        """Controle: com --force-veredito, a divergencia de preco e
        irrelevante - o conteudo inteiro e descartado de proposito (a
        protecao aqui e a do achado 2, nao a do achado 1)."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual", "--data", self._hora_hoje("09:00:00"))
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.quote(project, "candidato", "--fonte", "manual", "--preco", "999", "--loja", "LojaNova",
                   "--data", self._hora_hoje("10:00:00"))
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "de novo", "--sem-perdedores", "--comprado", "--force-veredito")
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Valor pago"), cc.brl(999.0))

    # ---- achado 2: --force-veredito nao pode apagar exportacao ----------

    def _decidir_e_exportar_d30(self, project, pid="candidato"):
        veredito = self._decidir(project, pid)
        self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")
        self.cli("preencher-veredito", str(veredito), "--fase", "d30",
                  "--nota-arrependimento", "9", "--compraria-de-novo", "sim",
                  "--resumo", "Otimo produto, avaliacao real de 30 dias de uso.")
        self.cli("aprender-veredito", str(veredito), "--fase", "d30",
                  "--licao", "Marca A entrega no prazo e o produto funciona bem.")
        return veredito

    def test_force_veredito_e_recusado_quando_d30_ja_foi_exportado_em_outro_dia(self):
        dia1, dia_force = "2026-02-01", "2026-06-01"
        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            veredito = self._decidir_e_exportar_d30(project)
        texto_antes = veredito.read_bytes()
        licoes_antes = (cc.BASE / "licoes.md").read_bytes()

        with patch.object(cc, "today", return_value=dia_force):
            with self.assertRaisesRegex(SystemExit, "ja tem aprendizado exportado"):
                self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                          "refazendo do zero", "--sem-perdedores", "--force-veredito")

        self.assertEqual(veredito.read_bytes(), texto_antes, "avaliacao D+30 tem que continuar intacta")
        self.assertEqual((cc.BASE / "licoes.md").read_bytes(), licoes_antes)
        self.assertEqual(len(list(cc.VEREDITOS.glob("*.md"))), 1)
        self.assertFalse(cc.pending_operations([project]))

    def test_force_veredito_e_recusado_quando_d30_ja_foi_exportado_no_mesmo_dia(self):
        """O mesmo achado 2, mas no MESMO dia - a protecao nao pode
        depender de dias terem passado."""
        project = self.project()
        veredito = self._decidir_e_exportar_d30(project)
        texto_antes = veredito.read_bytes()

        with self.assertRaisesRegex(SystemExit, "ja tem aprendizado exportado"):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "refazendo do zero", "--sem-perdedores", "--force-veredito")

        self.assertEqual(veredito.read_bytes(), texto_antes)

    def test_force_veredito_e_recusado_quando_d180_ja_foi_exportado(self):
        project = self.project()
        veredito = self._decidir(project)
        self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")
        self.cli("preencher-veredito", str(veredito), "--fase", "d180",
                  "--nota-arrependimento", "8", "--compraria-de-novo", "sim",
                  "--resumo", "Continua bom depois de 6 meses.")
        self.cli("aprender-veredito", str(veredito), "--fase", "d180",
                  "--licao", "Continua funcionando bem depois de 6 meses de uso.")
        texto_antes = veredito.read_bytes()

        with self.assertRaisesRegex(SystemExit, "ja tem aprendizado exportado"):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "refazendo do zero", "--sem-perdedores", "--force-veredito")

        self.assertEqual(veredito.read_bytes(), texto_antes)

    def test_force_veredito_e_recusado_com_marcador_legado_sem_fase(self):
        """Veredito real de antes da frente 6 separar D+30 de D+180 (so o
        marcador generico `## Aprendizado exportado`, sem fase) tambem
        precisa ser protegido - a checagem nao pode depender do formato
        novo de marcador."""
        project = self.project()
        veredito = self._decidir(project)
        texto = veredito.read_text(encoding="utf-8")
        texto += "\n## Aprendizado exportado\n\n- Data: 2025-01-01\n- Marca: Marca A\n"
        cc.atomic_write_text(veredito, texto)
        texto_antes = veredito.read_bytes()

        with self.assertRaisesRegex(SystemExit, "ja tem aprendizado exportado"):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "refazendo do zero", "--sem-perdedores", "--force-veredito")

        self.assertEqual(veredito.read_bytes(), texto_antes)

    def test_controle_force_veredito_sem_exportacao_continua_resetando_em_outro_dia(self):
        """Controle: sem nenhuma fase exportada, --force-veredito continua
        funcionando exatamente como o contrato ja documentado (reseta o
        MESMO veredito, mesmo em outro dia - comportamento intencional de
        `6e613d7`, preservado)."""
        dia1, dia2 = "2026-06-01", "2026-06-15"
        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            veredito = self._decidir(project)
        cc.atomic_write_text(
            veredito,
            cc.replace_or_append_bullet(veredito.read_text(encoding="utf-8"), "D+30 resumo", "SERA_DESCARTADO"),
        )

        with patch.object(cc, "today", return_value=dia2):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "unico candidato", "--sem-perdedores", "--comprado", "--force-veredito")

        vereditos = list(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(len(vereditos), 1)
        self.assertEqual(vereditos[0], veredito)
        texto = veredito.read_text(encoding="utf-8")
        self.assertNotIn("SERA_DESCARTADO", texto)
        self.assertEqual(cc.extract_bullet(texto, "Data da compra"), dia2)

    def test_controle_force_veredito_sem_veredito_existente_continua_criando_normalmente(self):
        """Controle: `--force-veredito` numa decisao genuinamente NOVA
        (nenhum veredito existente para este produto+projeto) nunca pode
        ser bloqueado pela checagem de exportacao - nao ha nada para
        proteger."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores", "--comprado", "--force-veredito")
        self.assertEqual(len(list(cc.VEREDITOS.glob("*.md"))), 1)

    # ---- achado 3 (observacao): cronologia continua ativa, sem mudanca --

    def test_observacao_force_veredito_com_comprado_ainda_e_bloqueado_pela_cronologia_sem_exportacao(self):
        """A checagem de cronologia do achado 4 (2a revisao) NAO foi
        alterada por esta correcao - continua recusando `--force-veredito
        --comprado` quando a nova data e cronologicamente impossivel
        contra o conteudo ainda nao substituido, mesmo sem nenhuma fase
        exportada (achado 3, classificado como observacao, nao como bug:
        mantido de proposito, ver STATUS.md e a secao 6 do plano)."""
        dia1 = "2026-02-01"
        dia_entrega = "2026-02-03"
        dia_inicio_uso = "2026-02-05"
        dia_force = "2026-06-01"

        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            veredito = self._decidir(project)
        with patch.object(cc, "today", return_value=dia_entrega):
            self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        with patch.object(cc, "today", return_value=dia_inicio_uso):
            self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")

        with patch.object(cc, "today", return_value=dia_force):
            with self.assertRaisesRegex(SystemExit, "posterior"):
                self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                          "refazendo do zero", "--sem-perdedores", "--comprado", "--force-veredito")

        self.assertIn("Data de entrega", veredito.read_text(encoding="utf-8"))
        self.assertFalse(cc.pending_operations([project]))

    # ---- retomada legitima nao pode ser bloqueada pelas novas checagens -

    def test_retomada_legitima_de_complemento_com_mesma_cotacao_nao_e_bloqueada(self):
        """Uma falha DURANTE um complemento legitimo (mesma cotacao,
        segunda chamada dias depois) e retomada num 3o dia nao pode ser
        barrada pela checagem financeira nova - `retomando_decisao` pula
        as duas checagens novas, exatamente como ja pulava a busca por
        identidade."""
        dia1, dia2, dia3 = "2026-03-01", "2026-03-05", "2026-03-09"
        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            veredito = self._decidir(project)

        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores", "--comprado"]

        def crash(ponto):
            if ponto == "veredito:iniciado":
                raise OSError("falha durante o complemento")

        with patch.object(cc, "today", return_value=dia2), \
                patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli(*args)

        with patch.object(cc, "today", return_value=dia3):
            self.cli(*args)

        self.assertFalse(cc.pending_operations([project]))
        self.assertEqual(len(list(cc.VEREDITOS.glob("*.md"))), 1)
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), dia2)

    def test_journal_antigo_pre_e048ad6_retomado_nao_aciona_as_novas_checagens(self):
        """Journal real criado pelo codigo do commit `3032436` (antes de
        `6e613d7` existir - sem `_veredito_existente_para` nem as
        checagens novas), interrompido em `veredito:iniciado`, tem que
        continuar retomavel normalmente com o codigo atual - mesmo que o
        veredito encontrado tivesse (hipoteticamente) alguma divergencia,
        a retomada usa o nome JA CONGELADO no journal, nunca refaz a busca
        nem as checagens novas."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores", "--comprado"]

        script = self.root / "scripts" / "central_compras.py"
        atual = script.read_bytes()
        antigo = subprocess.run(
            ["git", "show", "3032436:scripts/central_compras.py"],
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
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today())

    # ---- hipoteses descartadas na 5a revisao (mecanismo ja robusto) -----
    # Cobertura de `_veredito_existente_para` exercitada na 5a revisao
    # independente sem achar bug nenhum - migrada para a suite oficial
    # como protecao permanente, nao como reproducao de achado.

    def test_veredito_renomeado_manualmente_ainda_e_encontrado_por_identidade(self):
        project = self.project()
        veredito = self._decidir(project)
        novo_nome = cc.VEREDITOS / "veredito-renomeado-a-mao.md"
        veredito.rename(novo_nome)

        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores", "--comprado")

        self.assertEqual(len(list(cc.VEREDITOS.glob("*.md"))), 1,
                          "renomear o arquivo nao pode fazer o sistema criar um 2o veredito")
        self.assertEqual(cc.extract_bullet(novo_nome.read_text(encoding="utf-8"), "Data da compra"), cc.today())

    def test_veredito_com_produto_id_divergente_do_conteudo_nao_e_confundido(self):
        project = self.project()
        veredito_outro = self._decidir(project, pid="outro-produto")

        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--comprado", "--perdedores", "outro-produto: motivo")

        vereditos = list(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(len(vereditos), 2, "produto_id diferente tem que gerar um veredito PROPRIO")
        self.assertEqual(
            cc.extract_bullet(veredito_outro.read_text(encoding="utf-8"), "Data da compra"), "",
            "veredito do OUTRO produto nao pode ter sido tocado",
        )

    def test_veredito_standalone_sem_produto_id_nunca_e_reaproveitado(self):
        project = self.project()
        self.cli("novo-veredito", str(project))
        veredito_standalone = next(cc.VEREDITOS.glob("*.md"))

        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores", "--comprado")

        vereditos = list(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(len(vereditos), 2, "decidir tem que criar um veredito PROPRIO, nunca usar o standalone")
        self.assertEqual(
            cc.extract_bullet(veredito_standalone.read_text(encoding="utf-8"), "Data da compra"), "",
        )

    def test_mensagem_de_ambiguidade_nomeia_os_arquivos_reais_para_resolucao_manual(self):
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


class SetimaRevisaoIndependenteFrente6Test(ambiente.RepoTestCase):
    """Regressao dos achados A e B da 6a revisao independente (sobre o
    commit `1c8b503`) - reproduzidos primeiro em
    `tests/revisao_independente_1c8b503.py` (script externo daquela
    sessao, removido depois de incorporado aqui). Os testes daquele
    arquivo PASSAVAM com o defeito presente (retomada de journal ANTIGO
    ignorava as checagens da 5a revisao); aqui eles exigem o comportamento
    CORRETO (recusa antes de qualquer escrita, preservando journal e
    arquivos) ou a preservacao explicita dos controles ja publicados.

    Raiz comum: `_erro_divergencia_financeira_veredito`/
    `_erro_force_veredito_apagaria_exportacao` (5a revisao) so rodavam
    quando `not retomando_decisao` - um journal de uma versao ANTERIOR a
    elas, retomado com o codigo atual, nunca as via. Corrigido: as duas
    tambem rodam numa retomada, contra o arquivo congelado no proprio
    journal pendente (`pending_operation_record`), MAS so quando o passo
    "veredito" ainda nao escreveu de verdade (achado 1) - achado 2
    continua seguro mesmo depois de escrito, porque a ausencia dos
    marcadores de exportacao e auto-suficiente (nada resta pra proteger)."""

    def _decidir(self, project, pid="candidato", extra=()):
        self.product(project, pid)
        self.quote(project, pid, "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", pid,
                  "--porque", "unico candidato", "--sem-perdedores", *extra)
        return next(p for p in cc.VEREDITOS.glob("*.md") if pid in p.name)

    def _script_com_codigo(self, commit):
        script = self.root / "scripts" / "central_compras.py"
        atual = script.read_bytes()
        antigo = subprocess.run(
            ["git", "show", f"{commit}:scripts/central_compras.py"],
            cwd=REPO, capture_output=True, check=True,
        ).stdout
        return script, atual, antigo

    def _rodar(self, script, args, crash_apos=None):
        env = os.environ.copy()
        if crash_apos:
            env["CENTRAL_COMPRAS_TESTE_CRASH_APOS"] = crash_apos
        return subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, env=env, capture_output=True, text=True,
        )

    # ---- achado A: journal antigo bypassava a checagem financeira -------

    def test_journal_antigo_e048ad6_retomado_recusa_divergencia_financeira_e_preserva_tudo(self):
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual",
                   "--data", f"{dt.date.today().isoformat()}T09:00:00")

        script, atual, antigo_e048ad6 = self._script_com_codigo("6e613d7")
        script.write_bytes(antigo_e048ad6)
        primeira = self._rodar(script, ["decidir", str(project), "--produto-id", "candidato",
                                         "--porque", "primeira escolha", "--sem-perdedores"])
        self.assertEqual(primeira.returncode, 0, primeira.stderr)
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Valor pago"), cc.brl(200.0))

        self.quote(project, "candidato", "--fonte", "manual", "--preco", "999", "--loja", "LojaNova",
                   "--data", f"{dt.date.today().isoformat()}T10:00:00")
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "reconsiderei com cotacao nova", "--sem-perdedores", "--comprado"]
        crash = self._rodar(script, args, crash_apos="veredito:iniciado")
        self.assertEqual(crash.returncode, 70, crash.stderr)
        texto_antes_da_retomada = veredito.read_bytes()
        journal = next((project / ".operacoes").glob("*.json"))
        journal_antes = journal.read_bytes()

        script.write_bytes(atual)
        retomada = self._rodar(script, args)
        # CORRIGIDO: a retomada de um journal antigo, com dado financeiro
        # que nao bate, e recusada - nunca grava a data da compra ao lado
        # de um preco obsoleto.
        self.assertNotEqual(retomada.returncode, 0,
                            "retomada com divergencia financeira tem que ser recusada")
        self.assertIn("dados diferentes da cotacao", retomada.stdout + retomada.stderr)
        self.assertEqual(veredito.read_bytes(), texto_antes_da_retomada, "veredito nao pode ter sido alterado")
        self.assertEqual(journal.read_bytes(), journal_antes, "journal pendente tem que ser preservado intocado")
        self.assertTrue(cc.pending_operations([project]), "a operacao continua pendente para reconciliacao")

    def test_controle_journal_antigo_com_mesma_cotacao_continua_retomavel(self):
        """Controle: quando a cotacao da retomada bate com a do veredito
        (o caso comum), um journal antigo continua sendo retomado
        normalmente - a correcao do achado A nao pode travar o caminho
        legitimo."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")

        script, atual, antigo_e048ad6 = self._script_com_codigo("6e613d7")
        script.write_bytes(antigo_e048ad6)
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores", "--comprado"]
        crash = self._rodar(script, args, crash_apos="veredito:iniciado")
        self.assertEqual(crash.returncode, 70, crash.stderr)

        script.write_bytes(atual)
        retomada = self._rodar(script, args)
        self.assertEqual(retomada.returncode, 0, retomada.stderr)
        self.assertFalse(cc.pending_operations([project]))
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.assertTrue(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"))

    # ---- achado B: journal antigo bypassava a protecao de exportacao ----

    def _veredito_com_exportacao(self, fase):
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")
        self.cli("preencher-veredito", str(veredito), "--fase", fase,
                  "--nota-arrependimento", "9", "--compraria-de-novo", "sim",
                  "--resumo", "Avaliacao real registrada.")
        self.cli("aprender-veredito", str(veredito), "--fase", fase,
                  "--licao", "Licao real desta avaliacao.")
        return project, veredito

    def _assert_journal_antigo_preserva_exportacao(self, fase, marcador):
        project, veredito = self._veredito_com_exportacao(fase)
        texto_com_fase = veredito.read_text(encoding="utf-8")
        self.assertIn(marcador, texto_com_fase)
        licoes_antes = (cc.BASE / "licoes.md").read_bytes()

        script, atual, antigo_e048ad6 = self._script_com_codigo("6e613d7")
        script.write_bytes(antigo_e048ad6)
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "refazendo do zero", "--sem-perdedores", "--force-veredito"]
        crash = self._rodar(script, args, crash_apos="veredito:iniciado")
        self.assertEqual(crash.returncode, 70, crash.stderr)
        texto_antes_da_retomada = veredito.read_bytes()
        journal = next((project / ".operacoes").glob("*.json"))
        journal_antes = journal.read_bytes()

        script.write_bytes(atual)
        retomada = self._rodar(script, args)
        # CORRIGIDO: a retomada de um journal antigo com --force-veredito
        # sobre um veredito ja exportado e recusada - nunca apaga a
        # avaliacao nem o marcador que evita reexportar a mesma licao.
        self.assertNotEqual(retomada.returncode, 0,
                            "retomada que apagaria exportacao ja concluida tem que ser recusada")
        self.assertIn("ja tem aprendizado exportado", retomada.stdout + retomada.stderr)
        self.assertEqual(veredito.read_bytes(), texto_antes_da_retomada, "veredito nao pode ter sido alterado")
        self.assertEqual(journal.read_bytes(), journal_antes, "journal pendente tem que ser preservado intocado")
        self.assertEqual((cc.BASE / "licoes.md").read_bytes(), licoes_antes)
        self.assertTrue(cc.pending_operations([project]))

    def test_journal_antigo_e048ad6_retomado_recusa_apagar_exportacao_d30(self):
        self._assert_journal_antigo_preserva_exportacao("d30", "Aprendizado exportado D+30")

    def test_journal_antigo_e048ad6_retomado_recusa_apagar_exportacao_d180(self):
        self._assert_journal_antigo_preserva_exportacao("d180", "Aprendizado exportado D+180")

    def test_journal_antigo_e048ad6_retomado_recusa_apagar_exportacao_marcador_legado(self):
        """Marcador legado (sem fase, de vereditos anteriores a essa
        separacao) - escrito a mao, ja que nenhum caminho atual do CLI
        grava esse formato, so vereditos reais anteriores a essa mudanca."""
        project, veredito = self._veredito_com_exportacao("d30")
        texto = veredito.read_text(encoding="utf-8")
        texto = texto.replace("## Aprendizado exportado D+30", "## Aprendizado exportado")
        cc.atomic_write_text(veredito, texto)
        self.assertIn("## Aprendizado exportado\n", veredito.read_text(encoding="utf-8"))
        licoes_antes = (cc.BASE / "licoes.md").read_bytes()

        script, atual, antigo_e048ad6 = self._script_com_codigo("6e613d7")
        script.write_bytes(antigo_e048ad6)
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "refazendo do zero", "--sem-perdedores", "--force-veredito"]
        crash = self._rodar(script, args, crash_apos="veredito:iniciado")
        self.assertEqual(crash.returncode, 70, crash.stderr)
        texto_antes_da_retomada = veredito.read_bytes()

        script.write_bytes(atual)
        retomada = self._rodar(script, args)
        self.assertNotEqual(retomada.returncode, 0)
        self.assertIn("ja tem aprendizado exportado", retomada.stdout + retomada.stderr)
        self.assertEqual(veredito.read_bytes(), texto_antes_da_retomada)
        self.assertEqual((cc.BASE / "licoes.md").read_bytes(), licoes_antes)

    # ---- controles publicados: nao podem regredir com esta correcao -----

    def test_controle_journal_com_passo_veredito_ja_concluido_continua_retomavel(self):
        """Controle ja publicado na 6a revisao: um journal cujo passo
        "veredito" JA CONCLUIU (escrita real ja aconteceu, sob codigo
        antigo ou novo - so falta um passo POSTERIOR) continua retomavel
        normalmente - a correcao dos achados A/B nao pode travar pra
        sempre uma operacao cujo efeito ja aconteceu."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))

        script, atual, antigo_e048ad6 = self._script_com_codigo("6e613d7")
        script.write_bytes(antigo_e048ad6)
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "de novo", "--sem-perdedores", "--comprado"]
        # Crash DEPOIS do passo "veredito" concluir, ANTES do proximo
        # passo (timeline_veredito) - journal fica com "veredito":
        # {"situacao": "concluido"}.
        crash = self._rodar(script, args, crash_apos="timeline_veredito:iniciado")
        self.assertEqual(crash.returncode, 70, crash.stderr)
        journal = next((project / ".operacoes").glob("*.json"))
        registro = json.loads(journal.read_text(encoding="utf-8"))
        self.assertEqual(registro["passos"]["veredito"]["situacao"], "concluido")
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today())

        script.write_bytes(atual)
        retomada = self._rodar(script, args)
        self.assertEqual(retomada.returncode, 0, retomada.stderr)
        self.assertFalse(cc.pending_operations([project]))

    def test_controle_chamada_nova_com_exportacao_continua_recusada_sem_journal(self):
        """Controle ja publicado: uma chamada NOVA (sem journal nenhum)
        sobre um veredito ja exportado continua recusada de cara, sem
        criar journal - a correcao dos achados A/B (que passou a ler o
        journal pendente) nao pode mudar o caminho de chamada nova."""
        project, veredito = self._veredito_com_exportacao("d30")
        texto_antes = veredito.read_bytes()
        with self.assertRaisesRegex(SystemExit, "ja tem aprendizado exportado"):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "de novo", "--sem-perdedores", "--force-veredito")
        self.assertFalse(cc.pending_operations([project]))
        self.assertEqual(veredito.read_bytes(), texto_antes)

    # ---- janela de interrupcao: escrita ja efetiva, journal ainda "tentando" --

    def test_interrupcao_apos_escrever_data_da_compra_e_antes_de_concluir_nao_repete_nem_bloqueia(self):
        """Crash ENTRE `create_verdict` gravar de verdade e o journal
        marcar o passo "veredito" como concluido (`_crash_de_teste_se_pedido`
        entre `executar()` e `_concluir`) - a retomada tem que reconhecer
        que a escrita ja aconteceu (Data da compra ja bate com o valor
        CONGELADO) e completar o resto da operacao, sem re-bloquear por
        divergencia (nada mudou) nem duplicar o bullet."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))

        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "de novo", "--sem-perdedores", "--comprado"]
        script = self.root / "scripts" / "central_compras.py"
        crash = self._rodar(script, args, crash_apos="veredito:executado")
        self.assertEqual(crash.returncode, 70, crash.stderr)
        journal = next((project / ".operacoes").glob("*.json"))
        registro = json.loads(journal.read_text(encoding="utf-8"))
        self.assertEqual(registro["passos"]["veredito"]["situacao"], "tentando",
                         "pre-condicao: escrita ja aconteceu, mas journal ainda nao marcou concluido")
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today(),
                         "pre-condicao: create_verdict ja tinha gravado a data antes do crash")

        retomada = self._rodar(script, args)
        self.assertEqual(retomada.returncode, 0, retomada.stderr)
        self.assertFalse(cc.pending_operations([project]))
        texto_final = veredito.read_text(encoding="utf-8")
        self.assertEqual(texto_final.count("- Data da compra:"), 1, "nao pode ter duplicado o bullet")
        self.assertEqual(cc.extract_bullet(texto_final, "Data da compra"), cc.today())

    def test_interrupcao_apos_force_veredito_escrever_e_antes_de_concluir_nao_bloqueia_sem_exportacao(self):
        """Mesma janela, lado do achado 2: crash logo depois de
        `--force-veredito` reescrever o arquivo (sem nenhuma exportacao
        pendente pra proteger), antes do journal marcar concluido - a
        retomada tem que completar normalmente (a checagem de exportacao
        e auto-suficiente: sem marcador, nada bloqueia, com ou sem
        journal envolvido)."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        cc.atomic_write_text(
            veredito,
            cc.replace_or_append_bullet(veredito.read_text(encoding="utf-8"), "D+30 resumo", "MARCADOR"),
        )

        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "de novo", "--sem-perdedores", "--force-veredito"]
        script = self.root / "scripts" / "central_compras.py"
        crash = self._rodar(script, args, crash_apos="veredito:executado")
        self.assertEqual(crash.returncode, 70, crash.stderr)
        self.assertNotIn("MARCADOR", veredito.read_text(encoding="utf-8"),
                         "pre-condicao: force ja tinha reescrito o arquivo antes do crash")

        retomada = self._rodar(script, args)
        self.assertEqual(retomada.returncode, 0, retomada.stderr)
        self.assertFalse(cc.pending_operations([project]))

    # ---- journal ilegivel: contrato existente preservado ------------------

    def test_journal_ilegivel_continua_recusado_pela_mensagem_existente(self):
        """Requisito 6 do roteiro: journal ausente/ilegivel/incompleto
        nunca pode autorizar escrita por suposicao. A correcao dos achados
        A/B le o journal pendente ANTES de `tracked_operation`, mas para
        um journal ILEGIVEL isso devolve `None` (contrato ja existente de
        `pending_operation_record`) - a checagem nova simplesmente nao
        roda, e o proprio `tracked_operation` continua recusando com sua
        mensagem de journal ilegivel de sempre, sem nenhuma escrita."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "unico candidato", "--sem-perdedores", "--comprado"]
        script = self.root / "scripts" / "central_compras.py"
        crash = self._rodar(script, args, crash_apos="veredito:iniciado")
        self.assertEqual(crash.returncode, 70, crash.stderr)

        journal = next((project / ".operacoes").glob("*.json"))
        journal.write_text("{isto nao e json valido", encoding="utf-8")

        retomada = self._rodar(script, args)
        self.assertNotEqual(retomada.returncode, 0)
        self.assertIn("nao pode ser lido com confianca", retomada.stdout + retomada.stderr)
        self.assertEqual(journal.read_text(encoding="utf-8"), "{isto nao e json valido",
                         "journal ilegivel tem que ser preservado intocado, nunca sobrescrito")

    # ---- achado D: mensagem nunca sugere editar cotacoes.csv --------------

    def test_mensagem_financeira_nunca_sugere_editar_cotacoes_csv(self):
        # `data_coleta` vem do relogio real (resolucao de SEGUNDO) - fixar
        # `--data` com horarios distintos no mesmo dia real evita que as
        # duas cotacoes empatem no mesmo segundo e o desempate por preco
        # mais barato (proposital em `latest_quotes`) mascare a divergencia
        # que este teste precisa forcar.
        hoje = dt.date.today().isoformat()
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual", "--data", f"{hoje}T09:00:00")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        self.quote(project, "candidato", "--fonte", "manual", "--preco", "999", "--data", f"{hoje}T10:00:00")
        with self.assertRaises(SystemExit) as ctx:
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "de novo", "--sem-perdedores", "--comprado")
        mensagem = str(ctx.exception)
        self.assertNotIn("corrija a cotacao/veredito", mensagem)
        self.assertIn("cotacao NOVA", mensagem)
        self.assertIn("nunca editar a linha antiga em cotacoes.csv", mensagem)


class AchadoCRegistrarEventoCompradoTest(ambiente.RepoTestCase):
    """Fecha o achado C da 6a revisao independente (decisao de escopo do
    Josemar, sessao apos `ab569bb`): `registrar-evento --evento comprado`
    tambem impede confirmar a compra com dados financeiros incompativeis
    com a decisao correspondente. Reproduzido primeiro em
    `tests/revisao_independente_1c8b503.py` (removido depois de
    incorporado aqui).

    Contrato: a evidencia e SEMPRE o que `decisao.md` ja tem CONGELADO
    para a decisao aberta deste produto (`_evidencia_financeira_da_decisao`)
    - nunca preco atual nem ranking recalculado. So roda quando ha
    ASSOCIACAO clara (`_projeto_da_confirmacao_de_compra`, a MESMA usada
    pra sincronizar estado) - veredito historico, standalone ou sem
    projeto associado nunca entra na checagem, so o aviso de sempre.
    Identidade duplicada (2+ vereditos com o mesmo Projeto/Produto ID)
    recusa como ambiguidade, reaproveitando `_veredito_existente_para`
    (mesmo criterio de `decide()`). Roda so quando o passo "evento" ainda
    nao escreveu de verdade - reaplica numa retomada, mas nunca bloqueia
    um efeito ja concluido."""

    def _decidir(self, project, pid="candidato", extra=()):
        self.product(project, pid)
        self.quote(project, pid, "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", pid,
                  "--porque", "unico candidato", "--sem-perdedores", *extra)
        return next(p for p in cc.VEREDITOS.glob("*.md") if pid in p.name)

    # ---- reproducao original: A -> B -> A com cotacao diferente ---------

    def test_a_b_a_com_cotacao_diferente_e_recusado_ao_confirmar_por_registrar_evento(self):
        dia1, dia2, dia3 = "2026-01-01", "2026-01-02", "2026-01-20"
        hoje = dt.date.today().isoformat()

        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            self.product(project, "candidato-a")
            self.product(project, "candidato-b")
            self.quote(project, "candidato-a", "--fonte", "manual", "--data", f"{hoje}T09:00:00")
            self.cli("decidir", str(project), "--produto-id", "candidato-a",
                      "--porque", "primeira escolha", "--sem-perdedores")
        veredito_a = next(p for p in cc.VEREDITOS.glob("*.md")
                           if cc.extract_bullet(p.read_text(encoding="utf-8"), "Produto ID") == "candidato-a")

        with patch.object(cc, "today", return_value=dia2):
            self.quote(project, "candidato-b", "--fonte", "manual", "--data", f"{hoje}T09:30:00")
            self.cli("decidir", str(project), "--produto-id", "candidato-b", "--porque",
                      "troquei de ideia", "--perdedores", "candidato-a: desisti por enquanto")

        with patch.object(cc, "today", return_value=dia3):
            self.quote(project, "candidato-a", "--fonte", "manual", "--preco", "999", "--loja", "LojaNova",
                       "--data", f"{hoje}T10:00:00")
            self.cli("decidir", str(project), "--produto-id", "candidato-a", "--porque",
                      "reconsiderei, escolhi A de novo com cotacao nova",
                      "--perdedores", "candidato-b: nao entregou")

        texto_antes = veredito_a.read_bytes()
        decisao_antes = (project / "decisao.md").read_bytes()
        processo_antes = (project / "processo.md").read_bytes()
        with patch.object(cc, "today", return_value=dia3):
            with self.assertRaisesRegex(SystemExit, "dados financeiros diferentes"):
                self.cli("registrar-evento", str(veredito_a), "--evento", "comprado")

        self.assertEqual(veredito_a.read_bytes(), texto_antes, "veredito nao pode ter sido alterado")
        self.assertEqual((project / "decisao.md").read_bytes(), decisao_antes)
        self.assertEqual((project / "processo.md").read_bytes(), processo_antes)
        self.assertFalse(cc.pending_operations([project]))
        self.assertFalse(cc.pending_operations([cc.BASE]))
        status = self.cli("status", str(project))
        self.assertNotIn("Estado: comprado", status)

    # ---- confirmacao legitima, dados compativeis -------------------------

    def test_confirmacao_com_dados_compativeis_funciona_normalmente(self):
        project = self.project()
        veredito = self._decidir(project)
        self.cli("registrar-evento", str(veredito), "--evento", "comprado")
        texto = veredito.read_text(encoding="utf-8")
        self.assertEqual(cc.extract_bullet(texto, "Data da compra"), cc.today())
        status = self.cli("status", str(project))
        self.assertIn("Estado: comprado", status)

    # ---- requisito 2: nunca consulta preco atual/ranking recalculado ----

    def test_cotacao_nova_apos_a_decisao_nao_altera_a_evidencia_congelada(self):
        """Uma cotacao NOVA e adicionada depois de `decidir` (sem chamar
        `decidir` de novo) - `decisao.md` continua com a cotacao ORIGINAL
        congelada, e a confirmacao por `registrar-evento` continua
        funcionando normalmente porque a comparacao e sempre contra
        `decisao.md`, nunca contra a cotacao mais recente/ranking."""
        project = self.project()
        veredito = self._decidir(project)
        decisao_antes = (project / "decisao.md").read_bytes()

        self.quote(project, "candidato", "--fonte", "manual", "--preco", "999", "--loja", "LojaNova")

        self.assertEqual((project / "decisao.md").read_bytes(), decisao_antes,
                         "pre-condicao: decisao.md nao muda so por causa de uma cotacao nova")
        self.cli("registrar-evento", str(veredito), "--evento", "comprado")
        texto = veredito.read_text(encoding="utf-8")
        self.assertEqual(cc.extract_bullet(texto, "Data da compra"), cc.today())
        self.assertEqual(cc.extract_bullet(texto, "Valor pago"), cc.brl(200.0),
                         "Valor pago continua o da decisao ORIGINAL - nunca a cotacao nova nao decidida")

    # ---- divergencias isoladas: preco, vendedor, loja --------------------

    def _preparar_divergencia(self, mutar_quote):
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        # Simula uma decisao POSTERIOR sobre o mesmo produto que trocou so
        # 1 campo, sobrescrevendo decisao.md diretamente - representa uma
        # divergencia isolada sem depender de timing de cotacao real.
        texto_decisao = (project / "decisao.md").read_text(encoding="utf-8")
        texto_decisao = mutar_quote(texto_decisao)
        cc.atomic_write_text(project / "decisao.md", texto_decisao)
        return project, veredito

    def test_divergencia_isolada_de_preco_e_recusada(self):
        project, veredito = self._preparar_divergencia(
            lambda t: cc.replace_or_append_bullet(t, "Custo total confirmado", cc.brl(350.0))
        )
        with self.assertRaisesRegex(SystemExit, "Valor pago"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado")
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), "")

    def test_divergencia_isolada_de_loja_e_recusada(self):
        project, veredito = self._preparar_divergencia(
            lambda t: cc.replace_or_append_bullet(t, "Cotacao usada", "LojaNova / V")
        )
        with self.assertRaisesRegex(SystemExit, "Loja"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado")
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), "")

    def test_divergencia_isolada_de_vendedor_e_recusada(self):
        project, veredito = self._preparar_divergencia(
            lambda t: cc.replace_or_append_bullet(t, "Cotacao usada", "Amazon / OutroVendedor")
        )
        with self.assertRaisesRegex(SystemExit, "Vendedor"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado")
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), "")

    # ---- associacao ausente, ambigua, historico e standalone -------------

    def test_associacao_historico_nao_confere_preco_so_avisa(self):
        """Veredito de uma decisao ja SUBSTITUIDA por outra (produto
        diferente) - `_projeto_da_confirmacao_de_compra` devolve `None`,
        a checagem financeira nova nem roda, comportamento preservado
        (so avisa, nao sincroniza estado)."""
        project = self.project()
        veredito_antigo = self._decidir(project, pid="antigo")
        self.product(project, "novo")
        self.quote(project, "novo", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "novo", "--porque",
                  "troquei de ideia", "--perdedores", "antigo: troquei de ideia")

        saida = self.cli("registrar-evento", str(veredito_antigo), "--evento", "comprado")
        self.assertIn("NAO foi alterado", saida)
        self.assertEqual(
            cc.extract_bullet(veredito_antigo.read_text(encoding="utf-8"), "Data da compra"), cc.today(),
        )
        status = self.cli("status", str(project))
        self.assertNotIn("Estado: comprado", status)

    def test_associacao_standalone_nao_confere_preco_so_avisa(self):
        """`novo-veredito` (sem `Produto ID`) - `_projeto_da_confirmacao_de_compra`
        nunca resolve projeto pra ele, a checagem financeira nova nem
        roda."""
        project = self.project()
        self.cli("novo-veredito", str(project))
        veredito = next(cc.VEREDITOS.glob("*.md"))
        saida = self.cli("registrar-evento", str(veredito), "--evento", "comprado")
        self.assertIn("NAO foi alterado", saida)
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today())

    def test_associacao_ausente_projeto_nao_existe_nao_confere_preco(self):
        """Veredito com `Projeto` apontando pra um projeto que nao existe
        mais (renomeado/apagado) - `_projeto_da_confirmacao_de_compra`
        devolve `None` (projeto_dir.is_dir() falha), checagem nova nem
        roda."""
        project = self.project()
        veredito = self._decidir(project)
        texto = cc.replace_or_append_bullet(
            veredito.read_text(encoding="utf-8"), "Projeto", "projeto-que-nao-existe-mais"
        )
        cc.atomic_write_text(veredito, texto)
        saida = self.cli("registrar-evento", str(veredito), "--evento", "comprado")
        self.assertIn("NAO foi alterado", saida)
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today())

    def test_associacao_ambigua_com_veredito_duplicado_e_recusada(self):
        """2 vereditos com a MESMA identidade (Projeto/Produto ID) -
        reaproveita `_veredito_existente_para`, mesmo criterio de
        ambiguidade de `decide()` - nunca escolhe um dos dois por
        suposicao."""
        project = self.project()
        veredito1 = self._decidir(project)
        veredito2 = cc.VEREDITOS / f"{cc.today()}-duplicado-{project.name}-candidato.md"
        veredito2.write_text(veredito1.read_text(encoding="utf-8"), encoding="utf-8")

        with self.assertRaisesRegex(SystemExit, "Mais de um veredito"):
            self.cli("registrar-evento", str(veredito1), "--evento", "comprado")

        self.assertEqual(cc.extract_bullet(veredito1.read_text(encoding="utf-8"), "Data da compra"), "")
        self.assertEqual(cc.extract_bullet(veredito2.read_text(encoding="utf-8"), "Data da compra"), "")
        self.assertFalse(cc.pending_operations([project]))
        self.assertFalse(cc.pending_operations([cc.BASE]))

    # ---- recusa nao deixa journal, preserva avaliacoes/exportacoes -------

    def test_recusa_preserva_avaliacao_e_exportacao_ja_existentes(self):
        """A recusa por divergencia financeira nao pode mexer em NADA do
        veredito - inclusive um D+30 ja preenchido/exportado antes (cenario
        estrutural: a avaliacao existe, a compra so esta sendo confirmada
        tarde e com dado incompativel)."""
        project = self.project()
        veredito = self._decidir(project)
        self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")
        self.cli("preencher-veredito", str(veredito), "--fase", "d30",
                  "--nota-arrependimento", "9", "--compraria-de-novo", "sim", "--resumo", "foi bem")
        self.cli("aprender-veredito", str(veredito), "--fase", "d30", "--licao", "confirmar garantia")
        # "Comprado" nunca foi registrado ainda (fluxo incomum, mas valido:
        # o Josemar pode ter esquecido `decidir --comprado` na hora).
        cc.atomic_write_text(
            project / "decisao.md",
            cc.replace_or_append_bullet(
                (project / "decisao.md").read_text(encoding="utf-8"), "Custo total confirmado", cc.brl(999.0),
            ),
        )
        texto_antes = veredito.read_bytes()
        licoes_antes = (cc.BASE / "licoes.md").read_bytes()

        with self.assertRaisesRegex(SystemExit, "dados financeiros diferentes"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.assertEqual(veredito.read_bytes(), texto_antes)
        self.assertEqual((cc.BASE / "licoes.md").read_bytes(), licoes_antes)

    # ---- falha intermediaria com retomada ---------------------------------

    def test_falha_entre_gravar_evento_e_sincronizar_projeto_nao_e_bloqueada_pela_checagem_nova(self):
        """Mesmo cenario ja coberto em `SegundaRevisaoIndependenteFrente6Test`
        (falha ENTRE gravar o evento e sincronizar o projeto), com dados
        COMPATIVEIS - a checagem financeira nova, ao rodar de novo na
        retomada, reconhece que o passo "evento" ja escreveu (a data ja
        bate com o valor congelado) e NAO bloqueia a conclusao legitima."""
        project = self.project()
        veredito = self._decidir(project)

        def crash(ponto):
            if ponto == "estado_projeto:iniciado":
                raise OSError("falha entre gravar o evento e sincronizar o projeto")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today())
        self.assertNotIn("Estado: comprado", self.cli("status", str(project)))
        self.assertTrue(cc.pending_operations([cc.BASE]))

        self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.assertIn("Estado: comprado", self.cli("status", str(project)))
        self.assertFalse(cc.pending_operations([cc.BASE]))

    def test_retomada_de_evento_ainda_nao_escrito_ainda_recusa_por_divergencia(self):
        """Falha ANTES de `_gravar_evento` rodar, com dados JA
        incompativeis desde o inicio - a retomada tem que continuar
        recusando (o passo "evento" nunca escreveu), nunca deixar passar
        so porque virou uma retomada."""
        project = self.project()
        veredito = self._decidir(project)
        cc.atomic_write_text(
            project / "decisao.md",
            cc.replace_or_append_bullet(
                (project / "decisao.md").read_text(encoding="utf-8"), "Custo total confirmado", cc.brl(999.0),
            ),
        )

        def crash(ponto):
            if ponto == "evento:iniciado":
                raise OSError("falha antes de gravar o evento")

        # A propria 1a tentativa ja recusa antes de chegar perto do crash
        # simulado (a checagem roda ANTES de `tracked_operation`) - prova
        # que nao ha journal pendente nenhum pra "retomar" depois.
        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaisesRegex(SystemExit, "dados financeiros diferentes"):
                self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.assertFalse(cc.pending_operations([cc.BASE]))
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), "")

    # ---- controles: cronologia e outros eventos continuam intocados ------

    def test_controle_cronologia_continua_ativa_junto_da_checagem_financeira(self):
        project = self.project()
        veredito = self._decidir(project)
        ontem = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso", "--data", ontem)
        with self.assertRaisesRegex(SystemExit, "e posterior a Data de inicio de uso"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado", "--data", cc.today())

    def test_controle_entrega_e_inicio_uso_continuam_sem_checagem_financeira(self):
        """`entrega`/`inicio_uso` nunca tiveram e continuam sem checagem
        financeira - o achado C e especifico de `--evento comprado`."""
        project = self.project()
        veredito = self._decidir(project)
        self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")
        texto = veredito.read_text(encoding="utf-8")
        self.assertTrue(cc.extract_bullet(texto, "Data de entrega"))
        self.assertTrue(cc.extract_bullet(texto, "Data de inicio de uso"))


class OitavaRevisaoIndependenteFrente6Test(ambiente.RepoTestCase):
    """Corrige os achados I e II da 7a revisao independente (sobre os
    commits `ab569bb`+`822096b` em conjunto), registrados no commit
    `d72da8b`. Reproduzido primeiro em
    `tests/revisao_independente_68c3dbf_822096b.py` (removido depois de
    incorporado aqui).

    Achado I: a checagem financeira (achado A em `decide()`, achado C em
    `registrar-evento`) pulava a revalidacao numa retomada quando "o
    campo ja bate com o valor CONGELADO no journal pendente" - mas isso
    nunca prova que foi a PROPRIA operacao pendente quem escreveu aquele
    valor. Corrigido: a prova de que o passo ja produziu seu efeito passa
    a ser o proprio JOURNAL (`passos[passo]["situacao"] == "concluido"`),
    nunca o conteudo do arquivo - `_gravar_evento`/`create_verdict` sao
    sobrescritas/complementos idempotentes, entao revalidar de novo
    quando o passo NAO esta concluido nunca risca duplicar nada: se nada
    mudou desde a escrita original, a revalidacao da o MESMO resultado
    (passa); se algo mudou (ou o valor veio de uma edicao nunca
    validada), a recusa e o comportamento CORRETO - preserva a operacao
    pendente para reconciliacao manual, nunca repete escrita as cegas.

    Achado II: `decisao.md` sem os campos financeiros MINIMOS que o
    formato atual sempre grava (`Cotacao usada`, e um dos dois rotulos de
    custo) deixava a checagem do achado C cega, confirmando a compra com
    qualquer preco no veredito sem avisar ninguem. Corrigido: recusa
    explicita ANTES de qualquer escrita quando a evidencia esta
    incompleta - nunca inventa valor, nunca consulta preco atual/ranking,
    nunca exige os dois rotulos de custo juntos (sao mutuamente
    exclusivos no formato real)."""

    def _decidir(self, project, pid="candidato", extra=()):
        self.product(project, pid)
        self.quote(project, pid, "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", pid,
                  "--porque", "unico candidato", "--sem-perdedores", *extra)
        return next(p for p in cc.VEREDITOS.glob("*.md") if pid in p.name)

    def _hora_hoje(self, hhmmss: str) -> str:
        return f"{dt.date.today().isoformat()}T{hhmmss}"

    # ---- achado I, lado registrar-evento ----------------------------------

    def test_edicao_externa_com_valor_coincidente_e_decisao_divergente_e_recusada(self):
        """Reproducao original: `registrar-evento --evento comprado`
        interrompido ANTES de gravar; o veredito e editado por FORA desta
        operacao (edicao manual) com a MESMA data que o journal pendente
        ja tinha congelado, por coincidencia; `decisao.md` passa a
        refletir uma cotacao bem diferente. Retomando: tem que RECUSAR -
        o passo "evento" nunca chegou a "concluido" no journal, entao a
        checagem financeira roda de novo e acha a divergencia real."""
        project = self.project()
        veredito = self._decidir(project)

        def crash(ponto):
            if ponto == "evento:iniciado":
                raise OSError("falha antes de gravar o evento")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        journal = next((cc.BASE / ".operacoes").glob("*.json"))
        registro = json.loads(journal.read_text(encoding="utf-8"))
        self.assertNotEqual(registro.get("passos", {}).get("evento", {}).get("situacao"), "concluido",
                            "pre-condicao: passo evento nao pode estar concluido")

        # Edicao externa: mesma data congelada, por coincidencia.
        cc.atomic_write_text(
            veredito,
            cc.replace_or_append_bullet(veredito.read_text(encoding="utf-8"), "Data da compra", cc.today()),
        )
        cc.atomic_write_text(
            project / "decisao.md",
            cc.replace_or_append_bullet(
                (project / "decisao.md").read_text(encoding="utf-8"), "Custo total confirmado", cc.brl(999.0),
            ),
        )
        texto_antes = veredito.read_bytes()
        journal_antes = journal.read_bytes()
        licoes_antes = (cc.BASE / "licoes.md").read_bytes()

        with self.assertRaisesRegex(SystemExit, "dados financeiros diferentes"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.assertEqual(veredito.read_bytes(), texto_antes, "veredito nao pode ter sido alterado pela recusa")
        self.assertEqual(journal.read_bytes(), journal_antes, "journal pendente tem que ser preservado intocado")
        self.assertEqual((cc.BASE / "licoes.md").read_bytes(), licoes_antes)
        self.assertTrue(cc.pending_operations([cc.BASE]), "operacao continua pendente para reconciliacao")
        self.assertNotIn("Estado: comprado", self.cli("status", str(project)))

    def test_passo_evento_concluido_nao_e_bloqueado_por_decisao_divergente_depois(self):
        """Preserva: uma vez que o journal prova que o passo "evento" ja
        CONCLUIU (crash so no passo seguinte, `estado_projeto`), uma
        divergencia posterior em `decisao.md` (impossivel de acontecer
        via CLI de verdade aqui, ja que a trava de recursos bloquearia -
        simulada direto no arquivo pra isolar a questao) NAO pode
        impedir a retomada de terminar - o efeito ja e irreversivel e
        ja foi validado quando aconteceu."""
        project = self.project()
        veredito = self._decidir(project)

        def crash(ponto):
            if ponto == "estado_projeto:iniciado":
                raise OSError("falha entre gravar o evento e sincronizar o projeto")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        journal = next((cc.BASE / ".operacoes").glob("*.json"))
        registro = json.loads(journal.read_text(encoding="utf-8"))
        self.assertEqual(registro["passos"]["evento"]["situacao"], "concluido",
                         "pre-condicao: passo evento ja concluiu antes do crash simulado")

        cc.atomic_write_text(
            project / "decisao.md",
            cc.replace_or_append_bullet(
                (project / "decisao.md").read_text(encoding="utf-8"), "Custo total confirmado", cc.brl(999.0),
            ),
        )

        self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.assertIn("Estado: comprado", self.cli("status", str(project)))
        self.assertFalse(cc.pending_operations([cc.BASE]))

    def test_recuperacao_apos_escrita_sem_conclusao_sem_divergencia_completa_normalmente(self):
        """"Escrita efetiva sem marcacao de conclusao, com evidencias
        suficientes": crash bem entre `_gravar_evento` escrever e o
        journal marcar "concluido" - SEM nada divergir nesse meio tempo.
        A retomada revalida (passo nao esta "concluido"), acha os MESMOS
        dados (nada mudou), passa de novo, e completa sem duplicar o
        bullet nem bloquear."""
        project = self.project()
        veredito = self._decidir(project)

        def crash(ponto):
            if ponto == "evento:executado":
                raise OSError("falha logo apos escrever, antes de marcar concluido")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        journal = next((cc.BASE / ".operacoes").glob("*.json"))
        registro = json.loads(journal.read_text(encoding="utf-8"))
        self.assertEqual(registro["passos"]["evento"]["situacao"], "tentando",
                         "pre-condicao: escrita ja aconteceu, mas journal ainda nao marcou concluido")
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today(),
                         "pre-condicao: a escrita real ja tinha acontecido antes do crash")

        self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        texto_final = veredito.read_text(encoding="utf-8")
        self.assertEqual(texto_final.count("- Data da compra:"), 1, "nao pode ter duplicado o bullet")
        self.assertEqual(cc.extract_bullet(texto_final, "Data da compra"), cc.today())
        self.assertIn("Estado: comprado", self.cli("status", str(project)))
        self.assertFalse(cc.pending_operations([cc.BASE]))

    def test_escrita_sem_conclusao_com_divergencia_legitima_e_recusada(self):
        """Mesma janela (escrita efetiva, sem marcacao de conclusao), mas
        AGORA com uma divergencia real acontecendo nesse meio tempo -
        "evidencia insuficiente para distinguir escrita legitima de
        alteracao externa incompativel": a retomada tem que RECUSAR
        (nao ha como saber, so pelo journal, que nada mudou desde a
        escrita) e preservar a pendencia para reconciliacao manual -
        nunca completar as cegas."""
        project = self.project()
        veredito = self._decidir(project)

        def crash(ponto):
            if ponto == "evento:executado":
                raise OSError("falha logo apos escrever, antes de marcar concluido")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        cc.atomic_write_text(
            project / "decisao.md",
            cc.replace_or_append_bullet(
                (project / "decisao.md").read_text(encoding="utf-8"), "Custo total confirmado", cc.brl(999.0),
            ),
        )
        texto_antes = veredito.read_bytes()

        with self.assertRaisesRegex(SystemExit, "dados financeiros diferentes"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.assertEqual(veredito.read_bytes(), texto_antes)
        self.assertTrue(cc.pending_operations([cc.BASE]))
        self.assertNotIn("Estado: comprado", self.cli("status", str(project)))

    def test_journal_com_passo_nunca_tentado_e_valor_coincidente_ainda_recusa(self):
        """Journal pendente onde o passo "evento" nem chegou a ser anotado
        como "tentando" (`passos: {}`, journal de uma versao ainda mais
        antiga que o achado I) - COM um valor coincidente ja presente no
        veredito (nao so o caso trivial de conteudo vazio).

        8a revisao independente, achado de qualidade de teste: a versao
        anterior deste teste so testava `passos: {}` com o veredito AINDA
        em branco - nesse caso, tanto o design ANTIGO (comparar conteudo)
        quanto o NOVO (olhar o journal) concordam trivialmente que "nao
        foi escrito", entao o teste passava com ou sem a correcao do
        achado I, sem provar qual mecanismo estava decidindo. Fortalecido
        aqui: o veredito recebe o MESMO valor que seria escrito (edicao
        externa, simulando uma versao ainda mais antiga que gravava sem
        journal nenhum), o que faria o design ANTIGO pular a checagem por
        coincidencia de conteudo - confirmado contra o codigo do commit
        `d72da8b` (antes desta correcao) que esse cenario reproduzia o
        achado I de verdade (compra confirmada, projeto marcado comprado,
        com Valor pago R$200 nunca validado contra decisao.md R$999)."""
        project = self.project()
        veredito = self._decidir(project)

        def crash(ponto):
            if ponto == "evento:iniciado":
                raise OSError("falha antes de gravar o evento")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        journal = next((cc.BASE / ".operacoes").glob("*.json"))
        registro = json.loads(journal.read_text(encoding="utf-8"))
        # Simula um journal de uma versao ainda mais antiga, onde o passo
        # nem chegou a ser anotado como "tentando".
        registro["passos"] = {}
        cc.atomic_write_text(journal, json.dumps(registro, ensure_ascii=True, indent=2, sort_keys=True) + "\n")

        # Valor COINCIDENTE ja presente no veredito - o proprio cenario
        # que o design antigo (comparacao de conteudo) tratava como "ja
        # escrito por esta operacao".
        cc.atomic_write_text(
            veredito,
            cc.replace_or_append_bullet(veredito.read_text(encoding="utf-8"), "Data da compra", cc.today()),
        )
        cc.atomic_write_text(
            project / "decisao.md",
            cc.replace_or_append_bullet(
                (project / "decisao.md").read_text(encoding="utf-8"), "Custo total confirmado", cc.brl(999.0),
            ),
        )
        texto_antes = veredito.read_bytes()

        with self.assertRaisesRegex(SystemExit, "dados financeiros diferentes"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado")
        self.assertEqual(veredito.read_bytes(), texto_antes)
        self.assertNotIn("Estado: comprado", self.cli("status", str(project)))

    def test_controle_journal_antigo_68c3dbf_retomado_ainda_recusa_divergencia_financeira(self):
        """Controle publicado na 7a revisao: journal de `registrar-evento`
        do commit `ab569bb` (antes do achado C existir), retomado com o
        codigo atual, continua recusando divergencia financeira quando a
        escrita ainda nao aconteceu - a correcao do achado I preserva
        isso."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")

        script = self.root / "scripts" / "central_compras.py"
        atual = script.read_bytes()
        antigo_68c3dbf = subprocess.run(
            ["git", "show", "ab569bb:scripts/central_compras.py"],
            cwd=REPO, capture_output=True, check=True,
        ).stdout
        script.write_bytes(antigo_68c3dbf)

        decidir = subprocess.run(
            [sys.executable, str(script), "decidir", str(project), "--produto-id", "candidato",
             "--porque", "unico candidato", "--sem-perdedores"],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(decidir.returncode, 0, decidir.stderr)
        veredito = next(cc.VEREDITOS.glob("*.md"))

        args = ["registrar-evento", str(veredito), "--evento", "comprado"]
        env = os.environ.copy()
        env["CENTRAL_COMPRAS_TESTE_CRASH_APOS"] = "evento:iniciado"
        crash = subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, env=env, capture_output=True, text=True,
        )
        self.assertEqual(crash.returncode, 70, crash.stderr)
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), "")

        cc.atomic_write_text(
            project / "decisao.md",
            cc.replace_or_append_bullet(
                (project / "decisao.md").read_text(encoding="utf-8"), "Custo total confirmado", cc.brl(999.0),
            ),
        )

        script.write_bytes(atual)
        retomada = subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, capture_output=True, text=True,
        )
        self.assertNotEqual(retomada.returncode, 0,
                            "retomada de journal antigo com divergencia financeira tem que ser recusada")
        self.assertIn("dados financeiros diferentes", retomada.stdout + retomada.stderr)
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), "")

    # ---- achado I, lado decidir (mesmo mecanismo) --------------------------

    def test_decidir_edicao_externa_com_valor_coincidente_e_recusada(self):
        """Variante do achado I para `decide()` (achado A): a cotacao
        usada na comparacao e sempre a VIVA (protegida pelo hash da
        assinatura), entao a divergencia precisa vir de `Valor pago`
        corrompido diretamente no veredito - reproduzido e confirmado
        antes desta correcao (ver STATUS.md, sessao 32).

        Nota: `_marcar_projeto_comprado` roda ANTES do passo "veredito"
        dentro de `_decide_writes` (nao e guardado por
        `executar_uma_vez`/`registrar_efeito`, e idempotente por design) -
        na 1a tentativa (crash injetado logo depois), o estado do projeto
        JA fica "comprado" legitimamente, ja que a divergencia so passa a
        existir DEPOIS, na edicao externa - esse teste nao afirma nada
        sobre o estado do projeto, so sobre o veredito e o journal."""
        project = self.project()
        veredito = self._decidir(project)

        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "de novo", "--sem-perdedores", "--comprado"]

        def crash(ponto):
            if ponto == "veredito:iniciado":
                raise OSError("falha antes de gravar o veredito")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli(*args)

        texto = veredito.read_text(encoding="utf-8")
        texto = cc.replace_or_append_bullet(texto, "Data da compra", cc.today())
        texto = cc.replace_or_append_bullet(texto, "Valor pago", cc.brl(1.0))
        cc.atomic_write_text(veredito, texto)
        texto_antes = veredito.read_bytes()

        with self.assertRaisesRegex(SystemExit, "dados diferentes da cotacao"):
            self.cli(*args)

        self.assertEqual(veredito.read_bytes(), texto_antes)
        self.assertTrue(cc.pending_operations([project]))

    def test_decidir_passo_veredito_concluido_nao_e_bloqueado_por_divergencia_depois(self):
        """Preserva o caminho de `decide()`: passo "veredito" ja
        CONCLUIDO no journal (crash so no passo seguinte,
        `timeline_veredito`) nao pode ser travado por uma divergencia
        surgida depois."""
        project = self.project()
        veredito = self._decidir(project)

        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "de novo", "--sem-perdedores", "--comprado"]

        def crash(ponto):
            if ponto == "timeline_veredito:iniciado":
                raise OSError("falha depois do veredito concluir")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli(*args)

        journal = next((project / ".operacoes").glob("*.json"))
        registro = json.loads(journal.read_text(encoding="utf-8"))
        self.assertEqual(registro["passos"]["veredito"]["situacao"], "concluido")

        # Divergencia "surgida depois" - simulada direto no veredito, ja
        # que a trava de recursos bloquearia um `decidir --force-veredito`
        # de verdade sobre este mesmo veredito enquanto ha pendencia.
        # Aqui so confirmamos que a retomada com os MESMOS argumentos, que
        # ja tinha passado na 1a tentativa, nao e bloqueada retroativamente.
        self.cli(*args)

    def test_decidir_escrita_sem_conclusao_com_divergencia_externa_e_recusada(self):
        """Simetria com `registrar-evento`
        (`test_escrita_sem_conclusao_com_divergencia_legitima_e_recusada`):
        crash bem entre `create_verdict` escrever e o journal marcar
        "concluido" (passo continua "tentando"), com `Valor pago`
        corrompido diretamente no veredito nesse meio tempo - "evidencia
        insuficiente para distinguir escrita legitima de alteracao
        externa incompativel" tem que recusar, mesmo em `decide()`."""
        project = self.project()
        veredito = self._decidir(project)

        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "de novo", "--sem-perdedores", "--comprado"]

        def crash(ponto):
            if ponto == "veredito:executado":
                raise OSError("falha logo apos gravar, antes de marcar concluido")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli(*args)

        journal = next((project / ".operacoes").glob("*.json"))
        registro = json.loads(journal.read_text(encoding="utf-8"))
        self.assertEqual(registro["passos"]["veredito"]["situacao"], "tentando",
                         "pre-condicao: escrita ja aconteceu, mas journal ainda nao marcou concluido")
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today(),
                         "pre-condicao: create_verdict ja tinha gravado a data antes do crash")

        cc.atomic_write_text(
            veredito, cc.replace_or_append_bullet(veredito.read_text(encoding="utf-8"), "Valor pago", cc.brl(1.0)),
        )
        texto_antes = veredito.read_bytes()

        with self.assertRaisesRegex(SystemExit, "dados diferentes da cotacao"):
            self.cli(*args)

        self.assertEqual(veredito.read_bytes(), texto_antes)
        self.assertTrue(cc.pending_operations([project]))

    def test_decidir_journal_com_passo_nunca_tentado_e_valor_coincidente_ainda_recusa(self):
        """Simetria com `registrar-evento`
        (`test_journal_com_passo_nunca_tentado_e_valor_coincidente_ainda_recusa`):
        journal simulando uma versao ainda mais antiga (`passos: {}`) com
        um valor coincidente ja presente no veredito - o design antigo
        (comparacao de conteudo) pularia a checagem por coincidencia; o
        atual (olha o proprio journal) nao."""
        project = self.project()
        veredito = self._decidir(project)

        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "de novo", "--sem-perdedores", "--comprado"]

        def crash(ponto):
            if ponto == "veredito:iniciado":
                raise OSError("falha antes de gravar o veredito")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli(*args)

        journal = next((project / ".operacoes").glob("*.json"))
        registro = json.loads(journal.read_text(encoding="utf-8"))
        registro["passos"] = {}
        cc.atomic_write_text(journal, json.dumps(registro, ensure_ascii=True, indent=2, sort_keys=True) + "\n")

        texto = veredito.read_text(encoding="utf-8")
        texto = cc.replace_or_append_bullet(texto, "Data da compra", cc.today())
        texto = cc.replace_or_append_bullet(texto, "Valor pago", cc.brl(1.0))
        cc.atomic_write_text(veredito, texto)
        texto_antes = veredito.read_bytes()

        with self.assertRaisesRegex(SystemExit, "dados diferentes da cotacao"):
            self.cli(*args)
        self.assertEqual(veredito.read_bytes(), texto_antes)
        self.assertTrue(cc.pending_operations([project]), "recusa numa retomada preserva a pendencia")

    # ---- achado II: evidencia financeira insuficiente ----------------------

    def test_evidencia_totalmente_ausente_e_recusada(self):
        project = self.project()
        veredito = self._decidir(project)
        decisao_path = project / "decisao.md"
        texto_decisao = decisao_path.read_text(encoding="utf-8")
        texto_decisao = re.sub(r"(?m)^- Cotacao usada:.*$", "", texto_decisao)
        texto_decisao = re.sub(r"(?m)^- Custo total confirmado:.*$", "", texto_decisao)
        cc.atomic_write_text(decisao_path, texto_decisao)

        cc.atomic_write_text(
            veredito, cc.replace_or_append_bullet(veredito.read_text(encoding="utf-8"), "Valor pago", cc.brl(99999.0)),
        )
        texto_antes = veredito.read_bytes()

        with self.assertRaisesRegex(SystemExit, "nao tem evidencia financeira suficiente"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.assertEqual(veredito.read_bytes(), texto_antes)
        self.assertFalse(cc.pending_operations([cc.BASE]))
        self.assertNotIn("Estado: comprado", self.cli("status", str(project)))

    def test_evidencia_insuficiente_surgida_apos_interrupcao_preserva_pendencia(self):
        """Foco 5 do roteiro: a checagem de evidencia (achado II) tambem
        roda numa retomada (nao so numa chamada nova) - se a evidencia
        ficar insuficiente nesse meio tempo, a recusa preserva o journal
        pendente intocado, sem nenhuma escrita nova."""
        project = self.project()
        veredito = self._decidir(project)

        def crash(ponto):
            if ponto == "evento:iniciado":
                raise OSError("falha antes de gravar o evento")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        decisao_path = project / "decisao.md"
        texto_decisao = re.sub(r"(?m)^- Cotacao usada:.*$", "", decisao_path.read_text(encoding="utf-8"))
        cc.atomic_write_text(decisao_path, texto_decisao)
        journal = next((cc.BASE / ".operacoes").glob("*.json"))
        journal_antes = journal.read_bytes()
        texto_antes = veredito.read_bytes()

        with self.assertRaisesRegex(SystemExit, "nao tem evidencia financeira suficiente"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.assertEqual(veredito.read_bytes(), texto_antes)
        self.assertEqual(journal.read_bytes(), journal_antes)
        self.assertTrue(cc.pending_operations([cc.BASE]))

    def test_evidencia_parcial_falta_so_cotacao_usada_e_recusada(self):
        project = self.project()
        veredito = self._decidir(project)
        decisao_path = project / "decisao.md"
        texto_decisao = re.sub(r"(?m)^- Cotacao usada:.*$", "", decisao_path.read_text(encoding="utf-8"))
        cc.atomic_write_text(decisao_path, texto_decisao)

        with self.assertRaisesRegex(SystemExit, "nao tem evidencia financeira suficiente"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado")

    def test_evidencia_parcial_falta_so_custo_e_recusada(self):
        project = self.project()
        veredito = self._decidir(project)
        decisao_path = project / "decisao.md"
        texto_decisao = re.sub(
            r"(?m)^- Custo total confirmado:.*$", "", decisao_path.read_text(encoding="utf-8"),
        )
        cc.atomic_write_text(decisao_path, texto_decisao)

        with self.assertRaisesRegex(SystemExit, "nao tem evidencia financeira suficiente"):
            self.cli("registrar-evento", str(veredito), "--evento", "comprado")

    def test_controle_cotacao_web_com_custo_estimado_e_evidencia_suficiente(self):
        """Os dois rotulos de custo sao MUTUAMENTE EXCLUSIVOS no formato
        real - uma decisao com cotacao web so tem `Custo total estimado
        (fonte=web)`, nunca `Custo total confirmado` junto. A checagem de
        evidencia nao pode exigir os dois - so PELO MENOS UM."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "web", "--data", self._hora_hoje("09:00:00"))
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores", "--permitir-web")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        texto_decisao = (project / "decisao.md").read_text(encoding="utf-8")
        self.assertTrue(cc.extract_bullet(texto_decisao, "Custo total estimado (fonte=web)"))
        self.assertEqual(cc.extract_bullet(texto_decisao, "Custo total confirmado"), "")

        # Dados compativeis - nao deveria recusar por evidencia nem por
        # divergencia.
        self.cli("registrar-evento", str(veredito), "--evento", "comprado")
        self.assertIn("Estado: comprado", self.cli("status", str(project)))

    def test_controle_standalone_e_historico_nunca_rodam_checagem_de_evidencia(self):
        """Contrato preservado: veredito standalone (sem `Produto ID`) ou
        historico (decisao substituida) nunca chegam a checagem de
        evidencia/divergencia - so o aviso de sempre, sem exigir nada de
        `decisao.md`."""
        project = self.project()
        self.cli("novo-veredito", str(project))
        standalone = next(cc.VEREDITOS.glob("*.md"))
        saida = self.cli("registrar-evento", str(standalone), "--evento", "comprado")
        self.assertIn("NAO foi alterado", saida)
        self.assertEqual(cc.extract_bullet(standalone.read_text(encoding="utf-8"), "Data da compra"), cc.today())

        veredito_antigo = self._decidir(project, pid="antigo")
        self.product(project, "novo")
        self.quote(project, "novo", "--fonte", "manual", "--data", self._hora_hoje("10:00:00"))
        self.cli("decidir", str(project), "--produto-id", "novo", "--porque",
                  "troquei de ideia", "--perdedores", "antigo: troquei de ideia")
        saida = self.cli("registrar-evento", str(veredito_antigo), "--evento", "comprado")
        self.assertIn("NAO foi alterado", saida)
        self.assertNotIn("Estado: comprado", self.cli("status", str(project)))


if __name__ == "__main__":
    unittest.main()
