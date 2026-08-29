#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import hashlib
import html
import io
import itertools
import json
import math
import os
import re
import sys
import textwrap
import time
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

# O modulo csv grava CRLF por padrao. Como o repo e usado de varias maquinas,
# tudo aqui e gravado em LF, igual ao que o .gitattributes armazena.
CSV_EOL = "\n"

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
    "confirmacao",
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


def iso_datetime(value: str) -> str:
    """Valida `--data` na entrada.

    Data invalida era aceita e gravada. Como toda guarda de data depende de
    conseguir parsear `data_coleta`, uma cotacao com data podre nunca vencia,
    nunca entrava certo na comparacao de ancora e nao era reclamada por
    ninguem: escapava calada de todas as travas.
    """
    texto = (value or "").strip()
    for formato in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return reject_future(dt.datetime.strptime(texto, formato)).isoformat()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"data invalida: {value!r}. Use AAAA-MM-DD ou AAAA-MM-DDTHH:MM:SS."
    )


def real_number(value: str) -> float:
    """Valida numero na entrada do CLI.

    `type=float` do argparse aceita `NaN`, `inf` e `1e309`. Eles chegavam ate o
    `quote_float`, que os zerava em silencio: o CSV ficava com 0,0 e a validacao
    nao tinha o que reclamar, porque 0,0 e valido. O lixo tem que morrer na porta.
    """
    try:
        numero = float(str(value).replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"nao e numero: {value!r}") from None
    if math.isnan(numero):
        raise argparse.ArgumentTypeError(f"nao e numero: {value!r}")
    if math.isinf(numero):
        raise argparse.ArgumentTypeError(f"valor infinito: {value!r}")
    if numero < 0:
        raise argparse.ArgumentTypeError(f"valor negativo: {value!r}")
    return numero


def reject_future(momento: dt.datetime) -> dt.datetime:
    """Cotacao e observacao do passado. Nao existe preco coletado amanha."""
    if momento.date() > dt.date.today():
        raise argparse.ArgumentTypeError(
            f"data no futuro: {momento.date().isoformat()}. "
            "Cotacao e observacao de algo que voce viu, nao previsao."
        )
    return momento


def valid_collection_date(value: Any) -> bool:
    texto = str(value or "").strip()
    if not texto:
        return False
    try:
        dt.date.fromisoformat(texto[:10])
    except ValueError:
        return False
    return True


def today() -> str:
    return dt.date.today().isoformat()


def now_iso() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "item"


_TEMP_SEQ = itertools.count()
_REPLACE_RETRIES = 8
# Espera limitada para informar disputa; a liberacao por crash e do SO.
_LOCK_TIMEOUT_S = 30.0


@contextlib.contextmanager
def project_lock(project: Path):
    """Serializa comandos que escrevem no mesmo projeto.

    Escrita atomica garante que nenhum arquivo fique pela metade, mas nao que
    dois comandos simultaneos nao atrapalhem um ao outro: no Windows,
    `os.replace` falha se outro processo tiver o destino aberto, e a leitura
    de `processo.md` por um enquanto o outro grava perde atualizacao.

    O arquivo permanece no disco, mas a trava pertence ao descritor aberto.
    O proprio sistema operacional a libera se o processo terminar, inclusive
    por Ctrl+C ou encerramento forcado. Isso evita expirar uma trava legitima
    de um comando demorado e evita que um processo apague a trava de outro.
    """
    project.mkdir(parents=True, exist_ok=True)
    lock = project / ".central-compras.lock"
    limite = time.monotonic() + _LOCK_TIMEOUT_S
    arquivo = lock.open("a+b")
    arquivo.seek(0, os.SEEK_END)
    if arquivo.tell() == 0:
        arquivo.write(b"\0")
        arquivo.flush()
    adquirido = False
    while not adquirido:
        try:
            arquivo.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            adquirido = True
        except (BlockingIOError, OSError):
            if time.monotonic() > limite:
                arquivo.close()
                raise SystemExit(
                    f"Outro comando esta escrevendo em {project.name} "
                    f"(trava em {lock}).\nEspere terminar e tente novamente. "
                    "O arquivo de trava permanece no disco e nao deve ser apagado."
                )
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            arquivo.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
        finally:
            arquivo.close()


def atomic_write_text(path: Path, text: str) -> None:
    """Grava por arquivo temporario e troca de uma vez so.

    Abrir em modo `w` trunca o arquivo ANTES de escrever: um Ctrl+C, disco
    cheio ou excecao no meio deixava `cotacoes.csv` vazio e levava junto a
    serie historica inteira. `os.replace` e atomico no Windows e no POSIX.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Nome unico por processo: com um nome fixo, dois comandos rodando ao mesmo
    # tempo escreviam no MESMO temporario e um apagava o do outro, quebrando o
    # `os.replace` com PermissionError ou FileNotFoundError no Windows.
    temporario = path.with_name(f".{path.name}.{os.getpid()}.{next(_TEMP_SEQ)}.tmp")
    try:
        with temporario.open("w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        # No Windows, `os.replace` falha com PermissionError se outro processo
        # tiver o destino aberto, mesmo so para leitura. Com dois comandos
        # rodando ao mesmo tempo isso acontece o tempo todo, entao insiste um
        # pouco antes de desistir.
        for tentativa in range(_REPLACE_RETRIES):
            try:
                os.replace(temporario, path)
                break
            except PermissionError:
                if tentativa == _REPLACE_RETRIES - 1:
                    raise
                time.sleep(0.05 * (tentativa + 1))
    except BaseException:
        temporario.unlink(missing_ok=True)
        raise


def read_yaml(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
    except yaml.YAMLError as erro:
        detalhe = str(erro).splitlines()[0] if str(erro) else erro.__class__.__name__
        raise SystemExit(
            f"YAML invalido em {path}: {detalhe}\n"
            "Abra o arquivo e conserte a indentacao ou as aspas antes de continuar."
        ) from erro
    return default if loaded is None else loaded


def write_yaml(path: Path, data: Any) -> None:
    atomic_write_text(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def append_text(path: Path, text: str) -> None:
    """Anexa ao fim do arquivo, sem reler e reescrever.

    Ler-modificar-escrever aqui perdia dado em silencio sob concorrencia:
    medido, 20 licoes em paralelo viravam 7 gravadas e 13 sumidas, sem um
    unico erro. E o mesmo defeito que ja tinha sido corrigido no cotacoes.csv
    e que tinha sobrevivido na base de conhecimento, que e onde o aprendizado
    de verdade mora.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    separador = ""
    if path.exists() and path.stat().st_size:
        with path.open("rb") as f:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                separador = "\n"
    # Uma unica chamada de escrita em bytes, com O_APPEND: o sistema garante
    # atomicidade para escrita pequena. `f.write()` em modo texto pode virar
    # mais de uma escrita subjacente e ainda intercalar com outro processo.
    dados = (separador + text).encode("utf-8")
    descritor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        os.write(descritor, dados)
        os.fsync(descritor)
    finally:
        os.close(descritor)


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
    atomic_write_text(path, f"---\n{frontmatter}\n---\n\n{body.lstrip()}")


def project_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / value
    if not path.exists():
        candidates = sorted(p for p in PROJETOS.glob(f"*{value}*") if p.is_dir())
        if len(candidates) == 1:
            path = candidates[0]
        elif len(candidates) > 1:
            nomes = ", ".join(p.name for p in candidates)
            raise SystemExit(f"`{value}` casa com mais de um projeto: {nomes}. Seja especifico.")
    
    try:
        resolved_path = path.resolve()
        dentro = resolved_path.is_relative_to(PROJETOS.resolve())
    except Exception:
        dentro = False

    if not dentro or not path.exists() or not path.is_dir():
        disponiveis = ", ".join(p.name for p in project_dirs()) or "nenhum"
        raise SystemExit(f"Projeto nao encontrado: {value}. Existentes: {disponiveis}")
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
        numero = float(str(value).replace(",", "."))
    except ValueError:
        return default
    # NaN e infinito contaminam qualquer conta seguinte em silencio, porque
    # toda comparacao com NaN e falsa. `validar` reporta como erro; aqui eles
    # nao podem virar numero de ranking.
    if math.isnan(numero) or math.isinf(numero):
        return default
    return numero


def brl(value: Any, vazio: str = "-") -> str:
    """Dinheiro no formato brasileiro: 1234.5 -> `R$ 1.234,50`."""
    if value in {None, ""}:
        return vazio
    try:
        numero = float(str(value).replace(",", "."))
    except ValueError:
        return str(value)
    inteiro, _, centavos = f"{abs(numero):,.2f}".partition(".")
    inteiro = inteiro.replace(",", ".")
    sinal = "-" if numero < 0 else ""
    return f"{sinal}R$ {inteiro},{centavos}"


def quote_int(value: Any, default: int = 0) -> int:
    if value in {None, ""}:
        return default
    try:
        return int(float(str(value).replace(",", ".")))
    except ValueError:
        return default


_PREFS_CACHE: dict[str, Any] = {}


def preferences() -> dict[str, Any]:
    """Le preferencias.yaml uma vez por execucao."""
    if "data" not in _PREFS_CACHE:
        _PREFS_CACHE["data"] = read_yaml(CONFIG / "preferencias.yaml", {}) or {}
    return _PREFS_CACHE["data"]


def clamp01(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def quality_score(nota_ajustada: float) -> float:
    """Escala absoluta: 4.4 vale o mesmo em qualquer projeto.

    Antes era min-max dentro do projeto, o que dava 0,00 ao segundo colocado
    mesmo quando ele perdia por 0,2 ponto de nota.
    """
    cfg = (preferences().get("escala") or {}).get("qualidade") or {}
    piso = quote_float(cfg.get("nota_piso"), 3.8)
    teto = quote_float(cfg.get("nota_teto"), 5.0)
    if teto <= piso:
        return 0.5
    return clamp01((nota_ajustada - piso) / (teto - piso))


def value_score(custo: float, menor_custo: float) -> float:
    """Razao entre o mais barato e este. Custar o dobro vale 0,50, nao 0,00."""
    if custo <= 0 or menor_custo <= 0:
        return 0.0
    return clamp01(menor_custo / custo)


def convenience_score(prazo_dias: float | None) -> tuple[float, bool]:
    """Retorna (nota, tem_dado). Sem prazo informado o eixo e neutro e sinalizado."""
    if prazo_dias is None:
        return 0.5, False
    cfg = (preferences().get("escala") or {}).get("conveniencia") or {}
    otimo = quote_float(cfg.get("prazo_otimo_dias"), 2)
    ruim = quote_float(cfg.get("prazo_ruim_dias"), 30)
    if ruim <= otimo:
        return 0.5, True
    return clamp01((ruim - prazo_dias) / (ruim - otimo)), True


def adjusted_rating(nota: float, n: int, categoria: str | None = None) -> float:
    global_cfg = preferences().get("nota_bayesiana", {})
    cfg = global_cfg
    if categoria:
        cat_cfg = category_definition(categoria).get("nota_bayesiana") or {}
        cfg = {**global_cfg, **cat_cfg}
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


def compute_costs(
    preco_efetivo: float,
    frete: float,
    custo_extra: float,
    custo_total_override: float | None,
    custo_operacional_mensal: float,
    tco_meses: int,
    valor_revenda_estimado: float,
) -> tuple[float, float]:
    total = custo_total_override
    if total is None:
        total = preco_efetivo + frete + custo_extra
    total_rounded = round(float(total), 2)
    tco_total = quote_tco_total(
        total_rounded,
        custo_operacional_mensal,
        tco_meses,
        valor_revenda_estimado,
    )
    return total_rounded, tco_total


def leading_int(value: Any, default: int = 0) -> int:
    """`3 + 1 presencial` -> 3. Aceita config escrita em linguagem humana."""
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else default


def stop_rule(valor_estimado: float) -> dict[str, Any]:
    """Regra de parada da secao 7.5 do PRD, derivada da faixa de valor.

    Existia em preferencias.yaml desde o inicio e nunca era lida por ninguem.
    """
    regras = preferences().get("regras_parada") or {}
    faixas = []
    for nome, regra in regras.items():
        if not isinstance(regra, dict):
            continue
        teto = regra.get("valor_maximo")
        faixas.append((float("inf") if teto in {None, "", "null"} else quote_float(teto), nome, regra))
    if not faixas:
        return {}
    faixas.sort(key=lambda item: item[0])
    for teto, nome, regra in faixas:
        if valor_estimado <= teto:
            escolhida = (nome, regra)
            break
    else:
        escolhida = (faixas[-1][1], faixas[-1][2])
    nome, regra = escolhida
    return {
        "faixa": nome,
        "tempo_maximo": regra.get("tempo_maximo", ""),
        "candidatos": leading_int(regra.get("candidatos"), 0),
        "cotacoes_minimas_por_candidato": leading_int(regra.get("cotacoes_minimas_por_candidato"), 0),
        "cotacoes_minimas_texto": str(regra.get("cotacoes_minimas_por_candidato", "")),
    }


def stop_rule_status(project: Path) -> dict[str, Any]:
    """Compara a pesquisa real contra o orcamento de tempo/candidatos da faixa."""
    briefing, _ = load_frontmatter(project / "briefing.md")
    regra = stop_rule(quote_float(briefing.get("valor_estimado")))
    if not regra:
        return {}
    rows = read_quotes(project)
    cotacoes_por_produto: dict[str, int] = {}
    for row in rows:
        produto_id = row.get("produto_id")
        if produto_id:
            cotacoes_por_produto[produto_id] = cotacoes_por_produto.get(produto_id, 0) + 1
    # Candidato mapeado (`novo-produto`) conta mesmo sem cotacao ainda: sem
    # isso, 10 candidatos mapeados e zero cotacoes davam zero candidatos, e o
    # teto da faixa nunca disparava aviso.
    candidatos = project_candidate_ids(project) | set(cotacoes_por_produto)
    aberto_em = parse_dashboard_date(briefing.get("criado_em"))
    dias = (dt.date.today() - aberto_em).days if aberto_em else None
    faltando = sorted(
        produto_id
        for produto_id in candidatos
        if cotacoes_por_produto.get(produto_id, 0) < regra["cotacoes_minimas_por_candidato"]
    )
    return {
        **regra,
        "candidatos_atuais": len(candidatos),
        "dias_em_pesquisa": dias,
        "candidatos_excedidos": bool(regra["candidatos"] and len(candidatos) > regra["candidatos"]),
        "produtos_sem_cotacoes_suficientes": faltando,
    }


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
    regra = stop_rule(quote_float(args.valor_estimado))
    if regra:
        briefing = briefing.replace(
            "- Tempo maximo de pesquisa:\n- Numero maximo de candidatos:\n- Cotacoes minimas por candidato:",
            f"- Faixa de valor: {regra['faixa']}\n"
            f"- Tempo maximo de pesquisa: {regra['tempo_maximo']}\n"
            f"- Numero maximo de candidatos: {regra['candidatos']}\n"
            f"- Cotacoes minimas por candidato: {regra['cotacoes_minimas_texto']}",
            1,
        )
    atomic_write_text((path / "briefing.md"), briefing)
    atomic_write_text((path / "processo.md"), render_template("processo.md", data=today()))
    atomic_write_text(
        path / "01-definir-modelo.md",
        render_template("01-definir-modelo.md", necessidade=necessidade),
    )
    atomic_write_text((path / "ranking.md"), "# Ranking\n\nAinda nao gerado.\n")
    atomic_write_text((path / "decisao.md"), render_template("decisao.md"))
    atomic_write_text(path / "cotacoes.csv", ",".join(COTACOES_HEADER) + CSV_EOL)
    set_process_state(path, estado="pesquisando", proxima_acao="definir modelo/requisitos com ajuda da IA")
    print(path.relative_to(ROOT))
    print(f"Proximo comando: python scripts/central_compras.py prompt-ia projetos/{projeto_id} --etapa modelo")


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
    atomic_write_text((path / "pesquisa.md"), render_template("pesquisa.md"))
    append_timeline(project, "produto", f"Candidato registrado: {args.nome}", f"id={produto_id}")
    mark_steps(project, [3])
    print(path.relative_to(ROOT))


EXTRA_COLUMNS_KEY = "__extras__"


def raw_quotes_header(project: Path) -> list[str]:
    """Cabecalho exatamente como esta gravado no arquivo, sem uniao com o schema."""
    path = project / "cotacoes.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return [column for column in next(csv.reader(f), []) if column]


def quotes_header(project: Path) -> list[str]:
    """Cabecalho real do arquivo, unido ao schema atual.

    Colunas que o schema nao conhece sao preservadas no fim, nunca descartadas:
    cotacoes.csv e a serie historica e nao pode perder informacao escrita a mao.
    """
    path = project / "cotacoes.csv"
    header: list[str] = list(COTACOES_HEADER)
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as f:
            existing = next(csv.reader(f), [])
        for column in existing:
            if column and column not in header:
                header.append(column)
    return header


def read_quotes(project: Path) -> list[dict[str, str]]:
    path = project / "cotacoes.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, restkey=EXTRA_COLUMNS_KEY)
        rows = []
        for row in reader:
            # Linha com mais valores que colunas: guarda o excedente em vez de perder.
            leftovers = row.pop(EXTRA_COLUMNS_KEY, None)
            if leftovers:
                row[EXTRA_COLUMNS_KEY] = "|".join(str(value) for value in leftovers)
            rows.append({key: ("" if value is None else value) for key, value in row.items()})
        return rows


def append_quote(project: Path, row: dict[str, Any]) -> None:
    """Acrescenta UMA observacao ao fim do arquivo, sem reler nem reescrever.

    Reescrever o arquivo inteiro para acrescentar uma linha cria corrida de
    perda de atualizacao: dois `cotar` ao mesmo tempo leem a mesma base, cada um
    grava a sua versao, e a observacao de um some. Escrita atomica nao resolve
    isso, porque o problema nao e arquivo pela metade, e sim leitura velha.

    Anexar de verdade elimina a corrida e e o que "append-only" sempre quis
    dizer. Se o cabecalho do arquivo estiver defasado, para e manda migrar, em
    vez de reescrever tudo pelas costas.
    """
    path = project / "cotacoes.csv"
    header = raw_quotes_header(project)
    if not header:
        atomic_write_text(path, ",".join(COTACOES_HEADER) + CSV_EOL)
        header = list(COTACOES_HEADER)

    desconhecidas = [campo for campo in row if campo and campo != EXTRA_COLUMNS_KEY and campo not in header]
    if desconhecidas:
        raise SystemExit(
            f"cotacoes.csv nao tem as colunas: {', '.join(desconhecidas)}.\n"
            "Rode `migrar-cotacoes` para atualizar o cabecalho antes de cotar."
        )

    buffer = io.StringIO()
    csv.DictWriter(buffer, fieldnames=header, lineterminator=CSV_EOL).writerow(
        {campo: row.get(campo, "") for campo in header}
    )
    conteudo = path.read_text(encoding="utf-8") if path.exists() else ""
    separador = "" if not conteudo or conteudo.endswith(CSV_EOL) else CSV_EOL
    with path.open("a", encoding="utf-8", newline="") as f:
        f.write(separador + buffer.getvalue())
        f.flush()
        os.fsync(f.fileno())


def write_quotes(project: Path, rows: list[dict[str, Any]]) -> None:
    header = quotes_header(project)
    for row in rows:
        for key in row:
            if key and key != EXTRA_COLUMNS_KEY and key not in header:
                header.append(key)
    if any(row.get(EXTRA_COLUMNS_KEY) for row in rows) and EXTRA_COLUMNS_KEY not in header:
        header.append(EXTRA_COLUMNS_KEY)
    # Monta tudo em memoria e so entao troca o arquivo: a serie historica nunca
    # fica truncada no meio de uma gravacao.
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, lineterminator=CSV_EOL)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in header})
    atomic_write_text(project / "cotacoes.csv", buffer.getvalue())


def find_product_path(produto_id: str) -> Path | None:
    matches = list(PRODUTOS.glob(f"*/{produto_id}/produto.yaml"))
    return matches[0] if matches else None


def product_id_conflicts() -> list[str]:
    """Mesmo produto_id em categorias diferentes aponta para pastas diferentes.

    `find_product_path` devolveria a primeira encontrada, e a decisao poderia
    citar o produto errado. Melhor avisar antes.
    """
    seen: dict[str, list[str]] = {}
    for path in PRODUTOS.glob("*/*/produto.yaml"):
        seen.setdefault(path.parent.name, []).append(path.parent.parent.name)
    return [
        f"produto_id `{produto_id}` existe em mais de uma categoria: {', '.join(sorted(categorias))}"
        for produto_id, categorias in sorted(seen.items())
        if len(set(categorias)) > 1
    ]


def project_candidate_ids(project: Path) -> set[str]:
    """Todo produto_id mapeado para este projeto, com ou sem cotacao ainda.

    `novo-produto` grava `projeto` no `produto.yaml`. Antes disso, a regra de
    parada so via candidato quando a primeira cotacao chegava: com 10
    candidatos mapeados e zero cotacoes, ela contava zero.
    """
    ids: set[str] = set()
    for path in PRODUTOS.glob("*/*/produto.yaml"):
        dados = read_yaml(path, {})
        if dados.get("projeto") == project.name:
            ids.add(path.parent.name)
    return ids


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
    atomic_write_text(path, text)


def mark_steps(project: Path, steps: list[int]) -> None:
    path = project / "processo.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    for step in steps:
        text = re.sub(rf"(?m)^- \[ \] {step}\.", f"- [x] {step}.", text)
    atomic_write_text(path, text)


def add_quote(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    briefing, _ = load_frontmatter(project / "briefing.md")
    product = find_product(args.produto_id) or {}
    categoria = product.get("categoria") or briefing.get("categoria")
    rows = read_quotes(project)
    preco = quote_float(args.preco)
    promocional = quote_float(args.preco_promocional, 0)
    preco_efetivo = promocional or preco
    tco_meses = args.tco_meses if args.tco_meses is not None else category_tco_months(categoria)
    custo_total, tco_total = compute_costs(
        preco_efetivo,
        quote_float(args.frete),
        quote_float(args.custo_extra),
        args.custo_total,
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
        "custo_total": custo_total,
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
        "confirmacao": "coleta",
        "score": "",
    }
    append_quote(project, row)
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
    print(f"Cotacao adicionada: {args.produto_id} - {brl(row['custo_total'])}")


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
    atomic_write_text(path, text)


def find_product(produto_id: str) -> dict[str, Any] | None:
    path = find_product_path(produto_id)
    if not path:
        return None
    return read_yaml(path, {})


def latest_quotes(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    """Cotacao que representa cada produto no ranking.

    Manual vale mais que web porque foi conferida. Mas manual VENCIDA nao vale
    mais que uma observacao recente: preferir cegamente a manual fazia um preco
    de dois anos atras rankear no lugar do de hoje. Quando a manual venceu,
    usa a observacao mais recente e o ranking avisa que ela e estimativa.
    """
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("produto_id", ""), []).append(row)

    latest: dict[str, dict[str, str]] = {}
    for produto_id, values in grouped.items():
        por_data = sorted(values, key=lambda r: str(r.get("data_coleta") or ""))
        manual_no_prazo = [
            row for row in por_data if row.get("fonte") == "manual" and not quote_is_stale(row)
        ]
        if manual_no_prazo:
            latest[produto_id] = manual_no_prazo[-1]
            continue
        recentes = [row for row in por_data if not quote_is_stale(row)]
        if recentes:
            latest[produto_id] = recentes[-1]
            continue
        # Tudo vencido: fica a manual mais nova, ou a observacao mais nova.
        manual = [row for row in por_data if row.get("fonte") == "manual"]
        latest[produto_id] = (manual or por_data)[-1]
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


NUMERIC_FIELDS = [
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
    "garantia_meses",
]


def numeric_problems(row: dict[str, str]) -> list[str]:
    """Numero mal digitado vira 0.0 silenciosamente em quote_float.

    Aqui ele e detectado antes de virar `produto de graca` no ranking.
    """
    problems: list[str] = []
    for field in NUMERIC_FIELDS:
        raw = row.get(field)
        if raw in {None, ""}:
            continue
        try:
            valor = float(str(raw).replace(",", "."))
        except ValueError:
            problems.append(f"`{field}` nao e numero valido ({raw!r})")
            continue
        # `float("NaN")` e `float("inf")` sao aceitos pelo Python, e toda
        # comparacao com NaN e falsa: sem esta checagem eles escapavam de
        # `< 0` e viravam custo valido no ranking.
        if math.isnan(valor):
            problems.append(f"`{field}` nao e numero ({raw!r})")
            continue
        if math.isinf(valor):
            problems.append(f"`{field}` e infinito ({raw!r})")
            continue
        if valor < 0:
            problems.append(f"`{field}` negativo ({raw})")

    nota = quote_float(row.get("nota"))
    if nota and not (0 < nota <= 5):
        problems.append(f"`nota` fora da escala 0-5 ({row.get('nota')})")
    if nota and quote_int(row.get("n_avaliacoes")) == 0:
        problems.append("`nota` informada com `n_avaliacoes` zerado: nota sem volume nao e evidencia")

    preco = quote_float(row.get("preco"))
    promocional = quote_float(row.get("preco_promocional"))
    efetivo = promocional or preco
    esperado = round(efetivo + quote_float(row.get("frete_valor")) + quote_float(row.get("custo_extra")), 2)
    informado = quote_float(row.get("custo_total"))
    if efetivo and informado and abs(esperado - informado) > 0.05:
        problems.append(
            f"`custo_total` ({informado}) nao bate com preco+frete+extra ({esperado})"
        )
    if promocional and preco and promocional > preco:
        problems.append(f"`preco_promocional` ({promocional}) maior que `preco` ({preco})")
    return problems


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
        # So vale como defesa o que ja estava registrado ANTES desta coleta.
        # Comparar com cotacao posterior inverte a logica da serie historica.
        quando = str(row.get("data_coleta") or "")
        previous_prices = [
            quote_float(other.get("preco"))
            for other in rows
            if other is not row
            and other.get("produto_id") == row.get("produto_id")
            and str(other.get("data_coleta") or "") < quando
            and quote_float(other.get("preco"))
        ]
        # PRD secao 8: e ancora quando o preco "de" nunca apareceu nas cotacoes
        # anteriores. Se voce ja viu o produto bem mais barato que a ancora, a
        # ancora e inflada. Se as cotacoes antigas confirmam aquele patamar, o
        # desconto e real e nao deve ser sinalizado.
        if not previous_prices or min(previous_prices) < preco * 0.90:
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
        for problem in numeric_problems(row):
            errors.append(f"cotacoes.csv linha {index} ({row.get('produto_id')}): {problem}")
        futura = parse_dashboard_date(row.get("data_coleta"))
        if futura and futura > dt.date.today():
            errors.append(
                f"cotacoes.csv linha {index} ({row.get('produto_id')}): `data_coleta` no futuro "
                f"({futura.isoformat()}). Cotacao e observacao do passado, e data futura nunca vence."
            )
        if row.get("data_coleta") and not valid_collection_date(row.get("data_coleta")):
            errors.append(
                f"cotacoes.csv linha {index} ({row.get('produto_id')}): `data_coleta` "
                f"nao e data ISO ({row.get('data_coleta')!r}). Sem data valida a cotacao "
                "escapa das travas de frescor e da deteccao de preco ancora."
            )
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

    for produto_id, row in sorted(latest.items()):
        if quote_is_stale(row):
            idade = quote_age_days(row)
            limite = quote_expiry_days(row.get("fonte"))
            warnings.append(
                f"{produto_id}: cotacao usada no ranking tem {idade} dias "
                f"(limite {limite} para fonte={row.get('fonte')}). Recote antes de decidir."
            )

    regra = stop_rule_status(project)
    if regra:
        if regra["candidatos_excedidos"]:
            warnings.append(
                f"Regra de parada ({regra['faixa']}): {regra['candidatos_atuais']} candidatos para um teto de "
                f"{regra['candidatos']}. Pesquisar demais tambem custa caro."
            )
        if regra["produtos_sem_cotacoes_suficientes"]:
            warnings.append(
                f"Regra de parada ({regra['faixa']}): minimo de {regra['cotacoes_minimas_texto']} cotacao(oes) "
                f"por candidato. Abaixo disso: {', '.join(regra['produtos_sem_cotacoes_suficientes'])}."
            )

    errors.extend(product_id_conflicts())

    header_atual = raw_quotes_header(project)
    faltando_no_arquivo = [column for column in COTACOES_HEADER if header_atual and column not in header_atual]
    if faltando_no_arquivo:
        warnings.append(
            "cotacoes.csv esta num schema antigo, sem as colunas: "
            f"{', '.join(faltando_no_arquivo)}. Rode `migrar-cotacoes` para atualizar o cabecalho."
        )

    categoria_cfg = category_definition(categoria_projeto)
    extras_tipicos = categoria_cfg.get("custo_extra_tipico") or []
    if extras_tipicos and rows and all(quote_float(row.get("custo_extra")) == 0 for row in rows):
        warnings.append(
            f"Categoria `{categoria_projeto}` costuma ter custo extra obrigatorio "
            f"({', '.join(extras_tipicos)}) e nenhuma cotacao registrou `custo_extra`."
        )

    return errors, warnings


@dataclass
class ScoreBreakdown:
    weights: dict[str, float]
    included_axes: tuple[str, ...]
    missing_axes: tuple[str, ...]
    weighted_sum: float
    used_weight: float
    total_weight: float
    confidence: float
    score: float


def score_breakdown(
    axes: dict[str, float], missing_axes: list[str], weights: dict[str, Any]
) -> ScoreBreakdown:
    """Calcula score e confianca uma vez para todos os consumidores."""
    normalized_weights = {axis: quote_float(weights.get(axis), 0) for axis in axes}
    missing = tuple(axis for axis in axes if axis in missing_axes)
    included = tuple(axis for axis in axes if axis not in missing)
    total_weight = sum(normalized_weights.values())
    used_weight = sum(normalized_weights[axis] for axis in included)
    weighted_sum = sum(axes[axis] * normalized_weights[axis] for axis in included)
    confidence = used_weight / total_weight if total_weight else 0.0
    score = weighted_sum / used_weight * 100 if used_weight else 0.0
    return ScoreBreakdown(
        normalized_weights,
        included,
        missing,
        weighted_sum,
        used_weight,
        total_weight,
        round(confidence, 3),
        round(max(0.0, min(100.0, score)), 1),
    )


@dataclass
class Ranked:
    produto_id: str
    quote: dict[str, str]
    product: dict[str, Any]
    axes: dict[str, float]
    score: float
    eliminations: list[str]
    alerts: list[str]
    eixos_sem_dado: list[str]
    idade_dias: int | None
    vencida: bool
    confianca: float
    breakdown: ScoreBreakdown


def quote_age_days(row: dict[str, str], reference: dt.date | None = None) -> int | None:
    data = parse_dashboard_date(row.get("data_coleta"))
    if not data:
        return None
    return ((reference or dt.date.today()) - data).days


def quote_expiry_days(fonte: str | None) -> int:
    cfg = preferences().get("frescor") or {}
    if (fonte or "").lower() == "manual":
        return quote_int(cfg.get("validade_manual_dias"), 7) or 7
    return quote_int(cfg.get("validade_web_dias"), 14) or 14


def quote_is_stale(row: dict[str, str], reference: dt.date | None = None) -> bool:
    idade = quote_age_days(row, reference)
    if idade is None:
        return False
    return idade > quote_expiry_days(row.get("fonte"))


def preferred_store(loja: str | None) -> bool:
    """Loja da sua lista de preferidas, comparada sem acento nem caixa.

    `Mercado Livre` na config precisa casar com `MercadoLivre` no CSV.
    """
    if not loja:
        return False
    alvo = slugify(loja).replace("-", "")
    return any(
        slugify(str(nome)).replace("-", "") == alvo
        for nome in (preferences().get("lojas_preferidas") or [])
    )


def risk_parts(row: dict[str, str], alerts: list[str] | None = None) -> list[tuple[str, str, float, float]]:
    """Parcelas do eixo risco: (rotulo, o que foi lido, nota, peso).

    Devolver as parcelas em vez de so o total e o que permite `auditar` mostrar
    a conta inteira e cumprir o principio 3 do PRD.
    """
    cfg = (preferences().get("escala") or {}).get("risco") or {}
    tabela_vendedor = cfg.get("vendedor") or {}
    tabela_garantia = cfg.get("garantia") or {}

    vendedor = (row.get("vendedor_tipo") or "").lower()
    garantia = (row.get("garantia_tipo") or "").lower()
    meses_cheia = quote_float(cfg.get("garantia_meses_cheia"), 36) or 36
    meses = min(quote_float(row.get("garantia_meses")), meses_cheia) / meses_cheia
    preferida = preferred_store(row.get("loja"))

    return [
        (
            "vendedor",
            row.get("vendedor_tipo") or "nao informado",
            quote_float(tabela_vendedor.get(vendedor), quote_float(tabela_vendedor.get("desconhecido"), 0.55)),
            quote_float(cfg.get("peso_vendedor"), 0.30),
        ),
        (
            "garantia (tipo)",
            row.get("garantia_tipo") or "nao informado",
            quote_float(tabela_garantia.get(garantia), quote_float(tabela_garantia.get("desconhecido"), 0.45)),
            quote_float(cfg.get("peso_garantia_tipo"), 0.35),
        ),
        (
            "garantia (prazo)",
            f"{row.get('garantia_meses') or 0} de {int(meses_cheia)} meses",
            round(meses, 3),
            quote_float(cfg.get("peso_garantia_prazo"), 0.20),
        ),
        (
            "loja",
            f"{row.get('loja') or 'nao informada'}" + (" (preferida)" if preferida else " (fora da lista)"),
            quote_float(cfg.get("loja_preferida" if preferida else "loja_desconhecida"), 1.0 if preferida else 0.70),
            quote_float(cfg.get("peso_loja"), 0.15),
        ),
    ]


def risk_penalty(row: dict[str, str], alerts: list[str] | None = None) -> tuple[int, float]:
    cfg = (preferences().get("escala") or {}).get("risco") or {}
    quantidade = len(set(alerts or ([] if not row.get("flag_suspeita") else [row.get("flag_suspeita")])))
    penalidade = min(
        quote_float(cfg.get("penalidade_maxima"), 0.35),
        quantidade * quote_float(cfg.get("penalidade_por_alerta"), 0.15),
    )
    return quantidade, round(penalidade, 3)


def risk_score(row: dict[str, str], alerts: list[str] | None = None) -> float:
    score = sum(nota * peso for _, _, nota, peso in risk_parts(row, alerts))
    score -= risk_penalty(row, alerts)[1]
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
    prefs = preferences()
    categoria = product.get("categoria") or briefing.get("categoria") or "generico"
    gate = (categories.get(categoria) or categories.get("generico") or {}).get("gate", {})
    eliminations: list[str] = []

    if product.get("estado") == "descartado":
        motivo = product.get("descartado_porque") or "motivo nao registrado"
        eliminations.append(f"produto descartado ({motivo})")

    # Produto sem custo utilizavel nao e candidato: era tratado como "eixo valor
    # sem dado" e seguia elegivel, com score alto sobre os eixos restantes.
    if quote_float(row.get("custo_total")) <= 0:
        eliminations.append("cotacao sem custo utilizavel (custo_total zerado ou invalido)")

    # O teto do proprio produto e mais especifico que o do briefing e vence
    # quando for menor. Era aceito pelo CLI, gravado no produto.yaml e ignorado
    # aqui: campo que o usuario preenche e que nao fazia nada.
    tetos = [
        (quote_float(valor), origem)
        for valor, origem in [(briefing.get("preco_teto"), "briefing"), (product.get("preco_teto"), "produto")]
        if valor not in {None, "null", ""} and quote_float(valor) > 0
    ]
    if tetos:
        preco_teto, origem_teto = min(tetos)
        if quote_float(row.get("custo_total")) > preco_teto:
            eliminations.append(
                f"custo_total acima do preco_teto do {origem_teto} ({row.get('custo_total')} > {preco_teto})"
            )

    nota_minima = gate.get("nota_minima_ajustada")
    if nota_minima is not None:
        # Recalcula em vez de usar o valor congelado no CSV: se os pesos da nota
        # bayesiana mudarem em preferencias.yaml, o gate acompanha.
        atual = current_adjusted_rating(row, categoria)
        if atual < quote_float(nota_minima):
            eliminations.append(f"nota_ajustada abaixo do gate ({atual} < {nota_minima})")

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

    if gate.get("exige_rede_assistencia"):
        atributos = product.get("atributos") or {}
        reqs = product.get("requisitos_atendidos") or {}
        declarado = atributos.get("rede_assistencia", reqs.get("rede_assistencia"))
        if declarado in {None, ""}:
            eliminations.append("categoria exige rede de assistencia e o produto nao declara `rede_assistencia`")
        elif declarado is False or str(declarado).strip().lower() in {"false", "nao", "nenhuma", "no"}:
            eliminations.append("sem rede de assistencia")

    marca = product.get("marca")
    if marca and marca in (prefs.get("marcas_vetadas") or []):
        eliminations.append(f"marca vetada ({marca})")

    for key, value in (product.get("requisitos_atendidos") or {}).items():
        if value is False:
            eliminations.append(f"requisito obrigatorio nao atendido: {key}")

    return eliminations


def waiting_gap(product: dict[str, Any], quote: dict[str, str]) -> str:
    """Aviso para produto em `aguardando_preco` que ainda nao chegou ao alvo.

    O estado quer dizer "aprovado, mas decidi esperar preco melhor". Ele
    aparecia liderando o ranking sem nenhuma marca, como se estivesse pronto.
    """
    if (product or {}).get("estado") != "aguardando_preco":
        return ""
    alvo = quote_float((product or {}).get("preco_alvo"))
    atual = quote_float(quote.get("custo_total"))
    desde = (product or {}).get("aguardando_preco_desde") or ""
    if alvo and atual and atual > alvo:
        return (
            f"aguardando preco desde {desde}: faltam {brl(round(atual - alvo, 2))} "
            f"para o alvo de {brl(alvo)}. Voce decidiu esperar, nao comprar."
        )
    if alvo and atual and atual <= alvo:
        return f"AGUARDANDO PRECO E O ALVO FOI ATINGIDO: {brl(atual)} <= {brl(alvo)}. Hora de reavaliar."
    return f"aguardando preco desde {desde} (sem preco_alvo definido)."


def current_adjusted_rating(row: dict[str, str], categoria: str | None = None) -> float:
    """Nota ajustada recalculada agora, a partir de nota + n_avaliacoes."""
    nota = quote_float(row.get("nota"))
    if not nota:
        return 0.0
    return adjusted_rating(nota, quote_int(row.get("n_avaliacoes")), categoria)


def minimum_confidence(briefing: dict[str, Any]) -> float:
    """Confianca minima para fechar, mais exigente em compra cara.

    Nao existe uma segunda tabela de criticidade porque o peso do eixo ja e a
    criticidade dele: faltar `qualidade` (0,30) derruba a confianca tres vezes
    mais que faltar `conveniencia` (0,10).
    """
    cfg = preferences().get("confianca_minima_para_decidir")
    if not isinstance(cfg, dict):
        return quote_float(cfg, 0.80) or 0.80
    padrao = quote_float(cfg.get("padrao"), 0.80) or 0.80
    if quote_float(briefing.get("valor_estimado")) > 20000:
        return quote_float(cfg.get("acima_de_20000"), padrao) or padrao
    return padrao


def value_field_for(briefing: dict[str, Any]) -> tuple[str, str]:
    """Qual campo o eixo valor compara: custo de etiqueta ou TCO.

    Uma funcao so, usada pelo ranking e pela memoria de calculo, para os dois
    nunca divergirem de novo.
    """
    categoria = briefing.get("categoria") or "generico"
    usa_tco = bool(category_tco_months(categoria) or quote_float(briefing.get("valor_estimado")) > 20000)
    return ("tco_total", "TCO") if usa_tco else ("custo_total", "custo total")


def compute_ranking(project: Path) -> tuple[list[Ranked], list[Ranked]]:
    briefing, _ = load_frontmatter(project / "briefing.md")
    rows = read_quotes(project)
    latest = latest_quotes(rows)
    weights = preferences().get("score", {})
    pre_candidates: list[tuple[str, dict[str, str], dict[str, Any], list[str], list[str]]] = []
    for produto_id, row in latest.items():
        product = find_product(produto_id) or {"id": produto_id, "categoria": briefing.get("categoria"), "marca": ""}
        eliminations = gate_eliminations(row, product, briefing)
        alerts = manipulation_alerts(rows, row)
        pre_candidates.append((produto_id, row, product, eliminations, alerts))

    value_field, _ = value_field_for(briefing)

    def cost_of(row: dict[str, str]) -> float:
        return quote_float(row.get(value_field) or row.get("custo_total"))

    # O eixo valor e relativo ao mais barato que passou nos gates; se ninguem
    # passou, usa o conjunto inteiro para nao dividir por zero.
    scoring_pool = [item for item in pre_candidates if not item[3]] or pre_candidates
    positive_costs = [cost_of(row) for _, row, _, _, _ in scoring_pool if cost_of(row) > 0]
    menor_custo = min(positive_costs) if positive_costs else 0.0

    candidates: list[Ranked] = []
    for produto_id, row, product, eliminations, alerts in pre_candidates:
        sem_dado: list[str] = []
        categoria_produto = product.get("categoria") or briefing.get("categoria") or "generico"
        sem_frete = bool(category_definition(categoria_produto).get("sem_frete"))

        nota_ajustada = current_adjusted_rating(row, categoria_produto)
        if not nota_ajustada:
            sem_dado.append("qualidade")

        prazo_raw = row.get("frete_prazo_dias")
        prazo = quote_float(prazo_raw) if prazo_raw not in {"", None} else None
        conveniencia, tem_prazo = convenience_score(prazo)
        # Categoria sem frete real (ex.: carro): o eixo nao entra na conta,
        # nunca "sem dado" temporario que travaria a confianca para sempre.
        if sem_frete or not tem_prazo:
            sem_dado.append("conveniencia")

        if not (product.get("requisitos_atendidos") or {}):
            sem_dado.append("aderencia")

        if cost_of(row) <= 0:
            sem_dado.append("valor")

        axes = {
            "qualidade": quality_score(nota_ajustada),
            "valor": value_score(cost_of(row), menor_custo),
            "risco": risk_score(row, alerts),
            "aderencia": adherence_score(product),
        }
        if not sem_frete:
            axes["conveniencia"] = conveniencia

        # Eixo sem dado sai da conta em vez de entrar como 0,50 neutro, e os
        # pesos restantes sao renormalizados. Com o 0,50, "nao informei o prazo"
        # valia 5 pontos a mais que "o prazo e pessimo e eu sei disso": o score
        # premiava o silencio. Agora o score mede o que se sabe, e `confianca`
        # diz quanto do peso total esta de fato apoiado em dado.
        breakdown = score_breakdown(axes, sem_dado, weights)
        score = breakdown.score
        if eliminations:
            score = 0
        candidates.append(
            Ranked(
                produto_id,
                row,
                product,
                axes,
                score,
                eliminations,
                alerts,
                sem_dado,
                quote_age_days(row),
                quote_is_stale(row),
                breakdown.confidence,
                breakdown,
            )
        )

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
        "confianca",
        "idade_dias",
        "cotacao_vencida",
        "eixos_sem_dado",
        "custo_total",
        "custo_operacional_mensal",
        "tco_meses",
        "valor_revenda_estimado",
        "tco_total",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator=CSV_EOL)
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
                "confianca": item.confianca,
                "idade_dias": "" if item.idade_dias is None else item.idade_dias,
                "cotacao_vencida": "sim" if item.vencida else "nao",
                "eixos_sem_dado": "; ".join(item.eixos_sem_dado),
                "custo_total": item.quote.get("custo_total"),
                "custo_operacional_mensal": item.quote.get("custo_operacional_mensal"),
                "tco_meses": item.quote.get("tco_meses"),
                "valor_revenda_estimado": item.quote.get("valor_revenda_estimado"),
                "tco_total": item.quote.get("tco_total"),
            }
        )
    atomic_write_text(project / "ranking.csv", buffer.getvalue())


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
            # Eixo fora da conta nao pode exibir numero: mostrar `0.50` para algo
            # que nao entrou no score faz o leitor somar errado de cabeca.
            axes = " · ".join(
                f"{key} --" if key in item.eixos_sem_dado else f"{key} {value:.2f}"
                for key, value in item.axes.items()
            )
            fonte_alerta = "confirmada manualmente" if item.quote.get("fonte") == "manual" else "estimativa web"
            tco_line = ""
            if item.quote.get("tco_total") and quote_float(item.quote.get("tco_total")) != quote_float(item.quote.get("custo_total")):
                tco_line = f"   TCO {item.quote.get('tco_meses')} meses {brl(item.quote.get('tco_total'))}"
            lines.extend(
                [
                    f"{idx}. {product_name} - {item.score:.1f}",
                    f"   {axes}",
                    f"   custo total {brl(item.quote.get('custo_total'))} / {item.quote.get('loja')} / {fonte_alerta}",
                ]
            )
            if tco_line:
                lines.append(tco_line)
            if idx > 1 and elegiveis[0].score - item.score <= 3:
                lines.append("   empate tecnico com o lider: decida pelo criterio humano, nao pelo numero")
            if item.eixos_sem_dado:
                lines.append(
                    f"   confianca {item.confianca:.0%} - sem dado em: {', '.join(item.eixos_sem_dado)}. "
                    "Esses eixos ficaram FORA da conta; o score mede so o que se sabe."
                )
            if item.vencida:
                lines.append(
                    f"   cotacao vencida: {item.idade_dias} dias desde a coleta "
                    f"(limite {quote_expiry_days(item.quote.get('fonte'))} para fonte={item.quote.get('fonte')}); recote antes de decidir"
                )
            espera = waiting_gap(item.product, item.quote)
            if espera:
                lines.append(f"   {espera}")
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
                "- `confianca` e a fracao do peso do score apoiada em dado real. Score 80 com "
                "confianca 60% nao e comparavel com score 80 com confianca 100%.",
                "- Linha `fonte=web` nao fecha compra; confirme preco, estoque e frete antes de decidir.",
                "- Diferenca de ate 3 pontos entre finalistas deve ser tratada como empate tecnico.",
                "- `ranking.csv` e derivado e pode ser sobrescrito; `cotacoes.csv` preserva a serie historica.",
                "",
                "## Como o score foi montado",
                "",
                "- `qualidade`: nota ajustada em escala absoluta "
                f"({quote_float((preferences().get('escala') or {}).get('qualidade', {}).get('nota_piso'), 3.8)} = 0,00 / "
                f"{quote_float((preferences().get('escala') or {}).get('qualidade', {}).get('nota_teto'), 5.0)} = 1,00).",
                "- `valor`: razao entre o custo do mais barato elegivel e o custo deste. Custar o dobro vale 0,50.",
                "- `risco`: vendedor, tipo e prazo de garantia, menos penalidade por alerta de manipulacao.",
                "- `aderencia`: percentual de requisitos do briefing atendidos pelo produto.",
                "- `conveniencia`: prazo de frete em escala absoluta.",
                "- O score e comparativo dentro do projeto: qualidade e conveniencia usam escalas fixas, "
                "mas valor depende do candidato elegivel mais barato. Compare candidatos da mesma compra.",
            ]
        )

    atomic_write_text((project / "ranking.md"), "\n".join(lines) + "\n")
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


def price_history(project: Path, produto_id: str | None = None) -> list[dict[str, Any]]:
    """Serie historica de custo por produto. E ela que desmascara preco ancora.

    Usa a MESMA base de comparacao do ranking. Mostrar preco de etiqueta aqui
    enquanto o ranking compara por TCO faz a serie contar outra historia: foi
    o defeito que a auditoria achou no `auditar` e que tinha sobrevivido aqui.
    """
    briefing, _ = load_frontmatter(project / "briefing.md")
    campo_valor, rotulo_valor = value_field_for(briefing)

    def custo_de(row: dict[str, str]) -> float:
        return quote_float(row.get(campo_valor) or row.get("custo_total"))

    rows = read_quotes(project)
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        pid = row.get("produto_id") or ""
        if produto_id and pid != produto_id:
            continue
        grouped.setdefault(pid, []).append(row)

    series: list[dict[str, Any]] = []
    for pid, values in sorted(grouped.items()):
        values = sorted(values, key=lambda r: str(r.get("data_coleta") or ""))
        custos = [custo_de(r) for r in values if custo_de(r) > 0]
        if not custos:
            continue
        ordenado = sorted(custos)
        meio = len(ordenado) // 2
        mediana = ordenado[meio] if len(ordenado) % 2 else round((ordenado[meio - 1] + ordenado[meio]) / 2, 2)
        atual = custos[-1]
        product = find_product(pid) or {}
        series.append(
            {
                "produto_id": pid,
                "nome": product.get("nome") or pid,
                "observacoes": len(custos),
                "primeiro": custos[0],
                "atual": atual,
                "minimo": min(custos),
                "maximo": max(custos),
                "mediana": mediana,
                "variacao_pct": round(((atual - custos[0]) / custos[0]) * 100, 1) if custos[0] else 0.0,
                "desconto_real_vs_mediana_pct": round(((mediana - atual) / mediana) * 100, 1) if mediana else 0.0,
                "base": rotulo_valor,
                "primeira_coleta": values[0].get("data_coleta", ""),
                "ultima_coleta": values[-1].get("data_coleta", ""),
                "pontos": [
                    {
                        "data": r.get("data_coleta", ""),
                        "custo": custo_de(r),
                        "loja": r.get("loja", ""),
                        "fonte": r.get("fonte", ""),
                    }
                    for r in values
                    if custo_de(r) > 0
                ],
            }
        )
    return series


def show_history(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    series = price_history(project, args.produto_id)
    if not series:
        print("Sem serie historica de custo neste projeto.")
        return
    base = series[0]["base"]
    lines = [
        "# Historico de preco", "", f"Gerado em {now_iso()}.", "",
        f"Base de comparacao: **{base}** (a mesma do ranking).", "",
    ]
    for item in series:
        lines.append(f"## {item['nome']}")
        lines.append("")
        lines.append(
            f"- Observacoes: {item['observacoes']} "
            f"({item['primeira_coleta'][:10]} ate {item['ultima_coleta'][:10]})"
        )
        lines.append(
            f"- {item['base']}: atual {brl(item['atual'])} / minimo {brl(item['minimo'])} / "
            f"mediana {brl(item['mediana'])} / maximo {brl(item['maximo'])}"
        )
        lines.append(f"- Variacao desde a primeira coleta: {item['variacao_pct']}%")
        if item["observacoes"] < 2:
            lines.append(
                "- So ha uma observacao. Sem serie nao da para saber se um `desconto` anunciado e real: "
                "colete de novo em alguns dias."
            )
        else:
            lines.append(
                f"- Desconto real contra a propria mediana: {item['desconto_real_vs_mediana_pct']}%"
            )
        lines.append("")
        lines.append("| Data | Custo total | Loja | Fonte |")
        lines.append("|---|---:|---|---|")
        for ponto in item["pontos"]:
            lines.append(f"| {ponto['data']} | {brl(ponto['custo'])} | {ponto['loja']} | {ponto['fonte']} |")
        lines.append("")
    path = project / "historico.md"
    atomic_write_text(path, "\n".join(lines) + "\n")
    print(path)
    for item in series:
        print(
            f"{item['nome']} [{item['base']}]: {item['observacoes']} obs / atual {brl(item['atual'])} / "
            f"mediana {brl(item['mediana'])} / variacao {item['variacao_pct']}%"
        )


def promote_quote(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    briefing, _ = load_frontmatter(project / "briefing.md")
    product = find_product(args.produto_id) or {}
    categoria = product.get("categoria") or briefing.get("categoria")
    rows = read_quotes(project)
    base = latest_quote_for_product(rows, args.produto_id, fonte=args.fonte_base)
    if not base:
        raise SystemExit(f"Nenhuma cotacao {args.fonte_base} encontrada para {args.produto_id}")

    # `manual` significa "eu abri o site e conferi agora". Promover sem informar
    # nada copiava o preco antigo com a data de hoje e carimbava de conferido:
    # o pior tipo de mentira que este sistema pode contar para si mesmo.
    confirmados = [
        campo
        for campo, valor in {
            "--preco": args.preco,
            "--custo-total": args.custo_total,
            "--frete": args.frete,
            "--vendedor": args.vendedor,
            "--link": args.link,
            "--garantia-meses": args.garantia_meses,
        }.items()
        if valor is not None
    ]
    if not confirmados and not args.sem_alteracao:
        raise SystemExit(
            "Promover para `manual` exige dizer o que voce conferiu no site agora.\n"
            "Informe ao menos um entre --preco, --custo-total, --frete, --vendedor, "
            "--link ou --garantia-meses.\n"
            "Se conferiu e estava tudo igual ao que ja estava registrado, "
            "use --sem-alteracao para declarar isso explicitamente."
        )

    row = dict(base)
    row["data_coleta"] = args.data or now_iso()
    row["fonte"] = "manual"
    # Sem isto, a linha promovida sem alteracao ficava indistinguivel de uma
    # conferencia em que algo mudou: eu exigia a declaracao e nao a registrava.
    row["confirmacao"] = (
        "reconfirmado sem alteracao" if not confirmados
        else "conferido: " + ", ".join(c.lstrip("-") for c in confirmados)
    )
    # A suspeita da linha web se referia ao que se via na pesquisa. A conferencia
    # manual e uma observacao nova: ou voce reafirma a suspeita com --flag-suspeita,
    # ou ela nao se aplica. Herdar calado congela um alerta que talvez ja morreu.
    row["flag_suspeita"] = ""
    row["score"] = ""
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
    tco_meses = row.get("tco_meses")
    if not tco_meses:
        tco_meses = category_tco_months(categoria) or 0

    custo_total, tco_total = compute_costs(
        preco_efetivo,
        quote_float(row.get("frete_valor")),
        quote_float(row.get("custo_extra")),
        args.custo_total,
        quote_float(row.get("custo_operacional_mensal")),
        quote_int(tco_meses),
        quote_float(row.get("valor_revenda_estimado")),
    )
    row["custo_total"] = custo_total
    row["tco_meses"] = tco_meses or ""
    if args.tco_total is not None:
        row["tco_total"] = args.tco_total
    else:
        row["tco_total"] = tco_total
    row["nota_ajustada"] = adjusted_rating(quote_float(row.get("nota")), quote_int(row.get("n_avaliacoes"))) if quote_float(row.get("nota")) else ""
    row["score"] = ""

    append_quote(project, row)
    append_timeline(
        project,
        "cotacao-manual",
        f"Cotacao manual confirmada para {args.produto_id}",
        f"{row.get('loja')} / custo_total={row.get('custo_total')}",
    )
    mark_steps(project, [7])
    set_process_state(project, proxima_acao="gerar ranking com a cotacao manual e registrar decisao")
    print(f"Cotacao manual adicionada: {args.produto_id} - {brl(row.get('custo_total'))}")


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
    atomic_write_text(report, "\n".join(md_lines) + "\n")
    csv_path = BASE / "aguardando-preco.csv"
    fields = ["produto_id", "nome", "categoria", "projeto", "preco_atual", "preco_alvo", "preco_teto", "distancia_ate_alvo", "desde", "porque"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator=CSV_EOL)
    writer.writeheader()
    writer.writerows(rows)
    atomic_write_text(csv_path, buffer.getvalue())
    print(report.relative_to(ROOT))
    print(f"Itens: {len(rows)}")


def decision_briefing(project: Path) -> str:
    """Estado da pesquisa em texto legivel, para o prompt de decisao.

    Antes o prompt despejava o `repr` da lista de cotacoes: campo vazio,
    aspas e chaves ocupando espaco sem dizer nada, e sem o ranking. A IA
    precisa ver o score aberto, o corte e o alerta, nao o CSV cru.
    """
    elegiveis, cortados = compute_ranking(project)
    partes: list[str] = []

    if elegiveis:
        partes.append("Finalistas (score aberto, comparativo dentro deste projeto, 0-100):")
        for posicao, item in enumerate(elegiveis, 1):
            eixos = " · ".join(
                f"{k} --" if k in item.eixos_sem_dado else f"{k} {v:.2f}"
                for k, v in item.axes.items()
            )
            linha = (
                f"{posicao}. {item.product.get('nome') or item.produto_id} - {item.score:.1f}\n"
                f"   {eixos}\n"
                f"   {brl(item.quote.get('custo_total'))} em {item.quote.get('loja')} "
                f"({item.quote.get('vendedor') or 'vendedor nao confirmado'}, "
                f"garantia {item.quote.get('garantia_meses') or '?'} meses "
                f"{item.quote.get('garantia_tipo')}), fonte={item.quote.get('fonte')}"
            )
            if item.eixos_sem_dado:
                linha += (
                    f"\n   SEM DADO em {', '.join(item.eixos_sem_dado)}: esses eixos ficaram FORA "
                    f"da conta e o score foi renormalizado. Confianca {item.confianca:.0%}."
                )
            if item.vencida:
                linha += f"\n   COTACAO VENCIDA: {item.idade_dias} dias desde a coleta"
            if item.alerts:
                linha += f"\n   ALERTAS: {', '.join(item.alerts)}"
            partes.append(linha)
        if len(elegiveis) > 1 and elegiveis[0].score - elegiveis[1].score <= 3:
            partes.append(
                "ATENCAO: os dois primeiros estao dentro de 3 pontos. Isso e empate tecnico. "
                "Nao invente precisao: diga qual criterio humano deveria desempatar."
            )
    else:
        partes.append("Nenhum candidato passou pelos gates.")

    if cortados:
        partes.append("\nCortados pelos gates (nao entram no ranking):")
        for item in cortados:
            partes.append(
                f"- {item.product.get('nome') or item.produto_id}: {'; '.join(item.eliminations)}"
            )

    serie = price_history(project)
    com_serie = [item for item in serie if item["observacoes"] > 1]
    if com_serie:
        partes.append("\nSerie historica de custo:")
        for item in com_serie:
            partes.append(
                f"- {item['nome']}: atual {brl(item['atual'])}, mediana {brl(item['mediana'])}, "
                f"minimo {brl(item['minimo'])}, variacao {item['variacao_pct']}%"
            )
    if len(serie) > len(com_serie):
        partes.append(
            "\nOs demais produtos tem uma unica observacao de preco: nao afirme que "
            "algum desconto e real, porque nao ha serie para comparar."
        )

    regra = stop_rule_status(project)
    if regra:
        partes.append(
            f"\nRegra de parada da faixa ({regra['faixa']}): ate {regra['tempo_maximo']}, "
            f"{regra['candidatos']} candidatos, {regra['cotacoes_minimas_texto']} cotacao(oes) cada. "
            f"Hoje: {regra['candidatos_atuais']} candidatos"
            + (f", {regra['dias_em_pesquisa']} dias em pesquisa." if regra["dias_em_pesquisa"] is not None else ".")
        )

    manual = {row.get("produto_id") for row in read_quotes(project) if row.get("fonte") == "manual"}
    if not manual:
        partes.append(
            "\nNenhum produto tem cotacao manual ainda. Toda a comparacao esta sobre estimativa "
            "web, entao a decisao so pode ser provisoria."
        )
    return "\n".join(partes)


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
Situacao atual da pesquisa:
{decision_briefing(project)}

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

    # Principio 2 do PRD: gate antes de score. Ele valia no ranking e era
    # ignorado exatamente no momento que importa, a compra.
    briefing_meta, _ = load_frontmatter(project / "briefing.md")
    cortes = gate_eliminations(quote, product, briefing_meta)
    if cortes and not args.permitir_cortado:
        raise SystemExit(
            f"{args.produto_id} foi cortado pelos gates e nao deveria ser comprado:\n"
            + "\n".join(f"  - {motivo}" for motivo in cortes)
            + "\nUse --permitir-cortado se for uma excecao consciente, "
            "ou ajuste o gate da categoria se ele esta calibrado errado."
        )

    if quote_is_stale(quote) and not args.permitir_vencida:
        raise SystemExit(
            f"A cotacao escolhida tem {quote_age_days(quote)} dias "
            f"(limite {quote_expiry_days(quote.get('fonte'))} para fonte={quote.get('fonte')}). "
            "Recote antes de fechar, ou use --permitir-vencida para registrar assim mesmo."
        )

    if product.get("estado") == "aguardando_preco" and not args.permitir_aguardando:
        alvo = quote_float(product.get("preco_alvo"))
        atual = quote_float(quote.get("custo_total"))
        if alvo and atual > alvo:
            raise SystemExit(
                f"{args.produto_id} esta em `aguardando_preco` e o custo atual ({brl(atual)}) "
                f"ainda esta acima do seu preco alvo ({brl(alvo)}).\n"
                "Voce mesmo decidiu esperar. Use --permitir-aguardando se mudou de ideia, "
                "ou `aguardar-preco` de novo com outro alvo."
            )

    perdedores = []
    for value in args.perdedores or []:
        if ":" not in value:
            raise SystemExit("Use --perdedores produto_id: motivo")
        produto, motivo = value.split(":", 1)
        produto, motivo = produto.strip(), motivo.strip()
        if not motivo:
            raise SystemExit(f"Perdedor sem motivo: {produto}. O `nao escolhi` vale mais que o `escolhi`.")
        if produto == args.produto_id:
            raise SystemExit(
                f"`{produto}` e o produto escolhido; ele nao pode constar como perdedor."
            )
        if not find_product(produto):
            raise SystemExit(f"Perdedor nao existe em `produtos/`: {produto}. Confira o produto_id.")
        perdedores.append((produto, motivo))

    # Principio 4 do PRD: registrar por que o segundo colocado perdeu e o que
    # impede refazer a pesquisa inteira daqui a dois anos.
    outros = sorted(set(latest_quotes(read_quotes(project))) - {args.produto_id})
    registrados = {produto for produto, _ in perdedores}
    faltando = [produto for produto in outros if produto not in registrados]
    if args.sem_perdedores and outros:
        raise SystemExit(
            "--sem-perdedores declara que nao houve concorrente, mas estes tem cotacao "
            "neste projeto: " + ", ".join(outros) + ".\n"
            "Registre o motivo da derrota de cada um com --perdedores."
        )
    if faltando and not args.sem_perdedores:
        raise SystemExit(
            "Faltou registrar por que estes candidatos perderam: "
            + ", ".join(faltando)
            + "\nUse --perdedores \"produto_id: motivo\" para cada um, "
            "ou --sem-perdedores se realmente nao houve concorrente."
        )

    # Trava mais branda de todas, entao vem por ultimo: as anteriores dizem
    # respeito a regra do sistema; esta so diz que falta dado.
    minima = minimum_confidence(briefing_meta)
    elegiveis, cortados = compute_ranking(project)
    ranqueado = next(
        (item for item in [*elegiveis, *cortados] if item.produto_id == args.produto_id),
        None,
    )
    obrigatorios = [
        eixo for eixo in (preferences().get("eixos_obrigatorios_para_decidir") or [])
        if ranqueado and eixo in ranqueado.eixos_sem_dado
    ]
    if obrigatorios and not args.permitir_incompleto:
        raise SystemExit(
            f"Faltam eixos que nao podem faltar numa decisao final: {', '.join(obrigatorios)}.\n"
            "Nenhum limite de confianca cobre isso: sem esses dados a comparacao nao existe.\n"
            "Preencha, ou use --permitir-incompleto se for de proposito."
        )
    if ranqueado and ranqueado.confianca < minima and not args.permitir_incompleto:
        raise SystemExit(
            f"Confianca de apenas {ranqueado.confianca:.0%} no score de {args.produto_id} "
            f"(minimo {minima:.0%}).\n"
            f"Sem dado em: {', '.join(ranqueado.eixos_sem_dado)}.\n"
            "Preencha esses campos ou use --permitir-incompleto para decidir assim mesmo."
        )

    # O snapshot precisa nascer da mesma execucao que fecha a compra. Um
    # ranking.md antigo nao e evidencia do que o motor calculou agora.
    build_ranking(argparse.Namespace(projeto=args.projeto))
    instante = dt.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    snapshot_dir = project / "snapshots" / f"{instante}-{slugify(args.produto_id)}"
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    quote_canonical = json.dumps(quote, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    quote_hash = hashlib.sha256(quote_canonical.encode("utf-8")).hexdigest()
    for nome in ("ranking.md", "ranking.csv"):
        origem = project / nome
        if not origem.exists():
            raise SystemExit(f"Nao foi possivel congelar a decisao: {origem} nao existe.")
        atomic_write_text(snapshot_dir / nome, origem.read_text(encoding="utf-8"))
    snapshot_rel = snapshot_dir.relative_to(project).as_posix()
    atomic_write_text(
        snapshot_dir / "metadados.json",
        json.dumps(
            {
                "criado_em": now_iso(),
                "produto_id": args.produto_id,
                "cotacao_sha256": quote_hash,
                "cotacao": quote,
            },
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ) + "\n",
    )

    lines = [
        "# Decisao",
        "",
        "## Escolhido",
        "",
        f"- Produto: {product.get('nome')}",
        f"- Produto ID: {args.produto_id}",
        f"- Cotacao usada: {quote.get('loja')} / {quote.get('vendedor')}",
        f"- Data: {today()}",
        f"- Custo total confirmado: {brl(quote.get('custo_total'))}",
        f"- Evidencia congelada: {snapshot_rel}/ranking.md",
        f"- Cotacao SHA-256: {quote_hash}",
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
    atomic_write_text((project / "decisao.md"), "\n".join(lines) + "\n")
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
    print(snapshot_dir)
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
        "- Valor pago:": f"- Valor pago: {brl(quote.get('custo_total'))}",
        "- Vendedor:": f"- Vendedor: {quote.get('loja')} / {quote.get('vendedor')}",
        "- Veredito D+30 previsto:": f"- Veredito D+30 previsto: {d30.isoformat()}",
        "- Veredito D+180 previsto:": f"- Veredito D+180 previsto: {d180.isoformat()}",
        # Preenchidos aqui para que `aprender-veredito` consiga exportar marca,
        # loja e categoria sem depender de o usuario redigitar tudo na mao.
        "- Marca:": f"- Marca: {product.get('marca') or ''}",
        "- Loja:": f"- Loja: {quote.get('loja') or ''}",
        "- Categoria:": f"- Categoria: {product.get('categoria') or ''}",
    }
    for needle, replacement in replacements.items():
        text = text.replace(needle, replacement, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text)
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
    # O vendedor tem julgamento proprio: a loja pode ter resolvido bem uma
    # compra da qual voce se arrependeu, e o contrario tambem acontece.
    if args.nota_vendedor is not None:
        updates[f"{prefix} nota vendedor"] = str(args.nota_vendedor)
    if args.compraria_do_vendedor:
        updates[f"{prefix} compraria do mesmo vendedor"] = args.compraria_do_vendedor
    structured = {
        "chegou no prazo": args.chegou_no_prazo,
        "produto conforme": args.produto_conforme,
        "defeito": args.defeito,
        "vendedor respondeu": args.vendedor_respondeu,
        "ainda usa": args.ainda_usa,
        "valeu o que pagou": args.valeu_o_que_pagou,
        "o que aprendi": args.o_que_aprendi,
    }
    for label, value in structured.items():
        if value:
            updates[f"{prefix} {label}"] = value
    for label, value in updates.items():
        text = replace_or_append_bullet(text, label, value)
    atomic_write_text(path, text)
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
    preenchidas = {
        fase: any(
            extract_bullet(text, f"{prefix} {rotulo}")
            for rotulo in ("resumo", "licao", "nota arrependimento", "preenchido em")
        )
        for fase, prefix in (("d30", "D+30"), ("d180", "D+180"))
    }
    fase = args.fase or ("d180" if preenchidas["d180"] else "d30")
    prefix = "D+30" if fase == "d30" else "D+180"
    marker_heading = f"## Aprendizado exportado {prefix}"

    # Cada fase e uma observacao diferente. D+30 exportado nao pode bloquear o
    # aprendizado de uso prolongado em D+180, mas repetir a mesma fase tambem
    # nao pode pesar duas vezes na base.
    legacy_export = "## Aprendizado exportado\n" in text
    if (marker_heading in text or legacy_export) and not args.force:
        raise SystemExit(
            f"Este veredito ja foi exportado na fase {prefix} para a base de conhecimento.\n"
            f"Veja o bloco `{marker_heading}` em {path}.\n"
            "Use --force se quiser exportar de novo mesmo assim."
        )
    # Veredito em branco exportava "com sucesso", nao gravava nada e ainda
    # carimbava o arquivo como exportado, bloqueando a exportacao de verdade
    # quando o D+30 fosse preenchido. Silencio pior que erro.
    if not preenchidas[fase] and not (args.resumo or args.licao):
        raise SystemExit(
            f"Fase {prefix} ainda em branco: {path}\n"
            f"Preencha com `preencher-veredito --fase {fase}` antes de exportar, "
            "ou passe --resumo/--licao aqui."
        )

    project_name = extract_bullet(text, "Projeto")
    product_name = extract_bullet(text, "Produto")
    seller = extract_bullet(text, "Vendedor")
    categoria = args.categoria or extract_bullet(text, "Categoria") or "geral"
    marca = args.marca or extract_bullet(text, "Marca")
    loja = args.loja or extract_bullet(text, "Loja") or seller.split("/")[0].strip()
    summary = args.resumo or extract_bullet(text, f"{prefix} resumo") or f"Veredito {prefix} registrado para {product_name}."
    lesson = args.licao or extract_bullet(text, f"{prefix} licao") or extract_bullet(text, f"{prefix} o que aprendi")
    buy_again = args.compraria_de_novo or extract_bullet(text, f"{prefix} compraria de novo")
    regret = args.nota_arrependimento
    if regret is None:
        raw_regret = extract_bullet(text, f"{prefix} nota arrependimento")
        regret = quote_float(raw_regret, 0) if raw_regret else None

    # Julgamento do PRODUTO e do VENDEDOR sao coisas diferentes. Antes, um
    # arrependimento 9 com o produto derrubava a loja para nota 1 junto, mesmo
    # quando a loja tinha resolvido a devolucao perfeitamente. Cada um tem o
    # proprio campo; sem campo proprio, a entrada fica sem nota em vez de herdar
    # a nota alheia.
    nota_produto = None if regret is None else max(0, 10 - regret)
    nota_loja = args.nota_loja
    if nota_loja is None:
        bruto = extract_bullet(text, f"{prefix} nota vendedor")
        nota_loja = quote_float(bruto) if bruto else None
    compraria_produto = buy_again if buy_again in {"sim", "nao", "talvez"} else None
    compraria_loja = args.compraria_do_vendedor or (
        extract_bullet(text, f"{prefix} compraria do mesmo vendedor") or None
    )
    if compraria_loja not in {"sim", "nao", "talvez", None}:
        compraria_loja = None

    if marca:
        register_brand(
            argparse.Namespace(
                nome=marca,
                categoria=categoria,
                projeto=project_name,
                nota=nota_produto,
                compraria_de_novo=compraria_produto,
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
                nota=nota_loja,
                compraria_de_novo=compraria_loja,
                resumo=args.resumo_vendedor or summary,
                alerta=args.alerta,
            )
        )
    if lesson:
        register_lesson(argparse.Namespace(texto=lesson, categoria=categoria, gate=args.gate))

    marker = f"\n{marker_heading}\n\n- Data: {today()}\n- Marca: {marca}\n- Loja: {loja}\n- Categoria: {categoria}\n- Licao: {lesson}\n"
    if marker_heading not in text:
        append_text(path, marker)
    print(f"Aprendizado processado: {path}")


def new_verdict(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    path = VEREDITOS / f"{today()}-{project.name}.md"
    if path.exists() and not args.force:
        raise SystemExit(f"Veredito ja existe: {path}")
    text = render_template("veredito.md").replace("- Projeto:", f"- Projeto: {project.name}")
    atomic_write_text(path, text)
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

    regra = stop_rule_status(project)
    if regra:
        dias = regra["dias_em_pesquisa"]
        print(
            f"Regra de parada ({regra['faixa']}): teto {regra['tempo_maximo']}, "
            f"{regra['candidatos']} candidatos, {regra['cotacoes_minimas_texto']} cotacao(oes) cada"
            + (f" | {dias} dias em pesquisa" if dias is not None else "")
        )
        print(f"Candidatos hoje: {regra['candidatos_atuais']}")
        if regra["produtos_sem_cotacoes_suficientes"]:
            print("Falta cotacao em: " + ", ".join(regra["produtos_sem_cotacoes_suficientes"]))

    vencidas = sorted(pid for pid, row in latest.items() if quote_is_stale(row))
    if vencidas:
        print("Cotacao vencida (recote): " + ", ".join(vencidas))
    if web_only_ids:
        print("Confirmar manualmente: " + ", ".join(sorted(web_only_ids)))
        primeiro = sorted(web_only_ids)[0]
        print(
            "Comando sugerido: python scripts/central_compras.py promover-cotacao "
            f"projetos/{project.name} --produto-id {primeiro} [campos conferidos]"
        )
    elif not latest:
        print(
            "Comando sugerido: python scripts/central_compras.py prompt-ia "
            f"projetos/{project.name} --etapa modelo"
        )
    elif errors:
        print(
            "Comando sugerido: python scripts/central_compras.py validar "
            f"projetos/{project.name} --strict"
        )
    else:
        print(
            "Comando sugerido: python scripts/central_compras.py ranking "
            f"projetos/{project.name}"
        )


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
    atomic_write_text((project / "validacao.md"), "\n".join(lines) + "\n")
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


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return yaml.safe_dump(value, allow_unicode=True, default_flow_style=True).strip().rstrip("\n...").strip()


def set_category_gate(path: Path, categoria: str, field: str, value: Any) -> None:
    """Escreve `categoria.gate.campo` mexendo so na linha certa.

    Um `safe_dump` do arquivo inteiro apagava todo comentario que voce escreveu
    explicando por que cada gate existe. `categorias.yaml` e feito para ser
    editado a mao, entao a edicao aqui e cirurgica.
    """
    linhas = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    escrito = f"    {field}: {yaml_scalar(value)}"

    def fim_do_bloco(inicio: int, indent_minimo: int) -> int:
        fim = inicio + 1
        for i in range(inicio + 1, len(linhas)):
            crua = linhas[i]
            if not crua.strip() or crua.lstrip().startswith("#"):
                continue
            if len(crua) - len(crua.lstrip()) < indent_minimo:
                return fim
            fim = i + 1
        return fim

    inicio_categoria = next(
        (i for i, linha in enumerate(linhas) if linha.rstrip() == f"{categoria}:"), None
    )
    if inicio_categoria is None:
        if linhas and linhas[-1].strip():
            linhas.append("")
        linhas.extend([f"{categoria}:", "  gate:", escrito])
        atomic_write_text(path, "\n".join(linhas) + "\n")
        return

    fim_categoria = fim_do_bloco(inicio_categoria, 1)
    inicio_gate = next(
        (i for i in range(inicio_categoria + 1, fim_categoria) if linhas[i].rstrip() == "  gate:"),
        None,
    )
    if inicio_gate is None:
        linhas[fim_categoria:fim_categoria] = ["  gate:", escrito]
        atomic_write_text(path, "\n".join(linhas) + "\n")
        return

    fim_gate = fim_do_bloco(inicio_gate, 3)
    alvo = next(
        (i for i in range(inicio_gate + 1, fim_gate) if linhas[i].strip().startswith(f"{field}:")),
        None,
    )
    if alvo is None:
        linhas.insert(inicio_gate + 1, escrito)
    else:
        linhas[alvo] = escrito
    atomic_write_text(path, "\n".join(linhas) + "\n")


def apply_lesson_gate(gate: str) -> str:
    if "=" not in gate or "." not in gate.split("=", 1)[0]:
        raise SystemExit("Use --gate categoria.campo=valor. Exemplo: cosmetico.exige_vendedor_oficial=true")
    left, raw_value = gate.split("=", 1)
    categoria, field = left.split(".", 1)
    path = CONFIG / "categorias.yaml"
    valor = parse_scalar(raw_value)
    set_category_gate(path, categoria, field, valor)
    # Confere que o arquivo continua valido e que o valor chegou onde devia.
    conferencia = ((read_yaml(path, {}) or {}).get(categoria) or {}).get("gate", {})
    if conferencia.get(field) != valor:
        raise SystemExit(
            f"Nao consegui gravar o gate {categoria}.{field} em {path}. "
            "Edite o arquivo a mao e confira a indentacao."
        )
    return f"{categoria}.{field}={valor}"


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


def entry_dates(path: Path) -> list[dt.date]:
    """Datas das entradas de um arquivo de marca ou loja (`## AAAA-MM-DD`)."""
    if not path.exists():
        return []
    datas = []
    for match in re.finditer(r"(?m)^##\s*(\d{4}-\d{2}-\d{2})\s*$", path.read_text(encoding="utf-8")):
        data = parse_dashboard_date(match.group(1))
        if data:
            datas.append(data)
    return datas


def knowledge_predating(project: Path) -> dict[str, int]:
    """Conhecimento que ja existia ANTES desta compra comecar.

    Metrica 1 do PRD: reaproveitamento e a base ja ter informacao util quando a
    compra abriu. Contar o que o proprio projeto registrou depois faz a taxa dar
    100% sempre e nao mede nada.
    """
    briefing, _ = load_frontmatter(project / "briefing.md")
    aberto_em = parse_dashboard_date(briefing.get("criado_em"))
    if not aberto_em:
        return {"marcas": 0, "lojas": 0, "licoes": 0}

    brand_files, store_files = knowledge_files_for_project(project)
    marcas = sum(1 for path in brand_files if any(data < aberto_em for data in entry_dates(path)))
    lojas = sum(1 for path in store_files if any(data < aberto_em for data in entry_dates(path)))

    licoes = 0
    for linha in lesson_lines_for_category(briefing.get("categoria")):
        match = re.match(r"^(\d{4}-\d{2}-\d{2})", linha.strip())
        data = parse_dashboard_date(match.group(1)) if match else None
        if data and data < aberto_em:
            licoes += 1
    return {"marcas": marcas, "lojas": lojas, "licoes": licoes}


def reuse_stats(categoria: str | None = None) -> tuple[list[dict[str, Any]], int, int, float]:
    projects = sorted(path for path in PROJETOS.iterdir() if path.is_dir()) if PROJETOS.exists() else []
    rows = []
    for project in projects:
        briefing, _ = load_frontmatter(project / "briefing.md")
        if categoria and briefing.get("categoria") != categoria:
            continue
        anterior = knowledge_predating(project)
        useful = any(anterior.values())
        rows.append(
            {
                "projeto": project.name,
                "categoria": briefing.get("categoria"),
                "marcas": anterior["marcas"],
                "lojas": anterior["lojas"],
                "licoes": anterior["licoes"],
                "reaproveitou": useful,
            }
        )
    total = len(rows)
    reused = sum(1 for row in rows if row["reaproveitou"])
    percent = round((reused / total) * 100, 1) if total else 0
    return rows, total, reused, percent


def reuse_report(args: argparse.Namespace) -> None:
    rows, total, reused, percent = reuse_stats(args.categoria)
    lines = [
        "# Reaproveitamento",
        "",
        f"Gerado em {now_iso()}.",
        "",
        "Conta so o conhecimento que **ja existia antes** da compra abrir. O que o",
        "proprio projeto registrou durante a pesquisa nao e reaproveitamento: seria",
        "medir a si mesmo e dar 100% sempre.",
        "",
        f"- Projetos analisados: {total}",
        f"- Projetos que encontraram base pronta: {reused}",
        f"- Taxa: {percent}% (meta do PRD: acima de 40% a partir da decima compra)",
        "",
        "| Projeto | Categoria | Marcas | Lojas | Licoes | Reaproveitou |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(f"| {row['projeto']} | {row['categoria']} | {row['marcas']} | {row['lojas']} | {row['licoes']} | {'sim' if row['reaproveitou'] else 'nao'} |")
    if total and not reused:
        lines.extend([
            "",
            "Taxa zero aqui e o esperado nas primeiras compras: a base ainda esta sendo",
            "construida. Ela so passa a valer quando uma compra nova encontra licao, marca",
            "ou loja registrada por uma compra anterior.",
        ])
    path = BASE / "reaproveitamento.md"
    atomic_write_text(path, "\n".join(lines) + "\n")
    print(path.relative_to(ROOT))
    print(f"Taxa: {percent}%")


def read_csv_file(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def safe_html(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def pct(value: Any) -> str:
    """Confianca como porcentagem, com selo quando esta baixa."""
    if value in {None, ""}:
        return "-"
    fracao = quote_float(value)
    rotulo = f"{fracao:.0%}"
    if fracao < 0.80:
        return f'<span class="pill warn">{rotulo}</span>'
    return safe_html(rotulo)


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
    # Calcula com o motor em vez de ler o `ranking.csv` do disco: o dashboard
    # mostrava numero velho quando o ranking nao tinha sido regerado.
    elegiveis, cortados = compute_ranking(project)
    errors, warnings = validation_report(project)
    chosen, why = project_decision_summary(project)
    manual_ids = {row.get("produto_id") for row in quotes if row.get("fonte") == "manual"}
    leader = elegiveis[0] if elegiveis else None
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
        "lider": (leader.product.get("nome") or leader.produto_id) if leader else "",
        "score": leader.score if leader else "",
        "confianca": leader.confianca if leader else "",
        "confianca_minima": len([c for c in elegiveis if c.confianca < minimum_confidence(briefing)]),
        "escolhido": chosen,
        "porque": why,
        "aguardando_preco": len(waiting),
        "criado_em": opened_at.isoformat() if opened_at else "",
        "data_decisao": decided_at.isoformat() if decided_at else "",
        "dias_ate_decisao": decision_days,
        # `gate_ok` media erro de validacao, nao corte de gate: um projeto com o
        # unico candidato cortado aparecia com "Aderencia ao gate 100%".
        "validacao_ok": len(errors) == 0,
        "candidatos_cortados": len(cortados),
        "candidatos_elegiveis": len(elegiveis),
    }


def verdict_summaries() -> list[dict[str, str]]:
    def phase_status(text: str, prefix: str) -> str:
        filled = parse_dashboard_date(extract_bullet(text, f"{prefix} preenchido em"))
        if filled:
            return f"preenchido {filled.isoformat()}"
        expected = parse_dashboard_date(extract_bullet(text, f"Veredito {prefix} previsto"))
        if not expected:
            return "sem data"
        delta = (expected - dt.date.today()).days
        if delta < 0:
            return f"atrasado {abs(delta)} dia(s)"
        if delta == 0:
            return "vence hoje"
        return f"pendente, faltam {delta} dia(s)"

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
                "d30_status": phase_status(text, "D+30"),
                "d180_status": phase_status(text, "D+180"),
                "resumo": extract_bullet(text, "D+180 resumo") or extract_bullet(text, "D+30 resumo"),
            }
        )
    return rows


def dashboard_styles() -> str:
    return """
:root {
  color-scheme: light dark;
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
  --track: #ede8dc;
  --pill: #ede8dc;
  --pill-ok: #dff0df;
  --pill-warn: #faedcc;
  --pill-bad: #f5d7d1;
  --code-bg: #2b2a26;
  --code-ink: #faf7ef;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14140f;
    --surface: #1e1e19;
    --ink: #f0ece2;
    --muted: #a09b90;
    --line: #35342c;
    --teal: #5eead4;
    --green: #86e08a;
    --amber: #f0c674;
    --coral: #f0a08c;
    --blue: #8ab4f8;
    --track: #2c2b24;
    --pill: #2c2b24;
    --pill-ok: #1e3a1f;
    --pill-warn: #3d3218;
    --pill-bad: #43231c;
    --code-bg: #0d0d0a;
    --code-ink: #f0ece2;
  }
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
.pill { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 12px; background: var(--pill); color: var(--ink); }
.pill.ok { background: var(--pill-ok); color: var(--green); }
.pill.warn { background: var(--pill-warn); color: var(--amber); }
.pill.bad { background: var(--pill-bad); color: var(--coral); }
.bars { display: grid; gap: 8px; }
.bar-row { display: grid; grid-template-columns: 120px 1fr 42px; align-items: center; gap: 8px; font-size: 13px; }
.bar-track { height: 10px; background: var(--track); border-radius: 999px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--teal); }
.actions { display: flex; gap: 10px; flex-wrap: wrap; }
.actions a { font-size: 13px; }
pre {
  white-space: pre-wrap;
  background: var(--code-bg);
  color: var(--code-ink);
  padding: 12px;
  border-radius: 8px;
  overflow: auto;
}
@media (max-width: 900px) {
  .grid, .two { grid-template-columns: 1fr; }
  .topbar { display: block; }
  .shell { padding: 16px; }
  th, td { font-size: 12px; }
  /* Tabela larga rola dentro do proprio painel em vez de esmagar o texto
     e estourar os selos. A pagina nunca rola de lado. */
  .panel { overflow-x: auto; }
  table { table-layout: auto; }
  /* So a tabela com cabecalho (muitas colunas) precisa rolar.
     A de chave/valor cabe na tela e continua quebrando linha normalmente. */
  table:has(thead) { min-width: 520px; }
  table:has(thead) th, table:has(thead) td { white-space: nowrap; }
  table:has(thead) td:first-child, table:has(thead) th:first-child { white-space: normal; min-width: 120px; }
}
"""


def write_dashboard_asset() -> None:
    assets = DASHBOARD / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    atomic_write_text((assets / "styles.css"), dashboard_styles().strip() + "\n")


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
    elegiveis_p, cortados_p = compute_ranking(project)
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
    for item in [*elegiveis_p, *cortados_p]:
        cortado = bool(item.eliminations)
        ranking_rows.append(
            "<tr>"
            f"<td>{safe_html(item.product.get('nome') or item.produto_id)}</td>"
            f"<td class=\"num\">{safe_html(item.score)}</td>"
            f"<td class=\"num\">{pct(item.confianca)}</td>"
            f"<td><span class=\"pill {'bad' if cortado else 'ok'}\">{'cortado' if cortado else 'elegivel'}</span></td>"
            f"<td>{safe_html('; '.join(item.eliminations))}</td>"
            f"<td>{safe_html('; '.join(item.alerts))}</td>"
            "</tr>"
        )
    history_rows = []
    for item in price_history(project):
        unica = item["observacoes"] < 2
        aviso = (
            '<span class="pill warn">1 observacao</span>'
            if unica
            else f"{item['desconto_real_vs_mediana_pct']}%"
        )
        history_rows.append(
            "<tr>"
            f"<td>{safe_html(item['nome'])}</td>"
            f"<td class=\"num\">{safe_html(item['observacoes'])}</td>"
            f"<td class=\"num\">{safe_html(brl(item['atual']))}</td>"
            f"<td class=\"num\">{safe_html(brl(item['minimo']))}</td>"
            f"<td class=\"num\">{safe_html(brl(item['mediana']))}</td>"
            f"<td class=\"num\">{safe_html(brl(item['maximo']))}</td>"
            f"<td class=\"num\">{aviso}</td>"
            "</tr>"
        )

    quote_rows = []
    for row in quotes[-20:]:
        quote_rows.append(
            "<tr>"
            f"<td>{safe_html(row.get('data_coleta'))}</td>"
            f"<td>{safe_html(row.get('produto_id'))}</td>"
            f"<td>{safe_html(row.get('loja'))}</td>"
            f"<td class=\"num\">{safe_html(brl(row.get('custo_total')))}</td>"
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
      <tr><td>Validacao</td><td><span class="pill {'ok' if summary['validacao_ok'] else 'bad'}">{'sem erro' if summary['validacao_ok'] else 'com erro'}</span></td></tr>
      <tr><td>Candidatos</td><td>{summary['candidatos_elegiveis']} elegiveis, {summary['candidatos_cortados']} cortados pelo gate</td></tr>
      <tr><td>Aguardando preco</td><td>{safe_html(summary['aguardando_preco'])}</td></tr>
    </tbody>
  </table>
</section>
<section class="section panel">
  <h2>Ranking</h2>
  <table>
    <thead><tr><th>Produto</th><th class="num">Score</th><th class="num">Confianca</th><th>Status</th><th>Motivos</th><th>Alertas</th></tr></thead>
    <tbody>{''.join(ranking_rows) or '<tr><td colspan="6">Sem ranking gerado.</td></tr>'}</tbody>
  </table>
</section>
<section class="section panel">
  <h2>Historico de preco</h2>
  <p class="muted">Desconto so e desconto contra a sua propria serie. Com uma unica observacao, nao da para saber.</p>
  <table>
    <thead><tr><th>Produto</th><th class="num">Obs.</th><th class="num">Atual</th><th class="num">Minimo</th><th class="num">Mediana</th><th class="num">Maximo</th><th class="num">vs mediana</th></tr></thead>
    <tbody>{''.join(history_rows) or '<tr><td colspan="7">Sem historico.</td></tr>'}</tbody>
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
    atomic_write_text(page, html_page(project.name, body, page_dir))
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
    atomic_write_text(page, html_page("Base de conhecimento", body, DASHBOARD))
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
    sem_erro = sum(1 for summary in summaries if summary["validacao_ok"])
    validacao_rate = round((sem_erro / len(summaries)) * 100, 1) if summaries else 0
    total_cortados = sum(int(summary["candidatos_cortados"]) for summary in summaries)
    total_candidatos = total_cortados + sum(int(summary["candidatos_elegiveis"]) for summary in summaries)
    corte_rate = round((total_cortados / total_candidatos) * 100, 1) if total_candidatos else 0
    decision_days_values = [int(summary["dias_ate_decisao"]) for summary in summaries if summary["dias_ate_decisao"] != ""]
    avg_decision_days = round(sum(decision_days_values) / len(decision_days_values), 1) if decision_days_values else ""
    regrets = [
        quote_float(value)
        for row in verdicts
        for value in [row.get("d180") or row.get("d30")]
        if value not in {None, ""}
    ]
    avg_regret = round(sum(regrets) / len(regrets), 1) if regrets else ""
    verdicts_overdue = sum(
        1 for row in verdicts
        for key in ("d30_status", "d180_status")
        if str(row.get(key) or "").startswith("atrasado")
    )
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
            f"<td class=\"num\">{pct(summary['confianca'])}</td>"
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
            f"<td class=\"num\">{safe_html(brl(row['preco_atual'], ''))}</td>"
            f"<td class=\"num\">{safe_html(brl(row['preco_alvo'], ''))}</td>"
            f"<td class=\"num\">{safe_html(brl(row['distancia_ate_alvo'], ''))}</td>"
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
            f"<td>{safe_html(row['d30_status'])}</td>"
            f"<td>{safe_html(row['d180_status'])}</td>"
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
  <div class="panel"><h2>Indicadores</h2><table><tbody><tr><td>Reaproveitamento</td><td class="num">{safe_html(reuse_rate)}</td></tr><tr><td>Projetos sem erro de validacao</td><td class="num">{validacao_rate}%</td></tr><tr><td>Candidatos cortados pelo gate</td><td class="num">{total_cortados} de {total_candidatos} ({corte_rate}%)</td></tr><tr><td>Avisos abertos</td><td class="num">{warnings_total}</td></tr><tr><td>Arrependimento medio</td><td class="num">{safe_html(avg_regret)}</td></tr><tr><td>Vereditos</td><td class="num">{len(verdicts)}</td></tr><tr><td>Fases de veredito atrasadas</td><td class="num">{verdicts_overdue}</td></tr></tbody></table></div>
</section>
<section class="section panel">
  <h2>Projetos</h2>
  <table>
    <thead><tr><th>Projeto</th><th>Categoria</th><th>Estado</th><th>Lider</th><th class="num">Score</th><th class="num">Confianca</th><th class="num">Cotacoes</th><th class="num">Manual</th><th class="num">Dias</th></tr></thead>
    <tbody>{''.join(project_rows) or '<tr><td colspan="9">Nenhum projeto.</td></tr>'}</tbody>
  </table>
</section>
<section class="two section">
  <div class="panel"><h2>Aguardando Preco</h2><table><thead><tr><th>Produto</th><th>Projeto</th><th class="num">Atual</th><th class="num">Alvo</th><th class="num">Distancia</th></tr></thead><tbody>{''.join(waiting_rows) or '<tr><td colspan="5">Nenhum item.</td></tr>'}</tbody></table></div>
  <div class="panel"><h2>Vereditos</h2><table><thead><tr><th>Produto</th><th>Projeto</th><th class="num">D+30</th><th class="num">D+180</th><th>Situacao D+30</th><th>Situacao D+180</th><th>Resumo</th></tr></thead><tbody>{''.join(verdict_rows) or '<tr><td colspan="7">Nenhum veredito.</td></tr>'}</tbody></table></div>
</section>
"""
    index = DASHBOARD / "index.html"
    atomic_write_text(index, html_page("Central de Compras", body, DASHBOARD))
    print(index.relative_to(ROOT))
    print(f"Projetos: {len(projects)}")


def audit_score(args: argparse.Namespace) -> None:
    """Mostra a conta inteira: do que esta no CSV ate o score final.

    Principio 3 do PRD: se o score e 76,5, tem que dar para reconstruir os 76,5
    a mao, com uma calculadora. Ate aqui, dava para conferir eixos -> score, mas
    nao CSV -> eixos, porque os pesos internos do risco viviam so no codigo.
    """
    project = project_path(args.projeto)
    elegiveis, cortados = compute_ranking(project)
    todos = [*elegiveis, *cortados]
    if args.produto_id:
        todos = [item for item in todos if item.produto_id == args.produto_id]
        if not todos:
            raise SystemExit(f"Produto sem cotacao neste projeto: {args.produto_id}")

    escala = (preferences().get("escala") or {}).get("qualidade") or {}
    piso = quote_float(escala.get("nota_piso"), 3.8)
    teto = quote_float(escala.get("nota_teto"), 5.0)
    # O ranking compara por TCO quando a categoria define `tco_meses` ou o
    # projeto passa de R$ 20.000. A memoria de calculo precisa explicar o MESMO
    # numero: explicar por custo_total enquanto o ranking usou tco_total fazia a
    # conta publicada nao fechar justamente na compra cara.
    briefing_meta, _ = load_frontmatter(project / "briefing.md")
    campo_valor, rotulo_valor = value_field_for(briefing_meta)
    custos = [
        quote_float(item.quote.get(campo_valor) or item.quote.get("custo_total"))
        for item in elegiveis
        if quote_float(item.quote.get(campo_valor) or item.quote.get("custo_total")) > 0
    ]
    menor_custo = min(custos) if custos else 0.0

    linhas: list[str] = ["# Memoria de calculo", "", f"Gerado em {now_iso()}.", ""]
    for item in todos:
        row = item.quote
        categoria_produto = item.product.get("categoria")
        nota_ajustada = current_adjusted_rating(row, categoria_produto)
        linhas.extend([f"## {item.product.get('nome') or item.produto_id}", ""])
        if item.eliminations:
            linhas.extend([
                "**Cortado pelos gates, entao o score e 0 por definicao.** Motivos:",
                "",
                *(f"- {motivo}" for motivo in item.eliminations),
                "",
                "Os eixos abaixo sao informativos: gate vem antes de score.",
                "",
            ])

        linhas.extend(["### Qualidade", ""])
        linhas.append(
            f"- nota bruta {row.get('nota') or 0} com {row.get('n_avaliacoes') or 0} avaliacoes"
        )
        cfg_bayes = category_definition(categoria_produto or "generico").get("nota_bayesiana") or preferences().get("nota_bayesiana", {})
        media = quote_float(cfg_bayes.get("media_categoria_padrao"), 4.3)
        ancora = quote_float(cfg_bayes.get("peso_ancora"), 50)
        n = quote_int(row.get("n_avaliacoes"))
        linhas.append(
            f"- nota ajustada = ({n} x {row.get('nota') or 0} + {ancora} x {media}) / ({n} + {ancora}) = **{nota_ajustada}**"
        )
        linhas.append(
            f"- qualidade = ({nota_ajustada} - {piso}) / ({teto} - {piso}) = **{item.axes['qualidade']:.3f}**"
        )

        linhas.extend(["", "### Valor", ""])
        custo = quote_float(row.get(campo_valor) or row.get("custo_total"))
        linhas.append(f"- base de comparacao: **{rotulo_valor}**")
        if campo_valor == "tco_total":
            linhas.append(
                f"- custo de etiqueta {brl(row.get('custo_total'))} + operacao "
                f"{brl(row.get('custo_operacional_mensal'))}/mes x {row.get('tco_meses') or 0} meses "
                f"- revenda estimada {brl(row.get('valor_revenda_estimado'))} = **{brl(custo)}**"
            )
        else:
            linhas.append(f"- custo total desta cotacao: {brl(custo)}")
        linhas.append(f"- menor {rotulo_valor} entre os elegiveis: {brl(menor_custo)}")
        linhas.append(
            f"- valor = {brl(menor_custo)} / {brl(custo)} = **{item.axes['valor']:.3f}**"
        )

        linhas.extend(["", "### Risco", "", "| Parcela | Lido da cotacao | Nota | Peso | Contribui |", "|---|---|---:|---:|---:|"])
        subtotal = 0.0
        for rotulo, lido, nota, peso in risk_parts(row, item.alerts):
            subtotal += nota * peso
            linhas.append(f"| {rotulo} | {lido} | {nota:.2f} | {peso} | {nota * peso:.4f} |")
        quantidade, penalidade = risk_penalty(row, item.alerts)
        linhas.append(f"| soma | | | | **{subtotal:.4f}** |")
        if quantidade:
            linhas.append(
                f"| penalidade | {quantidade} alerta(s): {', '.join(item.alerts) or 'flag manual'} | | | **-{penalidade:.4f}** |"
            )
        linhas.append(f"| risco | | | | **{item.axes['risco']:.3f}** |")

        linhas.extend(["", "### Aderencia", ""])
        reqs = item.product.get("requisitos_atendidos") or {}
        if reqs:
            for chave, valor in reqs.items():
                peso_req = 1.0 if valor is True else (0.5 if str(valor).lower() in {"parcial", "partial"} else 0.0)
                linhas.append(f"- {chave}: {valor} vale {peso_req}")
            linhas.append(f"- aderencia = media = **{item.axes['aderencia']:.3f}**")
        else:
            linhas.append("- nenhum requisito registrado: o eixo fica **fora da conta** (nao vale 0,50)")

        linhas.extend(["", "### Conveniencia", ""])
        if "conveniencia" not in item.axes:
            linhas.append("- categoria sem frete real: o eixo nao entra na conta desta categoria")
        else:
            prazo = row.get("frete_prazo_dias")
            if prazo in {"", None}:
                linhas.append("- prazo de frete nao informado: o eixo fica **fora da conta** (nao vale 0,50)")
            else:
                cfg_conv = (preferences().get("escala") or {}).get("conveniencia") or {}
                otimo = quote_float(cfg_conv.get("prazo_otimo_dias"), 2)
                ruim = quote_float(cfg_conv.get("prazo_ruim_dias"), 30)
                linhas.append(
                    f"- conveniencia = ({ruim} - {prazo}) / ({ruim} - {otimo}) = **{item.axes['conveniencia']:.3f}**"
                )

        linhas.extend(["", "### Score final", "", "| Eixo | Nota | Peso | Entra na conta? | Contribui |", "|---|---:|---:|:--:|---:|"])
        breakdown = item.breakdown
        for eixo, nota in item.axes.items():
            peso = breakdown.weights[eixo]
            if eixo not in breakdown.included_axes:
                linhas.append(f"| {eixo} | -- | {peso} | nao (sem dado) | 0 |")
                continue
            linhas.append(f"| {eixo} | {nota:.3f} | {peso} | sim | {nota * peso:.6f} |")
        if breakdown.missing_axes:
            linhas.append(
                f"| soma dos que entraram | | {breakdown.used_weight:.6f} | | "
                f"**{breakdown.weighted_sum:.6f}** |"
            )
            linhas.append(
                f"| **renormalizado: {breakdown.weighted_sum:.6f} / "
                f"{breakdown.used_weight:.6f} x 100** | | | | **{breakdown.score:.1f}** |"
            )
        else:
            linhas.append(f"| **total x 100** | | | | **{breakdown.score:.1f}** |")
        linhas.append("")
        linhas.append(f"Confianca: **{breakdown.confidence:.0%}** do peso do score apoiado em dado real.")
        if item.eliminations:
            linhas.append("")
            linhas.append(
                f"Score publicado: **0** (cortado no gate, nao os {breakdown.score:.1f} acima)."
            )
        linhas.append("")

    caminho = project / "memoria-calculo.md"
    atomic_write_text(caminho, "\n".join(linhas) + "\n")
    print(caminho)
    for item in todos:
        nome = item.product.get("nome") or item.produto_id
        print(f"{nome}: score {item.score}")


@contextlib.contextmanager
def sources_frozen():
    """Congela as fontes: derivados podem ser refeitos, fonte nao muda.

    `build_ranking` marca etapas e reescreve "Proxima acao" no `processo.md`,
    que e fonte. Rodar `regenerar` mexia no historico decisorio enquanto
    imprimia "Nenhuma fonte foi tocada".
    """
    originais = (globals()["mark_steps"], globals()["set_process_state"])
    globals()["mark_steps"] = lambda *a, **k: None
    globals()["set_process_state"] = lambda *a, **k: None
    try:
        yield
    finally:
        globals()["mark_steps"], globals()["set_process_state"] = originais


def regenerate(args: argparse.Namespace) -> None:
    """Refaz todo arquivo derivado a partir das fontes.

    Derivado versionado da conflito de merge entre maquinas. A saida nao e
    apagar o derivado (o `ranking.md` ao lado do `decisao.md` e a evidencia de
    por que voce decidiu), e sim tornar o conflito trivial: fique com qualquer
    lado e rode isto.
    """
    projetos = [project_path(args.projeto)] if args.projeto else project_dirs()
    congelados = [c for p in projetos for c in p.glob("decisao-*-ranking.md")]
    antes = {c: c.read_text(encoding="utf-8") for c in congelados}
    with sources_frozen():
        for project in projetos:
            alvo = argparse.Namespace(projeto=str(project), produto_id=None, strict=False)
            build_ranking(alvo)
            validate(alvo)
            show_history(alvo)
            audit_score(alvo)
            print(f"  {project.name}: ranking, validacao, historico e memoria de calculo refeitos")
    list_waiting_price(argparse.Namespace(categoria=None))
    reuse_report(argparse.Namespace(categoria=None))
    generate_dashboard(argparse.Namespace())
    for caminho, conteudo in antes.items():
        if caminho.read_text(encoding="utf-8") != conteudo:
            raise SystemExit(f"BUG: `regenerar` alterou um ranking congelado: {caminho}")
    print(
        f"{len(projetos)} projeto(s) regenerado(s). Nenhuma fonte foi tocada"
        + (f", {len(congelados)} ranking(s) congelado(s) preservado(s)." if congelados else ".")
    )


def migrate_quotes(args: argparse.Namespace) -> None:
    """Atualiza o cabecalho do cotacoes.csv sem perder linha nem coluna."""
    alvos = [project_path(args.projeto)] if args.projeto else project_dirs()
    for project in alvos:
        path = project / "cotacoes.csv"
        if not path.exists():
            continue
        antes = raw_quotes_header(project)
        rows = read_quotes(project)
        write_quotes(project, rows)
        depois = raw_quotes_header(project)
        novas = [column for column in depois if column not in antes]
        if novas:
            print(f"{project.name}: {len(rows)} linhas preservadas, colunas adicionadas: {', '.join(novas)}")
        else:
            print(f"{project.name}: ja no schema atual ({len(rows)} linhas).")


def private_data_dir(_: argparse.Namespace) -> None:
    """Cria a pasta de dados pessoais FORA da arvore do repositorio.

    Secao 11 do PRD: `.gitignore` nao basta, porque um `git add -A` distraido
    ou um ignore mal escrito sobe o dado e o historico do Git guarda para sempre.
    """
    destino = Path.home() / ".central-compras" / "dados-privados"
    destino.mkdir(parents=True, exist_ok=True)
    readme = destino / "LEIA-ME.md"
    if not readme.exists():
        atomic_write_text(
            readme,
            "# Dados privados da Central de Compras\n\n"
            "Esta pasta fica FORA do repositorio de proposito. Arquivo que nao esta\n"
            "na arvore versionada nao pode subir para o GitHub por acidente.\n\n"
            "## Pode ficar aqui\n\n"
            "- Endereco de entrega e CEP\n"
            "- CPF para nota fiscal\n"
            "- Numero de pedido, rastreio e protocolo de atendimento\n"
            "- Comprovante e nota fiscal em PDF\n\n"
            "## Nunca fica aqui nem em lugar nenhum\n\n"
            "- Numero de cartao, CVV, senha, token\n\n"
            "No repositorio, referencie por caminho, nunca por copia do conteudo.\n",
        )
    print(destino)
    print("Dado pessoal mora aqui, fora do repositorio. Nunca cartao, CVV ou senha.")


SENSITIVE_PATTERNS: list[tuple[str, str, str]] = [
    ("CPF", r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", "CPF formatado"),
    ("CEP", r"\b\d{5}-\d{3}\b", "CEP"),
    # CPF sem pontuacao so conta quando esta rotulado: 11 digitos soltos sao
    # rastreio, EAN e telefone o tempo todo num repositorio de compras.
    ("CPF", r"(?i)\bcpf\b[^0-9]{0,12}\d{11}\b", "CPF sem pontuacao, rotulado"),
    ("CARTAO", r"\b(?:\d[ ._-]?){13,19}\b", "sequencia com cara de numero de cartao"),
    ("CVV", r"(?i)\bcvv\b\s*[:=]\s*\d{3,4}\b", "CVV"),
    # Sem `\b` a esquerda pelo mesmo motivo do api_key: em `database_password`
    # e em `MINHA_SENHA` o `_` e caractere de palavra e o padrao nunca casaria.
    # Mesma fronteira do TOKEN: `MINHA_SENHA` casa, `resenha:` nao.
    ("SENHA", r"(?i)(?:^|[^A-Za-z])(senha|password|passwd)\b\s*[:=]\s*\S+", "senha em texto"),
    # A esquerda aceita inicio de linha, separador ou `_`/`-`, mas nao letra:
    # sem isso `\bapi_key` nunca casaria `OPENAI_API_KEY`, e tirar a fronteira
    # inteira fazia `notapi_key` virar alarme.
    # A direita aceita o valor entre aspas, que e o formato comum em `.env`.
    (
        "TOKEN",
        r"(?i)(?:^|[^A-Za-z])(token|api[_-]?key|secret|access[_-]?key)\b\s*[:=]\s*[\"']?[A-Za-z0-9_\-\.]{12,}",
        "token/chave",
    ),
    ("GITHUB", r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", "token do GitHub"),
]

SCAN_SUFFIXES = {".md", ".csv", ".yaml", ".yml", ".txt", ".json", ".py", ".html", ".css", ".env", ".ini", ".cfg", ".toml"}

# Arquivos sem extensao que costumam guardar segredo.
SCAN_NAMES = {".env", ".env.local", "env", "credentials", "secrets"}

# Marcador de excecao na linha: exemplo em teste ou documentacao.
ALLOW_SECRET_MARKER = "central-compras:exemplo-nao-e-segredo"


def luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for char in reversed(digits):
        value = int(char)
        if alt:
            value *= 2
            if value > 9:
                value -= 9
        total += value
        alt = not alt
    return total % 10 == 0


def scan_sensitive(root: Path) -> list[tuple[str, int, str, str]]:
    """Procura dado sensivel na arvore versionada.

    Git guarda historico para sempre: e mais barato barrar antes do commit do
    que reescrever historico depois.
    """
    achados: list[tuple[str, int, str, str]] = []
    ignorar = {".git", "__pycache__", ".venv", "venv", ".pytest_cache", "dados-privados"}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or (path.suffix.lower() not in SCAN_SUFFIXES and path.name.lower() not in SCAN_NAMES):
            continue
        if any(part in ignorar for part in path.parts):
            continue
        try:
            linhas = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for numero, linha in enumerate(linhas, 1):
            # Excecao explicita e deliberada, na propria linha. Exemplo em teste
            # ou documentacao nao pode virar alarme eterno, mas tem que ser
            # marcado a mao: nunca por adivinhacao do varredor.
            if ALLOW_SECRET_MARKER in linha:
                continue
            for codigo, padrao, descricao in SENSITIVE_PATTERNS:
                for match in re.finditer(padrao, linha):
                    trecho = match.group()
                    if codigo == "CARTAO":
                        digitos = re.sub(r"\D", "", trecho)
                        # So acusa o que passa no Luhn: sem isso, todo CEP,
                        # codigo de barras e MLB longo viraria alarme falso.
                        if not (13 <= len(digitos) <= 19 and luhn_ok(digitos)):
                            continue
                    rel = path.relative_to(root).as_posix()
                    achados.append((rel, numero, codigo, descricao))
                    break
    return achados


def check_secrets(args: argparse.Namespace) -> None:
    achados = scan_sensitive(ROOT)
    if not achados:
        print("Nenhum padrao sensivel encontrado na arvore versionada.")
        print("Lembrete: endereco, CPF e comprovante moram em ~/.central-compras/dados-privados/.")
        return
    print(f"{len(achados)} ocorrencia(s) suspeita(s):")
    for arquivo, linha, codigo, descricao in achados:
        print(f"  {arquivo}:{linha} [{codigo}] {descricao}")
    print("")
    print("Nao commite antes de resolver. Se ja foi commitado, `git rm` NAO basta:")
    print("o historico guarda. O procedimento e reescrever com `git filter-repo`")
    print("e trocar o que vazou.")
    if args.strict:
        raise SystemExit(1)


def build_artifact(args: argparse.Namespace) -> None:
    try:
        from scripts import painel
    except ImportError:
        import painel

    painel.gerar_artifact(args)


def serve_panel(args: argparse.Namespace) -> None:
    """O painel vive em `scripts/painel.py`: este arquivo ja tem tamanho demais."""
    try:
        from scripts import painel
    except ImportError:
        import painel

    painel.servir(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Central de Compras")
    sub = parser.add_subparsers(required=True, dest="comando")

    p = sub.add_parser("init", help="confere/cria a estrutura de diretorios")
    p.set_defaults(func=ensure_structure)

    p = sub.add_parser("novo-projeto", help="cria um processo de compra")
    p.add_argument("nome")
    p.add_argument("--categoria", default="generico")
    p.add_argument("--valor-estimado", type=real_number, default=0)
    p.add_argument("--preco-teto", type=real_number)
    p.add_argument("--necessidade")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=new_project)

    p = sub.add_parser("novo-produto", help="registra um candidato")
    p.add_argument("projeto")
    p.add_argument("nome")
    p.add_argument("--marca", default="")
    p.add_argument("--categoria")
    p.add_argument("--produto-id")
    p.add_argument("--preco-alvo", type=real_number)
    p.add_argument("--preco-teto", type=real_number)
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
    p.add_argument("--preco", type=real_number, required=True)
    p.add_argument("--preco-promocional", type=real_number)
    p.add_argument("--frete", type=real_number, default=0)
    p.add_argument("--frete-prazo-dias", type=int)
    p.add_argument("--custo-extra", type=real_number, default=0)
    p.add_argument("--custo-total", type=real_number)
    p.add_argument("--custo-operacional-mensal", type=real_number, default=0)
    p.add_argument("--tco-meses", type=int)
    p.add_argument("--valor-revenda-estimado", type=real_number, default=0)
    p.add_argument("--nota", type=real_number, default=0)
    p.add_argument("--avaliacoes", type=int, default=0)
    p.add_argument("--garantia-meses", type=int)
    p.add_argument("--garantia-tipo", choices=["nacional", "importada", "vendedor", "nenhuma"], default="nenhuma")
    p.add_argument("--link")
    p.add_argument("--flag-suspeita", choices=["", "AVAL_SUSPEITA", "ANCORA", "RECICLADO"], default="")
    p.add_argument("--fonte", choices=["web", "manual"], default="manual")
    p.add_argument("--data", type=iso_datetime, help="AAAA-MM-DD ou AAAA-MM-DDTHH:MM:SS")
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
    p.add_argument("--nota", type=real_number)
    p.add_argument("--compraria-de-novo", choices=["sim", "nao", "talvez"])
    p.add_argument("--alerta")
    p.set_defaults(func=register_store)

    p = sub.add_parser("registrar-marca", help="adiciona experiencia propria sobre uma marca")
    p.add_argument("nome")
    p.add_argument("--resumo", required=True)
    p.add_argument("--categoria")
    p.add_argument("--projeto")
    p.add_argument("--nota", type=real_number)
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

    p = sub.add_parser("artifact", help="gera a pagina unica so-leitura para publicar")
    p.add_argument("--fragmento", help="tambem grava a versao sem <html>/<body>, para publicar")
    p.set_defaults(func=build_artifact)

    p = sub.add_parser("painel", help="abre a grade editavel no navegador (grava no repo)")
    p.add_argument("--projeto", help="sem isso, abre o projeto mais recente")
    p.add_argument("--porta", type=int, default=8800)
    p.add_argument("--sem-navegador", action="store_true", help="nao abre o navegador sozinho")
    p.set_defaults(func=serve_panel)

    p = sub.add_parser("historico", help="mostra a serie historica de custo e desmascara preco ancora")
    p.add_argument("projeto")
    p.add_argument("--produto-id")
    p.set_defaults(func=show_history)

    p = sub.add_parser("auditar", help="mostra a conta inteira do score, do CSV ate o numero final")
    p.add_argument("projeto")
    p.add_argument("--produto-id", help="um produto so; sem isso, audita todos")
    p.set_defaults(func=audit_score)

    p = sub.add_parser("regenerar", help="refaz todo arquivo derivado; use apos conflito de merge")
    p.add_argument("--projeto", help="um projeto especifico; sem isso, todos")
    p.set_defaults(func=regenerate)

    p = sub.add_parser("migrar-cotacoes", help="atualiza o cabecalho do cotacoes.csv preservando linhas e colunas extras")
    p.add_argument("--projeto", help="um projeto especifico; sem isso, migra todos")
    p.set_defaults(func=migrate_quotes)

    p = sub.add_parser("dados-privados", help="cria a pasta de dados pessoais fora do repositorio")
    p.set_defaults(func=private_data_dir)

    p = sub.add_parser("checar-segredos", help="procura CPF, cartao, senha e token na arvore versionada")
    p.add_argument("--strict", action="store_true", help="retorna erro se encontrar algo (use no pre-commit)")
    p.set_defaults(func=check_secrets)

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
    p.add_argument("--permitir-vencida", action="store_true", help="aceita cotacao fora do prazo de validade")
    p.add_argument("--permitir-aguardando", action="store_true", help="fecha mesmo com o produto em aguardando_preco acima do alvo")
    p.add_argument("--permitir-cortado", action="store_true", help="fecha mesmo com o produto reprovado nos gates")
    p.add_argument("--permitir-incompleto", action="store_true", help="fecha mesmo com confianca abaixo do minimo")
    p.add_argument("--sem-perdedores", action="store_true", help="fecha sem registrar derrotados (nao houve concorrente)")
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
    p.add_argument("--preco", type=real_number)
    p.add_argument("--preco-promocional", type=real_number)
    p.add_argument("--frete", type=real_number)
    p.add_argument("--frete-prazo-dias", type=int)
    p.add_argument("--custo-extra", type=real_number)
    p.add_argument("--custo-total", type=real_number)
    p.add_argument("--custo-operacional-mensal", type=real_number)
    p.add_argument("--tco-meses", type=int)
    p.add_argument("--valor-revenda-estimado", type=real_number)
    p.add_argument("--tco-total", type=real_number)
    p.add_argument("--nota", type=real_number)
    p.add_argument("--avaliacoes", type=int)
    p.add_argument("--garantia-meses", type=int)
    p.add_argument("--garantia-tipo", choices=["nacional", "importada", "vendedor", "nenhuma"])
    p.add_argument("--link")
    p.add_argument("--flag-suspeita", choices=["", "AVAL_SUSPEITA", "ANCORA", "RECICLADO"])
    p.add_argument("--data", type=iso_datetime, help="AAAA-MM-DD ou AAAA-MM-DDTHH:MM:SS")
    p.add_argument("--sem-alteracao", action="store_true", help="conferi no site e estava tudo igual ao registrado")
    p.set_defaults(func=promote_quote)

    p = sub.add_parser("descartar", help="marca candidato como descartado com motivo obrigatorio")
    p.add_argument("--produto-id", required=True)
    p.add_argument("--porque", required=True)
    p.add_argument("--projeto")
    p.set_defaults(func=discard_product)

    p = sub.add_parser("aguardar-preco", help="marca produto como aguardando preco alvo")
    p.add_argument("--produto-id", required=True)
    p.add_argument("--porque", required=True)
    p.add_argument("--preco-alvo", type=real_number)
    p.add_argument("--preco-teto", type=real_number)
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
    p.add_argument("--nota-vendedor", type=real_number, help="0 a 10 para o VENDEDOR, separado do produto")
    p.add_argument("--compraria-do-vendedor", choices=["sim", "nao", "talvez"])
    p.add_argument("--chegou-no-prazo", choices=["sim", "nao", "parcial"])
    p.add_argument("--produto-conforme", choices=["sim", "nao", "parcial"])
    p.add_argument("--defeito", choices=["sim", "nao", "parcial"])
    p.add_argument("--vendedor-respondeu", choices=["sim", "nao", "parcial"])
    p.add_argument("--ainda-usa", choices=["sim", "nao", "parcial"])
    p.add_argument("--valeu-o-que-pagou", choices=["sim", "nao", "parcial"])
    p.add_argument("--o-que-aprendi")
    p.set_defaults(func=fill_verdict)

    p = sub.add_parser("aprender-veredito", help="transforma veredito preenchido em marca, loja e licao")
    p.add_argument("veredito")
    p.add_argument("--fase", choices=["d30", "d180"], help="fase a exportar; sem isso usa a mais recente preenchida")
    p.add_argument("--marca")
    p.add_argument("--loja")
    p.add_argument("--categoria")
    p.add_argument("--resumo")
    p.add_argument("--licao")
    p.add_argument("--gate")
    p.add_argument("--alerta")
    p.add_argument("--nota-arrependimento", type=float)
    p.add_argument("--compraria-de-novo", choices=["sim", "nao", "talvez"])
    p.add_argument("--nota-loja", type=real_number, help="nota do VENDEDOR, separada da nota do produto")
    p.add_argument("--compraria-do-vendedor", choices=["sim", "nao", "talvez"])
    p.add_argument("--resumo-vendedor", help="o que a loja fez de bom ou de ruim, separado do produto")
    p.add_argument("--force", action="store_true", help="exporta de novo um veredito ja exportado")
    p.set_defaults(func=learn_from_verdict)

    return parser


MUTATING_COMMANDS = {
    "cotar", "promover-cotacao", "decidir", "anotar", "novo-produto",
    "ranking", "validar", "auditar", "historico", "descartar", "aguardar-preco",
    "novo-veredito", "regenerar", "migrar-cotacoes",
}

# Comandos que escrevem em `base-conhecimento/`. No Windows o O_APPEND e
# emulado (posiciona e escreve), entao anexar nao basta: sem trava, 30 licoes
# em paralelo viravam 29 e ninguem era avisado.
KNOWLEDGE_COMMANDS = {
    "registrar-marca", "registrar-loja", "registrar-licao", "aprender-veredito",
    "reaproveitamento", "listar-aguardando-preco", "regenerar", "decidir",
    "preencher-veredito",
}

PRODUCT_COMMANDS = {"novo-produto", "descartar", "aguardar-preco"}
ALL_PROJECT_COMMANDS = {"dashboard", "regenerar", "migrar-cotacoes"}


def locked_project(args: argparse.Namespace) -> Path | None:
    """Projeto que este comando vai escrever, se houver um so."""
    alvo = getattr(args, "projeto", None)
    if not alvo:
        return None
    try:
        return project_path(alvo)
    except SystemExit:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # Todas as travas sao adquiridas em ordem lexicografica. Assim, comandos
    # que tocam projeto + produtos + conhecimento nunca formam ciclo entre si.
    with contextlib.ExitStack() as travas:
        alvos: set[Path] = set()
        if args.comando in MUTATING_COMMANDS:
            projeto = locked_project(args)
            if projeto is not None:
                alvos.add(projeto)
        if args.comando in KNOWLEDGE_COMMANDS:
            alvos.add(BASE)
        if args.comando in PRODUCT_COMMANDS:
            alvos.add(PRODUTOS)
        if args.comando == "novo-projeto":
            alvos.add(PROJETOS)
        if args.comando == "dashboard":
            alvos.update({BASE, DASHBOARD, PROJETOS, *project_dirs()})
        if args.comando in ALL_PROJECT_COMMANDS and not getattr(args, "projeto", None):
            alvos.update(project_dirs())
        for alvo in sorted(alvos, key=lambda path: str(path.resolve()).casefold()):
            travas.enter_context(project_lock(alvo))
        args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
