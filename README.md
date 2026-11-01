# MasterERP Infrastructure

Definiciones de infraestructura compartida y Lambdas funcionales de MasterERP.

- `modules/api-gateways.yml`: definiciones compartidas de API Gateway.
- `modules/1.0-platform-base/1.1-tenant-onboarding/lambdas.yml`: tres Lambdas de onboarding.
- RDS y migraciones pertenecen a `mastererp-database`; el código funcional pertenece a `mastererp-platform`.

Las plantillas reorganizadas están en transición y no tienen despliegue automático habilitado. Antes de aplicarlas, completar la equivalencia con los stacks actuales y la migración de propiedad descrita en `docs/RESOURCE_OWNERSHIP.md`.

Los límites funcionales están documentados en `docs/` y cada módulo declara su responsabilidad antes de que exista una implementación técnica.
