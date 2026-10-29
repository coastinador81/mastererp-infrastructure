# mastererp-infrastructure

Infraestructura de MasterERP, alineada al diagrama funcional. Cada caja numerada es una carpeta con `template.yaml`.

## Flujo

Clientes entran por `gateways/api-clientes`. Admins entran por `gateways/api-admin`. Agentes IA entran por `gateways/gateway-mcp` y no llegan directo a la base. Debajo está la plataforma base y, por tenant, los módulos de negocio. Al final están las integraciones externas.

## 1.0 Plataforma base

- `templates/plataforma-base/onboarding-y-tenant/template.yaml` — 1.1
- `templates/plataforma-base/ia/template.yaml` — 1.2
- `templates/plataforma-base/datos/base-de-datos/template.yaml` — PostgreSQL real
- `templates/plataforma-base/datos/almacenamiento/template.yaml` — bucket real
- `templates/plataforma-base/datos/colas/template.yaml` — cola real
- `templates/plataforma-base/datos/seguridad/template.yaml` — roles reales
- `templates/plataforma-base/datos/monitoreo/template.yaml`

La red, los certificados, el borde y el cluster Fargate siguen en `templates/foundation` y `templates/shared/service`. Son el ambiente AWS, no una caja del diagrama funcional.

## 2.0 Módulos de negocio

- 2.1 Catálogo: productos, categorias, atributos, marcas, proveedores, inventario.
- 2.2 Finanzas: administracion, contabilidad, bi-analitica, masterpay.
- 2.3 Operaciones: pedidos, preparacion, rutas, repartidores, nodos.
- 2.4 Canales digitales: pagina-web, ecommerce.
- 2.5 Servicios: mantenimiento, fabricacion, proyectos, rfid.
- 2.6 Centro de agentes: ia-general, agentes-internos, agentes-personalizados, constructor, centro-de-documentacion, flujos-y-tareas, canales, aprobaciones, auditoria, configuracion.
- 2.7 RRHH: empleados, nomina, ausencias.
- 2.8 Productividad: opsphere, uonify, marketing (meta, hubspot, mastercrm), google-workspace (gmail, meet, drive), microsoft-365 (outlook, teams, onedrive, sharepoint, planner, power-automate).
- 2.9 POS: ventas-en-tienda, cajas.
- 2.10 Transporte: repartidores, chipro, mrw.

Repartidores está en operaciones 2.3.4 y en transporte 2.10.1. Es la misma entidad. MasterPay, Chipro y MRW también aparecen en integraciones externas.

## Integraciones externas

`templates/integraciones/` cubre marketplaces, pagos, logística, CRM, Google Workspace, Microsoft 365 y otros.

Las cajas que todavía no tienen servicio propio marcan el módulo con un parámetro SSM en valor `pendiente`.
