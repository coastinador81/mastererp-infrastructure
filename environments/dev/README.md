Ambiente de desarrollo en Oregon (us-west-2), cuenta 277352717693.

Las tres plantillas componen los módulos de `modules/`. `foundation.yaml` une red, certificados y la zona privada. `edge.yaml` une el balanceador. `platform.yaml` une base, documentos, cola, roles, cluster y un `service.yaml` por entrada pública.

Los stacks ya desplegados (`mastererp-dev-foundation`, `mastererp-dev-edge`, `mastererp-dev-platform`) se crearon con las plantillas anteriores, de un solo archivo. Actualizarlos con esta composición crearía stacks anidados nuevos y reemplazaría la red, el balanceador y la base. Esta separación queda en el repositorio hasta hacer esa migración a propósito.

Los servicios siguen en cero tareas y el balanceador responde el JSON fijo. Los esquemas de dominio están en `mastererp-database/schema/001_domains.sql`.
