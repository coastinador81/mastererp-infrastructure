#!/usr/bin/env bash
# set_gate_credentials.sh · LO EJECUTA SOLO EL DUEÑO, en su terminal y con su perfil de AWS.
#
# Guarda en el KeyValueStore de CloudFront «uonify-dev-gate» (el que leen gate-default.js y
# gate-api.js):
#   gate_cred_sha256  SHA-256 en hex de "usuario:contraseña"  (la contraseña NO se guarda)
#   gate_hmac_key     32 bytes aleatorios en hex: firman la cookie de la puerta
# Cada vez que cambias la contraseña se rota también la clave HMAC: todas las cookies de puerta
# anteriores dejan de valer y todo el mundo vuelve a ver el diálogo de usuario y contraseña.
#
# Uso:
#   ./set_gate_credentials.sh            pide usuario y contraseña (sin eco) y los guarda
#   ./set_gate_credentials.sh --revoke   solo rota la clave HMAC (expulsa a todos de la puerta)
#   ./set_gate_credentials.sh --check    dice si existen las dos claves (nunca enseña valores)
# Variables opcionales: AWS_PROFILE (perfil del dueño), KVS_NAME (por defecto uonify-dev-gate).
# Requisitos: AWS CLI v2 (firma SigV4A del API de KeyValueStore) y openssl.
#
# Garantías: la contraseña nunca va en la línea de comandos de ningún proceso, ni a un fichero,
# ni a la pantalla; el hash y la clave tampoco se imprimen. Viajan a AWS en un fichero temporal
# 0600 dentro de un directorio 0700 que se borra al salir, pase lo que pase.
set +x
set -u -o pipefail
umask 077
ulimit -c 0 2>/dev/null || true
export LC_ALL=C
export AWS_PAGER=""
export AWS_STS_REGIONAL_ENDPOINTS=regional

KVS_NAME="${KVS_NAME:-uonify-dev-gate}"
# El API de datos del KeyValueStore es global (firma SigV4A con región «*»), pero la AWS CLI exige
# una región: sin ella falla con NoRegion si el perfil del dueño no tiene región por defecto.
KVS_REGION="us-east-1"
K_HASH="gate_cred_sha256"
K_HMAC="gate_hmac_key"
MIN_PASSWORD=16
MAX_PASSWORD=256

WORK=""
cleanup() {
  # $WORK solo puede venir de mktemp -d (ver main).
  if [ -n "$WORK" ] && [ -d "$WORK" ]; then
    rm -rf -- "$WORK"
  fi
  WORK=""
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT TERM HUP

say() { printf '%s\n' "$*" >&2; }
die() { say "ERROR: $*"; exit 1; }

usage() {
  awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "$0" >&2
  exit 64
}

need() {
  command -v "$1" >/dev/null 2>&1 || die "falta el comando «$1»"
}

# Código de error de AWS sin volcar el mensaje completo (nunca contiene valores, pero por si acaso).
aws_error() {
  grep -o 'An error occurred ([A-Za-z]*)' "$1" 2>/dev/null | head -n 1 || true
}

sha256_hex() {
  # Lee de la entrada estándar: el secreto nunca aparece como argumento.
  openssl dgst -sha256 | awk '{print $NF}'
}

kvs_arn() {
  local kvs_state arn
  kvs_state=$(aws cloudfront describe-key-value-store --region us-east-1 --name "$KVS_NAME" \
    --query 'KeyValueStore.Status' --output text 2>"$WORK/err") ||
    die "no encuentro el KeyValueStore «$KVS_NAME» ($(aws_error "$WORK/err")). ¿Lo ha creado ya el CEO (paso 13)?"
  [ "$kvs_state" = "READY" ] || die "el KeyValueStore «$KVS_NAME» está en estado «$kvs_state», no READY"
  arn=$(aws cloudfront describe-key-value-store --region us-east-1 --name "$KVS_NAME" \
    --query 'KeyValueStore.ARN' --output text 2>"$WORK/err") || die "no puedo leer el ARN ($(aws_error "$WORK/err"))"
  case "$arn" in
    arn:aws:cloudfront::*:key-value-store/*) printf '%s' "$arn" ;;
    *) die "ARN inesperado para «$KVS_NAME»" ;;
  esac
}

# ETag actual del KeyValueStore (API de datos). Se llama también ANTES de pedir la contraseña: así un
# fallo de la CLI, de la región o de permisos sale antes de que el dueño la escriba.
kvs_etag() {
  local etag
  etag=$(aws cloudfront-keyvaluestore describe-key-value-store --kvs-arn "$1" --region "$KVS_REGION" \
    --query 'ETag' --output text 2>"$WORK/err") || die "no puedo leer el ETag del KeyValueStore ($(aws_error "$WORK/err")); no se ha cambiado nada"
  [ -n "$etag" ] && [ "$etag" != "None" ] || die "ETag vacío en el KeyValueStore; no se ha cambiado nada"
  printf '%s' "$etag"
}

# Escribe las parejas de $WORK/puts.json en una sola llamada (atómica), con reintento si otro
# cambio se adelanta (ETag).
put_keys() {
  local arn="$1" attempt etag
  for attempt in 1 2 3; do
    etag=$(kvs_etag "$arn") || exit 1
    if aws cloudfront-keyvaluestore update-keys --kvs-arn "$arn" --region "$KVS_REGION" --if-match "$etag" \
      --puts "file://$WORK/puts.json" --output json >/dev/null 2>"$WORK/err"; then
      rm -f "$WORK/puts.json"
      return 0
    fi
    say "Intento $attempt sin éxito ($(aws_error "$WORK/err")); reintento…"
    sleep 2
  done
  rm -f "$WORK/puts.json"
  die "no se ha podido guardar en el KeyValueStore"
}

# Compara lo guardado con lo esperado sin enseñar ninguno de los dos valores.
verify_key() {
  local arn="$1" key="$2" expected="$3" got
  got=$(aws cloudfront-keyvaluestore get-key --kvs-arn "$arn" --region "$KVS_REGION" --key "$key" \
    --query 'Value' --output text 2>"$WORK/err") || die "no puedo releer «$key» ($(aws_error "$WORK/err"))"
  [ "$got" = "$expected" ] || die "«$key» no coincide al releerlo"
  got=""
}

new_hmac_key() {
  local key
  key=$(openssl rand -hex 32) || die "openssl rand ha fallado"
  [[ "$key" =~ ^[0-9a-f]{64}$ ]] || die "clave HMAC con formato inesperado"
  printf '%s' "$key"
}

read_credentials() {
  local user pass pass2
  [ -t 0 ] || say "Aviso: la entrada no es una terminal; se lee igual y sin eco."
  printf 'Usuario de la puerta de DEV (letras, números, punto, guion o guion bajo): ' >&2
  IFS= read -r user || die "no se ha leído el usuario"
  [[ "$user" =~ ^[A-Za-z0-9._-]{3,64}$ ]] || die "usuario no válido: 3 a 64 caracteres [A-Za-z0-9._-]"
  printf 'Contraseña (no se verá al escribir; mínimo %s caracteres): ' "$MIN_PASSWORD" >&2
  IFS= read -r -s pass || die "no se ha leído la contraseña"
  printf '\n' >&2
  printf 'Repite la contraseña: ' >&2
  IFS= read -r -s pass2 || die "no se ha leído la confirmación"
  printf '\n' >&2
  if [ "$pass" != "$pass2" ]; then
    pass=""; pass2=""
    die "las dos contraseñas no coinciden; no se ha cambiado nada"
  fi
  pass2=""
  if [ "${#pass}" -lt "$MIN_PASSWORD" ] || [ "${#pass}" -gt "$MAX_PASSWORD" ]; then
    pass=""
    die "la contraseña debe tener entre $MIN_PASSWORD y $MAX_PASSWORD caracteres; no se ha cambiado nada"
  fi
  if ! [[ "$pass" =~ ^[[:print:]]+$ ]]; then
    pass=""
    die "usa solo caracteres ASCII imprimibles (sin tildes ni ñ: el navegador los codifica distinto); no se ha cambiado nada"
  fi
  if [ "$pass" = "$user" ]; then
    pass=""
    die "la contraseña no puede ser igual al usuario"
  fi
  CRED_HASH=$(printf '%s:%s' "$user" "$pass" | sha256_hex)
  pass=""
  [[ "$CRED_HASH" =~ ^[0-9a-f]{64}$ ]] || die "hash con formato inesperado"
  GATE_USER="$user"
}

main() {
  local mode="set"
  case "${1:-}" in
    "") ;;
    --revoke) mode="revoke" ;;
    --check) mode="check" ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
  [ "$#" -le 1 ] || usage
  need aws
  need openssl
  WORK=$(mktemp -d "${TMPDIR:-/tmp}/uonify-gate.XXXXXX") || die "no puedo crear el directorio temporal"
  chmod 700 "$WORK"

  local arn
  arn=$(kvs_arn) || exit 1

  if [ "$mode" = "check" ]; then
    local keys
    keys=$(aws cloudfront-keyvaluestore list-keys --kvs-arn "$arn" --region "$KVS_REGION" --query 'Items[].Key' \
      --output text 2>"$WORK/err") || die "no puedo listar las claves ($(aws_error "$WORK/err"))"
    for k in "$K_HASH" "$K_HMAC"; do
      case " $(printf '%s' "$keys" | tr '\t\n' '  ') " in
        *" $k "*) say "OK  $k existe" ;;
        *) say "FALTA $k" ;;
      esac
    done
    return 0
  fi

  # Prueba del API de datos (CLI, región y permisos) ANTES de pedir nada al dueño.
  kvs_etag "$arn" >/dev/null || exit 1

  CRED_HASH=""
  GATE_USER=""
  if [ "$mode" = "set" ]; then
    read_credentials
  fi
  HMAC_KEY=$(new_hmac_key) || exit 1

  if [ "$mode" = "set" ]; then
    printf '[{"Key":"%s","Value":"%s"},{"Key":"%s","Value":"%s"}]' \
      "$K_HASH" "$CRED_HASH" "$K_HMAC" "$HMAC_KEY" >"$WORK/puts.json"
  else
    printf '[{"Key":"%s","Value":"%s"}]' "$K_HMAC" "$HMAC_KEY" >"$WORK/puts.json"
  fi
  chmod 600 "$WORK/puts.json"
  put_keys "$arn"
  if [ "$mode" = "set" ]; then
    verify_key "$arn" "$K_HASH" "$CRED_HASH"
  fi
  verify_key "$arn" "$K_HMAC" "$HMAC_KEY"
  CRED_HASH=""
  HMAC_KEY=""

  if [ "$mode" = "set" ]; then
    say "Hecho: la puerta de DEV pide ahora el usuario «$GATE_USER» y la contraseña que has escrito."
    say "No se ha guardado la contraseña, solo su huella SHA-256. Se ha rotado la clave de las cookies:"
    say "quien ya hubiera entrado tendrá que volver a escribirla. El cambio llega a todo CloudFront"
    say "en unos segundos. Reparte el usuario y la contraseña por un canal privado, nunca por el chat."
  else
    say "Hecho: clave de las cookies rotada. Todas las sesiones de la puerta han caducado."
  fi
}

main "$@"
