# Gastos y fondos menores

Responsabilidad general: Organizar gastos operativos, caja chica, anticipos y rendiciones.

Estado: pendiente de implementación.

Propietario funcional: Finanzas → Administración; responsable nominal pendiente de asignación.
Dependencias: contexto autorizado de tenant y contratos del padre; reglas y criterios de aceptación se definirán con el Product Owner al priorizar la tarea.

## Submódulos

- [Gastos operativos](2.2.1.5.1-gastos-operativos/README.md)
- [Caja chica](2.2.1.5.2-caja-chica/README.md)
- [Anticipos y rendiciones](2.2.1.5.3-anticipos-rendiciones/README.md)

`resources.yml` raíz declara únicamente la Lambda técnica de esta carpeta, su rol y su Log Group; no contiene API Gateway ni recursos de datos.

## Diagnóstico técnico DEV

Función: `mastererp-dev-adm-gastos`. Estado funcional: pendiente de implementación; el handler mínimo no implementa operaciones de gastos. Recursos exclusivos declarados una sola vez en [resources.yml](resources.yml). Python 3.12, 128 MB, timeout 5 segundos; logs con retención de 14 días. Sin API Gateway, Function URL, acceso a datos ni secretos. Ver procedimiento de empaquetado, despliegue y verificación en Administración.
