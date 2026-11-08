# Uonify

Objetivo específico: Canal conversacional y de voz para consultar y coordinar operaciones con los módulos propietarios (`docs/MODULE_REGISTRY.md:7`). Por D1 (08-11-2026), `0-uonify` acoge además toda la app de Uonify de https://dev.uonify.com, en `0.2-app`.

Responsabilidad: en esta capa, los recursos AWS de Uonify y la operación de su host (stack, imágenes, secretos y copias). No incluye el código de la app ni el SQL. La web y su puerta se publican desde platform `frontend/modules/0-uonify/0.2-app/edge`, donde está su código.
Estado: la raíz guarda piezas del equipo (el hosting de app-dev), que Uonify no usa. La infraestructura de Uonify está en `0.2-app`: plantillas y scripts del DEV, en git desde el 08-11-2026 y sin despliegue automático.

## Contrato y estado de esta capa

Código: 0. Nombre/ruta: `modules/0-uonify`. Propietario funcional: el dueño de Uonify, su Product Owner. Propietario de los datos: Uonify. Esta capa aloja el disco y las copias de su base de DEV; el esquema es de database (`modules/0-uonify/0.2-app/migrations`, D4).

Capa: infraestructura. Dependencias: la cuenta AWS 277352717693 y la zona DNS `uonify.com`, compartidas con el equipo. Exclusiones: código y web (platform), SQL (database) y los recursos AWS del equipo. APIs/eventos/MCP: esta capa no declara ninguno.

Estado verificable: en dev `cb515f6` (08-11-2026), la raíz tiene `README.md`, `resources.yml` y `FRONTEND_DEPLOYMENT.md`. `0.2-app/` llegó con el PR #4 (`9595886`); su `edge/` salió de aquí con el PR #5 (`ab8496d`) y está en platform desde el PR #9 (`59ae0eb`). El detalle y su evidencia están en «Esta capa: infrastructure» y en el README de `0.2-app`.

Validaciones: las de la sección 10 de las Reglas comunes.

<!-- uonify-reglas-comunes:start -->
## Reglas comunes de Uonify (0)

Bloque idéntico, byte a byte, en los 4 README raíz de `0-uonify` (platform backend y frontend, infrastructure y database). Lo fija el dueño (propietario y Product Owner de Uonify); «el equipo» y «el arquitecto» son los de MasterERP. Dentro de `0-uonify`, las excepciones del dueño prevalecen sobre la norma del equipo que contradigan (`AGENTS.md:7` y `:32`); fuera, rige el estándar del equipo. Las rutas son relativas a la raíz de cada repo.

### 1. Dónde vive Uonify

| Capa | Repo | Carpeta |
| --- | --- | --- |
| Backend | `mastererp-platform` | `backend/modules/0-uonify` |
| Frontend | `mastererp-platform` | `frontend/modules/0-uonify` |
| Infraestructura | `mastererp-infrastructure` | `modules/0-uonify` |
| Base de datos | `mastererp-database` | `modules/0-uonify` |

`eticayservicios/uonify-front` y `eticayservicios/uonify-backend` están congelados desde el 08-11-2026: ni push, ni ramas, ni PR. Uonify se desarrolla solo en estos 3 repos.

### 2. Mapa 0.x

| Código | Carpeta | Qué contiene | Estado |
| --- | --- | --- | --- |
| 0 | `0-uonify` | Raíz: estas reglas y piezas heredadas del equipo, que se describen en la sección de cada capa | Existe en las 4 capas |
| 0.1 | `0-uonify/0.1-corporate-landing` | Reservado por el equipo (`docs/MODULE_REGISTRY.md:8`) | Sin carpeta en ninguna capa |
| 0.2 | `0-uonify/0.2-app` | La app de Uonify de dev.uonify.com: web, API, workers, voz y Estudio | Existe en las 4 capas; estado y evidencia en su README |

Áreas futuras de 0.2.x: viven hoy dentro de `0.2-app`; no se crean carpetas vacías. Cada área recibirá el siguiente número libre (0.2.1, 0.2.2…) solo cuando su código se separe, y nacerá a la vez en las 4 capas. D1 (08-11-2026): Estudio, ArtCraft, Amazon y el cobro van en 0, aunque el registro del equipo tenga `2.11-studio`, `2.3.5-product-content`, `2.3.6-marketplaces` y `1.2.x`; el encaje lo decide el dueño con el arquitecto.

| Área | Qué abarca |
| --- | --- |
| Uony | Cerebro y voz |
| Estudio | Motor de creación de vídeo y postproducción ArtCraft |
| Producto | Ficha, materiales y GPSR |
| Conexiones | Drive, Google Cloud y Amazon |
| Cuenta y cobro | Cuenta del cliente, suscripción y pagos |
| Alta | Registro y alta de clientes |
| Consola de administración | Gestión interna de Uonify |

### 3. Excepciones del propietario (08-11-2026, según `AGENTS.md:32`)

| Excepción | Alcance |
| --- | --- |
| Todo Uonify en 0 (D1) | Backend, frontend, infraestructura y base de datos de Uonify van en `0-uonify/0.2-app`, también lo que el registro del equipo sitúa en otros módulos (sección 2), frente a la propiedad por dominio de `PROJECT.md:19`. |
| Ramas y PR | Solo `dev` y `main`; `prod` la crea el arquitecto cuando decida. Cada cambio va en una rama corta con PR a `dev`, fusionado el mismo día (sección 5), en lugar de trabajar directamente en `dev` (`AGENTS.md:23`). |
| Revisión y fusión de PR | Regla del dueño: «pr que abre, pr que se fusiona con dev». Hoy no hay revisor asignado: quien abre el PR revisa su diff con la sección 10 y lo fusiona el mismo día, sin esperar a otro revisor, en lugar de «solicitar revisión» (`CONTRIBUTING.md:9`). La revisión humana que pide `CONTRIBUTING.md:11` la acuerda el dueño con el arquitecto (pendiente). |
| README como única documentación | Las reglas y el estado de cada carpeta van en su README, que se lee antes de trabajar y recibe cada regla nueva. Ningún `.md` nuevo si el dueño no lo pide; los `.md` existentes del equipo se respetan. |
| Solo dev.uonify.com | Todo lo de Uonify en DEV (web, API, OAuth, CORS y callbacks) apunta a `https://dev.uonify.com`. `app-dev.uonify.com` no se usa ni se propone para Uonify, aunque lo citen documentos del equipo (`START_HERE.md:3`). |
| 500 líneas con lista cerrada (D3) | Todo fichero nuevo o modificado tiene como máximo 500 líneas (`docs/DEVELOPMENT_STANDARD.md:5`). Por presión comercial, se exceptúa solo una lista cerrada de ficheros que ya corren en DEV y llegan como copia exacta; cada capa la publica en el README de su `0.2-app`, en su sección de excepción de 500 líneas. La lista no crece: quien toca uno de esos ficheros lo parte en ese mismo cambio y lo saca de la lista. Las migraciones ya aplicadas no se editan nunca. |
| Puerta y publicación de la web en platform | Las CloudFront Functions de la puerta de dev.uonify.com y los scripts que publican la web y la puerta viven en platform `frontend/modules/0-uonify/0.2-app/edge`, junto a la web y a las páginas legales de la puerta, frente a `AGENTS.md:53` de platform e infrastructure, que asigna a infrastructure la operación de publicación. Se publica a mano, con el usuario de AWS del dueño y desde un clon de platform en `dev`; GitHub no publica (decisión del dueño, 08-11-2026). |
| Sustrato de DEV (D6) | DEV corre en una EC2 arm64 de eu-west-1 con Docker Compose, PostgreSQL propio e inicio de sesión directo con Google; el estándar del equipo es us-west-1, Lambdas arm64 detrás de API Gateway, la RDS compartida y Cognito. Sigue vigente como excepción; alinearlo, si el dueño lo decide, será un proyecto aparte que empieza por una copia de la base de DEV. |

Otras excepciones, con su alcance escrito en otro README (D4 la decidió el CEO al aplicar la regla del dueño «database para la base de datos» y aún le falta su confirmación expresa, `AGENTS.md:32`):

- D4, solo en database: las migraciones de la base propia van en `modules/0-uonify/0.2-app/migrations`, fuera de `schema/` (README de ese `0.2-app`).
- Manual de identidad corporativa (platform `frontend/modules/0-uonify/identidad-corporativa/`): desde el 08-11-2026 es el canon de todo lo visual de Uonify y prevalece sobre `docs/UX_UI_STANDARD.md`, que sigue rigiendo las interfaces administrativas de MasterERP. La regla completa está en el `README.md` de la raíz de cada repo.

### 4. Antes de tocar nada

1. Leer este README, el de la subcarpeta que se va a tocar (por ejemplo, `0.2-app`) y, en la raíz del repo, `AGENTS.md`, `CONTRIBUTING.md`, `PROJECT.md`, `README.md`, `START_HERE.md`, `docs/FOLDER_STANDARD.md`, `docs/DEVELOPMENT_STANDARD.md` y `docs/HOW_TO_BUILD_A_MODULE.md` (`AGENTS.md:7` y `:15`). Si se toca interfaz, autenticación o hosting, además `docs/FRONTEND_ARCHITECTURE.md` (`AGENTS.md:5`) y `docs/UX_UI_STANDARD.md` (bloque UX/UI de `AGENTS.md`); en lo visual de Uonify manda el manual de identidad corporativa (sección 3).
2. Si un documento de Uonify anterior al 08-11-2026 que está fuera de estos repos (por ejemplo, las reglas del árbol local del dueño) choca con este bloque («sin commit ni push», «no hay git»…), manda este bloque.
3. Trabajar en un clon propio y comprobar rama, estado y PR abiertos sin pisar cambios ajenos: `git fetch origin && git status --short --branch && gh pr list --state open`.

### 5. Cómo se hace un cambio

1. Rama corta desde `dev` al día: `git switch dev && git pull --ff-only origin dev && git switch -c uonify/<tema>`.
2. Un cambio pequeño y de alcance único. Commit en español con prefijo `feat`, `fix`, `docs` o `chore`; por ejemplo, `git commit -m "docs(0-uonify): reglas comunes en los README"`.
3. Comprobaciones de la sección 10 y subida: `git push -u origin uonify/<tema>`.
4. PR solo si puede fusionarse hoy, y siempre contra `dev`: `gh pr create --base dev --title "…" --body "…"`. La rama por defecto del repo es `main`: sin `--base dev`, el PR iría a `main`. La descripción dice el repositorio, el módulo, el recurso afectado y si el cambio toca código, infraestructura o ambos (`AGENTS.md:55` de platform e infrastructure), qué lanza la fusión (sección 6) y qué se ha probado.
5. Justo antes de fusionar, con `git branch --show-current` en `uonify/<tema>` (nunca en `dev` ni `main`), poner la rama al día sin reescribirla y repetir las comprobaciones si `dev` trajo cambios: `git fetch origin && git merge --no-edit origin/dev && git push origin uonify/<tema>`.
6. Fusionar el mismo día, tras las comprobaciones de la sección 10, y borrar la rama, porque el borrado automático no está activo y solo puede activarlo la cuenta `eticayservicios`: `gh pr merge <n> --merge --delete-branch` y, después, `git switch dev && git pull --ff-only origin dev`.

Prohibido:
- Push directo a `dev` o `main`, y cualquier `--force` o `--force-with-lease` (`docs/DEVELOPMENT_STANDARD.md:29`: sin force salvo autorización específica).
- PR contra `main`, ramas largas, PR abiertos de un día para otro (el que no se puede fusionar hoy se cierra hoy) y tocar ramas o PR ajenos.
- Cambiar ajustes, secretos, variables, entornos o protecciones del repo: la cuenta `uonify` solo tiene rol write y eso corresponde a la cuenta `eticayservicios`.

### 6. Qué despliega cada fusión a dev

Antes del PR, comparar `git diff --name-only origin/dev...HEAD` con los `paths:` de `.github/workflows/*.yml`; cada workflow se dispara también con su propio YAML. Si se lanza algo más que «Validate structure», se dice en el PR antes de fusionar; si es un workflow del equipo, además hace falta decisión del dueño (sección 7). Después de fusionar, se confirma con `gh run list --commit "$(gh pr view <n> --json mergeCommit --jq .mergeCommit.oid)"`.

| Repo | Ruta tocada | Qué lanza la fusión en `dev` |
| --- | --- | --- |
| Los 3 | Cualquier ruta, y también cada PR | «Validate structure» (`structure.yml`): orientativo, no bloquea |
| platform | En `frontend/modules/0-uonify`, fuera de `0.2-app`: `index.html`, `src/**`, `styles/**`, `**/*.jsx`, `**/*.tsx`, `auth-config.json`, `vite.config.js`, `package*.json`, `.env.dev` y `.gitattributes`; además, `frontend/.gitattributes`, `frontend/shared/auth/*.mjs`, `frontend/app-shell/src/**` y varias `src/**` de 2.1, 2.3 y 2.10 | `publish-uonify-dev.yml`: republica la app del equipo en su hosting, no en dev.uonify.com |
| platform | En `frontend/modules/0-uonify`: `auth-config.json`, `components/Conversation.jsx` y `components/ShellIcons.tsx`; además, `frontend/app-shell/src/**` y `frontend/shared/auth/**` | También Finanzas, Ecommerce o la tienda, según el fichero (`publish-finance-dev.yml`, `publish-ecommerce-dev.yml`, `publish-storefront-dev.yml`) |
| platform | `frontend/modules/0-uonify/0.2-app/**` (web y `edge/`) | Solo «Validate structure»: `publish-uonify-dev.yml` excluye esa ruta desde `c4954c2` (PR #8; D5, aplicada el 08-11-2026) con su último patrón, `'!frontend/modules/0-uonify/0.2-app/**'` (`:36`). Quitar esa exclusión es tocar `.github/workflows` (sección 7). ⚠ Si se añade detrás otro patrón que alcance `0.2-app`, vuelve a dispararse; lo detecta el `gh run list` de esta sección |
| platform | `backend/modules/0-uonify/**`, los README de `0-uonify` y `0.2-app`, `docs/` | Solo «Validate structure» |
| infrastructure | `modules/0-uonify/**` | Solo «Validate structure» (`publish-agents-uonify.yml` vigila únicamente `modules/2.6-agent-center/agents-*`) |
| database | `schema/**`, `seeds/**`, `tests/**`, `migrations/lambda/**`, `scripts/package_migrator.py`, `.github/workflows/deploy-migrator.yml` | `apply-dev-database.yml`: redespliega el migrador y, si cambian `schema/`, `seeds/` o `tests/`, valida contra la RDS DEV, con datos reales, dentro de `BEGIN…ROLLBACK`; el `COMMIT` solo llega lanzándolo a mano con `apply_model=true` |
| database | `infrastructure/rds-dev-us-west-1.yaml` | ⚠ `deploy-dev-rds.yml` despliega la RDS compartida, que no tiene protección contra borrado. No se toca nunca |
| database | `modules/**` | Solo «Validate structure»: `modules/` no ejecuta nada (`docs/HOW_TO_BUILD_A_MODULE.md:42`) |

Ninguna fusión publica dev.uonify.com ni despliega su backend: la web se publica a mano (README de platform frontend `0.2-app`) y el backend corre por digest (README de platform backend `0.2-app`).

### 7. Lo que no se toca sin decisión del dueño

- Nada fuera de `0-uonify`: ni `frontend/app-shell`, ni `frontend/shared`, ni otros módulos, ni `.github/workflows`, ni los recursos AWS del equipo (Cognito, API Gateway, hosting y RDS).
- Dentro de `0-uonify`, las piezas heredadas del equipo (detalle en la sección de cada capa): el código de la raíz de `frontend/modules/0-uonify`, del que dependen `app-shell`, Finanzas y Ecommerce; `backend/modules/0-uonify/lambdas/`; `modules/0-uonify/resources.yml` y `FRONTEND_DEPLOYMENT.md` en infrastructure, y `modules/0-uonify/screens/` en database.
- ⚠ `infrastructure/rds-dev-us-west-1.yaml` de database no se toca nunca. Tampoco el migrador (`migrations/lambda/`) ni `schema/`, `seeds/` y `tests/`, que llegan a la RDS compartida: las migraciones de la base propia de Uonify van en database `modules/0-uonify/0.2-app/migrations` (D4), que ningún pipeline ejecuta.
- Las variables de Actions `UONIFY_DEV_BUCKET` y `UONIFY_DEV_DISTRIBUTION_ID` de platform (`publish-uonify-dev.yml:69-70`) son del equipo: nunca se pide que apunten a recursos de dev.uonify.com, ni que se amplíe el rol que asume ese workflow, `mastererp-dev-uonify-frontend-github-role`, que hoy solo puede escribir en el bucket y la distribución de app-dev (infrastructure `modules/0-uonify/resources.yml:199-236`). Con ambas cosas, la app del equipo pisaría la web aprobada.
- Los documentos del equipo en la raíz de cada repo (`AGENTS.md`, `CONTRIBUTING.md`, `PROJECT.md`, `START_HERE.md` y `README.md`) y en `docs/`. Solo hay una salvedad, que no necesita otra decisión: al crear una carpeta numerada de `0-uonify`, se añade su fila en `docs/MODULE_REGISTRY.md` (sección 11). Si el dueño decide cambiarlos, se sigue la sección 11.
- Nadie escribe al equipo desde Uonify (ni mensajes, ni issues, ni comentarios en sus PR): lo que le afecte se le pasa al dueño, que lo lleva al arquitecto.

### 8. Secretos y datos

- Los secretos del DEV de Uonify están en la cuenta AWS compartida 277352717693:
  - En SSM Parameter Store (SecureString con `alias/uonify-dev`, eu-west-1, bajo `/uonify/dev/`): los del backend (`run/*`) y el secreto de origen (`edge/origin-verify`).
  - Solo en el KeyValueStore de CloudFront `uonify-dev-gate`: el hash de la credencial de la puerta y la clave HMAC de su cookie. Los pone el dueño con `set_gate_credentials.sh` (platform `frontend/modules/0-uonify/0.2-app/edge`); nadie más los lee ni los copia.
  - En la base propia de Uonify, cifrados con `encryption-key`: los tokens de Google y Amazon de cada cliente.
- Nunca se sube: `.env` reales (solo `*.example` con valores falsos), claves, tokens, contraseñas, JSON de clientes OAuth, valores de SSM o KVS, copias reales de la configuración de CloudFront, volcados o copias de bases de datos, listas piloto u otros ficheros con UUID de usuarios, salidas de verificación con IDs, correos personales, grabaciones ni datos reales de clientes o del dueño.
- Nada valioso en el navegador: ni claves, ni precios internos, ni IDs de proveedor.
- Antes de subir código a una carpeta, se le añade su `.gitignore` (el del repo no cubre lo de Uonify). Antes de cada push, escaneo desde la raíz del repo: la lista de ficheros no puede traer `.env` reales, `.pem`, `.key` ni volcados; cada coincidencia del segundo comando se revisa y solo valen valores falsos evidentes de prueba. Las líneas añadidas con `password`, `secret` o `token` también se revisan.

  ```bash
  git diff --name-only origin/dev...HEAD
  git diff origin/dev...HEAD | grep '^+' | grep -nE '(AKIA|ASIA)[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|GOCSPX-|ya29\.|1//0[0-9A-Za-z_-]{20}|(sk|rk)_(live|test)_|whsec_|gh[pousr]_[0-9A-Za-z]{36}|github_pat_|eyJ[0-9A-Za-z_-]{20,}\.eyJ|PRIVATE KEY|HeaderValue'
  git diff origin/dev...HEAD | grep '^+' | grep -oE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' | grep -viE '@([a-z0-9-]+\.)*(example|test|invalid|localhost)$|@example\.(com|net|org)$' | sort -u
  ```

  El tercer comando lista todos los correos que no son de dominios reservados. Solo valen buzones genéricos (`hola@`, `persona@`…); una dirección o un nombre de persona real detiene el PR. Lo mismo se revisa en los mensajes de commit y en el cuerpo del PR (`git log origin/dev..HEAD --format=%B`).

### 9. Calidad, pruebas y gasto (Constitución del dueño)

- Regla 0: quien desarrolla actúa con autonomía dentro del alcance. Ninguna entrega llega al dueño sin estar hecha, probada por la UI real con evidencia y comprobada contra lo pedido.
- Frenos del dueño: desplegar a producción, y gastar fuera del pool de pruebas o con alcance nuevo.
- Pruebas reales con gasto: autorizadas dentro del pool de créditos de prueba del proyecto Google Cloud de pruebas. Se para ante una alerta o con saldo bajo.
- Incrementos pequeños, controlados y verificados antes de seguir. Sin bucles de corrección: si un arreglo no converge, se para y se investiga la causa.
- Aprobación visual previa del dueño para cualquier cambio de lo que se ve. Lo aprobado se queda vivo: no se apaga ni se sustituye sin su OK.
- Antes de diseñar o cambiar algo de Google ADK, Gemini/Live, Vertex AI, google-genai, Drive, OAuth o Google Cloud, se pide al dueño la revisión técnica Google AI (su «Consultor Google AI»); sin veredicto APROBADO no se implementa.
- Foco actual: que los agentes funcionen en todos los servicios de Uonify, y que el motor de creación de vídeo y la postproducción ArtCraft funcionen de forma profesional.

### 10. Comprobaciones de cada PR

1. `python scripts/validate_structure.py` en un clon limpio, sin `node_modules` ni builds: sin errores nuevos. Es orientativo y no se hace obligatorio (`AGENTS.md:36`).
2. `git diff --check origin/dev...HEAD` limpio, y las pruebas del área tocada que indique el README de su carpeta.
3. Límite de 500 líneas, que ninguna CI comprueba (`scripts/validate_phase5.py` no está en ningún workflow). Desde la raíz del repo, solo pueden salir ficheros de la lista cerrada añadidos como copia exacta; no cuentan los binarios ni los ficheros de bloqueo generados.

   ```bash
   git diff --name-only --diff-filter=AMR origin/dev...HEAD | while read -r f; do [ -f "$f" ] && grep -Iq . "$f" && n=$(awk 'END{print NR}' "$f") && [ "$n" -gt 500 ] && echo "$n $f"; done
   ```

4. Escaneo de secretos de la sección 8, revisado. Lo que llega como copia de DEV tiene el mismo sha256 que el original y, si el PR cambia este bloque, su sha256 coincide en los 4 README (sección 11).
5. Tras fusionar, el `gh run list` de la sección 6 muestra solo lo previsto, en verde. Si algo falla, se para y se investiga.

### 11. Numeración, nombres, idioma y documentos comunes

- «Nosotros somos 0». Los hijos van correlativos (0.1, 0.2…; dentro, 0.2.1, 0.2.2…) y no se renumeran (`docs/FOLDER_STANDARD.md:9`); el 0.1 es del equipo y lo nuestro empieza en 0.2. Carpetas en inglés y kebab-case, con el número delante (`0.2-app`); README, commits y PR en español de España.
- Cada carpeta numerada existe igual en las 4 capas, con su README (responsabilidad, estado, dependencias y propietario, `AGENTS.md:18`); en infrastructure, además, con `resources.yml`, que vacío es una reserva excluida del despliegue (`docs/FOLDER_STANDARD.md:11`). Se crea cuando el dueño la decide o cuando entra su código, y entonces nace a la vez en las 4 capas: donde aún no hay código, solo con su README (`docs/FOLDER_STANDARD.md:13`; en infrastructure, también con `resources.yml` vacío). Nunca se crea por adelantado.
- Las carpetas técnicas (`app/`, `migrations/`…) no llevan número, nunca empiezan por un dígito ni se llaman `screens`: el validador las trataría como módulos.
- Cada carpeta numerada se da de alta en `docs/MODULE_REGISTRY.md`. Ese registro y los demás documentos que son copia idéntica en los 3 repos (`PROJECT.md` y los de `docs/` con el mismo sha256 en los tres, como `FRONTEND_ARCHITECTURE.md` o `UX_UI_STANDARD.md`) se cambian primero en platform y se copian idénticos a los otros dos. Después se compara el SHA-256, y los 3 PR se fusionan el mismo día. `AGENTS.md`, `CONTRIBUTING.md`, `START_HERE.md`, el `README.md` de la raíz y el resto de `docs/` son propios de cada repo y no se copian.
- Este bloque se cambia igual, en los 4 README a la vez. Comprobación en cada uno: `awk '/uonify-reglas-comunes:[s]tart/,/uonify-reglas-comunes:[e]nd/' README.md | shasum -a 256` (o `sha256sum`).

### 12. Roadmap y estado

- El roadmap vive fuera de los repos (D7): lo lleva el dueño y se pinta en el chat en cada hito. No se sube a git.
- Cada README lleva solo reglas y el estado verificable de su carpeta: qué hay, con qué evidencia (commit, sha256 o ejecución de workflow) y qué falta, sin inflarlo (`AGENTS.md:46`). Una carpeta o un README no acreditan implementación.
<!-- uonify-reglas-comunes:end -->

## Esta capa: infrastructure

Lo propio de `mastererp-infrastructure/modules/0-uonify`. Los recursos de Uonify se declaran dentro de `0.2-app` (D1); el `resources.yml` de la raíz es del equipo.

### Qué hay en la raíz

| Ruta | Qué es | Regla |
| --- | --- | --- |
| `resources.yml` | Plantilla del hosting de app-dev del equipo: stack `mastererp-dev-uonify-hosting`, us-west-1 (`FRONTEND_DEPLOYMENT.md:3`) | No se toca (ver Reglas comunes, sección 7) |
| `FRONTEND_DEPLOYMENT.md` | Documento del equipo sobre cómo publicó su recorrido integrado en DEV | Se respeta: ni se edita ni se funde en este README |
| `0.2-app/` | Infraestructura del DEV de Uonify en dev.uonify.com: stack y host | Ver su README |

Qué declara `resources.yml`. Uonify no usa su alias `app-dev.uonify.com` ni lo propone:

| Id lógico | Recurso |
| --- | --- |
| `Bucket` | `mastererp-dev-uonify-app-277352717693-us-west-1`: privado, AES256, `Retain` |
| `OAC` | `mastererp-dev-uonify-app`: acceso firmado (SigV4) de CloudFront al bucket |
| `Distribution` | `E146MXYK3KTLSB`: alias `app-dev.uonify.com`, raíz `index.html`, sin caché, TLS 1.2 y certificado por el parámetro `CertificateArn` |
| `BucketPolicy` | Solo esa distribución lee el bucket |
| `Dns` | Registro A de `app-dev.uonify.com` en la zona compartida `Z08167243FAUSDUW0Z2KP` |
| `FrontendPublisherRole` | `mastererp-dev-uonify-frontend-github-role`: OIDC de GitHub solo para la rama `dev` de `eticayservicios/mastererp-platform`; lista, lee y sube al bucket e invalida la distribución. Lo asume `publish-uonify-dev.yml` de platform |

El equipo tiene otro stack con nombre de Uonify y sin plantilla en git: `mastererp-dev-uonify-google-connection` (us-west-1), una Lambda con rutas en el Agent API `ebn01q74hh` cuyo código se cambia con `scripts/update_uonify_artifact.py` (`docs/FINANCE_RESOURCE_MAP_DEV.md:69-76`). Es del equipo y tampoco se toca.

### Qué despliega

Nada: fusionar en `modules/0-uonify` solo lanza «Validate structure» (ver Reglas comunes, sección 6). En este repo ningún workflow aplica stacks: se aplican a mano, con change set (`README.md:29`, `FRONTEND_DEPLOYMENT.md:5`).

### Reglas de infraestructura

- Todo cambio en AWS se ve antes de aplicarse: change set en lo que gestiona CloudFormation y ensayo sin `--apply` en los scripts (`upload_dev_secrets.sh`, en esta capa; `deploy_edge.mjs plan` y `upload_dist.mjs`, en platform `frontend/modules/0-uonify/0.2-app/edge`). Se revisa qué modifica, reemplaza o borra, y solo después se ejecuta.
- Reemplazar o borrar un recurso con estado (la EC2, el disco, la clave, las copias, la IP o la red) necesita el OK del dueño. Cada actualización de un stack pasa todos los parámetros: uno omitido vuelve a su valor por defecto.
- Lo vivo hecho a mano se adopta con IMPORT y `DeletionPolicy: Retain`, en un change set propio. Nunca se crea un stack nuevo sobre nombres existentes (`docs/RESOURCE_OWNERSHIP.md:13`).
- Los nombres físicos vivos (`uonify-dev-*`) se conservan: renombrarlos a `mastererp-*` sería crear recursos nuevos y migrar (`docs/DEVELOPMENT_STANDARD.md:44`).
- Publicar o desplegar desde GitHub, solo con roles OIDC propios de Uonify, atados a la rama `dev` y limitados a sus recursos; nunca con claves AWS fijas ni tokens personales. Hoy no hay CI (ver «Publicación y CI» en `0.2-app`).
- Aquí no van HTML, CSS, JS, assets ni builds de la web (`AGENTS.md:53`). Por decisión del dueño (08-11-2026), dev.uonify.com se publica a mano desde un clon de platform, y la puerta (CloudFront Functions), sus páginas legales y los scripts de publicación están junto a la web, en platform `frontend/modules/0-uonify/0.2-app/edge` (PR #9). Es una excepción a `AGENTS.md:53`, que atribuye a Infrastructure la operación de publicación; su alcance es solo esa carpeta (`AGENTS.md:32`). Esta capa conserva los recursos AWS y su inventario: distribución, KVS, bucket web, certificados y DNS.
- La zona `uonify.com` es compartida: solo se tocan los registros de Uonify (`dev`, `origin-dev` y el TXT `_acme-challenge.origin-dev`), nunca los CNAME de validación de ACM, y ningún cambio de DNS llega como efecto de otra tarea (`AGENTS.md:22`).
