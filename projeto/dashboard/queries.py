"""
Consultas SQL do dashboard. Toda agregação é feita no PostgreSQL a cada mudança de filtro
(nada é pré-calculado no Python), então o que aparece na tela é sempre o estado atual do banco.

Cada função devolve (sql, parâmetros). O db.Sessao.lote() junta todas numa única ida ao banco:
com o servidor da Aiven a ~185 ms de distância, 8 consultas em sequência levavam ~1,9 s; em lote, ~0,2 s.

Os filtros viram parâmetros (%s) do psycopg2: o usuário nunca escreve SQL.
"""
from dataclasses import dataclass, field

OFICIAIS = "painel.obitos_maternos_oficiais"
DESCONS = "painel.obitos_desconsiderados"

NEGRAS = "('Preta', 'Parda')"
# CID-10 X85–Y09 = agressões (homicídios). Comparação de texto funciona: X85..X99, Y00..Y09.
AGRESSAO = "cod_categoria BETWEEN 'X85' AND 'Y09'"


@dataclass
class Filtros:
    ano_ini: int = 2014
    ano_fim: int = 2024
    regioes: list = field(default_factory=list)
    ufs: list = field(default_factory=list)
    racas: list = field(default_factory=list)
    faixas: list = field(default_factory=list)

    def where(self):
        """Devolve (cláusula WHERE, parâmetros). Lista vazia = sem filtro naquela dimensão."""
        partes = ["ano BETWEEN %s AND %s"]
        params = [self.ano_ini, self.ano_fim]
        for coluna, valores in (("regiao", self.regioes), ("uf", self.ufs),
                                ("raca_cor", self.racas), ("faixa_etaria", self.faixas)):
            if valores:
                partes.append(f"{coluna} = ANY(%s)")
                params.append(list(valores))
        return "WHERE " + " AND ".join(partes), params


def kpis_oficiais(f: Filtros):
    w, p = f.where()
    return f"""
        SELECT
            COALESCE(SUM(qtd_obitos), 0)                                               AS total,
            COUNT(DISTINCT ano)                                                        AS anos,
            COALESCE(SUM(qtd_obitos) FILTER (WHERE raca_cor IN {NEGRAS}), 0)           AS negras,
            COALESCE(SUM(qtd_obitos) FILTER (WHERE raca_cor <> 'Ignorado'), 0)         AS raca_informada,
            COALESCE(SUM(qtd_obitos) FILTER (WHERE tipo_morte_materna = 'Direta'), 0)  AS diretas,
            COALESCE(SUM(qtd_obitos) FILTER (WHERE investigacao_cmm <> 'Sim'), 0)      AS sem_cmm
        FROM {OFICIAIS} {w}
    """, p


def kpis_agressoes(f: Filtros):
    w, p = f.where()
    return f"""
        SELECT
            COALESCE(SUM(qtd_obitos), 0)                                       AS total,
            COALESCE(SUM(qtd_obitos) FILTER (WHERE raca_cor IN {NEGRAS}), 0)   AS negras,
            COALESCE(SUM(qtd_obitos) FILTER (WHERE raca_cor <> 'Ignorado'), 0) AS raca_informada
        FROM {DESCONS} {w} AND {AGRESSAO}
    """, p


def por_raca(f: Filtros):
    """Resumo por raça/cor usado na 'leitura rápida' (comparações entre grupos)."""
    w, p = f.where()
    return f"""
        SELECT raca_cor,
               SUM(qtd_obitos)                                                  AS total,
               SUM(qtd_obitos) FILTER (WHERE tipo_morte_materna = 'Direta')     AS diretas,
               SUM(qtd_obitos) FILTER (WHERE investigacao_cmm <> 'Sim')         AS sem_cmm,
               SUM(qtd_obitos) FILTER (WHERE idade < 20)                        AS adolescentes
        FROM {OFICIAIS} {w}
        GROUP BY raca_cor
    """, p


def serie_anual(f: Filtros):
    w, p = f.where()
    return f"""
        SELECT ano, raca_cor, SUM(qtd_obitos) AS obitos
        FROM {OFICIAIS} {w}
        GROUP BY ano, raca_cor
        ORDER BY ano
    """, p


# métrica escolhida no seletor "indicador em foco" -> expressão SQL (numerador, denominador)
METRICAS = {
    "obitos": ("SUM(qtd_obitos)", None),
    "negras": (f"SUM(qtd_obitos) FILTER (WHERE raca_cor IN {NEGRAS})",
               "SUM(qtd_obitos) FILTER (WHERE raca_cor <> 'Ignorado')"),
    "diretas": ("SUM(qtd_obitos) FILTER (WHERE tipo_morte_materna = 'Direta')", "SUM(qtd_obitos)"),
    "sem_cmm": ("SUM(qtd_obitos) FILTER (WHERE investigacao_cmm <> 'Sim')", "SUM(qtd_obitos)"),
}
DIMENSOES = {"faixa_etaria", "regiao", "periodo_obito"}  # lista fechada: entra no SQL como nome de coluna


def por_uf(f: Filtros, metrica):
    num, den = METRICAS[metrica]
    w, p = f.where()
    return f"""
        SELECT uf, regiao,
               COALESCE({num}, 0)                      AS numerador,
               COALESCE({den or 'SUM(qtd_obitos)'}, 0) AS denominador
        FROM {OFICIAIS} {w}
        GROUP BY uf, regiao
    """, p


def matriz(f: Filtros, metrica, dimensao):
    if dimensao not in DIMENSOES:
        raise ValueError(dimensao)
    num, den = METRICAS[metrica]
    if metrica == "negras":
        # cruzar "% de negras" com a própria raça/cor daria só 100% ou 0%; aqui a pergunta vira
        # "em cada faixa/região, qual a participação de cada raça/cor nos óbitos?"
        num, den = "SUM(qtd_obitos)", f"(SUM(SUM(qtd_obitos)) OVER (PARTITION BY {dimensao}))::bigint"
    w, p = f.where()
    return f"""
        SELECT raca_cor, {dimensao} AS coluna,
               COALESCE({num}, 0)                      AS numerador,
               COALESCE({den or 'SUM(qtd_obitos)'}, 0) AS denominador
        FROM {OFICIAIS} {w}
        GROUP BY raca_cor, {dimensao}
    """, p


def principais_causas(f: Filtros, limite=10):
    w, p = f.where()
    return f"""
        SELECT cod_categoria, categoria_descricao, tipo_morte_materna, SUM(qtd_obitos) AS obitos
        FROM {OFICIAIS} {w}
        GROUP BY cod_categoria, categoria_descricao, tipo_morte_materna
        ORDER BY obitos DESC
        LIMIT {int(limite)}
    """, p


def causas_externas(f: Filtros):
    """Óbitos de grávidas/puérperas por causas externas (CID-10 cap. XX), que ficam fora da contagem oficial."""
    w, p = f.where()
    return f"""
        SELECT ano,
               CASE
                   WHEN {AGRESSAO}                                  THEN 'Agressão (homicídio)'
                   WHEN cod_categoria BETWEEN 'X60' AND 'X84'       THEN 'Lesão autoprovocada (suicídio)'
                   WHEN cod_categoria LIKE 'V%%'                    THEN 'Acidente de transporte'
                   ELSE 'Outras causas externas'
               END AS grupo,
               SUM(qtd_obitos) AS obitos
        FROM {DESCONS} {w} AND substr(cod_categoria, 1, 1) IN ('V', 'W', 'X', 'Y')
        GROUP BY 1, 2
        ORDER BY 1
    """, p


def painel(f: Filtros, metrica, dimensao):
    """Todas as consultas que uma atualização da tela precisa, para irem juntas num lote."""
    return {
        "oficiais": kpis_oficiais(f),
        "agressoes": kpis_agressoes(f),
        "serie": serie_anual(f),
        "causas": principais_causas(f),
        "uf": por_uf(f, metrica),
        "matriz": matriz(f, metrica, dimensao),
        "externas": causas_externas(f),
        "raca": por_raca(f),
    }


def opcoes():
    """Valores distintos para montar os filtros (lidos do banco na abertura da página)."""
    return {
        "ufs": (f"SELECT DISTINCT regiao, uf FROM {OFICIAIS} ORDER BY regiao, uf", []),
        "faixas": (f"SELECT DISTINCT faixa_etaria FROM {OFICIAIS} ORDER BY faixa_etaria", []),
        "anos": (f"SELECT MIN(ano) AS ini, MAX(ano) AS fim FROM {OFICIAIS}", []),
    }
