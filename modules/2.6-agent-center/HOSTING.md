# Hosting frontend Centro de Agentes (agentes-dev.uonify.com)

Página de aterrizaje en https://agentes-dev.uonify.com con **misma línea visual que Finanzas** (tokens `--finance-*`, clase `finance-app`): fuente `modules/2.6-agent-center/agents-static/landing.html`, publicada como `index.html` por `.github/workflows/publish-agents-uonify.yml`. Criterios de producto y referencias en [UX.md](UX.md).

## Plantillas y stacks

| Archivo | Stack CloudFormation | Región |
| --- | --- | --- |
| `agents-frontend-certificate.json` | `mastererp-dev-agents-frontend-certificate` | **us-east-1** (ACM para CloudFront) |
| `agents-frontend-hosting.json` | `mastererp-dev-agents-frontend` | **us-west-1** (S3, CloudFront, Route53, OIDC) |

Recursos del hosting: bucket versionado y cifrado, OAC SigV4, distribución con alias **agentes-dev.uonify.com**, política de bucket restringida al ARN de la distribución, registros DNS **A** y **AAAA** en la zona `Z08167243FAUSDUW0Z2KP`, rol IAM **mastererp-dev-agents-frontend-github-role** para publicación OIDC. El `sub` del trust debe coincidir con el [sujeto inmutable](https://docs.github.com/en/actions/deployment/security/hardening-your-deployments/about-security-hardening-with-openid-connect) de este repositorio, p. ej. `repo:eticayservicios@144081289/mastererp-infrastructure@1434968384:ref:refs/heads/dev` (ver `gh api repos/.../actions/oidc/customization/sub`).

## Desplegar infraestructura

Desde la raíz de este repositorio, con perfil `mastererp-admin` (o credenciales equivalentes en la cuenta **277352717693**). El script pasa **`FrontendDomainName`** explícitamente (por defecto `agentes-dev.uonify.com`):

```powershell
python scripts/deploy_agents_frontend.py certificate prepare --profile mastererp-admin --output build/agents-frontend
# Revisar build/agents-frontend/certificate-plan.json
python scripts/deploy_agents_frontend.py certificate execute --profile mastererp-admin --output build/agents-frontend
aws cloudformation wait stack-update-complete --profile mastererp-admin --region us-east-1 --stack-name mastererp-dev-agents-frontend-certificate
# Esperar ISSUED en ACM si el certificado se renovó por cambio de dominio

python scripts/deploy_agents_frontend.py hosting prepare --profile mastererp-admin --output build/agents-frontend
# Revisar build/agents-frontend/hosting-plan.json
python scripts/deploy_agents_frontend.py hosting execute --profile mastererp-admin --output build/agents-frontend
aws cloudformation wait stack-update-complete --profile mastererp-admin --region us-west-1 --stack-name mastererp-dev-agents-frontend
aws cloudformation describe-stacks --profile mastererp-admin --region us-west-1 --stack-name mastererp-dev-agents-frontend --query "Stacks[0].Outputs"
```

En **CREATE** inicial sustituir `stack-update-complete` por `stack-create-complete`. El certificado ACM debe estar **ISSUED** antes de que CloudFront acepte la asociación.

Si cambias solo el **dominio** del certificado y el stack de certificado queda en `UPDATE_COMPLETE_CLEANUP_IN_PROGRESS` con errores al borrar el certificado antiguo («Certificate … is in use»), aplica primero la **actualización del stack de hosting** con el nuevo `FrontendCertificateArn` (como arriba) para que CloudFront suelte el certificado anterior; después el stack de certificado debería completar la limpieza.

## Publicación automática (GitHub Actions)

1. Variables `AGENTS_UONIFY_BUCKET` y `AGENTS_UONIFY_DISTRIBUTION_ID` (outputs del stack de hosting).
2. Workflow **Publish agentes-dev.uonify.com**: push a `dev` o `workflow_dispatch`.

Si el certificado o el alias cambian de dominio, reaplicar certificado + hosting antes de invalidar.

## Publicación manual (alternativa)

```powershell
$BUCKET = <FrontendBucketName del output>
$DIST = <FrontendDistributionId del output>
aws s3 cp modules/2.6-agent-center/agents-static/landing.html "s3://$BUCKET/index.html" --content-type "text/html; charset=utf-8" --cache-control "no-cache,max-age=0,must-revalidate" --profile mastererp-admin --region us-west-1
aws cloudfront create-invalidation --distribution-id $DIST --paths "/ /index.html" --profile mastererp-admin
```

## Verificación

```powershell
python scripts/verify_agents_frontend.py --profile mastererp-admin --output build/agents-frontend/verification.json
```

Comprueba **https://agentes-dev.uonify.com**, TLS, redirección HTTP→HTTPS, clase `finance-app`, bloqueo S3 anónimo.

## Notas

- No modifica `app-dev.uonify.com` ni el hosting de Finanzas.
- **DEV:** `agentes-dev.uonify.com`. Producción u otro host requiere parámetros y stacks dedicados.
- Precio CloudFront: `PriceClass_100`.

## Cambio de dominio DEV a español

Se sustituye el hostname anterior por agentes-dev.uonify.com sobre los mismos stacks, bucket y distribución. El certificado se reemplaza en us-east-1 y usa UpdateReplacePolicy Retain para no bloquear su actualización mientras el certificado anterior esté asociado a CloudFront. Después se actualizan el alias y los registros A/AAAA en us-west-1; solo estos registros DNS pueden requerir reemplazo por cambio de nombre. Revisar ambos change sets. El certificado anterior se limpia únicamente cuando ya no tenga InUseBy; no se cambia identidad, API, RDS ni otra aplicación.
