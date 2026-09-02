"""Estrelas absolutas no comparativo de caracteristicas.

Cada funcao aqui recebe SO um valor por vez, nunca uma lista de candidatos -
isso torna estruturalmente impossivel ranquear um candidato contra o outro:
empate e o resultado padrao quando o valor normalizado e igual, nao uma
coincidencia que um teste precisa torcer pra acontecer.
"""

import unittest

from scripts import central_compras as cc


class StarsFromFaixasTest(unittest.TestCase):
    def test_highest_qualifying_band_wins(self):
        faixas = [
            {"min": 8, "estrelas": 5},
            {"min": 3, "estrelas": 4},
            {"min": 1.9, "estrelas": 3},
            {"min": 1, "estrelas": 2},
            {"min": 0, "estrelas": 1},
        ]
        self.assertEqual(cc._stars_from_faixas(faixas, 4), 4)
        self.assertEqual(cc._stars_from_faixas(faixas, 16), 5)
        self.assertEqual(cc._stars_from_faixas(faixas, 0.5), 1)

    def test_boundary_value_uses_that_band(self):
        faixas = [{"min": 8, "estrelas": 5}, {"min": 3, "estrelas": 4}]
        self.assertEqual(cc._stars_from_faixas(faixas, 8), 5)
        self.assertEqual(cc._stars_from_faixas(faixas, 7.99), 4)

    def test_out_of_order_faixas_still_classify_correctly(self):
        # A lista chega do YAML fora de ordem (alguem colou errado). A funcao
        # nao pode confiar na ordem do arquivo - tem que ordenar por conta
        # propria, senao a primeira faixa que bater "ganha" por acidente.
        fora_de_ordem = [
            {"min": 1, "estrelas": 2},
            {"min": 8, "estrelas": 5},
            {"min": 0, "estrelas": 1},
            {"min": 3, "estrelas": 4},
        ]
        self.assertEqual(cc._stars_from_faixas(fora_de_ordem, 4), 4)
        self.assertEqual(cc._stars_from_faixas(fora_de_ordem, 16), 5)

    def test_non_numeric_value_is_unrated_not_guessed(self):
        faixas = [{"min": 0, "estrelas": 1}]
        self.assertIsNone(cc._stars_from_faixas(faixas, "nao-e-numero"))


class StarsFromValoresTest(unittest.TestCase):
    def test_exact_match(self):
        valores = {"colorida_holofote": 5, "colorida": 4, "monocromatica": 3}
        self.assertEqual(cc._stars_from_valores(valores, "colorida"), 4)

    def test_unmapped_value_is_unrated_not_guessed(self):
        valores = {"confirmado": 5}
        self.assertIsNone(cc._stars_from_valores(valores, "nao_confirmado"))
        self.assertIsNone(cc._stars_from_valores(valores, "digitei_errado"))


class StarsForAttributeTest(unittest.TestCase):
    """Usa a categoria `camera` real de config/categorias.yaml de proposito:
    e a mesma regua que o dashboard usa, entao o teste quebra se ela mudar
    sem querer."""

    def test_missing_value_is_unrated(self):
        self.assertIsNone(cc.stars_for_attribute("camera", "resolucao", None))
        self.assertIsNone(cc.stars_for_attribute("camera", "resolucao", ""))

    def test_field_without_rubric_is_unrated(self):
        # `conexao` e `armazenamento_tipo` nao tem regua de proposito: nao sao
        # tradeoff com direcao unica de melhor/pior.
        self.assertIsNone(cc.stars_for_attribute("camera", "conexao", "wifi"))
        self.assertIsNone(cc.stars_for_attribute("camera", "armazenamento_tipo", "sd"))

    def test_unknown_category_is_unrated(self):
        self.assertIsNone(cc.stars_for_attribute("categoria-que-nao-existe", "resolucao", 4))

    def test_tie_scenario_from_the_actual_request(self):
        # O pedido original: se dois candidatos tem o MESMO valor absoluto,
        # tem que empatar na mesma estrela - nunca "o melhor do grupo" ganha
        # mais so por estar sozinho no topo daquele grupo.
        tapo_c500 = cc.stars_for_attribute("camera", "resolucao", 2)
        tapo_tc40 = cc.stars_for_attribute("camera", "resolucao", 2)
        self.assertEqual(tapo_c500, tapo_tc40)
        self.assertEqual(tapo_c500, 3)  # 1080p/2MP e a faixa intermediaria, nao 5

        c320ws = cc.stars_for_attribute("camera", "resolucao", 4)
        c510w = cc.stars_for_attribute("camera", "resolucao", 3)
        self.assertEqual(c320ws, 4)
        self.assertEqual(c510w, 4)
        self.assertGreater(c320ws, tapo_c500, "2K tem que valer mais que 1080p, mesmo fora do topo do mercado")

    def test_real_camera_candidates_cross_checked_by_hand(self):
        casos = [
            ("resolucao", 2, 3),
            ("resolucao", 3, 4),
            ("resolucao", 4, 4),
            ("ip_rating", "IP67", 5),
            ("ip_rating", "IP66", 4),
            ("ip_rating", "IP65", 3),
            ("zoom_digital", 16, 5),
            ("zoom_digital", 12, 4),
            ("zoom_digital", 0, 1),
            ("angulo_visao", 98, 4),
            ("angulo_visao", 97, 4),
            # 73.5 graus cai na faixa 65-79 (2 estrelas), nao 80-94 (3): a
            # conferencia manual original errou essa conta, o teste pegou.
            ("angulo_visao", 73.5, 2),
            ("visao_noturna", "colorida_holofote", 5),
            ("visao_noturna", "colorida", 4),
            ("visao_noturna", "monocromatica", 3),
            ("deteccao_ia", "avancado", 5),
            ("deteccao_ia", "padrao", 4),
            ("deteccao_ia", "basico", 3),
            ("audio_bidirecional", "confirmado", 5),
        ]
        for campo, valor, esperado in casos:
            with self.subTest(campo=campo, valor=valor):
                self.assertEqual(cc.stars_for_attribute("camera", campo, valor), esperado)

    def test_audio_not_confirmed_has_no_star(self):
        self.assertIsNone(cc.stars_for_attribute("camera", "audio_bidirecional", "nao_confirmado"))


class StarsFromScoreTest(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(cc.stars_from_score(0.8), 5)
        self.assertEqual(cc.stars_from_score(0.79), 4)
        self.assertEqual(cc.stars_from_score(0.6), 4)
        self.assertEqual(cc.stars_from_score(0.59), 3)
        self.assertEqual(cc.stars_from_score(0.4), 3)
        self.assertEqual(cc.stars_from_score(0.39), 2)
        self.assertEqual(cc.stars_from_score(0.2), 2)
        self.assertEqual(cc.stars_from_score(0.19), 1)
        self.assertEqual(cc.stars_from_score(0.0), 1)

    def test_missing_score_is_unrated(self):
        self.assertIsNone(cc.stars_from_score(None))


class StarsGlyphsTest(unittest.TestCase):
    def test_renders_filled_and_empty_stars(self):
        self.assertEqual(cc.stars_glyphs(0), "☆☆☆☆☆")
        self.assertEqual(cc.stars_glyphs(3), "★★★☆☆")
        self.assertEqual(cc.stars_glyphs(5), "★★★★★")

    def test_none_is_empty_string_never_a_fabricated_star(self):
        self.assertEqual(cc.stars_glyphs(None), "")


if __name__ == "__main__":
    unittest.main()
