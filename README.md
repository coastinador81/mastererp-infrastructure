# MasterERP Infrastructure

## Mapa físico y referencias

```text
modules/{api-gateways.yml,resources.yml,README.md,…módulos numerados}/
integrations/
docs/
scripts/
.github/workflows/
```

[Arquitectura](docs/ARCHITECTURE.md), [propiedad de recursos](docs/RESOURCE_OWNERSHIP.md) e [integraciones](docs/INTEGRATION_BOUNDARIES.md). Las rutas con llaves resumen carpetas existentes, no son nombres literales. Database usa workflows existentes; publicar cambios observados puede aplicar SQL automáticamente. En Platform las pruebas Python de onboarding requieren sus dependencias y, para integración, una base desechable autorizada. Infrastructure no tiene un despliegue consolidado listo: revisar transición de stacks antes de aplicar plantillas.

Definiciones de infraestructura compartida y Lambdas funcionales de MasterERP.

- `modules/api-gateways.yml`: definiciones compartidas de API Gateway.
- `modules/1.0-platform-base/1.1-tenant-onboarding/lambdas/*/resources.yml`: tres Lambdas de onboarding.
- RDS y migraciones pertenecen a `mastererp-database`; el código funcional pertenece a `mastererp-platform`.

Las plantillas reorganizadas están en transición y no tienen despliegue automático habilitado. Antes de aplicarlas, completar la equivalencia con los stacks actuales y la migración de propiedad descrita en `docs/RESOURCE_OWNERSHIP.md`.

Los límites funcionales están documentados en `docs/` y cada módulo declara su responsabilidad antes de que exista una implementación técnica.

## Guía de trabajo

Leer [PROJECT.md](PROJECT.md), [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md), [carpetas](docs/FOLDER_STANDARD.md), [desarrollo](docs/DEVELOPMENT_STANDARD.md) y [registro](docs/MODULE_REGISTRY.md). Requisito para validación local: Python disponible; ejecutar `python scripts/validate_structure.py` (en Windows puede usarse `py scripts/validate_structure.py`) y `git diff --check`. No es obligatorio instalar herramientas locales para consultar documentación; el workflow existente Validate structure realiza el control en GitHub.

Estado: estructura funcional creada; las implementaciones y despliegues se distinguen en PROJECT.md y README de cada módulo. No hay un build frontend operativo declarado en este repositorio.
