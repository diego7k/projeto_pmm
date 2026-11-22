# Painel de Mortalidade Materna: código

O README completo (link do dashboard, indicadores e análise) está na raiz do repositório:
[../README.md](../README.md).

Esta pasta tem o código e os dados:

- `src/etl.py`: trata os CSVs do OOBr (2014 a 2024) e grava em `data/processed/`.
- `src/load.py`: cria as tabelas no PostgreSQL da Aiven (`sql/schema.sql`) e carrega os CSVs com `COPY`.
- `sql/permissoes.sql`: deixa o usuário `painel_leitura` só com leitura.
- `dashboard/`: o dashboard em Plotly Dash.
- `terraform/`: banco na Aiven e dashboard no Render.
- `docs/`: decisões de tratamento, infraestrutura, implantação, segurança e o log do ETL.

O banco tem duas tabelas no schema `painel`: `obitos_maternos_oficiais` (18.534 óbitos) e
`obitos_desconsiderados` (10.323 óbitos), com as mesmas colunas dos CSVs tratados.

Para rodar, de dentro desta pasta:

```bash
pip install -r requirements.txt
python src/etl.py        # tratamento
python src/load.py       # carga no banco (precisa do DATABASE_URL no .env)
python dashboard/app.py  # dashboard em http://127.0.0.1:8050
```
