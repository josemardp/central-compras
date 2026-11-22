"""Separa, SOMENTE LENDO o Git, o que e do Radar de Compras e o que e de outra sessao. Nunca altera arvore, indice ou stash.

Tambem faz backup do codigo do radar FORA do repositorio: enquanto nada esta commitado, `git stash -u`, `git clean` ou
`git checkout -- .` feitos por outra sessao apagariam o pacote radar/ (os scripts rastreados ja fazem `import radar`).
"""

from __future__ import annotations

import datetime as dt
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from . import caminhos

RADAR_PREFIXOS = (
    "radar/", "docs/ecossistema/", "tests/test_radar_", "tests/corpus/", "config/radar_", "scripts/rastrear_",
    "scripts/rodar_rastreador_robos.ps1", "requirements.txt", "tests/test_rastrear_",
)
SEMPRE_MISTO = ("STATUS.md",)
MAX_BACKUPS = 6


def _git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(caminhos.RAIZ), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return p.stdout


def _caminho(linha: str) -> str:
    c = linha[3:].strip().strip('"')
    return c.split(" -> ")[-1]


def secoes_status(diff_status: str) -> list[dict[str, str]]:
    """Secoes `## ...` ADICIONADAS ao STATUS.md e de quem parecem ser (radar x outro assunto)."""
    secoes = []
    for m in re.finditer(r"^\+(## .+)$", diff_status, re.M):
        titulo = m.group(1)
        dono = "radar" if re.search(r"radar|central-compras vira dono|fase 2|rastread", titulo, re.I) else (
            "outra_sessao" if re.search(r"climatizador", titulo, re.I) else "desconhecido")
        secoes.append({"secao": titulo[3:], "dono": dono})
    return secoes


def classificar(porcelain: str, diffs: dict[str, str] | None = None) -> dict[str, Any]:
    diffs = diffs or {}
    radar: list[str] = []
    outra: list[str] = []
    misto: list[str] = []
    desconhecido: list[str] = []
    for linha in porcelain.splitlines():
        if not linha.strip():
            continue
        c = _caminho(linha)
        novo = linha.startswith("??")
        if c in SEMPRE_MISTO:
            misto.append(c)
        elif "climatizador" in c.lower():
            outra.append(c)
        elif any(c.startswith(p) for p in RADAR_PREFIXOS):
            radar.append(c)
        elif not novo and "climatizador" in diffs.get(c, "").lower():
            outra.append(c)  # arquivo rastreado cujo diff e so de outro assunto (ex.: config/categorias.yaml)
        else:
            desconhecido.append(c)
    return {"radar": radar, "outra_sessao": outra, "misto": misto, "desconhecido": desconhecido}


def levantar() -> dict[str, Any]:
    por = _git("status", "--porcelain", "--untracked-files=all")
    diffs = {c: _git("diff", "-U0", "--", c) for c in {_caminho(l) for l in por.splitlines() if l and not l.startswith("??")}}
    r = classificar(por, diffs)
    r["secoes_status"] = secoes_status(diffs.get("STATUS.md", ""))
    r["head"] = _git("log", "-1", "--format=%h %s").strip()
    r["stash"] = len([x for x in _git("stash", "list").splitlines() if x])
    return r


def comandos_sugeridos(r: dict[str, Any]) -> list[str]:
    """Comandos para VOCE rodar no commit (nada e executado aqui)."""
    cmds: list[str] = []
    # diretorios inteiros viram um unico `git add <dir>`; arquivos soltos, um por um
    pastas = sorted({p.split("/")[0] + "/" + p.split("/")[1] + "/" if p.count("/") >= 1 and p.startswith(("radar/", "docs/ecossistema/", "tests/corpus/")) else p
                     for p in r["radar"]})
    cmds.append("git add " + " ".join(pastas))
    if r["misto"]:
        cmds.append("# STATUS.md tem secoes de outra sessao: use `git add -p STATUS.md` e aceite so as secoes do radar "
                    "(" + "; ".join(s["secao"][:40] for s in r["secoes_status"] if s["dono"] == "radar") + ")")
    return cmds


# ---------------------------------------------------------------- protecao do que e de OUTRA sessao (fase 4)

def _sha(p: Path) -> str:
    import hashlib

    return hashlib.sha256(p.read_bytes()).hexdigest()


def secoes_do_status(texto: str) -> dict[str, str]:
    """{titulo da secao '## ...': corpo} do STATUS.md (corpo inclui o proprio titulo)."""
    partes = re.split(r"(?m)^(?=## )", texto)
    return {p.splitlines()[0][3:].strip(): p.rstrip("\n") for p in partes if p.startswith("## ")}


def dono_da_secao(titulo: str) -> str:
    if re.search(r"climatizador", titulo, re.I):
        return "outra_sessao"
    if re.search(r"radar|central-compras vira dono|fase \d|rastread", titulo, re.I):
        return "radar"
    return "historico"  # secao antiga que ja estava no HEAD


def snapshot_alheios() -> dict[str, Any]:
    """Foto (SHA-256) de tudo que e de outra sessao: arquivos do climatizador, o bloco climatizador de categorias.yaml
    e a(s) secao(oes) do climatizador no STATUS.md. Serve para PROVAR no fim que nada disso foi alterado."""
    r = levantar()
    arquivos = {}
    for rel in r["outra_sessao"]:
        p = caminhos.RAIZ / rel
        if p.is_file():
            arquivos[rel] = _sha(p)
    status = (caminhos.RAIZ / "STATUS.md").read_text(encoding="utf-8")
    secoes = {t: __import__("hashlib").sha256(c.encode("utf-8")).hexdigest() for t, c in secoes_do_status(status).items()
              if dono_da_secao(t) == "outra_sessao"}
    return {"quando": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "arquivos": arquivos, "status_secoes_alheias": secoes}


def gravar_baseline(nome: str = "alheios-baseline.json", sobrescrever: bool = False) -> Path:
    import json

    destino = caminhos.backups_dir() / nome
    if destino.exists() and not sobrescrever:
        return destino  # a primeira foto e a que vale: nunca e trocada sem pedido explicito
    destino.write_text(json.dumps(snapshot_alheios(), ensure_ascii=False, indent=1), encoding="utf-8")
    return destino


def verificar_alheios(nome: str = "alheios-baseline.json") -> dict[str, Any]:
    import json

    base = json.loads((caminhos.backups_dir() / nome).read_text(encoding="utf-8"))
    agora = snapshot_alheios()
    mudados = sorted(k for k, v in base["arquivos"].items() if k in agora["arquivos"] and agora["arquivos"][k] != v)
    sumiram = sorted(k for k in base["arquivos"] if k not in agora["arquivos"])
    novos = sorted(k for k in agora["arquivos"] if k not in base["arquivos"])  # a outra sessao pode ter criado: informar, nao e culpa nossa
    sec_mud = sorted(t for t, h in base["status_secoes_alheias"].items() if agora["status_secoes_alheias"].get(t) != h)
    return {"baseline_de": base["quando"], "arquivos_conferidos": len(base["arquivos"]), "alterados": mudados, "sumiram": sumiram,
            "novos_da_outra_sessao": novos, "secoes_status_alteradas": sec_mud,
            "intacto": not (mudados or sumiram or sec_mud)}


def backup_alheios() -> Path:
    """Copia LEITURA dos arquivos de outra sessao (zip fora do Git). So protege: nada e movido, restaurado ou apagado."""
    r = levantar()
    destino = caminhos.backups_dir() / f"alheios-copia-{dt.datetime.now():%Y%m%d-%H%M%S}.zip"
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in r["outra_sessao"] + r["misto"]:
            p = caminhos.RAIZ / rel
            if p.is_file():
                z.write(p, rel)
    for velho in sorted(caminhos.backups_dir().glob("alheios-copia-*.zip"))[:-MAX_BACKUPS]:
        velho.unlink()
    return destino


def testar_restauracao(zip_path: Path) -> dict[str, Any]:
    """Prova que o backup e RECUPERAVEL: extrai numa pasta temporaria e roda os testes do radar de la, com dados privados descartaveis."""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp) / "restaurado"
        with zipfile.ZipFile(zip_path) as z:
            problemas = z.testzip()
            z.extractall(raiz)
        env = dict(os.environ, CENTRAL_COMPRAS_DADOS_PRIVADOS=str(Path(tmp) / "privado"), PYTHONUTF8="1")
        env.pop("PYTHONPATH", None)
        testes = sorted(p.stem for p in (raiz / "tests").glob("test_radar_*.py"))
        p = subprocess.run(["python", "-m", "unittest", *[f"tests.{t}" for t in testes]], cwd=str(raiz), env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        ult = [l for l in (p.stderr or "").splitlines() if l.strip()][-3:]
        arquivos = sum(1 for _ in raiz.rglob("*") if _.is_file())
        return {"zip": str(zip_path), "zip_integro": problemas is None, "arquivos": arquivos, "modulos_de_teste": len(testes),
                "codigo_saida": p.returncode, "resumo": ult}


def gerar_patch_status() -> tuple[str, dict[str, Any]]:
    """Patch do STATUS.md com SO as secoes do radar, sobre a versao do HEAD. Nada e aplicado nem staged: so gera e valida (--check)."""
    import difflib

    head = _git("show", "HEAD:STATUS.md")
    atual = (caminhos.RAIZ / "STATUS.md").read_text(encoding="utf-8")
    sec_head = secoes_do_status(head)
    sec_atual = secoes_do_status(atual)
    minhas = [(t, c) for t, c in sec_atual.items() if t not in sec_head and dono_da_secao(t) == "radar"]
    alheias = [t for t in sec_atual if t not in sec_head and dono_da_secao(t) == "outra_sessao"]
    desconhecidas = [t for t in sec_atual if t not in sec_head and dono_da_secao(t) == "historico"]
    # insere as minhas secoes antes da primeira secao '## Sessao' que ja existia no HEAD (mesmo lugar logico de onde foram escritas)
    ancora = next((t for t in sec_atual if t in sec_head), None)
    novo = head
    if minhas and ancora:
        bloco = "\n\n".join(c for _, c in minhas) + "\n\n"
        i = head.index("## " + ancora)
        novo = head[:i] + bloco + head[i:]
    patch = "".join(difflib.unified_diff(head.splitlines(True), novo.splitlines(True), "a/STATUS.md", "b/STATUS.md"))
    info = {"secoes_do_radar": [t for t, _ in minhas], "secoes_de_outra_sessao_excluidas": alheias, "secoes_sem_dono_claro": desconhecidas,
            "linhas_adicionadas": sum(1 for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++"))}
    return patch, info


def validar_patch(patch: str) -> dict[str, Any]:
    """`git apply --check` (e `--cached --check`): so valida, nunca aplica."""
    import tempfile

    out: dict[str, Any] = {}
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False, encoding="utf-8", newline="") as f:
        f.write(patch)
        nome = f.name
    try:
        for rotulo, extra in (("indice", ["--cached"]), ("arvore", [])):
            # na arvore o STATUS.md ja tem as secoes (mistas): o --check da arvore deve FALHAR; so o do indice (== HEAD) importa
            p = subprocess.run(["git", "-C", str(caminhos.RAIZ), "apply", "--check", *extra, nome], capture_output=True, text=True, encoding="utf-8", errors="replace")
            out[rotulo] = {"ok": p.returncode == 0, "msg": (p.stderr or "").strip()[:160]}
    finally:
        Path(nome).unlink(missing_ok=True)
    return out


def manifesto() -> dict[str, Any]:
    """Exatamente o que entraria no commit do radar (e o que NAO entra). Nada e executado."""
    r = levantar()
    patch, info = gerar_patch_status()
    return {"head": r["head"], "entra_no_commit": sorted(r["radar"]), "status_md": info, "nao_entra_outra_sessao": sorted(r["outra_sessao"]),
            "sem_dono_claro": sorted(r["desconhecido"]), "patch_status": patch, "validacao_patch": validar_patch(patch)}


def backup_codigo() -> Path:
    """Zip (fora do Git) de tudo que e do radar, incluindo o que ainda nao foi commitado."""
    r = levantar()
    destino = caminhos.backups_dir() / f"codigo-radar-{dt.datetime.now():%Y%m%d-%H%M%S}.zip"
    arquivos: set[Path] = set()
    for rel in r["radar"] + r["misto"]:
        p = caminhos.RAIZ / rel
        if p.is_file():
            arquivos.add(p)
    for pasta in ("radar", "docs/ecossistema", "tests/corpus"):
        base = caminhos.RAIZ / pasta
        arquivos |= {p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    arquivos |= {p for p in (caminhos.RAIZ / "config").glob("radar_*.yaml")}
    arquivos |= {p for p in (caminhos.RAIZ / "tests").glob("test_radar_*.py")}
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(arquivos):
            z.write(p, p.relative_to(caminhos.RAIZ).as_posix())
    antigos = sorted(caminhos.backups_dir().glob("codigo-radar-*.zip"))
    for velho in antigos[:-MAX_BACKUPS]:
        velho.unlink()
    return destino
