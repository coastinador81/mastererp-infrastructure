Ambiente de desarrollo en Oregon (us-west-2), cuenta 277352717693.

`foundation.yaml`, `edge.yaml` y `platform.yaml` componen las plantillas de `templates/`. La base, el borde y los servicios públicos salen de `templates/foundation`, `templates/datos/postgres` y `templates/shared/service`.

Los stacks ya desplegados (`mastererp-dev-foundation`, `mastererp-dev-edge`, `mastererp-dev-platform`) se crearon con las plantillas de un solo archivo. Actualizarlos con esta composición crearía stacks anidados y reemplazaría la red, el balanceador y la base.

Las carpetas de acceso, plataforma base y módulos de negocio siguen el diagrama. Todavía no despliegan un servicio por caja: marcan el módulo con un parámetro SSM.

Los servicios de Fargate siguen en cero tareas y el balanceador responde el JSON fijo. Los esquemas de dominio están en `mastererp-database/schema/001_domains.sql`.
