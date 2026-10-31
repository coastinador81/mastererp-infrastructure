# mastererp-infrastructure

Infraestructura de MasterERP, alineada al diagrama funcional. Cada caja numerada es una carpeta con `template.yaml`.

## Flujo

Clientes entran por `gateways/api-clientes`. Admins entran por `gateways/api-admin`. Agentes IA entran por `gateways/gateway-mcp` y no llegan directo a la base. Debajo está la plataforma base y, por tenant, los módulos de negocio. Al final están las integraciones externas.

## 1.0 Plataforma base

- `templates/1.0-plataforma-base/1.1-onboarding-y-tenant/template.yaml`
- `templates/1.0-plataforma-base/1.2-ia/template.yaml`
- `templates/1.0-plataforma-base/1.2-ia/1.2.2-uonify-core/template.yaml` — conversación, hilos, voz, memoria contextual, selección de modelos, guardas, orquestación y ejecución controlada de herramientas. El Centro de Agentes lo utiliza, pero no es propietario de esta lógica.
- `templates/1.0-plataforma-base/datos/base-de-datos/template.yaml` — PostgreSQL real
- `templates/1.0-plataforma-base/datos/almacenamiento/template.yaml` — bucket real
- `templates/1.0-plataforma-base/datos/colas/template.yaml` — cola real
- `templates/1.0-plataforma-base/datos/seguridad/template.yaml` — roles reales
- `templates/1.0-plataforma-base/datos/monitoreo/template.yaml`

La red, los certificados y el cluster siguen en `templates/foundation`. El balanceador, en `templates/foundation/edge`, solo publica las cuatro APIs: `client-api`, `admin-api`, `agents-api` y `mcp`. Siguen en Fargate, en la misma red que PostgreSQL.

Las cuatro webs están en `templates/amplify/webs`: `portal-web`, `super-admin-web`, `agents-web` y `storefront-web`. Amplify las sirve por CDN. Los archivos con hash se cachean un año y el HTML se revalida. El navegador llama a las APIs directo, sin API Gateway ni Lambda en ese camino.

El despliegue automático está en `.github/workflows/deploy-dev.yml`. Usa un usuario IAM propio y corre en cada push a `dev`. Crea `mastererp-dev-webs` y `mastererp-dev-modules`. No toca `mastererp-dev-foundation`, `mastererp-dev-edge` ni `mastererp-dev-platform`. Los dominios de las webs siguen en el balanceador hasta un disparo manual del flujo.

## 2.0 Módulos de negocio

- `2.1-catalogo`: 2.1.1 productos, 2.1.2 categorias, 2.1.3 atributos, 2.1.4 marcas, 2.1.5 proveedores, 2.1.6 inventario.
- `2.2-finanzas`: 2.2.1 administracion, 2.2.2 contabilidad, 2.2.3 bi-analitica, 2.2.4 masterpay.
- `2.3-operaciones`: 2.3.1 pedidos, 2.3.2 preparacion, 2.3.3 rutas, 2.3.5 nodos. Operaciones solicita o asigna entregas; no es propietaria de repartidores.
- `2.4-digital-sales`: 2.4.1 website, 2.4.2 ecommerce, 2.4.3 product-content, 2.4.4 marketplaces. Digital Sales gobierna funcionalmente los canales; sus conectores técnicos permanecen en integraciones externas.
- `2.5-servicios`: 2.5.1 mantenimiento, 2.5.2 fabricacion, 2.5.3 proyectos, 2.5.4 rfid.
- `2.6-centro-de-agentes`: 2.6.1 ia-general, 2.6.2 agentes-internos, 2.6.3 agentes-personalizados, 2.6.4 constructor, 2.6.5 centro-de-documentacion, 2.6.6 flujos-y-tareas, 2.6.7 canales, 2.6.8 aprobaciones, 2.6.9 auditoria, 2.6.10 configuracion.
- `2.7-rrhh`: 2.7.1 empleados, 2.7.2 nomina, 2.7.3 ausencias.
- `2.8-productividad`: 2.8.1 opsphere, 2.8.3 marketing (Meta y HubSpot), 2.8.4 mastercrm, 2.8.5 google-workspace, 2.8.6 microsoft-365. MasterCRM es propietario de clientes, contactos, oportunidades y pipeline; Marketing consume esos datos.
- `2.9-pos`: 2.9.1 ventas-en-tienda, 2.9.2 cajas.
- `2.10-transporte`: 2.10.1 repartidores, 2.10.2 chipro, 2.10.3 mrw.

Transporte es propietario de repartidores, transportistas, Chipro, MRW y despacho. MasterPay, Chipro y MRW también aparecen en integraciones externas como conectores técnicos.

## Integraciones externas

`templates/integraciones/` cubre marketplaces, pagos, logística, CRM, Google Workspace, Microsoft 365 y otros.

Las cajas que todavía no tienen servicio propio marcan el módulo con un parámetro SSM en valor `pendiente`.
