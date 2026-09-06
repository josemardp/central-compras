"""Benchmark manual e sintetico: python tests/benchmark_pipeline.py --projetos 40.

Compara HEAD anterior a auditoria e fontes atuais no mesmo catalogo descartavel.
Nao e teste de tempo: resultados dependem da maquina e carga concorrente.
"""
import argparse
import json
import subprocess
import sys
import time
import types
from unittest.mock import patch

import ambiente
sys.path.insert(0, str(ambiente.ROOT))
from scripts import central_compras as cc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--projetos", type=int, default=40)
    parser.add_argument("--baseline", default="feae025")
    args = parser.parse_args()
    if not 1 <= args.projetos <= 200:
        parser.error("use entre 1 e 200 projetos")
    source = subprocess.check_output(["git", "show", f"{args.baseline}:scripts/central_compras.py"], cwd=ambiente.ROOT).decode("utf-8")
    before = types.ModuleType("central_compras_baseline")
    before.__file__ = cc.__file__
    sys.modules[before.__name__] = before
    exec(compile(source, before.__file__, "exec"), before.__dict__)
    case = ambiente.RepoTestCase()
    case.setUp()
    try:
        projects = []
        for i in range(args.projetos):
            project = case.project(f"carga-{i}")
            projects.append(project)
            for j in range(3):
                pid = f"produto-{i}-{j}"
                case.product(project, pid)
                case.quote(project, pid)
        for key in ("ROOT", "CONFIG", "PROJETOS", "PRODUTOS", "TEMPLATES", "BASE", "VEREDITOS", "DASHBOARD"):
            setattr(before, key, getattr(cc, key))
        for label, module in ((args.baseline, before), ("atual", cc)):
            start = time.perf_counter()
            with patch.object(module.yaml, "safe_load", wraps=module.yaml.safe_load) as parse:
                summaries = [module.project_counts(project) for project in projects]
            print(json.dumps({"versao": label, "projetos": len(summaries), "produtos": 3 * len(projects),
                              "yaml_parses": parse.call_count, "segundos": round(time.perf_counter() - start, 3)}), flush=True)
    finally:
        case.doCleanups()
        sys.modules.pop(before.__name__, None)


if __name__ == "__main__":
    main()
