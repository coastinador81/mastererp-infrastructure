# Tesorería

Responsabilidad general: Organizar cobros, pagos y movimientos de fondos.

Estado: pendiente de implementación.

Propietario funcional: Finanzas → Administración; responsable nominal pendiente de asignación.
Dependencias: contexto autorizado de tenant y contratos del padre; reglas y criterios de aceptación se definirán con el Product Owner al priorizar la tarea.

## Submódulos

- [Cobros](2.2.1.4.1-cobros/README.md)
- [Pagos](2.2.1.4.2-pagos/README.md)
- [Caja](2.2.1.4.3-caja/README.md)
- [Bancos](2.2.1.4.4-bancos/README.md)
- [Transferencias](2.2.1.4.5-transferencias/README.md)
- [Conciliación](2.2.1.4.6-conciliacion/README.md)

`resources.yml` raíz declara únicamente la Lambda técnica de esta carpeta, su rol y su Log Group; no contiene API Gateway ni recursos de datos.

## Diagnóstico técnico DEV

Función: `mastererp-dev-adm-tesoreria`. Estado funcional: pendiente de implementación; el handler mínimo no implementa operaciones de tesoreria. Recursos exclusivos declarados una sola vez en [resources.yml](resources.yml). Python 3.12, 128 MB, timeout 5 segundos; logs con retención de 14 días. Sin API Gateway, Function URL, acceso a datos ni secretos. Ver procedimiento de empaquetado, despliegue y verificación en Administración.
