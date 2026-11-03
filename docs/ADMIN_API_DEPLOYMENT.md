# Admin API: un único mecanismo por recursos nativos

DEV us-west-1, cuenta 277352717693, API mastererp-dev-admin-api / qx8nmypdhi. Esta transición conserva el stack físico mastererp-dev-onboarding y el hijo mastererp-dev-administration bajo Finanzas; no crea otro API ni reorganiza globalmente stacks. La ubicación física histórica no se confunde con propiedad funcional.

## Regla vigente

Rutas e integraciones se administran exclusivamente mediante AWS::ApiGatewayV2::Route e Integration, en el resources.yml raíz de su módulo propietario. Permisos de invocación permanecen en ese módulo. API, stage, CORS y autorizador tienen una única declaración compartida seleccionada de modules/api-gateways.yml. Se prohíbe combinar esos recursos con Body, BodyS3Location, quick-create Target/RouteKey o Events HttpApi de SAM en el mismo API. OpenAPI puede utilizarse como documentación, nunca como escritor global de un API con recursos modulares. No usar import-api/reimport-api para actualizar este API.

La norma se basa en la [restricción oficial de AWS sobre mezclar OpenAPI y recursos CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-apigatewayv2-api.html). La [importación CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/resource-import-existing-stack.html) adopta identificadores existentes: no es una reimportación de la definición del API.

## Fuentes, propietario y composición

| Recursos | Fuente canónica | Propietario físico vigente |
| --- | --- | --- |
| AdminHttpApi, default stage y JWT authorizer | modules/api-gateways.yml: conjunto seleccionado de tres recursos | mastererp-dev-onboarding, excepción física conservada |
| Lambdas/roles/permisos y 12 rutas + 12 integraciones de Onboarding | modules/1.0-platform-base/1.1-tenant-onboarding/resources.yml | mastererp-dev-onboarding |
| 16 rutas y ocho integraciones de Administración | resources.yml de cada capacidad numerada | mastererp-dev-administration, hijo de Finanzas |

admin_api_model.assemble combina explícitamente el componente compartido y el módulo de Onboarding; detecta duplicados y rechaza escritores masivos/implícitos. Los fragmentos no son plantillas autónomas. La API permanece en su stack para conservar sus referencias, endpoint e identificadores; una futura transferencia a un stack de APIs requiere otra transición autorizada. Las definiciones antiguas no adoptadas de Client/Agent quedan como información histórica en Metadata, fuera del conjunto desplegable; sus recursos AWS no se modifican en este lote.

La API fue creada con OpenAPI sin ProtocolType en el modelo original de CloudFormation. Ese atributo es create-only. Para no provocar su reemplazo, la fuente adoptada no lo añade: los scripts son exclusivamente UPDATE sobre el ID conocido y comprueban que el servicio sigue siendo HTTP. Esta plantilla no se utiliza para CREATE ni para clonar QA/PROD; una creación nueva deberá declarar ProtocolType.

## Transición por lotes y recuperación

1. Inventario paginado completo de 28 rutas/20 integraciones y prueba HTTP funcional de línea base. Guardar plantillas originales/procesadas, recursos y huellas, fuera de secretos.
2. IMPORT de las doce rutas y doce integraciones implícitas, con DeletionPolicy/UpdateReplacePolicy Retain e identificadores ApiId + RouteId/IntegrationId. La plantilla SAM original se mantiene sin cambios durante esta fase: importar no debe predecir Modify/Create/Delete. El primer intento basado en la plantilla procesada fue rechazado por CloudFormation antes de ejecutar; se conservó el original para obtener 24 operaciones Import y ninguna modificación.
3. Retirar SAM/Body mediante el ensamblado nativo. El change set admite únicamente Modify AdminHttpApi con Replacement=False. Se desactiva rollback automático para evitar volver al Body destructivo si falla la transición. Un fallo se diagnostica y corrige hacia delante; no reimportar Body como recuperación.
4. Repetir una actualización real de UpdateApi modificando solamente Description (metadatos, sin efecto funcional), comparar todos los IDs/configuración y después comprobar el despliegue idéntico sin cambios.
5. Repetir Clientes/Proveedores, health y autenticación con fixtures identificadas y limpieza acotada. Sin migraciones SQL ni cambios de código Lambda.

El rollback anterior a la retirada de Body no debe ejecutarse ciegamente. Las plantillas y versiones S3 anteriores se conservan como evidencia; no volver a desplegar una definición OpenAPI antigua ni eliminar stacks. Retirar una adopción requiere Retain y un plan separado; no borrar rutas para recrearlas.

## Despliegues normales

```powershell
py scripts/deploy_admin_api.py --phase prepare --output <plan-local>
# Revisar plan.json: solo recursos de routing autorizados y sin reemplazos.
py scripts/deploy_admin_api.py --phase execute --output <mismo-plan>
py scripts/deploy_admin_api.py --phase verify --output <mismo-plan>
```

Un despliegue idéntico termina NO_CHANGES; no hay nada que ejecutar. verify es estricto para la prueba sin cambios funcionales. --allow-routing-additions habilita únicamente nuevas rutas/integraciones deliberadas, sin colisiones con claves de otros módulos; no permite crear otro API, borrar recursos o actualizar Lambdas. Una modificación funcional de CORS/autenticación necesita revisar también sus resultados esperados, no interpretar el comparador de la prueba de estabilidad como autorización funcional.

Código de Onboarding: repair_onboarding.py conserva su interfaz para las dos funciones permitidas, pero consume el mismo ensamblado nativo y verifica la huella completa y paginada. No puede volver a introducir Body. Administración sigue mediante deploy_parties.py prepare-finance/execute-finance; sus fases históricas prepare-api/execute-api quedan retiradas y redirigen a este procedimiento. No actualizar directamente el hijo.

El procedimiento excepcional de adopción está en stabilize_admin_api.py, con preparación/ejecución separadas; no repetir IMPORT sobre recursos ya adoptados. El despliegue normal no necesita ese script. No se añaden protecciones obligatorias de rama.

## Validación y límites

Comparar IDs y destinos de las 28 rutas, las 20 integraciones, el autorizador, default stage, endpoint, CORS, scopes y atributos relevantes; metadatos de petición, fechas y DeploymentId automático no son identidades de rutas. Probar HTTP, no solo UPDATE_COMPLETE. Las cinco funciones históricamente ausentes y sus rutas obsoletas se conservan como problema previo; no se recrean ni se eliminan en esta transición.

Evidencia de este lote: api-native-verification.json y admin-api-before-http.json / admin-api-after-http.json; prueba unitaria test_admin_api_model.py y validador estructural existente. Las pruebas sintéticas usan el migrador oficial únicamente para preparar/limpiar sus propias fixtures; no aplican ni reaplican migraciones.

## Resultado real del lote

Completado en DEV: 24 recursos existentes adoptados por IMPORT, sin crear ni eliminar rutas/integraciones. El propietario contiene 57 declaraciones; conserva los 33 IDs físicos originales. Administración mantiene sus 64 recursos y sus IDs. Se verificaron 28 RouteId, 20 IntegrationId, el API/endpoint, AuthorizerId, default stage, CORS/scopes/destinos y las configuraciones de once Lambdas vivas. Cinco funciones históricamente ausentes siguen ausentes. No se cambiaron códigos Lambda ni se ejecutaron migraciones SQL.

Se ejecutaron dos actualizaciones nativas del mismo API: retirada de Body y repetición con un cambio exclusivo de Description. Ambas conservaron la huella del grafo de routing. El despliegue idéntico por deploy_admin_api.py produjo NO_CHANGES y verify aprobó. AWS representa ese caso esperado mediante un change set fallido por ausencia de cambios: no es un fallo del stack, que queda UPDATE_COMPLETE, y no se intenta ejecutar ese change set.

AutoDeploy creó nuevas versiones DeploymentId y cambió sus mensajes/fechas; no sustituyó recursos Route/Integration/Authorizer/API. La primera comparación detectó ese mensaje volátil: se corrigió el comparador para excluir únicamente esos metadatos y se revalidaron todas las instantáneas, manteniendo íntegra la comparación de identidades, auth, destinos y configuración funcional. Las instantáneas originales no se sobrescribieron.

HTTP real: 33 comprobaciones de Clientes/Proveedores aprobadas antes y otras 33 después, con escrituras persistidas, replay/conflicto, concurrencia, scopes/permisos y aislamiento. Ambas tandas limpiaron solo sus fixtures. Además, 18 comprobaciones posteriores aprobaron ocho health 200, ausencia/token inválido 401, ID token 403, preflight 204 y origen no permitido sin autorización CORS. Nueve pruebas unitarias de guardas/revisión, sintaxis y validador estructural aprobados; git diff --check ejecutado.

Solo se modifica Infrastructure. El migrador oficial se invocó exclusivamente para preparar/retirar datos sintéticos del runner HTTP existente de Platform. No se publican cambios en Platform ni Database, ni trabajo local ajeno. La operación completa y el mapa de IDs quedan en [api-native-verification.json](api-native-verification.json); pruebas en [antes](admin-api-before-http.json), [después](admin-api-after-http.json) y [salud/autenticación/CORS](admin-api-auth-health.json).
