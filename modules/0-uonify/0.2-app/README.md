# Aplicación Uonify

Objetivo específico: infraestructura del DEV de la aplicación de Uonify, que se sirve en https://dev.uonify.com.

Responsabilidad: host de la API y los workers, borde de CloudFront con su puerta de acceso, imágenes y operación del DEV de Uonify.
Estado: plantillas y scripts copiados tal cual de lo que se usó para montar el DEV que corre hoy (08-11-2026). Fusionar en esta carpeta no despliega nada. `resources.yml` está vacío: es una reserva y no se despliega.

Antes de trabajar aquí, lee el README de [0-uonify](../README.md).

## Contrato y estado de esta capa

Código: 0.2. Nombre/ruta: `0-uonify/0.2-app`. Propietario funcional: Uonify; las decisiones (y todo gasto nuevo) las toma el Product Owner de Uonify. Capa: infraestructura. Dependencias: cuenta AWS 277352717693 y zona DNS de uonify.com. Exclusiones: recursos del equipo MasterERP; el hosting antiguo del equipo está en el `resources.yml` de la raíz de 0-uonify y no se toca.

## Qué hay

| Carpeta | Contenido |
| --- | --- |
| `stack/` | Plantilla CloudFormation `uonify-dev-backend` (eu-west-1) y su stack policy. Crea el host de DEV. |
| `host/runtime/` | `compose.yaml` (PostgreSQL, Redis, Mailpit, api, conversation-worker, materials-worker, billing-worker, clips-worker y nginx), `compose.env.example`, nginx y validación local. |
| `host/bootstrap/` | Arranque del host, copias nocturnas de PostgreSQL, certificados del origen y sus pruebas con AWS simulado. |
| `host/secrets/` | Volcado de Parameter Store (`/uonify/dev/*`) al host y su subida, con pruebas sobre valores ficticios. |
| `edge/` | Puerta de dev.uonify.com (CloudFront Functions `gate-default` y `gate-api`, con credenciales en el KVS y nunca en el código), publicación del borde y de la web, y sus pruebas. |

DEV hoy: EC2 arm64 en eu-west-1 con Docker Compose y PostgreSQL propio, detrás de CloudFront (`/api` va al origen `origin-dev.uonify.com`). Es una excepción del Product Owner frente al estándar del equipo (us-west-1, x86, RDS compartida y Cognito); alinearlo será un proyecto aparte. Además del stack, el DEV tiene piezas creadas fuera de él (CloudFront, el bucket de la web, el KVS, ECR y DNS) que se adoptarán por IMPORT, una a una.

## Reglas de esta carpeta

- Nunca se suben copias reales de la configuración de CloudFront (llevan el secreto de origen), `host/bootstrap/dist/`, salidas de verificación, listas de usuarios ni valores de Parameter Store o del KVS. El `.gitignore` de esta carpeta los excluye.
- `deploy_edge.mjs backup` guarda copias en `edge/backups/`, que está ignorada; para guardarlas fuera del repo, usa `--out`.
- `edge/test_gate.mjs` difiere del original en una línea: el usuario fijo de la prueba local es ficticio.
- Los cambios en AWS se hacen con change sets revisados, nunca con stacks nuevos sobre nombres existentes. Lo que está vivo se adopta por IMPORT con `Retain`.
- No se despliega ni se reinicia el host con un clip de pago en curso. Antes de desplegar, se hace una copia de la base.
- Esta carpeta no contiene HTML, CSS, JS ni assets de la web (AGENTS.md del repo): las páginas públicas de la puerta irán a `mastererp-platform/frontend/modules/0-uonify/0.2-app`.
- Límite de 500 líneas: la excepción del Product Owner (08-11-2026) cubre solo estos 5 ficheros, que ya estaban en uso. Si se toca uno, se parte en ese mismo cambio: `edge/test_gate.mjs` (939), `stack/uonify-dev-backend.yaml` (850), `edge/deploy_edge.mjs` (793), `host/bootstrap/bootstrap.sh` (660) y `host/secrets/upload_dev_secrets.sh` (525).
- La cabecera de `stack/uonify-dev-backend.yaml` dice «DRAFT, NOT DEPLOYED», pero el stack está desplegado y en uso.
