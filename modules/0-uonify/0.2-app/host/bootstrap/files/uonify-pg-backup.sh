#!/usr/bin/env bash
# Uonify DEV · copia nocturna de PostgreSQL (se instala en /usr/local/sbin/uonify-pg-backup, 0750 root).
# La lanza uonify-pg-backup.timer; también a mano: sudo systemctl start uonify-pg-backup.service
#
# Sin volcados en claro en disco: un contenedor EFÍMERO (la misma imagen, por ID, que el contenedor db,
# así pg_dump es de la misma versión que el servidor) se une a la red privada del proyecto y su salida
# va por una tubería a `aws s3 cp -`. El contenedor usa --log-driver none: con el driver por defecto
# Docker guardaría TODA la salida (el volcado) en su log.
#
# Cifrado: las subidas NO llevan --sse ni --sse-kms-key-id. El bucket cifra por defecto con la CMK del
# stack (SSE-KMS) y su política DenyRequestedEncryptionOtherThanDataKey DENIEGA cualquier subida que
# pida cifrado con otro id de clave; S3 compara la cabecera TAL CUAL con el ARN de la CMK, así que pedir
# alias/uonify-dev (o aws:kms sin id) también se deniega. Después, head-object exige aws:kms con una
# clave de esta cuenta y región y, si /etc/uonify/host.env trae UONIFY_KMS_KEY_ARN (salida KmsKeyArn del
# stack; bootstrap.sh --kms-key-arn), que sea EXACTAMENTE esa CMK.
#
# Por cada copia se suben tres objetos a s3://<bucket>/<prefijo>/uonify-dev-<UTC>.*:
#   .roles.sql  pg_dumpall --roles-only --no-role-passwords (los roles craft: pg_dump no los lleva y,
#               sin ellos, restaurar CON propietarios y privilegios falla con 42501)
#   .dump       pg_dump -Fc de la base uonify
#   .manifest   sha256 y bytes de los dos anteriores. Se sube EL ÚLTIMO: una copia sin .manifest
#               está incompleta y no vale para restaurar (el rol no puede borrar objetos; la regla de
#               ciclo de vida del bucket la elimina a los 35 días).
# Restauración (resumen; ensayarla en el paso 18): crear el clúster con la imagen y POSTGRES_PASSWORD_FILE,
#   comprobar los sha256 del .manifest, aplicar SOLO los roles uonify_craft_* que referencia el volcado,
#   y `pg_restore -d uonify` SIN --no-owner ni --no-privileges, en streaming desde S3 (aws s3 cp ... -).
set -Eeuo pipefail
umask 077
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME="${HOME:-/root}"
export AWS_REGION=eu-west-1 AWS_DEFAULT_REGION=eu-west-1 AWS_PAGER="" AWS_CLI_AUTO_PROMPT=off

readonly HOST_ENV=/etc/uonify/host.env
# Clave KMS de una sola región (MultiRegion: false en el stack), de la cuenta y la región del DEV.
readonly KMS_ARN_RE='^arn:aws:kms:eu-west-1:277352717693:key/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
log() { printf 'uonify-pg-backup: %s\n' "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

if [[ -r $HOST_ENV ]]; then
  meta=$(stat -c '%u %a' "$HOST_ENV")
  [[ ${meta%% *} == 0 && $(( 8#${meta##* } & 8#022 )) -eq 0 ]] || die "$HOST_ENV debe ser de root y no escribible por grupo/otros"
  set -a
  # shellcheck source=/dev/null
  . "$HOST_ENV"
  set +a
fi

PROJECT=${UONIFY_COMPOSE_PROJECT:-uonify-dev}
DB_SERVICE=${UONIFY_DB_SERVICE:-db}
DB_HOST=${UONIFY_DB_HOST:-$DB_SERVICE}
NETWORK=${UONIFY_BACKUP_NETWORK:-}
BUCKET=${UONIFY_BACKUP_BUCKET:-uonify-dev-backups-277352717693-eu-west-1}
PREFIX=${UONIFY_BACKUP_PREFIX:-pg}
KMS_KEY_ARN=${UONIFY_KMS_KEY_ARN:-}
DB_SECRETS=${UONIFY_DB_SECRETS_SRC:-/run/uonify-db}
AWS=${UONIFY_AWS_BIN:-/usr/local/bin/aws}
# Cerrojo en /run (root 0755), no en /run/lock (1777, escribible por todos).
LOCK_DIR=${UONIFY_LOCK_DIR:-/run}
USED_KEY=""

# Copia stdin -> stdout calculando sha256 y bytes; exige la cabecera esperada antes de dejar pasar nada.
# Argumentos: tipo (dump|roles) fichero_meta. Escribe "sha256 bytes" en el fichero meta al terminar.
readonly TEE_PY='
import hashlib, sys
kind, meta = sys.argv[1], sys.argv[2]
magic = {"dump": b"PGDMP", "roles": b"--"}[kind]
source, sink = sys.stdin.buffer, sys.stdout.buffer
digest, total, first = hashlib.sha256(), 0, True
while True:
    chunk = source.read(1 << 20)
    if not chunk:
        break
    if first:
        if not chunk.startswith(magic):
            sys.exit("cabecera inesperada en el volcado (" + kind + ")")
        first = False
    digest.update(chunk)
    total += len(chunk)
    sink.write(chunk)
sink.flush()
if total == 0:
    sys.exit("volcado vacío (" + kind + ")")
with open(meta, "w") as handle:
    handle.write(digest.hexdigest() + " " + str(total) + "\n")
'

find_db() {
  local ids count
  ids=$(docker ps -q --no-trunc --filter "label=com.docker.compose.project=${PROJECT}" \
    --filter "label=com.docker.compose.service=${DB_SERVICE}" --filter status=running)
  count=$(printf '%s\n' "$ids" | sed '/^$/d' | wc -l)
  [[ $count -eq 1 ]] || die "esperaba 1 contenedor ${PROJECT}/${DB_SERVICE} en marcha y hay ${count}"
  printf '%s' "$ids"
}

pick_network() {
  local cid=$1 networks private
  networks=$(docker inspect -f '{{range $name, $v := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' "$cid" | sed '/^$/d')
  if [[ -n $NETWORK ]]; then
    grep -qxF "$NETWORK" <<<"$networks" || die "el contenedor db no está en la red $NETWORK"
    printf '%s' "$NETWORK"
  elif [[ $(wc -l <<<"$networks") -eq 1 ]]; then
    printf '%s' "$networks"
  else
    private=$(grep -E '_private$' <<<"$networks" || true)
    [[ -n $private && $(wc -l <<<"$private") -eq 1 ]] \
      || die "el contenedor db está en varias redes; fija UONIFY_BACKUP_NETWORK en $HOST_ENV"
    printf '%s' "$private"
  fi
}

# Contenedor efímero endurecido: sin log, sin pull, solo lectura, sin capacidades, uid 70 (postgres).
pg_tool() { # nombre programa args...
  local name=$1 program=$2
  shift 2
  docker run --rm --log-driver none --pull never --network "$NET" \
    --name "uonify-pg-backup-${STAMP}-${name}" \
    --user 70:70 --read-only --cap-drop ALL --security-opt no-new-privileges \
    --memory 768m --pids-limit 64 \
    -v "${DB_SECRETS}:/run/uonify-db:ro" \
    -e PGPASSFILE=/run/uonify-db/pgpass -e PGHOST="$DB_HOST" -e PGPORT=5432 -e PGUSER=uonify \
    -e PGCONNECT_TIMEOUT=15 --entrypoint "$program" "$IMAGE" "$@"
}

# Sin cabeceras de cifrado: lo pone el cifrado por defecto del bucket (la CMK). Ver la cabecera.
upload() { # tipo clave_s3 -> stream desde stdin
  python3 -I -c "$TEE_PY" "$1" "$TMP/$1.meta" \
    | "$AWS" s3 cp - "s3://${BUCKET}/$2" --only-show-errors --no-progress
}

verify_object() { # clave_s3 bytes_esperados
  local got sse key size
  got=$("$AWS" s3api head-object --bucket "$BUCKET" --key "$1" \
    --query '[ServerSideEncryption, SSEKMSKeyId, ContentLength]' --output text)
  IFS=$'\t' read -r sse key size <<<"$got"
  [[ $sse == aws:kms ]] || die "s3://${BUCKET}/$1 cifrado con ${sse:-nada}; se esperaba aws:kms"
  [[ $key =~ $KMS_ARN_RE ]] || die "s3://${BUCKET}/$1 cifrado con ${key:-?}, que no es una clave KMS de esta cuenta y región"
  if [[ -n $KMS_KEY_ARN && $key != "$KMS_KEY_ARN" ]]; then
    die "s3://${BUCKET}/$1 cifrado con $key y no con la CMK $KMS_KEY_ARN (¿cambió el cifrado por defecto del bucket?)"
  fi
  [[ $size == "$2" ]] || die "s3://${BUCKET}/$1 tiene ${size:-?} bytes; se esperaban $2"
  USED_KEY=$key
}

main() {
  if [[ -n $KMS_KEY_ARN && ! $KMS_KEY_ARN =~ $KMS_ARN_RE ]]; then
    die "UONIFY_KMS_KEY_ARN no es el ARN de una clave KMS de 277352717693 en eu-west-1 (usa la salida KmsKeyArn del stack, nunca el alias)"
  fi
  if [[ -z $KMS_KEY_ARN ]]; then
    log "aviso: sin UONIFY_KMS_KEY_ARN en $HOST_ENV, compruebo aws:kms con una clave de la cuenta pero no la CMK exacta (bootstrap.sh --kms-key-arn)"
  fi
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 || die "Docker no está activo o no tengo acceso"
  [[ -x $AWS ]] || die "no encuentro la AWS CLI en $AWS"
  if [[ $DB_SECRETS == /* ]]; then
    [[ -f $DB_SECRETS/pgpass ]] || die "falta $DB_SECRETS/pgpass (¿uonify-secrets activo?)"
  fi
  if command -v flock >/dev/null 2>&1; then
    exec 9>"$LOCK_DIR/uonify-pg-backup.lock"
    flock -n 9 || die "ya hay una copia en curso"
  fi

  local cid
  cid=$(find_db)
  IMAGE=$(docker inspect -f '{{.Image}}' "$cid")
  NET=$(pick_network "$cid")
  STAMP=$(date -u +%Y%m%dT%H%M%SZ)
  TMP=$(mktemp -d)
  trap 'rm -rf "$TMP"' EXIT
  local base="${PREFIX}/uonify-dev-${STAMP}"
  log "copia ${base} desde ${PROJECT}/${DB_SERVICE} (imagen ${IMAGE#sha256:}, red ${NET})"

  pg_tool roles pg_dumpall --roles-only --no-role-passwords -l uonify | upload roles "${base}.roles.sql"
  pg_tool dump pg_dump -Fc -d uonify | upload dump "${base}.dump"

  local roles_sha roles_bytes dump_sha dump_bytes
  read -r roles_sha roles_bytes <"$TMP/roles.meta"
  read -r dump_sha dump_bytes <"$TMP/dump.meta"
  verify_object "${base}.roles.sql" "$roles_bytes"
  verify_object "${base}.dump" "$dump_bytes"

  {
    printf 'format=uonify-dev-pg-backup-v1\ncreated_utc=%s\ndb_image=%s\n' "$STAMP" "$IMAGE"
    printf 'roles_key=%s.roles.sql\nroles_sha256=%s\nroles_bytes=%s\n' "$base" "$roles_sha" "$roles_bytes"
    printf 'dump_key=%s.dump\ndump_sha256=%s\ndump_bytes=%s\n' "$base" "$dump_sha" "$dump_bytes"
  } >"$TMP/manifest"
  "$AWS" s3 cp "$TMP/manifest" "s3://${BUCKET}/${base}.manifest" --only-show-errors --no-progress
  verify_object "${base}.manifest" "$(wc -c <"$TMP/manifest" | tr -d ' ')"
  log "OK: ${base}.dump (${dump_bytes} bytes, sha256 ${dump_sha}); roles ${roles_bytes} bytes; SSE-KMS con ${USED_KEY}"
}

main "$@"
