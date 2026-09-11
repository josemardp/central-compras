#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import contextvars
import copy
import csv
import datetime as dt
import hashlib
import functools
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
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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
    "estoque",
    "proveniencia",
]

# Proveniencia: de onde veio cada campo comercial e o que foi de fato
# conferido - amarrado a ESTA observacao (esta linha), nunca ao produto em
# geral. `fonte` (web/manual) sozinho nao basta: uma linha `fonte=manual`
# pode ter so o preco conferido e o resto copiado da cotacao anterior.
PROVENIENCIA_ORIGENS = ["observacao_direta", "relatorio_ia", "conferencia_humana", "inferencia"]
# Origem que o registro assume quando nao ha nada gravado - nunca escolhida
# pelo usuario, so atribuida por parse_proveniencia() para linha antiga ou
# campo nunca preenchido.
PROVENIENCIA_ORIGEM_LEGADO = "legado_sem_evidencia"
PROVENIENCIA_CAMPOS = ["preco", "variacao", "vendedor", "frete", "estoque", "garantia"]
PROVENIENCIA_ESTOQUE_OPCOES = ["", "disponivel", "indisponivel", "sob_encomenda"]


def proveniencia_vazia() -> dict[str, Any]:
    """O valor padrao para um campo sem evidencia registrada - legado ou
    nunca preenchido. Nunca inventar data nem conferencia aqui."""
    return {"origem": PROVENIENCIA_ORIGEM_LEGADO, "evidencia": "", "data": None, "estado": "nao_conferido"}


def parse_proveniencia(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Le a proveniencia de UMA linha de cotacoes.csv, sempre com as 6
    chaves de PROVENIENCIA_CAMPOS presentes. Uma linha antiga (sem a coluna
    ou com JSON ilegivel) nunca vira evidencia fabricada - cai em
    proveniencia_vazia() campo a campo, o que É a marca de "legado sem
    evidencia registrada" que a frente pediu."""
    bruto = (row.get("proveniencia") or "").strip()
    carregado: dict[str, Any] = {}
    if bruto:
        try:
            lido = json.loads(bruto)
            if isinstance(lido, dict):
                carregado = lido
        except json.JSONDecodeError:
            carregado = {}
    resultado: dict[str, dict[str, Any]] = {}
    for campo in PROVENIENCIA_CAMPOS:
        entrada = carregado.get(campo)
        if isinstance(entrada, dict) and entrada.get("origem") in PROVENIENCIA_ORIGENS:
            resultado[campo] = {
                "origem": entrada.get("origem"),
                "evidencia": str(entrada.get("evidencia") or ""),
                "data": entrada.get("data") or None,
                "estado": entrada.get("estado") if entrada.get("estado") in ("conferido", "nao_conferido") else "nao_conferido",
            }
        else:
            resultado[campo] = proveniencia_vazia()
    return resultado


def serializar_proveniencia(dados: dict[str, dict[str, Any]]) -> str:
    completo = {campo: (dados.get(campo) or proveniencia_vazia()) for campo in PROVENIENCIA_CAMPOS}
    return json.dumps(completo, ensure_ascii=False, sort_keys=True)


def marcar_proveniencia(
    dados: dict[str, dict[str, Any]], campo: str, origem: str, evidencia: str, data: str
) -> None:
    """Atualiza a proveniencia de UM campo, marcando-o como conferido agora.
    So o campo passado muda - os outros ficam como estavam (chamador decide
    quais campos tocar; confirmacao parcial nunca deve afetar o resto)."""
    dados[campo] = {
        "origem": origem,
        "evidencia": str(evidencia or ""),
        "data": data or None,
        "estado": "conferido",
    }

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


def nonnegative_int(value: str) -> int:
    try:
        number = int(str(value))
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError(f"inteiro invalido: {value!r}") from None
    if number < 0:
        raise argparse.ArgumentTypeError(f"valor negativo: {value!r}")
    return number


def personal_rating(value: str) -> float:
    number = real_number(value)
    if number > 10:
        raise argparse.ArgumentTypeError("nota pessoal precisa estar entre 0 e 10")
    return number


def reject_future(momento: dt.datetime) -> dt.datetime:
    """Cotacao e observacao do passado. Nao existe preco coletado amanha."""
    if momento.date() > dt.date.today():
        raise argparse.ArgumentTypeError(
            f"data no futuro: {momento.date().isoformat()}. "
            "Cotacao e observacao de algo que voce viu, nao previsao."
        )
    return momento


def iso_event_date(value: str) -> str:
    """Valida `--data` de eventos pos-decisao (compra/entrega/inicio de uso).

    So data (sem hora - esses eventos, diferente de cotacao, nao registram
    granularidade de horario) e sempre um FATO do passado, nunca previsao -
    mesmo principio de `reject_future`, aplicado aqui de novo porque estes
    eventos usam um formato mais estrito (so `AAAA-MM-DD`).
    """
    texto = (value or "").strip()
    try:
        data = dt.datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"data invalida: {value!r}. Use AAAA-MM-DD.") from None
    if data > dt.date.today():
        raise argparse.ArgumentTypeError(
            f"data no futuro: {data.isoformat()}. Evento e algo que ja aconteceu, nao previsao."
        )
    return data.isoformat()


def valid_collection_date(value: Any) -> bool:
    texto = str(value or "").strip()
    if not texto:
        return False
    try:
        dt.datetime.fromisoformat(texto)
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


_OPERATIONS_DIRNAME = ".operacoes"
_JOURNAL_CAMPOS_OBRIGATORIOS = {"op_id", "kind", "situacao", "passos", "assinatura_fingerprint", "detalhe", "recursos"}


def _operation_path(scope: Path, op_id: str) -> Path:
    return scope / _OPERATIONS_DIRNAME / f"{slugify(op_id)}.json"


def _fingerprint(dados: dict[str, Any]) -> str:
    return json.dumps(dados, ensure_ascii=True, sort_keys=True, default=str, separators=(",", ":"))


def _valores_equivalentes(a: Any, b: Any) -> bool:
    """Igualdade usada para comparar assinaturas - mais estrita que `==` do
    Python exatamente onde `==` engana: `bool` e subclasse de `int` em
    Python, entao `False == 0` e `True == 1` sao `True` pro operador
    nativo, mesmo sendo valores de ENTRADA distintos (`--requisito
    uso=false` grava `False`; `--requisito uso=0` grava o INTEIRO `0` -
    `gate_eliminations` corta so o primeiro, via `is False`). Sem este
    cuidado, uma retomada podia trocar `false` por `0` (ou vice-versa) e
    `_assinaturas_compativeis` aceitava como "mesmo dado".

    Recursivo em dict/list/tuple, porque o mesmo problema vale escondido
    dentro de uma estrutura aninhada (`requisitos_atendidos`, por
    exemplo) - `==` do Python ja recursa em dict/list, mas carrega o
    mesmo furo de bool/int em cada nivel.
    """
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_valores_equivalentes(a[chave], b[chave]) for chave in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_valores_equivalentes(x, y) for x, y in zip(a, b))
    return a == b


def _assinaturas_compativeis(fingerprint_antigo: str, assinatura_nova: dict[str, Any]) -> bool:
    """Compara a assinatura persistida na 1a tentativa com a desta chamada,
    tolerando EVOLUCAO DE SCHEMA - um campo novo que o codigo antigo (que
    comecou o journal pendente) nem sabia que existia - sem abrir mao de
    recusar argumento realmente diferente.

    A comparacao entre dois valores PRESENTES usa `_valores_equivalentes`
    (nunca `==` puro), pra nao confundir `False` com `0` nem em estruturas
    aninhadas - limite deliberado: so tolera a EVOLUCAO DE SCHEMA (campo
    novo ausente do lado antigo), nunca uma diferenca de tipo/valor real
    entre dois campos que os DOIS lados ja preenchiam.

    Um campo ausente na assinatura antiga so e compativel com o valor
    ATUAL se esse valor for o default neutro (None/False/vazio/0) - o
    mesmo que "esta retomada nao esta pedindo nada que a versao antiga do
    codigo nao pudesse ja ter oferecido". Um campo ausente comparado com um
    valor PREENCHIDO continua RECUSADO - isso e argumento realmente
    diferente (ex.: `--data-compra` explicita numa retomada cujo journal
    foi criado antes desse argumento existir), nao mera evolucao de
    schema. Journal corrompido/nao-dict aqui nunca deveria acontecer (quem
    chama ja passou por `_ler_journal`), mas devolve incompativel por
    seguranca em vez de propagar excecao de parsing.
    """
    try:
        antiga = json.loads(fingerprint_antigo)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(antiga, dict):
        return False
    ausente = object()
    for chave in set(antiga) | set(assinatura_nova):
        valor_antigo = antiga.get(chave, ausente)
        valor_novo = assinatura_nova.get(chave, ausente)
        if valor_antigo is not ausente and valor_novo is not ausente:
            if _valores_equivalentes(valor_antigo, valor_novo):
                continue
            return False
        if valor_antigo is ausente and not valor_novo:
            continue
        if valor_novo is ausente and not valor_antigo:
            continue
        return False
    return True


class JournalPrecisaReconciliacao(Exception):
    """Journal existe mas nao da para saber com seguranca o que ja foi feito.

    Cobre dois casos: JSON corrompido (nao parseia) e JSON valido com
    estrutura errada (falta campo obrigatorio, tipo errado). Nos dois casos
    o arquivo e preservado sem alteracao - apagar ou sobrescrever destruiria
    a unica pista de que algo ficou pela metade.
    """


def _ler_journal(path: Path) -> dict[str, Any] | None:
    """None = nunca existiu. Levanta `JournalPrecisaReconciliacao` se existir
    mas nao puder ser lido com confianca. Nunca inventa estrutura ausente."""
    if not path.exists():
        return None
    try:
        bruto = path.read_text(encoding="utf-8")
    except OSError as erro:
        raise JournalPrecisaReconciliacao(f"nao foi possivel ler {path}: {erro}") from erro
    try:
        registro = json.loads(bruto)
    except ValueError as erro:
        raise JournalPrecisaReconciliacao(f"{path} nao e JSON valido: {erro}") from erro
    if not isinstance(registro, dict) or not _JOURNAL_CAMPOS_OBRIGATORIOS.issubset(registro):
        faltando = _JOURNAL_CAMPOS_OBRIGATORIOS - (set(registro) if isinstance(registro, dict) else set())
        raise JournalPrecisaReconciliacao(
            f"{path} e JSON valido mas com estrutura incompleta (falta: {sorted(faltando)})"
        )
    if not isinstance(registro.get("passos"), dict):
        raise JournalPrecisaReconciliacao(f"{path} tem campo 'passos' de tipo inesperado")
    return registro


class OperationHandle:
    """Estado de uma operacao de varios arquivos, com reconciliacao por efeito
    realmente persistido - nao so pelo que o journal diz que fez."""

    def __init__(self, path: Path, registro: dict[str, Any]):
        self._path = path
        self._registro = registro

    @property
    def detalhe(self) -> dict[str, Any]:
        """Dados congelados na primeira tentativa (ex.: caminho do snapshot).

        Uma retomada usa este valor, nunca um recem-calculado: recalcular a
        cada tentativa e o que fazia `decidir` criar um snapshot novo (e
        orfao) a cada retry."""
        return self._registro["detalhe"]

    @property
    def iniciado_em(self) -> str:
        return str(self._registro.get("iniciado_em") or "")

    def concluido(self, passo: str) -> bool:
        return self._registro["passos"].get(passo, {}).get("situacao") == "concluido"

    def efeito_congelado(self, passo: str) -> str | None:
        """Assinatura ja persistida para este `passo` via `registrar_efeito`,
        se alguma tentativa anterior (desta operacao, em QUALQUER versao do
        codigo que a comecou) ja chegou a registra-lo. `None` quando o passo
        nunca foi tentado - nesse caso e seguro montar o conteudo com dado
        ATUAL, porque nao ha nenhum efeito parcial (nem gravacao, nem
        assinatura congelada) que dependa de bater com um texto antigo.

        Existe pra permitir reaproveitar evidencia ja persistida mesmo
        quando `detalhe` (campo de uso livre, por operacao) nao tem as
        chaves que a versao ATUAL do codigo esperaria - journal comecado
        por uma versao anterior do comando, antes de um campo novo existir.
        `registrar_efeito` grava `assinatura_efeito` no disco ANTES de
        chamar `executar()` (ver docstring dele) - por isso, uma vez que o
        passo apareceu aqui, essa e a fonte da verdade, nunca o que uma
        chamada nova recalcularia."""
        existente = self._registro["passos"].get(passo)
        if existente and existente.get("situacao") in ("tentando", "concluido"):
            return existente.get("assinatura_efeito")
        return None

    def _persistir(self) -> None:
        self._registro["atualizado_em"] = now_iso()
        atomic_write_text(self._path, json.dumps(self._registro, ensure_ascii=True, indent=2, sort_keys=True) + "\n")

    def _concluir(self, passo: str) -> None:
        self._registro["passos"].setdefault(passo, {})["situacao"] = "concluido"
        self._persistir()
        _crash_de_teste_se_pedido(passo)

    def registrar_efeito(self, passo: str, arquivo: Path, assinatura_efeito: str, executar) -> None:
        """Executa um efeito nao-idempotente (append-only) com reconciliacao.

        `executar` e uma funcao sem argumentos que produz o efeito quando
        chamada. `assinatura_efeito` e o texto que aparece em `arquivo` uma
        vez que o efeito aconteceu.

        A identidade do efeito NAO e "esse texto existe no arquivo" - texto
        igual pode pertencer a uma operacao anterior legitima e independente
        (duas licoes iguais registradas no mesmo dia, por exemplo). A
        identidade e "quantas ocorrencias existiam ANTES desta tentativa
        comecar" (`contagem_anterior`, congelada junto da assinatura). Uma
        retomada so considera o efeito feito se a contagem AGORA for maior
        que a congelada - ou seja, se uma ocorrencia NOVA apareceu depois que
        esta tentativa comecou. Ocorrencias que ja existiam antes nunca contam
        como prova de que esta tentativa, especificamente, teve efeito.

        Se o passo nunca foi tentado: conta as ocorrencias atuais, grava ANTES
        de executar qual arquivo, assinatura e contagem eram esperados (para
        uma proxima chamada saber o que procurar), so entao executa e
        confirma.

        Se o passo ja estava `tentando`: confere a contagem contra a
        CONGELADA daquela tentativa, nunca contra uma recem-calculada (que
        poderia diferir por motivo alheio a esta operacao).
        """
        if self.concluido(passo):
            return
        existente = self._registro["passos"].get(passo)
        if existente and existente.get("situacao") == "tentando":
            arquivo_congelado = Path(existente.get("arquivo") or str(arquivo))
            assinatura_congelada = existente.get("assinatura_efeito", assinatura_efeito)
            contagem_anterior = existente.get("contagem_anterior", 0)
            atual = arquivo_congelado.read_text(encoding="utf-8") if arquivo_congelado.exists() else ""
            if atual.count(assinatura_congelada) <= contagem_anterior:
                executar()
            self._concluir(passo)
            return
        atual = arquivo.read_text(encoding="utf-8") if arquivo.exists() else ""
        self._registro["passos"][passo] = {
            "situacao": "tentando",
            "arquivo": str(arquivo),
            "assinatura_efeito": assinatura_efeito,
            "contagem_anterior": atual.count(assinatura_efeito),
        }
        self._persistir()
        _crash_de_teste_se_pedido(f"{passo}:iniciado")
        executar()
        _crash_de_teste_se_pedido(f"{passo}:executado")
        self._concluir(passo)

    def executar_uma_vez(self, passo: str, executar) -> None:
        """Executa uma captura de varios arquivos (nao append-only, sobrescrita
        cega) exatamente uma vez por operacao concluida.

        Diferente de `registrar_efeito`, aqui o efeito nao e "uma linha a
        mais": e um CONJUNTO de arquivos sobrescritos (snapshot inteiro,
        decisao.md). Reconciliar por conteudo linha a linha nao faz sentido
        e recalcular os dados de entrada (preferencias, categorias, fichas de
        produto) numa retomada pode capturar valores DIFERENTES dos que
        informaram a decisao original, se algo mudou entre a falha e o
        retry - isso corrompe a evidencia, nao recupera ela.

        Por isso a regra e binaria: se `passo` ja esta `concluido`, esta
        chamada NAO TOCA em nenhum arquivo - a captura anterior, completa,
        e a evidencia, e permanece intocada. Se `passo` nunca foi concluido
        (nem tentado, ou tentado e interrompido no meio), executa a captura
        inteira do zero: como e sobrescrita cega (nao append), refazer do
        zero apos uma interrupcao no meio e seguro, nunca duplica.
        """
        if self.concluido(passo):
            return
        if passo not in self._registro["passos"]:
            self._registro["passos"][passo] = {"situacao": "tentando"}
            self._persistir()
        _crash_de_teste_se_pedido(f"{passo}:iniciado")
        executar()
        _crash_de_teste_se_pedido(f"{passo}:executado")
        self._concluir(passo)


def _crash_de_teste_se_pedido(ponto: str) -> None:
    """Mata o processo de verdade (sem excecao Python) se a suite de teste
    pedir, via variavel de ambiente, para simular interrupcao real neste
    ponto exato. So dispara com o nome exato do ponto e nunca em uso normal:
    a variavel nao existe fora de teste."""
    alvo = os.environ.get("CENTRAL_COMPRAS_TESTE_CRASH_APOS")
    if alvo and alvo == ponto:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(70)


def _recursos_reivindicados_por_outros(exceto_op_id: str) -> dict[str, dict[str, Any]]:
    """Mapeia caminho de recurso (resolvido) -> registro que o reivindica,
    entre TODAS as operacoes em_andamento (qualquer escopo), exceto a
    de `exceto_op_id`. Journal ilegivel NAO entra aqui - ver
    `_escopos_com_journal_ilegivel`, que trata disso a parte porque um
    journal corrompido pode reivindicar qualquer arquivo do escopo dele,
    nao um caminho especifico conhecido.
    """
    mapa: dict[str, dict[str, Any]] = {}
    for registro in pending_operations([BASE, *project_dirs()]):
        if registro.get("situacao") != "em_andamento" or registro.get("op_id") == exceto_op_id:
            continue
        for recurso in registro.get("recursos") or []:
            mapa.setdefault(recurso, registro)
    return mapa


def _escopo_de(caminho: Path) -> Path:
    """BASE se `caminho` estiver sob `base-conhecimento/`; VEREDITOS se
    estiver sob `vereditos/`; senao, o projeto (`projetos/<nome>/`) que o
    contem. Usado para saber se um journal ilegivel num escopo pode estar
    reivindicando `caminho`."""
    resolvido = caminho.resolve()
    if resolvido.is_relative_to(BASE.resolve()):
        return BASE
    if resolvido.is_relative_to(VEREDITOS.resolve()):
        return VEREDITOS
    for projeto in project_dirs():
        if resolvido.is_relative_to(projeto.resolve()):
            return projeto
    return resolvido.parent


# Journal em BASE (aprender-veredito) ou num projeto (decidir) reivindica
# recursos FORA da propria pasta tambem - o arquivo de veredito, em
# `vereditos/`. Classificar um journal ilegivel so pela pasta fisica onde o
# `.operacoes/` mora deixava esses recursos "fora do alcance" da protecao:
# um journal corrompido nao bloqueava escrita em VEREDITOS, embora a MESMA
# operacao, legivel, reivindicasse os dois. A politica conservadora precisa
# cobrir tudo que aquele TIPO de operacao pode alcancar, nao so a pasta do
# journal - vale tanto para aprender-veredito (journal em BASE) quanto para
# decidir (journal no projeto, mas tambem reivindica o proprio veredito).
def _escopos_alcancados_por(escopo_do_journal: Path) -> "set[Path]":
    if escopo_do_journal.resolve() == BASE.resolve():
        return {BASE, VEREDITOS}
    return {escopo_do_journal, VEREDITOS}


def _escopos_com_journal_ilegivel() -> dict[str, dict[str, Any]]:
    """Escopo (str resolvido) -> primeiro registro `journal_ilegivel` que
    pode alcanca-lo (ver `_escopos_alcancados_por`)."""
    mapa: dict[str, dict[str, Any]] = {}
    for registro in pending_operations([BASE, *project_dirs()]):
        if registro.get("situacao") == "journal_ilegivel":
            for alcancado in _escopos_alcancados_por(Path(registro["escopo"])):
                mapa.setdefault(str(alcancado.resolve()), registro)
    return mapa


def _bloquear_se_recursos_conflitantes(recursos: "set[Path] | list[Path]", *,
                                        exceto_op_id: str = "", contexto: str = "") -> None:
    """Levanta `SystemExit` se qualquer arquivo em `recursos`:

    (a) estiver no mesmo escopo de um journal ILEGIVEL - um journal
        corrompido pode estar reivindicando qualquer arquivo daquele escopo,
        e nao ha como saber qual; tratar como "nada reivindicado" (o
        comportamento antigo) deixava a protecao inteira desativada por
        corrupcao, exatamente o oposto do que um journal corrompido deveria
        causar; ou

    (b) ja estiver reivindicado por outra operacao pendente (`recursos` de
        um journal `em_andamento` com `op_id` diferente de `exceto_op_id`).

    Ponto UNICO usado tanto por operacoes com journal proprio
    (`tracked_operation`, passando o proprio `op_id` como excecao) quanto
    por escritores diretos sem journal (`anotar`, `preencher-veredito`,
    `novo-veredito`, `registrar-licao`, `registrar-marca`, `registrar-loja`
    - despachados centralmente em `main()`, nao um a um dentro de cada
    funcao). `project_lock`/trava de `BASE` so serializam enquanto um
    comando esta RODANDO; esta checagem cobre a janela que a trava nao
    cobre, entre uma falha e a retomada.
    """
    recursos = list(recursos)
    if not recursos:
        return
    escopos_ilegiveis = _escopos_com_journal_ilegivel()
    for caminho in recursos:
        escopo = str(_escopo_de(caminho).resolve())
        if escopo in escopos_ilegiveis:
            registro = escopos_ilegiveis[escopo]
            raise SystemExit(
                f"Nao da para {contexto or f'escrever em {caminho}'}: ha um journal ilegivel em "
                f"{registro['arquivo']} ({registro.get('motivo')}), no mesmo escopo ({escopo}).\n"
                "Um journal corrompido pode estar reivindicando qualquer arquivo desse escopo - "
                "nao e seguro presumir que este aqui esta livre so porque o nome dele nao aparece "
                "explicitamente. Confira o arquivo do journal manualmente (o nome do arquivo indica "
                "qual operacao e produto/veredito ele descrevia) antes de consertar ou apagar."
            )
    conflitos = _recursos_reivindicados_por_outros(exceto_op_id)
    colisoes = {
        str(caminho.resolve()): conflitos[str(caminho.resolve())]
        for caminho in recursos if str(caminho.resolve()) in conflitos
    }
    if not colisoes:
        return
    detalhe_colisoes = "; ".join(
        f"{caminho} (operacao {info.get('kind')!r} {info.get('op_id')!r}, journal: {info.get('arquivo')})"
        for caminho, info in colisoes.items()
    )
    raise SystemExit(
        f"Nao da para {contexto or 'continuar'}: outra operacao pendente ja reivindica "
        f"arquivo(s) envolvido(s) aqui - {detalhe_colisoes}.\n"
        "Isso normalmente significa que uma tentativa anterior foi interrompida antes de terminar "
        "e ainda nao foi retomada. Resolva essa pendencia primeiro: rode `operacoes-pendentes` "
        "para ver o comando exato que a iniciou e repita-o com os MESMOS argumentos para retomar. "
        "So depois disso concluir (ou, apos conferir com cuidado, apagar o journal dela "
        "manualmente) esta operacao pode continuar."
    )


def _recusar_se_recurso_pendente(caminho: Path, *, exceto_op_id: str | None = None) -> None:
    """Atalho de `_bloquear_se_recursos_conflitantes` para um unico arquivo."""
    _bloquear_se_recursos_conflitantes({caminho}, exceto_op_id=exceto_op_id or "",
                                        contexto=f"escrever em {caminho}")


@contextlib.contextmanager
def tracked_operation(scope: Path, op_id: str, kind: str, assinatura: dict[str, Any],
                       detalhe_inicial: dict[str, Any] | None = None,
                       recursos: "set[Path] | list[Path]" = ()):
    """Registra em disco uma operacao que grava varios arquivos, antes de comecar.

    Nao existe transacao entre arquivos: cada `atomic_write_text` continua
    atomico por si so, mas a sequencia inteira nao e. O que este helper da e
    RECUPERACAO, nao atomicidade.

    `recursos` e a lista de arquivos que esta operacao vai escrever, POR
    FORA do proprio journal (ex.: `decisao.md`/`processo.md` para `decidir`;
    `licoes.md`/arquivo de marca/loja para `aprender-veredito`). Numa
    operacao NOVA (nao retomada), se qualquer um desses arquivos ja estiver
    reivindicado por outra operacao pendente, esta chamada e RECUSADA antes
    de escrever qualquer coisa - ver `_recursos_reivindicados_por_outros`
    para o porque. E uma escolha conservadora, deliberada: bloquear e
    reversivel (basta retomar ou resolver a pendencia), inventar identidade
    por linha de texto num arquivo pensado para leitura humana nao seria.

    `assinatura` e a impressao digital dos DADOS de entrada desta tentativa
    (preco, justificativa, licao...). Uma retomada com `op_id` igual mas
    `assinatura` diferente e RECUSADA: continuar misturaria passo antigo
    (feito com o dado velho) com passo novo (feito com o dado novo). Quem
    quiser recomecar do zero com dado novo apaga o arquivo do journal a mao,
    depois de conferir o que ficou pendente com `operacoes-pendentes`.

    `detalhe_inicial` e congelado na primeira tentativa e devolvido via
    `op.detalhe` em qualquer retomada - nunca recalculado.

    Journal ilegivel (JSON invalido ou com estrutura incompleta) NAO reinicia
    do zero: levanta `JournalPrecisaReconciliacao` e preserva o arquivo,
    porque reiniciar poderia repetir um efeito ja gravado.

    So chega ao fim do bloco `with` sem excecao quem terminou de verdade; so
    entao o journal e apagado.

    Precisa rodar dentro da trava (`project_lock`) do proprio `scope`: o
    journal nao tem lock proprio, so evita duplicacao entre chamadas
    SEQUENCIAIS (comando, crash, comando de novo), nao entre processos
    concorrentes escrevendo o mesmo `op_id` ao mesmo tempo - isso continua
    sendo papel do `project_lock`. A checagem de `recursos`, por sua vez,
    cobre exatamente a janela que a trava NAO cobre: entre uma falha e a
    retomada, quando nenhum processo esta rodando e nenhuma trava esta
    segurando nada.

    LIMITE ENTRE MAQUINAS: `.operacoes/` fica fora do Git de proposito (e
    estado de execucao local, nao historia de compra). Uma operacao
    interrompida numa maquina e INVISIVEL em outra: o journal nao viaja no
    `git pull`, e os arquivos parcialmente gravados tambem nao, contanto que
    ainda estejam so no working tree local (nao commitados). A defesa nao e
    tecnica, e de rotina: rode `operacoes-pendentes --strict` antes de
    commitar/dar push, e rode `git status` ao voltar numa maquina onde
    ficou trabalho parado. Um commit feito com operacao pendente nesta
    maquina viaja para as outras como se estivesse completo - o journal fica
    para tras. A checagem de `recursos` tambem so enxerga o que esta
    pendente NESTA maquina, pelo mesmo motivo.
    """
    path = _operation_path(scope, op_id)
    try:
        existente = _ler_journal(path)
    except JournalPrecisaReconciliacao as erro:
        raise SystemExit(
            f"O journal de operacao {path} existe mas nao pode ser lido com confianca: {erro}\n"
            "Nao vou presumir que nada foi executado - isso poderia repetir uma gravacao que ja "
            "aconteceu. Confira o arquivo e o que ele deveria ter gravado (marca, loja, licao, "
            "linha de processo.md ou snapshot, dependendo do 'op_id' no nome do arquivo) antes de "
            "apagar o journal manualmente e tentar de novo."
        ) from erro
    fingerprint_nova = _fingerprint(assinatura)
    if existente is not None and existente.get("kind") == kind and existente.get("situacao") == "em_andamento":
        fingerprint_antiga = existente.get("assinatura_fingerprint")
        if fingerprint_antiga != fingerprint_nova and not (
            isinstance(fingerprint_antiga, str) and _assinaturas_compativeis(fingerprint_antiga, assinatura)
        ):
            raise SystemExit(
                f"Ha uma operacao '{kind}' pendente para {op_id!r} com dados diferentes dos desta "
                f"chamada (journal: {path}).\n"
                "Isso normalmente significa: uma tentativa anterior falhou no meio, e esta chamada "
                "usa preco, justificativa, licao ou outro argumento diferente daquela tentativa.\n"
                "Continuar misturaria passo antigo com dado novo. Repita com os MESMOS argumentos "
                "da tentativa anterior para retomar, ou apague o arquivo do journal a mao (depois de "
                "conferir com `operacoes-pendentes` o que ficou pendente) para comecar do zero."
            )
        # Retomada: os recursos ja foram reivindicados por ESTA operacao na
        # 1a tentativa (senao ela nunca teria comecado) - reusa os mesmos,
        # nunca recalcula, e nao precisa checar conflito contra si mesma.
        registro = existente
        registro["situacao"] = "em_andamento"
    else:
        recursos_normalizados = sorted({str(Path(r).resolve()) for r in recursos})
        _bloquear_se_recursos_conflitantes(
            [Path(r) for r in recursos_normalizados], exceto_op_id=op_id,
            contexto=f"comecar '{kind}' ({op_id!r})",
        )
        registro = {
            "op_id": op_id,
            "kind": kind,
            "situacao": "em_andamento",
            "passos": {},
            "assinatura_fingerprint": fingerprint_nova,
            "detalhe": detalhe_inicial or {},
            "recursos": recursos_normalizados,
            "iniciado_em": now_iso(),
            "atualizado_em": now_iso(),
            "pid": os.getpid(),
        }
    atomic_write_text(path, json.dumps(registro, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
    handle = OperationHandle(path, registro)
    yield handle
    # So chega aqui sem excecao. Concluida de verdade: nao deixa rastro de
    # "em andamento" pendurado para sempre em operacoes que terminaram bem.
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def has_pending_operation(scope: Path, op_id: str, kind: str) -> bool:
    """Confere se ha journal em_andamento para este op_id exato, sem entrar nele.

    Usado por guardas de "ja fiz isso antes" (como o aviso de veredito ja
    exportado) para reconhecer quando o efeito que elas estao vendo pode ser
    de uma tentativa PROPRIA ainda em recuperacao, em vez de um uso normal
    anterior e concluido.
    """
    try:
        registro = _ler_journal(_operation_path(scope, op_id))
    except JournalPrecisaReconciliacao:
        return True  # journal ilegivel: trata como pendente, nao como ausente.
    return bool(registro and registro.get("kind") == kind and registro.get("situacao") == "em_andamento")


def pending_operation_record(scope: Path, op_id: str, kind: str) -> dict[str, Any] | None:
    """Devolve o journal pendente legivel desta operacao, se existir."""
    try:
        registro = _ler_journal(_operation_path(scope, op_id))
    except JournalPrecisaReconciliacao:
        return None
    if registro and registro.get("kind") == kind and registro.get("situacao") == "em_andamento":
        return registro
    return None


def pending_operations(scopes: list[Path]) -> list[dict[str, Any]]:
    """Varre `.operacoes/` nos escopos dados e devolve as que ficaram em_andamento
    ou cujo journal nao pode ser lido com confianca (`journal_ilegivel`)."""
    achadas = []
    for scope in scopes:
        pasta = scope / _OPERATIONS_DIRNAME
        if not pasta.exists():
            continue
        for arquivo in sorted(pasta.glob("*.json")):
            try:
                registro = _ler_journal(arquivo)
            except JournalPrecisaReconciliacao as erro:
                achadas.append({"arquivo": str(arquivo), "escopo": str(scope), "situacao": "journal_ilegivel",
                                 "motivo": str(erro)})
                continue
            if registro is not None and registro.get("situacao") == "em_andamento":
                registro = dict(registro)
                registro["arquivo"] = str(arquivo)
                registro["escopo"] = str(scope)
                achadas.append(registro)
    return achadas


_READ_CACHE = contextvars.ContextVar("central_compras_read_cache", default=None)


def read_session(func):
    """Reutiliza leituras dentro de uma operacao; nunca entre requests/threads."""
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        if _READ_CACHE.get() is not None:
            return func(*args, **kwargs)
        token = _READ_CACHE.set({})
        try:
            return func(*args, **kwargs)
        finally:
            _READ_CACHE.reset(token)
    return wrapped


def read_yaml(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    cache = _READ_CACHE.get()
    stat = path.stat()
    key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    if cache is not None and key in cache:
        return default if cache[key] is None else copy.deepcopy(cache[key])
    try:
        with path.open("r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
    except yaml.YAMLError as erro:
        detalhe = str(erro).splitlines()[0] if str(erro) else erro.__class__.__name__
        raise SystemExit(
            f"YAML invalido em {path}: {detalhe}\n"
            "Abra o arquivo e conserte a indentacao ou as aspas antes de continuar."
        ) from erro
    if isinstance(default, dict) and loaded is not None and not isinstance(loaded, dict):
        raise SystemExit(f"YAML em {path} precisa conter um mapa de campos.")
    if cache is not None:
        cache[key] = loaded
    return default if loaded is None else copy.deepcopy(loaded)


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
    match = re.match(r"\A---[ \t]*\n(.*?)^---[ \t]*(?:\n|$)", text, re.M | re.S)
    if not match:
        raise SystemExit(f"Frontmatter invalido em {path}: falta delimitador --- em linha propria.")
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as error:
        raise SystemExit(f"YAML invalido em {path}: confira o frontmatter.") from error
    if not isinstance(meta, dict):
        raise SystemExit(f"Frontmatter invalido em {path}: esperado mapa de campos.")
    return meta, text[match.end():].lstrip()


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
        dentro = resolved_path.parent == PROJETOS.resolve()
    except Exception:
        dentro = False

    if not dentro or not path.is_dir() or not (path / "briefing.md").is_file():
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
    except (ValueError, OverflowError):
        return default


_PREFS_CACHE: dict[str, Any] = {}


def preferences() -> dict[str, Any]:
    """Atualiza entre operacoes, inclusive no painel que permanece aberto."""
    return read_yaml(CONFIG / "preferencias.yaml", {}) or {}


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
    ofertas: dict[str, set[tuple[str, str, str]]] = {}
    presenciais: set[str] = set()
    for row in rows:
        produto_id = row.get("produto_id")
        if produto_id and not quote_is_stale(row) and valid_collection_date(row.get("data_coleta")):
            # Recotacao/promocao da mesma oferta nao e uma fonte independente.
            identidade = tuple(str(row.get(field) or "").strip().casefold()
                               for field in ("loja", "vendedor", "variacao"))
            ofertas.setdefault(produto_id, set()).add(identidade)
            if row.get("vendedor_tipo") == "fisica" and row.get("fonte") == "manual":
                presenciais.add(produto_id)
    cotacoes_por_produto = {pid: len(values) for pid, values in ofertas.items()}
    # Candidato mapeado (`novo-produto`) conta mesmo sem cotacao ainda: sem
    # isso, 10 candidatos mapeados e zero cotacoes davam zero candidatos, e o
    # teto da faixa nunca disparava aviso.
    # Cotacao legada sem produto continua contando; descartado conhecido sai
    # mesmo quando ainda tem linhas no historico de cotacoes.
    candidatos = (
        project_candidate_ids(project) | {r["produto_id"] for r in rows if r.get("produto_id")}
    ) - project_discarded_candidate_ids(project)
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
        "ofertas_distintas_atuais": cotacoes_por_produto,
        "produtos_sem_cotacao_presencial": sorted(candidatos - presenciais)
            if "presencial" in regra["cotacoes_minimas_texto"] else [],
    }


def _projeto_com_progresso_real(path: Path) -> str | None:
    """Devolve o motivo (texto pronto pra mensagem) se `path` ja tem
    progresso real registrado - cotacao, decisao ou snapshot - ou `None` se
    o projeto ainda e uma casca vazia (seguro para `--force` recriar).

    `cotacoes.csv` e append-only por principio deste repositorio: nenhum
    parametro de comando pode reduzi-lo ao cabecalho. `decisao.md` e
    `snapshots/` sao evidencia de uma decisao ja avaliada.
    """
    cotacoes = path / "cotacoes.csv"
    if cotacoes.exists():
        with cotacoes.open("r", encoding="utf-8", newline="") as f:
            linhas = sum(1 for _ in f)
        if linhas > 1:
            return f"{cotacoes} tem {linhas - 1} cotacao(oes) registrada(s), append-only"
    decisao = path / "decisao.md"
    if decisao.exists() and decisao.read_text(encoding="utf-8") != render_template("decisao.md"):
        return f"{decisao} ja tem uma decisao registrada"
    snapshots = path / "snapshots"
    if snapshots.exists() and any(snapshots.iterdir()):
        return f"{snapshots} tem evidencia de decisao congelada"
    return None


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
    projeto_id = _novo_projeto_id(args)
    path = PROJETOS / projeto_id
    if path.exists():
        if not args.force:
            raise SystemExit(f"Projeto ja existe: {path}")
        # A checagem de conflito com operacao PENDENTE roda centralizada em
        # `main()` (RECURSOS_DIRETOS_POR_COMANDO). Esta aqui e independente
        # disso: --force nunca pode apagar progresso real, pendencia ou nao
        # - cotacoes.csv e append-only por principio deste repositorio, e
        # decisao.md/snapshots sao evidencia de uma compra ja avaliada.
        razao = _projeto_com_progresso_real(path)
        if razao:
            raise SystemExit(
                f"--force recusado em {path}: {razao}.\n"
                "--force so serve para recuperar uma criacao que ficou pela metade "
                "(nenhuma cotacao, nenhuma decisao, nenhum snapshot). Para mudar um "
                "projeto que ja tem progresso, edite os arquivos diretamente ou "
                "abra um projeto novo com outro nome."
            )
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
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", produto_id):
        raise SystemExit("produto_id invalido: use letras, numeros, hifen ou sublinhado, sem caminhos.")
    path = PRODUTOS / slugify(categoria) / produto_id
    if not path.resolve().is_relative_to(PRODUTOS.resolve()):
        raise SystemExit("produto_id aponta para fora de produtos/.")
    return path


def new_product(args: argparse.Namespace) -> None:
    project = project_path(args.projeto)
    meta, _ = load_frontmatter(project / "briefing.md")
    categoria = args.categoria or meta.get("categoria") or "generico"
    produto_id = args.produto_id or slugify(args.nome)
    path = product_dir(categoria, produto_id)
    if path.exists() and not args.force:
        raise SystemExit(
            f"Produto ja existe: {path}\n"
            f"Para usar esta MESMA ficha em outro projeto (a pesquisa e os atributos ja "
            f"levantados continuam valendo), use:\n"
            f"  python scripts/central_compras.py vincular-produto --produto-id {produto_id} "
            f"--projeto {project.name}\n"
            "--force recria a ficha do zero; nao serve para reaproveitar produto em projeto novo."
        )
    # Toda a entrada e validada ANTES da primeira escrita: `parse_pairs` pode
    # recusar `--atributo`/`--requisito` mal formado (sem `chave=valor`), e
    # isso precisa acontecer antes de criar qualquer arquivo em disco - senao
    # uma entrada invalida deixava produto.yaml/pesquisa.md gravados e a
    # ficha orfa, sem participacao, sem chance de retomar por `vincular-produto`
    # (que recusa ficha ja existente apontando pro mesmo projeto so em formato
    # legado) nem por `novo-produto` de novo (recusa por ja existir, sem --force).
    atributos = parse_pairs(args.atributo or [])
    requisitos = parse_pairs(args.requisito or [])

    path.mkdir(parents=True, exist_ok=True)

    # So identidade e dado tecnico do produto moram na ficha. Estado, preco-alvo/teto
    # e requisitos sao PARTICIPACAO nesta compra especifica - gravados a parte, em
    # `projetos/<projeto>/participacoes/`, para o mesmo produto poder participar de
    # dois projetos com estados independentes (frente 5).
    data = {
        "id": produto_id,
        "categoria": categoria,
        "nome": args.nome,
        "marca": args.marca,
        "atributos": atributos,
        "proveniencia": None,
    }
    write_yaml(path / "produto.yaml", data)
    atomic_write_text((path / "pesquisa.md"), render_template("pesquisa.md"))

    participacao = default_participation(produto_id)
    participacao["preco_alvo"] = args.preco_alvo
    participacao["preco_teto"] = args.preco_teto if args.preco_teto is not None else meta.get("preco_teto")
    participacao["requisitos_atendidos"] = requisitos
    write_participation(project, produto_id, participacao)

    append_timeline(project, "produto", f"Candidato registrado: {args.nome}", f"id={produto_id}")
    mark_steps(project, [3])
    print(path.relative_to(ROOT))


def link_product(args: argparse.Namespace) -> None:
    """Vincula uma ficha JA EXISTENTE a outro projeto, com participacao propria.

    Caminho explicito para reaproveitar produto entre projetos (frente 5):
    nunca recria a ficha (preserva atributos e `pesquisa.md`) e nunca sobrescreve
    participacao existente - vincular de novo o mesmo par produto/projeto e
    seguro e nao apaga nada.
    """
    ficha_path = find_product_path(args.produto_id)
    if not ficha_path:
        raise SystemExit(
            f"Produto nao encontrado: {args.produto_id}. Use `novo-produto` para criar a ficha primeiro."
        )
    project = project_path(args.projeto)
    op_id = f"vincular-produto:{args.produto_id}"
    # Uma interrupcao entre gravar a participacao e registrar a linha na
    # timeline deixava a participacao no disco e o processo incompleto; a
    # guarda abaixo (participacao ja existe) recusava QUALQUER retomada,
    # inclusive a da propria tentativa interrompida. Journal `em_andamento`
    # com este op_id exato e o sinal de que a participacao encontrada pode
    # ser a desta mesma operacao, ainda incompleta - nesse caso a recusa
    # nao se aplica, e `tracked_operation` decide (aceita retomada com os
    # MESMOS argumentos, recusa com argumentos diferentes).
    retomando = has_pending_operation(project, op_id, "vincular_produto")
    if participation_path(project, args.produto_id).exists() and not retomando:
        raise SystemExit(
            f"{args.produto_id} ja tem participacao registrada em {project.name}. "
            "Nada foi alterado. Para mudar o estado dela use `descartar`/`aguardar-preco` "
            "normalmente - nao repita `vincular-produto`."
        )
    ficha = read_yaml(ficha_path, {})
    if ficha.get("projeto") == project.name:
        raise SystemExit(
            f"{args.produto_id} ja participa de {project.name} (registro legado, ainda nao "
            "migrado para o formato novo). Nada foi alterado; `descartar`/`aguardar-preco` ja "
            "funcionam nesse formato, ou rode `migrar-produtos --aplicar` para atualizar."
        )
    requisitos = parse_pairs(args.requisito or [])
    nome_produto = ficha.get("nome") or args.produto_id
    assinatura = {
        "produto_id": args.produto_id,
        "preco_alvo": args.preco_alvo,
        "preco_teto": args.preco_teto,
        "requisitos_atendidos": requisitos,
    }

    def _gravar_participacao() -> None:
        participacao = default_participation(args.produto_id)
        participacao["preco_alvo"] = args.preco_alvo
        participacao["preco_teto"] = args.preco_teto
        participacao["requisitos_atendidos"] = requisitos
        write_participation(project, args.produto_id, participacao)

    with tracked_operation(
        project, op_id, "vincular_produto", assinatura,
        # `data_evento`/`nome_produto` congelados na 1a tentativa (mesmo
        # principio do `snapshot_rel` de `decidir`): uma retomada precisa
        # escrever exatamente o mesmo conteudo que a assinatura do efeito de
        # timeline esta procurando, senao `registrar_efeito` nunca reconhece
        # a linha ja gravada e duplica. `nome_produto` vem da FICHA
        # compartilhada (nao da participacao desta operacao) - um
        # `novo-produto --force` rodado em OUTRO projeto entre a falha e a
        # retomada muda o nome ali, e recalcula-lo aqui teria o mesmo efeito
        # da data nao congelada: a linha escrita nunca bateria com o que foi
        # registrado como "tentando".
        detalhe_inicial={"data_evento": today(), "nome_produto": nome_produto},
        recursos={project / "processo.md", participation_path(project, args.produto_id)},
    ) as op:
        # Compatibilidade de journal: um journal `em_andamento` comecado por
        # uma versao ANTERIOR do comando pode nao ter `data_evento`/
        # `nome_produto` em `detalhe` (campos novos), ou pode nem ter
        # tentado o passo "timeline" ainda. `efeito_congelado` e a fonte da
        # verdade quando existe - reaproveita o texto EXATO que uma
        # tentativa anterior (desta versao ou de uma antiga) ja persistiu
        # antes de escrever, em vez de reconstruir com dado atual (que
        # poderia divergir e nunca ser reconhecido como o mesmo efeito). So
        # cai para dado atual (`op.detalhe`, com fallback pro valor desta
        # chamada se a chave nao existir num journal antigo) quando o passo
        # nunca foi tentado por ninguem - nesse caso nao ha efeito parcial
        # nenhum que dependa de bater com texto antigo, entao e seguro.
        linha_timeline = op.efeito_congelado("timeline")
        if linha_timeline is None:
            data_evento = op.detalhe.get("data_evento") or today()
            nome_timeline = op.detalhe.get("nome_produto") or nome_produto
            linha_timeline = (
                f"| {data_evento} | produto | Produto reaproveitado: {nome_timeline} | "
                f"id={args.produto_id} |"
            )
        # Sobrescrita cega, nao append-only: se interrompida no meio, a
        # proxima tentativa reescreve o arquivo inteiro do zero com os
        # MESMOS dados (a assinatura ja garante isso) - nunca duplica.
        op.executar_uma_vez("participacao", _gravar_participacao)
        op.registrar_efeito(
            "timeline", project / "processo.md", linha_timeline,
            lambda: append_timeline(project, linha=linha_timeline),
        )
        # Dentro do bloco `with`: uma interrupcao antes desta linha deixa o
        # journal `em_andamento` (nao apagado), entao a retomada ve a
        # pendencia e completa a etapa 3 - fora do bloco, a operacao ja
        # tinha sido dada como concluida (journal apagado) e uma falha bem
        # aqui deixava o checkbox preso sem nenhuma pendencia visivel para
        # retomar.
        mark_steps(project, [3])
    print(f"Vinculado: {args.produto_id} -> {project.name}")


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
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", str(produto_id)):
        return None
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


# --- Participacao: estado do produto NESTE projeto (frente 5) ---------------
#
# A ficha (`produto.yaml`) so guarda identidade e dado tecnico (nome, marca,
# categoria, atributos, proveniencia). Estado de pesquisa, motivo de
# descarte, preco-alvo/teto e requisitos atendidos sao PARTICIPACAO: dizem
# respeito a UMA compra especifica, nao ao produto em si. O mesmo produto_id
# pode estar descartado no projeto A e pesquisando no B - por isso cada
# projeto guarda a propria participacao, em `projetos/<projeto>/participacoes/
# <produto_id>.yaml`, nunca dentro da ficha compartilhada.
#
# Registro ANTIGO (antes desta frente) gravava estado/preco/requisitos direto
# na ficha, junto de um campo `projeto` unico - um produto so podia participar
# de UM projeto por vez. `read_participation` preserva leitura desses
# registros: se nao existe participacao no formato novo para este projeto,
# cai para os campos legados da ficha, MAS SO quando `ficha["projeto"]` e
# exatamente este projeto - nunca herda o estado gravado para outro projeto.
# Assim que qualquer comando grava participacao nova para este par, ela passa
# a valer sozinha (precedencia: novo formato sempre vence quando existe).

_PARTICIPATION_LEGACY_KEYS = (
    "estado", "preco_alvo", "preco_teto", "requisitos_atendidos",
    "descartado_porque", "aguardando_preco_porque", "aguardando_preco_desde",
)

# Vocabulario fechado de `estado` - qualquer coisa fora daqui (typo,
# migracao de outra ferramenta, edicao manual malfeita) nao e um estado que
# o motor sabe interpretar.
ESTADOS_PARTICIPACAO = ("pesquisando", "aguardando_preco", "descartado")


def participations_dir(project: Path) -> Path:
    return project / "participacoes"


def participation_path(project: Path, produto_id: str) -> Path:
    return participations_dir(project) / f"{produto_id}.yaml"


def default_participation(produto_id: str) -> dict[str, Any]:
    return {
        "produto_id": produto_id,
        "estado": "pesquisando",
        "preco_alvo": None,
        "preco_teto": None,
        "requisitos_atendidos": {},
        "descartado_porque": None,
        "aguardando_preco_porque": None,
        "aguardando_preco_desde": None,
    }


# Estado sintetico, NUNCA gravado em disco e fora de `ESTADOS_PARTICIPACAO`
# de proposito (nenhum comando/CLI jamais escreve isso) - devolvido por
# `read_participation` quando o arquivo tem CONTEUDO mas ele e incoerente
# (identidade errada, estado desconhecido, campo com tipo invalido). Marca
# "nao decido sozinho", nunca "pesquisando": participacao invalida NAO pode
# ser elegivel (fabricaria decisao sobre dado que ninguem confirmou) nem
# "descartada" (fabricaria um motivo de descarte que ninguem escreveu).
ESTADO_PARTICIPACAO_INVALIDA = "invalido"

_CAMPOS_MONETARIOS_PARTICIPACAO = ("preco_alvo", "preco_teto")
_CAMPOS_TEXTO_PARTICIPACAO = ("descartado_porque", "aguardando_preco_porque", "aguardando_preco_desde")


def _tipo_invalido_participacao(dados: dict[str, Any]) -> str | None:
    """Valida o TIPO dos campos OPCIONAIS conhecidos, quando presentes.

    "Opcional" nunca significou "tipo livre": ausencia (`None`, ou campo
    nem gravado) continua valida, mas um valor presente com tipo errado
    (`requisitos_atendidos` como lista, `preco_teto` como texto, `NaN` como
    limite monetario) nao pode passar batido - `requisitos_atendidos` vira
    `.items()` em `gate_eliminations`, e um preco nao-finito viraria limite
    ausente em silencio via `quote_float`. Campo desconhecido (schema
    futuro) nunca entra aqui - passa batido, de proposito.
    """
    requisitos = dados.get("requisitos_atendidos")
    if requisitos is not None and not isinstance(requisitos, dict):
        return f"requisitos_atendidos precisa ser um mapa (recebeu {type(requisitos).__name__})"
    for campo in _CAMPOS_MONETARIOS_PARTICIPACAO:
        valor = dados.get(campo)
        if valor is None:
            continue
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return f"{campo} precisa ser numero (recebeu {valor!r})"
        if not math.isfinite(valor):
            return f"{campo} nao e um numero finito (recebeu {valor!r})"
    for campo in _CAMPOS_TEXTO_PARTICIPACAO:
        valor = dados.get(campo)
        if valor is not None and not isinstance(valor, str):
            return f"{campo} precisa ser texto (recebeu {type(valor).__name__})"
    return None


def _participacao_invalida(dados: Any, produto_id: str) -> str | None:
    """Contrato minimo de uma participacao no formato novo, ja sabendo que
    `dados` e um mapa YAML NAO VAZIO (`_classificar_participacao` decide
    isso antes de chamar). Usado por `read_participation` (decidir se o
    arquivo em disco e autoridade sobre o estado) e por `migrate_products`
    (decidir se pode limpar a ficha legada por cima dele).

    Exige IDENTIDADE (`produto_id`, tem que bater com o proprio arquivo que
    o contem - nunca o de outro produto), ESTADO (dentro do vocabulario
    conhecido, `ESTADOS_PARTICIPACAO`) e TIPO dos campos opcionais conhecidos
    quando presentes (`_tipo_invalido_participacao`). Os demais campos
    (preco-alvo/teto, requisitos, motivo de descarte...) continuam opcionais
    por natureza quando AUSENTES - uma participacao recem-criada por
    `vincular-produto` nao tem nenhum deles ainda, e isso e valido. Campo
    desconhecido (schema futuro) tambem nunca invalida por si so.

    Devolve `None` quando valida, ou o motivo (texto curto, pra diagnostico)
    quando nao.
    """
    if dados.get("produto_id") != produto_id:
        return f"produto_id gravado ({dados.get('produto_id')!r}) diverge do arquivo ({produto_id!r})"
    if dados.get("estado") not in ESTADOS_PARTICIPACAO:
        return (
            f"estado {dados.get('estado')!r} fora do vocabulario conhecido "
            f"({', '.join(ESTADOS_PARTICIPACAO)})"
        )
    return _tipo_invalido_participacao(dados)


def _classificar_participacao(dados: Any, produto_id: str) -> tuple[str, str | None]:
    """Classifica o CONTEUDO BRUTO (ja carregado por `read_yaml(path, None)`)
    de um arquivo de participacao - ponto UNICO usado por `read_participation`
    e por `migrate_products`, para as duas nunca divergirem sobre o mesmo
    arquivo.

    Devolve `(status, motivo)`:
    - `("vazio", None)`: arquivo nao existe, ou existe mas nao tem NENHUM
      dado (0 bytes / `null` explicito viram `None` apos o parse do YAML, ou
      mapa vazio `{}`). Nunca houve escrita real; seguro tratar como se a
      participacao nunca tivesse sido criada (cai para o legado ou default).
    - `("valida", None)`: mapa YAML que passa no contrato minimo
      (`_participacao_invalida` devolve `None`).
    - `("invalida", motivo)`: tem CONTEUDO (uma lista, uma string, um mapa
      com identidade/estado/tipo errado...) mas nao e utilizavel. Difere de
      "vazio" de proposito - uma lista YAML com estado e motivo de descarte
      de verdade NAO e "arquivo sem dado", e tratar as duas a mesma coisa
      foi exatamente o bug que apagou evidencia por cima de conteudo real.
      Quem chama tem que diagnosticar e recusar autoridade, preservando os
      arquivos, nunca reescrever por cima.
    """
    if dados is None:
        return "vazio", None
    if isinstance(dados, dict) and not dados:
        return "vazio", None
    if not isinstance(dados, dict):
        return "invalida", f"conteudo nao e um mapa YAML (tipo {type(dados).__name__})"
    motivo = _participacao_invalida(dados, produto_id)
    if motivo:
        return "invalida", motivo
    return "valida", None


def _participation_from_legacy_ficha(produto_id: str, ficha: dict[str, Any]) -> dict[str, Any]:
    base = default_participation(produto_id)
    for key in _PARTICIPATION_LEGACY_KEYS:
        if key in ficha and ficha[key] is not None:
            base[key] = ficha[key]
    return base


def read_participation(project: Path, produto_id: str) -> dict[str, Any]:
    """Participacao deste produto NESTE projeto - nunca None.

    Tres caminhos, pela classificacao de `_classificar_participacao`:
    - "valida": o arquivo proprio sempre vence.
    - "vazio" (arquivo ausente, 0 bytes, ou mapa vazio): cai para os campos
      legados da ficha (so se ela ainda aponta pra ESTE projeto, nunca para
      outro) ou o default neutro (`pesquisando`) - igual a antes.
    - "invalida" (TEM conteudo, mas incoerente - identidade errada, estado
      desconhecido, tipo de campo invalido): NUNCA cai para o legado nem
      para o default neutro. Um estado legado mais antigo, ou "pesquisando"
      fabricado, reabilitaria silenciosamente um candidato cujo ultimo
      estado CONHECIDO podia ser `descartado`. Devolve o estado sintetico
      `invalido` (fora de `ESTADOS_PARTICIPACAO`, nunca gravavel por
      nenhum comando) com o motivo em `_motivo_invalido` - os consumidores
      (`gate_eliminations`, `validation_report`) tratam isso como "nao
      decido sozinho", nunca como elegivel nem como descarte confirmado.
    """
    dados = read_yaml(participation_path(project, produto_id), None)
    status, motivo = _classificar_participacao(dados, produto_id)
    if status == "valida":
        base = default_participation(produto_id)
        base.update(dados)
        return base
    if status == "invalida":
        base = default_participation(produto_id)
        base["estado"] = ESTADO_PARTICIPACAO_INVALIDA
        base["_motivo_invalido"] = motivo
        return base
    ficha_path = find_product_path(produto_id)
    ficha = read_yaml(ficha_path, {}) if ficha_path else {}
    if ficha.get("projeto") == project.name:
        return _participation_from_legacy_ficha(produto_id, ficha)
    return default_participation(produto_id)


def _recusar_se_participacao_invalida(project: Path, produto_id: str) -> None:
    """Recusa ANTES de qualquer escrita quando o arquivo de participacao em
    disco tem conteudo invalido (`_classificar_participacao` == "invalida").

    `descartar`/`aguardar-preco` mudam so um punhado de campos (estado,
    motivo, preco-alvo/teto) sobre o dict que `read_participation` devolve
    - mas para participacao invalida esse dict e SINTETICO (so defaults +
    o estado `invalido`), nunca o conteudo real do arquivo. Deixar esses
    comandos prosseguirem gravaria o sintetico por cima do real via
    `write_participation`, apagando preco-alvo/teto, requisitos e qualquer
    campo desconhecido que so existia no arquivo - o diagnostico nunca pode
    virar BASE para reconstruir dado. A reconciliacao e sempre manual:
    corrigir ou apagar o arquivo a mao, olhando o conteudo real.
    """
    dados = read_yaml(participation_path(project, produto_id), None)
    status, motivo = _classificar_participacao(dados, produto_id)
    if status == "invalida":
        raise SystemExit(
            f"Participacao de {produto_id} em {project.name} tem conteudo invalido "
            f"({motivo}).\nArquivo: {participation_path(project, produto_id)}\n"
            "Nao decido sozinho se e dado real incompleto ou lixo - corrija ou apague "
            "o arquivo a mao (preservando o que for dado real) e rode o comando de novo. "
            "Nada foi alterado."
        )


def _participacao_serializavel(dados: dict[str, Any]) -> dict[str, Any]:
    """Remove campos sinteticos internos (prefixo `_` - hoje so
    `_motivo_invalido`, o diagnostico que `read_participation` anexa quando
    o arquivo em disco tem conteudo invalido) antes de qualquer escrita.
    Nunca gravar isso em disco: nem no proprio arquivo de participacao, nem
    no snapshot congelado de uma decisao (evidencia, nao rascunho de
    diagnostico).
    """
    return {key: value for key, value in dados.items() if not key.startswith("_")}


def write_participation(project: Path, produto_id: str, dados: dict[str, Any]) -> None:
    """Grava participacao completa (defaults preenchidos) no arquivo proprio.

    Recusa gravar o estado sintetico (`ESTADO_PARTICIPACAO_INVALIDA`) como
    dado persistente - ele so existe para os CONSUMIDORES de leitura
    (`gate_eliminations`, `validation_report`) reconhecerem "nao decido
    sozinho"; nenhum comando de escrita pode fabricar essa palavra em disco.
    Defesa em profundidade: os chamadores que MUDAM estado (`descartar`,
    `aguardar-preco`) ja recusam antes de chegar aqui
    (`_recusar_se_participacao_invalida`), mas esta funcao e o unico lugar
    que efetivamente grava - nunca confia sozinho no chamador ter checado.
    """
    if dados.get("estado") == ESTADO_PARTICIPACAO_INVALIDA:
        raise SystemExit(
            f"Bug interno: tentativa de gravar o estado sintetico "
            f"{ESTADO_PARTICIPACAO_INVALIDA!r} em "
            f"{participation_path(project, produto_id)} - isso nunca pode virar dado "
            "persistente. Nada foi escrito."
        )
    path = participation_path(project, produto_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    completo = default_participation(produto_id)
    completo.update(_participacao_serializavel(dados))
    write_yaml(path, completo)


def projetos_participantes(produto_id: str) -> set[str]:
    """Nomes dos projetos onde este produto_id tem participacao (novo formato
    ou legado). Usado para resolver `--projeto` implicito sem ambiguidade."""
    nomes: set[str] = set()
    for projeto in project_dirs():
        if participation_path(projeto, produto_id).exists():
            nomes.add(projeto.name)
    ficha_path = find_product_path(produto_id)
    if ficha_path:
        legado = read_yaml(ficha_path, {}).get("projeto")
        if legado and (PROJETOS / str(legado)).exists():
            nomes.add(str(legado))
    return nomes


def resolve_participation_project(produto_id: str, projeto_arg: str | None) -> Path:
    """Projeto que um comando de participacao (descartar/aguardar-preco) vai
    tocar. `--projeto` explicito sempre vence. Sem ele, exige EXATAMENTE um
    projeto participante - ambiguo ou ausente e recusado, sem escrever nada.
    """
    if projeto_arg:
        return project_path(projeto_arg)
    candidatos = sorted(projetos_participantes(produto_id))
    if len(candidatos) == 1:
        return project_path(candidatos[0])
    if not candidatos:
        raise SystemExit(
            f"{produto_id} nao tem participacao registrada em nenhum projeto. Use --projeto."
        )
    raise SystemExit(
        f"{produto_id} participa de mais de um projeto ({', '.join(candidatos)}) - "
        "use --projeto para dizer qual participacao alterar. Nada foi alterado."
    )


def project_candidate_ids(project: Path) -> set[str]:
    """Todo produto_id ativo (nao descartado) com participacao neste projeto,
    com ou sem cotacao - novo formato tem precedencia; fichas antigas nao
    migradas (campo `projeto` na propria ficha) continuam contando enquanto
    nao tiverem participacao gravada aqui.

    Participacao no formato novo passa por `read_participation` (nunca
    `estado` bruto do arquivo) - o mesmo contrato usado pelo ranking, para
    esta lista nunca discordar dele sobre o mesmo candidato. Participacao
    com conteudo invalido nao entra aqui NEM em
    `project_discarded_candidate_ids`: nao e "ativo" confirmado, mas
    tambem nao e "descartado" confirmado - fica de fora dos dois ate
    reconciliar.
    """
    ids: set[str] = set()
    migrados: set[str] = set()
    pasta = participations_dir(project)
    if pasta.exists():
        for path in pasta.glob("*.yaml"):
            produto_id = path.stem
            migrados.add(produto_id)
            estado = read_participation(project, produto_id).get("estado")
            if estado not in ("descartado", ESTADO_PARTICIPACAO_INVALIDA):
                ids.add(produto_id)
    for path in PRODUTOS.glob("*/*/produto.yaml"):
        produto_id = path.parent.name
        if produto_id in migrados:
            continue
        dados = read_yaml(path, {})
        if dados.get("projeto") == project.name and dados.get("estado") != "descartado":
            ids.add(produto_id)
    return ids


def project_discarded_candidate_ids(project: Path) -> set[str]:
    """Descartados conhecidos neste projeto, inclusive os que ainda aparecem
    em cotacoes. Mesma precedencia novo-formato-primeiro de
    `project_candidate_ids`, e mesmo cuidado com participacao invalida (ver
    docstring daquela funcao) - nunca conta como descartado so porque um
    campo bruto qualquer diz `descartado` sem passar pelo contrato minimo.
    """
    ids: set[str] = set()
    migrados: set[str] = set()
    pasta = participations_dir(project)
    if pasta.exists():
        for path in pasta.glob("*.yaml"):
            produto_id = path.stem
            migrados.add(produto_id)
            if read_participation(project, produto_id).get("estado") == "descartado":
                ids.add(produto_id)
    for path in PRODUTOS.glob("*/*/produto.yaml"):
        produto_id = path.parent.name
        if produto_id in migrados:
            continue
        dados = read_yaml(path, {})
        if dados.get("projeto") == project.name and dados.get("estado") == "descartado":
            ids.add(produto_id)
    return ids


def set_process_state(project: Path, *, estado: str | None = None, proxima_acao: str | None = None, decisao_aberta: str | None = None) -> None:
    if _SOURCES_FROZEN.get():
        return
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
            text = re.sub(pattern, lambda _: replacement, text)
        else:
            text = text.replace("## Estado atual\n", f"## Estado atual\n\n{replacement}\n", 1)
    atomic_write_text(path, text)


def mark_steps(project: Path, steps: list[int]) -> None:
    if _SOURCES_FROZEN.get():
        return
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
    data_coleta = args.data or now_iso()
    # getattr com o mesmo default do argparse: chamadores que montam
    # Namespace na mao (comuns nos testes) nao precisam saber destes campos
    # novos pra continuar funcionando - cai no default real da CLI.
    origem_dados = getattr(args, "origem_dados", "observacao_direta") or "observacao_direta"
    evidencia = getattr(args, "evidencia", "") or ""
    # Proveniencia da coleta: preco/variacao/vendedor/frete/garantia sempre
    # tem um valor nesta linha (mesmo que seja o default do CLI, como
    # frete=0 ou garantia_tipo=nenhuma - isso E o que foi observado agora,
    # nao uma lacuna). estoque so vira "conferido" se --estoque foi de fato
    # informado; sem isso, nao ha base nenhuma pra alegar que se sabe o
    # estoque.
    estoque = getattr(args, "estoque", "") or ""
    proveniencia = {}
    for campo in ("preco", "variacao", "vendedor", "frete", "garantia"):
        marcar_proveniencia(proveniencia, campo, origem_dados, evidencia, data_coleta)
    if estoque:
        marcar_proveniencia(proveniencia, "estoque", origem_dados, evidencia, data_coleta)
    row = {
        "data_coleta": data_coleta,
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
        "estoque": estoque,
        "proveniencia": serializar_proveniencia(proveniencia),
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


def append_timeline(project: Path, etapa: str = "", decisao: str = "", porque: str = "", *,
                     data: str | None = None, linha: str | None = None) -> None:
    """`data` default e `today()` no momento da chamada - suficiente pra
    quem grava e conclui na mesma tentativa. Quem participa de recuperacao
    entre tentativas (`registrar_efeito`) precisa congelar a data e passar
    explicitamente aqui, senao uma retomada em outro dia escreve uma linha
    com data diferente da que a assinatura do efeito esta procurando, e
    nunca reconhece o efeito como ja feito - duplicando a cada retomada.

    `linha`, se informado, e o conteudo INTEIRO da linha da tabela (com os
    pipes das pontas, sem quebra de linha) - ignora `etapa`/`decisao`/
    `porque`/`data` e e escrito literalmente. Existe pra quem precisa
    reaproveitar um texto JA CONGELADO (`OperationHandle.efeito_congelado`)
    em vez de reconstrui-lo com dado atual - ver `link_product`. Congelar
    so a data (`data=`) nao basta quando outro ingrediente da linha (o nome
    do produto, por exemplo) tambem pode mudar entre tentativas."""
    path = project / "processo.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    line = (linha if linha is not None else f"| {data or today()} | {etapa} | {decisao} | {porque} |") + "\n"
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


def find_product(produto_id: str, project: Path | None = None) -> dict[str, Any] | None:
    """Ficha do produto - identidade e dado tecnico, sempre.

    `project` e opcional de proposito (identidade nao depende de projeto: nome,
    marca e atributos sao os mesmos em qualquer compra). Quando informado, o
    dict devolvido tambem inclui a PARTICIPACAO deste produto NAQUELE projeto
    (estado, descarte, preco-alvo/teto, requisitos atendidos) - esta e a UNICA
    funcao que faz essa juncao; todo consumidor que precisa saber "descartado
    ou nao", "aguardando preco" etc. passa `project` em vez de ler a ficha
    crua, para nunca misturar participacao de um projeto com a de outro.
    """
    path = find_product_path(produto_id)
    if not path:
        return None
    ficha = read_yaml(path, {})
    if project is None:
        return ficha
    participacao = read_participation(project, produto_id)
    merged = dict(ficha)
    merged.update({key: value for key, value in participacao.items() if key != "produto_id"})
    return merged


def latest_quotes(
    rows: list[dict[str, str]],
    prefer: Callable[[dict[str, str]], bool] | None = None,
) -> dict[str, dict[str, str]]:
    """Cotacao que representa cada produto no ranking.

    Manual vale mais que web porque foi conferida. Mas manual VENCIDA nao vale
    mais que uma observacao recente: preferir cegamente a manual fazia um preco
    de dois anos atras rankear no lugar do de hoje. Quando a manual venceu,
    usa a observacao mais recente e o ranking avisa que ela e estimativa.

    Quando quem chama informa `prefer`, a escolha dentro do mesmo nivel de
    prioridade privilegia a cotacao que passa no gate; so depois desempata por
    data e custo. Isso evita que uma observacao recente, mas inutil para a
    decisao, esconda outra cotacao igualmente fresca e elegivel.
    """

    def choose(values: list[dict[str, str]], *, prefer_cost_tiebreak: bool = True) -> dict[str, str]:
        preferred = [row for row in values if prefer and prefer(row)]
        pool = preferred or values
        chosen = pool[-1]
        if prefer_cost_tiebreak and preferred:
            same_date = [row for row in pool if str(row.get("data_coleta") or "") == str(chosen.get("data_coleta") or "")]
            positive_costs = [quote_float(row.get("custo_total")) for row in same_date if quote_float(row.get("custo_total")) > 0]
            if positive_costs:
                cheapest = min(positive_costs)
                cheapest_rows = [row for row in same_date if quote_float(row.get("custo_total")) == cheapest]
                chosen = cheapest_rows[-1]
        return chosen

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
            latest[produto_id] = choose(manual_no_prazo)
            continue
        recentes = [row for row in por_data if not quote_is_stale(row)]
        if recentes:
            latest[produto_id] = choose(recentes)
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


@read_session
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
        product = find_product(produto_id, project)
        if not product:
            errors.append(f"Produto citado em cotacao nao existe em `produtos/`: {produto_id}")
            continue
        missing_attrs = product_required_attrs(product, briefing)
        if missing_attrs:
            warnings.append(f"{produto_id}: atributos obrigatorios ausentes: {', '.join(missing_attrs)}")
        if product.get("estado") == "descartado" and not product.get("descartado_porque"):
            errors.append(f"{produto_id}: produto descartado sem motivo.")
        if product.get("estado") == ESTADO_PARTICIPACAO_INVALIDA:
            errors.append(
                f"{produto_id}: participacao com conteudo invalido "
                f"({product.get('_motivo_invalido')}) - requer reconciliacao manual antes de decidir."
            )

    # Participacao invalida sem NENHUMA cotacao ainda nao passa pelo loop
    # acima (que so cobre `latest`) - sem isto, o candidato some do ranking
    # (gate_eliminations) e some de "candidatos sem cotacao" (excluido de
    # `project_candidate_ids`), mas a validacao nunca avisa por que.
    pasta_participacoes = participations_dir(project)
    if pasta_participacoes.exists():
        for path in sorted(pasta_participacoes.glob("*.yaml")):
            produto_id = path.stem
            if produto_id in latest:
                continue
            participacao = read_participation(project, produto_id)
            if participacao.get("estado") == ESTADO_PARTICIPACAO_INVALIDA:
                errors.append(
                    f"{produto_id}: participacao com conteudo invalido "
                    f"({participacao.get('_motivo_invalido')}) - requer reconciliacao manual antes de decidir."
                )

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
        if regra["produtos_sem_cotacao_presencial"]:
            warnings.append("Regra de parada: falta cotacao manual presencial para: "
                            + ", ".join(regra["produtos_sem_cotacao_presencial"]))
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
    if categoria_projeto not in read_yaml(CONFIG / "categorias.yaml", {}):
        warnings.append(f"Categoria `{categoria_projeto}` sem configuracao propria: usa regras genericas. Revise atributos e gates.")
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
    sem_cotacao: bool = False


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
    elif product.get("estado") == ESTADO_PARTICIPACAO_INVALIDA:
        # Participacao com conteudo invalido nunca pode ser elegivel: seria
        # decidir sobre dado que ninguem confirmou. Tambem nunca vira
        # "descartado" (ramo acima) - isso fabricaria um motivo de descarte
        # que ninguem escreveu. Fica cortada ate a reconciliacao manual.
        motivo = product.get("_motivo_invalido") or "participacao com conteudo invalido"
        eliminations.append(f"participacao invalida, requer reconciliacao manual ({motivo})")

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


@read_session
def compute_ranking(project: Path) -> tuple[list[Ranked], list[Ranked]]:
    briefing, _ = load_frontmatter(project / "briefing.md")
    rows = read_quotes(project)

    def passes_gate(row: dict[str, str]) -> bool:
        produto_id = row.get("produto_id", "")
        product = find_product(produto_id, project) or {"id": produto_id, "categoria": briefing.get("categoria"), "marca": ""}
        return not gate_eliminations(row, product, briefing)

    latest = latest_quotes(rows, prefer=passes_gate)
    weights = preferences().get("score", {})
    pre_candidates: list[tuple[str, dict[str, str], dict[str, Any], list[str], list[str]]] = []
    for produto_id, row in latest.items():
        product = find_product(produto_id, project) or {"id": produto_id, "categoria": briefing.get("categoria"), "marca": ""}
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


def sem_cotacao_candidates(project: Path, categoria: str, known: list[Ranked]) -> list[Ranked]:
    """Candidatos mapeados (`novo-produto`) que ainda nao tem nenhuma cotacao.

    Aparecem no comparativo com os atributos ja conhecidos e "-" nos campos
    comerciais (preco, nota, garantia...), nunca um valor inventado - assim
    a pesquisa em andamento fica visivel na tabela em vez de sumir ate a
    primeira cotacao chegar.
    """
    conhecidos = {item.produto_id for item in known}
    faltando = sorted(project_candidate_ids(project) - conhecidos)
    itens: list[Ranked] = []
    for produto_id in faltando:
        product = find_product(produto_id, project) or {"id": produto_id, "categoria": categoria, "marca": ""}
        itens.append(
            Ranked(
                produto_id,
                {},
                product,
                {},
                0.0,
                [],
                [],
                [],
                None,
                False,
                0.0,
                score_breakdown({}, [], {}),
                sem_cotacao=True,
            )
        )
    return itens


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
    if rows:
        mark_steps(project, [5])
    if len(elegiveis) >= 2:
        mark_steps(project, [6])
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
            "--preco-promocional": args.preco_promocional,
            "--custo-total": args.custo_total,
            "--frete": args.frete,
            "--vendedor": args.vendedor,
            "--link": args.link,
            "--garantia-meses": args.garantia_meses,
        }.items()
        if valor is not None
    ]
    # Quais dos 6 campos de proveniencia esta promocao de fato conferiu -
    # so esses ganham proveniencia nova; o resto herda o que a cotacao base
    # ja tinha (confirmacao parcial nao pode virar "conferido" pra tudo).
    campos_proveniencia_confirmados = {
        "preco": args.preco is not None or args.preco_promocional is not None or args.custo_total is not None,
        "variacao": args.variacao is not None,
        "vendedor": args.vendedor is not None or args.vendedor_tipo is not None,
        "frete": args.frete is not None or args.frete_prazo_dias is not None,
        "estoque": getattr(args, "estoque", None) is not None,
        "garantia": args.garantia_meses is not None or args.garantia_tipo is not None,
    }
    if not confirmados and not args.sem_alteracao:
        raise SystemExit(
            "Promover para `manual` exige dizer o que voce conferiu no site agora.\n"
            "Informe ao menos um entre --preco, --custo-total, --frete, --vendedor, "
            "--link ou --garantia-meses.\n"
            "Se conferiu e estava tudo igual ao que ja estava registrado, "
            "use --sem-alteracao para declarar isso explicitamente."
        )

    if not args.sem_alteracao and all(
        value is None for value in (args.preco, args.preco_promocional, args.custo_total)
    ):
        raise SystemExit(
            "Confirme o preco com --preco, --preco-promocional ou --custo-total. "
            "Conferir apenas link, vendedor ou garantia nao renova o preco. "
            "Se conferiu tudo e continua igual, use --sem-alteracao."
        )
    if args.preco is not None and args.preco_promocional is None and quote_float(base.get("preco_promocional")):
        raise SystemExit(
            "A cotacao base tem desconto. Informe --preco-promocional com o valor confirmado "
            "ou --preco-promocional 0 se a promocao acabou; --preco e o preco de etiqueta."
        )

    row = dict(base)
    data_coleta = args.data or now_iso()
    row["data_coleta"] = data_coleta
    row["fonte"] = "manual"
    # Proveniencia: comeca herdando a da cotacao base (nao inventa nada
    # novo pros campos nao tocados) e so marca como conferido agora o que
    # este `promover-cotacao` de fato recebeu. --sem-alteracao e a unica
    # excecao: e uma reconfirmacao TOTAL declarada, entao os 6 campos
    # viram conferidos com a origem/evidencia informadas (ou o default
    # conferencia_humana).
    origem_dados = getattr(args, "origem_dados", None) or "conferencia_humana"
    evidencia = getattr(args, "evidencia", "") or ""
    proveniencia = parse_proveniencia(base)
    for campo in PROVENIENCIA_CAMPOS:
        if args.sem_alteracao or campos_proveniencia_confirmados.get(campo):
            marcar_proveniencia(proveniencia, campo, origem_dados, evidencia, data_coleta)
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
        "estoque": getattr(args, "estoque", None),
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
    row["proveniencia"] = serializar_proveniencia(proveniencia)

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
    if not find_product_path(args.produto_id):
        raise SystemExit(f"Produto nao encontrado: {args.produto_id}")
    # Projeto resolvido e a operacao recusada ANTES de qualquer escrita se for
    # ambigua (produto participando de mais de um projeto sem --projeto): a
    # participacao e por projeto, nunca um estado global do produto.
    project = resolve_participation_project(args.produto_id, args.projeto)
    _recusar_se_participacao_invalida(project, args.produto_id)
    participacao = read_participation(project, args.produto_id)
    participacao["estado"] = "descartado"
    participacao["descartado_porque"] = args.porque
    write_participation(project, args.produto_id, participacao)
    append_timeline(project, "descarte", f"Descartado {args.produto_id}", args.porque)
    build_ranking(argparse.Namespace(projeto=str(project)))
    elegiveis, _ = compute_ranking(project)
    if not elegiveis:
        print("Proxima acao mantida: nenhum candidato elegivel apos descarte.")
    print(f"Descartado: {args.produto_id} em {project.name}")


def wait_price(args: argparse.Namespace) -> None:
    if not find_product_path(args.produto_id):
        raise SystemExit(f"Produto nao encontrado: {args.produto_id}")
    project = resolve_participation_project(args.produto_id, args.projeto)
    _recusar_se_participacao_invalida(project, args.produto_id)
    participacao = read_participation(project, args.produto_id)
    participacao["estado"] = "aguardando_preco"
    if args.preco_alvo is not None:
        participacao["preco_alvo"] = args.preco_alvo
    if args.preco_teto is not None:
        participacao["preco_teto"] = args.preco_teto
    participacao["aguardando_preco_porque"] = args.porque
    participacao["aguardando_preco_desde"] = today()
    write_participation(project, args.produto_id, participacao)
    append_timeline(project, "aguardando_preco", f"{args.produto_id} aguardando preco", args.porque)
    set_process_state(project, proxima_acao="reconsultar itens em aguardando_preco antes de decidir")
    print(f"Aguardando preco: {args.produto_id} em {project.name}")


def waiting_price_rows() -> list[dict[str, Any]]:
    """Um item por (projeto, produto) em `aguardando_preco` - nunca por
    produto sozinho: o mesmo produto pode estar aguardando preco num projeto
    e nem participar de outro. Le pela juncao unica ficha+participacao
    (`find_product` com `project`), nunca pela ficha crua."""
    rows: list[dict[str, Any]] = []
    for project in project_dirs():
        for produto_id in project_candidate_ids(project):
            product = find_product(produto_id, project)
            if not product or product.get("estado") != "aguardando_preco":
                continue
            quote = latest_quotes(read_quotes(project)).get(produto_id)
            atual = quote_float(quote.get("custo_total")) if quote else 0
            alvo = quote_float(product.get("preco_alvo"))
            teto = quote_float(product.get("preco_teto"))
            rows.append(
                {
                    "produto_id": produto_id,
                    "nome": product.get("nome"),
                    "categoria": product.get("categoria"),
                    "projeto": project.name,
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
    modelo = project / "01-definir-modelo.md"
    modelo_texto = modelo.read_text(encoding="utf-8") if modelo.exists() else "Ainda nao definido."
    candidatos = [find_product(pid, project) or {"id": pid} for pid in sorted(project_product_ids(project))]
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

Definicao de modelo registrada:
{modelo_texto}

Candidatos ja mapeados (amostra pesquisada, nao universo completo):
{json.dumps(candidatos, ensure_ascii=False, default=str)}

Protocolo de pesquisa e evidencia:
- Compare geracoes atuais, antecessores e variantes regionais; registre data, fonte e modelo exato.
- Procure alternativas ausentes da lista; explique inclusoes e exclusoes. O ranking nao descobre candidatos.
- Separe fabricante, oferta observada, relato de usuario e inferencia de IA. Nao invente verificacao.
- Relatorio de IA externa entra como fonte=web. So marque manual apos conferencia da oferta exata.
- Confirme variacao, vendedor, estoque, preco final, frete, garantia e devolucao antes de pagar.
- Confianca do score mede cobertura de campos, nao veracidade, cobertura do mercado ou probabilidade de acerto.
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
6. 3 a 5 candidatos iniciais e lacunas da pesquisa, incluindo geracoes/variantes a verificar.
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


def _veredito_existente_para(project: Path, produto_id: str) -> Path | None:
    """Localiza o veredito ja existente desta decisao, pela IDENTIDADE
    gravada no CONTEUDO (bullets `Projeto`/`Produto ID`) - nunca pelo nome
    do arquivo, que comeca pela data de quem o CRIOU e por isso nao serve
    para reidentificar o mesmo veredito numa chamada de OUTRO dia (achado
    da 4a revisao independente da frente 6: `decidir --comprado` como "2a
    chamada", so pra confirmar uma compra que chegou depois da decisao, so
    complementava o veredito existente quando a 2a chamada caia no MESMO
    dia da 1a - em outro dia, `{today()}-{projeto}-{produto}.md` nunca
    batia com o arquivo real).

    Devolve `None` quando nenhum veredito bate essa identidade - decisao
    nova, ainda sem veredito, comportamento inalterado. Levanta
    `SystemExit` quando MAIS DE UM bate - nunca escolhe um dos dois
    arbitrariamente; a ambiguidade e reportada aqui, ANTES de qualquer
    escrita (journal, decisao.md, processo.md, veredito), para
    reconciliacao manual. Vereditos standalone (`novo-veredito`, sem
    `Produto ID` gravado) nunca entram aqui - a comparacao exige o campo
    preenchido e igual ao `produto_id` desta chamada.
    """
    if not produto_id or not VEREDITOS.is_dir():
        return None
    encontrados = []
    for candidato in sorted(VEREDITOS.glob("*.md")):
        texto = candidato.read_text(encoding="utf-8")
        if (extract_bullet(texto, "Projeto") == project.name
                and extract_bullet(texto, "Produto ID") == produto_id):
            encontrados.append(candidato)
    if len(encontrados) > 1:
        nomes = ", ".join(p.name for p in encontrados)
        raise SystemExit(
            f"Mais de um veredito encontrado para {project.name}/{produto_id}: {nomes}.\n"
            "Nao da para saber qual e o veredito desta decisao sem ambiguidade - nada foi "
            "alterado. Confira o conteudo de cada arquivo e renomeie ou apague manualmente "
            "o duplicado indevido antes de continuar."
        )
    return encontrados[0] if encontrados else None


def decide(args: argparse.Namespace) -> None:
    if args.data_compra and not args.comprado:
        raise SystemExit(
            "--data-compra so faz sentido junto de --comprado - decidir sozinho nunca "
            "comprova pagamento. Adicione --comprado, ou registre a compra depois com "
            "`registrar-evento` quando ela de fato acontecer."
        )
    project = project_path(args.projeto)
    # Gate, confianca e snapshot precisam se referir a MESMA oferta. Selecionar
    # de novo sem a preferencia do ranking podia fechar outra loja/preco ou
    # exigir bypass apesar de existir uma cotacao elegivel no ranking.
    elegiveis, cortados = compute_ranking(project)
    ranqueado = next(
        (item for item in [*elegiveis, *cortados] if item.produto_id == args.produto_id),
        None,
    )
    if ranqueado is None:
        raise SystemExit(f"Nenhuma cotacao encontrada para {args.produto_id}")
    quote = ranqueado.quote
    # Reaproveita o MESMO dict que o ranking usou para este projeto (ja
    # mescla ficha + participacao) em vez de reler a ficha crua - evita
    # decidir com base num estado de OUTRO projeto se o produto participar
    # de mais de um.
    product = ranqueado.product or {"nome": args.produto_id}
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

    # `decidir` grava snapshot, decisao.md, processo.md (duas vezes) e o
    # veredito numa unica chamada. Cada gravacao e atomica por si so, mas a
    # sequencia nao e: uma falha no meio e uma repeticao do comando podia
    # duplicar linha em `processo.md` ou criar um segundo snapshot orfao.
    #
    # `assinatura` congela os dados de ENTRADA desta tentativa: uma retomada
    # com produto_id igual mas preco/justificativa/perdedores diferentes e
    # recusada por `tracked_operation`, em vez de misturar passo velho com
    # dado novo. `detalhe_inicial` congela o CAMINHO do snapshot: uma
    # retomada reusa o mesmo diretorio, em vez de criar outro a cada retry.
    quote_canonical = json.dumps(quote, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    quote_hash = hashlib.sha256(quote_canonical.encode("utf-8")).hexdigest()
    assinatura = {
        "quote_sha256": quote_hash,
        "porque": args.porque,
        "perdedores": sorted(perdedores),
        "sem_perdedores": bool(args.sem_perdedores),
        "comprado": bool(args.comprado),
        "data_compra": args.data_compra,
        "risco": sorted(args.risco or []),
        "force_veredito": bool(args.force_veredito),
        "flags": {
            flag: bool(getattr(args, flag, False))
            for flag in ("permitir_web", "permitir_cortado", "permitir_vencida",
                         "permitir_aguardando", "permitir_incompleto")
        },
    }
    instante = dt.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    snapshot_rel_candidato = f"snapshots/{instante}-{slugify(args.produto_id)}"
    op_id = f"decidir:{args.produto_id}"
    # O nome do veredito e congelado AQUI (nao recalculado dentro de
    # `_decide_writes`) pelo mesmo motivo do snapshot: numa retomada, tem
    # que ser o MESMO arquivo da tentativa que falhou, nao um recalculado
    # com `today()` de um dia diferente - `tracked_operation` ja garante
    # isso reusando `op.detalhe` congelado, entao o candidato calculado
    # aqui so importa para uma operacao NOVA.
    #
    # Achado da 4a revisao independente: numa chamada NOVA que NAO e
    # retomada (`decidir --comprado` como "2a chamada", pra so confirmar
    # uma compra que chegou depois da decisao - o fluxo mais comum, ja que
    # raramente se paga no mesmo instante que se decide), o candidato
    # `{today()}-{projeto}-{produto}.md` so bate com o veredito JA
    # existente quando as duas chamadas caem no MESMO DIA. Em outro dia,
    # sem isso, criava um segundo veredito orfao (em vez de complementar o
    # real) e a checagem de cronologia do achado 4 (abaixo) olhava para um
    # arquivo que nao existia, pulando a validacao inteira. Corrigido:
    # localiza o veredito existente por IDENTIDADE (`Projeto`/`Produto ID`
    # gravados no CONTEUDO, nunca pelo nome do arquivo) via
    # `_veredito_existente_para` - so quando esta chamada NAO e retomada
    # (numa retomada de verdade, o nome congelado em `op.detalhe` sempre
    # vence, e procurar de novo so arriscaria uma ambiguidade irrelevante
    # bloquear uma retomada legitima).
    retomando_decisao = has_pending_operation(project, op_id, "decidir")
    if retomando_decisao:
        veredito_nome_candidato = f"{today()}-{project.name}-{args.produto_id}.md"
    else:
        veredito_existente_atual = _veredito_existente_para(project, args.produto_id)
        veredito_nome_candidato = (
            veredito_existente_atual.name if veredito_existente_atual is not None
            else f"{today()}-{project.name}-{args.produto_id}.md"
        )
    # Mesmo principio para `Data da compra`: `--comprado` sem `--data-compra`
    # explicita cai em `today()`, mas isso so pode ser calculado UMA VEZ, na
    # 1a tentativa - uma interrupcao antes de `create_verdict` rodar e uma
    # retomada em outro dia nao pode trocar a data da confirmacao original
    # pela data da retomada. `None` quando nao comprado (nunca fabrica).
    data_compra_efetiva = (args.data_compra or today()) if args.comprado else None
    # Achado 4: `decidir --comprado` pode COMPLEMENTAR um veredito ja
    # existente (achado da rodada anterior) - mas isso tem que respeitar o
    # MESMO contrato de cronologia que `registrar-evento` ja aplica pros
    # outros eventos, senao da pra gravar uma compra POSTERIOR a um inicio
    # de uso ja registrado. Confere ANTES de tocar em qualquer arquivo
    # (decisao.md, processo.md, snapshot, veredito) - mesmo principio do
    # achado 3 em `registrar-evento`: nunca deixa journal pendente pra
    # tras por causa de uma entrada invalida, e pula a checagem numa
    # retomada legitima (o calendario pode ter avancado; a validacao real
    # ja rodou na tentativa original). Com o candidato agora corrigido
    # (acima), `veredito_existente` aponta pro arquivo REAL quando existe
    # um, em qualquer dia - nao so quando a chamada cai no mesmo dia da
    # criacao.
    if args.comprado and not retomando_decisao:
        veredito_existente = VEREDITOS / veredito_nome_candidato
        if veredito_existente.exists():
            erro = _erro_cronologia_evento(
                veredito_existente.read_text(encoding="utf-8"), "comprado", data_compra_efetiva
            )
            if erro:
                raise SystemExit(erro + " Nada foi alterado.")
    # decisao.md e processo.md sao arquivos UNICOS por projeto, nao por
    # produto: `decidir A` e `decidir B` do mesmo projeto escrevem os dois no
    # MESMO lugar. Sem declarar isso como recurso, uma retomada de A depois
    # de um `decidir B` intercalado reaproveitava a captura (ja concluida)
    # sem perceber que decisao.md tinha sido reescrito por B nesse meio tempo.
    #
    # O arquivo de VEREDITO tambem e escrito por `decidir` (via
    # `create_verdict`), mas fora do proprio projeto, em `vereditos/`.
    # `aprender-veredito` ja reivindica esse mesmo arquivo (rodada anterior);
    # sem `decidir` tambem declara-lo, um `decidir --force-veredito` novo
    # rodava livre enquanto uma exportacao estava pendente naquele veredito
    # e apagava o D+30/D+180 preenchido - a mesma classe de bug que motivou
    # `recursos`, so que decidir nunca tinha declarado esse terceiro arquivo.
    with tracked_operation(project, op_id, "decidir", assinatura,
                            {"snapshot_rel": snapshot_rel_candidato, "veredito_nome": veredito_nome_candidato,
                             "data_compra_efetiva": data_compra_efetiva},
                            recursos={project / "decisao.md", project / "processo.md",
                                      VEREDITOS / veredito_nome_candidato}) as op:
        _decide_writes(args, project, quote, quote_hash, product, cortes, ranqueado, minima,
                        obrigatorios, perdedores, briefing_meta, op)


def _iso_date_prefix(value: Any) -> str | None:
    texto = str(value or "")[:10]
    try:
        dt.date.fromisoformat(texto)
    except ValueError:
        return None
    return texto


def _data_compra_para_decidir(args: argparse.Namespace, op: "OperationHandle") -> str | None:
    if not args.comprado:
        return None
    if args.data_compra:
        return args.data_compra
    congelada = op.detalhe.get("data_compra_efetiva")
    if congelada:
        return congelada
    # Compatibilidade com journals da frente 6 antes de `data_compra_efetiva`:
    # o nome do veredito ja era congelado na tentativa original e comecava pela
    # data que `--comprado` implicito usou. `iniciado_em` fica como segunda
    # evidencia persistida. Nunca cai em `today()` da retomada.
    for evidencia in (op.detalhe.get("veredito_nome"), op.iniciado_em):
        data = _iso_date_prefix(evidencia)
        if data:
            return data
    raise SystemExit(
        "Nao da para retomar `decidir --comprado`: o journal antigo nao contem "
        "data da compra efetiva, nome de veredito datado nem `iniciado_em` valido. "
        "Confira a operacao pendente manualmente antes de prosseguir."
    )


def _decide_writes(args, project, quote, quote_hash, product, cortes, ranqueado, minima,
                    obrigatorios, perdedores, briefing_meta, op: "OperationHandle") -> None:
    # O caminho do snapshot vem congelado em `op.detalhe`: numa retomada e o
    # MESMO diretorio da tentativa anterior, nunca um novo.
    snapshot_dir = project / op.detalhe["snapshot_rel"]

    def _capturar() -> None:
        """Congela ranking, decisao e as entradas que a informaram.

        So roda uma vez por decisao (`op.executar_uma_vez` abaixo). Numa
        retomada com a captura ja concluida, esta funcao NEM E CHAMADA: se
        `config/preferencias.yaml`, `categorias.yaml`, o briefing ou a ficha
        de um candidato mudarem entre a falha e o retry, a evidencia
        congelada continua sendo a de quando a decisao foi tomada de
        verdade, nao a config atual. Recalcular aqui a cada tentativa foi o
        que corrompia o manifesto (recontava um `manifesto.json` que a
        propria tentativa anterior tinha deixado no diretorio) e reescrevia
        o snapshot com dado diferente do que decidiu a compra.
        """
        # O ranking.md antigo nao e evidencia do que o motor calculou agora.
        build_ranking(argparse.Namespace(projeto=args.projeto))
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        excecoes = []
        condicoes = {
            "permitir_web": quote.get("fonte") != "manual",
            "permitir_cortado": bool(cortes),
            "permitir_vencida": quote_is_stale(quote),
            "permitir_aguardando": bool(waiting_gap(product, quote)),
            "permitir_incompleto": bool(obrigatorios or ranqueado.confianca < minima),
        }
        for flag, necessaria in condicoes.items():
            if necessaria and getattr(args, flag, False):
                excecoes.append("--" + flag.replace("_", "-"))
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
                    "schema_versao": 2,
                    "categoria": briefing_meta.get("categoria"),
                    "excecoes": excecoes,
                    "justificativa": args.porque,
                    "riscos_declarados": args.risco or [],
                    "cortes": cortes,
                    "confianca": ranqueado.confianca,
                    "confianca_minima": minima,
                },
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            ) + "\n",
        )

        custo_rotulo = "Custo total confirmado" if quote.get("fonte") == "manual" else "Custo total estimado (fonte=web)"
        lines = [
            "# Decisao",
            "",
            "## Escolhido",
            "",
            f"- Produto: {product.get('nome')}",
            f"- Produto ID: {args.produto_id}",
            f"- Cotacao usada: {quote.get('loja')} / {quote.get('vendedor')}",
            f"- Data: {today()}",
            f"- {custo_rotulo}: {brl(quote.get('custo_total'))}",
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
                *(f"- Excecao efetiva: {flag}. Justificativa: {args.porque}" for flag in excecoes),
                *(f"- Gate ignorado: {corte}" for corte in cortes),
                *(f"- {risco}" for risco in (args.risco or ([] if excecoes else ["Nenhum risco relevante registrado."]))),
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
        # Preserva entradas e justificativa antes de atualizar estado/processo.
        fontes = {
            "decisao.md": project / "decisao.md",
            "briefing.md": project / "briefing.md",
            "modelo.md": project / "01-definir-modelo.md",
            "cotacoes.csv": project / "cotacoes.csv",
            "categorias.yaml": CONFIG / "categorias.yaml",
            "preferencias.yaml": CONFIG / "preferencias.yaml",
            "motor.py": Path(__file__),
        }
        for pid in sorted(project_evidence_participant_ids(project)):
            path = find_product_path(pid)
            if path:
                fontes[f"produtos/{pid}.yaml"] = path
        for nome, path in fontes.items():
            if path.exists():
                atomic_write_text(snapshot_dir / nome, path.read_text(encoding="utf-8"))
        # A participacao (estado, requisitos_atendidos, descartado_porque etc.)
        # e a que o score de fato usou - inclusive quando vem de fallback legado
        # (ficha antiga sem arquivo de participacao proprio). Congelar so a ficha
        # deixava um requisito exclusivo desta compra fora da evidencia: um
        # requisito gravado so na participacao passava no `auditar-decisoes
        # --strict` sem nunca aparecer em nenhum arquivo congelado.
        #
        # Participacao com CONTEUDO INVALIDO (arquivo existe, mas identidade/
        # estado/tipo incoerente) e o caso especial: `read_participation`
        # devolve um dict SINTETICO (so defaults + estado `invalido`) para os
        # consumidores de leitura saberem "nao decido sozinho" - isso e
        # diagnostico, nunca evidencia. Gravar o sintetico no snapshot
        # apagaria a unica copia do dado real do concorrente (preco-alvo/
        # teto, requisitos, campo desconhecido) sem deixar rastro nenhum -
        # `auditar-decisoes --strict` passaria sem a decisao ser
        # reconstruivel a partir do que de fato existia. Congela o arquivo
        # BRUTO, tal como esta em disco, nesse caso - a fonte, nao a
        # interpretacao. Participacao "vazia" (ausente/0 bytes) continua
        # gravando o resultado INTERPRETADO (recupera do legado) - nao ha
        # arquivo bruto ali pra preservar, e essa recuperacao ja e o
        # comportamento estabelecido desde a 2a revisao independente.
        #
        # O inventario usa `project_evidence_participant_ids`, nao
        # `project_product_ids`: um produto com participacao INVALIDA e SEM
        # cotacao nenhuma fica de fora de `project_candidate_ids`/
        # `project_discarded_candidate_ids` de proposito (nao e "ativo" nem
        # "descartado" confirmado), e por isso tambem ficava fora de
        # `project_product_ids` - o loop nunca alcancava nem a ficha nem a
        # participacao desse produto, e `auditar-decisoes --strict` passava
        # sem preservar NENHUM arquivo daquele participante. A funcao nova
        # e um superset so pra fins de EVIDENCIA - nunca usada em ranking,
        # regra de parada ou qualquer lista de candidatos; incluir aqui nao
        # reabilita, nao pontua e nao fabrica descarte.
        (snapshot_dir / "participacoes").mkdir(parents=True, exist_ok=True)
        for pid in sorted(project_evidence_participant_ids(project)):
            destino = snapshot_dir / "participacoes" / f"{pid}.yaml"
            origem = participation_path(project, pid)
            status, _ = _classificar_participacao(read_yaml(origem, None), pid)
            if status == "invalida":
                atomic_write_text(destino, origem.read_text(encoding="utf-8"))
            else:
                write_yaml(destino, _participacao_serializavel(read_participation(project, pid)))
        atomic_write_text(snapshot_dir / "ambiente.json", json.dumps({
            "python": sys.version, "pyyaml": yaml.__version__,
            "argumentos": {key: value for key, value in vars(args).items() if key != "func"},
        }, indent=2, ensure_ascii=True, default=str) + "\n")
        # `manifesto.json` nunca entra no proprio manifesto: numa retomada
        # que precisasse refazer a captura do zero (ela ainda nao tinha
        # concluido), o arquivo de uma tentativa anterior incompleta poderia
        # estar no diretorio, e um manifesto que se auto-descrevesse nunca
        # bateria com o proprio conteudo depois de ser sobrescrito.
        manifesto = {path.relative_to(snapshot_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted(snapshot_dir.rglob("*"))
                     if path.is_file() and path.name != "manifesto.json"}
        atomic_write_text(snapshot_dir / "manifesto.json", json.dumps(manifesto, indent=2, sort_keys=True) + "\n")

    op.executar_uma_vez("captura", _capturar)

    # append_timeline sempre adiciona linha nova; uma repeticao apos falha
    # podia duplicar a mesma linha em `processo.md`. `registrar_efeito`
    # confere se uma ocorrencia NOVA da linha apareceu depois desta tentativa
    # comecar antes de decidir se escreve de novo.
    timeline_path = project / "processo.md"
    op.registrar_efeito(
        "timeline_decisao", timeline_path,
        f"| {today()} | decisao | Escolhido {args.produto_id} | {args.porque} |",
        lambda: append_timeline(project, "decisao", f"Escolhido {args.produto_id}", args.porque),
    )
    mark_steps(project, [8])
    if args.comprado:
        _marcar_projeto_comprado(project)
    else:
        set_process_state(project, proxima_acao="comprar ou marcar como comprado depois da confirmacao final")
    # O caminho vem congelado em `op.detalhe`, igual ao snapshot: precisa
    # ser o MESMO arquivo em qualquer retomada. A CRIACAO em si roda dentro
    # de `executar_uma_vez`: sem isso, uma retomada de `decidir` chamava
    # `create_verdict` de novo, e com `--force-veredito` isso SOBRESCREVIA
    # o veredito com o template em branco - apagando um D+30 que o Josemar
    # tivesse preenchido na janela entre a falha e a retomada.
    verdict_path = VEREDITOS / op.detalhe["veredito_nome"]
    data_compra_final = _data_compra_para_decidir(args, op)
    op.executar_uma_vez(
        "veredito",
        lambda: create_verdict(project, args.produto_id, product, quote,
                                force=args.force_veredito, path=verdict_path,
                                data_compra=data_compra_final),
    )
    op.registrar_efeito(
        "timeline_veredito", timeline_path,
        f"| {today()} | veredito | Arquivo de veredito criado | {verdict_path.name} |",
        lambda: append_timeline(project, "veredito", "Arquivo de veredito criado", verdict_path.name),
    )
    print(project / "decisao.md")
    print(snapshot_dir)
    print(verdict_path)


def audit_decisions(args: argparse.Namespace) -> None:
    """Verifica integridade dos snapshots e contabiliza excecoes sem reescrever historico."""
    projects = [project_path(args.projeto)] if args.projeto else project_dirs()
    problemas, totais = [], {}
    for project in projects:
        for snapshot in sorted((project / "snapshots").glob("*")):
            if not snapshot.is_dir():
                continue
            label = f"{project.name}/{snapshot.name}"
            try:
                meta = json.loads((snapshot / "metadados.json").read_text(encoding="utf-8"))
                canonical = json.dumps(meta["cotacao"], ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                if hashlib.sha256(canonical.encode()).hexdigest() != meta["cotacao_sha256"]:
                    problemas.append(f"{label}: hash da cotacao diverge")
                manifest_path = snapshot / "manifesto.json"
                if not manifest_path.exists():
                    if meta.get("schema_versao", 1) >= 2:
                        problemas.append(f"{label}: manifesto obrigatorio ausente")
                    else:
                        print(f"LEGADO {label}: sem manifesto de entradas; nao prova reproducibilidade completa.")
                else:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if not isinstance(manifest, dict) or not manifest:
                        raise ValueError("manifesto vazio ou invalido")
                    required = {"metadados.json", "decisao.md", "ranking.md", "ranking.csv", "cotacoes.csv",
                                "briefing.md", "categorias.yaml", "preferencias.yaml", "motor.py", "ambiente.json"}
                    if not required.issubset(manifest):
                        problemas.append(f"{label}: manifesto omite entradas obrigatorias")
                    for nome, digest in manifest.items():
                        path = (snapshot / nome).resolve()
                        if not path.is_relative_to(snapshot.resolve()) or not path.is_file():
                            problemas.append(f"{label}: arquivo ausente/invalido: {nome}")
                        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                            problemas.append(f"{label}: arquivo alterado: {nome}")
                for flag in meta.get("excecoes", []):
                    key = f"{meta.get('categoria', '?')} {flag}"
                    totais[key] = totais.get(key, 0) + 1
                print(f"SNAPSHOT {label}")
            except (OSError, ValueError, KeyError, TypeError) as erro:
                problemas.append(f"{label}: metadados invalidos ({type(erro).__name__})")
    for chave, total in sorted(totais.items()):
        print(f"EXCECAO {chave}: {total}")
    for problema in problemas:
        print(f"ERRO {problema}")
    if problemas and args.strict:
        raise SystemExit(1)


def report_pending_operations(args: argparse.Namespace) -> None:
    """Lista operacoes de varios arquivos que ficaram em_andamento (`.operacoes/*.json`).

    Journal sem `situacao: em_andamento` nao aparece aqui: ou nunca existiu, ou
    a operacao terminou e o proprio `tracked_operation` apagou o arquivo. So
    sobra journal em disco quando algo foi interrompido no meio - e e
    exatamente isso que este comando precisa deixar visivel, nunca escondido
    atras de um retry que "parece ter funcionado".
    """
    escopos = [BASE, *project_dirs()]
    pendentes = pending_operations(escopos)
    if not pendentes:
        print("Nenhuma operacao pendente.")
        return
    for registro in pendentes:
        if registro.get("situacao") == "journal_ilegivel":
            print(
                f"ILEGIVEL {registro['arquivo']}: {registro.get('motivo', 'journal corrompido')}. "
                "Nao da para saber com seguranca o que ja foi feito - precisa de conferencia manual, "
                "nao apague sem olhar o arquivo e os alvos prováveis (veredito, processo.md, licoes.md)."
            )
            continue
        passos = registro.get("passos") or {}
        concluidos = sorted(nome for nome, info in passos.items() if info.get("situacao") == "concluido")
        tentando = sorted(nome for nome, info in passos.items() if info.get("situacao") != "concluido")
        print(
            f"PENDENTE {registro['op_id']} ({registro['kind']}): iniciada em {registro['iniciado_em']}, "
            f"passos concluidos: {', '.join(concluidos) or 'nenhum'}; "
            f"passos tentados sem confirmar: {', '.join(tentando) or 'nenhum'}. Journal: {registro['arquivo']}"
        )
    print(
        f"\n{len(pendentes)} operacao(oes) pendente(s). Rode o MESMO comando, com os MESMOS "
        "argumentos que a iniciou, para retomar: os passos ja concluidos nao sao repetidos, e um "
        "passo so 'tentado' e reconciliado pelo que ja esta gravado no arquivo, nunca refeito as "
        "cegas. Se a operacao nao vai ser retomada, apague o arquivo do journal manualmente depois "
        "de conferir o que ficou faltando - apagar sem conferir esconde um resultado incompleto "
        "como se nunca tivesse acontecido."
    )
    if args.strict:
        raise SystemExit(1)


def create_verdict(project: Path, produto_id: str, product: dict[str, Any], quote: dict[str, str],
                    force: bool = False, path: Path | None = None,
                    data_compra: str | None = None) -> Path:
    """Cria o arquivo de veredito no momento de `decidir`.

    Frente 6: `decidir` fecha a DECISAO (escolha e justificativa), nunca a
    compra em si - cotacao manual e evidencia de uma OFERTA conferida, nao
    prova de pagamento. `data_compra` so chega aqui JA RESOLVIDA por quem
    chama (`_decide_writes`, a partir de `--comprado`/`--data-compra`
    congelados em `op.detalhe` na 1a tentativa - nunca recalculado numa
    retomada em outro dia) - `None`/vazio significa "nao confirmado ainda",
    nunca fabricado a partir da fonte da cotacao.

    `Veredito D+30 previsto`/`D+180 previsto` ficam em branco aqui - ver
    `register_verdict_event`: so sao calculados a partir da data de INICIO
    DE USO explicitamente registrada, nunca da data da decisao/compra/
    entrega, e nunca fabricados com `hoje()` na ausencia dela. Sem essa
    data, o painel mostra "aguardando inicio de uso" ate ser informado -
    nunca vence nem atrasa por conta de um prazo que ninguem confirmou.

    Quando o arquivo JA EXISTE (2a chamada de `decidir` sobre o mesmo
    projeto/produto/dia, tipicamente `decidir` sem `--comprado` seguido de
    `decidir --comprado` para so confirmar a compra) e `force=False`, o
    conteudo existente e PRESERVADO - so complementa `Data da compra` se
    ela ainda estiver em branco E esta chamada trouxe uma data (nunca
    sobrescreve uma ja registrada, mesmo principio de `registrar-evento`).
    Nao exige `--force-veredito` (que reescreveria o veredito inteiro,
    inclusive D+30/D+180 ja preenchidos) so para registrar uma confirmacao
    de compra que chegou depois.
    """
    if path is None:
        path = VEREDITOS / f"{today()}-{project.name}-{produto_id}.md"
    if path.exists() and not force:
        if data_compra:
            texto = path.read_text(encoding="utf-8")
            if not extract_bullet(texto, "Data da compra"):
                atomic_write_text(path, replace_or_append_bullet(texto, "Data da compra", data_compra))
        return path
    text = render_template("veredito.md")
    replacements = {
        "- Projeto:": f"- Projeto: {project.name}",
        "- Produto:": f"- Produto: {product.get('nome') or produto_id}",
        "- Produto ID:": f"- Produto ID: {produto_id}",
        "- Data da compra:": f"- Data da compra: {data_compra or ''}",
        "- Valor pago:": f"- Valor pago: {brl(quote.get('custo_total'))}",
        "- Vendedor:": f"- Vendedor: {quote.get('loja')} / {quote.get('vendedor')}",
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
        return re.sub(pattern, lambda _: replacement, text)
    return text.rstrip() + f"\n- {label}: {value}\n"


def resolve_verdict_path(veredito: str) -> Path:
    path = Path(veredito)
    if not path.is_absolute():
        path = ROOT / veredito
    if not path.exists():
        raise SystemExit(f"Veredito nao encontrado: {veredito}")
    return path


def fill_verdict(args: argparse.Namespace) -> None:
    path = resolve_verdict_path(args.veredito)
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


# Ordem cronologica esperada dos eventos pos-decisao - so usada pra recusar
# entrada obviamente fora de ordem (ex.: entrega registrada antes da
# compra). Nao exige que os eventos anteriores existam (o Josemar pode
# nunca ter rodado `decidir --comprado`, ou pode registrar so o inicio de
# uso), so que quando um evento anterior JA esta gravado, o novo nao seja
# cronologicamente impossivel.
VERDICT_EVENT_BULLET = {
    "comprado": "Data da compra",
    "entrega": "Data de entrega",
    "inicio_uso": "Data de inicio de uso",
}
VERDICT_EVENT_ORDER = ["comprado", "entrega", "inicio_uso"]


def _erro_cronologia_evento(text: str, evento: str, nova_data: str) -> str | None:
    """Confere se `nova_data` para `evento` e cronologicamente compativel
    com os OUTROS eventos ja registrados no veredito (`text`) - ponto
    UNICO usado tanto por `registrar-evento` quanto pelo complemento de
    compra em `decidir` (achado 4: os dois caminhos que podem gravar
    `Data da compra` precisam do MESMO contrato, nunca um mais frouxo que
    o outro). Devolve `None` se valido, ou a mensagem pronta (sem o
    'Nada foi alterado' final - quem chama decide o resto da frase) se
    invalido.
    """
    indice = VERDICT_EVENT_ORDER.index(evento)
    label = VERDICT_EVENT_BULLET[evento]
    for evento_anterior in VERDICT_EVENT_ORDER[:indice]:
        data_anterior = extract_bullet(text, VERDICT_EVENT_BULLET[evento_anterior])
        if data_anterior and nova_data < data_anterior:
            return (
                f"{label} ({nova_data}) e anterior a {VERDICT_EVENT_BULLET[evento_anterior]} "
                f"({data_anterior}) - confira a data informada."
            )
    for evento_posterior in VERDICT_EVENT_ORDER[indice + 1:]:
        data_posterior = extract_bullet(text, VERDICT_EVENT_BULLET[evento_posterior])
        if data_posterior and nova_data > data_posterior:
            return (
                f"{label} ({nova_data}) e posterior a {VERDICT_EVENT_BULLET[evento_posterior]} "
                f"({data_posterior}) - confira a data informada."
            )
    return None


def _marcar_projeto_comprado(project: Path) -> None:
    """Mesma transicao de estado que `decidir --comprado` ja fazia -
    extraida pra `registrar-evento --evento comprado` (achado independente:
    a confirmacao podia chegar DEPOIS de `decidir`, e so o veredito era
    atualizado - `processo.md`/`briefing.md` continuavam dizendo
    'pesquisando'/'comprar ou marcar como comprado')."""
    mark_steps(project, [9])
    set_project_state(project, "comprado")
    set_process_state(project, estado="comprado", proxima_acao="acompanhar entrega e preencher veredito D+30")


def _decisao_atual_e_deste_produto(project: Path, produto_id: str) -> bool:
    """Confere se `produto_id` e o produto da decisao ABERTA deste projeto
    agora - nunca sincroniza estado operacional (singular, um por projeto)
    a partir de um veredito de uma decisao ja substituida por outra mais
    recente sobre um produto diferente."""
    decisao_path = project / "decisao.md"
    if not decisao_path.exists():
        return False
    texto = decisao_path.read_text(encoding="utf-8")
    return bool(produto_id) and extract_bullet(texto, "Produto ID") == produto_id


def _projeto_da_confirmacao_de_compra(veredito: str) -> Path | None:
    """Projeto associado a um `registrar-evento --evento comprado` - unico
    ponto usado tanto pra TRAVAR (`main()`, ANTES de rodar) quanto pra
    DECLARAR RECURSO (dentro da propria `register_verdict_event`, ao
    montar `recursos=` de `tracked_operation`), pra nunca divergir sobre
    qual projeto e afetado. So LE arquivos (veredito e `decisao.md`), nunca
    escreve.
    Devolve `None` sempre que a sincronizacao de estado nao deve acontecer:
    veredito inexistente ainda, sem `Projeto`/`Produto ID` gravado (ex.:
    `novo-veredito` standalone), projeto inexistente, ou a decisao aberta
    do projeto nao ser deste produto (decisao substituida por outra)."""
    caminho = Path(veredito)
    if not caminho.is_absolute():
        caminho = ROOT / veredito
    if not caminho.exists():
        return None
    texto = caminho.read_text(encoding="utf-8")
    projeto_nome = extract_bullet(texto, "Projeto")
    produto_id = extract_bullet(texto, "Produto ID")
    if not projeto_nome:
        return None
    projeto_dir = PROJETOS / projeto_nome
    if not projeto_dir.is_dir():
        return None
    if not _decisao_atual_e_deste_produto(projeto_dir, produto_id):
        return None
    return projeto_dir


def _data_evento_para_validacao(registro: dict[str, Any] | None, args: argparse.Namespace) -> str:
    if registro is None:
        return args.data or today()
    detalhe = registro.get("detalhe") or {}
    data = detalhe.get("data_efetiva")
    if data and _iso_date_prefix(data):
        return data
    try:
        assinatura = json.loads(registro.get("assinatura_fingerprint") or "{}")
    except (TypeError, ValueError):
        assinatura = {}
    data_assinatura = assinatura.get("data") if isinstance(assinatura, dict) else None
    if data_assinatura and _iso_date_prefix(data_assinatura):
        return data_assinatura
    data_inicio = _iso_date_prefix(registro.get("iniciado_em"))
    if data_inicio:
        return data_inicio
    raise SystemExit(
        "Nao da para retomar `registrar-evento`: o journal antigo nao contem "
        "`data_efetiva`, data explicita na assinatura nem `iniciado_em` valido. "
        "Confira a operacao pendente manualmente antes de prosseguir."
    )


def register_verdict_event(args: argparse.Namespace) -> None:
    """`registrar-evento`: grava, num veredito ja existente, a data em que
    a compra foi paga, o produto chegou, ou o uso comecou de verdade -
    sempre POSTERIOR a `decidir` (que so fecha a escolha, nunca comprova
    nenhum desses tres fatos).

    Frente 6, principio central: cada evento e um FATO DATADO independente
    e nunca e sobrescrito silenciosamente - uma segunda tentativa de
    registrar o MESMO evento (mesmo com data diferente) e recusada antes de
    qualquer escrita; corrigir um engano de digitacao e edicao manual do
    arquivo, o mesmo padrao ja usado para participacao invalida. A
    cronologia e checada nos DOIS sentidos - um evento anterior ja
    registrado (`comprado`/`entrega` mais cedo na ordem) nao pode ficar
    DEPOIS do que esta sendo gravado agora, e um evento POSTERIOR ja
    registrado (ex.: `inicio_uso` gravado antes de `entrega` ser
    perguntada) tambem nao pode ficar ANTES - a ordem de gravacao no CLI
    nao e a ordem cronologica dos fatos.

    So o evento `inicio_uso` recalcula `Veredito D+30 previsto`/`D+180
    previsto` (data de inicio + 30/180 dias) - e a UNICA ancora valida para
    esses lembretes; nunca decisao, compra ou entrega. Uma fase que ja foi
    RESPONDIDA (`D+30 preenchido em` presente) nunca tem o `previsto`
    recalculado por cima - preserva o veredito ja preenchido, como pedido.

    `--evento comprado` tambem sincroniza o estado operacional do projeto
    (`processo.md`/`briefing.md`) com a mesma transicao de `decidir
    --comprado` - MAS SO quando este veredito e comprovadamente o da
    decisao ABERTA agora (`_projeto_da_confirmacao_de_compra`); um veredito
    de produto ja substituido por outra decisao, ou um `novo-veredito`
    standalone sem `Produto ID`, nunca mexe no estado do projeto - so avisa.

    Quando ha projeto associado, este comando grava DOIS arquivos por fora
    do proprio veredito (`processo.md`, `briefing.md`) - por isso roda
    dentro de `tracked_operation` (mesmo mecanismo de `decidir`/`aprender-
    veredito`): uma falha entre gravar o evento no veredito e sincronizar o
    projeto fica pendente e RETOMAVEL (a guarda de "fato ja registrado"
    acima reconhece a propria retomada via `has_pending_operation` e nao
    bloqueia), a data efetiva e congelada em `op.detalhe` na 1a tentativa
    (nunca recalculada com `today()` de uma retomada em outro dia - mesmo
    principio do `data_compra_efetiva` de `decidir`), e o projeto/
    `processo.md`/`briefing.md` sao reivindicados como recurso ANTES de
    escrever (passados em `recursos=` pra `tracked_operation`) - alem
    disso, `main()` tambem TRAVA esse mesmo projeto antes de chamar esta
    funcao (`_projeto_da_confirmacao_de_compra`), protegendo contra um
    `decidir` verdadeiramente concorrente no mesmo projeto.
    """
    path = resolve_verdict_path(args.veredito)
    text = path.read_text(encoding="utf-8")
    label = VERDICT_EVENT_BULLET[args.evento]
    op_id = f"registrar-evento:{path.name}:{args.evento}"
    registro_pendente = pending_operation_record(BASE, op_id, "registrar-evento")
    pendencia_propria_ilegivel = registro_pendente is None and has_pending_operation(BASE, op_id, "registrar-evento")
    retomando_propria = registro_pendente is not None or pendencia_propria_ilegivel
    existente = extract_bullet(text, label)
    if existente and not retomando_propria:
        raise SystemExit(
            f"{label} ja esta registrada ({existente}) neste veredito - fato datado nao e "
            "sobrescrito silenciosamente. Se foi engano de digitacao, corrija o arquivo a "
            f"mao: {path}"
        )
    # A validacao de cronologia roda ANTES de criar operacao nova e tambem
    # numa retomada legivel, usando a data efetiva congelada no journal. A
    # existencia de um journal pendente nao prova que a tentativa antiga ja
    # validou tudo: versoes anteriores podiam recusar tarde demais e deixar
    # `passos: {}` para tras. O cuidado e nunca revalidar retomada com
    # `today()` novo - a data precisa vir do proprio journal.
    if not pendencia_propria_ilegivel:
        data_para_validacao = _data_evento_para_validacao(registro_pendente, args)
        erro = _erro_cronologia_evento(text, args.evento, data_para_validacao)
        if erro:
            raise SystemExit(erro + " Nada foi alterado.")
    projeto_dir = _projeto_da_confirmacao_de_compra(args.veredito) if args.evento == "comprado" else None
    assinatura = {"evento": args.evento, "data": args.data}
    recursos = {path}
    if projeto_dir:
        recursos |= {projeto_dir / "processo.md", projeto_dir / "briefing.md"}
    with tracked_operation(
        BASE, op_id, "registrar-evento", assinatura,
        {
            "data_efetiva": args.data or today(),
            "projeto_dir": str(projeto_dir) if projeto_dir else None,
        },
        recursos=recursos,
    ) as op:
        nova_data = op.detalhe["data_efetiva"]

        def _gravar_evento() -> None:
            texto_atual = path.read_text(encoding="utf-8")
            texto_atual = replace_or_append_bullet(texto_atual, label, nova_data)
            if args.evento == "inicio_uso":
                inicio = dt.date.fromisoformat(nova_data)
                if not extract_bullet(texto_atual, "D+30 preenchido em"):
                    texto_atual = replace_or_append_bullet(
                        texto_atual, "Veredito D+30 previsto", (inicio + dt.timedelta(days=30)).isoformat()
                    )
                if not extract_bullet(texto_atual, "D+180 preenchido em"):
                    texto_atual = replace_or_append_bullet(
                        texto_atual, "Veredito D+180 previsto", (inicio + dt.timedelta(days=180)).isoformat()
                    )
            atomic_write_text(path, texto_atual)

        op.executar_uma_vez("evento", _gravar_evento)

        projeto_salvo = op.detalhe.get("projeto_dir")
        if projeto_salvo:
            op.executar_uma_vez("estado_projeto", lambda: _marcar_projeto_comprado(Path(projeto_salvo)))

    print(path)
    if args.evento == "comprado":
        if projeto_dir:
            print(f"Estado do projeto {projeto_dir.name} atualizado para comprado.")
        else:
            projeto_nome = extract_bullet(text, "Projeto") or "?"
            print(
                f"Nao encontrei a decisao aberta correspondente em `{projeto_nome}` - "
                "estado do projeto NAO foi alterado (so a data no veredito). Se o projeto ainda "
                "estiver com a decisao deste produto em aberto, confira `decisao.md` e "
                "`Produto ID` neste veredito."
            )


def learn_from_verdict(args: argparse.Namespace) -> None:
    path = resolve_verdict_path(args.veredito)
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
    op_id = f"aprender-veredito:{path.name}:{fase}"

    # Uma falha logo depois de escrever o marcador (mas antes de confirmar a
    # operacao) deixa o marcador no arquivo E um journal proprio pendente.
    # Sem isso, a guarda abaixo bloqueava a retomada exigindo --force, mesmo
    # sendo a MESMA tentativa que falhou, nao um reexport de verdade.
    retomando_propria_falha = has_pending_operation(BASE, op_id, "aprender-veredito")

    # Cada fase e uma observacao diferente. D+30 exportado nao pode bloquear o
    # aprendizado de uso prolongado em D+180, mas repetir a mesma fase tambem
    # nao pode pesar duas vezes na base.
    legacy_export = "## Aprendizado exportado\n" in text
    if (marker_heading in text or legacy_export) and not args.force and not retomando_propria_falha:
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
        try:
            regret = personal_rating(raw_regret) if raw_regret else None
        except argparse.ArgumentTypeError as erro:
            raise SystemExit(f"Nota de arrependimento invalida no veredito: {erro}") from erro

    # Julgamento do PRODUTO e do VENDEDOR sao coisas diferentes. Antes, um
    # arrependimento 9 com o produto derrubava a loja para nota 1 junto, mesmo
    # quando a loja tinha resolvido a devolucao perfeitamente. Cada um tem o
    # proprio campo; sem campo proprio, a entrada fica sem nota em vez de herdar
    # a nota alheia.
    nota_produto = None if regret is None else max(0, 10 - regret)
    nota_loja = args.nota_loja
    if nota_loja is None:
        bruto = extract_bullet(text, f"{prefix} nota vendedor")
        try:
            nota_loja = personal_rating(bruto) if bruto else None
        except argparse.ArgumentTypeError as erro:
            raise SystemExit(f"Nota do vendedor invalida no veredito: {erro}") from erro
    compraria_produto = buy_again if buy_again in {"sim", "nao", "talvez"} else None
    compraria_loja = args.compraria_do_vendedor or (
        extract_bullet(text, f"{prefix} compraria do mesmo vendedor") or None
    )
    if compraria_loja not in {"sim", "nao", "talvez", None}:
        compraria_loja = None

    gate_note = ""
    if args.gate:
        if not lesson:
            raise SystemExit("--gate exige uma licao para registrar a justificativa.")
        # Puro: so valida e formata, nao escreve categorias.yaml. A escrita de
        # verdade (apply_lesson_gate) fica dentro do executor da licao, para
        # nao repetir o efeito so para calcular a assinatura de reconciliacao.
        g_categoria, g_field, g_valor = parse_lesson_gate(args.gate)
        gate_note = f" Gate atualizado: {g_categoria}.{g_field}={g_valor}."

    # Marca, loja e licao sao 3 gravacoes append-only separadas. Uma falha
    # entre elas (crash, Ctrl+C) e uma repeticao do comando podia registrar de
    # novo o que ja tinha side, duplicando entrada. `assinatura` congela os
    # DADOS desta tentativa: uma retomada com marca/loja/licao diferentes (ex.:
    # o Josemar editou o veredito entre as duas chamadas) e recusada, em vez
    # de misturar passo velho com dado novo.
    assinatura = {
        "marca": marca, "loja": loja, "categoria": categoria, "resumo": summary,
        "licao": lesson, "nota_produto": nota_produto, "nota_loja": nota_loja,
        "compraria_produto": compraria_produto, "compraria_loja": compraria_loja,
        "gate": args.gate, "alerta": args.alerta, "resumo_vendedor": args.resumo_vendedor,
    }
    # licoes.md e UM arquivo compartilhado por TODAS as exportacoes, de
    # qualquer projeto ou veredito. Duas exportacoes legitimas e
    # independentes, com texto de licao identico no mesmo dia, escrevem no
    # MESMO lugar - sem declarar isso como recurso, uma retomada podia contar
    # a ocorrencia da OUTRA exportacao como prova do proprio efeito e nunca
    # gravar a sua. O mesmo vale para marca/loja quando o nome coincide.
    # O proprio arquivo de veredito tambem e reivindicado: `preencher-
    # veredito` e `novo-veredito --force` escrevem nele por fora do journal,
    # e podiam apagar um marcador ja gravado ou o restante do conteudo
    # humano enquanto esta exportacao ainda estivesse pendente.
    recursos = {path}
    if lesson:
        recursos.add(BASE / "licoes.md")
    if marca:
        recursos.add(BASE / "marcas" / f"{slugify(marca)}.md")
    if loja:
        recursos.add(BASE / "lojas" / f"{slugify(loja)}.md")
    with tracked_operation(BASE, op_id, "aprender-veredito", assinatura, {"veredito": str(path), "fase": fase},
                            recursos=recursos) as op:
        if marca:
            path_marca, entry_marca = knowledge_entry(
                argparse.Namespace(
                    nome=marca, categoria=categoria, projeto=project_name,
                    nota=nota_produto, compraria_de_novo=compraria_produto,
                    resumo=summary, alerta=args.alerta,
                ),
                "marca",
            )
            op.registrar_efeito("marca", path_marca, entry_marca, lambda: append_text(path_marca, entry_marca))
        if loja:
            path_loja, entry_loja = knowledge_entry(
                argparse.Namespace(
                    nome=loja, categoria=categoria, projeto=project_name,
                    nota=nota_loja, compraria_de_novo=compraria_loja,
                    resumo=args.resumo_vendedor or summary, alerta=args.alerta,
                ),
                "loja",
            )
            op.registrar_efeito("loja", path_loja, entry_loja, lambda: append_text(path_loja, entry_loja))
        if lesson:
            linha_licao = f"{today()} - {categoria} - {lesson}{gate_note}\n"

            def _gravar_licao(gate=args.gate, linha=linha_licao):
                if gate:
                    apply_lesson_gate(gate)
                append_text(BASE / "licoes.md", linha)

            op.registrar_efeito("licao", BASE / "licoes.md", linha_licao, _gravar_licao)

        # O marcador so precisa da leitura de `text` feita no topo da funcao:
        # se ja estava la (reexport com --force, ou a propria tentativa que
        # falhou depois de escreve-lo), nao duplica. Nao precisa de passo no
        # journal - reconciliar pelo conteudo real e mais simples e mais
        # confiavel do que confiar so no que o journal registrou.
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
    # A checagem de conflito com operacao pendente roda centralizada em
    # `main()` (tabela RECURSOS_DIRETOS_POR_COMANDO), antes de chegar aqui.
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


def parse_lesson_gate(gate: str) -> tuple[str, str, Any]:
    if "=" not in gate or "." not in gate.split("=", 1)[0]:
        raise SystemExit("Use --gate categoria.campo=valor. Exemplo: cosmetico.exige_vendedor_oficial=true")
    left, raw_value = gate.split("=", 1)
    categoria, field = left.split(".", 1)
    supported = {
        "nota_minima_ajustada", "minimo_avaliacoes", "garantia_minima_meses",
        "garantia_tipo_aceita", "exige_vendedor_oficial", "exige_rede_assistencia",
    }
    if field not in supported or not re.fullmatch(r"[A-Za-z0-9_-]+", categoria):
        raise SystemExit(f"gate nao suportado: {gate}. Campos aceitos: {', '.join(sorted(supported))}.")
    valor = parse_scalar(raw_value)
    if field.startswith("exige_"):
        valido = isinstance(valor, bool)
    elif field == "garantia_tipo_aceita":
        valido = isinstance(valor, list) and bool(valor) and all(
            item in {"nacional", "importada", "vendedor", "nenhuma"} for item in valor if isinstance(item, str)) and all(isinstance(item, str) for item in valor)
    else:
        valido = isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor) and valor >= 0
        if field == "nota_minima_ajustada":
            valido = valido and valor <= 5
        else:
            valido = valido and float(valor).is_integer()
    if not valido:
        raise SystemExit(f"Valor invalido para gate {categoria}.{field}: {raw_value}")
    return categoria, field, valor


def apply_lesson_gate(gate: str) -> str:
    categoria, field, valor = parse_lesson_gate(gate)
    path = CONFIG / "categorias.yaml"
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
    # Checagem de conflito centralizada em `main()`.
    gate_note = ""
    if args.gate:
        applied = apply_lesson_gate(args.gate)
        gate_note = f" Gate atualizado: {applied}."
    line = f"{today()} - {args.categoria or 'geral'} - {args.texto}{gate_note}\n"
    append_text(BASE / "licoes.md", line)
    print(BASE / "licoes.md")


def project_product_ids(project: Path) -> set[str]:
    ids = {row.get("produto_id") for row in read_quotes(project) if row.get("produto_id")}
    ids |= project_candidate_ids(project)
    ids |= project_discarded_candidate_ids(project)
    return ids


def project_evidence_participant_ids(project: Path) -> set[str]:
    """Todo produto_id que precisa ter EVIDENCIA congelada num snapshot de
    decisao deste projeto - superset de `project_product_ids`, usado SO
    por `_decide_writes` pra montar o inventario de fontes a copiar. Nunca
    usar para ranking, regra de parada, prompt-ia ou qualquer lista de
    candidatos - incluir um produto_id aqui nao reabilita, nao pontua e
    nao fabrica descarte.

    Participacao com CONTEUDO INVALIDO e SEM cotacao nenhuma fica de fora
    de `project_candidate_ids`/`project_discarded_candidate_ids` de
    proposito (nao e "ativo" confirmado nem "descartado" confirmado - ver
    docstring das duas) - e por isso tambem de fora de
    `project_product_ids`, que so uniao os dois mais quem tem cotacao. Isso
    e CORRETO para elegibilidade, mas errado para evidencia: o arquivo de
    participacao existe em disco com dado real (preco-alvo/teto, requisito,
    campo desconhecido), e uma decisao fechada nesse projeto precisa
    preservar essa evidencia tambem - mesmo que o participante nunca tenha
    entrado na disputa por falta de cotacao. Sem isto, `_decide_writes`
    nunca alcancava o ramo que copia o arquivo bruto (participacao
    invalida) nem a ficha desse produto: `auditar-decisoes --strict`
    passava sem nenhum arquivo do snapshot preservar aquele participante.
    """
    ids = set(project_product_ids(project))
    pasta = participations_dir(project)
    if pasta.exists():
        ids |= {path.stem for path in pasta.glob("*.yaml")}
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
    briefing, _ = load_frontmatter(project / "briefing.md")
    categoria = str(briefing.get("categoria") or "")
    for folder, found in (("marcas", brand_files), ("lojas", store_files)):
        for path in sorted((BASE / folder).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if categoria and re.search(rf"(?mi)^- Categoria:\s*{re.escape(categoria)}\s*$", text):
                found.append(path)
    return (sorted({path for path in brand_files if path.exists()}),
            sorted({path for path in store_files if path.exists()}))


def lesson_lines_for_category(categoria: str | None, *, limit: int | None = 10) -> list[str]:
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
    return lines if limit is None else lines[-limit:]


def knowledge_context(project: Path) -> str:
    briefing, _ = load_frontmatter(project / "briefing.md")
    categoria = briefing.get("categoria")
    brand_files, store_files = knowledge_files_for_project(project)
    lesson_lines = lesson_lines_for_category(categoria, limit=None)
    parts: list[str] = []
    if lesson_lines:
        parts.append("Licoes relevantes:\n" + "\n".join(f"- {line}" for line in lesson_lines))
    if brand_files:
        brand_text = []
        for path in brand_files:
            brand_text.append(path.read_text(encoding="utf-8").strip())
        parts.append("Marcas ja conhecidas:\n" + "\n\n".join(brand_text))
    if store_files:
        store_text = []
        for path in store_files:
            store_text.append(path.read_text(encoding="utf-8").strip())
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
    # O limite de contexto do prompt nao pode apagar conhecimento historico da
    # metrica: dez licoes novas faziam uma compra antiga deixar de reaproveitar.
    for linha in lesson_lines_for_category(briefing.get("categoria"), limit=None):
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


def is_technical_tie(elegiveis: list[Ranked]) -> bool:
    """Os dois primeiros elegiveis estao dentro da margem de 3 pontos."""
    return len(elegiveis) > 1 and elegiveis[0].score - elegiveis[1].score <= 3


@read_session
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
        "cotacoes_vencidas": sum(quote_is_stale(row) for row in latest.values()),
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
        # Mesma regua do Code.gs: fingir precisao alem disso seria mentir sobre
        # o que o score mede.
        "empate_tecnico": is_technical_tie(elegiveis),
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
            # `Veredito {prefix} previsto` so existe depois que o inicio de
            # uso e registrado (`registrar-evento --evento inicio_uso`) -
            # frente 6. Sem essa data, o lembrete fica pendente aqui, nunca
            # "atrasado" ou "vence hoje" fabricado a partir de hoje.
            return "aguardando inicio de uso"
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
.compare-wrap { overflow-x: auto; }
.compare { table-layout: auto; min-width: 100%; }
.compare th, .compare td { white-space: nowrap; }
.compare td:first-child, .compare th:first-child {
  position: sticky; left: 0; background: var(--surface); font-weight: 700;
  white-space: normal; min-width: 140px;
}
.stars { color: var(--amber); letter-spacing: 1px; }
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


def spec_comparison_label(chave: str) -> str:
    """Rotulo legivel para uma chave de atributo, sem depender de tabela por categoria.

    So troca `_` por espaco e capitaliza cada palavra: funciona pra qualquer
    categoria (carro, fone, camera...) sem manter uma lista de traducoes.
    """
    return " ".join(parte.capitalize() for parte in chave.split("_"))


def _stars_from_faixas(faixas: list[dict[str, Any]], valor: Any) -> int | None:
    """Primeira faixa (por `min` decrescente) que o valor numerico atinge.

    Ordena por `min` aqui dentro de proposito: nunca confia na ordem em que
    a lista foi escrita no YAML. Uma faixa colada fora de ordem por engano
    nao pode classificar errado em silencio.
    """
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    ordenadas = sorted(faixas, key=lambda f: quote_float(f.get("min")), reverse=True)
    for faixa in ordenadas:
        if numero >= quote_float(faixa.get("min")):
            return int(faixa["estrelas"])
    return None


def _stars_from_valores(valores: dict[str, Any], valor: Any) -> int | None:
    """Correspondencia exata categoria -> estrelas. Sem entrada = None, nunca um chute."""
    estrelas = valores.get(valor)
    return int(estrelas) if estrelas is not None else None


def stars_for_attribute(categoria: str, campo: str, valor: Any) -> int | None:
    """1-5, absoluto: nunca recebe lista de candidatos, so um valor por vez.

    Isso torna estruturalmente impossivel comparar um candidato contra o
    outro aqui dentro - empate e o padrao quando o valor normalizado e igual.
    Le a regua em `categorias.yaml` (`estrelas.<campo>`); campo sem regua ou
    valor sem correspondencia devolve None (sem dado, nunca 1 estrela).
    """
    if valor in {None, ""}:
        return None
    regua = (category_definition(categoria).get("estrelas") or {}).get(campo)
    if not regua:
        return None
    if "valores" in regua:
        return _stars_from_valores(regua.get("valores") or {}, valor)
    faixas = regua.get("faixas")
    if not faixas:
        return None
    return _stars_from_faixas(faixas, valor)


def stars_from_score(score01: float | None) -> int | None:
    """Mapeia um score 0-1 ja absoluto (qualidade, risco/garantia) em 1-5 estrelas."""
    if score01 is None:
        return None
    if score01 >= 0.8:
        return 5
    if score01 >= 0.6:
        return 4
    if score01 >= 0.4:
        return 3
    if score01 >= 0.2:
        return 2
    return 1


def stars_glyphs(estrelas: int | None) -> str:
    """'★★★☆☆' (Unicode simples). None -> string vazia, nunca estrela fabricada."""
    if estrelas is None:
        return ""
    cheias = max(0, min(5, estrelas))
    return "★" * cheias + "☆" * (5 - cheias)


def spec_comparison_rows(project: Path) -> tuple[str, list[str], list[Ranked]]:
    """Categoria + atributos + resumo comercial lado a lado, um candidato por coluna.

    Ordem das linhas: primeiro os `atributos_obrigatorios` da categoria (na
    ordem do `categorias.yaml`), depois qualquer atributo extra que apareca em
    algum candidato, em ordem alfabetica. Atributo ausente num candidato vira
    "-", nunca um valor inventado - o mesmo principio do ranking.
    """
    briefing_meta, _ = load_frontmatter(project / "briefing.md")
    categoria = briefing_meta.get("categoria") or "generico"
    elegiveis, cortados = compute_ranking(project)
    itens = [*elegiveis, *cortados, *sem_cotacao_candidates(project, categoria, [*elegiveis, *cortados])]
    if not itens:
        return categoria, [], []

    obrigatorios = list(category_definition(categoria).get("atributos_obrigatorios") or [])
    extras: list[str] = []
    for item in itens:
        for chave in (item.product.get("atributos") or {}):
            if chave not in obrigatorios and chave not in extras:
                extras.append(chave)
    return categoria, obrigatorios + sorted(extras), itens


LINHAS_COMERCIAIS = ["preco", "loja", "vendedor", "nota", "garantia", "fonte"]


def comercial_valor(item: Ranked, chave: str) -> tuple[str, int | None]:
    """(texto, estrelas) de uma linha comercial do comparativo.

    Fonte unica pro HTML (spec_comparison_section) e pro export de dados
    (sheets_export_payload) - os dois so formatam o que esta funcao decide,
    nunca recalculam por conta propria. Estrela e None quando o candidato
    foi cortado pelo gate, o dado falta, ou o eixo correspondente nao
    entrou na conta do ranking - nunca fabricada.
    """
    quote = item.quote
    if chave == "preco":
        # De proposito sem estrela: `valor` e o unico eixo relativo ao mais
        # barato do projeto, nao absoluto - documentado em preferencias.yaml.
        return brl(quote.get("custo_total")), None
    if chave == "loja":
        return quote.get("loja") or "-", None
    if chave == "vendedor":
        vendedor = quote.get("vendedor") or ""
        tipo = quote.get("vendedor_tipo") or ""
        if not vendedor:
            return "-", None
        return (f"{vendedor} ({tipo})" if tipo else vendedor), None
    if chave == "nota":
        nota = quote.get("nota")
        avaliacoes = quote.get("n_avaliacoes")
        # quote_float (nao `not nota` puro): "0.0" e string nao-vazia, mas o
        # valor numerico e zero - mesmo criterio de current_adjusted_rating,
        # senao o texto mostra "0.0 (0 aval.)" como se fosse nota de verdade
        # em vez de "nota nunca informada". Achado numa conferencia real na
        # planilha (candidato do decor-bloqueador, cotacao web sem nota).
        if not quote_float(nota):
            return "-", None
        # Estrela e etapa final da cotacao: so pros elegiveis, que chegam
        # na mesa de decisao. Cortado pelo gate nao ganha estrela - nao
        # vale gastar essa classificacao em quem ja saiu da disputa.
        # Nota ausente (eixo qualidade sem dado) tambem nunca vira 1
        # estrela por tabela: so estrela quando o eixo realmente entrou
        # na conta do ranking pra este candidato.
        if item.eliminations or "qualidade" in item.eixos_sem_dado:
            estrelas = None
        else:
            estrelas = stars_from_score(item.axes.get("qualidade"))
        return f"{nota} ({avaliacoes or 0} aval.)", estrelas
    if chave == "garantia":
        tipo = quote.get("garantia_tipo")
        meses = quote.get("garantia_meses")
        if not tipo:
            return "-", None
        texto = f"{tipo}, {meses} meses" if meses else tipo
        estrelas = None
        if not item.eliminations:
            # So a parcela "garantia (tipo)" do risco, buscada por rotulo
            # (nunca por indice) - reflete a mesma regua do score, sem
            # inventar uma segunda conta.
            parcela = next((p for p in risk_parts(quote) if p[0] == "garantia (tipo)"), None)
            estrelas = stars_from_score(parcela[2] if parcela else None)
        return texto, estrelas
    if chave == "fonte":
        return quote.get("fonte") or "-", None
    return "-", None


def atributo_valor(categoria: str, item: Ranked, chave: str) -> tuple[str, int | None]:
    """(texto, estrelas) de um atributo tecnico do comparativo.

    Mesmo principio de `comercial_valor`: fonte unica pro HTML e pro export.
    """
    texto = str((item.product.get("atributos") or {}).get(chave) or "-")
    if texto == "-" or item.eliminations or item.sem_cotacao:
        # Estrela e a etapa final da cotacao, so pra quem chega elegivel na
        # mesa de decisao - cortado pelo gate ou ainda sem cotacao mostra o
        # valor bruto, nunca a classificacao (nao vale gastar essa conta em
        # quem ainda nem tem preco, muito menos em quem ja saiu da disputa).
        return texto, None
    classificacao = (item.product.get("atributos_classificacao") or {}).get(chave)
    return texto, stars_for_attribute(categoria, chave, classificacao)


def _celula_com_estrelas(texto: str, estrelas: int | None) -> str:
    if estrelas is None:
        return safe_html(texto)
    return f'{safe_html(texto)} <span class="stars" title="{estrelas}/5">{stars_glyphs(estrelas)}</span>'


def spec_comparison_section(project: Path) -> str:
    categoria, atributos, itens = spec_comparison_rows(project)
    if not itens:
        return ""

    header_cols = "".join(
        f"<th>{safe_html(item.product.get('nome') or item.produto_id)}"
        + (
            ' <span class="pill bad">cortado</span>' if item.eliminations
            else ' <span class="pill">sem cotacao</span>' if item.sem_cotacao
            else ""
        )
        + "</th>"
        for item in itens
    )
    comercial_rows = "".join(
        f"<tr><td>{safe_html(spec_comparison_label(chave))}</td>"
        + "".join(
            f"<td>{_celula_com_estrelas(*comercial_valor(item, chave))}</td>"
            for item in itens
        )
        + "</tr>"
        for chave in LINHAS_COMERCIAIS
    )

    def celula_atributo(item: Ranked, chave: str) -> str:
        return _celula_com_estrelas(*atributo_valor(categoria, item, chave))

    spec_rows = "".join(
        f"<tr><td>{safe_html(spec_comparison_label(chave))}</td>"
        + "".join(f"<td>{celula_atributo(item, chave)}</td>" for item in itens)
        + "</tr>"
        for chave in atributos
    )
    return f"""
<section class="section panel">
  <h2>Comparativo de caracteristicas</h2>
  <p class="muted">Um candidato por coluna, igual comparador de celular. "-" e atributo sem dado, nunca valor inventado. Estrela e a classificacao final: so pros elegiveis (quem chega na mesa de decisao), nunca pros cortados pelo gate.</p>
  <div class="compare-wrap">
  <table class="compare">
    <thead><tr><th>Candidato</th>{header_cols}</tr></thead>
    <tbody>
      {comercial_rows}
      {spec_rows}
    </tbody>
  </table>
  </div>
</section>
"""


SHEETS_OVERVIEW_FIELDS = [
    "categoria", "estado", "lider", "score", "confianca", "cotacoes",
    "manual", "dias_ate_decisao", "escolhido", "aguardando_preco",
]
SHEETS_OVERVIEW_COLUMNS = [
    "projeto", "categoria", "estado", "lider", "score", "confianca",
    "cotacoes", "data_decisao",
]
SHEETS_SCHEMA_VERSION = 3
SHEETS_METRIC_FIELDS = [
    "produto", "situacao", "score", "confianca", "custo_total", "nota",
    "avaliacoes", "qualidade", "valor", "risco", "aderencia", "conveniencia",
    # Schema 3 (aditivo): estado da cotacao e motivo do corte, para a aba do
    # projeto explicar o que impede a decisao sem recomputar o gate.
    "vencida", "fonte", "motivos_corte",
]


def _linha_export(chave: str, tipo: str, valores: list[tuple[str, int | None]]) -> dict[str, Any]:
    rotulo = spec_comparison_label(chave)
    if tipo == "estrela":
        return {
            "rotulo": rotulo,
            "tipo": "estrela",
            "valores": [{"texto": texto, "estrelas": estrelas} for texto, estrelas in valores],
        }
    return {"rotulo": rotulo, "tipo": "texto", "valores": [texto for texto, _ in valores]}


def _valor_tipado(valor: Any, texto: str, estrelas: int | None = None) -> dict[str, Any]:
    """Valor adicional pro Sheets v2; o campo legado continua intacto."""
    if texto == "-" or valor is None or valor == "":
        return {"tipo": "vazio", "valor": "", "texto": texto, "estrelas": estrelas}
    if isinstance(valor, bool):
        return {"tipo": "booleano", "valor": valor, "texto": texto, "estrelas": estrelas}
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return {"tipo": "numero", "valor": valor, "texto": texto, "estrelas": estrelas}
    return {"tipo": "texto", "valor": texto, "texto": texto, "estrelas": estrelas}


def _valores_tipados_comerciais(chave: str, itens: list[Ranked]) -> list[dict[str, Any]]:
    tipados: list[dict[str, Any]] = []
    for item in itens:
        texto, estrelas = comercial_valor(item, chave)
        quote = item.quote
        if chave == "preco":
            custo = quote_float(quote.get("custo_total"))
            valor = _valor_tipado(custo if custo > 0 else None, texto, estrelas)
            valor["tipo"] = "moeda" if custo > 0 else "vazio"
        elif chave == "nota":
            nota = quote_float(quote.get("nota"))
            valor = _valor_tipado(nota if nota > 0 else None, texto, estrelas)
            valor["tipo"] = "nota" if nota > 0 else "vazio"
            valor["detalhe"] = f"{quote_int(quote.get('n_avaliacoes'))} avaliacoes" if nota > 0 else ""
        else:
            valor = _valor_tipado(texto if texto != "-" else None, texto, estrelas)
        tipados.append(valor)
    return tipados


def _metricas_sheets(item: Ranked, situacao: str) -> dict[str, Any]:
    quote = item.quote
    custo = quote_float(quote.get("custo_total"))
    nota = quote_float(quote.get("nota"))
    return {
        "produto": item.product.get("nome") or item.produto_id,
        "situacao": situacao,
        "score": "" if item.sem_cotacao else item.score,
        "confianca": "" if item.sem_cotacao else item.confianca,
        "custo_total": custo if custo > 0 else "",
        "nota": nota if nota > 0 else "",
        "avaliacoes": quote_int(quote.get("n_avaliacoes")) if nota > 0 else "",
        "qualidade": item.axes.get("qualidade", ""),
        "valor": item.axes.get("valor", ""),
        "risco": item.axes.get("risco", ""),
        "aderencia": item.axes.get("aderencia", ""),
        "conveniencia": item.axes.get("conveniencia", ""),
        # Schema 3 (aditivo): a aba mostra "cotacao vencida", "so fonte web" e
        # o motivo do corte sem reimplementar gate nem frescor no Apps Script.
        "vencida": bool(item.vencida),
        "fonte": quote.get("fonte") or "",
        "motivos_corte": list(item.eliminations),
    }


@read_session
def sheets_export_payload() -> dict[str, Any]:
    """JSON pronto pro Web App do Apps Script. So monta, nunca envia.

    Reaproveita project_counts() e spec_comparison_rows() (as mesmas contas
    do dashboard) e comercial_valor()/atributo_valor() (a mesma decisao de
    texto+estrela do HTML) - HTML e planilha nunca podem mostrar numero
    diferente pro mesmo candidato.
    """
    visao_geral: list[dict[str, Any]] = []
    comparativos: list[dict[str, Any]] = []
    for project in project_dirs():
        counts = project_counts(project)
        linha = {"projeto": counts["id"]}
        linha.update({campo: counts[campo] for campo in SHEETS_OVERVIEW_FIELDS})
        linha["data_decisao"] = counts["data_decisao"]
        linha["cotacoes_vencidas"] = counts["cotacoes_vencidas"]
        # Schema 3 (aditivo): a fila de atencao da Visao Geral usa os dois sem
        # refazer conta nenhuma no Apps Script.
        linha["abaixo_confianca_minima"] = counts["confianca_minima"]
        linha["empate_tecnico"] = counts["empate_tecnico"]
        visao_geral.append(linha)

        categoria, atributos, itens = spec_comparison_rows(project)
        if not itens:
            continue
        colunas = [item.product.get("nome") or item.produto_id for item in itens]
        situacao = [
            "sem_cotacao" if item.sem_cotacao
            else "cortado" if item.eliminations
            else "elegivel"
            for item in itens
        ]
        linhas: list[dict[str, Any]] = []
        for chave in LINHAS_COMERCIAIS:
            tipo = "estrela" if chave in {"nota", "garantia"} else "texto"
            valores = [comercial_valor(item, chave) for item in itens]
            linha = _linha_export(chave, tipo, valores)
            linha["secao"] = "precos"
            linha["valores_tipados"] = _valores_tipados_comerciais(chave, itens)
            linhas.append(linha)
        for chave in atributos:
            valores = [atributo_valor(categoria, item, chave) for item in itens]
            linha = _linha_export(chave, "estrela", valores)
            linha["secao"] = "atributos"
            linha["valores_tipados"] = [
                _valor_tipado((item.product.get("atributos") or {}).get(chave), texto, estrelas)
                for item, (texto, estrelas) in zip(itens, valores)
            ]
            linhas.append(linha)
        comparativos.append({
            "projeto": project.name,
            # Schema 3 (aditivo): cabecalho e faixa de veredito da aba.
            "categoria": categoria,
            "escolhido": counts["escolhido"],
            "data_decisao": counts["data_decisao"],
            "colunas": colunas,
            "situacao": situacao,
            "linhas": linhas,
            "metricas": [_metricas_sheets(item, status) for item, status in zip(itens, situacao)],
        })

    return {
        "schema_versao": SHEETS_SCHEMA_VERSION,
        "gerado_em": now_iso(),
        "visao_geral_colunas": SHEETS_OVERVIEW_COLUMNS,
        "metricas_colunas": ["projeto", *SHEETS_METRIC_FIELDS],
        "visao_geral": visao_geral,
        "comparativos": comparativos,
    }


def sheets_config_path() -> Path:
    return Path.home() / ".central-compras" / "dados-privados" / "integracao_sheets.json"


def sheets_endpoint_path() -> Path:
    """Parte NAO secreta da integracao, versionada de proposito.

    A URL do Web App sozinha nao da acesso: quem protege e o token, conferido
    dentro do Apps Script. Versionar a URL e o que faz `git pull` deixar outra
    maquina pronta - antes dela, so o token faltava e ninguem sabia disso.
    """
    return CONFIG / "integracao_sheets.yaml"


def carregar_config_sheets(caminho_explicito: str | None = None) -> tuple[str, str]:
    """Devolve (url, token) juntando a parte versionada com a parte local.

    - `--config` explicito: o arquivo tem que bastar sozinho (e o que os testes
      e uma maquina de teste usam para apontar para outro endpoint).
    - Sem `--config`: URL vem de config/integracao_sheets.yaml (versionada) e
      token de dados-privados. O arquivo local pode sobrepor a URL, para apontar
      uma maquina para um endpoint de teste sem sujar o repositorio.
    """
    if caminho_explicito:
        caminho = Path(caminho_explicito)
        if not caminho.exists():
            raise SystemExit(
                f"Configuracao nao encontrada: {caminho}\n"
                'Crie esse arquivo com {"url": "...", "token": "..."} '
                "(a URL do Web App do Apps Script e o token definido no Code.gs)."
            )
        try:
            local = json.loads(caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError as erro:
            raise SystemExit(f"{caminho} nao e um JSON valido: {erro}") from erro
        url, token = local.get("url"), local.get("token")
        if not url or not token:
            raise SystemExit(f"{caminho} precisa ter os campos 'url' e 'token'.")
        return url, token

    versionado = read_yaml(sheets_endpoint_path(), {}) or {}
    url = versionado.get("url")

    caminho = sheets_config_path()
    local: dict[str, Any] = {}
    if caminho.exists():
        try:
            local = json.loads(caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError as erro:
            raise SystemExit(f"{caminho} nao e um JSON valido: {erro}") from erro
        url = local.get("url") or url

    token = local.get("token")

    if not url:
        raise SystemExit(
            f"Falta a URL do Web App. Ela deveria estar versionada em "
            f"{sheets_endpoint_path()} (campo 'url') e chegar aqui pelo git pull.\n"
            "Se a implantacao mudou, atualize esse arquivo e commite - ver "
            "docs/infraestrutura-externa.md."
        )
    if not token:
        raise SystemExit(
            "Falta o token desta maquina. A URL ja veio pelo git pull; o token "
            "nao vai pelo Git de proposito.\n"
            "Pegue o valor no Code.gs (const TOKEN) ou em outra maquina que ja "
            "funciona, e rode:\n"
            "  python scripts/central_compras.py configurar-sheets --token SEU_TOKEN\n"
            f"Ele fica so em {sheets_config_path()}."
        )
    return url, token


def configurar_sheets(args: argparse.Namespace) -> None:
    """Grava o token desta maquina, sem obrigar ninguem a editar JSON na mao.

    Isso e o unico passo manual que sobra depois de um `git pull` numa maquina
    nova - a URL ja vem versionada.
    """
    caminho = sheets_config_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados: dict[str, Any] = {}
    if caminho.exists():
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            dados = {}
    dados["token"] = args.token
    if getattr(args, "url", None):
        dados["url"] = args.url
    elif "url" in dados:
        # URL antiga no arquivo local sobrepoe a versionada e ja causou 404
        # depois de um redeploy. Sem --url explicito, manda a versionada valer.
        dados.pop("url")
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    url_versionada = (read_yaml(sheets_endpoint_path(), {}) or {}).get("url")
    print(f"Token gravado em {caminho}")
    print(f"URL em uso: {dados.get('url') or url_versionada or '(nenhuma - confira config/integracao_sheets.yaml)'}")
    print("Agora rode: python scripts/central_compras.py sincronizar-planilha")


def validar_resposta_sheets(resultado: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    """Confere contagens quando o Web App v2+ as oferece; aceita a Versao 4."""
    if quote_int(resultado.get("schema_versao")) < 2:
        return []
    esperados = {
        "linhas_visao": len(payload["visao_geral"]),
        "projetos_escritos": len(payload["comparativos"]),
    }
    divergencias = [
        f"{campo}: esperado {esperado}, recebido {resultado.get(campo)!r}"
        for campo, esperado in esperados.items()
        if resultado.get(campo) != esperado
    ]
    if divergencias:
        raise SystemExit(
            "A planilha respondeu ok, mas a leitura de volta divergiu: "
            + "; ".join(divergencias)
        )
    return [str(aviso) for aviso in (resultado.get("avisos") or [])]


def sincronizar_planilha(args: argparse.Namespace) -> None:
    """Monta o payload e faz o POST pro Web App do Apps Script.

    So roda quando chamado - nunca dentro de `dashboard` (que e local e sem
    rede). Mandar dado pra fora e decisao explicita, nao efeito colateral.
    """
    url, token = carregar_config_sheets(getattr(args, "config", None))

    payload = sheets_export_payload()
    payload["token"] = token
    corpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    requisicao = urllib.request.Request(
        url, data=corpo, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=120) as resposta:
            corpo_resposta = resposta.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as erro:
        raise SystemExit(f"Falha ao conectar na planilha: {str(erro).replace(token, '[oculto]')}") from erro

    try:
        resultado = json.loads(corpo_resposta)
    except json.JSONDecodeError as erro:
        # A Web App pode devolver uma pagina de erro/login em vez do JSON
        # esperado (por exemplo, se o redirecionamento do Apps Script nao
        # preservou o POST). Erro claro em vez de traceback cru.
        raise SystemExit(
            "A planilha nao devolveu JSON valido - a implantacao pode ter "
            "mudado ou o link expirou. Confira a implantacao e a conta proprietaria."
        ) from erro

    if not isinstance(resultado, dict):
        raise SystemExit("Resposta da planilha precisa ser um objeto JSON.")
    if resultado.get("ok") is not True:
        mensagem = resultado.get("error") or resultado
        detalhe = resultado.get("detalhe")
        if detalhe:
            mensagem = f"{mensagem}. Detalhe: {detalhe}"
        abas_concluidas = resultado.get("abas_escritas_antes_da_falha")
        if abas_concluidas:
            mensagem = f"{mensagem}. Abas concluidas antes da falha: {', '.join(str(a) for a in abas_concluidas)}"
        # abas_parcialmente_alteradas (Code.gs V13+): abaLimpa ja rodou nessas
        # abas mas a escrita nova nao terminou - podem estar em branco. E um
        # campo distinto de abas_escritas_antes_da_falha (essas terminaram de
        # verdade); uma resposta antiga sem o campo so nao mostra esta linha.
        abas_parciais = resultado.get("abas_parcialmente_alteradas")
        if abas_parciais:
            mensagem = (
                f"{mensagem}. Abas parcialmente alteradas (podem estar em "
                f"branco, escrita nao terminou): {', '.join(str(a) for a in abas_parciais)}"
            )
        raise SystemExit(f"A planilha recusou os dados: {str(mensagem).replace(token, '[oculto]')}")
    avisos = validar_resposta_sheets(resultado, payload)
    print(
        f"Planilha sincronizada: {len(payload['visao_geral'])} projeto(s), "
        f"{len(payload['comparativos'])} comparativo(s)."
    )
    for aviso in avisos:
        print(f"Aviso da planilha: {aviso}")


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
    comparativo = spec_comparison_section(project)
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
{comparativo}
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


@read_session
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
        global_cfg = preferences().get("nota_bayesiana", {})
        cfg_bayes = global_cfg
        if categoria_produto:
            cat_cfg = category_definition(categoria_produto).get("nota_bayesiana") or {}
            cfg_bayes = {**global_cfg, **cat_cfg}
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


_SOURCES_FROZEN = contextvars.ContextVar("central_compras_sources_frozen", default=False)


@contextlib.contextmanager
def sources_frozen():
    """Congela as fontes: derivados podem ser refeitos, fonte nao muda.

    `build_ranking` marca etapas e reescreve "Proxima acao" no `processo.md`,
    que e fonte. Rodar `regenerar` mexia no historico decisorio enquanto
    imprimia "Nenhuma fonte foi tocada".
    """
    token = _SOURCES_FROZEN.set(True)
    try:
        yield
    finally:
        _SOURCES_FROZEN.reset(token)


@read_session
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


def migrate_products(args: argparse.Namespace) -> None:
    """Extrai estado/preco-alvo/preco-teto/requisitos/motivo-de-descarte
    LEGADOS (gravados direto na ficha, junto de um campo `projeto` unico) para
    um arquivo de participacao por projeto (frente 5).

    Idempotente: ficha ja limpa (sem nenhum campo legado) e ignorada
    silenciosamente numa segunda passada. So migra o caso INEQUIVOCO -
    ficha aponta para exatamente um projeto (via `projeto`), esse projeto
    existe, e nenhuma cotacao do mesmo produto_id aparece num projeto
    DIFERENTE - qualquer outra combinacao e relatada, nunca resolvida
    adivinhando. Participacao ja existente para aquele par nunca e
    sobrescrita (pode ser mais recente que a ficha, gravada por um
    `descartar`/`aguardar-preco` já rodado sobre o registro legado); a ficha
    ainda assim e limpa nesse caso, porque a participacao ja e quem manda.

    Sem `--aplicar`, so mostra a previa (nenhuma escrita). Seguro rodar
    quantas vezes quiser: cada ficha e reavaliada do zero a cada chamada, sem
    depender de progresso anterior gravado em disco - por isso nao precisa de
    journal proprio (`tracked_operation`); a trava de projeto/`produtos/` ja
    herdada de `main()` basta para serializar contra outros comandos.
    """
    projeto_alvo = project_path(args.projeto) if args.projeto else None
    todos_projetos = project_dirs()
    cotacoes_por_produto: dict[str, set[str]] = {}
    for projeto in todos_projetos:
        for row in read_quotes(projeto):
            pid = row.get("produto_id")
            if pid:
                cotacoes_por_produto.setdefault(pid, set()).add(projeto.name)

    migrados: list[str] = []
    ja_limpos = 0
    ambiguos: list[str] = []
    bloqueados: list[str] = []
    invalidos: list[str] = []

    for ficha_path in sorted(PRODUTOS.glob("*/*/produto.yaml")):
        produto_id = ficha_path.parent.name
        ficha = read_yaml(ficha_path, {})
        legado_projeto = ficha.get("projeto")
        tem_campo_legado = legado_projeto or any(
            key in ficha for key in _PARTICIPATION_LEGACY_KEYS
        )
        if not tem_campo_legado:
            ja_limpos += 1
            continue
        if not legado_projeto:
            ambiguos.append(
                f"{produto_id}: tem campo legado de participacao mas nenhum `projeto` gravado na "
                "ficha - nao da pra saber a qual compra pertencia. Confira e vincule manualmente "
                "com `vincular-produto`, ou edite a ficha a mao."
            )
            continue
        if projeto_alvo and legado_projeto != projeto_alvo.name:
            continue  # fora do escopo desta chamada (--projeto filtrou), nao e pendencia
        caminho_projeto = PROJETOS / str(legado_projeto)
        if not caminho_projeto.exists():
            ambiguos.append(
                f"{produto_id}: ficha aponta para o projeto `{legado_projeto}`, que nao existe mais. "
                "Nao migrado; confira se o projeto foi renomeado ou removido."
            )
            continue
        outros_projetos_com_cotacao = cotacoes_por_produto.get(produto_id, set()) - {legado_projeto}
        if outros_projetos_com_cotacao:
            ambiguos.append(
                f"{produto_id}: ficha aponta para `{legado_projeto}`, mas ha cotacao(oes) tambem em "
                f"{', '.join(sorted(outros_projetos_com_cotacao))}. Uso cruzado de verdade - vincule "
                "cada projeto manualmente com `vincular-produto` e confira a participacao de cada um "
                "antes de migrar; nao presumo qual delas e a legada."
            )
            continue

        # `write_participation`/`write_yaml` abaixo escrevem por fora do
        # journal proprio da migracao (ela nao tem um - e idempotente por
        # ficha). Sem esta checagem, um `decidir`/`vincular-produto`/
        # `aprender-veredito` interrompido, com journal ainda reivindicando
        # este MESMO arquivo de participacao, podia ser pisado por uma
        # migracao rodando por cima - a migracao criava o arquivo e limpava
        # a ficha antes da retomada daquela outra operacao terminar de ler
        # o dado que ela esperava encontrar.
        # `write_participation`/`write_yaml` abaixo escrevem por fora do
        # journal proprio da migracao (ela nao tem um - e idempotente por
        # ficha). Sem esta checagem, um `decidir`/`vincular-produto`/
        # `aprender-veredito` interrompido, com journal ainda reivindicando
        # este MESMO arquivo de participacao, podia ser pisado por uma
        # migracao rodando por cima - a migracao criava o arquivo e limpava
        # a ficha antes da retomada daquela outra operacao terminar de ler
        # o dado que ela esperava encontrar.
        participacao_alvo = participation_path(caminho_projeto, produto_id)
        try:
            _bloquear_se_recursos_conflitantes(
                {ficha_path, participacao_alvo},
                contexto=f"migrar `{produto_id}` para `{legado_projeto}`",
            )
        except SystemExit as erro:
            bloqueados.append(f"{produto_id}: {erro}")
            continue

        # A EXISTENCIA do arquivo de participacao nao prova que ele preserva
        # dado nenhum, nem que o dado que ele tem e confiavel. Tres casos,
        # tratamento diferente pra cada um (classificados por
        # `_classificar_participacao` - MESMO ponto usado por
        # `read_participation`, para as duas funcoes nunca divergirem sobre
        # o mesmo arquivo):
        #   (a) vazio (arquivo ausente, 0 bytes, `null`, ou mapa vazio `{}`)
        #       - nao ha NENHUM dado ali pra "ser mais recente que a ficha";
        #       seguro recuperar do legado, exatamente como se o arquivo nao
        #       existisse.
        #   (b) tem CONTEUDO mas nao passa no contrato minimo de
        #       participacao - uma lista/string/numero (nao e um mapa), ou
        #       um mapa com identidade/estado/tipo incoerente. Conteudo
        #       existente (mesmo que nao seja um mapa) NAO autoriza apagar a
        #       ficha legada (unica evidencia confiavel restante) - uma
        #       lista YAML com estado e motivo de descarte de verdade e
        #       conteudo, nao "arquivo vazio". Recusa preservando os dois
        #       arquivos, relata o motivo, decisao fica com o Josemar.
        #   (c) mapa valido (passa no contrato) - e sempre quem manda,
        #       nunca sobrescrito pelo legado; so a ficha e limpa.
        participacao_bruta = read_yaml(participacao_alvo, None)
        status_participacao, motivo_invalido = _classificar_participacao(participacao_bruta, produto_id)
        participacao_vazia = status_participacao == "vazio"
        if status_participacao == "invalida":
            invalidos.append(
                f"{produto_id}: participacao existente em `{participacao_alvo}` nao passa no contrato "
                f"minimo de participacao ({motivo_invalido}) - nao decido sozinho se e dado real "
                "incompleto ou lixo. Ficha legada preservada; confira o arquivo a mao (corrija ou "
                "apague, se for lixo) e rode `migrar-produtos` de novo."
            )
            continue
        if participacao_vazia:
            participacao = _participation_from_legacy_ficha(produto_id, ficha)
            if args.aplicar:
                write_participation(caminho_projeto, produto_id, participacao)
        ficha_limpa = {
            key: value for key, value in ficha.items()
            if key != "projeto" and key not in _PARTICIPATION_LEGACY_KEYS
        }
        if args.aplicar:
            write_yaml(ficha_path, ficha_limpa)
        if not participacao_vazia:
            acao = "participacao ja existia, so a ficha foi limpa"
        elif participacao_alvo.exists():
            acao = f"participacao existente estava vazia/invalida - recuperada do legado em `{legado_projeto}`"
        else:
            acao = f"participacao criada em `{legado_projeto}`"
        migrados.append(f"{produto_id}: {acao}")

    verbo = "Migrado" if args.aplicar else "SERIA migrado (rode com --aplicar para gravar)"
    for linha in migrados:
        print(f"{verbo}: {linha}")
    if ja_limpos:
        print(f"Ja no formato novo (sem campo legado): {ja_limpos} ficha(s).")
    if ambiguos:
        print(f"\nNAO migrado(s) - {len(ambiguos)} caso(s) ambiguo(s), decida manualmente:")
        for linha in ambiguos:
            print(f"  - {linha}")
    if bloqueados:
        print(f"\nBLOQUEADO(S) - {len(bloqueados)} caso(s) com operacao pendente reivindicando "
              "o mesmo arquivo (participacao ou ficha):")
        for linha in bloqueados:
            print(f"  - {linha}")
    if invalidos:
        print(f"\nINVALIDO(S) - {len(invalidos)} caso(s) com participacao existente que nao passa "
              "no contrato minimo (identidade/estado); ficha legada preservada, decida manualmente:")
        for linha in invalidos:
            print(f"  - {linha}")
    print(
        f"\nTotal: {len(migrados)} migravel(is), {ja_limpos} ja limpo(s), "
        f"{len(ambiguos)} ambiguo(s), {len(invalidos)} invalido(s), {len(bloqueados)} bloqueado(s)."
    )
    if args.aplicar and (bloqueados or invalidos):
        raise SystemExit(
            f"{len(bloqueados)} produto(s) nao foram migrados por causa de operacao pendente "
            f"reivindicando o mesmo arquivo e {len(invalidos)} por participacao existente que nao "
            "passa no contrato minimo - ver listas acima. Nada foi escrito para eles. Resolva a "
            "pendencia (bloqueados - rode `operacoes-pendentes` e retome ou apague o journal, com "
            "cuidado) ou corrija/apague a mao a participacao invalida (invalidos), e rode "
            "`migrar-produtos --aplicar` de novo."
        )


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
                    if codigo == "TOKEN" and linha[match.end():match.end() + 1] == "(":
                        # `token = carregar_config_sheets(...)` e codigo lendo um
                        # segredo, nao o segredo. Sem isso, qualquer funcao que
                        # devolva token vira alarme eterno - e alarme que sempre
                        # mente e alarme que se aprende a ignorar.
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

    p = sub.add_parser(
        "vincular-produto",
        help="vincula ficha de produto ja existente a outro projeto, com participacao propria (reaproveitamento)",
    )
    p.add_argument("--produto-id", required=True)
    p.add_argument("--projeto", required=True)
    p.add_argument("--preco-alvo", type=real_number)
    p.add_argument("--preco-teto", type=real_number)
    p.add_argument("--requisito", action="append", default=[])
    p.set_defaults(func=link_product)

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
    p.add_argument("--frete-prazo-dias", type=nonnegative_int)
    p.add_argument("--custo-extra", type=real_number, default=0)
    p.add_argument("--custo-total", type=real_number)
    p.add_argument("--custo-operacional-mensal", type=real_number, default=0)
    p.add_argument("--tco-meses", type=nonnegative_int)
    p.add_argument("--valor-revenda-estimado", type=real_number, default=0)
    p.add_argument("--nota", type=real_number, default=0)
    p.add_argument("--avaliacoes", type=nonnegative_int, default=0)
    p.add_argument("--garantia-meses", type=nonnegative_int)
    p.add_argument("--garantia-tipo", choices=["nacional", "importada", "vendedor", "nenhuma"], default="nenhuma")
    p.add_argument("--link")
    p.add_argument("--flag-suspeita", choices=["", "AVAL_SUSPEITA", "ANCORA", "RECICLADO"], default="")
    p.add_argument("--fonte", choices=["web", "manual"], default="manual")
    p.add_argument("--data", type=iso_datetime, help="AAAA-MM-DD ou AAAA-MM-DDTHH:MM:SS")
    p.add_argument("--estoque", choices=PROVENIENCIA_ESTOQUE_OPCOES, default="",
                    help="disponibilidade observada agora; sem isso, fica sem evidencia registrada")
    p.add_argument("--origem-dados", choices=PROVENIENCIA_ORIGENS, default="observacao_direta",
                    help="de onde vieram os valores desta cotacao (proveniencia)")
    p.add_argument("--evidencia", default="",
                    help="referencia livre a evidencia (URL, nome de relatorio, nota)")
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

    p = sub.add_parser("auditar-decisoes", help="verifica snapshots e contabiliza excecoes por categoria")
    p.add_argument("projeto", nargs="?")
    p.add_argument("--strict", action="store_true")
    p.set_defaults(func=audit_decisions)

    p = sub.add_parser("operacoes-pendentes", help="lista operacoes de varios arquivos interrompidas no meio")
    p.add_argument("--strict", action="store_true", help="sai com codigo 1 se houver alguma pendente")
    p.set_defaults(func=report_pending_operations)

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

    p = sub.add_parser(
        "migrar-produtos",
        help="extrai estado/preco/requisitos legados da ficha para participacao por projeto (frente 5); sem --aplicar so mostra previa",
    )
    p.add_argument("--projeto", help="um projeto especifico; sem isso, considera todos")
    p.add_argument("--aplicar", action="store_true", help="grava de verdade; sem isso so mostra o que seria feito")
    p.set_defaults(func=migrate_products)

    p = sub.add_parser("dados-privados", help="cria a pasta de dados pessoais fora do repositorio")
    p.set_defaults(func=private_data_dir)

    p = sub.add_parser("sincronizar-planilha", help="manda visao geral e comparativos pra uma Google Sheets via Apps Script")
    p.add_argument("--config", help="caminho alternativo do integracao_sheets.json (default: ~/.central-compras/dados-privados/)")
    p.set_defaults(func=sincronizar_planilha)

    p = sub.add_parser("configurar-sheets", help="grava o token desta maquina (a URL ja vem versionada pelo git pull)")
    p.add_argument("--token", required=True, help="o mesmo valor de const TOKEN no Code.gs")
    p.add_argument("--url", help="so para apontar esta maquina a um endpoint de teste; sem isso vale a URL versionada")
    p.set_defaults(func=configurar_sheets)

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
    p.add_argument("--data-compra", type=iso_event_date,
                    help="AAAA-MM-DD da compra, so com --comprado (default: hoje). "
                         "Decidir sem --comprado nunca grava data de compra.")
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
    p.add_argument("--frete-prazo-dias", type=nonnegative_int)
    p.add_argument("--custo-extra", type=real_number)
    p.add_argument("--custo-total", type=real_number)
    p.add_argument("--custo-operacional-mensal", type=real_number)
    p.add_argument("--tco-meses", type=nonnegative_int)
    p.add_argument("--valor-revenda-estimado", type=real_number)
    p.add_argument("--tco-total", type=real_number)
    p.add_argument("--nota", type=real_number)
    p.add_argument("--avaliacoes", type=nonnegative_int)
    p.add_argument("--garantia-meses", type=nonnegative_int)
    p.add_argument("--garantia-tipo", choices=["nacional", "importada", "vendedor", "nenhuma"])
    p.add_argument("--link")
    p.add_argument("--flag-suspeita", choices=["", "AVAL_SUSPEITA", "ANCORA", "RECICLADO"])
    p.add_argument("--data", type=iso_datetime, help="AAAA-MM-DD ou AAAA-MM-DDTHH:MM:SS")
    p.add_argument("--sem-alteracao", action="store_true", help="conferi no site e estava tudo igual ao registrado")
    p.add_argument("--estoque", choices=[o for o in PROVENIENCIA_ESTOQUE_OPCOES if o], default=None,
                    help="disponibilidade que voce conferiu agora")
    p.add_argument("--origem-dados", choices=PROVENIENCIA_ORIGENS, default=None,
                    help="de onde veio o que foi conferido (default: conferencia_humana)")
    p.add_argument("--evidencia", default="",
                    help="referencia livre a evidencia (URL, nome de relatorio, nota)")
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
    p.add_argument("--nota-arrependimento", type=personal_rating, required=True)
    p.add_argument("--compraria-de-novo", choices=["sim", "nao", "talvez"], required=True)
    p.add_argument("--resumo", required=True)
    p.add_argument("--problema")
    p.add_argument("--licao")
    p.add_argument("--nota-vendedor", type=personal_rating, help="0 a 10 para o VENDEDOR, separado do produto")
    p.add_argument("--compraria-do-vendedor", choices=["sim", "nao", "talvez"])
    p.add_argument("--chegou-no-prazo", choices=["sim", "nao", "parcial"])
    p.add_argument("--produto-conforme", choices=["sim", "nao", "parcial"])
    p.add_argument("--defeito", choices=["sim", "nao", "parcial"])
    p.add_argument("--vendedor-respondeu", choices=["sim", "nao", "parcial"])
    p.add_argument("--ainda-usa", choices=["sim", "nao", "parcial"])
    p.add_argument("--valeu-o-que-pagou", choices=["sim", "nao", "parcial"])
    p.add_argument("--o-que-aprendi")
    p.set_defaults(func=fill_verdict)

    p = sub.add_parser("registrar-evento",
                        help="registra data de compra, entrega ou inicio de uso num veredito existente")
    p.add_argument("veredito")
    p.add_argument("--evento", choices=["comprado", "entrega", "inicio_uso"], required=True)
    p.add_argument("--data", type=iso_event_date,
                    help="AAAA-MM-DD do evento (default: hoje). D+30/D+180 so contam a partir "
                         "de --evento inicio_uso; os outros eventos nao mexem no prazo.")
    p.set_defaults(func=register_verdict_event)

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
    p.add_argument("--nota-arrependimento", type=personal_rating)
    p.add_argument("--compraria-de-novo", choices=["sim", "nao", "talvez"])
    p.add_argument("--nota-loja", type=personal_rating, help="nota do VENDEDOR, separada da nota do produto")
    p.add_argument("--compraria-do-vendedor", choices=["sim", "nao", "talvez"])
    p.add_argument("--resumo-vendedor", help="o que a loja fez de bom ou de ruim, separado do produto")
    p.add_argument("--force", action="store_true", help="exporta de novo um veredito ja exportado")
    p.set_defaults(func=learn_from_verdict)

    return parser


def _projeto_alvo_do_comando(args: argparse.Namespace) -> Path | None:
    """Projeto que este comando efetivamente vai tocar - usado tanto para
    travar (`locked_project`) quanto para declarar recursos. `args.projeto`
    quando presente; senao, resolvido a partir da PARTICIPACAO do produto
    (`descartar` e `aguardar-preco` aceitam `--projeto` implicito) - a MESMA
    resolucao que `discard_product`/`wait_price` fazem inteiramente
    (`resolve_participation_project`), replicada aqui para travar e checar
    ANTES delas rodarem, nao depois. Ambiguo (produto participando de mais
    de um projeto) devolve None aqui, sem travar nada - a funcao real recusa
    a operacao antes de escrever, entao nao ha nada a proteger."""
    alvo = getattr(args, "projeto", None)
    produto_id = getattr(args, "produto_id", None)
    if not alvo and not produto_id:
        return None
    try:
        return resolve_participation_project(produto_id or "", alvo)
    except SystemExit:
        return None


def _novo_projeto_id(args: argparse.Namespace) -> str:
    return f"{dt.date.today().year}-{slugify(args.nome)}"


# `processo.md` de um projeto e escrito por `append_timeline`/`mark_steps`/
# `set_process_state`, chamados de dentro de varios comandos - nao so
# `anotar`. O inventario completo (com o que cada um escreve e por que) em
# docs/plano-pendencias-auditoria-2026-09-06.md, secao 2.
def _recursos_diretos_processo(args: argparse.Namespace) -> "set[Path]":
    projeto = _projeto_alvo_do_comando(args)
    return {projeto / "processo.md"} if projeto else set()


def _recursos_diretos_participacao(args: argparse.Namespace) -> "set[Path]":
    """`descartar`/`aguardar-preco` escrevem `processo.md` do projeto E o
    arquivo de participacao (frente 5) - nunca a ficha compartilhada em
    `produtos/`. Ambiguo (sem projeto resolvivel) devolve conjunto vazio: a
    funcao real recusa a operacao antes de escrever, entao nao ha recurso a
    proteger contra outra operacao pendente.

    `vincular-produto` NAO esta nesta tabela: ele tem journal proprio
    (`tracked_operation`), entao a checagem de conflito dele acontece por
    dentro, com `exceto_op_id` da propria operacao - listar aqui tambem
    faria este pre-checa generico (sem excecao de op_id) recusar a propria
    retomada de um `vincular-produto` interrompido."""
    projeto = _projeto_alvo_do_comando(args)
    if not projeto:
        return set()
    recursos = {projeto / "processo.md"}
    produto_id = getattr(args, "produto_id", None)
    if produto_id:
        recursos.add(participation_path(projeto, produto_id))
    return recursos


def _recursos_diretos_regenerar(args: argparse.Namespace) -> "set[Path]":
    projetos = [project_path(args.projeto)] if args.projeto else project_dirs()
    return {projeto / "processo.md" for projeto in projetos}


def _recursos_diretos_novo_projeto(args: argparse.Namespace) -> "set[Path]":
    """So ha recurso a checar se `--force` mira um projeto que JA existe -
    criar um projeto novo nao pode conflitar com nada, porque nada reivindica
    um caminho que ainda nao existia."""
    if not args.force:
        return set()
    alvo = PROJETOS / _novo_projeto_id(args)
    if not alvo.exists():
        return set()
    return {alvo / "decisao.md", alvo / "processo.md"}


def _recursos_diretos_preencher_veredito(args: argparse.Namespace) -> "set[Path]":
    caminho = Path(args.veredito)
    if not caminho.is_absolute():
        caminho = ROOT / args.veredito
    return {caminho}


def _recursos_diretos_novo_veredito(args: argparse.Namespace) -> "set[Path]":
    projeto = project_path(args.projeto)
    return {VEREDITOS / f"{today()}-{projeto.name}.md"}


def _recursos_diretos_registrar_licao(args: argparse.Namespace) -> "set[Path]":
    return {BASE / "licoes.md"}


def _recursos_diretos_registrar_marca(args: argparse.Namespace) -> "set[Path]":
    return {BASE / "marcas" / f"{slugify(args.nome)}.md"}


def _recursos_diretos_registrar_loja(args: argparse.Namespace) -> "set[Path]":
    return {BASE / "lojas" / f"{slugify(args.nome)}.md"}


# Inventario completo (comando -> arquivos -> travas -> checagem de
# conflito) em docs/plano-pendencias-auditoria-2026-09-06.md, secao 2.
# Comandos que escrevem em arquivo que `decidir`/`aprender-veredito` podem
# ter reivindicado, mas nunca passam pelo journal proprio
# (`tracked_operation`). Cada resolver devolve os arquivos que o comando
# vai escrever; `main()` checa conflito com operacao pendente UMA VEZ,
# centralizado, antes de chamar `args.func` - nao um a um dentro de cada
# funcao. `_recursos_diretos_processo` cobre TODO comando que grava
# processo.md por fora de decidir (nao so anotar): cotar, promover-cotacao,
# novo-produto, ranking, descartar, aguardar-preco chamam append_timeline/
# mark_steps/set_process_state internamente, direto ou via build_ranking.
RECURSOS_DIRETOS_POR_COMANDO: dict[str, Any] = {
    "novo-projeto": _recursos_diretos_novo_projeto,
    "anotar": _recursos_diretos_processo,
    "cotar": _recursos_diretos_processo,
    "promover-cotacao": _recursos_diretos_processo,
    "novo-produto": _recursos_diretos_processo,
    "ranking": _recursos_diretos_processo,
    "descartar": _recursos_diretos_participacao,
    "aguardar-preco": _recursos_diretos_participacao,
    "regenerar": _recursos_diretos_regenerar,
    "preencher-veredito": _recursos_diretos_preencher_veredito,
    "novo-veredito": _recursos_diretos_novo_veredito,
    "registrar-licao": _recursos_diretos_registrar_licao,
    "registrar-marca": _recursos_diretos_registrar_marca,
    "registrar-loja": _recursos_diretos_registrar_loja,
}


MUTATING_COMMANDS = {
    "cotar", "promover-cotacao", "decidir", "anotar", "novo-produto",
    "ranking", "validar", "auditar", "historico", "descartar", "aguardar-preco",
    "novo-veredito", "regenerar", "migrar-cotacoes", "vincular-produto", "migrar-produtos",
}

# Comandos que escrevem em `base-conhecimento/`. No Windows o O_APPEND e
# emulado (posiciona e escreve), entao anexar nao basta: sem trava, 30 licoes
# em paralelo viravam 29 e ninguem era avisado.
KNOWLEDGE_COMMANDS = {
    "registrar-marca", "registrar-loja", "registrar-licao", "aprender-veredito",
    "reaproveitamento", "listar-aguardando-preco", "regenerar", "decidir",
    "preencher-veredito", "registrar-evento",
}

PRODUCT_COMMANDS = {"novo-produto", "descartar", "aguardar-preco", "vincular-produto", "migrar-produtos"}
ALL_PROJECT_COMMANDS = {"dashboard", "regenerar", "migrar-cotacoes", "migrar-produtos"}


def locked_project(args: argparse.Namespace) -> Path | None:
    """Projeto que este comando vai escrever, se houver um so.

    `descartar`/`aguardar-preco` aceitam `--projeto` implicito (resolvido a
    partir do produto) - sem essa resolucao aqui, o comando rodava SEM
    travar projeto nenhum quando `--projeto` era omitido, mesmo escrevendo
    em `processo.md` daquele projeto.
    """
    return _projeto_alvo_do_comando(args)


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
            # --force num projeto que JA existe escreve dentro dele: sem
            # travar o proprio projeto (so travar a raiz `PROJETOS` nao
            # basta), ele podia rodar concorrente com um `decidir` do mesmo
            # projeto sem serializar com a trava dele.
            alvo_existente = PROJETOS / _novo_projeto_id(args)
            if alvo_existente.exists():
                alvos.add(alvo_existente)
        if args.comando == "registrar-evento" and getattr(args, "evento", None) == "comprado":
            # So sabemos QUAL projeto depois de ler o veredito (nao ha
            # `args.projeto` neste comando) - mesma resolucao usada por
            # `register_verdict_event` pra travar e checar recurso ANTES
            # dele rodar, nao depois. `None` (sem decisao aberta deste
            # produto, ou veredito standalone) nao trava nada: a funcao
            # real so escreve o proprio veredito nesse caso.
            projeto_evento = _projeto_da_confirmacao_de_compra(args.veredito)
            if projeto_evento is not None:
                alvos.add(projeto_evento)
        if args.comando == "dashboard":
            alvos.update({BASE, DASHBOARD, PROJETOS, *project_dirs()})
        if args.comando in ALL_PROJECT_COMMANDS and not getattr(args, "projeto", None):
            alvos.update(project_dirs())
        for alvo in sorted(alvos, key=lambda path: str(path.resolve()).casefold()):
            travas.enter_context(project_lock(alvo))
        # Escritores diretos (sem journal proprio) checam conflito com
        # operacao pendente aqui, ja dentro das travas acima, antes de
        # `args.func` fazer a 1a escrita. `decidir`/`aprender-veredito` tem
        # a propria checagem equivalente dentro de `tracked_operation`.
        resolver_recursos = RECURSOS_DIRETOS_POR_COMANDO.get(args.comando)
        if resolver_recursos is not None:
            _bloquear_se_recursos_conflitantes(
                resolver_recursos(args), contexto=f"executar '{args.comando}'"
            )
        args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
