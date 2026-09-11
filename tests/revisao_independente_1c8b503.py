"""Revisao adversarial independente do commit `1c8b503` (frente 6, 6a
revisao independente - `docs/plano-pendencias-auditoria-2026-09-06.md`,
secao 6).

**Estado apos a correcao da sessao seguinte**: os achados A (checagem
financeira pulada numa retomada de journal antigo) e B (protecao de
exportacao pulada numa retomada de journal antigo) foram corrigidos e as
reproducoes correspondentes MOVIDAS para
`tests/test_frente6_datas_veredito.py`, classe
`SetimaRevisaoIndependenteFrente6Test` (parte da suite oficial). O achado
D (mensagem sugerindo editar `cotacoes.csv`) tambem foi corrigido, coberto
la.

**O que continua aqui, deliberadamente**: o achado C
(`registrar-evento --evento comprado` nunca confere preco/cotacao - gap
mais amplo que os journals antigos, ver STATUS.md e a secao 6 do plano).
Classificado como EXPANSAO DE ESCOPO de `registrar-evento` (que nunca teve
nocao de preco, por design), nao decisao tecnica automatica - fica como
pergunta pendente ao Josemar. Esta reproducao segue fora da suite oficial
de proposito (nome do arquivo nao comeca com `test_`) ate ele decidir o
contrato.

Rodar manualmente com:

    python -m unittest discover -s tests -p "revisao_independente_1c8b503.py" -v
"""

import datetime as dt
import unittest
from unittest.mock import patch

import ambiente
from scripts import central_compras as cc


def _hora_hoje(hhmmss: str) -> str:
    """`data_coleta` vem do relogio real (`now_iso()`, nunca mockado por
    `patch.object(cc, "today", ...)`), com resolucao de SEGUNDO - fixar
    `--data` explicitamente evita que duas cotacoes no mesmo segundo
    empatem e o desempate por preco mais barato (proposital em
    `latest_quotes`) mascare a cotacao que o teste realmente quer usar."""
    return f"{dt.date.today().isoformat()}T{hhmmss}"


class RegistrarEventoCompradoAssociaPrecoObsoletoTest(ambiente.RepoTestCase):
    """Achado C (ainda ABERTO): `registrar-evento --evento comprado` e um
    caminho TOTALMENTE separado de `decidir --comprado` para confirmar a
    mesma compra (fluxo documentado desde a sessao 20: decidir sem
    --comprado, confirmar depois). As checagens da 5a/7a correcao vivem so
    dentro de `decide()` - `register_verdict_event` nunca leu cotacao
    nenhuma, entao nunca teve como comparar preco."""

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
        # ACHADO C (aberto, pendente de decisao de contrato com o Josemar):
        # a compra foi confirmada (Data da compra = dia3, a data REAL) mas
        # o veredito continua dizendo que o preco pago foi R$200,00 (Q1, a
        # cotacao da 1a escolha, JAMAIS paga de verdade) - a decisao real
        # (Q3, R$999,00) nunca chega ao veredito por este caminho, porque
        # `registrar-evento` nunca compara preco.
        self.assertEqual(
            cc.extract_bullet(texto_final, "Valor pago"), cc.brl(200.0),
            "Valor pago ficou obsoleto - registrar-evento nunca confere preco (achado C, aberto)",
        )
        status = self.cli("status", str(project))
        self.assertIn("Estado: comprado", status)


if __name__ == "__main__":
    unittest.main()
