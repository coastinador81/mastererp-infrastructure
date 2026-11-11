# Tesorería

Responsabilidad general: Organizar cobros, pagos y movimientos de fondos.

Estado: recursos candidatos para validación financiera de pagos; no desplegados por esta entrega.

Propietario funcional: Finanzas → Administración; responsable nominal pendiente de asignación.
Dependencias: contexto autorizado de tenant y contratos del padre; reglas y criterios de aceptación se definirán con el Product Owner al priorizar la tarea.

## Submódulos

- [Cobros](2.2.1.4.1-cobros/README.md)
- [Pagos](2.2.1.4.2-pagos/README.md)
- [Caja](2.2.1.4.3-caja/README.md)
- [Bancos](2.2.1.4.4-bancos/README.md)
- [Transferencias](2.2.1.4.5-transferencias/README.md)
- [Conciliación](2.2.1.4.6-conciliacion/README.md)

`resources.yml` raíz declara únicamente la Lambda técnica de esta carpeta, su rol y su Log Group; incluye la integración, ruta GET pública y permiso restringido para consumir el API existente; no declara otra API ni recursos de datos.

## Diagnóstico técnico DEV

Función: `mastererp-dev-adm-tesoreria`. Estado funcional: pendiente de implementación; el handler mínimo no implementa operaciones de tesoreria. Recursos exclusivos declarados una sola vez en [resources.yml](resources.yml). Python 3.12, 128 MB, timeout 5 segundos; logs con retención de 14 días. Sin Function URL, acceso a datos ni secretos. La ruta técnica pública se describe a continuación. Ver procedimiento de empaquetado, despliegue y verificación en Administración.

## Ruta de diagnóstico pública

GET /v1/administration/tesoreria/health en mastererp-dev-admin-api (qx8nmypdhi). Por decisión explícita del propietario, esta ruta técnica es pública (AuthorizationType NONE), sin datos ni operaciones de tenant. La autenticación queda pendiente antes de implementar capacidades de negocio. La API sigue en mastererp-dev-onboarding; esta carpeta declara su integración, ruta y permiso exclusivo. CORS se conserva en el propietario de la API. No se crea ni modifica ningún autorizador JWT. No desplegar las definiciones heredadas de APIs.
