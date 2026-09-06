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
    def _abrir_candidato(self, project, pid="candidato"):
        # produto_id e global por categoria (produtos/<categoria>/<id>), nao
        # por projeto - projetos distintos usados no mesmo teste precisam de
        # pid distinto para nao colidir com "Produto ja existe".
        self.product(project, pid)
        self.quote(project, pid, "--fonte", "manual")

    def _decidir(self, project, pid="candidato", **overrides):
        args = ["decidir", str(project), "--produto-id", pid,
                "--porque", overrides.pop("porque", "unico candidato"),
                "--sem-perdedores", "--comprado"]
        return self.cli(*args)

    def _fechar_com_veredito(self, project):
        return self._fechar_com_veredito_generico(project, licao="conferir estoque antes")

    def _fechar_com_veredito_generico(self, project, licao, pid="candidato"):
        self._abrir_candidato(project, pid)
        self._decidir(project, pid)
        veredito = next(p for p in cc.VEREDITOS.glob("*.md") if project.name in p.name)
        self.cli("preencher-veredito", str(veredito), "--fase", "d30",
                 "--resumo", "foi bem", "--licao", licao,
                 "--nota-arrependimento", "1", "--compraria-de-novo", "sim")
        return veredito

    def _cli_capturando(self, *argv):
        """Como `self.cli`, mas devolve (saida, excecao) em vez de propagar
        SystemExit - para inspecionar o que foi impresso mesmo quando o
        comando falha (ex.: `auditar-decisoes --strict` imprime os problemas
        antes de levantar)."""
        import contextlib as ctxlib
        import io
        output = io.StringIO()
        excecao = None
        with ctxlib.redirect_stdout(output):
            try:
                cc.main(list(argv))
            except SystemExit as erro:
                excecao = erro
        return output.getvalue(), excecao

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

    # ---- 3a revisao (Codex), sobre o commit 2a682a7 ------------------------

    def test_rev3_bug1_manifesto_nao_e_invalidado_pela_propria_recuperacao(self):
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

        self._decidir(project)  # retomada: reusa o mesmo diretorio de snapshot

        # So existir o manifesto.json nao prova integridade - precisa bater
        # com o conteudo real de cada arquivo listado, incluindo ele mesmo
        # nao se autodescrever de forma inconsistente.
        saida, erro = self._cli_capturando("auditar-decisoes", str(project), "--strict")
        self.assertIsNone(erro, f"BUG: auditar-decisoes --strict reprovou apos a recuperacao:\n{saida}")
        self.assertEqual(len(cc.pending_operations([project])), 0)

    def test_rev3_bug2_snapshot_nao_e_reescrito_com_config_diferente_apos_crash(self):
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

        snapshot_dir = next((project / "snapshots").iterdir())
        prefs_no_snapshot = snapshot_dir / "preferencias.yaml"
        categorias_no_snapshot = snapshot_dir / "categorias.yaml"
        bytes_prefs_originais = prefs_no_snapshot.read_bytes()
        bytes_categorias_originais = categorias_no_snapshot.read_bytes()

        # Muda a config REAL depois do crash, antes do retry - simula o
        # Josemar calibrando um peso entre a falha e a retomada.
        prefs_reais = self.root / "config" / "preferencias.yaml"
        prefs_reais.write_text(
            prefs_reais.read_text(encoding="utf-8") + "\nvalor_alterado_no_teste: true\n",
            encoding="utf-8",
        )

        self._decidir(project)  # retomada, MESMO comando

        self.assertEqual(prefs_no_snapshot.read_bytes(), bytes_prefs_originais,
                         "BUG: snapshot foi reescrito com a config alterada apos o crash")
        self.assertEqual(categorias_no_snapshot.read_bytes(), bytes_categorias_originais)
        saida, erro = self._cli_capturando("auditar-decisoes", str(project), "--strict")
        self.assertIsNone(erro, saida)

        # a config real, fora do snapshot, continua alterada - a correcao
        # nao deve ter revertido nada fora da evidencia congelada.
        self.assertIn("valor_alterado_no_teste", prefs_reais.read_text(encoding="utf-8"))

    def test_rev3_bug3_texto_identico_nao_confunde_operacoes_distintas_antes_de_executar(self):
        # Operacao A: exportacao legitima e completa, registrando uma licao.
        projeto_a = self.project("compra-a")
        veredito_a = self._fechar_com_veredito_generico(projeto_a, licao="conferir garantia antes", pid="candidato-a")
        self.cli("aprender-veredito", str(veredito_a))
        self.assertEqual((cc.BASE / "licoes.md").read_text(encoding="utf-8").count("conferir garantia antes"), 1)

        # Operacao B: outro projeto, MESMO texto de licao, no mesmo dia.
        # Interrompida exatamente entre persistir "licao:iniciado" (a
        # assinatura ja congelada) e executar a gravacao de verdade.
        projeto_b = self.project("compra-b")
        veredito_b = self._fechar_com_veredito_generico(projeto_b, licao="conferir garantia antes", pid="candidato-b")

        real_hook = cc._crash_de_teste_se_pedido

        def falha_em(ponto_alvo):
            def _hook(ponto):
                if ponto == ponto_alvo:
                    raise RuntimeError(f"crash simulado em {ponto}")
                return real_hook(ponto)
            return _hook

        with patch.object(cc, "_crash_de_teste_se_pedido", falha_em("licao:iniciado")):
            with self.assertRaises(RuntimeError):
                self.cli("aprender-veredito", str(veredito_b))

        licoes = (cc.BASE / "licoes.md").read_text(encoding="utf-8")
        self.assertEqual(licoes.count("conferir garantia antes"), 1,
                         "so a operacao A devia ter gravado ate aqui; B foi interrompida antes de executar")

        # Retomada de B: precisa gravar a PROPRIA ocorrencia, sem confundir
        # com a entrada legitima e independente que A ja tinha gravado.
        self.cli("aprender-veredito", str(veredito_b))
        licoes = (cc.BASE / "licoes.md").read_text(encoding="utf-8")
        self.assertEqual(licoes.count("conferir garantia antes"), 2,
                         "BUG: a retomada de B confundiu a entrada de A com o proprio efeito e nao gravou nada")
        self.assertEqual(cc.pending_operations([cc.BASE]), [])

    def test_rev3_bug3_texto_identico_falha_apos_executar_tambem_nao_duplica(self):
        projeto_a = self.project("compra-a")
        veredito_a = self._fechar_com_veredito_generico(projeto_a, licao="conferir garantia antes", pid="candidato-a")
        self.cli("aprender-veredito", str(veredito_a))

        projeto_b = self.project("compra-b")
        veredito_b = self._fechar_com_veredito_generico(projeto_b, licao="conferir garantia antes", pid="candidato-b")

        real_hook = cc._crash_de_teste_se_pedido

        def falha_em(ponto_alvo):
            def _hook(ponto):
                if ponto == ponto_alvo:
                    raise RuntimeError(f"crash simulado em {ponto}")
                return real_hook(ponto)
            return _hook

        # Desta vez a falha e DEPOIS de executar a gravacao de B (que produz
        # a 2a ocorrencia do texto), mas antes de confirmar o passo.
        with patch.object(cc, "_crash_de_teste_se_pedido", falha_em("licao:executado")):
            with self.assertRaises(RuntimeError):
                self.cli("aprender-veredito", str(veredito_b))

        licoes = (cc.BASE / "licoes.md").read_text(encoding="utf-8")
        self.assertEqual(licoes.count("conferir garantia antes"), 2,
                         "a gravacao de B ja devia ter acontecido antes do crash simulado")

        # Retomada: NAO deve gravar uma 3a ocorrencia.
        self.cli("aprender-veredito", str(veredito_b))
        licoes = (cc.BASE / "licoes.md").read_text(encoding="utf-8")
        self.assertEqual(licoes.count("conferir garantia antes"), 2,
                         "BUG: a retomada duplicou a licao de B apos falha pos-execucao")
        self.assertEqual(cc.pending_operations([cc.BASE]), [])

    def test_rev3_bug3_duas_fases_com_texto_identico_nao_se_confundem(self):
        project = self.project()
        veredito = self._fechar_com_veredito_generico(project, licao="conferir garantia antes")
        self.cli("aprender-veredito", str(veredito))  # exporta D+30

        # Preenche e exporta D+180 com o MESMO texto de licao que o D+30 ja
        # exportou. Sao operacoes (op_id) distintas por causa da fase.
        self.cli("preencher-veredito", str(veredito), "--fase", "d180",
                 "--resumo", "continua bom", "--licao", "conferir garantia antes",
                 "--nota-arrependimento", "1", "--compraria-de-novo", "sim",
                 "--ainda-usa", "sim")
        self.cli("aprender-veredito", str(veredito))
        licoes = (cc.BASE / "licoes.md").read_text(encoding="utf-8")
        self.assertEqual(licoes.count("conferir garantia antes"), 2,
                         "as duas fases sao exportacoes distintas; as duas devem ter gravado")
        self.assertEqual(cc.pending_operations([cc.BASE]), [])

    # ---- Concorrencia: as travas existentes ainda serializam --------------

    def test_comandos_concorrentes_no_mesmo_projeto_sao_serializados(self):
        project = self.project()
        self._abrir_candidato(project)
        resultados = []
        erros = []

        def tentar():
            try:
                resultados.append(self._decidir(project))
            except BaseException as erro:  # so aceitavel se for o timeout da trava
                erros.append(erro)

        import threading
        threads = [threading.Thread(target=tentar) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        # Toda excecao tem que ser EXATAMENTE o timeout de trava esperado -
        # qualquer outro tipo de erro (corrupcao, dado inconsistente) reprova.
        for erro in erros:
            self.assertIsInstance(erro, SystemExit)
            self.assertIn("Outro comando esta escrevendo", str(erro))

        # Ninguem deve ter corrompido processo.md: as linhas da linha do
        # tempo (comecam com a data) precisam continuar com as 4 colunas
        # inteiras, sem fusao/truncamento por escrita concorrente mal
        # serializada.
        processo = (project / "processo.md").read_text(encoding="utf-8")
        for linha in processo.splitlines():
            if re.match(r"^\| \d{4}-\d{2}-\d{2} \|", linha):
                self.assertEqual(linha.count("|"), 5, f"linha corrompida por corrida: {linha!r}")
        self.assertEqual(len(cc.pending_operations([project])), 0)
        # O numero de sucessos tem que bater EXATAMENTE com o numero de linhas
        # de decisao gravadas - nem mais (duplicacao), nem menos (perda).
        linhas_decisao = processo.count("| decisao | Escolhido candidato |")
        self.assertEqual(linhas_decisao, len(resultados))
        self.assertEqual(len(resultados) + len(erros), 3)
        self.assertGreaterEqual(len(resultados), 1)

        saida, erro_auditoria = self._cli_capturando("auditar-decisoes", str(project), "--strict")
        self.assertIsNone(erro_auditoria, saida)


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

    def test_concorrencia_com_processos_separados(self):
        """Threads no mesmo processo compartilham handle de arquivo com o SO
        de um jeito que nao testa a trava entre PROCESSOS de verdade - o
        cenario real de duas maquinas, ou dois terminais, rodando o mesmo
        comando. Isto aqui usa `subprocess.Popen` de verdade."""
        with tempfile.TemporaryDirectory() as tmp:
            raiz = ambiente.montar(Path(tmp))
            script = raiz / "scripts" / "central_compras.py"

            def rodar(*args):
                return subprocess.run(
                    [sys.executable, str(script), *args],
                    cwd=str(raiz), capture_output=True, text=True, timeout=60,
                )

            nome_projeto = "concorrencia-processos-separados"
            r = rodar("novo-projeto", nome_projeto, "--categoria", "fone", "--valor-estimado", "400")
            self.assertEqual(r.returncode, 0, r.stderr)
            projeto_dir = raiz / "projetos" / f"{cc.today()[:4]}-{cc.slugify(nome_projeto)}"
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

            processos = [
                subprocess.Popen([sys.executable, str(script), *decidir_args], cwd=str(raiz),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for _ in range(3)
            ]
            resultados = []
            for p in processos:
                saida, erro = p.communicate(timeout=60)  # .wait() implicito: so entao .returncode e real
                resultados.append((p.returncode, saida, erro))

            sucessos = 0
            for codigo, saida, erro in resultados:
                if codigo == 0:
                    sucessos += 1
                else:
                    # A UNICA falha aceitavel e o timeout da propria trava -
                    # qualquer outra coisa (traceback cru, corrupcao) reprova.
                    self.assertIn("Outro comando esta escrevendo", saida + erro,
                                 f"processo separado falhou por motivo inesperado: {erro}")
            self.assertGreaterEqual(sucessos, 1)

            processo_md = (projeto_dir / "processo.md").read_text(encoding="utf-8")
            linhas_decisao = processo_md.count("| decisao | Escolhido candidato |")
            self.assertEqual(linhas_decisao, sucessos,
                             "numero de linhas de decisao deve bater exatamente com o numero de sucessos")
            for linha in processo_md.splitlines():
                if re.match(r"^\| \d{4}-\d{2}-\d{2} \|", linha):
                    self.assertEqual(linha.count("|"), 5, f"linha corrompida por corrida entre processos: {linha!r}")

            r = rodar("operacoes-pendentes", "--strict")
            self.assertEqual(r.returncode, 0, r.stdout)
            r = rodar("auditar-decisoes", str(projeto_dir), "--strict")
            self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
