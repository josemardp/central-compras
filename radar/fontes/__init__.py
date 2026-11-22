"""Registro das fontes. Cada modulo expoe `coletar(cfg) -> list[Oferta]` e levanta FonteErro em falha."""

from . import gatry, hardmob, meliuz, pelando, promobit, telegram_publico, telegram_usuario

FONTES = {
    "telegram_usuario": telegram_usuario.coletar,
    "promobit": promobit.coletar,
    "gatry": gatry.coletar,
    "pelando": pelando.coletar,
    "hardmob": hardmob.coletar,
    "meliuz": meliuz.coletar,
    "telegram_publico": telegram_publico.coletar,
}
