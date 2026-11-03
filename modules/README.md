# Módulos de infraestructura

Jerarquía funcional compartida con frontend, backend y database. Cada carpeta numerada tiene README.md y resources.yml. Los YAML vacíos son reservas y se excluyen del despliegue. Los API Gateway compartidos se declaran en api-gateways.yml. Ver docs/FOLDER_STANDARD.md para nuevas carpetas y propiedad de recursos.

## Routing nativo vigente

El Admin API se administra por recursos Route/Integration individuales y un ensamblado explícito de configuración compartida. Las referencias SAM/Body anteriores son históricas; no se usan para actualizar el API. Procedimiento y límites: docs/ADMIN_API_DEPLOYMENT.md en la raíz del repositorio. No desplegar directamente los fragmentos ni reimportar OpenAPI sobre rutas modulares.
