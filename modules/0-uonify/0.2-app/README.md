# Aplicación Uonify

Antes de trabajar aquí, leer el README de [`modules/0-uonify`](../README.md): sus Reglas comunes y su sección «Esta capa: infrastructure» rigen también en esta carpeta. Este README solo añade lo propio de `0.2-app`.

Objetivo específico: la infraestructura AWS del DEV de Uonify en https://dev.uonify.com: el host de la API y los workers, sus imágenes y su operación, y el inventario del borde (CloudFront, puerta y bucket web), cuyo código está en platform `frontend/modules/0-uonify/0.2-app/edge`.

Responsabilidad: declarar, desplegar y operar el host y sus imágenes, y documentar el estado real de los recursos AWS del DEV, también los del borde. El código de la web, la API y los workers es de platform `0.2-app`, igual que la puerta y los scripts de publicación (`frontend/modules/0-uonify/0.2-app/edge`); las migraciones, de database `0.2-app`.
Estado: en git desde el 08-11-2026: plantilla del stack y host (PR #4, `9595886`). `edge/` (la puerta y los scripts de publicación) salió de aquí con el PR #5 (`ab8496d`, fusionado en `cb515f6`) y está en platform desde el PR #9 (`59ae0eb`), junto a las páginas legales de la puerta. Decisión del dueño (08-11-2026, `4136003`): dev.uonify.com se publica a mano con su usuario de AWS desde un clon de platform; no hay rol ni workflow de CI. Fusionar aquí no despliega nada. `resources.yml` está vacío (0 bytes) y se excluye del despliegue (`docs/FOLDER_STANDARD.md:11`), pero esta carpeta tiene recursos vivos: los declara `stack/uonify-dev-backend.yaml` (stack `uonify-dev-backend`), y lo creado a mano no está en ninguna plantilla. Es una excepción transitoria a `AGENTS.md:19`, ligada al sustrato de DEV (D6). Como con las plantillas preexistentes (`docs/FOLDER_STANDARD.md:26`), no se mueve ni se copia a `resources.yml` sin una transición revisada (change set, IMPORT y `Retain`) y sin decisión del dueño.

## Contrato y estado de esta capa

Código: 0.2. Nombre/ruta: `modules/0-uonify/0.2-app`. Propietario funcional: el dueño de Uonify, que decide todo gasto nuevo. Propietario de los datos: Uonify; su base de DEV vive en el disco de datos de la EC2 y en sus copias.

Capa: infraestructura. Dependencias: la cuenta 277352717693 y la zona `uonify.com` del equipo; platform `0.2-app` (web, API y workers y, en `frontend/modules/0-uonify/0.2-app/edge`, la puerta y su publicación) y database `0.2-app` (migraciones). Exclusiones: los recursos del equipo (hosting de app-dev, Cognito, API Gateway y RDS) y el código, la web y el SQL. APIs/eventos/MCP: ninguno; `https://dev.uonify.com/api/*` es de platform backend `0.2-app`.

Estado verificable: alta en `docs/MODULE_REGISTRY.md:9`, igual en los 3 repos. Los 44 ficheros de código (`stack/` y `host/`) son copia exacta de la copia durable de DEV del 08-11. `host/runtime/nginx.conf` (sha256 `fa56fbb53dcbb247…`) es el que se aplicó el 08-11. Lo hecho a mano aún no está declarado en ninguna plantilla del repo.

Validaciones: Reglas comunes, sección 10, más las pruebas de cada carpeta (tabla de «Estructura técnica»).

## Inventario del DEV (foto del 08-11-2026)

Según la decisión de hosting del dueño del 07-11-2026 (D-DEV-HOSTING-20261107, que las Reglas comunes recogen como D6) y la plantilla del stack. Antes de actuar, se comprueba en vivo. eu-west-1 y arm64 son la excepción D6 (ver Reglas comunes, sección 3); el bucket web y el certificado de CloudFront están en us-east-1. «(platform)» señala los scripts de platform `frontend/modules/0-uonify/0.2-app/edge/`.

| Recurso | Identificador | Región | ¿Código o hecho a mano? |
| --- | --- | --- | --- |
| Cuenta AWS | `277352717693`, compartida con el equipo | — | Del equipo |
| Stack CloudFormation | `uonify-dev-backend`, con protección contra borrado en el stack y en la EC2 | eu-west-1 | Código: `stack/` |
| EC2 | `i-0c7e4e7041a7cfc7e`: t4g.medium, arm64, Ubuntu 24.04; sin SSH ni par de claves, solo SSM; IMDSv2 | eu-west-1 | Código (stack) |
| Red y disco | VPC `10.77.0.0/16`; entrada 443 solo desde CloudFront (`pl-4fa04526`); disco de datos de 30 GiB cifrado; IP elástica (salida `ElasticIp`) | eu-west-1 | Código (stack) |
| Cifrado, copias y logs | KMS `alias/uonify-dev`; DLM diario a las 03:00 UTC con 7 copias; bucket `uonify-dev-backups-277352717693-eu-west-1`; logs `/uonify/dev/{api,workers,nginx}`, 30 días | eu-west-1 | Código (stack) |
| Servicios del host | Compose `uonify-dev`: db (Postgres 17), redis, mailpit, api, conversation-, materials-, billing- y clips-worker (perfil `armed`: armado, sin tarifa) y nginx | eu-west-1 | Código: `host/runtime/`, instalado con `host/bootstrap/` por SSM |
| CloudFront | `E4N1UCPZZ2F0`, alias `dev.uonify.com`: web desde S3 y `/api/*` (voz incluida, sin caché) hacia el origen `uonify-dev-origin` | Global | A mano, sin stack; se cambia con `deploy_edge.mjs` (platform) |
| Puerta | Funciones `uonify-dev-gate-default` y `uonify-dev-gate-api` (usuario y contraseña, cookie firmada); KVS `uonify-dev-gate`, cuyos valores solo están en el KVS | Global | Código en platform `frontend/modules/0-uonify/0.2-app/edge/`, publicado con su `deploy_edge.mjs`; los valores, el dueño |
| Cabeceras | Política `uonify-dev-security-headers`: HSTS de 1 año sin subdominios, nosniff, sin marcos y noindex | Global | Script (`deploy_edge.mjs`, platform) |
| Bucket web | `uonify-dev-web-277352717693`, con versiones | us-east-1 | A mano; el contenido, con `upload_dist.mjs` (platform) |
| Origen | `origin-dev.uonify.com`: registro A hacia la IP elástica; nginx responde 403 si falta `X-Origin-Verify` | eu-west-1 | Registro a mano, fuera del stack; nginx, código |
| ECR | `uonify-dev/api`, `uonify-dev/clips` y `uonify-dev/conv`, etiquetas inmutables. En uso, `devorigin-20261107` (digests `7e3743d0cbc9…`, `40562e4368bb…` y `1ba56906ee0d…`) | eu-west-1 | A mano (CLI) |
| SSM | Prefijo `/uonify/dev/`: `run/*` para el backend y `edge/origin-verify` para el borde; SecureString con `alias/uonify-dev` | eu-west-1 | Script (`host/secrets/upload_dev_secrets.sh`) |
| DNS | Zona compartida `uonify.com` (`Z08167243FAUSDUW0Z2KP`): `dev.uonify.com` A y AAAA hacia E4N1, `origin-dev.uonify.com` A y el TXT temporal `_acme-challenge.origin-dev` | Global | A mano; el TXT lo escribe el host al renovar |
| Certificados | ACM de `dev.uonify.com` en E4N1: su ARN se anota aquí tras comprobarlo en vivo. Let's Encrypt de `origin-dev.uonify.com` en el host: DNS-01, `certbot.timer`, vence el 05-02-2027 | us-east-1 y host | ACM, sin plantilla; Let's Encrypt, script |
| Cliente OAuth | «Uonify · DEV» de Google, en Testing; vuelta `https://dev.uonify.com/api/auth/google/callback`; su JSON solo está en SSM | Google Cloud | A mano (consola) |

Estado de la puerta: pide credenciales en la app, `/api/*`, la voz y, desde el 08-11-2026, también en «/» (`ROOT_PUBLIC = false` en `gate-default.js`); `/web/…`, `/privacidad` (sin el JS de la app) y `/api/health` responden sin ellas. Lo comprueba `deploy_edge.mjs verify` (platform), con 12 pruebas sin credenciales: el 08-11 dio 12/12.

⚠ Riesgo aceptado por el dueño el 08-11-2026: cualquier administrador de la cuenta compartida puede descifrar los secretos y las copias y abrir un shell de root por SSM. La base de DEV empezó vacía y con claves nuevas; desde el 08-11 guarda la cuenta del dueño y sus tokens de Google, cifrados con `encryption-key`. La aceptación cubre solo su cuenta: en DEV no se conectan cuentas de clientes, y cualquier otra cuenta necesita su OK.

## Estructura técnica

Carpetas sin número (ver Reglas comunes, sección 11). `images/` y `ops/` están previstas y se crearán cuando llegue su contenido.

| Carpeta | Qué hay | Pruebas |
| --- | --- | --- |
| `stack/` | `uonify-dev-backend.yaml` y su stack policy | Ninguna automática: cada cambio, por change set revisado |
| `host/runtime/` | `compose.yaml`, `compose.env.example`, `nginx.conf`, `nginx-entrypoint.sh` y `validate-local.sh` | `validate-local.sh`, solo en la estación de trabajo |
| `host/bootstrap/` | `bootstrap.sh`, `make_host_bundle.sh`, `files/` (apt, Docker, certbot y copia nocturna de PostgreSQL) y `tests/` | `tests/run_*.sh`, `tests/test_pg_backup.sh` y `python3 tests/lint_units.py` |
| `host/secrets/` | `uonify-secrets-sync.sh` y su servicio, `uonify_secrets_render.py`, `upload_dev_secrets.sh` y `tests/` | `tests/run_*.sh` y `tests/test_upload_dev_secrets.sh` |
| `images/` (prevista) | Los digests que se despliegan, que hoy solo están en `/etc/uonify/compose.env` del host | — |
| `ops/` (prevista) | Comprobaciones por SSM (paridad de imágenes, seguridad, simulacro de copia), sin sus salidas; después, alarmas y presupuesto | — |

Los `run_*.sh` y `test_pg_backup.sh` de `host/` usan contenedores desechables, sin salida a internet ni AWS, y necesitan Docker con las imágenes ya descargadas (`--pull never`): las de `TEST_IMAGE` y `TEST_IMAGES` (por defecto, `uonify-dev-*:devorigin-20261107`, las mismas de ECR) y `postgres:17-alpine`. `test_upload_dev_secrets.sh` corre con el bash 3.2 de macOS y una AWS CLI falsa.

## Lo que nunca se sube

Además de lo de las Reglas comunes (sección 8). El `.gitignore` de esta carpeta cubre estos casos, pero no sustituye a la revisión.

- ⚠ `get-distribution`, `get-distribution-config` y `list-distributions` devuelven `X-Origin-Verify` en claro. No se ejecutan a mano (como mucho, `get-distribution-config` con `--query ETag`, `deploy_edge.mjs:27-29`) ni se pegan sus salidas en PR, issues o chats; las copias de E4N1 se hacen solo con `deploy_edge.mjs backup` (platform), que deja el secreto en blanco.
- `host/bootstrap/dist/`, el paquete autoextraíble que genera `make_host_bundle.sh`.
- Salidas de verificación y de pruebas: `out-*.txt`, `validate-out.txt`, `resumen-revision.json`, `tmp/` y `.run-*/`.
- Los ficheros que lee `upload_dev_secrets.sh` (`--oauth-json`, `--local-dir` y `--extra-file`), entre ellos las listas piloto (llevan UUID de usuarios); los valores de SSM o del KVS; el `compose.env` real del host, y los objetos de la copia de la base (`.dump`, `.roles.sql` y `.manifest`).

## Publicación y CI

Decisión del dueño (08-11-2026, `4136003`): dev.uonify.com se publica a mano con su usuario de AWS desde un clon de platform (procedimiento en platform `frontend/modules/0-uonify/0.2-app/README.md`). No hay rol ni workflow de CI, y `resources.yml` sigue vacío (ver «Estado»). Si el dueño decide crear una CI:

- Sus roles se declaran en esta carpeta y no reutilizan `mastererp-dev-uonify-frontend-github-role`, que es del hosting de app-dev.
- Sus roles no pueden: leer la configuración de la distribución (`cloudfront:GetDistribution`, `GetDistributionConfig` ni `ListDistributions*`, que devuelven `X-Origin-Verify` en claro); usar el KVS `uonify-dev-gate`; cambiar, probar o publicar las funciones `uonify-dev-gate-*` (leen el KVS al ejecutarse: cambiarlas equivale a leer la clave HMAC o a abrir la puerta); usar `ssm:StartSession` ni `ssm:SendCommand` con documentos de AWS (`AWS-RunShellScript`, `AWS-RunRemoteScript`…), solo con un documento propio cerrado que acepte únicamente digests `sha256:` de `uonify-dev/*`; leer `/uonify/dev/*`, usar `kms:Decrypt` con `alias/uonify-dev` ni leer el bucket de copias.
- Atar la confianza a la rama `dev` y al workflow (`job_workflow_ref`) no basta: `dev` no tiene protección y cualquiera con push puede editar ese workflow. Lo que dé root en la EC2 o toque la puerta o la distribución sigue a mano mientras `eticayservicios` no configure un entorno con aprobación del dueño.

## Operación

- Al host solo se entra por SSM; no hay SSH. `host/runtime/` vive en `/opt/uonify/runtime`; como root: `docker compose -f /opt/uonify/runtime/compose.yaml --env-file /etc/uonify/compose.env up -d`, y para el clips-worker, además, `--profile armed`. Las imágenes se fijan siempre por digest en ese `compose.env`, nunca por etiqueta.
- ⚠ No se reinicia ni se despliega con un clip de pago en curso. Antes, se comprueba en la base que no hay filas `running` en `creative_execution_attempts` ni `reserved` en `creative_generation_attempts` (README de platform `backend/modules/0-uonify/0.2-app`).
- ⚠ Antes de desplegar, copia de la base en dos pasos, como pide el README de database `modules/0-uonify/0.2-app`: volcado a demanda por SSM (`sudo systemctl start uonify-pg-backup.service`, comprobando su `.manifest`) y snapshot del disco de datos desde fuera del host (`aws ec2 create-snapshot --volume-id <salida DataVolumeId>`), porque el rol del host no tiene permiso. El volcado nocturno (`uonify-pg-backup.timer`, 02:15 UTC) y el snapshot DLM de las 03:00 UTC no tienen alarmas: la copia programada del 08-11 falló sin avisar.
- Palancas del dueño, que nadie acciona sin su OK: la contraseña de la puerta (`set_gate_credentials.sh`, platform; la ejecuta él), abrir «/» u otra ruta de la puerta, los secretos de SSM, la tarifa del clip, las URI del cliente OAuth, restaurar la base y borrar o recrear el stack.
- Vuelta atrás. ⚠ Abrir la puerta, restaurar la base o borrar recursos solo con OK expreso del dueño. Los scripts manuales se conservan aunque llegue una CI:
  - Backend: los digests anteriores en `/etc/uonify/compose.env` y recrear los servicios. Si se aplicaron migraciones, restaurar la copia previa sustituye todo lo escrito después: solo con OK del dueño (README de database `0.2-app`).
  - Stack: otro change set con la plantilla y todos los parámetros anteriores. El «DELIBERATE DELETE» de la cabecera de la plantilla (`stack/uonify-dev-backend.yaml:33-43`) destruye el DEV y no es una vuelta atrás. La stack policy frena reemplazos y borrados en las actualizaciones, no `delete-stack`.
  - Web, puerta y distribución: con los scripts de platform `frontend/modules/0-uonify/0.2-app/edge/`, junto a su procedimiento de publicación, y siempre con «/» cerrada. ⚠ Restaurar E4N1 con una copia anterior a la puerta (paso 13, 08-11-2026) quita la puerta y `/api/*` y deja público el JavaScript de la app. `rollback` solo comprueba CallerReference y alias (`deploy_edge.mjs:600-601`), así que también aceptaría el fixture real `edge/test/fixtures/e4n1-config.json`.

## Coste aproximado

Unos 41 USD/mes, aprobados por el dueño el 07-11 (D-DEV-HOSTING-20261107). La plantilla estima unos 38 USD/mes para el stack en el primer año (EC2, discos, IPv4 pública, KMS, snapshots, logs y S3). Pasar a `t4g.large` (unos 27 USD/mes más) o a `CpuCredits=unlimited` (hasta unos 47 USD/mes más) es decisión de gasto del dueño.

## Excepción de 500 líneas: lista cerrada de esta capa

Las reglas están en las Reglas comunes, sección 3 (D3). En infraestructura la norma alcanza también a las plantillas mantenidas a mano (`docs/IMPLEMENTATION_PATTERN.md:12-13`). El resto de la carpeta tiene 472 líneas o menos.

| Fichero | Líneas | sha256 en git (inicio) |
| --- | --- | --- |
| `stack/uonify-dev-backend.yaml` | 850 | `71d34e07f131` |
| `host/bootstrap/bootstrap.sh` | 660 | `7c8d3f0b6cd6` |
| `host/secrets/upload_dev_secrets.sh` | 525 | `0f376165768e` |

`edge/test_gate.mjs` y `edge/deploy_edge.mjs` salieron de esta capa con `edge/` (PR #5, `ab8496d`) y figuran en la lista de platform `frontend/modules/0-uonify/0.2-app`.

## Pendientes

- La cabecera de `stack/uonify-dev-backend.yaml` aún dice «DRAFT, NOT DEPLOYED», aunque el stack existe desde el 07-11. Corregirla obliga a partir la plantilla sin reemplazar recursos vivos, con un diseño revisado; mientras, manda este README.
- Adoptar por IMPORT y `Retain` lo hecho a mano (E4N1, bucket web, ECR, DNS y certificado ACM), comprobando antes qué admite IMPORT y en qué región y stack va cada pieza.
- Quién revisa los change sets de Uonify (el repo pide revisión humana, `CONTRIBUTING.md:9-11`): lo decide el dueño con el arquitecto.
- Despliegue del backend desde git (imágenes construidas desde el repo y desplegadas por digest): sin CI y pendiente de decisión del dueño.
- `images/`: construir las imágenes desde git; hoy son overlays selladas por ID sobre imágenes que solo existen en el Mac.
- `ops/`: ⚠ alarmas y presupuesto, que no existen (ver «Operación»).
- Correo saliente: no hay salida SMTP (587, para SES); hoy el correo se queda en mailpit.
- Anotar el ARN del certificado ACM de `dev.uonify.com` que usa E4N1, comprobado en vivo.
- Alinear con el estándar (D6) exige otra plantilla: esta solo se despliega en la cuenta 277352717693 y en eu-west-1 (regla `OnlyUonifyAccountInIreland`).
