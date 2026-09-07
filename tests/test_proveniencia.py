"""Proveniencia por campo comercial (frente 4 do plano de pendencias).

Cada observacao de cotacoes.csv carrega, na coluna `proveniencia` (JSON),
origem/evidencia/data/estado para os 6 campos comerciais (preco, variacao,
vendedor, frete, estoque, garantia) - amarrado aquela linha, nunca ao
produto em geral. `fonte` (web/manual) sozinho nao prova proveniencia
detalhada; `confirmacao` (texto livre) tambem nao - os dois continuam
existindo, mas nao sao mais a unica fonte da verdade sobre o que foi
conferido.

Sem mock: CLI real via ambiente.RepoTestCase, cotacoes.csv real em disco.
"""
import json
import unittest
from pathlib import Path

import ambiente

from scripts import central_compras as cc


class ParseProveniencia(unittest.TestCase):
    """parse_proveniencia() e pura - sem CLI, sem disco."""

    def test_linha_sem_a_coluna_vira_legado_sem_evidencia_nos_6_campos(self):
        prov = cc.parse_proveniencia({"loja": "Amazon", "preco": "100"})
        self.assertEqual(set(prov.keys()), set(cc.PROVENIENCIA_CAMPOS))
        for campo in cc.PROVENIENCIA_CAMPOS:
            self.assertEqual(prov[campo]["origem"], cc.PROVENIENCIA_ORIGEM_LEGADO)
            self.assertEqual(prov[campo]["estado"], "nao_conferido")
            self.assertIsNone(prov[campo]["data"])
            self.assertEqual(prov[campo]["evidencia"], "")

    def test_json_ilegivel_nunca_derruba_a_leitura_nem_fabrica_evidencia(self):
        prov = cc.parse_proveniencia({"proveniencia": "{nao e json valido"})
        for campo in cc.PROVENIENCIA_CAMPOS:
            self.assertEqual(prov[campo]["origem"], cc.PROVENIENCIA_ORIGEM_LEGADO)

    def test_json_com_origem_desconhecida_tambem_cai_no_legado(self):
        # Protege contra um valor futuro/estranho no campo origem virar
        # "conferido" por engano so porque o JSON parseou.
        bruto = json.dumps({"preco": {"origem": "chute", "estado": "conferido"}})
        prov = cc.parse_proveniencia({"proveniencia": bruto})
        self.assertEqual(prov["preco"]["origem"], cc.PROVENIENCIA_ORIGEM_LEGADO)

    def test_campo_ausente_do_json_tambem_vira_legado(self):
        bruto = json.dumps({"preco": {"origem": "observacao_direta", "estado": "conferido", "evidencia": "", "data": "2026-09-07"}})
        prov = cc.parse_proveniencia({"proveniencia": bruto})
        self.assertEqual(prov["preco"]["origem"], "observacao_direta")
        self.assertEqual(prov["garantia"]["origem"], cc.PROVENIENCIA_ORIGEM_LEGADO)


class ColetaCLI(ambiente.RepoTestCase):
    """`cotar`: relatorio de IA continua identificado como tal; estoque so
    vira conferido se de fato informado."""

    def test_relatorio_ia_fica_marcado_como_tal_na_linha(self):
        project = self.project()
        self.product(project)
        self.cli(
            "cotar", str(project), "--produto-id", "candidato", "--loja", "Amazon",
            "--vendedor", "V", "--vendedor-tipo", "oficial", "--preco", "200",
            "--nota", "4.8", "--avaliacoes", "1000", "--garantia-tipo", "nacional",
            "--garantia-meses", "12", "--link", "https://example.invalid/item",
            "--fonte", "web",
            "--origem-dados", "relatorio_ia", "--evidencia", "relatorio-2026-09-07.md",
        )
        linhas = cc.read_quotes(project)
        prov = cc.parse_proveniencia(linhas[-1])
        self.assertEqual(prov["preco"]["origem"], "relatorio_ia")
        self.assertEqual(prov["preco"]["evidencia"], "relatorio-2026-09-07.md")
        self.assertEqual(prov["preco"]["estado"], "conferido")

    def test_estoque_sem_flag_fica_sem_evidencia_com_flag_fica_conferido(self):
        project = self.project()
        self.product(project)
        self.quote(project)
        sem = cc.parse_proveniencia(cc.read_quotes(project)[-1])
        self.assertEqual(sem["estoque"]["origem"], cc.PROVENIENCIA_ORIGEM_LEGADO)
        self.assertEqual(cc.read_quotes(project)[-1]["estoque"], "")

        self.quote(project, "candidato", "--estoque", "disponivel")
        com = cc.parse_proveniencia(cc.read_quotes(project)[-1])
        self.assertEqual(com["estoque"]["origem"], "observacao_direta")
        self.assertEqual(com["estoque"]["estado"], "conferido")
        self.assertEqual(cc.read_quotes(project)[-1]["estoque"], "disponivel")

    def test_default_e_observacao_direta_sem_flag_de_origem(self):
        project = self.project()
        self.product(project)
        self.quote(project)
        prov = cc.parse_proveniencia(cc.read_quotes(project)[-1])
        self.assertEqual(prov["preco"]["origem"], "observacao_direta")
        self.assertEqual(prov["preco"]["estado"], "conferido")


class PromocaoParcial(ambiente.RepoTestCase):
    """`promover-cotacao`: confirmacao parcial afeta so os campos
    conferidos - o resto herda a proveniencia da cotacao base, sem virar
    'conferido' por tabela."""

    def test_promover_so_preco_nao_toca_a_proveniencia_de_garantia_ou_vendedor(self):
        project = self.project()
        self.product(project)
        self.quote(project, "candidato", "--origem-dados", "relatorio_ia", "--evidencia", "relatorio-base.md")
        base_prov = cc.parse_proveniencia(cc.read_quotes(project)[-1])
        self.assertEqual(base_prov["garantia"]["origem"], "relatorio_ia")

        self.cli(
            "promover-cotacao", str(project), "--produto-id", "candidato",
            "--preco", "195", "--origem-dados", "conferencia_humana", "--evidencia", "conferi no site",
        )
        nova = cc.read_quotes(project)[-1]
        prov = cc.parse_proveniencia(nova)
        # So preco foi conferido AGORA.
        self.assertEqual(prov["preco"]["origem"], "conferencia_humana")
        self.assertEqual(prov["preco"]["estado"], "conferido")
        self.assertEqual(prov["preco"]["evidencia"], "conferi no site")
        # Garantia, vendedor, frete, variacao e estoque continuam com a
        # proveniencia HERDADA da base (relatorio_ia) - nao viraram
        # "conferencia_humana" so porque a linha inteira foi promovida.
        self.assertEqual(prov["garantia"]["origem"], "relatorio_ia")
        self.assertEqual(prov["vendedor"]["origem"], "relatorio_ia")
        self.assertEqual(prov["frete"]["origem"], "relatorio_ia")

    def test_nova_cotacao_preserva_a_cotacao_anterior_e_sua_origem(self):
        # Append-only: a promocao nunca reescreve a linha base. A proveniencia
        # antiga continua legivel na linha antiga, intocada.
        project = self.project()
        self.product(project)
        self.quote(project, "candidato", "--origem-dados", "relatorio_ia")
        antes = list(cc.read_quotes(project))
        self.assertEqual(len(antes), 1)
        prov_antes = cc.parse_proveniencia(antes[0])

        self.cli("promover-cotacao", str(project), "--produto-id", "candidato", "--preco", "195")

        depois = cc.read_quotes(project)
        self.assertEqual(len(depois), 2, "promover tem que ACRESCENTAR linha, nunca substituir")
        self.assertEqual(depois[0], antes[0], "a linha antiga nao pode mudar um unico campo")
        self.assertEqual(cc.parse_proveniencia(depois[0]), prov_antes)

    def test_sem_alteracao_reconfirma_todos_os_6_campos(self):
        project = self.project()
        self.product(project)
        self.quote(project, "candidato", "--origem-dados", "relatorio_ia")
        self.cli("promover-cotacao", str(project), "--produto-id", "candidato", "--sem-alteracao")
        prov = cc.parse_proveniencia(cc.read_quotes(project)[-1])
        for campo in cc.PROVENIENCIA_CAMPOS:
            if campo == "estoque":
                continue  # nunca foi informado em nenhuma das duas chamadas
            self.assertEqual(prov[campo]["estado"], "conferido", campo)
            self.assertEqual(prov[campo]["origem"], "conferencia_humana", campo)


class RegistrosLegados(ambiente.RepoTestCase):
    """Uma cotacao gravada ANTES desta frente (sem a coluna proveniencia)
    continua legivel e nunca ganha evidencia fabricada."""

    def test_linha_legada_sem_coluna_proveniencia_continua_utilizavel(self):
        project = self.project()
        self.product(project)
        self.quote(project)
        # Simula uma linha de antes desta frente: reescreve o cotacoes.csv
        # sem a coluna proveniencia (como um cotacoes.csv historico real).
        caminho = project / "cotacoes.csv"
        conteudo = caminho.read_text(encoding="utf-8")
        header, resto = conteudo.split("\n", 1)
        colunas = header.split(",")
        idx_estoque = colunas.index("estoque")
        colunas_legadas = colunas[:idx_estoque]
        linhas_legadas = []
        for linha in resto.splitlines():
            if not linha:
                continue
            valores = linha.split(",")
            linhas_legadas.append(",".join(valores[:idx_estoque]))
        caminho.write_text(",".join(colunas_legadas) + "\n" + "\n".join(linhas_legadas) + "\n", encoding="utf-8")

        linhas = cc.read_quotes(project)
        self.assertEqual(len(linhas), 1)
        self.assertNotIn("proveniencia", cc.raw_quotes_header(project))
        prov = cc.parse_proveniencia(linhas[0])
        for campo in cc.PROVENIENCIA_CAMPOS:
            self.assertEqual(prov[campo]["origem"], cc.PROVENIENCIA_ORIGEM_LEGADO)
        # migrar-cotacoes adiciona a coluna sem inventar proveniencia pras
        # linhas antigas nem perder nenhuma.
        self.cli("migrar-cotacoes", "--projeto", str(project))
        self.assertIn("proveniencia", cc.raw_quotes_header(project))
        self.assertIn("estoque", cc.raw_quotes_header(project))
        migradas = cc.read_quotes(project)
        self.assertEqual(len(migradas), 1)
        prov_migrada = cc.parse_proveniencia(migradas[0])
        for campo in cc.PROVENIENCIA_CAMPOS:
            self.assertEqual(prov_migrada[campo]["origem"], cc.PROVENIENCIA_ORIGEM_LEGADO)

    def test_fonte_manual_sozinho_nao_vira_conferido_pra_tudo(self):
        # fonte=manual, isoladamente, nao comprova proveniencia detalhada -
        # uma linha manual sem proveniencia gravada ainda e "legado sem
        # evidencia" campo a campo.
        row = {"fonte": "manual", "confirmacao": "coleta"}
        prov = cc.parse_proveniencia(row)
        for campo in cc.PROVENIENCIA_CAMPOS:
            self.assertEqual(prov[campo]["origem"], cc.PROVENIENCIA_ORIGEM_LEGADO)
            self.assertEqual(prov[campo]["estado"], "nao_conferido")


class PainelMesmoContrato(ambiente.RepoTestCase):
    """O painel grava pelo MESMO caminho da CLI (`cc.main(["cotar", ...])`),
    entao usa o mesmo contrato de proveniencia sem reimplementar nada."""

    def test_painel_inclui_os_campos_novos_no_formulario_de_cotar(self):
        from scripts import painel
        for campo in ("estoque", "origem_dados", "evidencia"):
            self.assertIn(campo, painel.CAMPOS_COTACAO)

    def test_gravar_cotacao_pelo_painel_produz_a_mesma_proveniencia_que_a_cli(self):
        from scripts import painel
        project = self.project()
        self.product(project)
        resultado = painel._gravar_cotacao(project, {
            "produto_id": "candidato", "loja": "Amazon", "vendedor": "V",
            "vendedor_tipo": "oficial", "preco": "200", "nota": "4.8",
            "avaliacoes": "1000", "garantia_tipo": "nacional", "garantia_meses": "12",
            "fonte": "web", "estoque": "disponivel",
            "origem_dados": "relatorio_ia", "evidencia": "relatorio-x.md",
        })
        self.assertTrue(resultado["ok"], resultado)
        linha = cc.read_quotes(project)[-1]
        self.assertEqual(linha["estoque"], "disponivel")
        prov = cc.parse_proveniencia(linha)
        self.assertEqual(prov["preco"]["origem"], "relatorio_ia")
        self.assertEqual(prov["preco"]["evidencia"], "relatorio-x.md")
        self.assertEqual(prov["estoque"]["origem"], "relatorio_ia")

    def test_estado_do_painel_expoe_proveniencia_no_ranking_e_nas_ultimas(self):
        from scripts import painel
        project = self.project()
        self.product(project)
        self.quote(project, "candidato", "--origem-dados", "relatorio_ia")
        e = painel.estado(project)
        self.assertTrue(e["elegiveis"] or e["cortados"])
        linha_ranking = (e["elegiveis"] + e["cortados"])[0]
        self.assertIn("proveniencia", linha_ranking)
        self.assertEqual(linha_ranking["proveniencia"]["preco"]["origem"], "relatorio_ia")
        self.assertTrue(e["ultimas"])
        self.assertIn("proveniencia", e["ultimas"][0])
        self.assertEqual(e["ultimas"][0]["proveniencia"]["preco"]["origem"], "relatorio_ia")


class SnapshotPreservaProveniencia(ambiente.RepoTestCase):
    """Uma decisao congela a cotacao vencedora (com a proveniencia dela)
    no snapshot; uma promocao POSTERIOR nunca altera essa evidencia
    congelada."""

    def test_snapshot_conserva_valores_e_proveniencia_apos_promocao_posterior(self):
        project = self.project()
        self.product(project)
        self.quote(project, "candidato", "--origem-dados", "relatorio_ia", "--evidencia", "relatorio-inicial.md")
        self.cli(
            "decidir", str(project), "--produto-id", "candidato",
            "--porque", "unico candidato", "--sem-perdedores", "--comprado", "--permitir-web",
        )
        snapshot_dir = next((project / "snapshots").glob("*-candidato"))
        metadados_antes = json.loads((snapshot_dir / "metadados.json").read_text(encoding="utf-8"))
        prov_congelada = cc.parse_proveniencia(metadados_antes["cotacao"])
        self.assertEqual(prov_congelada["preco"]["origem"], "relatorio_ia")
        self.assertEqual(prov_congelada["preco"]["evidencia"], "relatorio-inicial.md")
        cotacoes_csv_congelado = (snapshot_dir / "cotacoes.csv").read_text(encoding="utf-8")

        # Uma nova observacao DEPOIS da decisao (ex.: conferencia humana
        # posterior) nunca pode voltar no tempo e mudar o que a decisao
        # gravou como evidencia.
        self.cli(
            "promover-cotacao", str(project), "--produto-id", "candidato",
            "--preco", "180", "--origem-dados", "conferencia_humana", "--evidencia", "conferi depois",
        )

        metadados_depois = json.loads((snapshot_dir / "metadados.json").read_text(encoding="utf-8"))
        self.assertEqual(metadados_depois, metadados_antes, "o snapshot nao pode mudar depois de gravado")
        self.assertEqual(
            (snapshot_dir / "cotacoes.csv").read_text(encoding="utf-8"), cotacoes_csv_congelado,
            "a copia congelada de cotacoes.csv nao pode ganhar a linha nova",
        )
        prov_ainda_congelada = cc.parse_proveniencia(json.loads((snapshot_dir / "metadados.json").read_text(encoding="utf-8"))["cotacao"])
        self.assertEqual(prov_ainda_congelada["preco"]["origem"], "relatorio_ia")
        self.assertEqual(prov_ainda_congelada["preco"]["evidencia"], "relatorio-inicial.md")

        # A auditoria continua batendo (nada foi adulterado).
        self.cli("auditar-decisoes", str(project), "--strict")


class SemReferenciasOrfas(ambiente.RepoTestCase):
    """Duas observacoes seguidas nunca compartilham nem misturam
    proveniencia - cada linha e independente."""

    def test_duas_cotacoes_do_mesmo_produto_tem_proveniencias_independentes(self):
        project = self.project()
        self.product(project)
        self.quote(project, "candidato", "--origem-dados", "relatorio_ia", "--evidencia", "relatorio-1.md")
        self.quote(project, "candidato", "--origem-dados", "observacao_direta", "--evidencia", "relatorio-2.md")
        linhas = cc.read_quotes(project)
        self.assertEqual(len(linhas), 2)
        prov1 = cc.parse_proveniencia(linhas[0])
        prov2 = cc.parse_proveniencia(linhas[1])
        self.assertEqual(prov1["preco"]["origem"], "relatorio_ia")
        self.assertEqual(prov1["preco"]["evidencia"], "relatorio-1.md")
        self.assertEqual(prov2["preco"]["origem"], "observacao_direta")
        self.assertEqual(prov2["preco"]["evidencia"], "relatorio-2.md")
        # Mutar o dict devolvido por uma nao pode vazar pra outra (cada
        # parse_proveniencia() precisa devolver objetos independentes).
        prov1["preco"]["origem"] = "adulterado"
        self.assertEqual(cc.parse_proveniencia(linhas[1])["preco"]["origem"], "observacao_direta")

    def test_erro_no_meio_da_promocao_nao_deixa_linha_parcial(self):
        # promover-cotacao sem nenhum campo conferido e sem --sem-alteracao
        # tem que recusar ANTES de qualquer escrita - nao pode aparecer
        # meia-linha em cotacoes.csv.
        project = self.project()
        self.product(project)
        self.quote(project)
        antes = cc.read_quotes(project)
        with self.assertRaises(SystemExit):
            self.cli("promover-cotacao", str(project), "--produto-id", "candidato")
        depois = cc.read_quotes(project)
        self.assertEqual(antes, depois)


if __name__ == "__main__":
    unittest.main()
