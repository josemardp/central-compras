#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import os
import re
import sys
import textwrap
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
PROJETOS = ROOT / "projetos"
PRODUTOS = ROOT / "produtos"
TEMPLATES = ROOT / "templates"
BASE = ROOT / "base-conhecimento"
VEREDITOS = ROOT / "vereditos"
DASHBOARD = ROOT / "dashboard"

COTACOES_HEADER = [
    "data_coleta",
    "produto_id",
    "loja",
    "vendedor",
    "vendedor_tipo",
    "anuncio_id",
    "variacao",
    "preco",
    "preco_promocional",
    "frete_valor",
    "frete_prazo_dias",
    "custo_extra",
    "custo_total",
    "custo_operacional_mensal",
    "tco_meses",
    "valor_revenda_estimado",
    "tco_total",
    "nota",
    "n_avaliacoes",
    "nota_ajustada",
    "garantia_meses",
    "garantia_tipo",
    "link",
    "flag_suspeita",
    "fonte",
    "score",
]

QUOTE_REQUIRED_FIELDS = [
    "data_coleta",
    "produto_id",
    "loja",
    "vendedor_tipo",
    "custo_total",
    "nota",
    "n_avaliacoes",
    "garantia_tipo",
    "fonte",
]

MANUAL_REQUIRED_FIELDS = [
    "vendedor",
    "garantia_meses",
    "link",
]


def today() -> str:
    return dt.date.today().isoformat()


def now_iso() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "item"


def read_yaml(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    return default if loaded is None else loaded


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    separator = "" if not existing or existing.endswith("\n") else "\n"
    path.write_text(existing + separator + text, encoding="utf-8", newline="\n")


def render_template(name: str, **values: Any) -> str:
    path = TEMPLATES / name
    text = path.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


def parse_scalar(value: str) -> Any:
    lowered = value.strip().lower()
    if lowered in {"true", "sim", "yes"}:
        return True
    if lowered in {"false", "nao", "não", "no"}:
        return False
    if lowered in {"null", "none", ""}:
        return None
    try:
        if "." in value.replace(",", "."):
            return float(value.replace(",", "."))
        return int(value)
    except ValueError:
        return value


def parse_pairs(pairs: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"Use chave=valor, recebido: {pair}")
        key, value = pair.split("=", 1)
        result[key.strip()] = parse_scalar(value.strip())
    return result


def load_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = yaml.safe_load(parts[1]) or {}
    return meta, parts[2].lstrip()


def save_frontmatter(path: Path, meta: dict[str, Any], body: str) -> None:
    frontmatter = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    path.write_text(f"---\n{frontmatter}\n---\n\n{body.lstrip()}", encoding="utf-8", newline="\n")


def project_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / value
    if not path.exists():
        candidates = sorted(PROJETOS.glob(f"*{value}*"))
        if len(candidates) == 1:
            return candidates[0]
    if not path.exists() or not path.is_dir():
        raise SystemExit(f"Projeto nao encontrado: {value}")
    return path


def set_project_state(project: Path, estado: str) -> None:
    briefing = project / "briefing.md"
    if not briefing.exists():
        return
    meta, body = load_frontmatter(briefing)
    meta["estado"] = estado
    save_frontmatter(briefing, meta, body)


def quote_float(value: Any, default: float = 0.0) -> float:
    if value in {None, ""}:
        return default
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return default


def quote_int(value: Any, default: int = 0) -> int:
    if value in {None, ""}:
        return default
    try:
        return int(float(str(value).replace(",", ".")))
    except ValueError:
        return default


def adjusted_rating(nota: float, n: int) -> float:
    prefs = read_yaml(CONFIG / "preferencias.yaml", {})
    cfg = prefs.get("nota_bayesiana", {})
    media = quote_float(cfg.get("media_categoria_padrao"), 4.3)
    anchor = quote_float(cfg.get("peso_ancora"), 50)
    if n < 0:
        n = 0
    return round(((n * nota) + (anchor * media)) / (n + anchor), 3) if (n + anchor) else round(nota, 3)


def category_tco_months(categoria: str | None) -> int:
    if not categoria:
        return 0
    category = category_definition(categoria)
    return quote_int(category.get("tco_meses"))


def quote_tco_total(
    custo_total: float,
    custo_operacional_mensal: float = 0.0,
    tco_meses: int = 0,
    valor_revenda_estimado: float = 0.0,
) -> float:
    if not tco_meses:
        return round(custo_total, 2)
    return round(custo_total + (custo_operacional_mensal * tco_meses) - valor_revenda_estimado, 2)


def ensure_structure(_: argparse.Namespace) -> None:
    for path in [
        CONFIG,
        PROJETOS,
        PRODUTOS,
        TEMPLATES,
        BASE / "lojas",
        BASE / "marcas",
        VEREDITOS,
        ROOT / "scripts",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    print("Estrutura conferida.")


def new_project(args: argparse.Namespace) -> None:
    ensure_structure(args)
    year = dt.date.today().year
    projeto_id = f"{year}-{slugify(args.nome)}"
    path = PROJETOS / projeto_id
    if path.exists() and not args.force:
        raise SystemExit(f"Projeto ja existe: {path}")
    path.mkdir(parents=True, exist_ok=True)

    necessidade = args.necessidade or args.nome
    briefing = render_template(
        "briefing.md",
        projeto_id=projeto_id,
        categoria=args.categoria,
        valor_estimado=args.valor_estimado,
        preco_teto=args.preco_teto if args.preco_teto is not None else "null",
        data=today(),
        necessidade=necessidade,
    )
    (path / "briefing.md").write_text(briefing, encoding="utf-8", newline="\n")
    (path / "processo.md").write_text(render_template("processo.md", data=today()), encoding="utf-8", newline="\n")
    (path / "01-definir-modelo.md").write_text(
        render_template("01-definir-modelo.md", necessidade=necessidade),
        encoding="utf-8",
        newline="\n",
    )
    (path / "ranking.md").write_text("# Ranking\n\nAinda nao gerado.\n", encoding="utf-8", newline="\n")
    (path / "decisao.md").write_text(render_template("decisao.md"), encoding="utf-8", newline="\n")
    with (path / "cotacoes.csv").open("w", encoding="utf-8", newline="") as f:
        csv.DictWriter(f, fieldnames=COTACOES_HEADER).writeheader()
    set_process_state(path, estado="pesquisando", proxima_acao="definir modelo/requisitos com ajuda da IA")
    print(path.relative_to(ROOT))


def product_dir(categoria: str, produto_id: str) -> Path:
    return PRODUTOS / slugify(categoria) / produto_id


def new_product(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    meta, _ = load_frontmatter(project / "briefing.md")
    categoria = args.categoria or meta.get("categoria") or "generico"
    produto_id = args.produto_id or slugify(args.nome)
    path = product_dir(categoria, produto_id)
    if path.exists() and not args.force:
        raise SystemExit(f"Produto ja existe: {path}")
    path.mkdir(parents=True, exist_ok=True)

    data = {
        "id": produto_id,
        "categoria": categoria,
        "nome": args.nome,
        "marca": args.marca,
        "estado": "pesquisando",
        "projeto": project.name,
        "preco_alvo": args.preco_alvo,
        "preco_teto": args.preco_teto if args.preco_teto is not None else meta.get("preco_teto"),
        "atributos": parse_pairs(args.atributo or []),
        "requisitos_atendidos": parse_pairs(args.requisito or []),
        "descartado_porque": None,
    }
    write_yaml(path / "produto.yaml", data)
    (path / "pesquisa.md").write_text(render_template("pesquisa.md"), encoding="utf-8", newline="\n")
    append_timeline(project, "produto", f"Candidato registrado: {args.nome}", f"id={produto_id}")
    mark_steps(project, [3])
    print(path.relative_to(ROOT))


def read_quotes(project: Path) -> list[dict[str, str]]:
    path = project / "cotacoes.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_quotes(project: Path, rows: list[dict[str, Any]]) -> None:
    with (project / "cotacoes.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COTACOES_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in COTACOES_HEADER})


def find_product_path(produto_id: str) -> Path | None:
    matches = list(PRODUTOS.glob(f"*/{produto_id}/produto.yaml"))
    return matches[0] if matches else None


def set_process_state(project: Path, *, estado: str | None = None, proxima_acao: str | None = None, decisao_aberta: str | None = None) -> None:
    path = project / "processo.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    replacements = {
        "Estado": estado,
        "Proxima acao": proxima_acao,
        "Decisao aberta": decisao_aberta,
    }
    for label, value in replacements.items():
        if value is None:
            continue
        pattern = rf"(?m)^- {re.escape(label)}:.*$"
        replacement = f"- {label}: {value}"
        if re.search(pattern, text):
            text = re.sub(pattern, replacement, text)
        else:
            text = text.replace("## Estado atual\n", f"## Estado atual\n\n{replacement}\n", 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def mark_steps(project: Path, steps: list[int]) -> None:
    path = project / "processo.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    for step in steps:
        text = re.sub(rf"(?m)^- \[ \] {step}\.", f"- [x] {step}.", text)
    path.write_text(text, encoding="utf-8", newline="\n")


def add_quote(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    briefing, _ = load_frontmatter(project / "briefing.md")
    product = find_product(args.produto_id) or {}
    categoria = product.get("categoria") or briefing.get("categoria")
    rows = read_quotes(project)
    preco = quote_float(args.preco)
    promocional = quote_float(args.preco_promocional, 0)
    preco_efetivo = promocional or preco
    total = args.custo_total
    if total is None:
        total = preco_efetivo + quote_float(args.frete) + quote_float(args.custo_extra)
    tco_meses = args.tco_meses if args.tco_meses is not None else category_tco_months(categoria)
    tco_total = quote_tco_total(
        float(total),
        quote_float(args.custo_operacional_mensal),
        quote_int(tco_meses),
        quote_float(args.valor_revenda_estimado),
    )
    nota = quote_float(args.nota)
    avaliacoes = quote_int(args.avaliacoes)
    row = {
        "data_coleta": args.data or now_iso(),
        "produto_id": args.produto_id,
        "loja": args.loja,
        "vendedor": args.vendedor,
        "vendedor_tipo": args.vendedor_tipo,
        "anuncio_id": args.anuncio_id or "",
        "variacao": args.variacao or "",
        "preco": preco,
        "preco_promocional": promocional or "",
        "frete_valor": quote_float(args.frete),
        "frete_prazo_dias": args.frete_prazo_dias if args.frete_prazo_dias is not None else "",
        "custo_extra": quote_float(args.custo_extra),
        "custo_total": round(float(total), 2),
        "custo_operacional_mensal": quote_float(args.custo_operacional_mensal),
        "tco_meses": tco_meses or "",
        "valor_revenda_estimado": quote_float(args.valor_revenda_estimado),
        "tco_total": tco_total,
        "nota": nota,
        "n_avaliacoes": avaliacoes,
        "nota_ajustada": adjusted_rating(nota, avaliacoes) if nota else "",
        "garantia_meses": args.garantia_meses if args.garantia_meses is not None else "",
        "garantia_tipo": args.garantia_tipo,
        "link": args.link or "",
        "flag_suspeita": args.flag_suspeita or "",
        "fonte": args.fonte,
        "score": "",
    }
    rows.append(row)
    write_quotes(project, rows)
    append_timeline(
        project,
        "cotacao",
        f"Cotacao registrada para {args.produto_id}",
        f"{args.loja} / fonte={args.fonte} / custo_total={row['custo_total']}",
    )
    mark_steps(project, [4])
    if args.fonte == "manual":
        mark_steps(project, [7])
        set_process_state(project, proxima_acao="gerar ranking e comparar finalistas com cotacao manual")
    print(f"Cotacao adicionada: {args.produto_id} - R$ {row['custo_total']}")


def append_timeline(project: Path, etapa: str, decisao: str, porque: str) -> None:
    path = project / "processo.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    line = f"| {today()} | {etapa} | {decisao} | {porque} |\n"
    lines = text.splitlines(keepends=True)
    insert_at = None
    for index, existing in enumerate(lines):
        if existing.strip() == "|---|---|---|---|":
            insert_at = index + 1
    if insert_at is None:
        lines.append("\n## Linha do tempo decisoria\n\n")
        lines.append("| Data | Etapa | Decisao | Por que |\n")
        lines.append("|---|---|---|---|\n")
        insert_at = len(lines)
    lines.insert(insert_at, line)
    text = "".join(lines)
    path.write_text(text, encoding="utf-8", newline="\n")


def find_product(produto_id: str) -> dict[str, Any] | None:
    path = find_product_path(produto_id)
    if not path:
        return None
    return read_yaml(path, {})


def latest_quotes(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("produto_id", ""), []).append(row)
    latest: dict[str, dict[str, str]] = {}
    for produto_id, values in grouped.items():
        manual = [row for row in values if row.get("fonte") == "manual"]
        pool = manual or values
        latest[produto_id] = sorted(pool, key=lambda r: r.get("data_coleta", ""))[-1]
    return latest


def latest_quote_for_product(rows: list[dict[str, str]], produto_id: str, fonte: str | None = None) -> dict[str, str] | None:
    matches = [row for row in rows if row.get("produto_id") == produto_id]
    if fonte:
        matches = [row for row in matches if row.get("fonte") == fonte]
    if not matches:
        return None
    return sorted(matches, key=lambda r: r.get("data_coleta", ""))[-1]


def category_definition(categoria: str) -> dict[str, Any]:
    categories = read_yaml(CONFIG / "categorias.yaml", {})
    return categories.get(categoria) or categories.get("generico") or {}


def product_required_attrs(product: dict[str, Any], briefing: dict[str, Any]) -> list[str]:
    categoria = product.get("categoria") or briefing.get("categoria") or "generico"
    category = category_definition(categoria)
    required = category.get("atributos_obrigatorios") or []
    attrs = product.get("atributos") or {}
    return [field for field in required if attrs.get(field) in {None, ""}]


def quote_missing_fields(row: dict[str, str]) -> list[str]:
    missing = [field for field in QUOTE_REQUIRED_FIELDS if row.get(field) in {None, ""}]
    if row.get("fonte") == "manual":
        missing.extend(field for field in MANUAL_REQUIRED_FIELDS if row.get(field) in {None, ""})
    return missing


def manipulation_alerts(rows: list[dict[str, str]], row: dict[str, str]) -> list[str]:
    alerts: list[str] = []
    explicit = row.get("flag_suspeita")
    if explicit:
        alerts.append(explicit)

    nota = quote_float(row.get("nota"))
    avaliacoes = quote_int(row.get("n_avaliacoes"))
    if nota >= 4.9 and 0 < avaliacoes < 150:
        alerts.append("AVAL_SUSPEITA")

    preco = quote_float(row.get("preco"))
    promocional = quote_float(row.get("preco_promocional"))
    if preco and promocional and promocional < preco * 0.60:
        previous_prices = [
            quote_float(other.get("preco"))
            for other in rows
            if other is not row and other.get("produto_id") == row.get("produto_id") and quote_float(other.get("preco"))
        ]
        if not previous_prices or min(previous_prices) > preco * 0.90:
            alerts.append("ANCORA")

    anuncio_id = row.get("anuncio_id")
    if anuncio_id:
        product_ids = {other.get("produto_id") for other in rows if other.get("anuncio_id") == anuncio_id and other.get("produto_id")}
        if len(product_ids) > 1:
            alerts.append("RECICLADO")

    return sorted(set(alerts))


def validation_report(project: Path) -> tuple[list[str], list[str]]:
    briefing, _ = load_frontmatter(project / "briefing.md")
    categoria_projeto = briefing.get("categoria") or "generico"
    tco_required = bool(category_tco_months(categoria_projeto) or quote_float(briefing.get("valor_estimado")) > 20000)
    rows = read_quotes(project)
    latest = latest_quotes(rows)
    errors: list[str] = []
    warnings: list[str] = []

    if not rows:
        warnings.append("Projeto ainda nao tem cotacoes.")

    for produto_id in sorted(latest):
        product = find_product(produto_id)
        if not product:
            errors.append(f"Produto citado em cotacao nao existe em `produtos/`: {produto_id}")
            continue
        missing_attrs = product_required_attrs(product, briefing)
        if missing_attrs:
            warnings.append(f"{produto_id}: atributos obrigatorios ausentes: {', '.join(missing_attrs)}")
        if product.get("estado") == "descartado" and not product.get("descartado_porque"):
            errors.append(f"{produto_id}: produto descartado sem motivo.")

    for index, row in enumerate(rows, 2):
        missing = quote_missing_fields(row)
        if missing:
            errors.append(f"cotacoes.csv linha {index}: campos obrigatorios ausentes: {', '.join(missing)}")
        if tco_required:
            tco_missing = [
                field
                for field in ["custo_operacional_mensal", "tco_meses", "valor_revenda_estimado", "tco_total"]
                if row.get(field) in {None, ""}
            ]
            if tco_missing:
                warnings.append(f"cotacoes.csv linha {index} ({row.get('produto_id')}): TCO incompleto: {', '.join(tco_missing)}")
        alerts = manipulation_alerts(rows, row)
        if alerts:
            warnings.append(f"cotacoes.csv linha {index} ({row.get('produto_id')}): alertas {', '.join(alerts)}")

    manual_ids = {row.get("produto_id") for row in rows if row.get("fonte") == "manual"}
    if latest and not manual_ids:
        warnings.append("Nenhum produto tem cotacao manual; decisao final ainda nao deve ser fechada.")

    return errors, warnings


@dataclass
class Ranked:
    produto_id: str
    quote: dict[str, str]
    product: dict[str, Any]
    axes: dict[str, float]
    score: float
    eliminations: list[str]
    alerts: list[str]


def normalize(values: list[float], current: float, invert: bool = False) -> float:
    if not values:
        return 0.0
    lo, hi = min(values), max(values)
    if hi == lo:
        return 1.0
    else:
        score = (current - lo) / (hi - lo)
    if invert:
        score = 1.0 - score
    return round(max(0.0, min(1.0, score)), 3)


def risk_score(row: dict[str, str], alerts: list[str] | None = None) -> float:
    vendedor = (row.get("vendedor_tipo") or "").lower()
    garantia = (row.get("garantia_tipo") or "").lower()
    vendedor_score = {"oficial": 1.0, "fisica": 0.85, "terceiro": 0.65}.get(vendedor, 0.55)
    garantia_score = {"nacional": 1.0, "importada": 0.70, "vendedor": 0.55, "nenhuma": 0.10}.get(garantia, 0.45)
    meses = min(quote_float(row.get("garantia_meses")), 36) / 36
    score = (vendedor_score * 0.35) + (garantia_score * 0.40) + (meses * 0.25)
    alert_count = len(set(alerts or ([] if not row.get("flag_suspeita") else [row.get("flag_suspeita")])))
    score -= min(0.35, alert_count * 0.15)
    return round(max(0.0, min(1.0, score)), 3)


def adherence_score(product: dict[str, Any]) -> float:
    reqs = product.get("requisitos_atendidos") or {}
    if not reqs:
        return 0.5
    total = 0.0
    possible = 0.0
    for value in reqs.values():
        possible += 1
        if value is True:
            total += 1
        elif str(value).lower() in {"parcial", "partial"}:
            total += 0.5
    return round(total / possible, 3) if possible else 0.5


def gate_eliminations(row: dict[str, str], product: dict[str, Any], briefing: dict[str, Any]) -> list[str]:
    categories = read_yaml(CONFIG / "categorias.yaml", {})
    prefs = read_yaml(CONFIG / "preferencias.yaml", {})
    categoria = product.get("categoria") or briefing.get("categoria") or "generico"
    gate = (categories.get(categoria) or categories.get("generico") or {}).get("gate", {})
    eliminations: list[str] = []

    if product.get("estado") == "descartado":
        motivo = product.get("descartado_porque") or "motivo nao registrado"
        eliminations.append(f"produto descartado ({motivo})")

    preco_teto = briefing.get("preco_teto")
    if preco_teto not in {None, "null", ""} and quote_float(row.get("custo_total")) > quote_float(preco_teto):
        eliminations.append(f"custo_total acima do preco_teto ({row.get('custo_total')} > {preco_teto})")

    nota_minima = gate.get("nota_minima_ajustada")
    if nota_minima is not None and quote_float(row.get("nota_ajustada")) < quote_float(nota_minima):
        eliminations.append(f"nota_ajustada abaixo do gate ({row.get('nota_ajustada')} < {nota_minima})")

    minimo_avaliacoes = gate.get("minimo_avaliacoes")
    if minimo_avaliacoes is not None and quote_int(row.get("n_avaliacoes")) < quote_int(minimo_avaliacoes):
        eliminations.append(f"avaliacoes insuficientes ({row.get('n_avaliacoes')} < {minimo_avaliacoes})")

    garantia_minima = gate.get("garantia_minima_meses")
    if garantia_minima is not None and quote_int(row.get("garantia_meses")) < quote_int(garantia_minima):
        eliminations.append(f"garantia abaixo do minimo ({row.get('garantia_meses')} < {garantia_minima})")

    garantia_aceita = gate.get("garantia_tipo_aceita") or []
    if garantia_aceita and row.get("garantia_tipo") not in garantia_aceita:
        eliminations.append(f"garantia_tipo nao aceito ({row.get('garantia_tipo')})")

    if gate.get("exige_vendedor_oficial") and row.get("vendedor_tipo") != "oficial":
        eliminations.append("categoria exige vendedor oficial")

    marca = product.get("marca")
    if marca and marca in (prefs.get("marcas_vetadas") or []):
        eliminations.append(f"marca vetada ({marca})")

    for key, value in (product.get("requisitos_atendidos") or {}).items():
        if value is False:
            eliminations.append(f"requisito obrigatorio nao atendido: {key}")

    return eliminations


def compute_ranking(project: Path) -> tuple[list[Ranked], list[Ranked]]:
    briefing, _ = load_frontmatter(project / "briefing.md")
    rows = read_quotes(project)
    latest = latest_quotes(rows)
    prefs = read_yaml(CONFIG / "preferencias.yaml", {})
    weights = prefs.get("score", {})
    categoria = briefing.get("categoria") or "generico"
    use_tco = bool(category_tco_months(categoria) or quote_float(briefing.get("valor_estimado")) > 20000)

    pre_candidates: list[tuple[str, dict[str, str], dict[str, Any], list[str], list[str]]] = []
    for produto_id, row in latest.items():
        product = find_product(produto_id) or {"id": produto_id, "categoria": briefing.get("categoria"), "marca": ""}
        eliminations = gate_eliminations(row, product, briefing)
        alerts = manipulation_alerts(rows, row)
        pre_candidates.append((produto_id, row, product, eliminations, alerts))

    scoring_pool = [item for item in pre_candidates if not item[3]] or pre_candidates
    value_field = "tco_total" if use_tco else "custo_total"
    costs = [quote_float(row.get(value_field) or row.get("custo_total")) for _, row, _, _, _ in scoring_pool]
    ratings = [quote_float(row.get("nota_ajustada")) for _, row, _, _, _ in scoring_pool]
    days = [
        quote_float(row.get("frete_prazo_dias"), 99)
        for _, row, _, _, _ in scoring_pool
        if row.get("frete_prazo_dias") not in {"", None}
    ]

    candidates: list[Ranked] = []
    for produto_id, row, product, eliminations, alerts in pre_candidates:
        axes = {
            "qualidade": normalize(ratings, quote_float(row.get("nota_ajustada"))),
            "valor": normalize(costs, quote_float(row.get(value_field) or row.get("custo_total")), invert=True),
            "risco": risk_score(row, alerts),
            "aderencia": adherence_score(product),
            "conveniencia": normalize(days, quote_float(row.get("frete_prazo_dias"), 99), invert=True) if days else 0.5,
        }
        score = sum(axes[key] * quote_float(weights.get(key), 0) for key in axes) * 100
        if eliminations:
            score = 0
        candidates.append(Ranked(produto_id, row, product, axes, round(score, 1), eliminations, alerts))

    elegiveis = sorted([c for c in candidates if not c.eliminations], key=lambda c: c.score, reverse=True)
    cortados = sorted([c for c in candidates if c.eliminations], key=lambda c: c.produto_id)
    return elegiveis, cortados


def write_ranking_csv(project: Path, elegiveis: list[Ranked], cortados: list[Ranked]) -> None:
    fields = [
        "produto_id",
        "nome",
        "score",
        "qualidade",
        "valor",
        "risco",
        "aderencia",
        "conveniencia",
        "status",
        "motivos",
        "alertas",
        "fonte",
        "custo_total",
        "custo_operacional_mensal",
        "tco_meses",
        "valor_revenda_estimado",
        "tco_total",
    ]
    with (project / "ranking.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in [*elegiveis, *cortados]:
            writer.writerow(
                {
                    "produto_id": item.produto_id,
                    "nome": item.product.get("nome") or item.produto_id,
                    "score": item.score,
                    "qualidade": item.axes.get("qualidade"),
                    "valor": item.axes.get("valor"),
                    "risco": item.axes.get("risco"),
                    "aderencia": item.axes.get("aderencia"),
                    "conveniencia": item.axes.get("conveniencia"),
                    "status": "cortado" if item.eliminations else "elegivel",
                    "motivos": "; ".join(item.eliminations),
                    "alertas": "; ".join(item.alerts),
                    "fonte": item.quote.get("fonte"),
                    "custo_total": item.quote.get("custo_total"),
                    "custo_operacional_mensal": item.quote.get("custo_operacional_mensal"),
                    "tco_meses": item.quote.get("tco_meses"),
                    "valor_revenda_estimado": item.quote.get("valor_revenda_estimado"),
                    "tco_total": item.quote.get("tco_total"),
                }
            )


def build_ranking(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    rows = read_quotes(project)
    elegiveis, cortados = compute_ranking(project)

    lines = ["# Ranking", "", f"Gerado em {now_iso()}.", ""]
    if not rows:
        lines.append("Ainda nao ha cotacoes.")
    else:
        lines.extend(["## Elegiveis", ""])
        if not elegiveis:
            lines.append("Nenhum candidato passou pelos gates.")
        for idx, item in enumerate(elegiveis, 1):
            product_name = item.product.get("nome") or item.produto_id
            axes = " · ".join(f"{key} {value:.2f}" for key, value in item.axes.items())
            fonte_alerta = "confirmada manualmente" if item.quote.get("fonte") == "manual" else "estimativa web"
            tco_line = ""
            if item.quote.get("tco_total") and quote_float(item.quote.get("tco_total")) != quote_float(item.quote.get("custo_total")):
                tco_line = f"   TCO {item.quote.get('tco_meses')} meses R$ {item.quote.get('tco_total')}"
            lines.extend(
                [
                    f"{idx}. {product_name} - {item.score:.1f}",
                    f"   {axes}",
                    f"   custo_total R$ {item.quote.get('custo_total')} / {item.quote.get('loja')} / {fonte_alerta}",
                ]
            )
            if tco_line:
                lines.append(tco_line)
            if idx > 1 and elegiveis[0].score - item.score <= 3:
                lines.append("   empate tecnico com o lider")
            if item.alerts:
                lines.append(f"   alertas: {', '.join(item.alerts)}")
            lines.append("")
        lines.extend(["## Cortados pelos gates", ""])
        if not cortados:
            lines.append("Nenhum corte.")
        for item in cortados:
            product_name = item.product.get("nome") or item.produto_id
            motivos = "; ".join(item.eliminations)
            alertas = f" alertas: {', '.join(item.alerts)}" if item.alerts else ""
            lines.append(f"- {product_name}: {motivos}{alertas}")
        lines.extend(
            [
                "",
                "## Observacoes",
                "",
                "- Score zerado significa corte por gate, nao produto ruim em absoluto.",
                "- Linha `fonte=web` nao fecha compra; confirme preco, estoque e frete antes de decidir.",
                "- Diferenca de ate 3 pontos entre finalistas deve ser tratada como empate tecnico.",
                "- `ranking.csv` e derivado e pode ser sobrescrito; `cotacoes.csv` preserva a serie historica.",
            ]
        )

    (project / "ranking.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    write_ranking_csv(project, elegiveis, cortados)
    mark_steps(project, [5, 6])
    if elegiveis:
        lider = elegiveis[0]
        product_name = lider.product.get("nome") or lider.produto_id
        if lider.quote.get("fonte") == "manual":
            next_action = "registrar decisao final ou comparar segundo colocado"
            open_decision = f"{product_name} lidera com cotacao manual."
        else:
            next_action = "confirmar manualmente preco, frete, estoque, vendedor e garantia dos finalistas"
            open_decision = f"{product_name} lidera a pesquisa web, mas ainda nao fecha compra sem cotacao manual."
        set_process_state(project, proxima_acao=next_action, decisao_aberta=open_decision)
    print(project / "ranking.md")


def promote_quote(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    briefing, _ = load_frontmatter(project / "briefing.md")
    product = find_product(args.produto_id) or {}
    categoria = product.get("categoria") or briefing.get("categoria")
    rows = read_quotes(project)
    base = latest_quote_for_product(rows, args.produto_id, fonte=args.fonte_base)
    if not base:
        raise SystemExit(f"Nenhuma cotacao {args.fonte_base} encontrada para {args.produto_id}")

    row = dict(base)
    row["data_coleta"] = args.data or now_iso()
    row["fonte"] = "manual"
    for field, value in {
        "loja": args.loja,
        "vendedor": args.vendedor,
        "vendedor_tipo": args.vendedor_tipo,
        "anuncio_id": args.anuncio_id,
        "variacao": args.variacao,
        "preco": args.preco,
        "preco_promocional": args.preco_promocional,
        "frete_valor": args.frete,
        "frete_prazo_dias": args.frete_prazo_dias,
        "custo_extra": args.custo_extra,
        "custo_total": args.custo_total,
        "custo_operacional_mensal": args.custo_operacional_mensal,
        "tco_meses": args.tco_meses,
        "valor_revenda_estimado": args.valor_revenda_estimado,
        "tco_total": args.tco_total,
        "nota": args.nota,
        "n_avaliacoes": args.avaliacoes,
        "garantia_meses": args.garantia_meses,
        "garantia_tipo": args.garantia_tipo,
        "link": args.link,
        "flag_suspeita": args.flag_suspeita,
    }.items():
        if value is not None:
            row[field] = value

    preco = quote_float(row.get("preco"))
    promocional = quote_float(row.get("preco_promocional"), 0)
    preco_efetivo = promocional or preco
    if args.custo_total is None:
        row["custo_total"] = round(preco_efetivo + quote_float(row.get("frete_valor")) + quote_float(row.get("custo_extra")), 2)
    if not row.get("tco_meses"):
        row["tco_meses"] = category_tco_months(categoria) or ""
    if args.tco_total is None:
        row["tco_total"] = quote_tco_total(
            quote_float(row.get("custo_total")),
            quote_float(row.get("custo_operacional_mensal")),
            quote_int(row.get("tco_meses")),
            quote_float(row.get("valor_revenda_estimado")),
        )
    row["nota_ajustada"] = adjusted_rating(quote_float(row.get("nota")), quote_int(row.get("n_avaliacoes"))) if quote_float(row.get("nota")) else ""
    row["score"] = ""

    rows.append(row)
    write_quotes(project, rows)
    append_timeline(
        project,
        "cotacao-manual",
        f"Cotacao manual confirmada para {args.produto_id}",
        f"{row.get('loja')} / custo_total={row.get('custo_total')}",
    )
    mark_steps(project, [7])
    set_process_state(project, proxima_acao="gerar ranking com a cotacao manual e registrar decisao")
    print(f"Cotacao manual adicionada: {args.produto_id} - R$ {row.get('custo_total')}")


def discard_product(args: argparse.Namespace) -> None:
    if not args.porque.strip():
        raise SystemExit("Descarte exige motivo em --porque.")
    path = find_product_path(args.produto_id)
    if not path:
        raise SystemExit(f"Produto nao encontrado: {args.produto_id}")
    product = read_yaml(path, {})
    product["estado"] = "descartado"
    product["descartado_porque"] = args.porque
    write_yaml(path, product)
    project = project_path(args.projeto or product.get("projeto"))
    append_timeline(project, "descarte", f"Descartado {args.produto_id}", args.porque)
    set_process_state(project, proxima_acao="seguir com finalistas restantes ou registrar nova cotacao")
    print(f"Descartado: {args.produto_id}")


def wait_price(args: argparse.Namespace) -> None:
    path = find_product_path(args.produto_id)
    if not path:
        raise SystemExit(f"Produto nao encontrado: {args.produto_id}")
    product = read_yaml(path, {})
    project = project_path(args.projeto or product.get("projeto"))
    product["estado"] = "aguardando_preco"
    if args.preco_alvo is not None:
        product["preco_alvo"] = args.preco_alvo
    if args.preco_teto is not None:
        product["preco_teto"] = args.preco_teto
    product["aguardando_preco_porque"] = args.porque
    product["aguardando_preco_desde"] = today()
    write_yaml(path, product)
    append_timeline(project, "aguardando_preco", f"{args.produto_id} aguardando preco", args.porque)
    set_process_state(project, proxima_acao="reconsultar itens em aguardando_preco antes de decidir")
    print(f"Aguardando preco: {args.produto_id}")


def waiting_price_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for product_file in PRODUTOS.glob("*/**/produto.yaml"):
        product = read_yaml(product_file, {})
        if product.get("estado") != "aguardando_preco":
            continue
        project = PROJETOS / str(product.get("projeto"))
        quote = latest_quotes(read_quotes(project)).get(product.get("id")) if project.exists() else None
        atual = quote_float(quote.get("custo_total")) if quote else 0
        alvo = quote_float(product.get("preco_alvo"))
        teto = quote_float(product.get("preco_teto"))
        rows.append(
            {
                "produto_id": product.get("id"),
                "nome": product.get("nome"),
                "categoria": product.get("categoria"),
                "projeto": product.get("projeto"),
                "preco_atual": atual or "",
                "preco_alvo": alvo or "",
                "preco_teto": teto or "",
                "distancia_ate_alvo": round(atual - alvo, 2) if atual and alvo else "",
                "desde": product.get("aguardando_preco_desde", ""),
                "porque": product.get("aguardando_preco_porque", ""),
            }
        )
    return sorted(rows, key=lambda row: (str(row["categoria"]), str(row["produto_id"])))


def list_waiting_price(args: argparse.Namespace) -> None:
    rows = [row for row in waiting_price_rows() if not args.categoria or row["categoria"] == args.categoria]
    md_lines = [
        "# Aguardando preco",
        "",
        f"Gerado em {now_iso()}.",
        "",
        "| Produto | Categoria | Projeto | Atual | Alvo | Teto | Distancia | Desde | Motivo |",
        "|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        md_lines.append(
            f"| {row['nome']} | {row['categoria']} | {row['projeto']} | {row['preco_atual']} | {row['preco_alvo']} | {row['preco_teto']} | {row['distancia_ate_alvo']} | {row['desde']} | {row['porque']} |"
        )
    report = BASE / "aguardando-preco.md"
    report.write_text("\n".join(md_lines) + "\n", encoding="utf-8", newline="\n")
    csv_path = BASE / "aguardando-preco.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        fields = ["produto_id", "nome", "categoria", "projeto", "preco_atual", "preco_alvo", "preco_teto", "distancia_ate_alvo", "desde", "porque"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(report.relative_to(ROOT))
    print(f"Itens: {len(rows)}")


def ai_prompt(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    briefing_meta, briefing_body = load_frontmatter(project / "briefing.md")
    quotes = read_quotes(project)
    known = knowledge_context(project)
    known_block = f"\n\nBase de conhecimento relevante:\n{known}" if known else "\n\nBase de conhecimento relevante: nada registrado ainda."
    etapa = args.etapa
    common = f"""
Voce e meu assessor de compras. Use apenas como contexto as informacoes abaixo e deixe claro o que for inferencia.

Projeto: {project.name}
Categoria: {briefing_meta.get('categoria')}
Preco teto: {briefing_meta.get('preco_teto')}

Briefing:
{briefing_body.strip()}
{known_block}
"""
    if etapa == "modelo":
        prompt = common + """
Tarefa: transforme o pedido em um modelo de compra.

Responda com:
1. tipo/modelo mais adequado;
2. atributos obrigatorios para comparar produtos;
3. atributos que parecem marketing;
4. deal-breakers;
5. perguntas que eu ainda preciso responder antes de cotar.
"""
    elif etapa == "cotacao":
        prompt = common + """
Tarefa: sugira candidatos e uma estrategia de cotacao.

Responda com:
1. 3 a 5 candidatos plausiveis;
2. quais lojas/vendedores verificar manualmente;
3. problemas recorrentes para pesquisar em reviews;
4. campos de cotacao que eu nao posso esquecer;
5. alerta sobre o que voce nao consegue confirmar sem eu abrir o site.
"""
    elif etapa == "decisao":
        prompt = common + f"""
Cotacoes atuais:
{quotes}

Tarefa: ajude a redigir a decisao.

Responda com:
1. escolhido recomendado, se houver dados suficientes;
2. por que ele vence;
3. por que cada finalista perde;
4. riscos aceitos;
5. o que conferir manualmente antes de pagar.
"""
    else:
        prompt = common + """
Tarefa: monte perguntas de veredito D+30 e D+180 para extrair aprendizado reutilizavel.
"""
    print(textwrap.dedent(prompt).strip())


def decide(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    quote = latest_quotes(read_quotes(project)).get(args.produto_id)
    if not quote:
        raise SystemExit(f"Nenhuma cotacao encontrada para {args.produto_id}")
    product = find_product(args.produto_id) or {"nome": args.produto_id}
    if quote.get("fonte") != "manual" and not args.permitir_web:
        raise SystemExit("A cotacao final nao e manual. Use --permitir-web se quiser registrar mesmo assim.")

    perdedores = []
    for value in args.perdedores or []:
        if ":" not in value:
            raise SystemExit("Use --perdedores produto_id: motivo")
        produto, motivo = value.split(":", 1)
        perdedores.append((produto.strip(), motivo.strip()))

    lines = [
        "# Decisao",
        "",
        "## Escolhido",
        "",
        f"- Produto: {product.get('nome')}",
        f"- Produto ID: {args.produto_id}",
        f"- Cotacao usada: {quote.get('loja')} / {quote.get('vendedor')}",
        f"- Data: {today()}",
        f"- Custo total confirmado: R$ {quote.get('custo_total')}",
        "",
        "## Por que escolhi",
        "",
        f"- {args.porque}",
        "",
        "## Por que os outros perderam",
        "",
        "| Produto | Motivo |",
        "|---|---|",
    ]
    if perdedores:
        lines.extend(f"| {produto} | {motivo} |" for produto, motivo in perdedores)
    else:
        lines.append("|  |  |")
    lines.extend(
        [
            "",
            "## Riscos aceitos",
            "",
            *(f"- {risco}" for risco in (args.risco or ["Nenhum risco relevante registrado."])),
            "",
            "## O que conferir antes de pagar",
            "",
            "- [ ] Preco final",
            "- [ ] Frete",
            "- [ ] Prazo",
            "- [ ] Estoque",
            "- [ ] Vendedor",
            "- [ ] Garantia",
            "- [ ] Politica de devolucao",
            "",
            "## Lembretes de veredito",
            "",
            "- D+30:",
            "- D+180:",
        ]
    )
    (project / "decisao.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    append_timeline(project, "decisao", f"Escolhido {args.produto_id}", args.porque)
    mark_steps(project, [8])
    if args.comprado:
        mark_steps(project, [9])
        set_project_state(project, "comprado")
        set_process_state(project, estado="comprado", proxima_acao="acompanhar entrega e preencher veredito D+30")
    else:
        set_process_state(project, proxima_acao="comprar ou marcar como comprado depois da confirmacao final")
    verdict_path = create_verdict(project, args.produto_id, product, quote, force=args.force_veredito)
    append_timeline(project, "veredito", "Arquivo de veredito criado", verdict_path.name)
    print(project / "decisao.md")
    print(verdict_path)


def create_verdict(project: Path, produto_id: str, product: dict[str, Any], quote: dict[str, str], force: bool = False) -> Path:
    path = VEREDITOS / f"{today()}-{project.name}-{produto_id}.md"
    if path.exists() and not force:
        return path
    d30 = dt.date.today() + dt.timedelta(days=30)
    d180 = dt.date.today() + dt.timedelta(days=180)
    text = render_template("veredito.md")
    replacements = {
        "- Projeto:": f"- Projeto: {project.name}",
        "- Produto:": f"- Produto: {product.get('nome') or produto_id}",
        "- Data da compra:": f"- Data da compra: {today() if quote.get('fonte') == 'manual' else ''}",
        "- Valor pago:": f"- Valor pago: R$ {quote.get('custo_total')}",
        "- Vendedor:": f"- Vendedor: {quote.get('loja')} / {quote.get('vendedor')}",
        "- Veredito D+30 previsto:": f"- Veredito D+30 previsto: {d30.isoformat()}",
        "- Veredito D+180 previsto:": f"- Veredito D+180 previsto: {d180.isoformat()}",
    }
    for needle, replacement in replacements.items():
        text = text.replace(needle, replacement, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def replace_or_append_bullet(text: str, label: str, value: str) -> str:
    pattern = rf"(?m)^- {re.escape(label)}:[^\n]*$"
    replacement = f"- {label}: {value}"
    if re.search(pattern, text):
        return re.sub(pattern, replacement, text)
    return text.rstrip() + f"\n- {label}: {value}\n"


def fill_verdict(args: argparse.Namespace) -> None:
    path = Path(args.veredito)
    if not path.is_absolute():
        path = ROOT / args.veredito
    if not path.exists():
        raise SystemExit(f"Veredito nao encontrado: {args.veredito}")
    text = path.read_text(encoding="utf-8")
    prefix = "D+30" if args.fase == "d30" else "D+180"
    updates = {
        f"{prefix} preenchido em": today(),
        f"{prefix} nota arrependimento": str(args.nota_arrependimento),
        f"{prefix} compraria de novo": args.compraria_de_novo,
        f"{prefix} resumo": args.resumo,
    }
    if args.problema:
        updates[f"{prefix} problema"] = args.problema
    if args.licao:
        updates[f"{prefix} licao"] = args.licao
    for label, value in updates.items():
        text = replace_or_append_bullet(text, label, value)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(path)


def extract_bullet(text: str, label: str) -> str:
    for match in re.finditer(rf"(?m)^- {re.escape(label)}:[ \t]*(.*)$", text):
        value = match.group(1).strip()
        if value:
            return value
    return ""


def learn_from_verdict(args: argparse.Namespace) -> None:
    path = Path(args.veredito)
    if not path.is_absolute():
        path = ROOT / args.veredito
    if not path.exists():
        raise SystemExit(f"Veredito nao encontrado: {args.veredito}")
    text = path.read_text(encoding="utf-8")
    project_name = extract_bullet(text, "Projeto")
    product_name = extract_bullet(text, "Produto")
    seller = extract_bullet(text, "Vendedor")
    categoria = args.categoria or extract_bullet(text, "Categoria") or "geral"
    marca = args.marca or extract_bullet(text, "Marca")
    loja = args.loja or extract_bullet(text, "Loja") or seller.split("/")[0].strip()
    d30_summary = extract_bullet(text, "D+30 resumo")
    d180_summary = extract_bullet(text, "D+180 resumo")
    summary = args.resumo or d180_summary or d30_summary or f"Veredito registrado para {product_name}."
    lesson = args.licao or extract_bullet(text, "D+180 licao") or extract_bullet(text, "D+30 licao")
    buy_again = args.compraria_de_novo or extract_bullet(text, "D+180 compraria de novo") or extract_bullet(text, "D+30 compraria de novo")
    regret = args.nota_arrependimento
    if regret is None:
        raw_regret = extract_bullet(text, "D+180 nota arrependimento") or extract_bullet(text, "D+30 nota arrependimento")
        regret = quote_float(raw_regret, 0) if raw_regret else None

    if marca:
        register_brand(
            argparse.Namespace(
                nome=marca,
                categoria=categoria,
                projeto=project_name,
                nota=None if regret is None else max(0, 10 - regret),
                compraria_de_novo=buy_again if buy_again in {"sim", "nao", "talvez"} else None,
                resumo=summary,
                alerta=args.alerta,
            )
        )
    if loja:
        register_store(
            argparse.Namespace(
                nome=loja,
                categoria=categoria,
                projeto=project_name,
                nota=None if regret is None else max(0, 10 - regret),
                compraria_de_novo=buy_again if buy_again in {"sim", "nao", "talvez"} else None,
                resumo=summary,
                alerta=args.alerta,
            )
        )
    if lesson:
        register_lesson(argparse.Namespace(texto=lesson, categoria=categoria, gate=args.gate))

    marker = f"\n## Aprendizado exportado\n\n- Data: {today()}\n- Marca: {marca}\n- Loja: {loja}\n- Categoria: {categoria}\n- Licao: {lesson}\n"
    if "## Aprendizado exportado" not in text:
        append_text(path, marker)
    print(f"Aprendizado processado: {path}")


def new_verdict(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    path = VEREDITOS / f"{today()}-{project.name}.md"
    if path.exists() and not args.force:
        raise SystemExit(f"Veredito ja existe: {path}")
    text = render_template("veredito.md").replace("- Projeto:", f"- Projeto: {project.name}")
    path.write_text(text, encoding="utf-8", newline="\n")
    print(path.relative_to(ROOT))


def annotate(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    append_timeline(project, args.etapa, args.decisao, args.porque)
    print(f"Anotado em {project / 'processo.md'}")


def summarize(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    briefing_meta, _ = load_frontmatter(project / "briefing.md")
    quotes = read_quotes(project)
    latest = latest_quotes(quotes)
    decision = (project / "decisao.md").read_text(encoding="utf-8") if (project / "decisao.md").exists() else ""
    chosen_match = re.search(r"(?m)^- Produto:\s*(.+?)\s*$", decision)
    why_match = re.search(r"## Por que escolhi\s*\n\s*- ([^\n]+)", decision)

    print(f"Projeto: {project.name}")
    print(f"Categoria: {briefing_meta.get('categoria')}")
    print(f"Estado: {briefing_meta.get('estado')}")
    print(f"Preco teto: {briefing_meta.get('preco_teto')}")
    print(f"Cotacoes: {len(quotes)} ({sum(1 for r in quotes if r.get('fonte') == 'manual')} manuais)")
    print(f"Candidatos com cotacao: {len(latest)}")
    if chosen_match:
        chosen = chosen_match.group(1).strip()
        if chosen and not chosen.startswith("- "):
            print(f"Escolhido: {chosen}")
    if why_match:
        first_reason = why_match.group(1).strip()
        if first_reason:
            print(f"Por que: {first_reason}")


def status(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    briefing_meta, _ = load_frontmatter(project / "briefing.md")
    process = (project / "processo.md").read_text(encoding="utf-8") if (project / "processo.md").exists() else ""
    rows = read_quotes(project)
    latest = latest_quotes(rows)
    manual_ids = {row.get("produto_id") for row in rows if row.get("fonte") == "manual"}
    web_only_ids = set(latest) - manual_ids
    errors, warnings = validation_report(project)
    checked_steps = re.findall(r"(?m)^- \[x\] (\d+)\. (.+)$", process)
    open_steps = re.findall(r"(?m)^- \[ \] (\d+)\. (.+)$", process)
    next_action = re.search(r"(?m)^- Proxima acao:\s*(.+)$", process)
    open_decision = re.search(r"(?m)^- Decisao aberta:\s*(.+)$", process)

    print(f"Projeto: {project.name}")
    print(f"Estado: {briefing_meta.get('estado')}")
    print(f"Categoria: {briefing_meta.get('categoria')}")
    print(f"Preco teto: {briefing_meta.get('preco_teto')}")
    print(f"Etapas concluidas: {len(checked_steps)}")
    if open_steps:
        print(f"Proxima etapa aberta: {open_steps[0][0]}. {open_steps[0][1]}")
    if next_action:
        print(f"Proxima acao: {next_action.group(1).strip()}")
    if open_decision:
        print(f"Decisao aberta: {open_decision.group(1).strip()}")
    print(f"Cotacoes: {len(rows)} total, {len(manual_ids)} produtos com cotacao manual, {len(web_only_ids)} so web")
    print(f"Validacao: {len(errors)} erros, {len(warnings)} avisos")
    if web_only_ids:
        print("Confirmar manualmente: " + ", ".join(sorted(web_only_ids)))


def validate(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    errors, warnings = validation_report(project)
    lines = ["# Validacao", "", f"Gerado em {now_iso()}.", ""]
    lines.extend(["## Erros", ""])
    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("Nenhum erro.")
    lines.extend(["", "## Avisos", ""])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("Nenhum aviso.")
    lines.extend(
        [
            "",
            "## Criterio",
            "",
            "- Erro: impede decisao confiavel ou viola schema.",
            "- Aviso: nao impede pesquisa, mas precisa ser considerado antes de comprar.",
        ]
    )
    (project / "validacao.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(project / "validacao.md")
    print(f"Erros: {len(errors)}")
    print(f"Avisos: {len(warnings)}")
    if args.strict and errors:
        raise SystemExit(1)


def knowledge_entry(args: argparse.Namespace, kind: str) -> tuple[Path, str]:
    name = args.nome
    path = BASE / ("lojas" if kind == "loja" else "marcas") / f"{slugify(name)}.md"
    title = f"# {name}\n\n" if not path.exists() else ""
    fields = [
        f"## {today()}",
        "",
        f"- Tipo: {kind}",
        f"- Nome: {name}",
        f"- Categoria: {args.categoria or 'geral'}",
        f"- Projeto: {args.projeto or ''}",
        f"- Nota pessoal: {args.nota if args.nota is not None else ''}",
        f"- Compraria de novo: {args.compraria_de_novo or ''}",
        f"- Resumo: {args.resumo}",
    ]
    if args.alerta:
        fields.append(f"- Alerta: {args.alerta}")
    fields.append("")
    return path, title + "\n".join(fields) + "\n"


def register_store(args: argparse.Namespace) -> None:
    path, entry = knowledge_entry(args, "loja")
    append_text(path, entry)
    print(path.relative_to(ROOT))


def register_brand(args: argparse.Namespace) -> None:
    path, entry = knowledge_entry(args, "marca")
    append_text(path, entry)
    print(path.relative_to(ROOT))


def apply_lesson_gate(gate: str) -> str:
    if "=" not in gate or "." not in gate.split("=", 1)[0]:
        raise SystemExit("Use --gate categoria.campo=valor. Exemplo: cosmetico.exige_vendedor_oficial=true")
    left, raw_value = gate.split("=", 1)
    categoria, field = left.split(".", 1)
    categories = read_yaml(CONFIG / "categorias.yaml", {})
    category = categories.setdefault(categoria, {})
    gate_cfg = category.setdefault("gate", {})
    gate_cfg[field] = parse_scalar(raw_value)
    write_yaml(CONFIG / "categorias.yaml", categories)
    return f"{categoria}.{field}={gate_cfg[field]}"


def register_lesson(args: argparse.Namespace) -> None:
    gate_note = ""
    if args.gate:
        applied = apply_lesson_gate(args.gate)
        gate_note = f" Gate atualizado: {applied}."
    line = f"{today()} - {args.categoria or 'geral'} - {args.texto}{gate_note}\n"
    append_text(BASE / "licoes.md", line)
    print(BASE / "licoes.md")


def project_product_ids(project: Path) -> set[str]:
    ids = {row.get("produto_id") for row in read_quotes(project) if row.get("produto_id")}
    for product_file in PRODUTOS.glob("*/**/produto.yaml"):
        product = read_yaml(product_file, {})
        if product.get("projeto") == project.name and product.get("id"):
            ids.add(product["id"])
    return ids


def project_brands(project: Path) -> set[str]:
    brands: set[str] = set()
    for produto_id in project_product_ids(project):
        product = find_product(produto_id)
        if product and product.get("marca"):
            brands.add(str(product["marca"]))
    return brands


def project_stores(project: Path) -> set[str]:
    return {row.get("loja") for row in read_quotes(project) if row.get("loja")}


def knowledge_files_for_project(project: Path) -> tuple[list[Path], list[Path]]:
    brand_files = [BASE / "marcas" / f"{slugify(name)}.md" for name in project_brands(project)]
    store_files = [BASE / "lojas" / f"{slugify(name)}.md" for name in project_stores(project)]
    return [path for path in brand_files if path.exists()], [path for path in store_files if path.exists()]


def lesson_lines_for_category(categoria: str | None) -> list[str]:
    path = BASE / "licoes.md"
    if not path.exists():
        return []
    lines = []
    wanted = (categoria or "").lower()
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or clean.startswith("Formato") or clean.startswith("```"):
            continue
        lowered = clean.lower()
        if not wanted or f"- {wanted} -" in lowered or "- geral -" in lowered:
            lines.append(clean)
    return lines[-10:]


def knowledge_context(project: Path) -> str:
    briefing, _ = load_frontmatter(project / "briefing.md")
    categoria = briefing.get("categoria")
    brand_files, store_files = knowledge_files_for_project(project)
    lesson_lines = lesson_lines_for_category(categoria)
    parts: list[str] = []
    if lesson_lines:
        parts.append("Licoes relevantes:\n" + "\n".join(f"- {line}" for line in lesson_lines))
    if brand_files:
        brand_text = []
        for path in brand_files:
            brand_text.append(path.read_text(encoding="utf-8").strip()[-1200:])
        parts.append("Marcas ja conhecidas:\n" + "\n\n".join(brand_text))
    if store_files:
        store_text = []
        for path in store_files:
            store_text.append(path.read_text(encoding="utf-8").strip()[-1200:])
        parts.append("Lojas ja conhecidas:\n" + "\n\n".join(store_text))
    return "\n\n".join(parts)


def reuse_stats(categoria: str | None = None) -> tuple[list[dict[str, Any]], int, int, float]:
    projects = sorted(path for path in PROJETOS.iterdir() if path.is_dir()) if PROJETOS.exists() else []
    rows = []
    for project in projects:
        briefing, _ = load_frontmatter(project / "briefing.md")
        if categoria and briefing.get("categoria") != categoria:
            continue
        brand_files, store_files = knowledge_files_for_project(project)
        lessons = lesson_lines_for_category(briefing.get("categoria"))
        useful = bool(brand_files or store_files or lessons)
        rows.append(
            {
                "projeto": project.name,
                "categoria": briefing.get("categoria"),
                "marcas": len(brand_files),
                "lojas": len(store_files),
                "licoes": len(lessons),
                "reaproveitou": useful,
            }
        )
    total = len(rows)
    reused = sum(1 for row in rows if row["reaproveitou"])
    percent = round((reused / total) * 100, 1) if total else 0
    return rows, total, reused, percent


def reuse_report(args: argparse.Namespace) -> None:
    rows, total, reused, percent = reuse_stats(args.categoria)
    lines = ["# Reaproveitamento", "", f"Gerado em {now_iso()}.", "", f"- Projetos analisados: {total}", f"- Projetos com conhecimento reutilizavel: {reused}", f"- Taxa: {percent}%", "", "| Projeto | Categoria | Marcas | Lojas | Licoes | Reaproveitou |", "|---|---|---:|---:|---:|---|"]
    for row in rows:
        lines.append(f"| {row['projeto']} | {row['categoria']} | {row['marcas']} | {row['lojas']} | {row['licoes']} | {'sim' if row['reaproveitou'] else 'nao'} |")
    path = BASE / "reaproveitamento.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(path.relative_to(ROOT))
    print(f"Taxa: {percent}%")


def read_csv_file(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def safe_html(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def dashboard_link(from_dir: Path, target: Path, label: str) -> str:
    rel = os.path.relpath(target, from_dir).replace("\\", "/")
    return f'<a href="{safe_html(rel)}">{safe_html(label)}</a>'


def project_dirs() -> list[Path]:
    if not PROJETOS.exists():
        return []
    return sorted(path for path in PROJETOS.iterdir() if path.is_dir() and (path / "briefing.md").exists())


def project_decision_summary(project: Path) -> tuple[str, str]:
    decision = project / "decisao.md"
    if not decision.exists():
        return "", ""
    text = decision.read_text(encoding="utf-8")
    chosen = extract_bullet(text, "Produto")
    why_match = re.search(r"## Por que escolhi\s*\n\s*- ([^\n]+)", text)
    why = why_match.group(1).strip() if why_match else ""
    if chosen.startswith("- "):
        chosen = ""
    return chosen, why


def project_counts(project: Path) -> dict[str, Any]:
    briefing, _ = load_frontmatter(project / "briefing.md")
    quotes = read_quotes(project)
    latest = latest_quotes(quotes)
    ranking = read_csv_file(project / "ranking.csv")
    errors, warnings = validation_report(project)
    chosen, why = project_decision_summary(project)
    manual_ids = {row.get("produto_id") for row in quotes if row.get("fonte") == "manual"}
    leader = next((row for row in ranking if row.get("status") == "elegivel"), None)
    opened_at = parse_dashboard_date(briefing.get("criado_em"))
    decided_at = decision_date(project)
    decision_days = (decided_at - opened_at).days if opened_at and decided_at else ""
    waiting = [
        row for row in waiting_price_rows()
        if row.get("projeto") == project.name
    ]
    return {
        "id": project.name,
        "categoria": briefing.get("categoria"),
        "estado": briefing.get("estado"),
        "preco_teto": briefing.get("preco_teto"),
        "cotacoes": len(quotes),
        "manual": len(manual_ids),
        "candidatos": len(latest),
        "erros": len(errors),
        "avisos": len(warnings),
        "lider": leader.get("nome") if leader else "",
        "score": leader.get("score") if leader else "",
        "escolhido": chosen,
        "porque": why,
        "aguardando_preco": len(waiting),
        "criado_em": opened_at.isoformat() if opened_at else "",
        "data_decisao": decided_at.isoformat() if decided_at else "",
        "dias_ate_decisao": decision_days,
        "gate_ok": len(errors) == 0,
    }


def verdict_summaries() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(VEREDITOS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        rows.append(
            {
                "arquivo": path.name,
                "projeto": extract_bullet(text, "Projeto"),
                "produto": extract_bullet(text, "Produto"),
                "d30": extract_bullet(text, "D+30 nota arrependimento"),
                "d180": extract_bullet(text, "D+180 nota arrependimento"),
                "resumo": extract_bullet(text, "D+180 resumo") or extract_bullet(text, "D+30 resumo"),
            }
        )
    return rows


def dashboard_styles() -> str:
    return """
:root {
  color-scheme: light;
  --bg: #f7f5ef;
  --surface: #ffffff;
  --ink: #20201d;
  --muted: #67645e;
  --line: #ded8cb;
  --teal: #0f766e;
  --green: #2f7d32;
  --amber: #b7791f;
  --coral: #b45342;
  --blue: #2563eb;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Arial, Helvetica, sans-serif;
  background: var(--bg);
  color: var(--ink);
  letter-spacing: 0;
}
a { color: var(--teal); text-decoration: none; }
a:hover { text-decoration: underline; }
.shell { max-width: 1240px; margin: 0 auto; padding: 24px; }
.topbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  border-bottom: 1px solid var(--line);
  padding-bottom: 18px;
  margin-bottom: 18px;
}
h1 { font-size: 28px; line-height: 1.1; margin: 0 0 6px; }
h2 { font-size: 18px; margin: 0 0 12px; }
h3 { font-size: 15px; margin: 0 0 8px; }
.muted { color: var(--muted); font-size: 13px; }
.grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.panel, .metric {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
}
.metric strong { display: block; font-size: 24px; line-height: 1.1; }
.metric span { color: var(--muted); font-size: 12px; }
.metric.teal { border-top: 4px solid var(--teal); }
.metric.green { border-top: 4px solid var(--green); }
.metric.amber { border-top: 4px solid var(--amber); }
.metric.coral { border-top: 4px solid var(--coral); }
.section { margin-top: 18px; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
th, td { border-bottom: 1px solid var(--line); padding: 8px 6px; text-align: left; vertical-align: top; font-size: 13px; }
th { color: var(--muted); font-weight: 700; }
td.num, th.num { text-align: right; }
.pill { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 12px; background: #ede8dc; color: var(--ink); }
.pill.ok { background: #dff0df; color: var(--green); }
.pill.warn { background: #faedcc; color: var(--amber); }
.pill.bad { background: #f5d7d1; color: var(--coral); }
.bars { display: grid; gap: 8px; }
.bar-row { display: grid; grid-template-columns: 120px 1fr 42px; align-items: center; gap: 8px; font-size: 13px; }
.bar-track { height: 10px; background: #ede8dc; border-radius: 999px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--teal); }
.actions { display: flex; gap: 10px; flex-wrap: wrap; }
.actions a { font-size: 13px; }
pre {
  white-space: pre-wrap;
  background: #2b2a26;
  color: #faf7ef;
  padding: 12px;
  border-radius: 8px;
  overflow: auto;
}
@media (max-width: 900px) {
  .grid, .two { grid-template-columns: 1fr; }
  .topbar { display: block; }
  .shell { padding: 16px; }
  th, td { font-size: 12px; }
}
"""


def write_dashboard_asset() -> None:
    assets = DASHBOARD / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "styles.css").write_text(dashboard_styles().strip() + "\n", encoding="utf-8", newline="\n")


def html_page(title: str, body: str, current_dir: Path) -> str:
    css = os.path.relpath(DASHBOARD / "assets" / "styles.css", current_dir).replace("\\", "/")
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_html(title)}</title>
  <link rel="stylesheet" href="{safe_html(css)}">
</head>
<body>
  <main class="shell">
    {body}
  </main>
</body>
</html>
"""


def bar_chart(counts: dict[str, int]) -> str:
    max_value = max(counts.values(), default=1) or 1
    rows = []
    for label, value in sorted(counts.items()):
        width = round((value / max_value) * 100, 1)
        rows.append(
            f'<div class="bar-row"><span>{safe_html(label)}</span><div class="bar-track"><div class="bar-fill" style="width: {width}%"></div></div><strong>{value}</strong></div>'
        )
    return '<div class="bars">' + "".join(rows) + "</div>"


def parse_dashboard_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.date):
        return value
    if value in {None, ""}:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def decision_date(project: Path) -> dt.date | None:
    decision = project / "decisao.md"
    if not decision.exists():
        return None
    text = decision.read_text(encoding="utf-8")
    return parse_dashboard_date(extract_bullet(text, "Data"))


def generate_project_page(project: Path) -> Path:
    page_dir = DASHBOARD / "projetos"
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{project.name}.html"
    summary = project_counts(project)
    ranking = read_csv_file(project / "ranking.csv")
    quotes = read_quotes(project)
    source_links = " · ".join(
        [
            dashboard_link(page_dir, project / "briefing.md", "briefing"),
            dashboard_link(page_dir, project / "processo.md", "processo"),
            dashboard_link(page_dir, project / "ranking.md", "ranking"),
            dashboard_link(page_dir, project / "cotacoes.csv", "cotacoes"),
            dashboard_link(page_dir, project / "validacao.md", "validacao"),
        ]
    )
    ranking_rows = []
    for row in ranking:
        status_class = "bad" if row.get("status") == "cortado" else "ok"
        ranking_rows.append(
            "<tr>"
            f"<td>{safe_html(row.get('nome'))}</td>"
            f"<td class=\"num\">{safe_html(row.get('score'))}</td>"
            f"<td><span class=\"pill {status_class}\">{safe_html(row.get('status'))}</span></td>"
            f"<td>{safe_html(row.get('motivos'))}</td>"
            f"<td>{safe_html(row.get('alertas'))}</td>"
            "</tr>"
        )
    quote_rows = []
    for row in quotes[-20:]:
        quote_rows.append(
            "<tr>"
            f"<td>{safe_html(row.get('data_coleta'))}</td>"
            f"<td>{safe_html(row.get('produto_id'))}</td>"
            f"<td>{safe_html(row.get('loja'))}</td>"
            f"<td class=\"num\">{safe_html(row.get('custo_total'))}</td>"
            f"<td>{safe_html(row.get('fonte'))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>{safe_html(project.name)}</h1>
    <div class="muted">{safe_html(summary.get('categoria'))} · {safe_html(summary.get('estado'))}</div>
  </div>
  <div class="actions">{dashboard_link(page_dir, DASHBOARD / "index.html", "inicio")} · {source_links}</div>
</div>
<section class="grid">
  <div class="metric teal"><strong>{safe_html(summary['cotacoes'])}</strong><span>cotacoes</span></div>
  <div class="metric green"><strong>{safe_html(summary['manual'])}</strong><span>produtos com cotacao manual</span></div>
  <div class="metric amber"><strong>{safe_html(summary['avisos'])}</strong><span>avisos</span></div>
  <div class="metric coral"><strong>{safe_html(summary['dias_ate_decisao'])}</strong><span>dias ate decisao</span></div>
</section>
<section class="section panel">
  <h2>Decisao</h2>
  <table>
    <tbody>
      <tr><td>Escolhido</td><td>{safe_html(summary['escolhido'])}</td></tr>
      <tr><td>Por que</td><td>{safe_html(summary['porque'])}</td></tr>
      <tr><td>Gate</td><td><span class="pill {'ok' if summary['gate_ok'] else 'bad'}">{'ok' if summary['gate_ok'] else 'com erro'}</span></td></tr>
      <tr><td>Aguardando preco</td><td>{safe_html(summary['aguardando_preco'])}</td></tr>
    </tbody>
  </table>
</section>
<section class="section panel">
  <h2>Ranking</h2>
  <table>
    <thead><tr><th>Produto</th><th class="num">Score</th><th>Status</th><th>Motivos</th><th>Alertas</th></tr></thead>
    <tbody>{''.join(ranking_rows) or '<tr><td colspan="5">Sem ranking gerado.</td></tr>'}</tbody>
  </table>
</section>
<section class="section panel">
  <h2>Cotacoes</h2>
  <table>
    <thead><tr><th>Data</th><th>Produto</th><th>Loja</th><th class="num">Custo</th><th>Fonte</th></tr></thead>
    <tbody>{''.join(quote_rows) or '<tr><td colspan="5">Sem cotacoes.</td></tr>'}</tbody>
  </table>
</section>
"""
    page.write_text(html_page(project.name, body, page_dir), encoding="utf-8", newline="\n")
    return page


def generate_knowledge_page() -> Path:
    page = DASHBOARD / "base-conhecimento.html"
    brand_files = sorted((BASE / "marcas").glob("*.md"))
    store_files = sorted((BASE / "lojas").glob("*.md"))
    lessons = lesson_lines_for_category(None)
    brand_rows = "".join(f"<tr><td>{dashboard_link(DASHBOARD, path, path.stem)}</td></tr>" for path in brand_files)
    store_rows = "".join(f"<tr><td>{dashboard_link(DASHBOARD, path, path.stem)}</td></tr>" for path in store_files)
    lesson_rows = "".join(f"<tr><td>{safe_html(line)}</td></tr>" for line in lessons)
    body = f"""
<div class="topbar">
  <div>
    <h1>Base de conhecimento</h1>
    <div class="muted">Marcas, lojas e licoes registradas</div>
  </div>
  <div class="actions">{dashboard_link(DASHBOARD, DASHBOARD / "index.html", "inicio")} · {dashboard_link(DASHBOARD, BASE / "licoes.md", "licoes.md")}</div>
</div>
<section class="grid">
  <div class="metric teal"><strong>{len(brand_files)}</strong><span>marcas</span></div>
  <div class="metric green"><strong>{len(store_files)}</strong><span>lojas</span></div>
  <div class="metric amber"><strong>{len(lessons)}</strong><span>licoes recentes</span></div>
  <div class="metric coral"><strong>{len(waiting_price_rows())}</strong><span>aguardando preco</span></div>
</section>
<section class="two section">
  <div class="panel"><h2>Marcas</h2><table><tbody>{brand_rows or '<tr><td>Nenhuma marca.</td></tr>'}</tbody></table></div>
  <div class="panel"><h2>Lojas</h2><table><tbody>{store_rows or '<tr><td>Nenhuma loja.</td></tr>'}</tbody></table></div>
</section>
<section class="section panel"><h2>Licoes</h2><table><tbody>{lesson_rows or '<tr><td>Nenhuma licao.</td></tr>'}</tbody></table></section>
"""
    page.write_text(html_page("Base de conhecimento", body, DASHBOARD), encoding="utf-8", newline="\n")
    return page


def generate_dashboard(args: argparse.Namespace) -> None:
    DASHBOARD.mkdir(parents=True, exist_ok=True)
    write_dashboard_asset()
    projects = project_dirs()
    summaries = [project_counts(project) for project in projects]
    for project in projects:
        generate_project_page(project)
    knowledge_page = generate_knowledge_page()
    waiting = waiting_price_rows()
    verdicts = verdict_summaries()
    states: dict[str, int] = {}
    for summary in summaries:
        states[str(summary.get("estado") or "sem_estado")] = states.get(str(summary.get("estado") or "sem_estado"), 0) + 1
    _, _, _, reuse_percent = reuse_stats(None)
    reuse_rate = f"{reuse_percent}%"
    manual_projects = sum(1 for summary in summaries if summary["manual"])
    warnings_total = sum(int(summary["avisos"]) for summary in summaries)
    gate_ok = sum(1 for summary in summaries if summary["gate_ok"])
    gate_rate = round((gate_ok / len(summaries)) * 100, 1) if summaries else 0
    decision_days_values = [int(summary["dias_ate_decisao"]) for summary in summaries if summary["dias_ate_decisao"] != ""]
    avg_decision_days = round(sum(decision_days_values) / len(decision_days_values), 1) if decision_days_values else ""
    regrets = [
        quote_float(value)
        for row in verdicts
        for value in [row.get("d180") or row.get("d30")]
        if value not in {None, ""}
    ]
    avg_regret = round(sum(regrets) / len(regrets), 1) if regrets else ""
    project_rows = []
    for project, summary in zip(projects, summaries):
        page = DASHBOARD / "projetos" / f"{project.name}.html"
        pill_class = "ok" if summary["estado"] == "comprado" else "warn" if summary["aguardando_preco"] else ""
        project_rows.append(
            "<tr>"
            f"<td>{dashboard_link(DASHBOARD, page, summary['id'])}</td>"
            f"<td>{safe_html(summary['categoria'])}</td>"
            f"<td><span class=\"pill {pill_class}\">{safe_html(summary['estado'])}</span></td>"
            f"<td>{safe_html(summary['lider'])}</td>"
            f"<td class=\"num\">{safe_html(summary['score'])}</td>"
            f"<td class=\"num\">{safe_html(summary['cotacoes'])}</td>"
            f"<td class=\"num\">{safe_html(summary['manual'])}</td>"
            f"<td class=\"num\">{safe_html(summary['dias_ate_decisao'])}</td>"
            "</tr>"
        )
    waiting_rows = []
    for row in waiting:
        waiting_rows.append(
            "<tr>"
            f"<td>{safe_html(row['nome'])}</td>"
            f"<td>{safe_html(row['projeto'])}</td>"
            f"<td class=\"num\">{safe_html(row['preco_atual'])}</td>"
            f"<td class=\"num\">{safe_html(row['preco_alvo'])}</td>"
            f"<td class=\"num\">{safe_html(row['distancia_ate_alvo'])}</td>"
            "</tr>"
        )
    verdict_rows = []
    for row in verdicts[-10:]:
        verdict_rows.append(
            "<tr>"
            f"<td>{dashboard_link(DASHBOARD, VEREDITOS / row['arquivo'], row['produto'] or row['arquivo'])}</td>"
            f"<td>{safe_html(row['projeto'])}</td>"
            f"<td class=\"num\">{safe_html(row['d30'])}</td>"
            f"<td class=\"num\">{safe_html(row['d180'])}</td>"
            f"<td>{safe_html(row['resumo'])}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Central de Compras</h1>
    <div class="muted">Atualizado em {safe_html(now_iso())}</div>
  </div>
  <div class="actions">{dashboard_link(DASHBOARD, knowledge_page, "base de conhecimento")} · {dashboard_link(DASHBOARD, BASE / "aguardando-preco.md", "aguardando preco")}</div>
</div>
<section class="grid">
  <div class="metric teal"><strong>{len(projects)}</strong><span>projetos</span></div>
  <div class="metric green"><strong>{manual_projects}</strong><span>com cotacao manual</span></div>
  <div class="metric amber"><strong>{len(waiting)}</strong><span>aguardando preco</span></div>
  <div class="metric coral"><strong>{safe_html(avg_decision_days)}</strong><span>dias medios ate decisao</span></div>
</section>
<section class="two section">
  <div class="panel"><h2>Estados</h2>{bar_chart(states)}</div>
  <div class="panel"><h2>Indicadores</h2><table><tbody><tr><td>Reaproveitamento</td><td class="num">{safe_html(reuse_rate)}</td></tr><tr><td>Aderencia ao gate</td><td class="num">{gate_rate}%</td></tr><tr><td>Avisos abertos</td><td class="num">{warnings_total}</td></tr><tr><td>Arrependimento medio</td><td class="num">{safe_html(avg_regret)}</td></tr><tr><td>Vereditos</td><td class="num">{len(verdicts)}</td></tr></tbody></table></div>
</section>
<section class="section panel">
  <h2>Projetos</h2>
  <table>
    <thead><tr><th>Projeto</th><th>Categoria</th><th>Estado</th><th>Lider</th><th class="num">Score</th><th class="num">Cotacoes</th><th class="num">Manual</th><th class="num">Dias</th></tr></thead>
    <tbody>{''.join(project_rows) or '<tr><td colspan="8">Nenhum projeto.</td></tr>'}</tbody>
  </table>
</section>
<section class="two section">
  <div class="panel"><h2>Aguardando Preco</h2><table><thead><tr><th>Produto</th><th>Projeto</th><th class="num">Atual</th><th class="num">Alvo</th><th class="num">Distancia</th></tr></thead><tbody>{''.join(waiting_rows) or '<tr><td colspan="5">Nenhum item.</td></tr>'}</tbody></table></div>
  <div class="panel"><h2>Vereditos</h2><table><thead><tr><th>Produto</th><th>Projeto</th><th class="num">D+30</th><th class="num">D+180</th><th>Resumo</th></tr></thead><tbody>{''.join(verdict_rows) or '<tr><td colspan="5">Nenhum veredito.</td></tr>'}</tbody></table></div>
</section>
"""
    index = DASHBOARD / "index.html"
    index.write_text(html_page("Central de Compras", body, DASHBOARD), encoding="utf-8", newline="\n")
    print(index.relative_to(ROOT))
    print(f"Projetos: {len(projects)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Central de Compras")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("init", help="confere/cria a estrutura de diretorios")
    p.set_defaults(func=ensure_structure)

    p = sub.add_parser("novo-projeto", help="cria um processo de compra")
    p.add_argument("nome")
    p.add_argument("--categoria", default="generico")
    p.add_argument("--valor-estimado", type=float, default=0)
    p.add_argument("--preco-teto", type=float)
    p.add_argument("--necessidade")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=new_project)

    p = sub.add_parser("novo-produto", help="registra um candidato")
    p.add_argument("projeto")
    p.add_argument("nome")
    p.add_argument("--marca", default="")
    p.add_argument("--categoria")
    p.add_argument("--produto-id")
    p.add_argument("--preco-alvo", type=float)
    p.add_argument("--preco-teto", type=float)
    p.add_argument("--atributo", action="append", default=[])
    p.add_argument("--requisito", action="append", default=[])
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=new_product)

    p = sub.add_parser("cotar", help="adiciona uma cotacao append-only")
    p.add_argument("projeto")
    p.add_argument("--produto-id", required=True)
    p.add_argument("--loja", required=True)
    p.add_argument("--vendedor", default="")
    p.add_argument("--vendedor-tipo", choices=["oficial", "terceiro", "fisica"], default="terceiro")
    p.add_argument("--anuncio-id")
    p.add_argument("--variacao")
    p.add_argument("--preco", type=float, required=True)
    p.add_argument("--preco-promocional", type=float)
    p.add_argument("--frete", type=float, default=0)
    p.add_argument("--frete-prazo-dias", type=int)
    p.add_argument("--custo-extra", type=float, default=0)
    p.add_argument("--custo-total", type=float)
    p.add_argument("--custo-operacional-mensal", type=float, default=0)
    p.add_argument("--tco-meses", type=int)
    p.add_argument("--valor-revenda-estimado", type=float, default=0)
    p.add_argument("--nota", type=float, default=0)
    p.add_argument("--avaliacoes", type=int, default=0)
    p.add_argument("--garantia-meses", type=int)
    p.add_argument("--garantia-tipo", choices=["nacional", "importada", "vendedor", "nenhuma"], default="nenhuma")
    p.add_argument("--link")
    p.add_argument("--flag-suspeita", choices=["", "AVAL_SUSPEITA", "ANCORA", "RECICLADO"], default="")
    p.add_argument("--fonte", choices=["web", "manual"], default="manual")
    p.add_argument("--data")
    p.set_defaults(func=add_quote)

    p = sub.add_parser("ranking", help="gera ranking.md com gates e score aberto")
    p.add_argument("projeto")
    p.set_defaults(func=build_ranking)

    p = sub.add_parser("validar", help="gera validacao.md com campos faltantes e alertas")
    p.add_argument("projeto")
    p.add_argument("--strict", action="store_true", help="retorna erro se houver erro de validacao")
    p.set_defaults(func=validate)

    p = sub.add_parser("registrar-loja", help="adiciona experiencia propria sobre uma loja")
    p.add_argument("nome")
    p.add_argument("--resumo", required=True)
    p.add_argument("--categoria")
    p.add_argument("--projeto")
    p.add_argument("--nota", type=float)
    p.add_argument("--compraria-de-novo", choices=["sim", "nao", "talvez"])
    p.add_argument("--alerta")
    p.set_defaults(func=register_store)

    p = sub.add_parser("registrar-marca", help="adiciona experiencia propria sobre uma marca")
    p.add_argument("nome")
    p.add_argument("--resumo", required=True)
    p.add_argument("--categoria")
    p.add_argument("--projeto")
    p.add_argument("--nota", type=float)
    p.add_argument("--compraria-de-novo", choices=["sim", "nao", "talvez"])
    p.add_argument("--alerta")
    p.set_defaults(func=register_brand)

    p = sub.add_parser("registrar-licao", help="adiciona licao e opcionalmente converte em gate")
    p.add_argument("texto")
    p.add_argument("--categoria")
    p.add_argument("--gate", help="atualiza gate no formato categoria.campo=valor")
    p.set_defaults(func=register_lesson)

    p = sub.add_parser("reaproveitamento", help="gera relatorio de conhecimento reutilizavel")
    p.add_argument("--categoria")
    p.set_defaults(func=reuse_report)

    p = sub.add_parser("dashboard", help="gera dashboard HTML local")
    p.set_defaults(func=generate_dashboard)

    p = sub.add_parser("prompt-ia", help="gera prompt de apoio para uma etapa")
    p.add_argument("projeto")
    p.add_argument("--etapa", choices=["modelo", "cotacao", "decisao", "veredito"], default="modelo")
    p.set_defaults(func=ai_prompt)

    p = sub.add_parser("decidir", help="preenche decisao.md")
    p.add_argument("projeto")
    p.add_argument("--produto-id", required=True)
    p.add_argument("--porque", required=True)
    p.add_argument("--perdedores", action="append", default=[])
    p.add_argument("--risco", action="append", default=[])
    p.add_argument("--permitir-web", action="store_true")
    p.add_argument("--comprado", action="store_true", help="marca o projeto como comprado ao decidir")
    p.add_argument("--force-veredito", action="store_true", help="sobrescreve veredito existente")
    p.set_defaults(func=decide)

    p = sub.add_parser("novo-veredito", help="cria arquivo de veredito pos-compra")
    p.add_argument("projeto")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=new_verdict)

    p = sub.add_parser("promover-cotacao", help="cria uma cotacao manual baseada na ultima cotacao web")
    p.add_argument("projeto")
    p.add_argument("--produto-id", required=True)
    p.add_argument("--fonte-base", choices=["web", "manual"], default="web")
    p.add_argument("--loja")
    p.add_argument("--vendedor")
    p.add_argument("--vendedor-tipo", choices=["oficial", "terceiro", "fisica"])
    p.add_argument("--anuncio-id")
    p.add_argument("--variacao")
    p.add_argument("--preco", type=float)
    p.add_argument("--preco-promocional", type=float)
    p.add_argument("--frete", type=float)
    p.add_argument("--frete-prazo-dias", type=int)
    p.add_argument("--custo-extra", type=float)
    p.add_argument("--custo-total", type=float)
    p.add_argument("--custo-operacional-mensal", type=float)
    p.add_argument("--tco-meses", type=int)
    p.add_argument("--valor-revenda-estimado", type=float)
    p.add_argument("--tco-total", type=float)
    p.add_argument("--nota", type=float)
    p.add_argument("--avaliacoes", type=int)
    p.add_argument("--garantia-meses", type=int)
    p.add_argument("--garantia-tipo", choices=["nacional", "importada", "vendedor", "nenhuma"])
    p.add_argument("--link")
    p.add_argument("--flag-suspeita", choices=["", "AVAL_SUSPEITA", "ANCORA", "RECICLADO"])
    p.add_argument("--data")
    p.set_defaults(func=promote_quote)

    p = sub.add_parser("descartar", help="marca candidato como descartado com motivo obrigatorio")
    p.add_argument("--produto-id", required=True)
    p.add_argument("--porque", required=True)
    p.add_argument("--projeto")
    p.set_defaults(func=discard_product)

    p = sub.add_parser("aguardar-preco", help="marca produto como aguardando preco alvo")
    p.add_argument("--produto-id", required=True)
    p.add_argument("--porque", required=True)
    p.add_argument("--preco-alvo", type=float)
    p.add_argument("--preco-teto", type=float)
    p.add_argument("--projeto")
    p.set_defaults(func=wait_price)

    p = sub.add_parser("listar-aguardando-preco", help="gera relatorio de itens aguardando preco")
    p.add_argument("--categoria")
    p.set_defaults(func=list_waiting_price)

    p = sub.add_parser("anotar", help="registra uma decisao intermediaria no processo.md")
    p.add_argument("projeto")
    p.add_argument("--etapa", required=True)
    p.add_argument("--decisao", required=True)
    p.add_argument("--porque", required=True)
    p.set_defaults(func=annotate)

    p = sub.add_parser("resumo", help="mostra um resumo rapido da compra")
    p.add_argument("projeto")
    p.set_defaults(func=summarize)

    p = sub.add_parser("status", help="mostra etapa atual, bloqueios e proximas acoes")
    p.add_argument("projeto")
    p.set_defaults(func=status)

    p = sub.add_parser("preencher-veredito", help="preenche resumo estruturado D+30 ou D+180")
    p.add_argument("veredito")
    p.add_argument("--fase", choices=["d30", "d180"], required=True)
    p.add_argument("--nota-arrependimento", type=float, required=True)
    p.add_argument("--compraria-de-novo", choices=["sim", "nao", "talvez"], required=True)
    p.add_argument("--resumo", required=True)
    p.add_argument("--problema")
    p.add_argument("--licao")
    p.set_defaults(func=fill_verdict)

    p = sub.add_parser("aprender-veredito", help="transforma veredito preenchido em marca, loja e licao")
    p.add_argument("veredito")
    p.add_argument("--marca")
    p.add_argument("--loja")
    p.add_argument("--categoria")
    p.add_argument("--resumo")
    p.add_argument("--licao")
    p.add_argument("--gate")
    p.add_argument("--alerta")
    p.add_argument("--nota-arrependimento", type=float)
    p.add_argument("--compraria-de-novo", choices=["sim", "nao", "talvez"])
    p.set_defaults(func=learn_from_verdict)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
