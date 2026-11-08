# Hosting frontend Centro de Agentes (agentes-dev.uonify.com)

El dominio `https://agentes-dev.uonify.com` sirve el artefacto generado desde `mastererp-platform/frontend/modules/2.6-agent-center/agents-web/index.html`. Este repositorio no contiene ni edita la interfaz; conserva exclusivamente su hosting y permisos de publicación.

## Regla obligatoria de separación

**Platform es la única fuente de código frontend.** Antes de editar HTML, CSS, JavaScript, assets o build del Centro de Agentes, los agentes deben informar al desarrollador y trabajar en `mastererp-platform/frontend/modules/2.6-agent-center/`. Infrastructure solo admite cambios de S3, CloudFront, Route 53, ACM, IAM/OIDC, variables de publicación o documentación operativa. Un cambio de infraestructura no autoriza a modificar la interfaz.

## Plantillas y stacks

| Archivo | Stack CloudFormation | Región |
| --- | --- | --- |
| `agents-frontend-certificate.json` | `mastererp-dev-agents-frontend-certificate` | **us-east-1** (ACM para CloudFront) |
| `agents-frontend-hosting.json` | `mastererp-dev-agents-frontend` | **us-west-1** (S3, CloudFront, Route53, OIDC) |

Recursos del hosting: bucket versionado y cifrado, OAC SigV4, distribución con alias **agentes-dev.uonify.com**, política de bucket restringida al ARN de la distribución, registros DNS **A** y **AAAA** en la zona `Z08167243FAUSDUW0Z2KP`, rol IAM **mastererp-dev-agents-frontend-github-role** para publicación OIDC. El trust OIDC del rol se limita a `repo:eticayservicios/mastererp-platform:ref:refs/heads/dev`; Platform es quien publica el frontend.

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

## Publicación desde Platform

El workflow de publicación vive en `mastererp-platform/.github/workflows/publish-agents-uonify.yml`. Usa las variables `AGENTS_UONIFY_BUCKET` y `AGENTS_UONIFY_DISTRIBUTION_ID` del repositorio Platform y publica el artefacto generado desde el módulo 2.6. No ejecutar publicaciones manuales desde Infrastructure ni restaurar una copia local de la interfaz.

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

## Publicación del lanzador compartido

La landing carga `/shared/module-launcher.mjs` desde su propio origen. El workflow verifica el SHA-256 del manifiesto generado, publica el JavaScript antes de index.html y luego invalida ambas rutas. El objeto usa Content-Type `text/javascript; charset=utf-8` y caché revalidable. No requiere nuevas credenciales, permisos IAM, DNS, certificados ni stacks.

En una publicación manual autorizada, subir también `modules/2.6-agent-center/agents-static/shared/module-launcher.mjs` a `s3://<bucket-existente>/shared/module-launcher.mjs` con los mismos headers e incluir `/shared/module-launcher.mjs` en la invalidación. No descargar la implementación desde otro dominio en runtime. Las próximas actualizaciones se sincronizan desde la fuente oficial de Platform y se revisan en ambos repositorios.
