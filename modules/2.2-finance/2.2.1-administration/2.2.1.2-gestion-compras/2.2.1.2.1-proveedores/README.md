# Proveedores

Responsabilidad general: Gestionar la relación administrativa de compras con los proveedores del maestro de Catálogo, sin duplicarlo.

Estado: pendiente de implementación.

Propietario funcional: Finanzas → Administración; responsable nominal pendiente de asignación.
Dependencias: contexto autorizado de tenant y contratos del padre; reglas y criterios de aceptación se definirán con el Product Owner al priorizar la tarea.

Maestro de referencia: [Proveedores de Catálogo](../../../../2.1-catalog/2.1.5-suppliers/README.md). Esta dependencia documental no acredita que el maestro esté implementado; consumir su contrato cuando exista, sin copiar sus datos.

`resources.yml` raíz declara únicamente la Lambda técnica de esta carpeta, su rol y su Log Group; incluye la integración, ruta GET pública y permiso restringido para consumir el API existente; no declara otra API ni recursos de datos.

## Diagnóstico técnico DEV

Función: `mastererp-dev-adm-proveedores`. Estado funcional: pendiente de implementación; el handler mínimo no implementa operaciones de proveedores. Recursos exclusivos declarados una sola vez en [resources.yml](resources.yml). Python 3.12, 128 MB, timeout 5 segundos; logs con retención de 14 días. Sin Function URL, acceso a datos ni secretos. La ruta técnica pública se describe a continuación. Ver procedimiento de empaquetado, despliegue y verificación en Administración.

## Ruta de diagnóstico pública

GET /v1/administration/proveedores/health en mastererp-dev-admin-api (qx8nmypdhi). Por decisión explícita del propietario, esta ruta técnica es pública (AuthorizationType NONE), sin datos ni operaciones de tenant. La autenticación queda pendiente antes de implementar capacidades de negocio. La API sigue en mastererp-dev-onboarding; esta carpeta declara su integración, ruta y permiso exclusivo. CORS se conserva en el propietario de la API. No se crea ni modifica ningún autorizador JWT. No desplegar las definiciones heredadas de APIs.
