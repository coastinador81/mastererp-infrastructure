# Gestión de compras

Responsabilidad general: Organizar proveedores y documentos administrativos de compras.

Estado: pendiente de implementación.

Propietario funcional: Finanzas → Administración; responsable nominal pendiente de asignación.
Dependencias: contexto autorizado de tenant y contratos del padre; reglas y criterios de aceptación se definirán con el Product Owner al priorizar la tarea.

## Submódulos

- [Proveedores](2.2.1.2.1-proveedores/README.md)
- [Solicitudes de compra](2.2.1.2.2-solicitudes-compra/README.md)
- [Órdenes de compra](2.2.1.2.3-ordenes-compra/README.md)
- [Facturas de proveedores](2.2.1.2.4-facturas-proveedores/README.md)

`resources.yml` raíz declara únicamente la Lambda técnica de esta carpeta, su rol y su Log Group; no contiene API Gateway ni recursos de datos.

## Diagnóstico técnico DEV

Función: `mastererp-dev-adm-compras`. Estado funcional: pendiente de implementación; el handler mínimo no implementa operaciones de compras. Recursos exclusivos declarados una sola vez en [resources.yml](resources.yml). Python 3.12, 128 MB, timeout 5 segundos; logs con retención de 14 días. Sin API Gateway, Function URL, acceso a datos ni secretos. Ver procedimiento de empaquetado, despliegue y verificación en Administración.
