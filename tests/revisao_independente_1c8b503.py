"""Revisao adversarial independente do commit `1c8b503` (frente 6, correcao
dos 2 achados da 5a revisao: `_erro_divergencia_financeira_veredito` e
`_erro_force_veredito_apagaria_exportacao`, as duas guardadas por
`not retomando_decisao` em `decide()`).

Nao faz parte da suite oficial de proposito (nome do arquivo nao comeca com
`test_`, entao `python -m unittest discover -s tests` NAO coleta isto - os
achados aqui ainda nao foram corrigidos em producao, e a suite oficial tem
que continuar 100% verde). Rodar manualmente com:

    python -m unittest discover -s tests -p "revisao_independente_1c8b503.py" -v

Guardado em caminho persistente do repositorio (nao em %TEMP%). Ver
STATUS.md e a secao 6 de docs/plano-pendencias-auditoria-2026-09-06.md
para o relato completo desta rodada (6a revisao independente da frente 6).
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


def _hora_hoje(hhmmss: str) -> str:
    """`data_coleta` vem do relogio real (`now_iso()`, nunca mockado por
    `patch.object(cc, "today", ...)`), com resolucao de SEGUNDO - fixar
    `--data` explicitamente evita que duas cotacoes no mesmo segundo
    empatem e o desempate por preco mais barato (proposital em
    `latest_quotes`) mascare a cotacao que o teste realmente quer usar."""
    return f"{dt.date.today().isoformat()}T{hhmmss}"


class JournalAntigoBypassaProtecoesNovasTest(ambiente.RepoTestCase):
    """Foco 1 do roteiro: as checagens novas de `decide()`
    (`_erro_divergencia_financeira_veredito`,
    `_erro_force_veredito_apagaria_exportacao`) so rodam quando
    `not retomando_decisao` - um journal criado pelo codigo do commit
    `e048ad6` (a versao IMEDIATAMENTE ANTERIOR a `1c8b503`, sem essas duas
    checagens) e retomado com o codigo ATUAL pula as duas por completo,
    porque a retomada nunca as roda de novo - so usa o nome/data ja
    congelados em `op.detalhe`."""

    def test_journal_antigo_e048ad6_bypassa_checagem_financeira_e_grava_preco_obsoleto(self):
        """Acha 1 (financeiro), via journal antigo: `decidir candidato`
        (sem comprado) com o codigo de `e048ad6` cria o veredito com a
        cotacao Q1 (R$200/Amazon). Uma cotacao NOVA Q2 (R$999/LojaNova) e
        adicionada. `decidir candidato --comprado` (ainda com o codigo de
        `e048ad6`, que NAO tem `_erro_divergencia_financeira_veredito`) e
        interrompido ANTES de `create_verdict` rodar - o journal congela
        `veredito_nome`/`data_compra_efetiva`, mas o veredito continua com
        Q1 intacto. Atualizando para o codigo ATUAL (`1c8b503`, que TEM a
        checagem) e retomando o MESMO comando: a checagem nao roda (e uma
        retomada), `create_verdict` grava `Data da compra` certa ao lado de
        `Valor pago`/`Vendedor`/`Loja` ainda de Q1 - o mesmo sintoma do
        achado 1 que a correcao pretendia fechar, so que via journal
        antigo em vez de uma chamada nova."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual", "--data", _hora_hoje("09:00:00"))

        script = self.root / "scripts" / "central_compras.py"
        atual = script.read_bytes()
        antigo_e048ad6 = subprocess.run(
            ["git", "show", "e048ad6:scripts/central_compras.py"],
            cwd=REPO, capture_output=True, check=True,
        ).stdout
        script.write_bytes(antigo_e048ad6)

        primeira = subprocess.run(
            [sys.executable, str(script), "decidir", str(project), "--produto-id", "candidato",
             "--porque", "primeira escolha", "--sem-perdedores"],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(primeira.returncode, 0, primeira.stderr)
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Valor pago"), cc.brl(200.0))

        self.quote(project, "candidato", "--fonte", "manual", "--preco", "999", "--loja", "LojaNova",
                   "--data", _hora_hoje("10:00:00"))

        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "reconsiderei com cotacao nova", "--sem-perdedores", "--comprado"]
        env = os.environ.copy()
        env["CENTRAL_COMPRAS_TESTE_CRASH_APOS"] = "veredito:iniciado"
        crash = subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, env=env, capture_output=True, text=True,
        )
        self.assertEqual(crash.returncode, 70, crash.stderr)
        # Pre-condicao: o veredito continua intocado pela tentativa que caiu.
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Valor pago"), cc.brl(200.0))
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), "")

        script.write_bytes(atual)
        retry = subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(retry.returncode, 0, retry.stderr)
        self.assertFalse(cc.pending_operations([project]))

        texto_final = veredito.read_text(encoding="utf-8")
        self.assertTrue(cc.extract_bullet(texto_final, "Data da compra"), "Data da compra tem que ter sido gravada")
        # ACHADO: Valor pago continua com o preco OBSOLETO de Q1 (R$200),
        # nunca atualizado para Q2 (R$999) - a checagem financeira nova foi
        # pulada porque esta chamada e uma RETOMADA (`retomando_decisao`).
        self.assertEqual(
            cc.extract_bullet(texto_final, "Valor pago"), cc.brl(200.0),
            "Valor pago ficou obsoleto - a checagem financeira nova nunca rodou nesta retomada",
        )
        self.assertNotEqual(cc.extract_bullet(texto_final, "Valor pago"), cc.brl(999.0))

    def test_journal_antigo_e048ad6_bypassa_protecao_de_exportacao_e_apaga_d30(self):
        """Achado 2 (exportacao), via journal antigo: veredito com D+30 JA
        EXPORTADO (marcador + licoes.md). `decidir candidato --force-
        veredito` (codigo de `e048ad6`, sem
        `_erro_force_veredito_apagaria_exportacao`) e interrompido ANTES de
        `create_verdict` rodar - journal congela `veredito_nome`, veredito
        continua com o D+30 intacto. Atualizando para o codigo ATUAL e
        retomando o MESMO comando: a checagem de exportacao nao roda (e
        retomada), `create_verdict` roda com `force=True` e reescreve o
        arquivo do zero - apagando o D+30 exportado, o mesmo sintoma do
        achado 2 que a correcao pretendia fechar."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")
        self.cli("preencher-veredito", str(veredito), "--fase", "d30",
                  "--nota-arrependimento", "9", "--compraria-de-novo", "sim",
                  "--resumo", "Otimo produto, avaliacao real de 30 dias de uso.")
        self.cli("aprender-veredito", str(veredito), "--fase", "d30",
                  "--licao", "Marca A entrega no prazo e o produto funciona bem.")
        texto_com_d30 = veredito.read_text(encoding="utf-8")
        self.assertIn("Aprendizado exportado D+30", texto_com_d30)
        licoes_antes = (cc.BASE / "licoes.md").read_bytes()

        script = self.root / "scripts" / "central_compras.py"
        atual = script.read_bytes()
        antigo_e048ad6 = subprocess.run(
            ["git", "show", "e048ad6:scripts/central_compras.py"],
            cwd=REPO, capture_output=True, check=True,
        ).stdout
        script.write_bytes(antigo_e048ad6)

        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "refazendo do zero", "--sem-perdedores", "--force-veredito"]
        env = os.environ.copy()
        env["CENTRAL_COMPRAS_TESTE_CRASH_APOS"] = "veredito:iniciado"
        crash = subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, env=env, capture_output=True, text=True,
        )
        self.assertEqual(crash.returncode, 70, crash.stderr)
        # Pre-condicao: o D+30 exportado continua intocado pela tentativa que caiu.
        self.assertIn("Aprendizado exportado D+30", veredito.read_text(encoding="utf-8"))

        script.write_bytes(atual)
        retry = subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(retry.returncode, 0, retry.stderr)
        self.assertFalse(cc.pending_operations([project]))

        texto_final = veredito.read_text(encoding="utf-8")
        # ACHADO: o D+30 exportado foi apagado - a protecao nova nunca
        # rodou nesta retomada.
        self.assertNotIn(
            "Aprendizado exportado D+30", texto_final,
            "o marcador de exportacao foi apagado - a protecao nova nunca rodou nesta retomada",
        )
        self.assertNotIn("Otimo produto, avaliacao real de 30 dias de uso.", texto_final)
        # A base de conhecimento (licoes.md) preserva o que ja foi
        # exportado (append-only) - so o VEREDITO perdeu a evidencia local.
        self.assertEqual((cc.BASE / "licoes.md").read_bytes(), licoes_antes)


class RegistrarEventoCompradoAssociaPrecoObsoletoTest(ambiente.RepoTestCase):
    """Foco 2 do roteiro: `registrar-evento --evento comprado` e um
    caminho TOTALMENTE separado de `decidir --comprado` para confirmar a
    mesma compra (fluxo documentado desde a sessao 20: decidir sem
    --comprado, confirmar depois). A correcao do achado 1 vive so dentro
    de `decide()` - `register_verdict_event` nunca leu cotacao nenhuma,
    entao nunca teve como comparar preco."""

    def test_registrar_evento_comprado_apos_redecisao_grava_data_certa_com_preco_obsoleto(self):
        dia1, dia2, dia3 = "2026-01-01", "2026-01-02", "2026-01-20"

        with patch.object(cc, "today", return_value=dia1):
            project = self.project()
            self.product(project, "candidato-a")
            self.product(project, "candidato-b")
            self.quote(project, "candidato-a", "--fonte", "manual", "--data", _hora_hoje("09:00:00"))
            self.cli("decidir", str(project), "--produto-id", "candidato-a",
                      "--porque", "primeira escolha", "--sem-perdedores")
        veredito_a = next(p for p in cc.VEREDITOS.glob("*.md")
                           if cc.extract_bullet(p.read_text(encoding="utf-8"), "Produto ID") == "candidato-a")
        self.assertEqual(cc.extract_bullet(veredito_a.read_text(encoding="utf-8"), "Valor pago"), cc.brl(200.0))

        with patch.object(cc, "today", return_value=dia2):
            self.quote(project, "candidato-b", "--fonte", "manual", "--data", _hora_hoje("09:30:00"))
            self.cli("decidir", str(project), "--produto-id", "candidato-b", "--porque",
                      "troquei de ideia", "--perdedores", "candidato-a: desisti por enquanto")

        # Reconsiderou, decide A de novo - MAS sem --comprado (so fecha a
        # escolha por enquanto) e com uma cotacao NOVA (preco diferente).
        # create_verdict, sem --comprado, retorna sem tocar em NADA no
        # veredito ja existente (nem sequer roda a checagem do achado 1,
        # que so se aplica com --comprado) - v1 continua com os dados de
        # Q1, mesmo decisao.md agora refletindo Q3.
        with patch.object(cc, "today", return_value=dia3):
            self.quote(project, "candidato-a", "--fonte", "manual", "--preco", "999", "--loja", "LojaNova",
                       "--data", _hora_hoje("10:00:00"))
            self.cli("decidir", str(project), "--produto-id", "candidato-a", "--porque",
                      "reconsiderei, escolhi A de novo com cotacao nova",
                      "--perdedores", "candidato-b: nao entregou")

        self.assertEqual(
            cc.extract_bullet((project / "decisao.md").read_text(encoding="utf-8"), "Custo total confirmado")
            or cc.extract_bullet((project / "decisao.md").read_text(encoding="utf-8"), "Custo total estimado"),
            cc.brl(999.0),
            "decisao.md tem que refletir a cotacao REAL desta redecisao (Q3)",
        )
        self.assertEqual(cc.extract_bullet(veredito_a.read_text(encoding="utf-8"), "Valor pago"), cc.brl(200.0))
        self.assertEqual(cc.extract_bullet(veredito_a.read_text(encoding="utf-8"), "Data da compra"), "")

        # Confirma a compra pelo caminho documentado (registrar-evento,
        # nao decidir --comprado de novo) - nada aqui olha para preco.
        with patch.object(cc, "today", return_value=dia3):
            self.cli("registrar-evento", str(veredito_a), "--evento", "comprado")

        texto_final = veredito_a.read_text(encoding="utf-8")
        self.assertEqual(cc.extract_bullet(texto_final, "Data da compra"), dia3)
        # ACHADO: a compra foi confirmada (Data da compra = dia3, a data
        # REAL) mas o veredito continua dizendo que o preco pago foi
        # R$200,00 (Q1, a cotacao da 1a escolha, JAMAIS paga de verdade) -
        # a decisao real (Q3, R$999,00) nunca chega ao veredito por este
        # caminho, porque `registrar-evento` nunca compara preco.
        self.assertEqual(
            cc.extract_bullet(texto_final, "Valor pago"), cc.brl(200.0),
            "Valor pago ficou obsoleto - registrar-evento nunca confere preco",
        )
        status = self.cli("status", str(project))
        self.assertIn("Estado: comprado", status)


class ControlesRetomadaLegitimaSemJournalAntigoTest(ambiente.RepoTestCase):
    """Controles: sob o codigo ATUAL, do INICIO AO FIM (sem journal de
    versao anterior no meio), uma falha e retomada legitima NAO deve ser
    bloqueada pelas checagens novas - elas ja rodaram (e passaram) na
    tentativa ORIGINAL, antes do journal existir."""

    def test_retomada_legitima_com_exportacao_ja_existente_nao_e_bloqueada(self):
        """Veredito ja tem D+30 exportado. Uma chamada NOVA com
        --force-veredito seria recusada (achado 2) - mas se essa MESMA
        chamada crashar e for retomada, a retomada tem que falhar da MESMA
        forma que a tentativa original (que nunca deveria ter passado da
        checagem), nunca silenciosamente destruir o D+30 so por ter virado
        uma retomada."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        self.cli("registrar-evento", str(veredito), "--evento", "entrega")
        self.cli("registrar-evento", str(veredito), "--evento", "inicio_uso")
        self.cli("preencher-veredito", str(veredito), "--fase", "d30",
                  "--nota-arrependimento", "9", "--compraria-de-novo", "sim", "--resumo", "foi bem")
        self.cli("aprender-veredito", str(veredito), "--fase", "d30", "--licao", "confirmar garantia")
        texto_antes = veredito.read_bytes()

        # Chamada NOVA com --force-veredito: recusada de cara (achado 2),
        # NUNCA chega perto de `tracked_operation` - nenhum journal criado.
        with self.assertRaisesRegex(SystemExit, "ja tem aprendizado exportado"):
            self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                      "de novo", "--sem-perdedores", "--force-veredito")
        self.assertFalse(cc.pending_operations([project]), "recusa antes da checagem nao pode deixar journal")
        self.assertEqual(veredito.read_bytes(), texto_antes)


class ControlePassoJaConcluidoNaoPodeFicarPresoTest(ambiente.RepoTestCase):
    """Controle para o PROMPT DE CORRECAO desta rodada: qualquer fechamento
    dos achados 1/1b/2 (rodar as checagens tambem numa retomada) precisa
    diferenciar um passo "veredito" JA CONCLUIDO (escrita real ja
    aconteceu, sob codigo antigo ou novo - bloquear so travaria uma
    operacao legitimamente recuperavel presa para sempre, sem solucao) de
    um passo AINDA NAO TENTADO/incompleto (onde a checagem faz sentido -
    e o caso dos 2 achados desta revisao, sempre crash ANTES do passo
    "veredito" concluir). Este teste PASSA hoje (nao e achado, e
    comportamento correto ja existente) - serve para provar que o
    fechamento futuro nao pode quebrar isto."""

    def test_journal_com_passo_veredito_ja_concluido_continua_retomavel(self):
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))

        script = self.root / "scripts" / "central_compras.py"
        atual = script.read_bytes()
        antigo_e048ad6 = subprocess.run(
            ["git", "show", "e048ad6:scripts/central_compras.py"],
            cwd=REPO, capture_output=True, check=True,
        ).stdout
        script.write_bytes(antigo_e048ad6)

        args = ["decidir", str(project), "--produto-id", "candidato", "--porque",
                "de novo", "--sem-perdedores", "--comprado"]
        env = os.environ.copy()
        # Crash DEPOIS do passo "veredito" concluir (create_verdict ja
        # rodou, Data da compra ja gravada), mas ANTES do proximo passo
        # (timeline_veredito) - journal fica pendente com "veredito":
        # {"situacao": "concluido"}.
        env["CENTRAL_COMPRAS_TESTE_CRASH_APOS"] = "timeline_veredito:iniciado"
        crash = subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, env=env, capture_output=True, text=True,
        )
        self.assertEqual(crash.returncode, 70, crash.stderr)

        import json as _json
        journal = next((project / ".operacoes").glob("*.json"))
        registro = _json.loads(journal.read_text(encoding="utf-8"))
        self.assertEqual(registro["passos"]["veredito"]["situacao"], "concluido",
                         "pre-condicao: o passo veredito ja tem que estar concluido")
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), cc.today())

        script.write_bytes(atual)
        retry = subprocess.run(
            [sys.executable, str(script), *args], cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(
            retry.returncode, 0,
            "uma retomada cujo passo veredito JA concluiu tem que continuar terminando com sucesso: "
            + retry.stderr,
        )
        self.assertFalse(cc.pending_operations([project]))


if __name__ == "__main__":
    unittest.main()
