Ambiente de desarrollo en Oregon (us-west-2), cuenta 277352717693.

`foundation.yaml`, `edge.yaml` y `platform.yaml` componen la red, el balanceador de las APIs y los cuatro servicios Fargate. `webs.yaml` compone las cuatro webs en Amplify. La base, el almacenamiento, las colas y los roles salen de `templates/1.0-plataforma-base/datos`.

Los stacks ya desplegados (`mastererp-dev-foundation`, `mastererp-dev-edge`, `mastererp-dev-platform`) siguen con la red, el balanceador, PostgreSQL y los servicios Fargate. El flujo de GitHub Actions no los actualiza: un cambio de plantilla ahí reemplazaría la red y la base.

El flujo `.github/workflows/deploy-dev.yml` publica dos stacks nuevos en cada push a `dev`: `mastererp-dev-webs` (Amplify, sin dominios) y `mastererp-dev-modules` (un parámetro SSM por módulo). Los dominios de Amplify se asocian solo con el disparo manual y la opción de publicarlos, cuando cada app ya tenga un artefacto.

Las carpetas siguen el diagrama funcional, de la 1.0 a la 2.10, más las integraciones externas. Todavía no despliegan un servicio por caja: marcan el módulo con un parámetro SSM.

En Fargate quedan `client-api`, `admin-api`, `agents-api` y `mcp`, todavía en cero tareas. El balanceador responde el JSON fijo de esas cuatro APIs. Las webs del esqueleto nuevo son Amplify. Los esquemas de dominio están en `mastererp-database/schema/001_domains.sql`.
