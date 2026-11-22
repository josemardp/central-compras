"""SQLite do radar: esquema versionado, migracoes com rollback e backup.

Um unico arquivo (radar.db) sob a responsabilidade deste repositorio. Sem
servidor, sem ORM. O historico original (historico.jsonl dos rastreadores)
continua intacto; o banco guarda uma copia normalizada e idempotente.
"""

from __future__ import annotations

import datetime as dt
import shutil
import sqlite3
from pathlib import Path

from . import caminhos

# (versao, descricao, SQL para subir, SQL para descer)
MIGRACOES: list[tuple[int, str, str, str]] = [
    (
        1,
        "esquema inicial: observacoes, ofertas, alertas, execucoes, jobs, fontes, outbox",
        """
        CREATE TABLE observacoes (
            id INTEGER PRIMARY KEY,
            origem TEXT NOT NULL,
            produto TEXT NOT NULL,
            coletado_em TEXT NOT NULL,
            preco_entregue REAL,
            onde TEXT,
            parcelamento TEXT,
            validacao TEXT NOT NULL DEFAULT 'COLETA_PROPRIA',
            degradada INTEGER NOT NULL DEFAULT 0,
            hash TEXT NOT NULL UNIQUE
        );
        CREATE INDEX ix_obs_produto_data ON observacoes(produto, coletado_em);

        CREATE TABLE ofertas (
            id INTEGER PRIMARY KEY,
            fonte TEXT NOT NULL,
            canal TEXT NOT NULL DEFAULT '',
            id_externo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            url TEXT,
            url_norm TEXT,
            loja TEXT,
            vendedor TEXT,
            produto TEXT,
            preco_anunciado REAL,
            frete REAL,
            cupom_codigo TEXT,
            cupom_json TEXT,
            status_cupom TEXT,
            preco_final REAL,
            final_estimado INTEGER NOT NULL DEFAULT 1,
            detectado_em TEXT NOT NULL,
            publicado_em TEXT,
            ultima_vista_em TEXT NOT NULL,
            classe TEXT,
            score REAL,
            motivo TEXT,
            UNIQUE (fonte, canal, id_externo)
        );
        CREATE INDEX ix_ofertas_produto ON ofertas(produto, detectado_em);

        CREATE TABLE alertas (
            id INTEGER PRIMARY KEY,
            oferta_id INTEGER,
            chave TEXT NOT NULL,
            produto TEXT,
            enviado_em TEXT NOT NULL,
            classe TEXT,
            preco REAL,
            cupom TEXT,
            status_cupom TEXT,
            modo TEXT NOT NULL,
            detalhe TEXT
        );
        CREATE INDEX ix_alertas_chave ON alertas(chave, enviado_em);

        CREATE TABLE execucoes (
            id INTEGER PRIMARY KEY,
            job TEXT NOT NULL,
            passo TEXT,
            inicio TEXT NOT NULL,
            fim TEXT,
            status TEXT NOT NULL,
            codigo INTEGER,
            resumo TEXT
        );
        CREATE INDEX ix_exec_job ON execucoes(job, inicio);

        CREATE TABLE jobs_estado (
            job TEXT PRIMARY KEY,
            ultima_execucao TEXT,
            ultimo_status TEXT,
            ultimo_sucesso TEXT,
            falhas_consecutivas INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE fontes_saude (
            fonte TEXT PRIMARY KEY,
            ultimo_ok TEXT,
            ultimo_erro TEXT,
            erro_msg TEXT,
            falhas_consecutivas INTEGER NOT NULL DEFAULT 0,
            itens_ultima INTEGER,
            ultima_tentativa TEXT
        );

        CREATE TABLE outbox (
            id INTEGER PRIMARY KEY,
            criado_em TEXT NOT NULL,
            origem TEXT,
            texto TEXT NOT NULL,
            tentativas INTEGER NOT NULL DEFAULT 0,
            ultimo_erro TEXT,
            enviado_em TEXT
        );
        """,
        """
        DROP TABLE outbox;
        DROP TABLE fontes_saude;
        DROP TABLE jobs_estado;
        DROP TABLE execucoes;
        DROP TABLE alertas;
        DROP TABLE ofertas;
        DROP TABLE observacoes;
        """,
    ),
    (
        2,
        "invalidacao auditavel de observacoes, fila com tipo/validade, telemetria por ciclo de coleta",
        """
        ALTER TABLE observacoes ADD COLUMN invalida INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE observacoes ADD COLUMN preco_corrigido REAL;
        ALTER TABLE observacoes ADD COLUMN correcao_motivo TEXT;

        ALTER TABLE outbox ADD COLUMN tipo TEXT NOT NULL DEFAULT 'relatorio';
        ALTER TABLE outbox ADD COLUMN expira_em TEXT;
        ALTER TABLE outbox ADD COLUMN oferta_id INTEGER;
        ALTER TABLE outbox ADD COLUMN desfecho TEXT;

        CREATE TABLE coletas_ciclo (
            id INTEGER PRIMARY KEY,
            ciclo_em TEXT NOT NULL,
            fonte TEXT NOT NULL,
            status TEXT NOT NULL,
            itens INTEGER NOT NULL DEFAULT 0,
            casadas INTEGER NOT NULL DEFAULT 0,
            cupons_extraidos INTEGER NOT NULL DEFAULT 0,
            cupons_aplicados INTEGER NOT NULL DEFAULT 0,
            descartes_json TEXT,
            erro TEXT
        );
        CREATE INDEX ix_ciclo_data ON coletas_ciclo(ciclo_em, fonte);
        """,
        """
        DROP TABLE coletas_ciclo;
        ALTER TABLE outbox DROP COLUMN desfecho;
        ALTER TABLE outbox DROP COLUMN oferta_id;
        ALTER TABLE outbox DROP COLUMN expira_em;
        ALTER TABLE outbox DROP COLUMN tipo;
        ALTER TABLE observacoes DROP COLUMN correcao_motivo;
        ALTER TABLE observacoes DROP COLUMN preco_corrigido;
        ALTER TABLE observacoes DROP COLUMN invalida;
        """,
    ),
    (
        3,
        "validacao manual persistente (radar validar) por oferta",
        """
        CREATE TABLE validacoes_manuais (
            oferta_id INTEGER PRIMARY KEY,
            por TEXT NOT NULL,
            em TEXT NOT NULL,
            preco_validado REAL
        );
        """,
        "DROP TABLE validacoes_manuais;",
    ),
    (
        4,
        "tres horas separadas (published/first_seen/collected) e fila de candidatos a alerta com prioridade",
        """
        ALTER TABLE ofertas ADD COLUMN primeira_vista_em TEXT;
        ALTER TABLE ofertas ADD COLUMN coletado_em TEXT;
        ALTER TABLE ofertas ADD COLUMN hora_incerta INTEGER NOT NULL DEFAULT 0;

        CREATE TABLE candidatos_alerta (
            id INTEGER PRIMARY KEY,
            oferta_id INTEGER,
            produto TEXT NOT NULL,
            familia TEXT NOT NULL,
            classe TEXT NOT NULL,
            score REAL NOT NULL,
            componentes_json TEXT,
            preco_final REAL,
            economia REAL,
            economia_pct REAL,
            status_cupom TEXT,
            cupom TEXT,
            fonte TEXT,
            hora_incerta INTEGER NOT NULL DEFAULT 0,
            mensagem TEXT NOT NULL,
            url TEXT,
            estado TEXT NOT NULL DEFAULT 'pendente',
            motivo TEXT,
            criado_em TEXT NOT NULL,
            expira_em TEXT NOT NULL,
            decidido_em TEXT
        );
        CREATE INDEX ix_cand_estado ON candidatos_alerta(estado, criado_em);
        CREATE INDEX ix_cand_produto ON candidatos_alerta(produto, decidido_em);
        """,
        """
        DROP TABLE candidatos_alerta;
        ALTER TABLE ofertas DROP COLUMN hora_incerta;
        ALTER TABLE ofertas DROP COLUMN coletado_em;
        ALTER TABLE ofertas DROP COLUMN primeira_vista_em;
        """,
    ),
]

VERSAO_ATUAL = max(m[0] for m in MIGRACOES)


def agora() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _conectar(caminho: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(caminho), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def versao_aplicada(con: sqlite3.Connection) -> int:
    con.execute(
        "CREATE TABLE IF NOT EXISTS schema_migracoes (versao INTEGER PRIMARY KEY, descricao TEXT, aplicada_em TEXT)"
    )
    row = con.execute("SELECT MAX(versao) AS v FROM schema_migracoes").fetchone()
    return int(row["v"] or 0)


def backup(caminho: Path | None = None, motivo: str = "manual") -> Path | None:
    """Copia o banco (com o WAL consolidado) para backups/. Retorna None se ainda nao existe."""
    origem = caminho or caminhos.db_path()
    if not origem.exists():
        return None
    destino = caminhos.backups_dir() / f"radar-{dt.datetime.now():%Y%m%d-%H%M%S}-{motivo}.db"
    con = _conectar(origem)
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        con.close()
    shutil.copy2(origem, destino)
    return destino


def migrar(con: sqlite3.Connection, alvo: int | None = None) -> list[int]:
    """Aplica migracoes pendentes ate `alvo` (padrao: a mais nova). Retorna as versoes aplicadas."""
    alvo = VERSAO_ATUAL if alvo is None else alvo
    atual = versao_aplicada(con)
    aplicadas: list[int] = []
    for versao, descricao, sql_up, _ in MIGRACOES:
        if atual < versao <= alvo:
            con.executescript("BEGIN;" + sql_up + "COMMIT;")
            con.execute(
                "INSERT INTO schema_migracoes (versao, descricao, aplicada_em) VALUES (?,?,?)",
                (versao, descricao, agora()),
            )
            con.commit()
            aplicadas.append(versao)
    return aplicadas


def reverter(con: sqlite3.Connection, alvo: int) -> list[int]:
    """Desfaz migracoes acima de `alvo` (rollback). Faca backup antes."""
    atual = versao_aplicada(con)
    desfeitas: list[int] = []
    for versao, _, _, sql_down in sorted(MIGRACOES, key=lambda m: m[0], reverse=True):
        if alvo < versao <= atual:
            con.executescript("BEGIN;" + sql_down + "COMMIT;")
            con.execute("DELETE FROM schema_migracoes WHERE versao = ?", (versao,))
            con.commit()
            desfeitas.append(versao)
    return desfeitas


def abrir(caminho: Path | None = None, *, migrar_automatico: bool = True) -> sqlite3.Connection:
    """Abre o banco; se for a primeira vez ou houver migracao pendente, faz backup e migra."""
    destino = caminho or caminhos.db_path()
    destino.parent.mkdir(parents=True, exist_ok=True)
    existia = destino.exists()
    con = _conectar(destino)
    if migrar_automatico and versao_aplicada(con) < VERSAO_ATUAL:
        if existia:
            con.close()
            backup(destino, motivo="pre-migracao")
            con = _conectar(destino)
        migrar(con)
    return con
