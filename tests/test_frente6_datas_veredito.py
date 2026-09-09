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
import unittest
from unittest.mock import patch

import ambiente
from scripts import central_compras as cc


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


if __name__ == "__main__":
    unittest.main()
