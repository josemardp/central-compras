"""Etapa do especialista tecnico: especificar para o MEU contexto e avaliar acessorios.

O que se protege aqui: o prompt da etapa modelo leva perfil e guia da
categoria; o `status` cobra especificacao e acessorios sem cobrar projeto
antigo (template sem a secao); acessorio com preco a comparar vira projeto
proprio, ligado ao principal, sem misturar ranking.
"""

from tests.ambiente import RepoTestCase


class EspecialistaTest(RepoTestCase):
    def modelo(self, projeto):
        return projeto / "01-definir-modelo.md"

    def test_prompt_modelo_leva_perfil_e_guia_da_categoria(self):
        from scripts import central_compras as cc
        (cc.CONFIG / "perfil.yaml").write_text(
            "# comentario fica de fora\nequipamentos:\n  - tipo: celular\n    descricao: \"Android Samsung\"\n",
            encoding="utf-8",
        )
        guias = cc.BASE / "especificacoes"
        guias.mkdir(parents=True, exist_ok=True)
        (guias / "fone.md").write_text("# Fone\n\nChamada exige microfone com ENC.\n", encoding="utf-8")
        projeto = self.project("fone chamada", category="fone")

        prompt = self.cli("prompt-ia", str(projeto), "--etapa", "modelo")

        self.assertIn("Android Samsung", prompt)
        self.assertNotIn("comentario fica de fora", prompt)
        self.assertIn("Chamada exige microfone com ENC.", prompt)
        self.assertIn("perguntas decisivas", prompt)
        self.assertIn("Acessorio | Necessidade | Especificacao tecnica", prompt)

    def test_prompt_sem_perfil_nem_guia_manda_perguntar(self):
        from scripts import central_compras as cc
        (cc.CONFIG / "perfil.yaml").unlink(missing_ok=True)
        projeto = self.project("camera quintal", category="camera")

        prompt = self.cli("prompt-ia", str(projeto), "--etapa", "modelo")

        self.assertIn("Meu perfil: nao cadastrado", prompt)
        self.assertIn("Guia do especialista desta categoria: ainda nao existe.", prompt)

    def test_status_cobra_especificacao_e_acessorios_pendentes(self):
        projeto = self.project("fone pendente")

        saida = self.cli("status", str(projeto))

        self.assertIn("Especificacao tecnica: PENDENTE", saida)
        self.assertIn("Acessorios: nao avaliados", saida)

    def test_status_conta_linhas_preenchidas_e_ignora_cabecalho(self):
        projeto = self.project("fone definido")
        texto = self.modelo(projeto).read_text(encoding="utf-8")
        texto = texto.replace(
            "| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |\n|---|---|---|---|\n",
            "| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |\n|---|---|---|---|\n"
            "| Bluetooth | 5.0 | 5.3 multiponto | celular e notebook ao mesmo tempo |\n"
            "| Bateria | 20 h | 40 h | dia inteiro de plantao |\n"
            "|  |  |  |  |\n",
        )
        texto = texto.replace(
            "| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |\n|---|---|---|---|---|\n",
            "| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |\n|---|---|---|---|---|\n"
            "| Estojo rigido | recomendado | interno >= 18 cm | vai na mochila | junto |\n",
        )
        self.modelo(projeto).write_text(texto, encoding="utf-8")

        saida = self.cli("status", str(projeto))

        self.assertIn("Especificacao tecnica: 2 atributo(s) definido(s)", saida)
        self.assertIn("Acessorios: 1 avaliado(s)", saida)

    def test_projeto_antigo_sem_secao_nao_e_cobrado(self):
        projeto = self.project("fone antigo")
        self.modelo(projeto).write_text("# Definir modelo\n\n## Decisao de modelo\n\n- Tipo: x\n", encoding="utf-8")

        saida = self.cli("status", str(projeto))

        self.assertNotIn("Especificacao tecnica:", saida)
        self.assertNotIn("Acessorios:", saida)

    def test_acessorio_vira_projeto_ligado_ao_principal(self):
        from scripts import central_compras as cc
        principal = self.project("camera frente", category="camera")

        self.cli("novo-projeto", "cartao microsd camera frente", "--categoria", "generico",
                 "--valor-estimado", "80", "--acessorio-de", str(principal))
        acessorio = cc.PROJETOS / f"{cc.today()[:4]}-cartao-microsd-camera-frente"

        meta, _ = cc.load_frontmatter(acessorio / "briefing.md")
        self.assertEqual(meta["acessorio_de"], principal.name)
        self.assertEqual(meta["estado"], "pesquisando")
        self.assertIn(f"aberto projeto {acessorio.name}", (principal / "processo.md").read_text(encoding="utf-8"))
        self.assertIn(f"acessorio de {principal.name}", (acessorio / "processo.md").read_text(encoding="utf-8"))

    def test_acessorio_de_projeto_inexistente_e_recusado(self):
        from scripts import central_compras as cc
        with self.assertRaises(SystemExit):
            self.cli("novo-projeto", "cabo orfao", "--acessorio-de", "projeto-que-nao-existe")
        self.assertFalse((cc.PROJETOS / f"{cc.today()[:4]}-cabo-orfao").exists())
