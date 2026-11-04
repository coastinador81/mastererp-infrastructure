# Gestión de compras

Responsabilidad general: Organizar proveedores y documentos administrativos de compras.

Estado: borradores básicos implementados en DEV; validación HTTP/visual aprobada. Aprobación, emisión y efectos financieros pendientes.

Propietario funcional: Finanzas → Administración; responsable nominal pendiente de asignación.
Dependencias: contexto autorizado de tenant y contratos del padre; reglas y criterios de aceptación se definirán con el Product Owner al priorizar la tarea.

## Submódulos

- [Proveedores](2.2.1.2.1-proveedores/README.md)
- [Solicitudes de compra](2.2.1.2.2-solicitudes-compra/README.md)
- [Órdenes de compra](2.2.1.2.3-ordenes-compra/README.md)
- [Facturas de proveedores](2.2.1.2.4-facturas-proveedores/README.md)

El resources.yml raíz declara la Lambda Compras compartida, rol, logs, integración y opciones. Las tres capacidades hijas declaran sus rutas y permisos exclusivos en sus propios resources.yml raíz; la pantalla compartida no declara recursos AWS.


## Borradores conectados DEV

Solicitud → orden → factura de proveedor. Listado paginado, detalle, creación y edición con el maestro de proveedores existente. Una única Lambda Compras, Python 3.12, 256 MB, timeout 15 segundos y logs de 14 días. Las operaciones funcionales usan JWT, contexto validado y mastererp_app con comandos SQL controlados; no hay DML general. El diagnóstico GET /v1/administration/compras/health conserva su respuesta pública mínima.

API existente qx8nmypdhi y autorizador del stack mastererp-dev-onboarding. No se reimporta ni se cambia su CORS. El stack de Administración permanece anidado en Finanzas. Ver [contrato, despliegue y pruebas](../../../../docs/PURCHASE_DRAFTS_DEV.md) y la pantalla compartida [purchases](screens/purchases/README.md).
