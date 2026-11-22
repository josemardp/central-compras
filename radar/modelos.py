"""Tipos compartilhados entre as fontes, o motor de cupons, o ranking e os alertas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Oferta:
    """Uma publicacao de oferta/cupom vinda de uma fonte, ainda sem interpretacao.

    Tres horas DIFERENTES (nunca confundir):
      publicado_em      (published_at)   hora REAL da postagem, so quando a FONTE informa. None = desconhecida.
      primeira_vista_em (first_seen_at)  quando o RADAR viu o item pela 1a vez. Nao prova quando foi postado.
      coletado_em       (collected_at)   quando esta leitura foi feita (cada ciclo).
    Fonte sem hora confiavel (HardMOB) deixa `publicado_em` vazio: a oferta fica com `hora_incerta` e nunca e 'relampago'.
    """

    fonte: str
    id_externo: str
    titulo: str
    canal: str = ""
    url: str | None = None
    loja: str | None = None
    vendedor: str | None = None
    preco_anunciado: float | None = None
    frete: float | None = None
    texto: str = ""
    cupom_codigo: str | None = None
    publicado_em: str | None = None  # 'YYYY-MM-DD HH:MM' no fuso local; so se a fonte informa
    verificado_em: str | None = None  # a propria fonte diz que verificou o cupom/oferta nesse horario
    comentarios: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)
    primeira_vista_em: str | None = None
    coletado_em: str | None = None

    @property
    def hora_incerta(self) -> bool:
        """A fonte nao informou a hora da postagem (so existe a hora em que o radar viu)."""
        return self.publicado_em is None and self.primeira_vista_em is not None

    @property
    def texto_completo(self) -> str:
        return " \n".join(p for p in (self.titulo, self.texto, self.cupom_codigo or "") if p)
