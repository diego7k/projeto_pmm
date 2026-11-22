# Dashboard da mortalidade materna (Plotly Dash). Consulta o PostgreSQL da Aiven a cada filtro.
# Rodar de dentro de projeto/: python dashboard/app.py  (abre em http://127.0.0.1:8050)
# No Render roda com gunicorn --chdir dashboard app:server
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html, no_update

import db
import queries as q

AQUI = Path(__file__).parent
GEOJSON = json.loads((AQUI / "br_ufs.geojson").read_text(encoding="utf-8"))
FUSO = ZoneInfo("America/Sao_Paulo")

# cores
PRETO = "#0b0b0b"
CINZA_ESCURO = "#52514e"
CINZA = "#898781"
CINZA_CLARO = "#e1e0d9"
COR_EIXO = "#c3c2b7"
BRANCO = "#fcfcfb"

# cada raça/cor tem sempre a mesma cor, em todos os gráficos
CORES_RACA = {
    "Parda": "#2a78d6",
    "Preta": "#eb6834",
    "Branca": "#1baf7a",
    "Indígena": "#eda100",
    "Amarela": "#e87ba4",
    "Ignorado": "#b5b3ab",
}
ORDEM_RACA = list(CORES_RACA)

CORES_TIPO = {"Direta": "#6250d6", "Indireta": "#b5b3ab", "Não especificada": "#d9d7cf"}
CORES_EXTERNAS = {
    "Agressão (homicídio)": "#e34948",
    "Lesão autoprovocada (suicídio)": "#6f6d68",
    "Acidente de transporte": "#a3a19a",
    "Outras causas externas": "#d3d1c9",
}
# azul claro -> escuro, usado no mapa e na matriz
AZUIS = ["#e8f1fc", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
ESCALA_AZUL = [[i / (len(AZUIS) - 1), c] for i, c in enumerate(AZUIS)]

METRICAS = {
    "negras": "% de mulheres negras",
    "diretas": "% causas obstétricas diretas",
    "sem_cmm": "% sem investigação do CMM",
    "obitos": "Nº de óbitos",
}
DIMENSOES = {"faixa_etaria": "Faixa etária", "regiao": "Região", "periodo_obito": "Momento do óbito"}
ROTULO_PERIODO = {
    "Durante a gravidez, parto ou aborto": "Gravidez/parto/aborto",
    "Durante o puerpério, até 42 dias": "Puerpério ≤ 42 dias",
    "Durante o puerpério, de 43 dias a menos de 1 ano": "Puerpério tardio",
    "Não na gravidez ou no puerpério": "Fora da gravidez/puerpério",
    "Não informado ou ignorado": "Não informado",
    "Período inconsistente": "Inconsistente",
}
LEGENDA_MATRIZ = {
    "negras": "Cada célula: participação da raça/cor no total de óbitos da coluna (cada coluna soma 100%).",
    "diretas": "Cada célula: % dos óbitos do grupo causados por complicações obstétricas diretas.",
    "sem_cmm": "Cada célula: % dos óbitos do grupo sem investigação registrada pelo Comitê de Mortalidade Materna.",
    "obitos": "Cada célula: número de óbitos maternos oficiais do grupo.",
}
MIN_CASOS = 20  # com menos de 20 óbitos a % muda muito com 1 caso, então não mostramos


def fmt_int(n):
    return f"{int(n):,}".replace(",", ".")


def fmt_pct(x, casas=1):
    return "–" if x is None or pd.isna(x) else f"{x:.{casas}f}%".replace(".", ",")


def pct(num, den):
    return None if not den else num / den * 100


def layout_base(fig, altura=340, **kw):
    fig.update_layout(
        height=altura,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family='system-ui, -apple-system, "Segoe UI", Roboto, sans-serif', size=12, color=CINZA_ESCURO),
        separators=",.",
        hoverlabel=dict(bgcolor="white", bordercolor=CINZA_CLARO, font=dict(color=PRETO, size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title=None,
                    font=dict(color=CINZA_ESCURO)),
        **kw,
    )
    fig.update_xaxes(showgrid=False, linecolor=COR_EIXO, ticks="", tickfont=dict(color=CINZA), zeroline=False)
    fig.update_yaxes(gridcolor=CINZA_CLARO, gridwidth=1, zeroline=False, linecolor=COR_EIXO, tickfont=dict(color=CINZA))
    return fig


def figura_vazia(msg="Sem dados para os filtros escolhidos", altura=340):
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font=dict(color=CINZA, size=13), x=0.5, y=0.5,
                       xref="paper", yref="paper")
    layout_base(fig, altura)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


# gráficos
def fig_serie(df, modo):
    if df.empty:
        return figura_vazia()
    tabela = df.pivot_table(index="ano", columns="raca_cor", values="obitos", aggfunc="sum").fillna(0)
    if modo == "pct":
        tabela = tabela.div(tabela.sum(axis=1), axis=0) * 100
    fig = go.Figure()
    anos = tabela.index.tolist()
    if 2020 in anos or 2021 in anos:
        fig.add_vrect(x0=2019.5, x1=2021.5, fillcolor="#f0efec", line_width=0, layer="below")
        fig.add_annotation(x=2020.5, y=1, yref="paper", text="COVID-19", showarrow=False,
                           font=dict(size=11, color=CINZA), yanchor="top")
    if 2024 in anos:
        fig.add_annotation(x=2024, y=1, yref="paper", text="preliminar", showarrow=False,
                           font=dict(size=11, color=CINZA), yanchor="top", xanchor="center")
    for raca in ORDEM_RACA:
        if raca not in tabela:
            continue
        y = tabela[raca]
        formato = "%{y:.1f}% dos óbitos do ano" if modo == "pct" else "%{y:,.0f} óbitos"
        fig.add_trace(go.Scatter(
            x=anos, y=y, name=raca, mode="lines+markers",
            line=dict(color=CORES_RACA[raca], width=2, shape="linear"),
            marker=dict(size=8, color=CORES_RACA[raca], line=dict(color=BRANCO, width=2)),
            hovertemplate=f"<b>{raca}</b>: {formato}<extra></extra>",
        ))
    layout_base(fig, 340, hovermode="x unified")
    fig.update_xaxes(dtick=1)
    fig.update_yaxes(ticksuffix="%" if modo == "pct" else "", tickformat=",d", rangemode="tozero")
    return fig


def fig_mapa(df, metrica):
    if df.empty or df["denominador"].sum() == 0:
        return figura_vazia(altura=400)
    df = df.copy()
    if metrica == "obitos":
        df["valor"] = df["numerador"]
        df["texto"] = df["numerador"].map(fmt_int) + " óbitos"
        barra = dict(title=None, tickformat=",.0f")
    else:
        df["valor"] = df["numerador"] / df["denominador"].where(df["denominador"] >= MIN_CASOS) * 100
        df["texto"] = [
            f"{fmt_pct(v)} ({fmt_int(n)} de {fmt_int(d)})" if pd.notna(v) else f"poucos casos (n={fmt_int(d)})"
            for v, n, d in zip(df["valor"], df["numerador"], df["denominador"])
        ]
        barra = dict(title=None, ticksuffix="%")
    fig = go.Figure(go.Choropleth(
        geojson=GEOJSON, featureidkey="properties.sigla",
        locations=df["uf"], z=df["valor"], customdata=df[["texto"]],
        zmin=0, zmax=max(df["valor"].max(), 1) if df["valor"].notna().any() else 1,
        colorscale=ESCALA_AZUL,
        marker_line_color="white", marker_line_width=0.8,
        colorbar=dict(thickness=10, len=0.6, outlinewidth=0, tickfont=dict(color=CINZA), **barra),
        hovertemplate="<b>%{location}</b><br>%{customdata[0]}<extra></extra>",
    ))
    fig.update_geos(visible=False, fitbounds="locations", projection_type="mercator", bgcolor="rgba(0,0,0,0)")
    layout_base(fig, 400)
    return fig


def fig_matriz(df, metrica, dimensao):
    if df.empty or df["denominador"].sum() == 0:
        return figura_vazia(altura=400), []
    df = df.copy()
    if dimensao == "periodo_obito":
        df["coluna"] = df["coluna"].map(ROTULO_PERIODO).fillna(df["coluna"])
    tab_num = df.pivot_table(index="raca_cor", columns="coluna", values="numerador", aggfunc="sum").fillna(0)
    tab_den = df.pivot_table(index="raca_cor", columns="coluna", values="denominador", aggfunc="sum").fillna(0)
    linhas = [r for r in ORDEM_RACA if r in tab_num.index and r != "Ignorado"] or list(tab_num.index)
    if dimensao == "periodo_obito":
        colunas = [c for c in ROTULO_PERIODO.values() if c in tab_num.columns]
    else:
        colunas = sorted(c for c in tab_num.columns if c != "Ignorada")
    tab_num = tab_num.reindex(index=linhas, columns=colunas)
    tab_den = tab_den.reindex(index=linhas, columns=colunas)

    if metrica == "obitos":
        valores = tab_num
        texto = tab_num.map(lambda v: fmt_int(v) if v else "")
        sufixo = ""
    else:
        valores = (tab_num / tab_den.where(tab_den >= MIN_CASOS)) * 100
        if metrica != "negras":
            # tira as linhas que ficariam todas em branco
            manter = valores.notna().any(axis=1)
            if manter.any():
                valores, tab_num, tab_den = valores[manter], tab_num[manter], tab_den[manter]
                linhas = valores.index.tolist()
        texto = valores.map(lambda v: "" if pd.isna(v) else f"{v:.0f}%")
        sufixo = "%"
    # texto do mouse em cada célula (o mesmo texto vai para a tabela embaixo do gráfico)
    hover = []
    for i in range(len(linhas)):
        linha = []
        for j in range(len(colunas)):
            n = tab_num.iat[i, j]
            d = tab_den.iat[i, j]
            v = valores.iat[i, j]
            if metrica == "obitos":
                linha.append(f"{fmt_int(n)} óbitos")
            elif pd.isna(v):
                linha.append(f"poucos casos para calcular % (n={fmt_int(d)})")
            else:
                linha.append(f"{fmt_pct(v)} — {fmt_int(n)} de {fmt_int(d)} óbitos")
        hover.append(linha)

    zmax = valores.max().max()
    fig = go.Figure(go.Heatmap(
        z=valores.values, x=colunas, y=linhas, text=texto.values, texttemplate="%{text}",
        customdata=hover, xgap=2, ygap=2,
        colorscale=ESCALA_AZUL,
        zmin=0, zmax=zmax if pd.notna(zmax) else 1,
        colorbar=dict(thickness=10, len=0.8, outlinewidth=0, ticksuffix=sufixo, tickfont=dict(color=CINZA)),
        hovertemplate="<b>%{y}</b> · %{x}<br>%{customdata}<extra></extra>",
    ))
    layout_base(fig, 400)
    fig.update_xaxes(side="top", linecolor="rgba(0,0,0,0)", tickfont=dict(color=CINZA_ESCURO))
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)", tickfont=dict(color=CINZA_ESCURO))

    tabela = []
    for i, raca in enumerate(linhas):
        tabela.append({"Raça/cor": raca, **dict(zip(colunas, hover[i]))})
    return fig, tabela


def fig_causas(df):
    if df.empty:
        return figura_vazia(altura=400)
    df = df.iloc[::-1].copy()  # maior no topo

    def encurtar(t, n=46):
        return t if len(t) <= n else t[: n - 1].rstrip() + "…"

    df["rotulo"] = df["cod_categoria"] + " " + df["categoria_descricao"].map(encurtar)
    fig = go.Figure()
    for tipo, cor in CORES_TIPO.items():
        parte = df[df["tipo_morte_materna"] == tipo]
        if parte.empty:
            continue
        fig.add_trace(go.Bar(
            y=parte["rotulo"], x=parte["obitos"], name=f"Causa {tipo.lower()}", orientation="h",
            marker=dict(color=cor, cornerradius=4), width=0.6,
            text=parte["obitos"].map(fmt_int), textposition="outside", cliponaxis=False,
            textfont=dict(color=CINZA_ESCURO, size=11),
            customdata=parte[["categoria_descricao"]],
            hovertemplate="<b>%{customdata[0]}</b><br>%{x:,.0f} óbitos<extra>" + tipo + "</extra>",
        ))
    # legenda do plotly brigava com os nomes compridos das causas, por isso ela é feita no html (legenda_html)
    layout_base(fig, 380, barmode="overlay", showlegend=False)
    fig.update_yaxes(categoryorder="array", categoryarray=df["rotulo"].tolist(), gridcolor="rgba(0,0,0,0)",
                     tickfont=dict(color=CINZA_ESCURO, size=11))
    fig.update_layout(margin=dict(r=44))  # espaço para o valor da maior barra
    fig.update_xaxes(visible=False, range=[0, df["obitos"].max() * 1.12])
    return fig


def fig_externas(df):
    if df.empty:
        return figura_vazia(altura=340)
    tabela = df.pivot_table(index="ano", columns="grupo", values="obitos", aggfunc="sum").fillna(0)
    fig = go.Figure()
    for grupo, cor in CORES_EXTERNAS.items():
        if grupo not in tabela:
            continue
        fig.add_trace(go.Bar(
            x=tabela.index, y=tabela[grupo], name=grupo,
            marker=dict(color=cor, line=dict(color=BRANCO, width=1)),
            hovertemplate=f"{grupo}: %{{y:,.0f}}<extra></extra>",
        ))
    layout_base(fig, 340, barmode="stack", bargap=0.35, hovermode="x unified")
    fig.update_layout(legend_traceorder="normal")
    fig.update_xaxes(dtick=1)
    return fig


# layout da página
app = Dash(
    __name__,
    title="Mortalidade Materna no Brasil · ODS 5 e 18",
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server  # usado pelo gunicorn


def carregar_opcoes():
    try:
        d, _ = db.executar(lambda s: s.lote(q.opcoes()))
        anos = d["anos"].iloc[0]
        return d["ufs"], d["faixas"]["faixa_etaria"].tolist(), int(anos["ini"]), int(anos["fim"]), None
    except Exception as e:  # banco fora do ar: a página abre mesmo assim e mostra o erro
        return pd.DataFrame(columns=["regiao", "uf"]), [], 2014, 2024, str(e)


def card(titulo, subtitulo, corpo, controles=None, classe=""):
    cabecalho = html.Div([
        html.Div([html.H3(titulo, className="card-titulo"), html.P(subtitulo, className="card-sub")]),
        # tem que ser "is not None": componente sem filhos (tipo o RadioItems) conta como False e o controle sumiria
        html.Div(controles, className="card-controles") if controles is not None else None,
    ], className="card-cabecalho")
    return html.Div([cabecalho, corpo], className=f"painel-card {classe}")


def legenda_html(itens):
    return html.Div([html.Span([html.Span(className="amostra", style={"background": cor}), nome],
                               className="legenda-item") for nome, cor in itens.items()],
                    className="legenda")


def kpi(id_, rotulo, ajuda):
    return html.Div([
        html.Div(rotulo, className="kpi-rotulo"),
        html.Div("–", id=f"kpi-{id_}", className="kpi-valor"),
        html.Div("", id=f"kpi-{id_}-sub", className="kpi-sub"),
        html.Div(ajuda, className="kpi-ajuda"),
    ], className="kpi")


def montar_layout():
    ufs, faixas, ini, fim, erro = carregar_opcoes()
    regioes = sorted(ufs["regiao"].unique())
    filtros = html.Div([
        html.Div([
            html.Label("Período", htmlFor="f-anos"),
            dcc.RangeSlider(id="f-anos", min=ini, max=fim, step=1, value=[ini, fim],
                            marks={a: {"label": str(a) if a % 2 == 0 or a == fim else ""} for a in range(ini, fim + 1)},
                            allowCross=False, tooltip={"placement": "bottom", "always_visible": False}),
        ], className="filtro filtro-anos"),
        html.Div([html.Label("Região", htmlFor="f-regiao"),
                  dcc.Dropdown(id="f-regiao", options=regioes, multi=True, placeholder="Todas")], className="filtro"),
        html.Div([html.Label("UF", htmlFor="f-uf"),
                  dcc.Dropdown(id="f-uf", options=sorted(ufs["uf"]), multi=True, placeholder="Todas")],
                 className="filtro"),
        html.Div([html.Label("Raça/cor", htmlFor="f-raca"),
                  dcc.Dropdown(id="f-raca", options=ORDEM_RACA, multi=True, placeholder="Todas")],
                 className="filtro"),
        html.Div([html.Label("Faixa etária", htmlFor="f-faixa"),
                  dcc.Dropdown(id="f-faixa", options=faixas, multi=True, placeholder="Todas")],
                 className="filtro"),
        html.Button("Limpar", id="f-limpar", className="btn-limpar", n_clicks=0),
    ], className="barra-filtros")

    return html.Div([
        dcc.Store(id="ufs-por-regiao", data=ufs.to_dict("records")),
        dcc.Interval(id="relogio", interval=60_000),
        html.Header([
            html.Div([
                html.Div(["ODS 5 · Igualdade de gênero", html.Span("·"), "ODS 18 · Igualdade étnico-racial"],
                         className="selo"),
                html.H1("Mortalidade materna no Brasil, 2014–2024"),
                html.P("Quem são as mulheres que morrem na gravidez, no parto e no puerpério — e o que a contagem "
                       "oficial deixa de fora. Dados do SIM/DATASUS tratados pelo Observatório Obstétrico "
                       "Brasileiro (OOBr), consultados ao vivo no PostgreSQL.", className="lead"),
            ], className="cabecalho-texto"),
        ], className="cabecalho"),
        dbc.Alert(f"Não foi possível conectar ao banco: {erro}", color="danger", className="m-0 mb-3",
                  is_open=bool(erro), id="alerta-banco"),
        filtros,
        html.Div([
            kpi("total", "Óbitos maternos oficiais", "Contagem oficial do Ministério da Saúde"),
            kpi("negras", "Mulheres negras", "Pretas + pardas, entre óbitos com raça/cor informada"),
            kpi("diretas", "Causas obstétricas diretas", "Hipertensão, hemorragia, infecção… em grande parte evitáveis"),
            kpi("cmm", "Sem investigação do CMM", "Óbitos sem investigação registrada pelo Comitê de Mortalidade Materna"),
            kpi("agressao", "Assassinadas",
                "Grávidas e puérperas mortas por agressão (CID X85–Y09) — fora da contagem oficial"),
        ], className="kpis"),
        html.Div([
            card("Óbitos maternos por ano e raça/cor",
                 "A pandemia quase dobrou as mortes em 2021; 2024 ainda é preliminar.",
                 dcc.Graph(id="g-serie", config={"displayModeBar": False}),
                 controles=dcc.RadioItems(id="serie-modo", value="n", inline=True, className="segmentado",
                                          options=[{"label": "Nº", "value": "n"},
                                                   {"label": "% do ano", "value": "pct"}]),
                 classe="span-7"),
            card("Principais causas", "As 10 causas básicas mais frequentes (CID-10)",
                 html.Div([
                     legenda_html({f"Causa {t.lower()}": c for t, c in CORES_TIPO.items()}),
                     dcc.Graph(id="g-causas", config={"displayModeBar": False}),
                 ]), classe="span-5"),
        ], className="grade"),
        html.Div([
            html.Span("Indicador em foco no mapa e na matriz:", className="foco-rotulo"),
            dcc.RadioItems(id="metrica", value="negras", inline=True, className="segmentado",
                           options=[{"label": v, "value": k} for k, v in METRICAS.items()]),
        ], className="barra-foco"),
        html.Div([
            card("Por unidade da federação", "Passe o mouse sobre o estado para ver os números",
                 dcc.Graph(id="g-mapa", config={"displayModeBar": False}), classe="span-5"),
            card("Matriz interseccional", "Raça/cor cruzada com outra dimensão. Células com menos de "
                 f"{MIN_CASOS} óbitos ficam em branco (porcentagem instável).",
                 html.Div([
                     html.P(id="matriz-legenda", className="matriz-legenda"),
                     dcc.Graph(id="g-matriz", config={"displayModeBar": False}),
                     html.Details([html.Summary("Ver como tabela"), html.Div(id="tabela-matriz")],
                                  className="detalhes-tabela"),
                 ]),
                 controles=dcc.Dropdown(id="dimensao", value="faixa_etaria", clearable=False, searchable=False,
                                        options=[{"label": v, "value": k} for k, v in DIMENSOES.items()],
                                        className="dropdown-pequeno"),
                 classe="span-7"),
        ], className="grade"),
        html.Div([
            card("Violência: mortes por causas externas de grávidas e puérperas",
                 "Óbitos “desconsiderados” — não entram na razão de mortalidade materna oficial.",
                 dcc.Graph(id="g-externas", config={"displayModeBar": False}), classe="span-7"),
            card("Leitura rápida", "Gerada a partir dos dados filtrados",
                 html.Div(id="insights", className="insights"), classe="span-5"),
        ], className="grade"),
        html.Footer([
            html.Div(id="status-banco", className="status"),
            html.Div([
                "Fonte: OOBr — óbitos de gestantes e puérperas (SIM/DATASUS), versão de fev/2025. "
                "2024 é preliminar. Sem dados de nascidos vivos (SINASC), o painel mostra contagens e "
                "proporções, não a razão de mortalidade materna.",
            ], className="nota"),
        ], className="rodape"),
    ], className="pagina")


app.layout = montar_layout  # função: cada visita lê as opções atualizadas do banco


# callbacks
@app.callback(
    Output("f-uf", "options"), Output("f-uf", "value", allow_duplicate=True),
    Input("f-regiao", "value"), State("f-uf", "value"), State("ufs-por-regiao", "data"),
    prevent_initial_call=True,
)
def ufs_da_regiao(regioes, ufs_marcadas, dados):
    tabela = pd.DataFrame(dados)
    if regioes:
        tabela = tabela[tabela["regiao"].isin(regioes)]
    opcoes = sorted(tabela["uf"])
    return opcoes, [u for u in (ufs_marcadas or []) if u in opcoes]


@app.callback(
    Output("f-anos", "value"), Output("f-regiao", "value"), Output("f-uf", "value", allow_duplicate=True),
    Output("f-raca", "value"), Output("f-faixa", "value"),
    Input("f-limpar", "n_clicks"), State("f-anos", "min"), State("f-anos", "max"),
    prevent_initial_call=True,
)
def limpar(_, ini, fim):
    return [ini, fim], [], [], [], []


def consultar_tudo(s, f, metrica, dimensao):
    d = s.lote(q.painel(f, metrica, dimensao))  # 8 consultas, 1 ida ao banco
    d["oficiais"], d["agressoes"] = d["oficiais"].iloc[0], d["agressoes"].iloc[0]  # KPIs: uma linha só
    return d


# frases da "leitura rápida", calculadas com os filtros atuais (nenhum número fixo)
def gerar_insights(d):
    o, a = d["oficiais"], d["agressoes"]
    itens = []
    if o["total"]:
        itens.append(f"{fmt_pct(pct(o['negras'], o['raca_informada']), 0)} das mortes maternas do recorte "
                     f"foram de mulheres negras (pretas + pardas).")

        por_ano = d["serie"].groupby("ano")["obitos"].sum()
        if por_ano.get(2019) and por_ano.get(2021):
            itens.append(f"Com a COVID-19, os óbitos passaram de {fmt_int(por_ano[2019])} em 2019 para "
                         f"{fmt_int(por_ano[2021])} em 2021 "
                         f"(+{fmt_pct(pct(por_ano[2021] - por_ano[2019], por_ano[2019]), 0)}).")

        r = d["raca"].set_index("raca_cor").fillna(0)
        r = r[(r.index != "Ignorado") & (r["total"] >= MIN_CASOS)]
        if len(r) >= 2:
            r = r.assign(p_diretas=r["diretas"] / r["total"] * 100, p_cmm=r["sem_cmm"] / r["total"] * 100,
                         p_adol=r["adolescentes"] / r["total"] * 100)
            alto, baixo = r["p_diretas"].idxmax(), r["p_diretas"].idxmin()
            itens.append(f"Causas obstétricas diretas (as mais evitáveis): {fmt_pct(r.at[alto, 'p_diretas'], 0)} "
                         f"das mortes entre mulheres {alto.lower()}s, contra {fmt_pct(r.at[baixo, 'p_diretas'], 0)} "
                         f"entre {baixo.lower()}s.")
            alto, baixo = r["p_cmm"].idxmax(), r["p_cmm"].idxmin()
            itens.append(f"Sem investigação do Comitê de Mortalidade Materna: {fmt_pct(r.at[alto, 'p_cmm'], 0)} "
                         f"entre {alto.lower()}s e {fmt_pct(r.at[baixo, 'p_cmm'], 0)} entre {baixo.lower()}s.")
            alto = r["p_adol"].idxmax()
            itens.append(f"Adolescentes (menos de 20 anos) são {fmt_pct(r.at[alto, 'p_adol'], 0)} das mortes "
                         f"entre mulheres {alto.lower()}s — a maior proporção entre os grupos.")
    if a["total"]:
        itens.append(f"{fmt_int(a['total'])} grávidas ou puérperas foram assassinadas e não entram na "
                     f"contagem oficial; {fmt_pct(pct(a['negras'], a['raca_informada']), 0)} delas eram negras.")
    if not itens:
        itens = ["Nenhum óbito para os filtros escolhidos."]
    return html.Ul([html.Li(t) for t in itens])


@app.callback(Output("matriz-legenda", "children"), Input("metrica", "value"))
def legenda_matriz(metrica):
    return LEGENDA_MATRIZ[metrica]


@app.callback(
    Output("kpi-total", "children"), Output("kpi-total-sub", "children"),
    Output("kpi-negras", "children"), Output("kpi-negras-sub", "children"),
    Output("kpi-diretas", "children"), Output("kpi-diretas-sub", "children"),
    Output("kpi-cmm", "children"), Output("kpi-cmm-sub", "children"),
    Output("kpi-agressao", "children"), Output("kpi-agressao-sub", "children"),
    Output("g-serie", "figure"), Output("g-causas", "figure"), Output("g-mapa", "figure"),
    Output("g-matriz", "figure"), Output("tabela-matriz", "children"), Output("g-externas", "figure"),
    Output("insights", "children"), Output("status-banco", "children"),
    Output("alerta-banco", "is_open"), Output("alerta-banco", "children"),
    Input("f-anos", "value"), Input("f-regiao", "value"), Input("f-uf", "value"),
    Input("f-raca", "value"), Input("f-faixa", "value"),
    Input("metrica", "value"), Input("dimensao", "value"), Input("serie-modo", "value"),
    Input("relogio", "n_intervals"),
)
def atualizar(anos, regioes, ufs, racas, faixas, metrica, dimensao, modo_serie, _):
    f = q.Filtros(anos[0], anos[1], regioes or [], ufs or [], racas or [], faixas or [])
    try:
        d, sessao = db.executar(consultar_tudo, f, metrica, dimensao)
    except Exception as e:
        # banco caiu: zera os KPIs, deixa os gráficos vazios e mostra o aviso vermelho
        vazio = figura_vazia("Banco indisponível")
        kpis_vazios = ["–", "", "–", "", "–", "", "–", "", "–", ""]
        status = html.Span([html.Span(className="ponto ponto-erro"), "Sem conexão com o banco"])
        aviso = f"Não foi possível consultar o banco: {e}"
        return (*kpis_vazios, vazio, vazio, vazio, vazio, None, vazio, "", status, True, aviso)

    o, a = d["oficiais"], d["agressoes"]
    n_anos = max(int(o["anos"]), 1)
    kpis = [
        fmt_int(o["total"]), f"média de {fmt_int(round(o['total'] / n_anos))} por ano · {anos[0]}–{anos[1]}",
        fmt_pct(pct(o["negras"], o["raca_informada"])), f"{fmt_int(o['negras'])} óbitos",
        fmt_pct(pct(o["diretas"], o["total"])), f"{fmt_int(o['diretas'])} óbitos",
        fmt_pct(pct(o["sem_cmm"], o["total"])), f"{fmt_int(o['sem_cmm'])} óbitos",
        fmt_int(a["total"]),
        f"{fmt_pct(pct(a['negras'], a['raca_informada']), 0)} eram negras" if a["total"] else "",
    ]

    fig_m, tabela = fig_matriz(d["matriz"], metrica, dimensao)
    tabela_html = dbc.Table.from_dataframe(pd.DataFrame(tabela), size="sm", striped=False, bordered=False,
                                           className="tabela") if tabela else None

    # rodapé: mostra que os dados vieram do banco agora
    agora = datetime.now(FUSO).strftime("%H:%M:%S")
    texto = f"Consultado no banco às {agora} · {origem_banco()} · {sessao.n_consultas} consultas, {sessao.ms:.0f} ms"
    status = html.Span([html.Span(className="ponto ponto-ok"), texto])

    return (*kpis,
            fig_serie(d["serie"], modo_serie), fig_causas(d["causas"]), fig_mapa(d["uf"], metrica),
            fig_m, tabela_html, fig_externas(d["externas"]),
            gerar_insights(d), status, False, no_update)


_origem = None


# pega a versão do PostgreSQL só uma vez, pra mostrar no rodapé (ex.: "PostgreSQL 18.7 · Aiven")
def origem_banco():
    global _origem
    if _origem is None:
        try:
            info = db.info_servidor()
            host = info["host"] or ""
            onde = "Aiven" if "aivencloud" in host else host
            _origem = f"PostgreSQL {info['versao']} · {onde}"
        except Exception:
            return "PostgreSQL"
    return _origem


if __name__ == "__main__":
    app.run(debug=os.environ.get("DASH_DEBUG") == "1", host="0.0.0.0" if os.environ.get("PORT") else "127.0.0.1",
            port=int(os.environ.get("PORT", 8050)))
