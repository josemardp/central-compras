"""Recuperacao de operacoes de varios arquivos interrompidas no meio (journal).

Reproduz os achados da auditoria de 06/09/2026 e da segunda revisao (Codex,
sobre o commit 83c0901) sobre `decidir` e `aprender-veredito`:

1. licao duplicada com "sucesso aparente" - falha entre gravar e confirmar
   o passo no journal;
2. marcador gravado que travava a recuperacao atras da guarda de "ja
   exportado";
3. `decidir` criando um segundo snapshot (orfao) a cada retry.

Cada bug tem um teste que reproduz o cenario exato relatado, mais testes de
retomada incompativel, journal corrompido/malformado, interrupcao real de
subprocesso e concorrencia com as travas existentes.
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ambiente
from scripts import central_compras as cc


class OperationRecoveryTest(ambiente.RepoTestCase):
    def _abrir_candidato(self, project):
        self.product(project)
        self.quote(project, "candidato", "--fonte", "manual")

    def _decidir(self, project, **overrides):
        args = ["decidir", str(project), "--produto-id", "candidato",
                "--porque", overrides.pop("porque", "unico candidato"),
                "--sem-perdedores", "--comprado"]
        return self.cli(*args)

    def _fechar_com_veredito(self, project):
        self._abrir_candidato(project)
        self._decidir(project)
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.cli("preencher-veredito", str(veredito), "--fase", "d30",
                 "--resumo", "foi bem", "--licao", "conferir estoque antes",
                 "--nota-arrependimento", "1", "--compraria-de-novo", "sim")
        return veredito

    # ---- Bug 1: licao duplicada com sucesso aparente -----------------------

    def test_bug1_licao_duplicada_se_falhar_apos_gravar_antes_de_confirmar(self):
        veredito = self._fechar_com_veredito(self.project())

        # Simula exatamente a janela relatada: o efeito (append_text da
        # licao) ja aconteceu, e a falha ocorre so na confirmacao do passo
        # no journal - antes desta correcao, o retry repetia register_lesson
        # porque o journal nunca chegou a saber que "licao" tinha sido feita.
        real_concluir = cc.OperationHandle._concluir

        def falha_ao_confirmar(self_op, passo):
            if passo == "licao":
                raise RuntimeError("crash simulado apos gravar, antes de confirmar")
            return real_concluir(self_op, passo)

        with patch.object(cc.OperationHandle, "_concluir", falha_ao_confirmar):
            with self.assertRaises(RuntimeError):
                self.cli("aprender-veredito", str(veredito))

        licoes = (cc.BASE / "licoes.md").read_text(encoding="utf-8")
        self.assertEqual(licoes.count("conferir estoque antes"), 1,
                         "a licao ja devia ter sido gravada pela tentativa que falhou")
        pendentes = cc.pending_operations([cc.BASE])
        self.assertEqual(len(pendentes), 1)

        # Retry sem falha: reconcilia pelo conteudo real, nao duplica.
        self.cli("aprender-veredito", str(veredito))
        licoes = (cc.BASE / "licoes.md").read_text(encoding="utf-8")
        self.assertEqual(licoes.count("conferir estoque antes"), 1,
                         "BUG 1: a licao duplicou no retry")
        self.assertEqual(cc.pending_operations([cc.BASE]), [])
        self.assertEqual(licoes.count("Aprendizado exportado D+30"), 0)  # marcador fica no veredito, nao aqui
        self.assertIn("Aprendizado exportado D+30", veredito.read_text(encoding="utf-8"))

    # ---- Bug 2: marcador gravado deixa recuperacao presa -------------------

    def test_bug2_retry_apos_marcador_gravado_nao_fica_preso_na_guarda(self):
        veredito = self._fechar_com_veredito(self.project())

        real_append_text = cc.append_text

        def grava_e_falha_no_marcador(path_, texto_):
            resultado = real_append_text(path_, texto_)
            if "Aprendizado exportado" in texto_:
                raise RuntimeError("crash simulado logo depois de gravar o marcador")
            return resultado

        with patch.object(cc, "append_text", side_effect=grava_e_falha_no_marcador):
            with self.assertRaises(RuntimeError):
                self.cli("aprender-veredito", str(veredito))

        # O marcador ja esta no veredito quando a excecao propagou.
        self.assertIn("Aprendizado exportado D+30", veredito.read_text(encoding="utf-8"))
        self.assertEqual(len(cc.pending_operations([cc.BASE])), 1)

        # BUG 2: sem --force, e sem repetir marca/loja/licao, so reconciliar.
        self.cli("aprender-veredito", str(veredito))  # nao pode levantar SystemExit pedindo --force
        licoes = (cc.BASE / "licoes.md").read_text(encoding="utf-8")
        self.assertEqual(licoes.count("conferir estoque antes"), 1)
        self.assertEqual(veredito.read_text(encoding="utf-8").count("Aprendizado exportado D+30"), 1)
        self.assertEqual(cc.pending_operations([cc.BASE]), [])

    def test_guarda_de_ja_exportado_continua_valendo_sem_operacao_pendente(self):
        """Reexport de verdade (sem crash, sem journal) continua exigindo --force."""
        veredito = self._fechar_com_veredito(self.project())
        self.cli("aprender-veredito", str(veredito))
        with self.assertRaisesRegex(SystemExit, "ja foi exportado"):
            self.cli("aprender-veredito", str(veredito))
        # com --force, nao duplica o bloco de marcador
        self.cli("aprender-veredito", str(veredito), "--force")
        texto = veredito.read_text(encoding="utf-8")
        self.assertEqual(texto.count("## Aprendizado exportado D+30"), 1)

    # ---- Bug 3: decidir cria snapshot duplicado no retry --------------------

    def test_bug3_retry_de_decidir_nao_cria_segundo_snapshot(self):
        project = self.project()
        self._abrir_candidato(project)

        real_append_timeline = cc.append_timeline

        def falha_no_veredito(project_, etapa, decisao, porque):
            if etapa == "veredito":
                raise RuntimeError("crash simulado antes da linha do veredito")
            return real_append_timeline(project_, etapa, decisao, porque)

        with patch.object(cc, "append_timeline", side_effect=falha_no_veredito):
            with self.assertRaises(RuntimeError):
                self._decidir(project)

        snapshots_antes = sorted(p.name for p in (project / "snapshots").iterdir())
        self.assertEqual(len(snapshots_antes), 1)

        self._decidir(project)  # retry
        snapshots_depois = sorted(p.name for p in (project / "snapshots").iterdir())
        self.assertEqual(snapshots_depois, snapshots_antes,
                         "BUG 3: retry criou um segundo diretorio de snapshot")
        # a captura retomada tem manifesto valido (nao ficou pela metade)
        manifesto = (project / "snapshots" / snapshots_depois[0] / "manifesto.json")
        self.assertTrue(manifesto.exists())
        processo = (project / "processo.md").read_text(encoding="utf-8")
        self.assertEqual(processo.count("| decisao | Escolhido candidato |"), 1)
        self.assertEqual(processo.count("| veredito | Arquivo de veredito criado |"), 1)
        self.assertEqual(cc.pending_operations([project]), [])

    # ---- Retomada com dados diferentes: recusa, nao mistura -----------------

    def test_retomada_com_justificativa_diferente_e_recusada(self):
        project = self.project()
        self._abrir_candidato(project)
        with patch.object(cc, "append_timeline", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                self._decidir(project, porque="motivo original")

        with self.assertRaisesRegex(SystemExit, "dados diferentes"):
            self._decidir(project, porque="motivo mudou depois do crash")

        # com a MESMA justificativa da tentativa que falhou, retoma normalmente
        self._decidir(project, porque="motivo original")
        processo = (project / "processo.md").read_text(encoding="utf-8")
        self.assertEqual(processo.count("| decisao | Escolhido candidato | motivo original |"), 1)

    def test_retomada_com_licao_diferente_e_recusada(self):
        veredito = self._fechar_com_veredito(self.project())
        with patch.object(cc, "append_text", side_effect=RuntimeError("crash antes de qualquer gravacao")):
            with self.assertRaises(RuntimeError):
                self.cli("aprender-veredito", str(veredito))

        with self.assertRaisesRegex(SystemExit, "dados diferentes"):
            self.cli("aprender-veredito", str(veredito), "--licao", "licao diferente da tentativa anterior")

    # ---- Journal ilegivel: nunca reinicia do zero sozinho -------------------

    def test_journal_json_invalido_bloqueia_e_preserva_o_arquivo(self):
        project = self.project()
        self._abrir_candidato(project)
        pasta = project / ".operacoes"
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = pasta / f"{cc.slugify('decidir:candidato')}.json"
        arquivo.write_text("{nao e json valido", encoding="utf-8")

        with self.assertRaisesRegex(SystemExit, "nao pode ser lido com confianca"):
            self._decidir(project)
        self.assertEqual(arquivo.read_text(encoding="utf-8"), "{nao e json valido",
                         "o journal ilegivel nao pode ser sobrescrito silenciosamente")

    def test_journal_json_valido_com_estrutura_incompleta_bloqueia(self):
        project = self.project()
        self._abrir_candidato(project)
        pasta = project / ".operacoes"
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = pasta / f"{cc.slugify('decidir:candidato')}.json"
        arquivo.write_text('{"op_id": "decidir:candidato", "situacao": "em_andamento"}', encoding="utf-8")

        with self.assertRaisesRegex(SystemExit, "nao pode ser lido com confianca"):
            self._decidir(project)

    def test_pending_operations_relata_journal_ilegivel_sem_apagar(self):
        project = self.project()
        pasta = project / ".operacoes"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "quebrado.json").write_text("{nao e json valido", encoding="utf-8")
        pendentes = cc.pending_operations([project])
        self.assertEqual(len(pendentes), 1)
        self.assertEqual(pendentes[0]["situacao"], "journal_ilegivel")
        self.assertTrue((pasta / "quebrado.json").exists())

    # ---- operacoes-pendentes: relata e some -------------------------------

    def test_operacoes_pendentes_relata_e_some_apos_concluir(self):
        project = self.project()
        self._abrir_candidato(project)

        with patch.object(cc, "append_timeline", side_effect=RuntimeError("crash simulado")):
            with self.assertRaises(RuntimeError):
                self._decidir(project)

        saida = self.cli("operacoes-pendentes")
        self.assertIn("PENDENTE decidir:candidato", saida)

        with self.assertRaises(SystemExit):
            self.cli("operacoes-pendentes", "--strict")

        self._decidir(project)
        saida = self.cli("operacoes-pendentes")
        self.assertIn("Nenhuma operacao pendente", saida)
        self.cli("operacoes-pendentes", "--strict")  # nao deve sair com erro

    # ---- Concorrencia: as travas existentes ainda serializam --------------

    def test_comandos_concorrentes_no_mesmo_projeto_sao_serializados(self):
        project = self.project()
        self._abrir_candidato(project)
        resultados = []
        erros = []

        def tentar():
            try:
                resultados.append(self._decidir(project))
            except BaseException as erro:  # inclui SystemExit de timeout da trava
                erros.append(erro)

        import threading
        threads = [threading.Thread(target=tentar) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        # Ninguem deve ter corrompido processo.md: as linhas da linha do
        # tempo (comecam com a data) precisam continuar com as 4 colunas
        # inteiras, sem fusao/truncamento por escrita concorrente mal
        # serializada.
        processo = (project / "processo.md").read_text(encoding="utf-8")
        for linha in processo.splitlines():
            if re.match(r"^\| \d{4}-\d{2}-\d{2} \|", linha):
                self.assertEqual(linha.count("|"), 5, f"linha corrompida por corrida: {linha!r}")
        self.assertEqual(len(cc.pending_operations([project])), 0)
        # ao menos uma tentativa deve ter completado com sucesso
        self.assertGreaterEqual(len(resultados), 1)


class SubprocessRecoveryTest(unittest.TestCase):
    """Interrupcao real de processo (os._exit, sem excecao Python) e recuperacao."""

    def test_interrupcao_real_de_subprocesso_e_recuperacao(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = ambiente.montar(Path(tmp))
            script = raiz / "scripts" / "central_compras.py"

            def rodar(*args, crash_apos=None):
                env = dict(os.environ)
                if crash_apos:
                    env["CENTRAL_COMPRAS_TESTE_CRASH_APOS"] = crash_apos
                else:
                    env.pop("CENTRAL_COMPRAS_TESTE_CRASH_APOS", None)
                return subprocess.run(
                    [sys.executable, str(script), *args],
                    cwd=str(raiz), env=env, capture_output=True, text=True, timeout=30,
                )

            nome_projeto = "relogio-teste-subprocesso"
            r = rodar("novo-projeto", nome_projeto, "--categoria", "fone", "--valor-estimado", "400")
            self.assertEqual(r.returncode, 0, r.stderr)
            projeto_dir = raiz / "projetos" / f"{cc.today()[:4]}-{cc.slugify(nome_projeto)}"
            self.assertTrue(projeto_dir.is_dir(), r.stdout + r.stderr)

            r = rodar("novo-produto", str(projeto_dir), "candidato", "--produto-id", "candidato",
                      "--marca", "Marca", "--requisito", "uso=true")
            self.assertEqual(r.returncode, 0, r.stderr)
            r = rodar("cotar", str(projeto_dir), "--produto-id", "candidato", "--loja", "Amazon",
                      "--vendedor", "V", "--vendedor-tipo", "oficial", "--preco", "200",
                      "--nota", "4.8", "--avaliacoes", "1000", "--frete-prazo-dias", "2",
                      "--garantia-tipo", "nacional", "--garantia-meses", "12",
                      "--link", "https://example.invalid/item", "--fonte", "manual")
            self.assertEqual(r.returncode, 0, r.stderr)

            decidir_args = ("decidir", str(projeto_dir), "--produto-id", "candidato",
                            "--porque", "unico candidato", "--sem-perdedores", "--comprado")

            # Mata o processo de verdade (os._exit) logo depois de executar o
            # efeito da linha "veredito" na linha do tempo, antes de confirmar
            # o passo no journal - a mesma janela do bug 3, mas com
            # interrupcao real de SO, nao excecao Python capturada.
            r = rodar(*decidir_args, crash_apos="timeline_veredito:executado")
            self.assertEqual(r.returncode, 70, f"esperava os._exit(70); stdout={r.stdout} stderr={r.stderr}")

            snapshots_antes = sorted(p.name for p in (projeto_dir / "snapshots").iterdir())
            self.assertEqual(len(snapshots_antes), 1)

            r = rodar("operacoes-pendentes", "--strict")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("decidir:candidato", r.stdout)

            # Retomada real, em processo novo, sem a variavel de crash.
            r = rodar(*decidir_args)
            self.assertEqual(r.returncode, 0, r.stderr)

            snapshots_depois = sorted(p.name for p in (projeto_dir / "snapshots").iterdir())
            self.assertEqual(snapshots_depois, snapshots_antes, "criou snapshot duplicado apos recuperacao real")
            processo = (projeto_dir / "processo.md").read_text(encoding="utf-8")
            self.assertEqual(processo.count("| decisao | Escolhido candidato |"), 1)
            self.assertEqual(processo.count("| veredito | Arquivo de veredito criado |"), 1)

            r = rodar("operacoes-pendentes", "--strict")
            self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
