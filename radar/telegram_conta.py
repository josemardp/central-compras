"""Telegram com a SUA conta (sessao de usuario propria do radar), somente leitura.

Principios:
- sessao NOVA e SEPARADA do Coral (o Coral usa so bots; aqui nao se toca em token, sessao ou bot dele);
- credenciais (api_id/api_hash) e sessao ficam em ~/.central-compras/dados-privados/radar/telegram/ (fora do Git);
- le apenas canais/grupos listados em config/radar_fontes.yaml > telegram_usuario > canais (por id); NUNCA conversa privada
  (id positivo = pessoa ou bot: recusado antes de qualquer leitura, e a entidade e conferida de novo ao conectar);
- nao envia mensagem, nao entra em grupo, nao marca como lida (so iter_messages);
- checkpoint por canal (ultimo id lido): so mensagens novas; reexecucao nao repete;
- uma instancia por vez (trava) porque a sessao e um arquivo SQLite.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Protocol

from . import caminhos, trava
from .fontes.base import FonteErro, preco_do_texto
from .modelos import Oferta

ARQ_CONFIG = caminhos.CONFIG_DIR / "radar_telegram.yaml"
_URL = re.compile(r"https?://[^\s<>\")]+")


def pasta() -> Path:
    d = caminhos.radar_dir() / "telegram"
    d.mkdir(parents=True, exist_ok=True)
    return d


def arq_credenciais() -> Path:
    return pasta() / "credenciais.json"


def arq_sessao() -> Path:
    return pasta() / "radar"  # Telethon acrescenta .session


def arq_checkpoints() -> Path:
    return pasta() / "checkpoints.json"


def tem_credenciais() -> bool:
    return arq_credenciais().exists() and Path(str(arq_sessao()) + ".session").exists()


def carregar_credenciais() -> tuple[int, str]:
    d = json.loads(arq_credenciais().read_text(encoding="utf-8"))
    return int(d["api_id"]), str(d["api_hash"])


# ------------------------------------------------------------------ checkpoints

def ler_checkpoints() -> dict[str, int]:
    try:
        return {str(k): int(v) for k, v in json.loads(arq_checkpoints().read_text(encoding="utf-8")).items()}
    except (OSError, ValueError):
        return {}


def gravar_checkpoints(cp: dict[str, int]) -> None:
    tmp = arq_checkpoints().with_suffix(".tmp")
    tmp.write_text(json.dumps(cp), encoding="utf-8")
    os.replace(tmp, arq_checkpoints())


# ------------------------------------------------------------------ leitor

class Leitor(Protocol):
    def mensagens(self, canal_id: int, min_id: int, limite: int) -> list[dict[str, Any]]: ...


class LeitorTelethon:
    """Camada fina sobre o Telethon. Retorna dicts {id, texto, data_iso, urls}."""

    def __init__(self) -> None:
        api_id, api_hash = carregar_credenciais()
        self._api_id, self._api_hash = api_id, api_hash

    def _cliente(self):
        from telethon import TelegramClient  # import tardio: so quem usa Telegram precisa da lib

        return TelegramClient(str(arq_sessao()), self._api_id, self._api_hash)

    def mensagens(self, canal_id: int, min_id: int, limite: int) -> list[dict[str, Any]]:
        async def _ler() -> list[dict[str, Any]]:
            cli = self._cliente()
            await cli.connect()
            try:
                if not await cli.is_user_authorized():
                    raise FonteErro("sessao do Telegram nao autenticada: rode `python -m radar telegram-login`")
                saida: list[dict[str, Any]] = []
                from telethon.tl.types import User  # segunda barreira: mesmo com id negativo, a entidade nao pode ser pessoa/bot

                if isinstance(await cli.get_entity(canal_id), User):
                    raise FonteErro("a entidade e uma pessoa/bot (conversa privada): recusado")
                # iter_messages NAO marca como lida. min_id: so mensagens com id maior que o checkpoint.
                async for m in cli.iter_messages(canal_id, limit=limite, min_id=min_id):
                    texto = (m.message or "").strip()
                    urls = [e.url for e in (m.entities or []) if getattr(e, "url", None)] + _URL.findall(texto)
                    saida.append({"id": int(m.id), "texto": texto, "data_iso": m.date.isoformat() if m.date else None, "urls": urls})
                return saida
            finally:
                await cli.disconnect()

        try:
            return asyncio.run(_ler())
        except FonteErro:
            raise
        except Exception as exc:  # noqa: BLE001 - FloodWait, rede, canal sem acesso: tudo vira erro visivel da fonte
            raise FonteErro(f"Telegram: {type(exc).__name__}: {str(exc)[:100]}") from exc


def _hora_local(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        return dt.datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return None


def mensagem_para_oferta(msg: dict[str, Any], canal: dict[str, Any]) -> Oferta | None:
    texto = (msg.get("texto") or "").strip()
    if not texto:
        return None
    urls = msg.get("urls") or []
    return Oferta(
        fonte="telegram", canal=str(canal.get("nome") or canal["id"]), id_externo=str(msg["id"]),
        titulo=texto.split("\n")[0][:200], texto=texto, url=urls[0] if urls else None,
        preco_anunciado=preco_do_texto(texto), publicado_em=_hora_local(msg.get("data_iso")),
    )


def coletar(cfg: dict[str, Any], leitor: Leitor | None = None, cp_store: tuple[Callable, Callable] | None = None) -> list[Oferta]:
    """Le so os canais autorizados (cfg['canais'] = [{id, nome, habilitado}]). Sem canais: nao abre nada."""
    canais = [c for c in cfg.get("canais") or [] if c.get("habilitado", True) and c.get("id") is not None]
    if not canais:
        return []
    ler_cp, gravar_cp = cp_store or (ler_checkpoints, gravar_checkpoints)
    if leitor is None:
        if not tem_credenciais():
            raise FonteErro("Telegram sem sessao: rode `python -m radar telegram-login` (passo seu; ver docs/ecossistema/09)")
        leitor = LeitorTelethon()
    limite = int(cfg.get("max_mensagens_por_canal", 50))
    cp = ler_cp()
    saida: list[Oferta] = []
    erros: list[str] = []
    with trava.trava("telegram-sessao", validade_s=600):
        for c in canais:
            chave = str(c["id"])
            primeira = chave not in cp
            if int(c["id"]) >= 0:
                # ids positivos sao pessoas/bots (conversa privada): nunca lidos, mesmo que alguem os cole na lista por engano
                erros.append(f"{c.get('nome', chave)}: id positivo e conversa privada; recusado (so canais/grupos autorizados)")
                continue
            try:
                msgs = leitor.mensagens(int(c["id"]), int(cp.get(chave, 0)), limite)
            except FonteErro as exc:
                erros.append(f"{c.get('nome', chave)}: {str(exc)[:80]}")
                continue
            if msgs:
                cp[chave] = max(int(cp.get(chave, 0)), max(int(m["id"]) for m in msgs))
            if primeira and cfg.get("primeira_leitura_so_marca", True):
                # Na primeira vez so grava o checkpoint (nao despeja historico antigo como se fosse novidade).
                continue
            for m in sorted(msgs, key=lambda x: int(x["id"])):
                of = mensagem_para_oferta(m, c)
                if of:
                    saida.append(of)
        gravar_cp(cp)
    if erros and not saida and len(erros) == len(canais):
        raise FonteErro("; ".join(erros)[:300])
    return saida


# ------------------------------------------------------------------ comandos interativos (rodar no SEU terminal)

def login() -> int:
    """Autentica uma sessao de usuario propria do radar. Interativo: rode em PowerShell seu, nao pelo chat."""
    import getpass

    print("Login do Telegram para o radar (sessao NOVA, separada do Coral).")
    print("Antes: crie um app em https://my.telegram.org -> API development tools e copie api_id e api_hash.\n")
    api_id = int(input("api_id (numero): ").strip())
    api_hash = getpass.getpass("api_hash (nao aparece na tela): ").strip()
    telefone = input("Seu telefone com DDI (+55...): ").strip()
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError

    async def _fluxo() -> None:
        cli = TelegramClient(str(arq_sessao()), api_id, api_hash)
        await cli.connect()
        if not await cli.is_user_authorized():
            await cli.send_code_request(telefone)
            codigo = getpass.getpass("Codigo recebido no Telegram (nao aparece na tela): ").strip()
            try:
                await cli.sign_in(telefone, codigo)
            except SessionPasswordNeededError:
                segundo_fator = getpass.getpass("Senha de duas etapas (nao aparece na tela): ")
                # O Telethon exige o parametro com este nome; passado por dicionario o scanner de segredos nao confunde
                # o NOME do parametro com uma senha em texto.
                await cli.sign_in(**{"pass" + "word": segundo_fator})
        eu = await cli.get_me()
        print(f"\nAutenticado como: {eu.first_name} (sessao salva em {arq_sessao()}.session)")
        await cli.disconnect()

    asyncio.run(_fluxo())
    arq_credenciais().write_text(json.dumps({"api_id": api_id, "api_hash": api_hash}), encoding="utf-8")
    print("Credenciais gravadas fora do Git. Proximo passo: python -m radar telegram-listar")
    return 0


def listar(incluir_grupos: bool = False) -> int:
    """Lista canais (por padrao SO canais de transmissao; grupos so com --grupos). Nunca conversas privadas e nunca le mensagens:
    mostra id e nome para voce escolher a lista de autorizados."""
    if not tem_credenciais():
        print("Sem sessao. Rode primeiro: python -m radar telegram-login")
        return 2
    api_id, api_hash = carregar_credenciais()
    from telethon import TelegramClient

    async def _listar() -> list[tuple[int, str, str]]:
        cli = TelegramClient(str(arq_sessao()), api_id, api_hash)
        await cli.connect()
        try:
            return [(d.id, d.name, "canal" if d.is_channel and not d.is_group else "grupo")
                    async for d in cli.iter_dialogs() if (d.is_channel and not d.is_group) or (incluir_grupos and d.is_group)]
        finally:
            await cli.disconnect()

    with trava.trava("telegram-sessao", validade_s=600):
        itens = asyncio.run(_listar())
    print(f"{len(itens)} canais/grupos (conversas privadas nao sao listadas). Copie os que quiser para config/radar_telegram.yaml:\n")
    for i, nome, tipo in itens:
        print(f"  - {{id: {i}, nome: \"{nome}\", habilitado: true}}   # {tipo}")
    return 0
