"""
Conexão com o PostgreSQL (Aiven).

A URL vem da variável de ambiente DATABASE_URL (arquivo .env no ambiente local,
variável de ambiente no serviço de hospedagem). Nada de credencial no código.
"""
import os
import time
from contextlib import contextmanager

import pandas as pd
import psycopg2
from psycopg2 import pool

try:
    from dotenv import find_dotenv, load_dotenv

    # procura o .env subindo a partir da pasta atual (funciona rodando de projeto/ ou da raiz)
    load_dotenv(find_dotenv(usecwd=True))
except ImportError:
    pass

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("Defina DATABASE_URL (ex.: no arquivo .env) para o dashboard acessar o banco.")
        _pool = pool.ThreadedConnectionPool(
            1, 5, url,
            connect_timeout=10,
            application_name="dashboard_mortalidade_materna",
            # mantém a conexão viva: a Aiven derruba conexões ociosas
            keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
        )
    return _pool


@contextmanager
def conexao():
    p = _get_pool()
    conn = p.getconn()
    # só leitura: autocommit dispensa o BEGIN/ROLLBACK (uma ida a menos ao servidor por atualização)
    if not conn.autocommit:
        conn.autocommit = True
    try:
        yield conn
        p.putconn(conn)
    except psycopg2.OperationalError:
        p.putconn(conn, close=True)  # conexão caiu: descarta em vez de devolver ao pool
        raise
    except Exception:
        p.putconn(conn)
        raise


class Sessao:
    """Executa consultas numa mesma conexão e mede o tempo gasto no banco."""

    def __init__(self, conn):
        self.conn = conn
        self.n_consultas = 0
        self.ms = 0.0

    def lote(self, consultas):
        """
        Recebe {nome: (sql, params)} e executa tudo numa única ida ao banco.

        Cada consulta vira uma subconsulta que devolve suas linhas em JSON:
            SELECT (SELECT json_agg(t) FROM (<consulta 1>) t) AS nome1,
                   (SELECT json_agg(t) FROM (<consulta 2>) t) AS nome2, ...
        Devolve {nome: DataFrame}.
        """
        nomes = list(consultas)
        partes, params = [], []
        for nome in nomes:
            sql, p = consultas[nome]
            partes.append(f"(SELECT COALESCE(json_agg(t), '[]'::json) FROM ({sql}) t) AS {nome}")
            params.extend(p)
        inicio = time.perf_counter()
        with self.conn.cursor() as cur:
            cur.execute("SELECT " + ",\n".join(partes), params)
            linha = cur.fetchone()  # o psycopg2 já converte json em listas de dicionários
        self.ms += (time.perf_counter() - inicio) * 1000
        self.n_consultas += len(nomes)
        return {nome: pd.DataFrame(registros) for nome, registros in zip(nomes, linha)}


def executar(func, *args, tentativas=2):
    """Roda func(sessao, *args); se a conexão tiver caído, tenta de novo com uma nova."""
    for i in range(tentativas):
        try:
            with conexao() as conn:
                sessao = Sessao(conn)
                return func(sessao, *args), sessao
        except psycopg2.OperationalError:
            if i == tentativas - 1:
                raise


def info_servidor():
    with conexao() as conn, conn.cursor() as cur:
        cur.execute("SELECT split_part(version(), ' ', 2), current_database()")
        versao, banco = cur.fetchone()
        host = conn.info.host
    return {"versao": versao, "banco": banco, "host": host}
