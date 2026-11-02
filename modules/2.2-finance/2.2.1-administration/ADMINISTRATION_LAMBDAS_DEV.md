# Lambdas técnicas de Administración DEV

Estado de esta entrega: integración de las ocho rutas públicas de diagnóstico desplegada y verificada; ver sección Integración HTTP. La sección Resultado comprobado de la fase inicial describe el despliegue anterior sin API.

Ocho diagnósticos mínimos, sin capacidades de negocio, base de datos, secretos, llamadas de red, API Gateway o Function URL. Región us-west-1; cuenta 277352717693. Invocación directa exclusivamente mediante identidad IAM autorizada. El statusCode 200 del handler no es evidencia HTTP de una API.

## Propiedad

Código: mastererp-platform/backend/modules/2.2-finance/2.2.1-administration, bajo lambdas/<nombre> en la carpeta funcional de cada capacidad. Recursos: mismo propietario funcional en mastererp-infrastructure/modules, declarados en su resources.yml raíz. El manifiesto scripts/administration_lambdas.json identifica las ocho ubicaciones y coincide entre ambos repositorios. No se replican carpetas técnicas de Lambdas en Infrastructure.

Un único stack nuevo mastererp-dev-administration ensambla las ocho plantillas funcionales, sin duplicarlas en un YAML agregado versionado: 8 funciones, 8 roles y 8 Log Groups. El ensamblado generado es un artefacto temporal. No reemplaza stacks existentes. Cada rol permite únicamente logs:CreateLogStream y logs:PutLogEvents sobre su propio Log Group precreado. Sin políticas administradas generales. Retención de logs: 14 días. Python 3.12, ARM64, 128 MB y timeout 5 segundos: proporcionales a una respuesta constante sin dependencias ni binarios. Sin VPC ni variables de credenciales.

## Preparación reproducible

Requisitos: Python estándar y AWS CLI ya configurado. No instalar dependencias. Los ejemplos asumen ambos repositorios como carpetas hermanas y ejecución desde mastererp-infrastructure. En Windows usar py en lugar de python. Elegir un directorio temporal fuera de los repositorios.

```powershell
Push-Location ../mastererp-platform
py scripts/validate_structure.py
git diff --check
Pop-Location
py scripts/validate_structure.py
py scripts/deploy_administration.py --platform-root ../mastererp-platform --output "$env:TEMP/mastererp-administration-dev" --bucket aws-sam-cli-managed-default-samclisourcebucket-sxnqlc5ufsez
```

Ejecutar también git diff --check desde cada repositorio. El empaquetador compila/importa cada handler, verifica dos eventos y produce ZIP deterministas que solo contienen handler.py. No incluye .env, credenciales, dependencias, archivos locales ni código de otros módulos.

## Publicación y despliegue autorizado

Publicar commits de alcance exclusivo en dev, revisar los disparadores y conservar cambios locales ajenos fuera del commit. Los workflows actuales solo validan estructura para estas rutas; no despliegan automáticamente Administración. El despliegue usa el mecanismo existente CloudFormation mediante AWS CLI y este script, no un workflow nuevo ni una actualización directa fuera de IaC.

```powershell
aws sts get-caller-identity --profile mastererp-admin --region us-west-1
py scripts/deploy_administration.py --profile mastererp-admin --platform-root ../mastererp-platform --output "$env:TEMP/mastererp-administration-dev" --bucket aws-sam-cli-managed-default-samclisourcebucket-sxnqlc5ufsez --deploy --verify
```

El script verifica cuenta, región y bloqueo público del bucket existente; rechaza funciones con propietarios ajenos. Publica ZIP con claves de contenido SHA-256, valida la plantilla combinada, prepara un change set, muestra y comprueba sus cambios antes de ejecutarlo: solo Add/Modify de los 24 recursos previstos, sin reemplazos ni eliminaciones. Compara el SHA desplegado con el artefacto e invoca cada diagnóstico únicamente si se solicita --verify. No reintenta despliegues fallidos automáticamente.

## Comprobación y recuperación

Conservar changeset.json, manifest.json y verification.json del directorio temporal como evidencia no secreta. Verificar Active, LastUpdateStatus Successful y ocho respuestas de invocación sin FunctionError, statusCode 200 y JSON esperado. Revisar que no haya Function URL, permisos de invocación públicos, VPC ni permisos de datos. Las API y funciones preexistentes deben permanecer sin cambios.

Si falla, inspeccionar aws cloudformation describe-stack-events --stack-name mastererp-dev-administration --profile mastererp-admin --region us-west-1; no ampliar permisos de aplicación para hacerlo pasar. CloudFormation revierte su propio stack al fallar. Para una actualización posterior, recuperar los commits/artefactos anteriores y preparar otro change set sin reemplazos. No borrar automáticamente el stack, logs ni artefactos; una eliminación requiere petición explícita. El bucket reutilizado no pertenece a este stack y no se elimina al revertirlo.

Clientes y Proveedores no crean maestros nuevos. Sin modificaciones de Database, SQL ni frontend. Las rutas HTTP y su autenticación se implementarán en una entrega posterior autorizada.

## Resultado comprobado de la fase inicial sin API — 2026-11-02

Stack mastererp-dev-administration: CREATE_COMPLETE. Ocho funciones Active y LastUpdateStatus Successful. Las ocho invocaciones directas IAM devolvieron statusCode 200 y JSON status=ok con el nombre exacto; sin FunctionError. Código publicado: Platform 37ed114; plantillas y procedimiento: Infrastructure 4336144. Validadores locales y de GitHub aprobados. CloudFormation validó las ocho plantillas y el ensamblado; change set de 24 altas, sin modificaciones ni eliminaciones.

Se verificaron roles limitados al Log Group propio, retención de 14 días, ausencia de Function URL y política de invocación pública, sin VPC ni variables de credenciales. Comparación antes/después: tres API Gateway (configuración, rutas, integraciones y autorizadores) y cinco Lambdas preexistentes sin cambios. No se ejecutó SQL ni se modificó Database o frontend.

[Evidencia sanitizada y ARN de las ocho funciones](administration-dev-verification.json). Son pruebas técnicas mediante invocación directa, no pruebas HTTP ni capacidades funcionales implementadas. API Gateway queda fuera de esta entrega por instrucción del propietario.

## Integración HTTP — decisión posterior del propietario

El propietario solicitó dejar públicas únicamente estas ocho rutas técnicas GET /v1/administration/<capacidad>/health (AuthorizationType NONE). No se implementa autorización de operaciones de negocio ni se entregan datos de tenant. No se crean ni modifican Cognito o autorizadores. La prueba esperada ahora es HTTP 200 SIN token; la comprobación anterior de denegación sin token queda reemplazada por esta decisión explícita.

API reutilizada: mastererp-dev-admin-api, ID qx8nmypdhi; base https://qx8nmypdhi.execute-api.us-west-1.amazonaws.com. Propietario confirmado: mastererp-dev-onboarding, recurso AdminHttpApi; stage $default con AutoDeploy. La API administrativa no tenía autorizadores. Se preservan CORS, las 12 rutas y 12 integraciones previas; no se despliega modules/api-gateways.yml ni se actualiza el stack de onboarding, que contiene recursos heredados pendientes de transición.

Cada resources.yml raíz propietario añade solo su Integration AWS_PROXY (payload 2.0), HealthRoute GET y ApiPermission. El permiso restringe cuenta, API, stage $default, método GET y ruta exacta. ExistingAdminApiId se parametriza y limita al ID confirmado. No se cambia el código de las Lambdas, sus roles ni su configuración.

El stack mastererp-dev-administration ensambla ahora 48 recursos: los 24 anteriores y 24 nuevos de integración (8 rutas, 8 integraciones y 8 permisos). El ensamblado debe conservar los 24 recursos anteriores sin cambios. El change set esperado contiene únicamente 24 altas. No se crea otra API ni se cambia su propietario. El script anterior actualizado conserva todas las declaraciones al reaplicar; no usar versiones antiguas de 24 recursos porque retirarían las rutas del stack.

Desplegar con el mismo comando --deploy --verify documentado arriba. Después, desde Infrastructure:

```powershell
py scripts/validate_administration_http.py --output "$env:TEMP/mastererp-administration-api/http-verification.json"
```

El validador no obtiene contraseñas ni tokens: exige 200 y JSON exacto en las ocho rutas sin autenticación, y comprueba preflight del origen legítimo existente. CORS permanece a cargo de la API y Lambda no añade cabeceras CORS. No se añade app-dev.uonify.com ni otro origen por esta entrega. Comparar las rutas/integraciones originales y configuración CORS antes y después; los IDs nuevos se admiten solo para estas ocho capacidades.

Recuperación: inspeccionar eventos del stack y preparar un change set que retire únicamente los 24 recursos de esta integración si se requiere revertirla; conservar las ocho funciones y las rutas ajenas. No ejecutar eliminaciones o restauraciones automáticamente. Antes de añadir lógica o datos de negocio, definir e implementar JWT y autorización funcional de tenant; estos diagnósticos no acreditan esas capacidades.

## Resultado HTTP comprobado — 2026-11-02

Las ocho rutas GET públicas respondieron HTTP 200 SIN token, cuerpo exacto status=ok y nombre de su Lambda, con Cache-Control no-store. Los ocho preflight del origen legítimo existente respondieron 204. No se obtuvieron, imprimieron ni guardaron tokens para estas pruebas. JWT y rechazo sin token no se probaron como controles porque fueron excluidos explícitamente por el propietario.

API qx8nmypdhi conservada en mastererp-dev-onboarding; CORS y autorizadores sin cambios. Las 12 rutas y 12 integraciones previas se conservaron por ID y configuración; las otras dos API permanecen iguales. Change set de mastererp-dev-administration: exactamente 24 altas de rutas, integraciones y permisos, sin modificar o eliminar los recursos previos; estado UPDATE_COMPLETE. Código de handlers sin cambios.

Commits: Platform 9e8a57f (documentación); Infrastructure 92e967a (integraciones y procedimiento). Los validadores locales y los de GitHub aprobaron. [Resultados HTTP y comparación de preservación](administration-api-verification.json). Estas rutas son pruebas técnicas públicas, no capacidades funcionales ni evidencia de autorización multi-tenant. Database no se modificó.
