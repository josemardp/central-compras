#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
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
        "atributos": parse_pairs(args.atributo or []),
        "requisitos_atendidos": parse_pairs(args.requisito or []),
        "descartado_porque": None,
    }
    write_yaml(path / "produto.yaml", data)
    (path / "pesquisa.md").write_text(render_template("pesquisa.md"), encoding="utf-8", newline="\n")
    append_timeline(project, "produto", f"Candidato registrado: {args.nome}", f"id={produto_id}")
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


def add_quote(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    rows = read_quotes(project)
    preco = quote_float(args.preco)
    promocional = quote_float(args.preco_promocional, 0)
    preco_efetivo = promocional or preco
    total = args.custo_total
    if total is None:
        total = preco_efetivo + quote_float(args.frete) + quote_float(args.custo_extra)
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
    matches = list(PRODUTOS.glob(f"*/{produto_id}/produto.yaml"))
    if not matches:
        return None
    return read_yaml(matches[0], {})


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


@dataclass
class Ranked:
    produto_id: str
    quote: dict[str, str]
    product: dict[str, Any]
    axes: dict[str, float]
    score: float
    eliminations: list[str]


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


def risk_score(row: dict[str, str]) -> float:
    vendedor = (row.get("vendedor_tipo") or "").lower()
    garantia = (row.get("garantia_tipo") or "").lower()
    vendedor_score = {"oficial": 1.0, "fisica": 0.85, "terceiro": 0.65}.get(vendedor, 0.55)
    garantia_score = {"nacional": 1.0, "importada": 0.70, "vendedor": 0.55, "nenhuma": 0.10}.get(garantia, 0.45)
    meses = min(quote_float(row.get("garantia_meses")), 36) / 36
    score = (vendedor_score * 0.35) + (garantia_score * 0.40) + (meses * 0.25)
    if row.get("flag_suspeita"):
        score -= 0.2
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


def build_ranking(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    briefing, _ = load_frontmatter(project / "briefing.md")
    rows = read_quotes(project)
    latest = latest_quotes(rows)
    prefs = read_yaml(CONFIG / "preferencias.yaml", {})
    weights = prefs.get("score", {})

    candidates: list[Ranked] = []
    costs = [quote_float(row.get("custo_total")) for row in latest.values()]
    ratings = [quote_float(row.get("nota_ajustada")) for row in latest.values()]
    days = [quote_float(row.get("frete_prazo_dias"), 99) for row in latest.values() if row.get("frete_prazo_dias") not in {"", None}]

    for produto_id, row in latest.items():
        product = find_product(produto_id) or {"id": produto_id, "categoria": briefing.get("categoria"), "marca": ""}
        eliminations = gate_eliminations(row, product, briefing)
        axes = {
            "qualidade": normalize(ratings, quote_float(row.get("nota_ajustada"))),
            "valor": normalize(costs, quote_float(row.get("custo_total")), invert=True),
            "risco": risk_score(row),
            "aderencia": adherence_score(product),
            "conveniencia": normalize(days, quote_float(row.get("frete_prazo_dias"), 99), invert=True) if days else 0.5,
        }
        score = sum(axes[key] * quote_float(weights.get(key), 0) for key in axes) * 100
        if eliminations:
            score = 0
        candidates.append(Ranked(produto_id, row, product, axes, round(score, 1), eliminations))

    elegiveis = sorted([c for c in candidates if not c.eliminations], key=lambda c: c.score, reverse=True)
    cortados = sorted([c for c in candidates if c.eliminations], key=lambda c: c.produto_id)

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
            lines.extend(
                [
                    f"{idx}. {product_name} - {item.score:.1f}",
                    f"   {axes}",
                    f"   custo_total R$ {item.quote.get('custo_total')} / {item.quote.get('loja')} / {fonte_alerta}",
                    "",
                ]
            )
        lines.extend(["## Cortados pelos gates", ""])
        if not cortados:
            lines.append("Nenhum corte.")
        for item in cortados:
            product_name = item.product.get("nome") or item.produto_id
            lines.append(f"- {product_name}: {'; '.join(item.eliminations)}")
        lines.extend(
            [
                "",
                "## Observacoes",
                "",
                "- Score zerado significa corte por gate, nao produto ruim em absoluto.",
                "- Linha `fonte=web` nao fecha compra; confirme preco, estoque e frete antes de decidir.",
                "- Diferenca de ate 3 pontos entre finalistas deve ser tratada como empate tecnico.",
            ]
        )

    (project / "ranking.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(project / "ranking.md")


def ai_prompt(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    briefing_meta, briefing_body = load_frontmatter(project / "briefing.md")
    quotes = read_quotes(project)
    etapa = args.etapa
    common = f"""
Voce e meu assessor de compras. Use apenas como contexto as informacoes abaixo e deixe claro o que for inferencia.

Projeto: {project.name}
Categoria: {briefing_meta.get('categoria')}
Preco teto: {briefing_meta.get('preco_teto')}

Briefing:
{briefing_body.strip()}
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
    print(project / "decisao.md")


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
    p.set_defaults(func=decide)

    p = sub.add_parser("novo-veredito", help="cria arquivo de veredito pos-compra")
    p.add_argument("projeto")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=new_verdict)

    p = sub.add_parser("anotar", help="registra uma decisao intermediaria no processo.md")
    p.add_argument("projeto")
    p.add_argument("--etapa", required=True)
    p.add_argument("--decisao", required=True)
    p.add_argument("--porque", required=True)
    p.set_defaults(func=annotate)

    p = sub.add_parser("resumo", help="mostra um resumo rapido da compra")
    p.add_argument("projeto")
    p.set_defaults(func=summarize)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
