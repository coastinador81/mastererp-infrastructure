# Hosting frontend de Finanzas DEV

Histórico de la primera entrega: página pública inicial en https://finanzas-dev.uonify.com: Finanzas — MasterERP, Desarrollo y Hola mundo. Sin login, datos, APIs u operaciones. Autenticación y navegación/contexto con Uonify son otra entrega. No modificar app-dev.uonify.com.

## Recorrido integrado y acceso independiente

La entrega actual sustituye el Hola mundo por el mismo shell y pantallas de Finanzas que se compilan en Uonify. La raíz general sigue siendo app-dev.uonify.com; este hosting permite desarrollo independiente autenticado con el mismo cliente Cognito y callback explícito. Sus orígenes API /v1/uonify/* y /v1/administration/* consumen las APIs existentes sin caché y sin reimportarlas; cada operación mantiene JWT y autorización. Ver [procedimiento común](../0-uonify/FRONTEND_DEPLOYMENT.md) y Platform/docs/FINANCE_UI_INTEGRATION.md para resultados. La evidencia de abajo corresponde a la primera entrega, con su fecha.

## Papel del acceso independiente

La entrada general DEV de MasterERP es app-dev.uonify.com. La experiencia objetivo presenta las pantallas de Finanzas dentro del espacio de Uonify con navegación, identidad y contexto comunes, mediante menú o chat opcional. finanzas-dev.uonify.com se conserva como acceso independiente de desarrollo y pruebas; no es la navegación objetivo del usuario final ni obliga a crear finanzas.uonify.com en producción.

Finanzas conserva componentes, build, pipeline, despliegue y rollback propios. El primer recorrido integra pantallas por composición en build y rutas hash, documentadas en Platform; las demás capacidades siguen pendientes; no se impone `/finanzas`, iframe, Module Federation u otra solución. El hosting y las pruebas que se documentan abajo acreditan solo la página independiente ya publicada. La decisión de experiencia no elimina hosting ni cambia DNS, stacks o recursos. Ver [contrato oficial](../../docs/FRONTEND_ARCHITECTURE.md).

## Propiedad y composición explícita

- `resources.yml`: única declaración de bucket privado versionado/cifrado, OAC, distribución, política restringida a su ARN, DNS A/AAAA y rol OIDC exclusivo de publicación.
- Stack propietario del hosting: `mastererp-dev-finance-frontend`, us-west-1. Dominio Finanzas; ciclo de vida separado del padre backend existente `mastererp-dev-finance` y su Administración anidada. No se traslada ningún recurso backend.
- `certificate.yml`: stack auxiliar `mastererp-dev-finance-frontend-certificate`, us-east-1, exclusivamente ACM validado por DNS. Publica CertificateArn que el script entrega explícitamente al hosting.
- `Metadata.FinanceFrontendComposition` identifica parámetros/recursos/outputs del artefacto ensamblado. `scripts/deploy_finance_frontend.py` extrae solo esa vista y retira su condición de activación. Nunca desplegar resources.yml completo para crear hosting: incluye el backend ajeno a esta entrega. En el padre original FinanceFrontendEnabled=false mantiene los nuevos recursos excluidos.
- Environment y dominio parametrizados para futura revisión QA/PROD. El ejecutor y rol publicados están limitados a DEV/cuenta 277352717693; no crear otros ambientes cambiando solo parámetros.

## Inspección previa

Cuenta consultada por STS: 277352717693, usuario devops-duran. La zona Z08167243FAUSDUW0Z2KP coincide con los NS públicos de uonify.com consultados en 1.1.1.1. Al preparar esta entrega no existían alias CloudFront, certificado, bucket o registro para Finanzas DEV. Se reutiliza esa zona y el proveedor OIDC token.actions.githubusercontent.com; no los recrea la plantilla. app-dev.uonify.com conserva su distribución E146MXYK3KTLSB y stack ajenos.

## Preparar, revisar y aplicar infraestructura

Desde Infrastructure, con boto3 y credenciales existentes; omitir --profile en un entorno con credenciales efímeras. No almacena secretos. El script valida la cuenta y las plantillas, bloquea eliminaciones y reemplazos, y guarda el change set para revisión. No aplica automáticamente.

```powershell
python scripts/deploy_finance_frontend.py certificate prepare --profile mastererp-admin --output build/finance-frontend
# Revisar certificate-plan.json: solo certificado propio.
python scripts/deploy_finance_frontend.py certificate execute --profile mastererp-admin --output build/finance-frontend
aws cloudformation wait stack-create-complete --profile mastererp-admin --region us-east-1 --stack-name mastererp-dev-finance-frontend-certificate
python scripts/deploy_finance_frontend.py hosting prepare --profile mastererp-admin --output build/finance-frontend
# Revisar hosting-plan.json: solo los seis recursos FinanceFrontend*, sin reemplazos/borrados.
python scripts/deploy_finance_frontend.py hosting execute --profile mastererp-admin --output build/finance-frontend
aws cloudformation wait stack-create-complete --profile mastererp-admin --region us-west-1 --stack-name mastererp-dev-finance-frontend
aws cloudformation describe-stacks --profile mastererp-admin --region us-west-1 --stack-name mastererp-dev-finance-frontend --query 'Stacks[0].Outputs'
```

Para actualizaciones esperar stack-update-complete cuando exista un change set con cambios. Una preparación sin diferencias devuelve NO_CHANGES y no modifica recursos. Repetir prepare después de cada edición, revisar y ejecutar solo el plan nuevo. El certificado debe estar ISSUED antes de crear CloudFront. No añadir permisos de APIs, Cognito, RDS ni otros buckets.

## Build y publicación

Platform `frontend/modules/2.2-finance/`: `npm ci` y `npm run build`; Node 24, Vite fijado en lockfile. Workflow Platform `.github/workflows/publish-finance-dev.yml`, independiente, con concurrencia DEV. Rol OIDC del hosting limitado a sujeto inmutable `repo:eticayservicios@144081289/mastererp-platform@1434968316:ref:refs/heads/dev` y aud sts.amazonaws.com, verificado mediante `gh api repos/eticayservicios/mastererp-platform/actions/oidc/customization/sub`. No aceptar sujetos de otros repositorios o ramas. Solo ListBucket/GetObject/PutObject del bucket propio e invalidación de su distribución. No crea claves permanentes ni permisos de despliegue de infraestructura.

Configurar variables de repositorio Platform FINANCE_DEV_BUCKET y FINANCE_DEV_DISTRIBUTION_ID usando los outputs homónimos del stack (FrontendBucketName/FrontendDistributionId). Publicar dev activa build, upload e invalidación; no disparar otra ejecución simultánea.

Publicación manual reproducible del mismo artefacto, únicamente si no hay workflow en curso:

```powershell
aws s3 sync <dist>/ s3://<FrontendBucketName>/ --exclude index.html --cache-control 'public,max-age=31536000,immutable' --profile mastererp-admin --region us-west-1
aws s3 cp <dist>/index.html s3://<FrontendBucketName>/index.html --content-type 'text/html; charset=utf-8' --cache-control 'no-cache,max-age=0,must-revalidate' --profile mastererp-admin --region us-west-1
aws cloudfront create-invalidation --distribution-id <FrontendDistributionId> --paths / /index.html --profile mastererp-admin
```

No se configura website público ni fallback SPA. CloudFront usa S3 REST, OAC SigV4 siempre, TLS mínimo 1.2 y redirección HTTP→HTTPS. Cache policy administrada CachingOptimized; HTML con no-cache y min TTL de esa política de 1 segundo, más invalidación en cada publicación. Los assets con hash se conservan para evitar errores durante rollback. S3 rechaza transporte sin TLS y acceso anónimo; los cuatro bloqueos públicos están activos.

## Verificación y recuperación

```powershell
python scripts/verify_finance_frontend.py --profile mastererp-admin --output build/finance-frontend/verification.json
```

El verificador es de solo lectura, comprueba TLS con verificación de hostname/cadena, redirección, textos y assets, bloqueo S3, política y OAC, y guarda IDs físicos para comparar después del segundo despliegue. No confundirlo con pruebas de negocio.


Comprobar DNS público A/AAAA, HTTPS sin omitir verificación TLS, GET / HTTP 200 con los tres textos, HTTP→HTTPS, HTML Content-Type y S3 REST anónimo 403. Repetir prepare/execute sin cambios debe conservar IDs; repetir la publicación debe actualizar el artefacto e invalidación. Comparar hashes de objetos con dist y revisar la ejecución real del workflow.

Recuperar contenido mediante revert acotado de archivos de esta aplicación en Platform/dev (nuevo commit) o republicación del artefacto previo revisado, seguido de invalidación. No borrar bucket, certificado, distribución o stacks. El bucket tiene Retain y versionado. Si falla una actualización de infraestructura, revisar eventos/rollback de CloudFormation; no trasladar propiedad ni recrear recursos para forzar éxito.

## Resultado de esta ejecución

Comprobado en DEV el 2026-11-03:

| Recurso | Propietario / identificador |
| --- | --- |
| Hosting | mastererp-dev-finance-frontend, us-west-1, UPDATE_COMPLETE |
| Bucket privado | mastererp-dev-finance-web-277352717693-us-west-1 |
| CloudFront | E1S38NCRMLNTNV; d3ekgfbquy6pq4.cloudfront.net; Deployed |
| OAC | ESWK4O5SKNRWG |
| DNS A/AAAA | finanzas-dev.uonify.com, zona Z08167243FAUSDUW0Z2KP |
| Certificado | mastererp-dev-finance-frontend-certificate, us-east-1; a03020cc-a31d-49d0-b9f3-2782a725dd9c; ISSUED |
| Publicación OIDC | mastererp-dev-finance-frontend-github-role |

Se revisaron los change sets: certificado Add; hosting seis Add; corrección posterior solo Modify de AssumeRolePolicyDocument sin reemplazo. La primera publicación [41635023399](https://github.com/eticayservicios/mastererp-platform/actions/runs/41635023399) falló antes de subir archivos por usar el formato anterior del sujeto OIDC. Se inspeccionó la configuración GitHub y se corrigió al sujeto inmutable exacto, sin ampliar permisos. También se retiró un input no soportado de configure-aws-credentials@v4.

Publicación automática corregida [41637395248](https://github.com/eticayservicios/mastererp-platform/actions/runs/41637395248): success, incluyendo build, OIDC, subida e invalidación. Segunda publicación secuencial sin cambios funcionales [41637696282](https://github.com/eticayservicios/mastererp-platform/actions/runs/41637696282): success. Se compararon los seis IDs físicos, todos iguales; index.html tiene nueva VersionId de S3 y el mismo SHA-256 de contenido. Repreparar hosting y certificado devolvió NO_CHANGES; execute de ese plan de hosting fue no-op.

Verificaciones reales con el verificador: DNS normal resuelve; TLS válido para finanzas-dev.uonify.com (negociado TLS 1.3); HTTPS / 200, text/html; charset=utf-8, con los tres textos; JS y CSS 200; HTTP 301 a HTTPS; S3 REST index.html sin autenticación 403; cuatro bloqueos públicos activos, política IsPublic=false y acceso OAC restringido al ARN de esta distribución. HTML de CloudFront coincide con S3. Tras normalizar LF en la aplicación, el build local coincide byte a byte con CI: SHA-256 ea34a4261e9a918ba85ea68b4784e95bf798ae9275a6a0b7289dafe24b354bf0. Se fijó Vite 8.3.5: npm audit no detectó vulnerabilidades.

Build y repetición local, parseo YAML, Bash -n, compilación Python, validadores estructurales de ambos repositorios y git diff --check aprobados. Las definiciones backend preexistentes de Finance (parámetros, recursos y outputs) se compararon con HEAD previo y permanecen iguales. El stack Uonify conservaba UPDATE_COMPLETE y LastUpdatedTime 2026-11-01T16:27:54.302Z; no se desplegó sobre él. No se modificaron APIs, Cognito, Lambdas o Database.

Las evidencias detalladas y planes locales están en build/finance-frontend/ (ignorado; sin secretos). La página no demuestra operaciones financieras, autenticación o continuidad de contexto; siguen pendientes para otra entrega.
