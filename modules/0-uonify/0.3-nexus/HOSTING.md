# Hosting Nexus DEV

Dominio: **https://nexus-dev.uonify.com/**

## Despliegue de infraestructura

```powershell
cd mastererp-infrastructure
python scripts/deploy_nexus_frontend.py certificate prepare --profile mastererp-admin --output .cursor-deploy-plans/nexus
python scripts/deploy_nexus_frontend.py certificate execute --profile mastererp-admin --output .cursor-deploy-plans/nexus
# Esperar certificado ISSUED en ACM us-east-1
python scripts/deploy_nexus_frontend.py hosting prepare --profile mastererp-admin --output .cursor-deploy-plans/nexus
python scripts/deploy_nexus_frontend.py hosting execute --profile mastererp-admin --output .cursor-deploy-plans/nexus
```

## Verificación

```powershell
python scripts/verify_nexus_frontend.py --profile mastererp-admin --output .cursor-deploy-plans/nexus/verify.json
```

## Publicación de contenido

Desde Platform (OIDC rol `mastererp-dev-nexus-frontend-github-role`): workflow `publish-nexus-uonify.yml` empaqueta `frontend/modules/0-uonify/0.3-nexus/nexus-web/index.html` y fuentes Inter compartidas.

No publicar HTML desde este repositorio.
