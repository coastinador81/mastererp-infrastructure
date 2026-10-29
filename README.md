# mastererp-infrastructure

Infraestructura de MasterERP, alineada al diagrama funcional. Cada caja numerada es una carpeta con `template.yaml`.

## Flujo

Clientes entran por `gateways/api-clientes`. Admins entran por `gateways/api-admin`. Agentes IA entran por `gateways/gateway-mcp` y no llegan directo a la base. Debajo está la plataforma base y, por tenant, los módulos de negocio. Al final están las integraciones externas.

## 1.0 Plataforma base

- `templates/1.0-plataforma-base/1.1-onboarding-y-tenant/template.yaml`
- `templates/1.0-plataforma-base/1.2-ia/template.yaml`
- `templates/1.0-plataforma-base/datos/base-de-datos/template.yaml` — PostgreSQL real
- `templates/1.0-plataforma-base/datos/almacenamiento/template.yaml` — bucket real
- `templates/1.0-plataforma-base/datos/colas/template.yaml` — cola real
- `templates/1.0-plataforma-base/datos/seguridad/template.yaml` — roles reales
- `templates/1.0-plataforma-base/datos/monitoreo/template.yaml`

La red, los certificados, el borde y el cluster Fargate siguen en `templates/foundation` y `templates/shared/service`. Son el ambiente AWS, no una caja del diagrama funcional.

## 2.0 Módulos de negocio

- `2.1-catalogo`: 2.1.1 productos, 2.1.2 categorias, 2.1.3 atributos, 2.1.4 marcas, 2.1.5 proveedores, 2.1.6 inventario.
- `2.2-finanzas`: 2.2.1 administracion, 2.2.2 contabilidad, 2.2.3 bi-analitica, 2.2.4 masterpay.
- `2.3-operaciones`: 2.3.1 pedidos, 2.3.2 preparacion, 2.3.3 rutas, 2.3.4 repartidores, 2.3.5 nodos.
- `2.4-canales-digitales`: 2.4.1 pagina-web, 2.4.2 ecommerce.
- `2.5-servicios`: 2.5.1 mantenimiento, 2.5.2 fabricacion, 2.5.3 proyectos, 2.5.4 rfid.
- `2.6-centro-de-agentes`: 2.6.1 ia-general, 2.6.2 agentes-internos, 2.6.3 agentes-personalizados, 2.6.4 constructor, 2.6.5 centro-de-documentacion, 2.6.6 flujos-y-tareas, 2.6.7 canales, 2.6.8 aprobaciones, 2.6.9 auditoria, 2.6.10 configuracion.
- `2.7-rrhh`: 2.7.1 empleados, 2.7.2 nomina, 2.7.3 ausencias.
- `2.8-productividad`: 2.8.1 opsphere, 2.8.2 uonify, 2.8.3 marketing, 2.8.4 google-workspace, 2.8.5 microsoft-365.
- `2.9-pos`: 2.9.1 ventas-en-tienda, 2.9.2 cajas.
- `2.10-transporte`: 2.10.1 repartidores, 2.10.2 chipro, 2.10.3 mrw.

Repartidores está en operaciones 2.3.4 y en transporte 2.10.1. Es la misma entidad. MasterPay, Chipro y MRW también aparecen en integraciones externas.

## Integraciones externas

`templates/integraciones/` cubre marketplaces, pagos, logística, CRM, Google Workspace, Microsoft 365 y otros.

Las cajas que todavía no tienen servicio propio marcan el módulo con un parámetro SSM en valor `pendiente`.
