# Hosting storefront público (tienda-dev.uonify.com)

El frontend de https://tienda-dev.uonify.com pertenece a mastererp-platform, en
`frontend/modules/2.3-ecommerce/2.3.2-stores/storefront/`. Su build y publicación
son responsabilidad exclusiva del workflow Platform `.github/workflows/publish-storefront-dev.yml`.
Infrastructure conserva únicamente las definiciones y los scripts de infraestructura del hosting.

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

Publicación canónica: workflow Platform `.github/workflows/publish-storefront-dev.yml`. No existe un publicador alternativo de la tienda en Infrastructure.

## Propiedad de publicación de la aplicación

La aplicación Expo de tienda-dev.uonify.com se publica desde Platform mediante publish-storefront-dev.yml. Usa STOREFRONT_UONIFY_BUCKET y STOREFRONT_UONIFY_DISTRIBUTION_ID referenciando los recursos existentes. Infrastructure conserva IaC. Se retiraron el HTML histórico «Hola mundo» y su workflow de bootstrap manual para evitar que sobrescriban la aplicación. Esta limpieza no modifica buckets, objetos publicados, CloudFront, DNS, certificados, roles IAM ni stacks. La recuperación de contenido debe realizarse desde los artefactos del frontend de Platform, no recreando una segunda implementación en Infrastructure.
