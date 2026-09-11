"""7a revisao adversarial independente da frente 6, cobrindo CONJUNTAMENTE
os commits `68c3dbf` (retomada de journal antigo tambem valida financeiro/
exportacao - achados A/B) e `822096b` (achado C - `registrar-evento`
tambem valida dado financeiro).

Nao faz parte da suite oficial de proposito (nome do arquivo nao comeca
com `test_`, entao `python -m unittest discover -s tests` NAO coleta isto
- os achados aqui ainda nao foram corrigidos em producao, e a suite
oficial tem que continuar 100% verde). Rodar manualmente com:

    python -m unittest discover -s tests -p "revisao_independente_68c3dbf_822096b.py" -v

Guardado em caminho persistente do repositorio (nao em %TEMP%). Ver
STATUS.md e a secao 6 de docs/plano-pendencias-auditoria-2026-09-06.md
para o relato completo desta rodada.
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


class EscritaJaRealizadaVsDadoCoincidenteTest(ambiente.RepoTestCase):
    """Foco 3 do roteiro: a checagem financeira do achado C (e, pelo mesmo
    padrao, do achado A em `decide()`) pula a validacao quando o campo
    JA BATE com o valor CONGELADO na operacao pendente - mas "o campo ja
    bate" nao prova que ESTA operacao pendente foi quem escreveu. Um valor
    IDENTICO gravado por qualquer OUTRO meio (edicao manual, outro
    comando) engana a mesma checagem."""

    def test_valor_preexistente_de_edicao_manual_engana_a_checagem_e_confirma_compra_incompativel(self):
        """Cenario: `registrar-evento --evento comprado` comeca, cai ANTES
        de gravar (journal congela `data_efetiva`=hoje). Antes da retomada,
        o Josemar edita o veredito A MAO (corrigindo outra coisa qualquer,
        ou por qualquer motivo) e digita `Data da compra: hoje` - o MESMO
        valor que o journal pendente ja tinha congelado, por coincidencia
        (data de hoje e o valor mais comum de se digitar). A decisao do
        projeto TAMBEM mudou nesse meio tempo (redecidiu o mesmo produto
        com uma cotacao nova, sem --comprado). Retomando o `registrar-
        evento` pendente: a checagem financeira nova compara `existente`
        (a data que acabou de ser digitada a mao) contra `data_para_validacao`
        (a data CONGELADA do journal) - sao IGUAIS por coincidencia, entao
        a checagem financeira e PULADA - mesmo o veredito nunca tendo sido
        validado contra a cotacao atual da decisao."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato",
                  "--porque", "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))

        def crash(ponto):
            if ponto == "evento:iniciado":
                raise OSError("falha antes de gravar o evento")

        with patch.object(cc, "_crash_de_teste_se_pedido", side_effect=crash):
            with self.assertRaises(OSError):
                self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        self.assertTrue(cc.pending_operations([cc.BASE]), "pre-condicao: journal pendente existe")
        self.assertEqual(cc.extract_bullet(veredito.read_text(encoding="utf-8"), "Data da compra"), "")

        # "Edicao manual" (ou qualquer outro meio fora deste comando) grava
        # a MESMA data que o journal pendente ja tinha congelado - sem
        # NENHUMA validacao financeira ter rodado sobre esse valor.
        cc.atomic_write_text(
            veredito,
            cc.replace_or_append_bullet(veredito.read_text(encoding="utf-8"), "Data da compra", cc.today()),
        )

        # A decisao do projeto "mudou" nesse meio tempo - simulado direto
        # em decisao.md (o journal pendente ja reivindica processo.md como
        # recurso - `cotar`/`decidir` de verdade seriam bloqueados
        # enquanto essa pendencia existir; a mutacao direta isola a
        # questao logica sendo testada aqui, sem depender de contornar a
        # trava de recursos). O veredito continua com os dados
        # FINANCEIROS antigos - so a Data da compra foi editada a mao.
        cc.atomic_write_text(
            project / "decisao.md",
            cc.replace_or_append_bullet(
                (project / "decisao.md").read_text(encoding="utf-8"), "Custo total confirmado", cc.brl(999.0),
            ),
        )

        licoes_antes = (cc.BASE / "licoes.md").read_bytes()

        # Retomando o registrar-evento pendente: a checagem financeira
        # deveria recusar (o veredito - Valor pago R$200 - nao bate com a
        # decisao atual - R$999) mas e PULADA pela coincidencia de data.
        self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        texto_final = veredito.read_text(encoding="utf-8")
        status = self.cli("status", str(project))
        # ACHADO: a compra foi "confirmada" (projeto marcado comprado) com
        # o veredito ainda mostrando o preco OBSOLETO (R$200), nunca
        # validado contra a cotacao real da decisao atual (R$999) - a
        # checagem financeira nova nunca rodou, enganada pela coincidencia
        # de data.
        self.assertEqual(cc.extract_bullet(texto_final, "Valor pago"), cc.brl(200.0))
        self.assertIn("Estado: comprado", status,
                      "ACHADO: projeto marcado comprado com dado financeiro nunca validado")
        self.assertEqual((cc.BASE / "licoes.md").read_bytes(), licoes_antes)


class EvidenciaFinanceiraAusenteTest(ambiente.RepoTestCase):
    """Foco 1 do roteiro: `_divergencias_financeiras` so compara campos
    PREENCHIDOS dos dois lados - ausencia de evidencia (label vazio em
    `decisao.md`, formato legado sem `Cotacao usada`/`Custo total...`)
    nunca e tratada como divergencia. Isso protege contra "inventar
    valor", mas tambem significa que `decisao.md` incompleto faz a
    checagem do achado C ficar CEGA, sem avisar ninguem."""

    def test_decisao_sem_evidencia_financeira_completa_deixa_a_checagem_cega(self):
        """`decisao.md` sem `Cotacao usada`/`Custo total...` (formato
        legado, ou corrompido) - `_evidencia_financeira_da_decisao`
        devolve tudo vazio, `_divergencias_financeiras` nunca acha
        divergencia nenhuma, e a compra e confirmada mesmo com o veredito
        tendo QUALQUER preco, sem checagem nenhuma - e sem avisar que a
        checagem nao rodou de verdade."""
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")
        self.cli("decidir", str(project), "--produto-id", "candidato",
                  "--porque", "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))

        # Simula decisao.md de formato ANTIGO/incompleto - sem a evidencia
        # financeira que a versao atual sempre grava.
        decisao_path = project / "decisao.md"
        texto_decisao = decisao_path.read_text(encoding="utf-8")
        import re as _re
        texto_decisao = _re.sub(r"(?m)^- Cotacao usada:.*$", "", texto_decisao)
        texto_decisao = _re.sub(r"(?m)^- Custo total confirmado:.*$", "", texto_decisao)
        cc.atomic_write_text(decisao_path, texto_decisao)
        self.assertEqual(cc.extract_bullet(texto_decisao, "Cotacao usada"), "")

        # Veredito com um preco absurdamente diferente do que foi de fato
        # cotado - simula corrupcao/dado obsoleto que a checagem deveria
        # pegar, mas nao pode, porque nao ha evidencia pra comparar.
        cc.atomic_write_text(
            veredito,
            cc.replace_or_append_bullet(veredito.read_text(encoding="utf-8"), "Valor pago", cc.brl(99999.0)),
        )

        self.cli("registrar-evento", str(veredito), "--evento", "comprado")

        status = self.cli("status", str(project))
        # ACHADO: confirmado sem nenhum aviso de que a checagem nao pode
        # validar nada (evidencia ausente em decisao.md).
        self.assertIn("Estado: comprado", status,
                      "ACHADO: compra confirmada sem checagem financeira nenhuma, sem aviso")


class JournalAntigoRegistrarEventoTest(ambiente.RepoTestCase):
    """Foco 4 do roteiro, especifico do achado C: journal de
    `registrar-evento` criado pelo codigo do commit `68c3dbf` (ANTES do
    achado C existir), retomado com o codigo atual - ao contrario dos
    achados A/B em `decide()` (que so rodavam a checagem quando
    `not retomando_decisao`), a checagem do achado C usa
    `existente != data_para_validacao`, sem depender de
    `retomando_propria` - hipotese: journal antigo NAO deveria bypassar a
    checagem quando a escrita ainda nao aconteceu. Controle, nao achado
    esperado."""

    def test_journal_antigo_68c3dbf_retomado_ainda_recusa_divergencia_financeira(self):
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual")

        script = self.root / "scripts" / "central_compras.py"
        atual = script.read_bytes()
        antigo_68c3dbf = subprocess.run(
            ["git", "show", "68c3dbf:scripts/central_compras.py"],
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

        # decisao.md "muda" sem tocar no veredito - mutacao direta, ja que
        # o journal pendente reivindica processo.md como recurso e
        # bloquearia um `decidir`/`cotar` de verdade neste meio tempo.
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


class IdentidadeENomeacaoTest(ambiente.RepoTestCase):
    """Foco 5 do roteiro: veredito renomeado a mao continua protegido pelo
    achado C (a associacao e por CONTEUDO - Projeto/Produto ID - nunca
    pelo nome do arquivo)."""

    def test_veredito_renomeado_continua_protegido_pelo_achado_c(self):
        # `data_coleta` vem do relogio real (resolucao de SEGUNDO) - fixar
        # `--data` com horarios distintos no mesmo dia real evita que as
        # duas cotacoes empatem no mesmo segundo e o desempate por preco
        # mais barato (proposital em `latest_quotes`) mascare a
        # divergencia que este teste precisa forcar.
        hoje = dt.date.today().isoformat()
        project = self.project()
        self.product(project, "candidato")
        self.quote(project, "candidato", "--fonte", "manual", "--data", f"{hoje}T09:00:00")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "unico candidato", "--sem-perdedores")
        veredito = next(cc.VEREDITOS.glob("*.md"))
        novo_nome = cc.VEREDITOS / "veredito-renomeado-a-mao.md"
        veredito.rename(novo_nome)

        self.quote(project, "candidato", "--fonte", "manual", "--preco", "999", "--loja", "LojaNova",
                   "--data", f"{hoje}T10:00:00")
        self.cli("decidir", str(project), "--produto-id", "candidato", "--porque",
                  "redecidi", "--sem-perdedores")

        with self.assertRaisesRegex(SystemExit, "dados financeiros diferentes"):
            self.cli("registrar-evento", str(novo_nome), "--evento", "comprado")
        self.assertEqual(cc.extract_bullet(novo_nome.read_text(encoding="utf-8"), "Data da compra"), "")


if __name__ == "__main__":
    unittest.main()
