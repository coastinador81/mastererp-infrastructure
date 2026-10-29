Ambiente de desarrollo en Oregon (us-west-2), cuenta 277352717693.

`foundation.yaml`, `edge.yaml` y `platform.yaml` componen las plantillas de `templates/`. La base, el almacenamiento, las colas y los roles salen de `templates/plataforma-base/datos`. El borde y la red salen de `templates/foundation`.

Los stacks ya desplegados (`mastererp-dev-foundation`, `mastererp-dev-edge`, `mastererp-dev-platform`) se crearon con las plantillas de un solo archivo. Actualizarlos con esta composición crearía stacks anidados y reemplazaría la red, el balanceador y la base.

Las carpetas siguen el diagrama funcional, de la 1.0 a la 2.10, más las integraciones externas. Todavía no despliegan un servicio por caja: marcan el módulo con un parámetro SSM.

Los servicios de Fargate siguen en cero tareas y el balanceador responde el JSON fijo. Los esquemas de dominio están en `mastererp-database/schema/001_domains.sql`.
