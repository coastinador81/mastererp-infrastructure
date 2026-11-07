# Hosting storefront público (tienda-dev.uonify.com)

Página estática provisional (`Hola mundo`) en https://tienda-dev.uonify.com, fuente
`storefront-static/index.html`, publicada por `.github/workflows/publish-tienda-dev-uonify.yml`.

## Plantillas y stacks

| Archivo | Stack CloudFormation | Región |
| --- | --- | --- |
| `storefront-frontend-certificate.json` | `mastererp-dev-storefront-frontend-certificate` | **us-east-1** |
| `storefront-frontend-hosting.json` | `mastererp-dev-storefront-frontend` | **us-west-1** |

## Desplegar infraestructura

```powershell
python scripts/deploy_storefront_frontend.py certificate prepare --profile mastererp-admin --output build/storefront-frontend
python scripts/deploy_storefront_frontend.py certificate execute --profile mastererp-admin --output build/storefront-frontend
aws cloudformation wait stack-create-complete --profile mastererp-admin --region us-east-1 --stack-name mastererp-dev-storefront-frontend-certificate

python scripts/deploy_storefront_frontend.py hosting prepare --profile mastererp-admin --output build/storefront-frontend
python scripts/deploy_storefront_frontend.py hosting execute --profile mastererp-admin --output build/storefront-frontend
aws cloudformation wait stack-create-complete --profile mastererp-admin --region us-west-1 --stack-name mastererp-dev-storefront-frontend
```

Publicación manual del Hola mundo:

```powershell
$BUCKET = <FrontendBucketName>
$DIST = <FrontendDistributionId>
aws s3 cp modules/2.3-ecommerce/2.3.2-stores/storefront-static/index.html "s3://$BUCKET/index.html" --content-type "text/html; charset=utf-8" --cache-control "no-cache,max-age=0,must-revalidate" --profile mastererp-admin --region us-west-1
aws cloudfront create-invalidation --distribution-id $DIST --paths "/ /index.html" --profile mastererp-admin
```

## CORS Client API (`btqqku792c`)

El stack propietario es `mastererp-dev-http-apis`. Tras cambiar dominios de storefront,
aplicar `modules/2.3-ecommerce/2.3.2-stores/client-api-cors-dev.json`:

```powershell
python scripts/apply_client_api_cors.py --profile mastererp-admin
```

## Publicación

Variables GitHub (repositorio **mastererp-platform**, rama `dev`):

- `STOREFRONT_UONIFY_BUCKET`, `STOREFRONT_UONIFY_DISTRIBUTION_ID` (outputs del stack)
- `STOREFRONT_DEV_TENANT_ID` (tenant business con la tienda activa para el dominio)

Publicación canónica: workflow Platform `.github/workflows/publish-storefront-dev.yml`. El workflow de Infrastructure queda solo para la página estática provisional.
