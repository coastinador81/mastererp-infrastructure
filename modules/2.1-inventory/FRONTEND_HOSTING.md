# Hosting frontend de Inventario DEV

Propietario único: módulo 2.1 Inventario, resources.yml raíz. Stack regional mastererp-dev-inventory-frontend en us-west-1; certificado en mastererp-dev-inventory-frontend-certificate, us-east-1. Dominio inventario-dev.uonify.com, zona autoritativa uonify.com Z08167243FAUSDUW0Z2KP, delegación comprobada con DNS público. No modifica APIs, Database, Cognito ni otros stacks.

## Recursos

S3 privado cifrado AES256 con versionado y cuatro bloqueos públicos; retención para bucket. CloudFront REST S3 con OAC firmado, HTTPS por redirección, TLS mínimo 1.2; index.html como documento inicial. Política de lectura solo para la distribución propietaria, denegación de transporte no seguro. Registros A/AAAA Route53. Rol OIDC exclusivo para Platform/dev, permisos únicamente de lectura/listado/publicación en su bucket e invalidación en su distribución. No hay origen API ni fallback SPA: la navegación usa ?vista.

Certificate.yml declara exclusivamente ACM y validación DNS en la zona existente. Hosting recibe el ARN mediante parámetro explícito. Parámetros de ambiente/dominio preparados sin crear QA/PROD. Script de bootstrap limitado a DEV y cuenta 277352717693; nunca despliega otro módulo.

## Despliegue reproducible

Desde Infrastructure, con un perfil autorizado (sin exportar secretos):

```powershell
py scripts/deploy_inventory_frontend.py certificate prepare --profile mastererp-admin --output build/inventory-dev
# Revisar certificate-plan.json: solo Certificate Add para creación.
py scripts/deploy_inventory_frontend.py certificate execute --profile mastererp-admin --output build/inventory-dev
aws cloudformation wait stack-create-complete --profile mastererp-admin --region us-east-1 --stack-name mastererp-dev-inventory-frontend-certificate
py scripts/deploy_inventory_frontend.py hosting prepare --profile mastererp-admin --output build/inventory-dev
# Revisar hosting-plan.json: sin recursos ajenos, eliminaciones o reemplazos.
py scripts/deploy_inventory_frontend.py hosting execute --profile mastererp-admin --output build/inventory-dev
aws cloudformation wait stack-create-complete --profile mastererp-admin --region us-west-1 --stack-name mastererp-dev-inventory-frontend
```

No ejecutar un prepare/execute sobre un stack ajeno. El ejecutor compara el change set revisado antes de ejecutarlo y rechaza eliminaciones/reemplazos. Un segundo prepare sin cambios informa NO_CHANGES. Planes build/ ignorados, sin secretos. Para una actualización usar stack-update-complete si corresponde.

## Publicar artefacto

Platform: frontend/modules/2.1-inventory, npm ci y npm run build. Workflow preparado publish-inventory-dev.yml, rama dev, OIDC, con variables no secretas INVENTORY_DEV_BUCKET y INVENTORY_DEV_DISTRIBUTION_ID de los outputs. Hasta publicar ese workflow puede hacerse bootstrap del mismo artefacto por CLI:

```powershell
$inventoryBucket = aws cloudformation describe-stacks --profile mastererp-admin --region us-west-1 --stack-name mastererp-dev-inventory-frontend --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue | [0]" --output text
$inventoryDistribution = aws cloudformation describe-stacks --profile mastererp-admin --region us-west-1 --stack-name mastererp-dev-inventory-frontend --query "Stacks[0].Outputs[?OutputKey=='FrontendDistributionId'].OutputValue | [0]" --output text
aws s3 sync ../mastererp-platform/frontend/modules/2.1-inventory/dist/ "s3://$inventoryBucket/" --exclude index.html --cache-control 'public,max-age=31536000,immutable' --profile mastererp-admin --region us-west-1
aws s3 cp ../mastererp-platform/frontend/modules/2.1-inventory/dist/index.html "s3://$inventoryBucket/index.html" --content-type 'text/html; charset=utf-8' --cache-control 'no-cache,max-age=0,must-revalidate' --profile mastererp-admin --region us-west-1
aws cloudfront create-invalidation --profile mastererp-admin --distribution-id $inventoryDistribution --paths / /index.html
```

Verificar DNS, HTTPS 200, contenido, redirección HTTP y denegación S3 sin firma. Recuperación: republicar artefacto anterior y nueva invalidación, sin eliminar stacks. El hosting público solo sirve base visual sin datos ni operaciones; autenticación y autorización de inventario pendientes.

## Límites funcionales aprobados

Ecommerce posee Nodos y Preparación; nodo representa sucursal por ahora. Sin Nodos se utilizará una sucursal predeterminada sin selector; multinodo requiere activación y autorización reales. Sin almacenes. No se trasladan los directorios históricos en esta tarea ni se modifican sus recursos. No hay nueva Lambda, migrador, API o SQL.

## Resultado del bootstrap verificado — 2026-11-08

- Cuenta 277352717693, perfil mastererp-admin; identidad devops-duran.
- Certificado: stack mastererp-dev-inventory-frontend-certificate, us-east-1, CREATE_COMPLETE; ACM ISSUED con validación DNS SUCCESS.
- Hosting: stack mastererp-dev-inventory-frontend, us-west-1, CREATE_COMPLETE.
- Bucket: mastererp-dev-inventory-web-277352717693-us-west-1.
- Distribución: EQ2JCACZWCPPW, d1f7xqyk7ss5og.cloudfront.net.
- Rol: mastererp-dev-inventory-frontend-github-role.
- URL: https://inventario-dev.uonify.com.
- Bootstrap del artefacto compilado por AWS CLI, con Content-Type text/html UTF-8 y no-cache para index; assets inmutables. No se ejecutó un workflow de publicación todavía.
- Variables Platform INVENTORY_DEV_BUCKET e INVENTORY_DEV_DISTRIBUTION_ID configuradas con esos outputs, sin secretos. Workflow preparado localmente; sin commit ni push de esta entrega.
- DNS resuelto; TLS 1.3 y certificado válido; HTTP 301 a HTTPS; HTTPS 200 y contenido Inventario; objeto S3 sin firma 403.
- Navegador DEV: Resumen, menú, navegación/recarga, requisito Nodos sin selector, lanzador misma pestaña, móvil y Escape; sin llamadas API. Pruebas visuales, no inventario funcional.
- Segundo prepare hosting: NO_CHANGES, recursos conservados. Plantillas validadas por CloudFormation y validadores estructurales aprobados.

El bootstrap no desplegó otras aplicaciones. La publicación posterior del catálogo compartido por los workflows incorpora Inventario y Chat principal en sus menús. No se publicaron cambios ajenos ni los candidatos locales de Sugerencias de Finanzas.
