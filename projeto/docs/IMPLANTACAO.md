# Implantação do dashboard (fase 3)

Este guia continua o [INFRAESTRUTURA.md](INFRAESTRUTURA.md). Ele supõe que o banco na Aiven já está
provisionado e carregado: Terraform aplicado, `python src/load.py` executado e `sql/permissoes.sql`
aplicado. Todos os comandos rodam a partir da pasta `projeto/`.

## Rodar localmente (um comando)

Com o `.env` na raiz do repositório (veja `.env.example`):

```bash
pip install -r requirements.txt && python dashboard/app.py
```

Abra http://127.0.0.1:8050. Para recarregar o código a cada alteração, use `DASH_DEBUG=1`.

No `.env` local pode ficar a URL do `avnadmin`. Na nuvem, use sempre a URL do `painel_leitura`:

```bash
terraform -chdir=terraform output -raw database_url_leitura
```

## Publicar na internet (Render)

O dashboard roda como web service Python no Render. O plano gratuito hiberna depois de 15 minutos
sem acesso, então a primeira visita depois disso leva cerca de 50 segundos.

### Opção A: Terraform (infraestrutura versionada)

O recurso está em `terraform/dashboard.tf`. Ele usa o mesmo Terraform do banco e já passa ao Render
a `DATABASE_URL` do usuário `painel_leitura`. A senha não aparece em nenhum arquivo.

```bash
cd terraform
export AIVEN_TOKEN=...          # como na fase 2
export RENDER_API_KEY=rnd_...   # Render > Account Settings > API Keys
export RENDER_OWNER_ID=usr-...  # aparece na URL do painel do Render
# no terraform.tfvars: criar_dashboard = true
terraform init -upgrade         # baixa o provider do Render e atualiza o .terraform.lock.hcl
terraform apply
terraform output dashboard_url
```

Com `auto_deploy = true`, cada push na branch `main` publica de novo.

Mesmo com `criar_dashboard = false`, o Terraform carrega o provider do Render. Se o `plan` reclamar
da chave do Render, exporte as duas variáveis do Render ou rode com `criar_dashboard = true`.

### Opção B: Blueprint (sem Terraform)

O arquivo `render.yaml`, na raiz do repositório, descreve o mesmo serviço.

1. No Render, abra New > Blueprint e escolha este repositório.
2. Quando pedir `DATABASE_URL`, cole a saída de
   `terraform -chdir=terraform output -raw database_url_leitura`.

Use esse caminho se o provider do Render recusar `plan = "free"`. A documentação do provider não
lista o plano gratuito.

### Comando de start

As duas opções usam o mesmo comando:

```
gunicorn --chdir dashboard app:server --workers 2 --timeout 60 --bind 0.0.0.0:$PORT
```

Cada worker abre no máximo 5 conexões. Dois workers somam 10 conexões, abaixo do limite de 20 do
plano gratuito da Aiven.

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `could not translate host name ... aivencloud.com` | O serviço gratuito foi desligado por inatividade | Ligue o serviço no console da Aiven (Power on). O endereço volta em 1 a 3 minutos. |
| `password authentication failed` | A senha foi trocada | Gere o `.env` de novo com `terraform output`, ou atualize a variável no Render. |
| A primeira visita ao Render demora | O plano free hiberna | Abra o link alguns minutos antes da apresentação. |
| `too many connections` | O limite de 20 conexões foi atingido | Não suba mais que 2 workers do gunicorn. |
| `permission denied for table` | O `sql/permissoes.sql` não foi aplicado | Rode o `psql ... -f sql/permissoes.sql` (veja INFRAESTRUTURA.md). |
