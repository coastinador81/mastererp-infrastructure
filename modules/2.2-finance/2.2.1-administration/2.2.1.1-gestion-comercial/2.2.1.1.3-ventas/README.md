# Ventas

Responsabilidad general: Organizar la gestión administrativa de las ventas.

Estado: pendiente de implementación.

Propietario funcional: Finanzas → Administración; responsable nominal pendiente de asignación.
Dependencias: contexto autorizado de tenant y contratos del padre; reglas y criterios de aceptación se definirán con el Product Owner al priorizar la tarea.

`resources.yml` raíz declara únicamente la Lambda técnica de esta carpeta, su rol y su Log Group; incluye la integración, ruta GET pública y permiso restringido para consumir el API existente; no declara otra API ni recursos de datos.

## Diagnóstico técnico DEV — histórico previo a 048

Función: `mastererp-dev-adm-ventas`. Estado funcional: pendiente de implementación; el handler mínimo no implementa operaciones de ventas. Recursos exclusivos declarados una sola vez en [resources.yml](resources.yml). Python 3.12, 128 MB, timeout 5 segundos; logs con retención de 14 días. Sin Function URL, acceso a datos ni secretos. La ruta técnica pública se describe a continuación. Ver procedimiento de empaquetado, despliegue y verificación en Administración.

## Ruta de diagnóstico pública

GET /v1/administration/ventas/health en mastererp-dev-admin-api (qx8nmypdhi). Por decisión explícita del propietario, esta ruta técnica es pública (AuthorizationType NONE), sin datos ni operaciones de tenant. La excepción pública se limita a health; las lecturas funcionales nuevas exigen JWT y autorización PostgreSQL. La API sigue en mastererp-dev-onboarding; esta carpeta declara su integración, ruta y permiso exclusivo. CORS se conserva en el propietario de la API. No se crea ni modifica ningún autorizador JWT. No desplegar las definiciones heredadas de APIs.


## Consulta de Ventas — desplegada en DEV

La Lambda existente mastererp-dev-adm-ventas recibe únicamente la lectura de listado/ficha y conserva /health. Recursos comunes en este resources.yml raíz: rol/log/Lambda/integración existentes y dos rutas GET JWT con permisos de invocación propios. Se reutilizan referencia de aplicación, subnets privadas, SG y autorizador ya usados por Proveedores; no se crean API, red ni secretos. Los YAML vacíos de screens/list y screens/detail son reservas documentales excluidas del ensamblado.

Actualizar por scripts/deploy_sales.py, usando el stack padre mastererp-dev-finance y su hijo mastererp-dev-administration. El script parte de la plantilla desplegada, superpone solo recursos Ventas y conserva parámetros/recursos ajenos. Revisar change sets raíz y anidado: sin eliminaciones ni reemplazos. No reimportar OpenAPI/SAM ni cambiar CORS/autenticación global. Aplicar 048 de Database antes de activar la API y publicar frontend después de comprobar HTTP real.

Estado: desplegado en DEV el 07/11/2026 desde Platform 1ec28f3 e Infrastructure 27c198a. Lambda Active/Successful, Python 3.12, 256 MB, 15 s. Revisión raíz/anidada sin reemplazos ni eliminaciones; IDs físicos, rutas anteriores y CORS conservados. Veinte comprobaciones HTTP reales de lectura aprobadas. No se modificaron otros recursos. Recuperación: usar PreviousArtifactKey y PreviousTemplateUrl del plan revisado conservado por el operador, preparar/revisar nuevo change set sobre el mismo padre y mantener 048 (aditiva) si se revierte frontend/código. Nunca restaurar snapshot sobre RDS activa para revertir una pantalla.
