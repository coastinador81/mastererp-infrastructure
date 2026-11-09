# Nexus (0.3)

Hosting DEV de la página estática de Nexus en `nexus-dev.uonify.com`. El HTML/CSS/JS editable vive en Platform (`frontend/modules/0-uonify/0.3-nexus`).

## Stacks

| Stack | Región | Plantilla |
| --- | --- | --- |
| `mastererp-dev-nexus-frontend-certificate` | us-east-1 | `nexus-frontend-certificate.json` |
| `mastererp-dev-nexus-frontend` | us-west-1 | `nexus-frontend-hosting.json` |

Scripts: `scripts/deploy_nexus_frontend.py`, `scripts/verify_nexus_frontend.py`.

## Publicación

Workflow en **Platform**: `.github/workflows/publish-nexus-uonify.yml`. Variables GitHub: `NEXUS_UONIFY_BUCKET`, `NEXUS_UONIFY_DISTRIBUTION_ID`.

Ver `HOSTING.md` para detalle operativo.
