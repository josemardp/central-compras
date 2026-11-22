import re
import unittest
from pathlib import Path

from radar import git_escopo as ge

PORCELAIN = """ M STATUS.md
 M config/categorias.yaml
 M requirements.txt
 M scripts/rastrear_robos_bf.py
?? radar/cli.py
?? radar/fontes/gatry.py
?? config/radar_jobs.yaml
?? tests/test_radar_nucleo.py
?? tests/corpus/radar_ofertas_rotuladas.yaml
?? docs/ecossistema/04-matriz-de-fontes.md
?? produtos/climatizador/x/produto.yaml
?? projetos/2026-climatizador-ventisol-torre-3-6l/decisao.md
?? coisa_estranha.txt
"""
DIFFS = {"config/categorias.yaml": "+# Aberta em 21/11/2026 para analise do Climatizador Ventisol\n+climatizador:\n"}
STATUS_DIFF = ("+## Sessão 21/11/2026: análise do Climatizador Ventisol Torre 3,6 L (CLIT3.6)\n"
               "+## Sessão 21/11/2026: homologação e expansão do radar (fase 2)\n"
               "+## Sessão 20/11/2026 (noite): Radar de compras V3 (central-compras vira dono único das automações de compras)\n"
               "+## Sessão 22/11/2026: outro assunto qualquer\n")


class SecoesStatusTest(unittest.TestCase):
    TEXTO = "# T\n\nintro\n\n## Sessão 21/11/2026: análise do Climatizador Ventisol\n- a\n\n## Sessão 21/11/2026: radar fase 3\n- b\n\n## Sessão 10/10/2026: HB20S\n- c\n"

    def test_secoes_e_donos(self):
        s = ge.secoes_do_status(self.TEXTO)
        self.assertEqual(list(s), ["Sessão 21/11/2026: análise do Climatizador Ventisol", "Sessão 21/11/2026: radar fase 3", "Sessão 10/10/2026: HB20S"])
        self.assertEqual([ge.dono_da_secao(t) for t in s], ["outra_sessao", "radar", "historico"])
        self.assertTrue(s["Sessão 21/11/2026: radar fase 3"].endswith("- b"))

    def test_nunca_considera_do_radar_uma_secao_do_climatizador(self):
        self.assertEqual(ge.dono_da_secao("Sessão 21/11: climatizador e radar de compras"), "outra_sessao")


class EscopoTest(unittest.TestCase):
    def setUp(self):
        self.r = ge.classificar(PORCELAIN, DIFFS)

    def test_separa_radar_outra_sessao_misto_e_desconhecido(self):
        self.assertIn("radar/fontes/gatry.py", self.r["radar"])
        self.assertIn("scripts/rastrear_robos_bf.py", self.r["radar"])
        self.assertIn("requirements.txt", self.r["radar"])
        self.assertEqual(self.r["misto"], ["STATUS.md"])
        self.assertEqual(self.r["desconhecido"], ["coisa_estranha.txt"])
        self.assertEqual(sorted(self.r["outra_sessao"]),
                         ["config/categorias.yaml", "produtos/climatizador/x/produto.yaml", "projetos/2026-climatizador-ventisol-torre-3-6l/decisao.md"])

    def test_nada_do_climatizador_cai_na_lista_do_radar(self):
        self.assertFalse([p for p in self.r["radar"] if "climatizador" in p or p == "config/categorias.yaml"])

    def test_secoes_do_status_por_dono(self):
        s = {x["secao"][:20]: x["dono"] for x in ge.secoes_status(STATUS_DIFF)}
        donos = [x["dono"] for x in ge.secoes_status(STATUS_DIFF)]
        self.assertEqual(donos, ["outra_sessao", "radar", "radar", "desconhecido"])

    def test_comando_sugerido_nao_inclui_status_inteiro_nem_arquivos_alheios(self):
        r = dict(self.r, secoes_status=ge.secoes_status(STATUS_DIFF))
        cmds = " ".join(ge.comandos_sugeridos(r))
        self.assertIn("git add -p STATUS.md", cmds)
        self.assertNotIn("climatizador", cmds.split("# STATUS.md")[0])
        self.assertNotIn("categorias.yaml", cmds)

    def test_o_modulo_so_usa_git_de_leitura(self):
        fonte = Path(ge.__file__).read_text(encoding="utf-8")
        verbos = set(re.findall(r'_git\(\s*"(\w+)"', fonte))
        self.assertTrue(verbos <= {"status", "diff", "log", "stash", "show"}, verbos)  # todos de leitura
        self.assertEqual(re.findall(r'_git\(\s*"stash",\s*"(\w+)"', fonte), ["list"])  # stash so para LISTAR
        # `git apply` so com --check (valida o patch; nunca aplica nem altera o indice)
        self.assertEqual(fonte.count('"apply"'), 1)
        self.assertIn('"apply", "--check"', fonte)
        for proibido in ("checkout", "reset", "clean", "restore", "commit", "push", "pull", "merge", "rebase", "rm", "mv"):
            self.assertNotIn(f'"{proibido}"', fonte, proibido)


if __name__ == "__main__":
    unittest.main()
