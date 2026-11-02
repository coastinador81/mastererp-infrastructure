# Conciliación

Responsabilidad general: Organizar la conciliación de movimientos y saldos de tesorería.

Estado: pendiente de implementación.

Propietario funcional: Finanzas → Administración; responsable nominal pendiente de asignación.
Dependencias: contexto autorizado de tenant y contratos del padre; reglas y criterios de aceptación se definirán con el Product Owner al priorizar la tarea.

`resources.yml` raíz declara únicamente la Lambda técnica de esta carpeta, su rol y su Log Group; no contiene API Gateway ni recursos de datos.

## Diagnóstico técnico DEV

Función: `mastererp-dev-adm-conciliacion`. Estado funcional: pendiente de implementación; el handler mínimo no implementa operaciones de conciliacion. Recursos exclusivos declarados una sola vez en [resources.yml](resources.yml). Python 3.12, 128 MB, timeout 5 segundos; logs con retención de 14 días. Sin API Gateway, Function URL, acceso a datos ni secretos. Ver procedimiento de empaquetado, despliegue y verificación en Administración.
