# Gastos y fondos menores

Responsabilidad general: Organizar gastos operativos, caja chica, anticipos y rendiciones.

Estado: pendiente de implementación.

Propietario funcional: Finanzas → Administración; responsable nominal pendiente de asignación.
Dependencias: contexto autorizado de tenant y contratos del padre; reglas y criterios de aceptación se definirán con el Product Owner al priorizar la tarea.

## Submódulos

- [Gastos operativos](2.2.1.5.1-gastos-operativos/README.md)
- [Caja chica](2.2.1.5.2-caja-chica/README.md)
- [Anticipos y rendiciones](2.2.1.5.3-anticipos-rendiciones/README.md)

`resources.yml` raíz declara únicamente la Lambda técnica de esta carpeta, su rol y su Log Group; incluye la integración, ruta GET pública y permiso restringido para consumir el API existente; no declara otra API ni recursos de datos.

## Diagnóstico técnico DEV

Función: `mastererp-dev-adm-gastos`. Estado funcional: pendiente de implementación; el handler mínimo no implementa operaciones de gastos. Recursos exclusivos declarados una sola vez en [resources.yml](resources.yml). Python 3.12, 128 MB, timeout 5 segundos; logs con retención de 14 días. Sin Function URL, acceso a datos ni secretos. La ruta técnica pública se describe a continuación. Ver procedimiento de empaquetado, despliegue y verificación en Administración.

## Ruta de diagnóstico pública

GET /v1/administration/gastos/health en mastererp-dev-admin-api (qx8nmypdhi). Por decisión explícita del propietario, esta ruta técnica es pública (AuthorizationType NONE), sin datos ni operaciones de tenant. La autenticación queda pendiente antes de implementar capacidades de negocio. La API sigue en mastererp-dev-onboarding; esta carpeta declara su integración, ruta y permiso exclusivo. CORS se conserva en el propietario de la API. No se crea ni modifica ningún autorizador JWT. No desplegar las definiciones heredadas de APIs.
