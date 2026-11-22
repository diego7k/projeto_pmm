# Fase 3: web service do dashboard (Plotly Dash + gunicorn) no Render.
# Só é criado com criar_dashboard = true no terraform.tfvars.
# O app conecta com o usuário somente leitura painel_leitura (ver sql/permissoes.sql).
resource "render_web_service" "dashboard" {
  count = var.criar_dashboard ? 1 : 0

  name              = "painel-mortalidade-materna"
  plan              = var.render_plano
  region            = var.render_regiao
  root_directory    = "projeto"
  start_command     = "gunicorn --chdir dashboard app:server --workers 1 --threads 4 --timeout 60 --bind 0.0.0.0:$PORT"
  health_check_path = "/"

  runtime_source = {
    native_runtime = {
      auto_deploy   = true
      branch        = "main"
      build_command = "pip install -r requirements.txt"
      repo_url      = var.repo_url
      runtime       = "python"
    }
  }

  env_vars = {
    "DATABASE_URL"   = { value = "postgres://${aiven_pg_user.leitura.username}:${aiven_pg_user.leitura.password}@${aiven_pg.painel.service_host}:${aiven_pg.painel.service_port}/defaultdb?sslmode=require" }
    "PYTHON_VERSION" = { value = "3.11.9" }
  }
}

output "dashboard_url" {
  description = "Endereço público do dashboard"
  value       = var.criar_dashboard ? render_web_service.dashboard[0].url : null
}
