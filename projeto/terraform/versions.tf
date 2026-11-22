terraform {
  required_version = ">= 1.6"

  required_providers {
    aiven = {
      source  = "aiven/aiven"
      version = "~> 4.64"
    }
    render = {
      source  = "render-oss/render"
      version = "~> 1.9"
    }
  }
}

# token na variável de ambiente AIVEN_TOKEN
provider "aiven" {}

# chave e dono nas variáveis de ambiente RENDER_API_KEY e RENDER_OWNER_ID (usr-... ou tea-...)
provider "render" {}
