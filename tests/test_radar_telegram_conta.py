"""Telegram (conta do usuario): somente canais autorizados, checkpoint, sem despejo de historico, sem tocar no Coral."""

import os
import tempfile
import unittest
from unittest import mock

from radar import telegram_conta as tc
from radar.fontes.base import FonteErro


class LeitorFalso:
    def __init__(self, por_canal):
        self.por_canal, self.chamadas = por_canal, []

    def mensagens(self, canal_id, min_id, limite):
        self.chamadas.append((canal_id, min_id, limite))
        if isinstance(self.por_canal.get(canal_id), Exception):
            raise self.por_canal[canal_id]
        return [m for m in self.por_canal.get(canal_id, []) if m["id"] > min_id]


def msg(i, texto="Robô Dreame F10 por R$ 1.099,00 https://amzn.to/x"):
    return {"id": i, "texto": texto, "data_iso": "2026-11-21T13:00:00+00:00", "urls": ["https://amzn.to/x"]}


class ConversaPrivadaTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_id_positivo_e_conversa_privada_e_nunca_chega_ao_leitor(self):
        leitor = LeitorFalso({123456: [msg(1)], -100: [msg(1)]})
        cfg = {"canais": [{"id": 123456, "nome": "Pessoa"}, {"id": -100, "nome": "Canal"}], "primeira_leitura_so_marca": False}
        saida = tc.coletar(cfg, leitor)
        self.assertEqual([c[0] for c in leitor.chamadas], [-100])   # o id positivo nem foi consultado
        self.assertEqual(len(saida), 1)

    def test_lista_so_com_ids_positivos_vira_erro_visivel_e_nao_le_nada(self):
        leitor = LeitorFalso({999: [msg(1)]})
        with self.assertRaises(FonteErro) as e:
            tc.coletar({"canais": [{"id": 999, "nome": "Amigo"}]}, leitor)
        self.assertIn("conversa privada", str(e.exception))
        self.assertEqual(leitor.chamadas, [])

    def test_entidade_de_pessoa_e_recusada_mesmo_com_id_negativo(self):
        try:
            from telethon.tl.types import User
        except ImportError:
            self.skipTest("telethon nao instalado")

        class Cli:
            async def connect(self): pass
            async def disconnect(self): pass
            async def is_user_authorized(self): return True
            async def get_entity(self, i): return User(id=1)
            def iter_messages(self, *a, **k):
                raise AssertionError("nao pode ler mensagens de uma pessoa")

        with mock.patch.object(tc, "carregar_credenciais", return_value=(1, "x")):
            leitor = tc.LeitorTelethon()
        with mock.patch.object(tc.LeitorTelethon, "_cliente", return_value=Cli()):
            with self.assertRaises(FonteErro) as e:
                leitor.mensagens(-100, 0, 10)
        self.assertIn("recusado", str(e.exception))


class SomenteLeituraTest(unittest.TestCase):
    """O radar so le canais da lista: nunca entra em grupo, envia, apaga, encaminha, marca como lida ou toca no Coral."""

    ARQUIVOS = ("telegram_conta.py", "fontes/telegram_usuario.py", "fontes/telegram_publico.py")

    def fontes(self):
        from pathlib import Path
        raiz = Path(tc.__file__).parent
        return {a: (raiz / a).read_text(encoding="utf-8") for a in self.ARQUIVOS}

    def test_nenhuma_chamada_que_escreve_ou_entra_em_algum_lugar(self):
        proibidos = ("JoinChannel", "join_chat", "ImportChatInvite", "send_message", "send_file", "send_read_acknowledge", "delete_messages",
                     "forward_messages", "edit_message", "LeaveChannel", "iter_participants", "get_participants", "client.start(", "cli.start(", "PrivacyRequest")
        for nome, src in self.fontes().items():
            for p in proibidos:
                self.assertNotIn(p, src, f"{nome}: {p}")

    def test_a_unica_chamada_que_envia_algo_e_o_codigo_de_login_para_o_proprio_celular(self):
        src = self.fontes()["telegram_conta.py"]
        self.assertEqual(src.count("send_code_request"), 1)
        self.assertIn("def login()", src)

    def test_sessao_e_credenciais_ficam_so_na_pasta_do_radar_e_nao_tocam_no_coral(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": tmp}):
            base = Path(tmp).resolve()
            for arq in (tc.arq_sessao(), tc.arq_credenciais(), tc.arq_checkpoints()):
                self.assertTrue(Path(str(arq)).resolve().is_relative_to(base / "radar" / "telegram"), arq)
        for nome, src in self.fontes().items():
            codigo = "\n".join(l for l in src.splitlines() if not l.strip().startswith(("#", '"""', "-", "sessao NOVA")))
            self.assertNotIn("projetos/coral", codigo.lower().replace("\\", "/"), nome)
            self.assertNotIn("/coral/", codigo.lower().replace("\\", "/"), nome)

    def test_comandos_de_login_e_listagem_existem_e_a_listagem_nao_le_mensagens(self):
        import inspect
        self.assertTrue(callable(tc.login) and callable(tc.listar))
        src = inspect.getsource(tc.listar)
        self.assertNotIn("iter_messages", src)
        self.assertNotIn("get_messages", src)
        self.assertIn("incluir_grupos", src)


class TelegramContaTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        p = mock.patch.dict(os.environ, {"CENTRAL_COMPRAS_DADOS_PRIVADOS": self._tmp.name})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)
        self.cfg = {"canais": [{"id": -100, "nome": "Ofertas A"}], "primeira_leitura_so_marca": True}

    def test_sem_canais_autorizados_nao_abre_nada_nem_exige_login(self):
        self.assertEqual(tc.coletar({"canais": []}), [])
        self.assertEqual(tc.coletar({}), [])
        self.assertEqual(tc.coletar({"canais": [{"id": -1, "habilitado": False}]}), [])

    def test_com_canal_mas_sem_sessao_e_erro_explicito_com_o_procedimento(self):
        with self.assertRaises(FonteErro) as cm:
            tc.coletar(self.cfg)
        self.assertIn("telegram-login", str(cm.exception))

    def test_primeira_leitura_so_marca_checkpoint_e_nao_despeja_historico(self):
        leitor = LeitorFalso({-100: [msg(1), msg(2), msg(3)]})
        self.assertEqual(tc.coletar(self.cfg, leitor), [])
        self.assertEqual(tc.ler_checkpoints(), {"-100": 3})

    def test_depois_so_mensagens_novas_em_ordem_e_sem_repetir(self):
        leitor = LeitorFalso({-100: [msg(1), msg(2)]})
        tc.coletar(self.cfg, leitor)
        leitor.por_canal[-100] += [msg(3, "Cupom CASATECH10 10% no K800"), msg(4)]
        novas = tc.coletar(self.cfg, leitor)
        self.assertEqual([o.id_externo for o in novas], ["3", "4"])
        self.assertEqual(novas[0].canal, "Ofertas A")
        self.assertEqual(leitor.chamadas[-1], (-100, 2, 50))  # pediu so id > checkpoint
        self.assertEqual(tc.coletar(self.cfg, leitor), [])  # nada novo: nao repete
        self.assertEqual(tc.ler_checkpoints(), {"-100": 4})

    def test_so_le_os_canais_listados_e_um_canal_com_erro_nao_derruba_o_outro(self):
        cfg = {"canais": [{"id": -100, "nome": "A"}, {"id": -200, "nome": "B"}], "primeira_leitura_so_marca": False}
        leitor = LeitorFalso({-100: FonteErro("Telegram: ChannelPrivateError"), -200: [msg(7)], -999: [msg(1)]})
        r = tc.coletar(cfg, leitor)
        self.assertEqual([(o.canal, o.id_externo) for o in r], [("B", "7")])
        self.assertEqual({c[0] for c in leitor.chamadas}, {-100, -200})  # -999 (nao autorizado) nunca consultado

    def test_todos_os_canais_com_erro_vira_falha_da_fonte(self):
        with self.assertRaises(FonteErro):
            tc.coletar(self.cfg | {"primeira_leitura_so_marca": False}, LeitorFalso({-100: FonteErro("x")}))

    def test_mensagem_vira_oferta_com_preco_url_e_hora(self):
        o = tc.mensagem_para_oferta(msg(9), {"id": -100, "nome": "Ofertas A"})
        self.assertEqual((o.preco_anunciado, o.url, o.fonte), (1099.0, "https://amzn.to/x", "telegram"))
        self.assertTrue(o.publicado_em.startswith("2026-11-21"))
        self.assertIsNone(tc.mensagem_para_oferta({"id": 1, "texto": "  "}, {"id": 1}))

    def test_sessao_e_credenciais_ficam_fora_do_repositorio(self):
        self.assertTrue(str(tc.pasta()).startswith(self._tmp.name))
        self.assertNotIn(str(tc.caminhos.RAIZ), str(tc.arq_sessao()))

    def test_api_do_telethon_usada_existe_na_versao_instalada(self):
        try:
            from telethon import TelegramClient
        except ImportError:
            self.skipTest("telethon nao instalado neste Python")
        for nome in ("iter_messages", "iter_dialogs", "connect", "is_user_authorized", "send_code_request", "sign_in", "get_me"):
            self.assertTrue(hasattr(TelegramClient, nome), nome)

    def test_a_camada_telethon_nunca_envia_nem_marca_como_lida(self):
        import inspect

        fonte = inspect.getsource(tc)
        for proibido in ("send_message", "send_read_acknowledge", "join_channel", "JoinChannel", "delete_messages", "forward_messages"):
            self.assertNotIn(proibido, fonte, proibido)


if __name__ == "__main__":
    unittest.main()
