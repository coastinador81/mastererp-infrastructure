# MasterERP Infrastructure

Puerta de implementación: [propiedad y autorización](docs/IMPLEMENTATION_PATTERN.md).

## Arquitectura frontend

MasterERP conserva datos, reglas, procesos y autorización. `app-dev.uonify.com` es la entrada general DEV: la experiencia objetivo es un dashboard con chat y menú de módulos habilitados para el tenant y autorizados para el usuario. Sus pantallas se presentan dentro de Uonify, con navegación, identidad y contexto comunes; conversar no es obligatorio. Finanzas agrupa Administración, Contabilidad, BI y capacidades asociadas y conserva build/pipeline/despliegue propios. Su hosting `finanzas-dev.uonify.com` existe como acceso independiente de desarrollo y pruebas, no como navegación objetivo del usuario final; no se exige un subdominio financiero en producción ni una entrada `/finanzas`. El primer recorrido de Clientes/Proveedores ya está integrado y probado en DEV; las demás capacidades siguen pendientes. Cognito autentica; MasterERP autoriza cada operación por API. Ver [contrato oficial y estado desplegado](docs/FRONTEND_ARCHITECTURE.md).

Entrada rápida: [START_HERE.md](START_HERE.md).

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

<!-- ux-ui-standard:start -->
## Estándar UX/UI de los módulos

La referencia administrativa común es Finanzas/Proveedores: Inter regular, menú blanco, fondo gris azulado, acentos azules, tablas suaves e iconos de línea. Leer el [estándar UX/UI y la imagen de referencia](docs/UX_UI_STANDARD.md) antes de desarrollar una interfaz o su contrato. La implementación visual pertenece a Platform; esta guía no acredita que todos los módulos estén adaptados ni cambia las responsabilidades de cada repositorio.
<!-- ux-ui-standard:end -->

## Diseño de Uonify: el manual de identidad corporativa es canon

Todo lo visual de Uonify —módulo `0-uonify` y https://dev.uonify.com: interfaz, UX/UI, marca, logotipos, color, tipografía, iconografía, componentes, web y piezas gráficas— se rige por el [manual de identidad corporativa de Uonify](https://github.com/eticayservicios/mastererp-platform/blob/dev/frontend/modules/0-uonify/identidad-corporativa/Uonify_Identidad_Corporativa.pdf). Es el canon por decisión del Product Owner (08-11-2026), una excepción del propietario documentada con su alcance:

- Quien vaya a tocar cualquier diseño o UX/UI de Uonify lee antes el manual.
- No se inventan diseños, estilos ni patrones de UX/UI nuevos. Todo cambio visual respeta el manual, y lo que el manual no cubra no se improvisa: lo decide el Product Owner.
- Un cambio visual de Uonify que no cumpla el manual no se fusiona.
- En Uonify prevalece este manual; [docs/UX_UI_STANDARD.md](docs/UX_UI_STANDARD.md) sigue rigiendo las interfaces administrativas de MasterERP.

## Organización de aplicaciones vigente

La numeración local se ha actualizado a la [distribución de aplicaciones y mapa de transición](docs/MODULE_RENUMBERING.md). No implica despliegue, migración de stacks ni cambio de contratos SQL/API.
