#!/usr/bin/env bash
# =====================================================================================================
# Uonify DEV · upload_dev_secrets.sh  (D-DEV-HOSTING-20261107)
#
# Lo ejecuta el DUEÑO en su Mac, con su sesión de AWS (aws login o --profile). Compatible con el bash
# 3.2 de macOS. Necesita la AWS CLI v2 y python3. Por defecto es un ENSAYO: no escribe nada.
#
# Sube a SSM Parameter Store, como SecureString cifrado con alias/uonify-dev (cuenta 277352717693,
# eu-west-1), EXACTAMENTE estos ficheros de /run/uonify:
#   /uonify/dev/run/google-oauth.json            JSON del cliente OAuth NUEVO de DEV (--oauth-json RUTA)
#   /uonify/dev/run/stripe-test-key              copiado de platform/backend/.local
#   /uonify/dev/run/stripe-test-publishable-key  copiado de platform/backend/.local
#   /uonify/dev/run/stripe-test-vat21            marcador: SSM no admite valores vacíos; el host vuelve
#                                                a crear el fichero vacío (el backend solo mira que exista)
#   /uonify/dev/run/encryption-key               clave Fernet NUEVA, generada en memoria (BD vacía)
#   /uonify/dev/run/postgres-password            contraseña NUEVA de Postgres, generada en memoria
# Por decisión NO se suben jev-api-key, amazon-* ni semantic-model-pilot.json, y las listas piloto
# empiezan ausentes (se añaden tras tu primer login, con tu UUID nuevo, usando --extra-file).
#
# Opcional:
#   --with-edge-secret        genera /uonify/dev/edge/origin-verify (cabecera secreta CloudFront -> nginx)
#   --extra-file NOMBRE=RUTA  otro fichero de /run/uonify (listas piloto, tarifa del clip). Repetible.
#
# Comprobaciones de los orígenes (sin mostrar valores):
#   - google-oauth.json debe ser un cliente NUEVO: si su client_id es el de <local-dir>/google-oauth.json
#     (el del entorno local) se rechaza siempre, también con --skip-oauth-uri-check; y se rechaza si
#     todas sus URI de vuelta son locales. Del fichero local solo se lee web.client_id.
#   - Las listas piloto (--extra-file *-pilot-users.json, live-*-users.json) deben cumplir las reglas de
#     pilot_users() de app/settings.py; si no, la API y los workers no arrancarían.
#
# Garantías:
#   - Ningún valor secreto se imprime, se registra ni aparece en la línea de órdenes: python3 lo lee
#     (o lo genera con el módulo secrets) y escribe el documento de put-parameter en un fichero 0600
#     dentro de una carpeta temporal privada (0700); `aws ssm put-parameter --cli-input-json file://…`
#     lo lee y el fichero se borra en cuanto la AWS CLI responde (el trap borra la carpeta siempre).
#     No va por una tubería porque la AWS CLI 2.36 no lee --cli-input-json desde /dev/stdin ni
#     /dev/fd/0 («Invalid JSON received») y con un FIFO se queda colgada (comprobado el 08-11-2026).
#   - Solo muestra nombres de parámetros y versiones.
#   - No sobrescribe un parámetro existente sin --force. Las claves generadas (encryption-key,
#     postgres-password, edge) solo se regeneran con --force Y nombrándolas en --only: regenerarlas
#     en un DEV con datos rompe el descifrado de la BD o el acceso a Postgres.
#
# Ejemplos:
#   ./upload_dev_secrets.sh --oauth-json ~/Downloads/client_secret_dev.json            # ensayo
#   ./upload_dev_secrets.sh --oauth-json ~/Downloads/client_secret_dev.json --apply    # escribe
#   ./upload_dev_secrets.sh --extra-file adk-pilot-users.json=/ruta/adk.json --apply   # tras 1er login
# =====================================================================================================
set -euo pipefail
umask 077

readonly REGION=eu-west-1
readonly ACCOUNT=277352717693
readonly KMS_ALIAS=alias/uonify-dev
readonly RUN_PREFIX=/uonify/dev/run
readonly EDGE_PARAM=/uonify/dev/edge/origin-verify
readonly EMPTY_MARKER=__UONIFY_EMPTY_FILE__
readonly DEV_CALLBACK=https://dev.uonify.com/api/auth/google/callback

case $- in *x*) echo "ERROR: xtrace (set -x) activo; desactívalo: podría mostrar valores." >&2; exit 2 ;; esac

OAUTH_JSON=""
LOCAL_DIR="${HOME}/Documents/Gitlab/uonify/platform/backend/.local"
APPLY=0
FORCE=0
ONLY=""
WITH_EDGE=0
SKIP_URI_CHECK=0
ALLOW_EXCLUDED=0
ASSUME_YES=0
N_EXTRA=0
EXTRA_NAMES=()
EXTRA_PATHS=()

usage() {
  cat <<'EOF'
Uso: upload_dev_secrets.sh [opciones]
  --oauth-json RUTA        JSON del cliente OAuth NUEVO de DEV (obligatorio si hay que crear o
                           sobrescribir google-oauth.json)
  --local-dir RUTA         carpeta con stripe-test-key y stripe-test-publishable-key
                           (por defecto ~/Documents/Gitlab/uonify/platform/backend/.local)
  --profile PERFIL         perfil de la AWS CLI (si no, el de tu sesión actual)
  --apply                  escribir de verdad (sin esto solo es un ensayo)
  --force                  sobrescribir parámetros existentes
  --only a,b,c             limitar los ficheros estándar: google-oauth.json, stripe-test-key,
                           stripe-test-publishable-key, stripe-test-vat21, encryption-key,
                           postgres-password, edge
  --with-edge-secret       generar también /uonify/dev/edge/origin-verify
  --extra-file NOMBRE=RUTA otro fichero de /run/uonify (repetible); se procesa siempre
  --allow-excluded         permitir en --extra-file jev-api-key, amazon-* o semantic-model-pilot.json
                           (excluidos de DEV por decisión; solo si el dueño lo decide)
  --skip-oauth-uri-check   no exigir que el JSON liste la URI de vuelta de DEV (solo si la añadiste en
                           la consola después de descargarlo). Nunca salta la comparación con el
                           cliente local ni el rechazo de un JSON con todas las URI locales.
  --yes                    no pedir confirmación al escribir
  -h, --help               esta ayuda
EOF
}

die() { echo "ERROR: $*" >&2; exit 1; }
note() { echo "  · $*"; }

while [ $# -gt 0 ]; do
  case $1 in
    --oauth-json) [ $# -ge 2 ] || die "--oauth-json necesita una ruta"; OAUTH_JSON=$2; shift 2 ;;
    --local-dir) [ $# -ge 2 ] || die "--local-dir necesita una ruta"; LOCAL_DIR=$2; shift 2 ;;
    --profile) [ $# -ge 2 ] || die "--profile necesita un nombre"; export AWS_PROFILE=$2; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --force) FORCE=1; shift ;;
    --only) [ $# -ge 2 ] || die "--only necesita una lista"; ONLY=$2; shift 2 ;;
    --with-edge-secret) WITH_EDGE=1; shift ;;
    --extra-file)
      [ $# -ge 2 ] || die "--extra-file necesita NOMBRE=RUTA"
      case $2 in *=*) ;; *) die "--extra-file necesita NOMBRE=RUTA" ;; esac
      EXTRA_NAMES[$N_EXTRA]=${2%%=*}
      EXTRA_PATHS[$N_EXTRA]=${2#*=}
      N_EXTRA=$((N_EXTRA + 1))
      shift 2 ;;
    --allow-excluded) ALLOW_EXCLUDED=1; shift ;;
    --skip-oauth-uri-check) SKIP_URI_CHECK=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "opción desconocida: $1" ;;
  esac
done

export AWS_PAGER="" AWS_CLI_AUTO_PROMPT=off AWS_REGION=$REGION AWS_DEFAULT_REGION=$REGION

TMPD=$(mktemp -d "${TMPDIR:-/tmp}/uonify-upload.XXXXXX")
trap 'rm -rf "$TMPD"' EXIT INT TERM HUP
chmod 700 "$TMPD"

# ---------------------------------------------------------------------------------------- python
# Valida un fichero de origen SIN mostrar su contenido.
# Argumentos: tipo nombre ruta saltar_uri google-oauth.json_local
VALIDATE_PY='
import json, os, re, sys, uuid
from urllib.parse import urlsplit
kind, name, path, skip_uri, local_oauth = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1", sys.argv[5]
callback = "https://dev.uonify.com/api/auth/google/callback"
# Las listas piloto que lee pilot_users() de app/settings.py (igual en api, clips y conv). Una lista que
# no cumpla sus reglas hace que la API y los workers NO arranquen (RuntimeError en load_settings).
PILOT_LISTS = {"adk-pilot-users.json", "material-adk-pilot-users.json", "live-pilot-users.json",
               "live-adk-users.json", "live-gateway-users.json", "creative-execution-pilot-users.json",
               "creative-provider-dispatch-pilot-users.json", "creative-upload-pilot-users.json"}
def fail(msg):
    print("    ERROR " + name + ": " + msg); sys.exit(1)
def warn(msg):
    print("    AVISO " + name + ": " + msg)
def is_local(uri):
    try:
        host = (urlsplit(uri).hostname or "").lower()
    except ValueError:
        return False
    return host in ("127.0.0.1", "localhost", "::1") or host.endswith(".localhost")
def pilot_problem(text, live):
    # Mismas reglas que pilot_users(): objeto con EXACTAMENTE userIds (y sessionLimit en
    # live-pilot-users.json), userIds lista de UUID en texto sin repetir (tras normalizar),
    # sessionLimit entero 1..200. El tamaño (<= 4096 bytes) ya se comprobó.
    try:
        data = json.loads(text)
    except ValueError:
        return "no es JSON válido (UTF-8 sin BOM)"
    expected = {"userIds", "sessionLimit"} if live else {"userIds"}
    if not isinstance(data, dict) or set(data) != expected:
        return "debe ser un objeto JSON con exactamente las claves " + " y ".join(sorted(expected, reverse=True))
    if not isinstance(data["userIds"], list):
        return "userIds debe ser una lista"
    seen = set()
    for position, value in enumerate(data["userIds"], 1):
        try:
            if not isinstance(value, str):
                raise ValueError
            normalized = str(uuid.UUID(value))
        except ValueError:
            return "el id n.º " + str(position) + " de userIds no es un UUID en texto"
        if normalized in seen:
            return "userIds tiene ids repetidos"
        seen.add(normalized)
    if live and (type(data["sessionLimit"]) is not int or not 1 <= data["sessionLimit"] <= 200):
        return "sessionLimit debe ser un entero entre 1 y 200"
    return None
try:
    info = os.stat(path)
except OSError:
    fail("no existe o no se puede leer: " + path)
if not os.path.isfile(path): fail("no es un fichero normal: " + path)
if info.st_size == 0: fail("está vacío")
if info.st_size > 4096: fail("ocupa más de 4096 bytes (límite del nivel Standard de SSM)")
with open(path, "rb") as handle:
    raw = handle.read()
try:
    text = raw.decode("utf-8")
except UnicodeDecodeError:
    fail("no es texto UTF-8")
value = text.strip()
if kind == "oauth":
    try:
        data = json.loads(text)
    except ValueError:
        fail("no es JSON válido")
    web = data.get("web") if isinstance(data, dict) else None
    if not isinstance(web, dict): fail("no es un cliente OAuth de tipo Aplicación web (falta la clave web)")
    cid, sec = web.get("client_id"), web.get("client_secret")
    if not (isinstance(cid, str) and re.fullmatch(r"[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com", cid)):
        fail("client_id con formato inesperado")
    if not (isinstance(sec, str) and len(sec) >= 10): fail("falta client_secret")
    # DEV usa un cliente OAuth NUEVO: nunca el client_id del entorno local, se salte o no la comprobación
    # de la URI. Del fichero local solo se lee web.client_id, que no se muestra.
    if os.path.lexists(local_oauth):
        local_id = None
        try:
            with open(local_oauth, "rb") as handle:
                local_raw = handle.read(65537)
            if len(local_raw) <= 65536:
                local_web = json.loads(local_raw.decode("utf-8")).get("web")
                if isinstance(local_web, dict) and isinstance(local_web.get("client_id"), str):
                    local_id = local_web["client_id"]
        except (OSError, ValueError, AttributeError):
            local_id = None
        if not local_id:
            fail("no puedo leer el client_id de " + local_oauth + " para comprobar que el de DEV es un cliente NUEVO")
        if local_id == cid:
            fail("es el MISMO cliente OAuth que el del entorno local (mismo client_id que " + local_oauth + "): DEV necesita un cliente NUEVO; no se sube el client_secret del local")
    else:
        warn("no existe " + local_oauth + ": no puedo comparar el client_id con el del entorno local (revisa --local-dir)")
    uris = [u for u in (web.get("redirect_uris") or []) if isinstance(u, str)]
    origins = [u for u in (web.get("javascript_origins") or []) if isinstance(u, str)]
    if uris and all(is_local(u) for u in uris):
        fail("todas sus URI de vuelta son locales (127.0.0.1/localhost): es un cliente del entorno local, no el NUEVO de DEV")
    if callback not in uris:
        if skip_uri: warn("redirect_uris no incluye " + callback + " (comprobación saltada: añádela en la consola de Google)")
        else: fail("redirect_uris no incluye " + callback + ": ¿es el JSON del cliente NUEVO de DEV? (--skip-oauth-uri-check si añadiste la URI después de descargarlo)")
    if any(is_local(u) for u in uris + origins):
        warn("incluye URIs locales además de las de DEV: confirma que es el cliente NUEVO de DEV")
    if "https://dev.uonify.com" not in origins:
        warn("javascript_origins no incluye https://dev.uonify.com")
elif kind == "stripe-secret":
    if not (value.startswith(("sk_test_", "rk_test_")) and re.fullmatch(r"[A-Za-z0-9_]{16,512}", value)):
        fail("se esperaba una clave de PRUEBAS de Stripe (sk_test_ o rk_test_)")
elif kind == "stripe-publishable":
    if not re.fullmatch(r"pk_test_[A-Za-z0-9]{16,240}", value):
        fail("se esperaba una clave publicable de PRUEBAS de Stripe (pk_test_)")
elif kind == "extra":
    if name in PILOT_LISTS:
        problem = pilot_problem(text, name == "live-pilot-users.json")
        if problem:
            fail("lista piloto que la API y los workers rechazarían al arrancar: " + problem)
    elif name.endswith(".json"):
        try:
            json.loads(text)
        except ValueError:
            fail("no es JSON válido")
print("    OK    " + name)
'

# Genera el documento --cli-input-json de put-parameter y lo escribe en stdout (una tubería hacia aws).
# Argumentos: modo nombre_parametro ruta sobrescribir clave_kms
BUILD_PY='
import base64, json, secrets, sys
mode, name, path, overwrite, kms = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1", sys.argv[5]
if mode in ("file", "extra"):
    with open(path, "rb") as handle:
        raw = handle.read(4097)
    if not raw or len(raw) > 4096:
        sys.exit("tamaño no válido en el origen")
    value = raw.decode("utf-8")
elif mode == "marker":
    value = "__UONIFY_EMPTY_FILE__"
elif mode == "fernet":
    value = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
elif mode == "hex32":
    value = secrets.token_hex(32)
elif mode == "edge":
    value = secrets.token_urlsafe(48)
else:
    sys.exit("modo desconocido")
if name.startswith("/uonify/dev/run/"):
    description = "Uonify DEV: /run/uonify/" + name.rsplit("/", 1)[1] + " (upload_dev_secrets.sh)"
else:
    description = "Uonify DEV: CloudFront origin header secret for nginx (upload_dev_secrets.sh)"
doc = {"Name": name, "Description": description, "Value": value, "Type": "SecureString",
       "KeyId": kms, "Overwrite": overwrite, "Tier": "Standard", "DataType": "text"}
if not overwrite:
    doc["Tags"] = [{"Key": "Project", "Value": "uonify"}, {"Key": "Env", "Value": "dev"},
                   {"Key": "ManagedBy", "Value": "upload_dev_secrets"}]
sys.stdout.write(json.dumps(doc))
'

# --------------------------------------------------------------------------------------- comprobaciones
command -v aws >/dev/null 2>&1 || die "no encuentro la AWS CLI (aws)"
command -v python3 >/dev/null 2>&1 || die "no encuentro python3"
case $(aws --version 2>&1) in aws-cli/2.*) ;; *) die "hace falta la AWS CLI v2" ;; esac
# Con cli_history activado la AWS CLI guarda en disco (~/.aws/cli/history) el cuerpo de cada petición,
# es decir, los valores secretos. No se sigue.
case $(aws configure get cli_history 2>/dev/null || true) in
  enabled) die "cli_history está activado en tu perfil de la AWS CLI: guardaría los valores en disco. Desactívalo (aws configure set cli_history disabled) y repite." ;;
esac

echo "Uonify DEV · carga de secretos en SSM ($([ $APPLY = 1 ] && echo 'MODO ESCRITURA' || echo 'ENSAYO, no escribe nada'))"
echo
echo "1) Cuenta, región y clave"
if ! account=$(aws sts get-caller-identity --query Account --output text 2>"$TMPD/sts.err"); then
  cat "$TMPD/sts.err" >&2
  die "no hay sesión de AWS válida (ejecuta aws login o pasa --profile)"
fi
[ "$account" = "$ACCOUNT" ] || die "la sesión es de la cuenta $account, no de $ACCOUNT: no sigo"
note "cuenta $ACCOUNT, región $REGION"
if ! key_state=$(aws kms describe-key --key-id "$KMS_ALIAS" --query 'KeyMetadata.KeyState' --output text 2>"$TMPD/kms.err"); then
  cat "$TMPD/kms.err" >&2
  die "no existe $KMS_ALIAS en $REGION: crea antes el stack uonify-dev-backend"
fi
[ "$key_state" = "Enabled" ] || die "$KMS_ALIAS está en estado $key_state"
note "clave $KMS_ALIAS: Enabled"

if ! EXISTING=$(aws ssm describe-parameters --parameter-filters "Key=Path,Option=Recursive,Values=/uonify/dev" \
    --query 'Parameters[].[Name,Version,Type]' --output text 2>"$TMPD/describe.err"); then
  cat "$TMPD/describe.err" >&2
  die "no puedo listar los parámetros de /uonify/dev"
fi
existing_version() { printf '%s\n' "$EXISTING" | awk -F'\t' -v n="$1" '$1 == n { print $2; exit }'; }

# --------------------------------------------------------------------------------------------- plan
N_ITEMS=0
ITEM_KEYS=(); ITEM_PARAMS=(); ITEM_MODES=(); ITEM_SRCS=(); ITEM_KINDS=(); ITEM_ACTIONS=(); ITEM_VERSIONS=()
add_item() {
  ITEM_KEYS[$N_ITEMS]=$1; ITEM_PARAMS[$N_ITEMS]=$2; ITEM_MODES[$N_ITEMS]=$3
  ITEM_SRCS[$N_ITEMS]=$4; ITEM_KINDS[$N_ITEMS]=$5
  N_ITEMS=$((N_ITEMS + 1))
}
wanted() { [ -z "$ONLY" ] && return 0; case ",$ONLY," in *",$1,"*) return 0 ;; esac; return 1; }

if [ -n "$ONLY" ]; then
  for k in $(printf '%s' "$ONLY" | tr ',' ' '); do
    case $k in
      google-oauth.json|stripe-test-key|stripe-test-publishable-key|stripe-test-vat21|encryption-key|postgres-password|edge) ;;
      *) die "--only: nombre desconocido «$k»" ;;
    esac
  done
fi

wanted google-oauth.json && add_item google-oauth.json "$RUN_PREFIX/google-oauth.json" file "${OAUTH_JSON:--}" oauth
wanted stripe-test-key && add_item stripe-test-key "$RUN_PREFIX/stripe-test-key" file "$LOCAL_DIR/stripe-test-key" stripe-secret
wanted stripe-test-publishable-key && add_item stripe-test-publishable-key "$RUN_PREFIX/stripe-test-publishable-key" file "$LOCAL_DIR/stripe-test-publishable-key" stripe-publishable
wanted stripe-test-vat21 && add_item stripe-test-vat21 "$RUN_PREFIX/stripe-test-vat21" marker - marker
wanted encryption-key && add_item encryption-key "$RUN_PREFIX/encryption-key" fernet - generated
wanted postgres-password && add_item postgres-password "$RUN_PREFIX/postgres-password" hex32 - generated
if [ $WITH_EDGE = 1 ] && wanted edge; then
  add_item edge "$EDGE_PARAM" edge - generated
fi

i=0
while [ $i -lt $N_EXTRA ]; do
  name=${EXTRA_NAMES[$i]}
  printf '%s' "$name" | grep -Eq '^[a-z0-9][a-z0-9._-]{0,99}$' || die "--extra-file: nombre no válido «$name»"
  case $name in *..*) die "--extra-file: nombre no válido «$name»" ;; esac
  case $name in
    google-oauth.json|stripe-test-key|stripe-test-publishable-key|stripe-test-vat21|encryption-key|postgres-password|pgpass)
      die "--extra-file: $name tiene su propio flujo en este script" ;;
    jev-api-key|amazon-*|semantic-model-pilot.json)
      [ $ALLOW_EXCLUDED = 1 ] || die "--extra-file: $name está excluido de DEV por decisión (--allow-excluded solo si el dueño lo decide)" ;;
  esac
  add_item "$name" "$RUN_PREFIX/$name" extra "${EXTRA_PATHS[$i]}" extra
  i=$((i + 1))
done
[ $N_ITEMS -gt 0 ] || die "no hay nada que hacer"

i=0
while [ $i -lt $N_ITEMS ]; do
  version=$(existing_version "${ITEM_PARAMS[$i]}")
  ITEM_VERSIONS[$i]=$version
  if [ -z "$version" ]; then
    ITEM_ACTIONS[$i]=crear
  elif [ "${ITEM_KINDS[$i]}" = generated ]; then
    if [ $FORCE = 1 ] && [ -n "$ONLY" ] && wanted "${ITEM_KEYS[$i]}"; then
      ITEM_ACTIONS[$i]=regenerar
    else
      ITEM_ACTIONS[$i]=mantener
    fi
  elif [ $FORCE = 1 ]; then
    ITEM_ACTIONS[$i]=sobrescribir
  else
    ITEM_ACTIONS[$i]=omitir
  fi
  i=$((i + 1))
done

echo
echo "2) Plan"
printf '  %-14s %-47s %s\n' "ACCIÓN" "PARÁMETRO" "ORIGEN"   # Ó y Á ocupan 2 bytes
i=0
while [ $i -lt $N_ITEMS ]; do
  case ${ITEM_MODES[$i]} in
    file|extra) origin="fichero ${ITEM_SRCS[$i]}" ;;
    marker) origin="marcador de fichero vacío" ;;
    fernet) origin="clave Fernet nueva generada en memoria" ;;
    hex32) origin="contraseña nueva generada en memoria (256 bits)" ;;
    edge) origin="secreto de borde nuevo generado en memoria" ;;
  esac
  shown=${ITEM_PARAMS[$i]}
  if [ -n "${ITEM_VERSIONS[$i]}" ]; then shown="$shown (v${ITEM_VERSIONS[$i]})"; fi
  printf '  %-13s %-46s %s\n' "${ITEM_ACTIONS[$i]}" "$shown" "$origin"
  i=$((i + 1))
done
if [ $FORCE = 1 ]; then
  case ",$ONLY," in *,encryption-key,*|*,postgres-password,*)
    echo "  AVISO: regenerar encryption-key o postgres-password en un DEV con datos rompe el descifrado de la BD o el acceso de la API a Postgres." ;;
  esac
fi

echo
echo "3) Validación de orígenes (no se muestra ningún valor)"
problems=0
i=0
while [ $i -lt $N_ITEMS ]; do
  case ${ITEM_ACTIONS[$i]} in crear|sobrescribir)
    case ${ITEM_MODES[$i]} in file|extra)
      if [ "${ITEM_SRCS[$i]}" = "-" ]; then
        echo "    ERROR ${ITEM_KEYS[$i]}: falta --oauth-json con el JSON del cliente OAuth NUEVO de DEV"
        problems=1
      elif ! python3 -I -c "$VALIDATE_PY" "${ITEM_KINDS[$i]}" "${ITEM_KEYS[$i]}" "${ITEM_SRCS[$i]}" \
          "$SKIP_URI_CHECK" "$LOCAL_DIR/google-oauth.json"; then
        problems=1
      fi ;;
    esac ;;
  esac
  i=$((i + 1))
done
if [ -f "$LOCAL_DIR/stripe-test-vat21" ]; then
  if [ -s "$LOCAL_DIR/stripe-test-vat21" ]; then
    note "stripe-test-vat21 local no está vacío; en DEV será un fichero vacío (el backend solo comprueba que exista)"
  fi
else
  note "stripe-test-vat21 no existe en $LOCAL_DIR; en DEV existirá vacío (Stripe de pruebas activo, como en local)"
fi
for excluded in jev-api-key amazon-config.json amazon-client-secret semantic-model-pilot.json; do
  if [ -n "$(existing_version "$RUN_PREFIX/$excluded")" ]; then
    note "AVISO: existe $RUN_PREFIX/$excluded, excluido de DEV por decisión (no lo borro)"
  fi
done
[ $problems = 0 ] || die "corrige los orígenes marcados con ERROR; no se ha escrito nada"

if [ $APPLY != 1 ]; then
  echo
  echo "ENSAYO terminado: no se ha escrito nada. Repite con --apply para escribir."
  exit 0
fi

pending=0
i=0
while [ $i -lt $N_ITEMS ]; do
  case ${ITEM_ACTIONS[$i]} in crear|sobrescribir|regenerar) pending=$((pending + 1)) ;; esac
  i=$((i + 1))
done
if [ $pending = 0 ]; then
  echo
  echo "Nada que escribir (todo existe; usa --force para sobrescribir)."
  exit 0
fi
if [ $ASSUME_YES != 1 ]; then
  [ -t 0 ] || die "sin terminal para confirmar: añade --yes"
  printf '\n¿Escribir %s parámetro(s) en SSM de la cuenta %s? Escribe «si» para continuar: ' "$pending" "$ACCOUNT"
  read -r answer
  case $answer in si|sí|SI|SÍ|Si|Sí) ;; *) die "cancelado; no se ha escrito nada" ;; esac
fi

# --------------------------------------------------------------------------------------------- escritura
# El documento (con el valor) vive en un fichero 0600 de $TMPD (0700) solo mientras la AWS CLI lo lee.
put_param() {
  local doc="$TMPD/put-parameter.json" rc=0
  rm -f "$doc"
  : >"$TMPD/aws.err"
  if ! (umask 077 && python3 -I -c "$BUILD_PY" "$1" "$2" "$3" "$4" "$KMS_ALIAS" >"$doc" 2>"$TMPD/build.err"); then
    rm -f "$doc"
    return 1
  fi
  aws ssm put-parameter --cli-input-json "file://$doc" --query Version --output text 2>"$TMPD/aws.err" || rc=$?
  rm -f "$doc"
  return $rc
}
aws_error_code() {
  local code
  code=$(sed -n 's/.*An error occurred (\([A-Za-z0-9.]*\)).*/\1/p' "$1" | head -n 1)
  if [ -n "$code" ]; then printf '%s' "$code"
  elif grep -Eqi 'credential|expired|login|token' "$1"; then printf 'sesión de AWS no válida o caducada'
  else printf 'error de la AWS CLI (detalle oculto por seguridad)'
  fi
}

echo
echo "4) Escritura"
failed=0
i=0
while [ $i -lt $N_ITEMS ]; do
  action=${ITEM_ACTIONS[$i]}
  case $action in
    crear|sobrescribir|regenerar)
      overwrite=0
      [ "$action" = crear ] || overwrite=1
      if version=$(put_param "${ITEM_MODES[$i]}" "${ITEM_PARAMS[$i]}" "${ITEM_SRCS[$i]}" "$overwrite") \
          && printf '%s' "$version" | grep -Eq '^[0-9]+$'; then
        echo "    OK    ${ITEM_PARAMS[$i]} -> versión $version"
      else
        detail=$(head -c 200 "$TMPD/build.err" | tr '\n' ' ')
        echo "    ERROR ${ITEM_PARAMS[$i]}: $(aws_error_code "$TMPD/aws.err")${detail:+ / $detail}"
        failed=1
      fi ;;
    *) echo "    --    ${ITEM_PARAMS[$i]}: $action" ;;
  esac
  i=$((i + 1))
done

echo
echo "5) Estado final de /uonify/dev (nombres y versiones)"
aws ssm describe-parameters --parameter-filters "Key=Path,Option=Recursive,Values=/uonify/dev" \
  --query 'Parameters[].[Name,Version,Type]' --output text | sort | awk -F'\t' '{ printf "    %-50s v%-4s %s\n", $1, $2, $3 }'

echo
echo "Siguiente paso: en el host, sudo /usr/local/sbin/uonify-secrets-sync (o bootstrap.sh) vuelca estos valores a /run/uonify."
if [ $WITH_EDGE = 1 ]; then
  echo "Recuerda: la cabecera de origen X-Origin-Verify de CloudFront debe llevar el MISMO valor que $EDGE_PARAM."
fi
if [ $failed != 0 ]; then
  die "alguna escritura falló (ver arriba); repite: lo ya creado se omite"
fi
exit 0
