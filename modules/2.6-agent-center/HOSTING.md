# Hosting frontend Centro de Agentes (agents.uonify.com)

Página estática mínima en https://agents.uonify.com (título **Centro de Agentes — MasterERP**), servida por **S3** (origen privado) y **CloudFront** con TLS. El HTML se genera en el workflow de este repositorio `.github/workflows/publish-agents-uonify.yml`; no hay `index.html` en el árbol de código.

## Plantillas y stacks

| Archivo | Stack CloudFormation | Región |
| --- | --- | --- |
| `agents-frontend-certificate.json` | `mastererp-dev-agents-frontend-certificate` | **us-east-1** (ACM para CloudFront) |
| `agents-frontend-hosting.json` | `mastererp-dev-agents-frontend` | **us-west-1** (S3, CloudFront, Route53, rol OIDC) |

Recursos del hosting: bucket versionado y cifrado, OAC SigV4, distribución con alias `agents.uonify.com`, política de bucket restringida al ARN de la distribución, registros DNS **A** y **AAAA** en la zona `Z08167243FAUSDUW0Z2KP`, rol IAM **mastererp-dev-agents-frontend-github-role** para publicación OIDC. El `sub` del trust debe coincidir con el [sujeto inmutable](https://docs.github.com/en/actions/deployment/security/hardening-your-deployments/about-security-hardening-with-openid-connect) de este repositorio, p. ej. `repo:eticayservicios@144081289/mastererp-infrastructure@1434968384:ref:refs/heads/dev` (ver `gh api repos/.../actions/oidc/customization/sub`).

## Desplegar infraestructura

Desde la raíz de este repositorio, con perfil `mastererp-admin` (o credenciales equivalentes en la cuenta **277352717693**):

```powershell
python scripts/deploy_agents_frontend.py certificate prepare --profile mastererp-admin --output build/agents-frontend
# Revisar build/agents-frontend/certificate-plan.json
python scripts/deploy_agents_frontend.py certificate execute --profile mastererp-admin --output build/agents-frontend
aws cloudformation wait stack-create-complete --profile mastererp-admin --region us-east-1 --stack-name mastererp-dev-agents-frontend-certificate

python scripts/deploy_agents_frontend.py hosting prepare --profile mastererp-admin --output build/agents-frontend
# Revisar build/agents-frontend/hosting-plan.json
python scripts/deploy_agents_frontend.py hosting execute --profile mastererp-admin --output build/agents-frontend
aws cloudformation wait stack-create-complete --profile mastererp-admin --region us-west-1 --stack-name mastererp-dev-agents-frontend
aws cloudformation describe-stacks --profile mastererp-admin --region us-west-1 --stack-name mastererp-dev-agents-frontend --query "Stacks[0].Outputs"
```

El certificado ACM debe estar en estado **ISSUED** antes de crear o actualizar CloudFront.

## Publicación automática (GitHub Actions)

1. En el repositorio **mastererp-infrastructure**, añadir variables `AGENTS_UONIFY_BUCKET` y `AGENTS_UONIFY_DISTRIBUTION_ID` (valores de los outputs `FrontendBucketName` y `FrontendDistributionId` del stack de hosting).
2. Workflow **Publish agents.uonify.com**: push a `dev` o ejecución manual (`workflow_dispatch`). Asume el rol `mastererp-dev-agents-frontend-github-role`, sube `index.html` e invalida CloudFront.

Si el stack de hosting ya existía con el sujeto OIDC antiguo (`mastererp-platform`), aplicar un **change set** con la plantilla actualizada para que el rol acepte tokens de **este** repositorio.

## Publicación manual (alternativa)

```powershell
$BUCKET = <FrontendBucketName del output>
$DIST = <FrontendDistributionId del output>
# Crear index.html localmente o copiar el generado por el workflow
aws s3 cp index.html "s3://$BUCKET/index.html" --content-type "text/html; charset=utf-8" --cache-control "no-cache,max-age=0,must-revalidate" --profile mastererp-admin --region us-west-1
aws cloudfront create-invalidation --distribution-id $DIST --paths "/ /index.html" --profile mastererp-admin
```

## Verificación

```powershell
python scripts/verify_agents_frontend.py --profile mastererp-admin --output build/agents-frontend/verification.json
```

Comprueba TLS, redirección HTTP→HTTPS, presencia del título **Centro de Agentes**, bloqueo de lectura anónima en S3 y coherencia HTML S3/CloudFront.

## Notas

- No modifica `app-dev.uonify.com` ni el hosting de Finanzas.
- El dominio por defecto es **agents.uonify.com**. Para un subdominio DEV aparte (p. ej. `agents-dev.uonify.com`), duplicar parámetros y stacks con otro sufijo de entorno.
- Precio CloudFront: `PriceClass_100` (EE. UU., Canadá y Europa).
