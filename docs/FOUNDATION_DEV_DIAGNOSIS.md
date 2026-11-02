# Diagnóstico de base compartida DEV — 2026-11-02

Estado: NO CERRADA. [Guía y promoción](FOUNDATION_INTEGRATION.md), [evidencia HTTP/código/configuración](foundation-dev-diagnosis.json). Cuenta 277352717693; solo us-west-1. Ramas dev actualizadas con fetch y HEAD coincidente con origin/dev, sin checkout o pull que sobrescriba trabajo local. Los ZIP antiguos no se usaron.

| Área | Implementado | Desplegado | Probado realmente ahora | Pendiente |
| --- | --- | --- | --- | --- |
| Cognito e identidad estable | Implementación local issuer/sub y permisos SQL 006; parte sin publicar | Sí para Uonify; migrador incluye 006 | Login real y spaces 200; status 200; sin token 401; tenant ajeno 403; tres tablas de identidad y flags app sin privilegios | Publicar baseline por su propietario; completar adopción en onboarding |
| Onboarding funcional | Python existente; conserva búsqueda por correo y bypass platform.admin | Tres funciones reales; seis rutas heredadas a funciones eliminadas | Sesión GET devuelve 500 con y sin access token; catálogo heredado 500 | Corregir autenticación/grupos, empaquetado/configuración y cobertura HTTP |
| Configuración de onboarding | Pool/cliente y secreto de BD vacíos; sin VPC | Esa es la configuración desplegada, no solo un README | Consultas Lambda de metadatos; no se leyó contraseña | Configurar app credentials/red/identidad con stack propietario; causa detallada de cada 500 por confirmar |
| Tenant y RLS | SQL existente + overlays 005/006 | Identidad y rol mastererp_app verificados por acción de lectura del migrador | Cuatro archivos SQL en PG 17.9 desechable, SET ROLE y reaplicación | Cobertura funcional API y auditoría de denegaciones |
| Empresa/sucursal | Tablas y RLS owner existentes; FK individual no asegura tenant compuesto | Modelo anterior; candidato 007 no aplicado | En desechable: FK/contención, lectura aislada, asociación ajena denegada | Promover 007 y contrato/ACL de empresa por definir |
| Módulo + permiso | Permiso con override en 006; guard combinado nuevo en candidato | Guard combinado todavía no conectado a Uonify/onboarding | En SQL local: módulo suspendido, expiración/estados de contexto y override | Probar denegación HTTP, empaquetar/conectar guard |
| Idempotencia | Tenant existente sin huella; candidato añade tenant/company con huella | Candidato no aplicado | 8 conexiones simultáneas por tenant y por empresa; un resultado/efecto; conflicto de contenido | API concurrente y transición de claves antiguas |
| Auditoría | Evento SQL de efecto + utilidad candidata de campos fijos | La utilidad nueva no está conectada | Eventos de escritura local con correlación; pruebas unitarias de whitelist | Auditoría HTTP de resultados/denegación/replay y cobertura de operaciones |
| Finanzas | Solo diagnósticos | Padre/hijo ya desplegados; no se modificaron | No se usaron health como cierre funcional | Operaciones de negocio fuera de alcance |

## Diferencias verificadas

El migrador publicado en Git solo declara schemas 001–005 y dos tests, mientras el paquete desplegado declara 006. El test publicado espera 14 tablas; el trabajo local existente espera 17 y contiene tests de identidad. No hay una equivalencia commit → paquete → modelo reproducible que permita aplicar 007 sin publicar ese trabajo previo. El handler oficial reaplica el modelo por manifiesto; esta inspección no identificó un ledger de migraciones por archivo/hash que sustituya esa trazabilidad.

El paquete real de onboarding contiene tenant_security/auth.py con OR email, y su handler usa la ruta histórica lambdas/onboarding-session-manager/handler.lambda_handler. El archivo local de auth no es solo histórico: está dentro de un paquete usado por integraciones actuales. Uonify usa el adaptador distinto identity_access.py, con issuer/sub y token_use access; no se debe degradar a la ruta antigua.

La configuración de las tres funciones de onboarding tiene COGNITO_USER_POOL_ID y COGNITO_APP_CLIENT_ID vacíos, DATABASE_SECRET_ARN vacío y no tiene subnets VPC. ALLOW_TENANT_SELF_REGISTRATION sigue false. No se afirmó que usen credenciales maestras: no hay secreto configurado. No se amplió IAM, red ni permisos para conseguir un 200. El provisioner no tiene permiso de invocación API registrado, acorde con su uso interno previsto; no se inventó una ruta para probarlo.

## Qué se corrigió y qué no

Se preparó candidato nuevo sin sobrescribir archivos locales ajenos: 007, pruebas de fronteras y concurrencia, y helper Backend. Las pruebas de autorización SQL existentes se ajustaron únicamente para añadir contexto tenant a sus fixtures de idempotencia conforme al nuevo campo. No se modificó el manifiesto ni el workflow ajenos, por lo que 007 no se declara integrado/promovido. No se aplicaron migraciones en DEV ni se desplegó código runtime en esta tarea.

Se reparó el arranque del Docker existente apartando de forma reversible su carpeta de sockets bloqueada; sin reset, instalación, borrado de imágenes o volúmenes. Las pruebas usan contenedor nuevo sin red, puertos o volúmenes y borran únicamente ese contenedor al terminar. Ninguna escritura de fixtures se hizo en RDS. La única invocación del migrador fue verify_dev_identity, de consultas SELECT de metadatos, no apply_model.

## Bloqueos concretos para continuar

- El propietario debe publicar la base 006 y su empaquetado/tests actualmente locales para que el workflow no actualice el migrador con la versión Git anterior. La instrucción de no publicar trabajo ajeno impide hacerlo implícitamente en esta tarea.
- Después, integrar 007 y el guard en las rutas funcionales, corregir onboarding y ejecutar sus pruebas HTTP con mastererp_app. No se considera cerrado por las pruebas SQL de un contenedor.
- La decisión funcional de registro quedó resuelta: cualquier usuario interno activo autenticado puede registrar su propio tenant; email/groups/platform.admin no autorizan pertenencia. ACL por empresa adicional permanece por definir; conservar el contrato owner-only actual mientras tanto.
- El origen exacto de cada 500 requiere continuar el diagnóstico de logs/integraciones y empaquetado; no se atribuye a una causa única sin evidencia. Las seis rutas obsoletas no se eliminan y las cinco funciones ausentes no se recrean.

No se probó en DEV override false por API, módulo suspendido por API, registro HTTP idempotente/concurrente, empresas/sucursales por HTTP ni sesión de navegador completa en esta tarea. Sí se probó login real por Code+PKCE y regresión HTTP de Uonify sin persistir tokens. No declarar cerrados los casos pendientes.
