"""Lista de autorizacao de grupos de WhatsApp (trava de seguranca para um futuro leitor).

Nada aqui le o WhatsApp. Esta camada so responde "este grupo pode ser lido?". O leitor, quando existir, DEVE chamar
`exigir_autorizado(nome)` antes de abrir qualquer conversa.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from . import caminhos
from .catalogo import normalizar

ARQ = caminhos.CONFIG_DIR / "radar_whatsapp_grupos.yaml"


class GrupoNaoAutorizado(PermissionError):
    pass


def carregar(caminho: Path | None = None) -> dict[str, Any]:
    cfg = yaml.safe_load((caminho or ARQ).read_text(encoding="utf-8")) or {}
    cfg.setdefault("autorizados", [])
    cfg.setdefault("nunca", [])
    cfg.setdefault("max_grupos", 5)
    return cfg


def _parece_telefone(nome: str) -> bool:
    return len(re.sub(r"\D", "", nome)) >= 8 and not re.search(r"[a-z]{3,}", normalizar(nome))


def verificar(nome: str, cfg: dict[str, Any] | None = None) -> tuple[bool, str]:
    cfg = cfg if cfg is not None else carregar()
    n = normalizar(nome)
    if not n:
        return False, "nome vazio"
    if _parece_telefone(nome):
        return False, "nome parece numero de telefone (conversa privada)"
    for proibido in cfg.get("nunca", []):
        if normalizar(proibido) and normalizar(proibido) in n:
            return False, f"grupo bloqueado pela lista `nunca` ({proibido})"
    ativos = [g for g in cfg.get("autorizados", []) if g.get("habilitado", True)]
    if len(ativos) > int(cfg.get("max_grupos", 5)):
        return False, "lista de autorizados maior que max_grupos: revise a configuracao"
    if any(normalizar(g.get("nome", "")) == n for g in ativos):
        return True, "autorizado explicitamente"
    return False, "nao esta na lista de autorizados"


def exigir_autorizado(nome: str, cfg: dict[str, Any] | None = None) -> None:
    ok, motivo = verificar(nome, cfg)
    if not ok:
        raise GrupoNaoAutorizado(f"leitura de '{nome}' recusada: {motivo}")


def resumo(cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg if cfg is not None else carregar()
    ativos = [g["nome"] for g in cfg.get("autorizados", []) if g.get("habilitado", True)]
    if not ativos:
        return "Nenhum grupo de WhatsApp autorizado: o radar nao le nenhum grupo (so envia ao seu chat)."
    return f"{len(ativos)} grupo(s) autorizado(s): " + ", ".join(ativos)
