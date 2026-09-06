"""Recuperacao de operacoes de varios arquivos interrompidas no meio (journal).

Reproduz o achado da auditoria de 06/09/2026 ("Escritas em multiplos
arquivos... falta de espaco ou interrupcao entre arquivos ainda pode deixar
uma operacao parcialmente concluida"): uma falha entre `register_lesson` e o
marcador de exportado duplicava a licao inteira em `licoes.md` numa
repeticao do comando. O mesmo padrao existia em `decidir`, duplicando linha
na linha do tempo de `processo.md`.
"""

import unittest
from unittest.mock import patch

import ambiente
from scripts import central_compras as cc


class OperationRecoveryTest(ambiente.RepoTestCase):
    def _abrir_candidato(self, project):
        self.product(project)
        self.quote(project, "candidato", "--fonte", "manual")

    def test_aprender_veredito_retry_apos_falha_nao_duplica(self):
        project = self.project()
        self._abrir_candidato(project)
        self.cli("decidir", str(project), "--produto-id", "candidato",
                 "--porque", "unico candidato", "--sem-perdedores", "--comprado")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.cli("preencher-veredito", str(veredito), "--fase", "d30",
                 "--resumo", "foi bem", "--licao", "conferir estoque antes",
                 "--nota-arrependimento", "1", "--compraria-de-novo", "sim")

        real_append_text = cc.append_text

        def falha_no_marcador(path, text):
            if "Aprendizado exportado" in text:
                raise RuntimeError("crash simulado antes do marcador")
            return real_append_text(path, text)

        with patch.object(cc, "append_text", side_effect=falha_no_marcador):
            with self.assertRaises(RuntimeError):
                self.cli("aprender-veredito", str(veredito))

        # A licao ja foi registrada uma vez antes do crash simulado; o journal
        # continua em disco, marcando que o passo "licao" ja foi feito.
        licoes = (cc.BASE / "licoes.md").read_text(encoding="utf-8")
        self.assertEqual(licoes.count("conferir estoque antes"), 1)
        pendentes = cc.pending_operations([cc.BASE])
        self.assertEqual(len(pendentes), 1)
        self.assertEqual(pendentes[0]["kind"], "aprender-veredito")
        self.assertIn("licao", pendentes[0]["passos"])

        # Retry sem falha: so falta o marcador. Nao repete marca/loja/licao.
        self.cli("aprender-veredito", str(veredito))
        licoes = (cc.BASE / "licoes.md").read_text(encoding="utf-8")
        self.assertEqual(licoes.count("conferir estoque antes"), 1)
        self.assertIn("Aprendizado exportado D+30", veredito.read_text(encoding="utf-8"))
        self.assertEqual(cc.pending_operations([cc.BASE]), [])

    def test_decidir_retry_apos_falha_nao_duplica_linha_do_tempo(self):
        project = self.project()
        self._abrir_candidato(project)

        real_append_timeline = cc.append_timeline

        def falha_no_veredito(project_, etapa, decisao, porque):
            if etapa == "veredito":
                raise RuntimeError("crash simulado antes da linha do veredito")
            return real_append_timeline(project_, etapa, decisao, porque)

        with patch.object(cc, "append_timeline", side_effect=falha_no_veredito):
            with self.assertRaises(RuntimeError):
                self.cli("decidir", str(project), "--produto-id", "candidato",
                         "--porque", "unico candidato", "--sem-perdedores", "--comprado")

        # decisao.md e o snapshot ja existem; a linha "decisao" ja foi
        # escrita na linha do tempo antes do crash simulado.
        self.assertTrue((project / "decisao.md").exists())
        processo = (project / "processo.md").read_text(encoding="utf-8")
        self.assertEqual(processo.count("| decisao | Escolhido candidato |"), 1)
        pendentes = cc.pending_operations([project])
        self.assertEqual(len(pendentes), 1)
        self.assertEqual(pendentes[0]["kind"], "decidir")
        self.assertIn("timeline_decisao", pendentes[0]["passos"])
        self.assertNotIn("timeline_veredito", pendentes[0]["passos"])

        # Retry sem falha: completa so o que faltou, sem duplicar "decisao".
        self.cli("decidir", str(project), "--produto-id", "candidato",
                 "--porque", "unico candidato", "--sem-perdedores", "--comprado")
        processo = (project / "processo.md").read_text(encoding="utf-8")
        self.assertEqual(processo.count("| decisao | Escolhido candidato |"), 1)
        self.assertEqual(processo.count("| veredito | Arquivo de veredito criado |"), 1)
        self.assertEqual(cc.pending_operations([project]), [])

    def test_operacoes_pendentes_relata_e_some_apos_concluir(self):
        project = self.project()
        self._abrir_candidato(project)

        with patch.object(cc, "append_timeline", side_effect=RuntimeError("crash simulado")):
            with self.assertRaises(RuntimeError):
                self.cli("decidir", str(project), "--produto-id", "candidato",
                         "--porque", "unico candidato", "--sem-perdedores", "--comprado")

        saida = self.cli("operacoes-pendentes")
        self.assertIn("PENDENTE decidir:candidato", saida)
        self.assertIn("decidir", saida)

        with self.assertRaises(SystemExit):
            self.cli("operacoes-pendentes", "--strict")

        self.cli("decidir", str(project), "--produto-id", "candidato",
                 "--porque", "unico candidato", "--sem-perdedores", "--comprado")
        saida = self.cli("operacoes-pendentes")
        self.assertIn("Nenhuma operacao pendente", saida)
        # com tudo concluido, --strict nao deve sair com erro
        self.cli("operacoes-pendentes", "--strict")

    def test_journal_corrompido_nao_bloqueia_nem_finge_confiavel(self):
        project = self.project()
        pasta = project / ".operacoes"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "quebrado.json").write_text("{nao e json valido", encoding="utf-8")
        pendentes = cc.pending_operations([project])
        self.assertEqual(len(pendentes), 1)
        self.assertEqual(pendentes[0]["situacao"], "journal_ilegivel")


if __name__ == "__main__":
    unittest.main()
