# mastererp-infrastructure

Infraestructura de MasterERP. Cada caja del diagrama de módulos de negocio es una carpeta con su `template.yaml`, con la misma forma que uonify-capital-infrastructure.

## Foundation

Base de AWS del ambiente. Estas plantillas ya describen recursos reales.

- `templates/foundation/network/template.yaml`
- `templates/foundation/certificates/template.yaml`
- `templates/foundation/internal-dns/template.yaml`
- `templates/foundation/edge/template.yaml`
- `templates/foundation/documents/template.yaml`
- `templates/foundation/queues/template.yaml`
- `templates/foundation/security/template.yaml`
- `templates/foundation/cluster/template.yaml`
- `templates/shared/service/template.yaml`
- `templates/datos/postgres/template.yaml`

## Acceso

- `templates/acceso/clientes/template.yaml`
- `templates/acceso/admins/template.yaml`
- `templates/acceso/agentes/template.yaml`
- `templates/acceso/gateway-apis/template.yaml`
- `templates/acceso/gateway-mcp/template.yaml`

## Plataforma base

- `templates/plataforma-base/onboarding-y-tenant/template.yaml`
- `templates/plataforma-base/ia/template.yaml`

## Módulos de negocio

- Catalogo: productos, categoria, atributos, marcas, proveedor, inventario.
- Finanzas: admin, contabilidad, bi, masterpay.
- Operaciones: pedidos, preparacion, rutas, nodos.
- Canales digitales: pagina-web, ecommerce.
- Servicios: mantenimiento, fabricacion, proyectos, rfid.
- RRHH: empleados, nomina, ausencias.
- Centro de agentes: general, agentes-internos, agentes-custom, constructor, centro-de-documentacion, flujos-y-tareas, canales, aprobaciones, auditoria, configuracion.
- Productividad: opsphere, uonify, y marketing con meta, hubspot y mastercrm.
- Google: gmail, meet, drive.
- Microsoft: outlook, teams, one-drive, sharepoint, planner, automate.
- POS: ventas-en-tienda, cajas.
- Transporte: repartidores, chipro, mrw.

Cada una vive en `templates/<grupo>/<modulo>/template.yaml`.

Las cajas del diagrama todavía no crean un servicio propio. La plantilla marca el módulo con un parámetro SSM en valor `pendiente`. La red, el balanceador, PostgreSQL y Fargate siguen en las plantillas de foundation.
