"""Testes unitarios das funcoes puras do rastreador do chuveiro (sem rede/Zap)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import rastrear_chuveiro_bf as rc


class RastrearChuveiroTest(unittest.TestCase):
    def test_parse_leroy_texto(self):
        texto = (
            "Chuveiro Eletrico Eletronico 220V 6800w Branco\n"
            "R$ 127,90\n"
            "R$ 136,06\n"
            "Receba em casa Frete R$ 24,90\n"
            "Mais opcoes a partir de R$ 128,90\n"
        )
        res = rc._parse_leroy_texto(texto)
        self.assertEqual(res["preco_avista"], 127.90)
        self.assertEqual(res["frete_valor"], 24.90)
        self.assertEqual(res["total"], 152.80)

    def test_parse_leroy_ignora_servico_de_instalacao(self):
        """Regressao de 20/11/2026: o menor valor da pagina (instalacao R$ 89,90) virava o preco do chuveiro."""
        texto = (
            "Chuveiro Eletrico Eletronico 220V 6800w Branco Quadrado Loren Shower Lorenzetti\n"
            "CÓD. 91697823\n"
            "Descrição\n"
            "R$ 127,90\nà vista\nR$ 136,06\na prazo\nem até 6x no cartão Celebre!\n"
            "Vendido e entregue por LEROY MERLIN\n"
            "Instalação por R$ 89,90 à vista ou parcelado, com 1 ano(s) de garantia. Saiba mais\n"
            "Calcule seu frete\n"
        )
        res = rc._parse_leroy_texto(texto)
        self.assertEqual(res["preco_avista"], 127.90)

    def test_parse_leroy_sem_rotulo_a_vista_ainda_ignora_instalacao(self):
        texto = "R$ 127,90\nR$ 136,06\nInstalação por R$ 60,65 à vista\n"
        self.assertEqual(rc._parse_leroy_texto(texto)["preco_avista"], 127.90)

    def test_carregar_cep_fallback_endereco(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            end_file = root / "endereco.md"
            cep_ficticio = "01001" + "-" + "000"
            end_file.write_text(f"# Endereco\n- CEP: {cep_ficticio}\n", encoding="utf-8")
            with (
                mock.patch.object(rc, "CONFIG_PATH", root / "inexistente1.json"),
                mock.patch.object(rc, "ARES_CONFIG_PATH", root / "inexistente2.json"),
                mock.patch.object(rc, "ENDERECO_PATH", end_file),
            ):
                self.assertEqual(rc.carregar_cep(), "01001000")

    def test_carregar_cep_prioriza_config_ares(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ares_cfg = root / "ares.json"
            cep_ficticio = "12345" + "-" + "678"
            ares_cfg.write_text(json.dumps({"cep_12k": cep_ficticio}), encoding="utf-8")
            with (
                mock.patch.object(rc, "CONFIG_PATH", root / "inexistente.json"),
                mock.patch.object(rc, "ARES_CONFIG_PATH", ares_cfg),
            ):
                self.assertEqual(rc.carregar_cep(), "12345678")

    def test_detectar_alteracoes_preco(self):
        ant = {
            "coletado_em": "2026-11-19 14:00",
            "modelos": {
                "loren_shower_6800_220v": {
                    "nome": "Lorenzetti Loren Shower Eletronico 6800W 220V",
                    "melhor_preco": 111.89,
                    "melhor_onde": "Amazon (Amazon.com.br, frete Gratis)",
                }
            },
        }
        atu = {
            "coletado_em": "2026-11-19 20:00",
            "modelos": {
                "loren_shower_6800_220v": {
                    "nome": "Lorenzetti Loren Shower Eletronico 6800W 220V",
                    "melhor_preco": 99.90,
                    "melhor_onde": "Amazon (Amazon.com.br, frete Gratis)",
                }
            },
        }
        self.assertEqual(rc.detectar_alteracoes(ant, ant), [])
        mudancas = rc.detectar_alteracoes(atu, ant)
        self.assertEqual(len(mudancas), 1)
        self.assertIn("BAIXOU", mudancas[0])
        self.assertIn("99,90", mudancas[0])

    def test_montar_mensagem_completa(self):
        snap = {
            "coletado_em": "2026-11-19 19:20",
            "modelos": {
                "loren_shower_6800_220v": {
                    "nome": "Lorenzetti Loren Shower Eletronico 6800W 220V",
                    "sku": "7510157",
                    "melhor_preco": 111.89,
                    "melhor_onde": "Amazon (Amazon.com.br, frete Gratis)",
                    "melhor_parcelamento": "R$ 128,90 em ate 4x de R$ 32,24 s/ juros",
                    "amazon": {"cupons": ["10OFFBF", "25PRIMEBF"]},
                    "leroy": {"preco_avista": 127.90, "total": None},
                    "zoom": {"menor_preco": 152.99, "loja": "Magazine Luiza"},
                    "promobit": [{"preco": 95.0, "href": "https://promobit.com.br/x"}],
                }
            },
        }
        msg = rc.montar_mensagem(snap, None, primeira_vez=True)
        self.assertIn("🚿 *RASTREIO CHUVEIRO", msg)
        self.assertIn("Lorenzetti Loren Shower Eletronico 6800W 220V", msg)
        self.assertIn("R$ 111,89", msg)
        self.assertIn("10OFFBF · 25PRIMEBF", msg)
        self.assertIn("Leroy Merlin: R$ 127,90 + frete", msg)
        self.assertIn("Zoom/Magazine Luiza: R$ 152,99", msg)
        self.assertIn("Alerta Promobit: *R$ 95,00*", msg)


if __name__ == "__main__":
    unittest.main()
