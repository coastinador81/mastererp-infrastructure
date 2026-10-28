Ambiente de desarrollo en Oregon (us-west-2), cuenta 277352717693.

`foundation.yaml` crea la red, los certificados y la zona privada del MCP interno. El stack desplegado es `mastererp-dev-foundation`.

`edge.yaml` crea el balanceador HTTPS y los alias de los dominios de DEV en `uonify.com`. Cada host responde con el nombre del servicio hasta que exista la aplicación. El stack es `mastererp-dev-edge`.

`platform.yaml` crea la base PostgreSQL `mastererp`, el bucket de documentos, la cola de flujos de agentes, el cluster Fargate y un repositorio de imágenes por entrada pública. Los servicios quedan en cero tareas: todavía no hay imagen. Los target groups ya existen, pero el balanceador sigue respondiendo el JSON fijo. El stack es `mastererp-dev-platform`. Los esquemas de dominio están en `mastererp-database/schema/001_domains.sql`.
