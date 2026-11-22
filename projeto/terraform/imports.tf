# o banco foi criado antes pelo console do Aiven; num ambiente novo, apagar este arquivo
import {
  to = aiven_pg.painel
  id = "${var.aiven_project}/${var.service_name}"
}

# o usuário painel_leitura também foi criado pelo console do Aiven (fase 3, para o dashboard)
import {
  to = aiven_pg_user.leitura
  id = "${var.aiven_project}/${var.service_name}/${var.usuario_leitura}"
}
