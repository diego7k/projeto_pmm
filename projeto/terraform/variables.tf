variable "aiven_project" {
  description = "Projeto no Aiven"
  type        = string
  default     = "diego7k"
}

variable "service_name" {
  description = "Nome do serviço PostgreSQL"
  type        = string
  default     = "pg-3f45094b"
}

variable "cloud_name" {
  description = "Nuvem e região, ex.: do-nyc"
  type        = string
}

variable "plan" {
  description = "Plano do serviço (free-1-1gb é o gratuito)"
  type        = string
  default     = "free-1-1gb"
}

variable "usuario_leitura" {
  description = "Usuário somente leitura do painel"
  type        = string
  default     = "painel_leitura"
}

# ---------------- Fase 3: hospedagem do dashboard no Render ----------------
variable "criar_dashboard" {
  description = "Cria o web service do dashboard no Render (false = só o banco)"
  type        = bool
  default     = false
}

variable "render_plano" {
  description = "Plano do web service no Render (free hiberna após 15 min sem acesso)"
  type        = string
  default     = "free"
}

variable "render_regiao" {
  description = "Região do Render: oregon, ohio, virginia, frankfurt ou singapore"
  type        = string
  default     = "virginia"
}

variable "repo_url" {
  description = "Repositório com o código do dashboard"
  type        = string
  default     = "https://github.com/diego7k/projeto_pmm"
}
