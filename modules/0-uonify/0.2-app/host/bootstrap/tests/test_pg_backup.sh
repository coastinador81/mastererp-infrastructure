#!/bin/bash
# Prueba LOCAL de uonify-pg-backup contra un Postgres DESECHABLE (red interna propia, etiquetas propias
# uonify-bktest, contraseña ficticia) y un stub de S3 que reproduce el cifrado por defecto y la política
# del bucket del stack. Incluye un simulacro de restauración CON propietarios en otro Postgres
# desechable. Nunca toca el stack uonify-local-* ni AWS.
# PG_BACKUP_SCRIPT=ruta prueba otra versión del script (p. ej. la anterior, para ver que el stub la caza).
set -u
HERE=$(cd "$(dirname "$0")" && pwd -P)
SCRIPT=${PG_BACKUP_SCRIPT:-$HERE/../files/uonify-pg-backup.sh}
RUN="$HERE/.run-backup"
NET=uonify-bktest_private VOL=uonify-bktest-dbsecrets BADVOL=uonify-bktest-badsecrets
DB=uonify-bktest-db RESTORE=uonify-bktest-restore IMG=postgres:17-alpine
BUCKET=uonify-dev-backups-277352717693-eu-west-1
# Claves FICTICIAS: la CMK del bucket y otra clave de la misma cuenta (p. ej. la gestionada aws/s3).
CMK=arn:aws:kms:eu-west-1:277352717693:key/11111111-2222-4333-8444-555555555555
OTHER_KEY=arn:aws:kms:eu-west-1:277352717693:key/99999999-8888-4777-8666-555555555555
PW="bktest-$(python3 -I -c 'import secrets; print(secrets.token_hex(8))')"
PASS=0; FAILS=0
ok() { PASS=$((PASS + 1)); echo "  ok   $*"; }
ko() { FAILS=$((FAILS + 1)); echo "  FAIL $*"; }
check() { if eval "$2"; then ok "$1"; else ko "$1"; fi; }
cleanup() {
  docker rm -f "$DB" "$RESTORE" >/dev/null 2>&1
  docker network rm "$NET" >/dev/null 2>&1
  docker volume rm "$VOL" "$BADVOL" >/dev/null 2>&1
  rm -rf "$RUN"
}
trap cleanup EXIT
cleanup
mkdir -p "$RUN/bin" "$RUN/s3" "$RUN/lock"
cp "$HERE/fake_aws_s3.py" "$RUN/bin/aws"; chmod +x "$RUN/bin/aws"

wait_ready() { local i; for i in $(seq 1 60); do docker exec "$1" pg_isready -q -U uonify -d uonify && return 0; sleep 1; done; return 1; }
make_secrets() { # volumen contraseña
  docker volume create "$1" >/dev/null
  docker run --rm --network none --pull never -e PW="$2" -v "$1:/v" --entrypoint sh "$IMG" -c \
    'printf "*:*:*:uonify:%s\n" "$PW" >/v/pgpass && chown 70:70 /v/pgpass && chmod 0400 /v/pgpass && chmod 0711 /v'
}
backup() { # proyecto volumen [UONIFY_KMS_KEY_ARN] [CMK por defecto del bucket]
  UONIFY_COMPOSE_PROJECT=$1 UONIFY_DB_SECRETS_SRC=$2 UONIFY_KMS_KEY_ARN=${3:-} \
    FAKE_S3_CMK_ARN=${4:-$CMK} UONIFY_AWS_BIN="$RUN/bin/aws" \
    UONIFY_LOCK_DIR="$RUN/lock" FAKE_S3_DIR="$RUN/s3" bash "$SCRIPT" >"$RUN/out.txt" 2>&1
  echo $? >"$RUN/rc"
}
objects() { find "$RUN/s3" -type f ! -name '*.sse.json' | wc -l | tr -d ' '; }
manifests() { find "$RUN/s3" -name '*.manifest' | wc -l | tr -d ' '; }
reset_s3() { rm -rf "$RUN/s3"; mkdir -p "$RUN/s3"; }

echo "0) el stub reproduce el cifrado y la política del bucket (si no, la prueba no valdría)"
stub_put() { printf 'x' | FAKE_S3_DIR="$RUN/s3probe" FAKE_S3_CMK_ARN="$CMK" "$RUN/bin/aws" s3 cp - \
  "s3://$BUCKET/probe/obj" "$@" --only-show-errors --no-progress >"$RUN/probe.out" 2>&1; }
check "pedir el alias alias/uonify-dev: AccessDenied" '! stub_put --sse aws:kms --sse-kms-key-id alias/uonify-dev && grep -q "(AccessDenied)" "$RUN/probe.out"'
check "aws:kms sin id de clave: AccessDenied" '! stub_put --sse aws:kms'
check "AES256: AccessDenied" '! stub_put --sse AES256'
check "denegado: no queda objeto" '[ ! -e "$RUN/s3probe/$BUCKET/probe/obj" ]'
check "ARN exacto de la CMK: aceptado" 'stub_put --sse aws:kms --sse-kms-key-id "$CMK"'
check "sin cabeceras: aceptado y cifrado con la CMK por defecto" 'stub_put && [ "$(FAKE_S3_DIR="$RUN/s3probe" "$RUN/bin/aws" s3api head-object --bucket "$BUCKET" --key probe/obj --query "[ServerSideEncryption, SSEKMSKeyId, ContentLength]" --output text)" = "$(printf "aws:kms\t%s\t1" "$CMK")" ]'
rm -rf "$RUN/s3probe"

echo "preparación: Postgres desechable con un rol craft dueño de una tabla"
docker network create --internal "$NET" >/dev/null
make_secrets "$VOL" "$PW"
make_secrets "$BADVOL" "wrong-password"
docker run -d --name "$DB" --network "$NET" --network-alias db --pull never --label com.docker.compose.project=uonify-bktest \
  --label com.docker.compose.service=db -e POSTGRES_USER=uonify -e POSTGRES_DB=uonify \
  -e POSTGRES_PASSWORD="$PW" "$IMG" >/dev/null
wait_ready "$DB" || { echo "Postgres de prueba no arrancó"; exit 1; }
docker exec "$DB" psql -q -U uonify -d uonify -v ON_ERROR_STOP=1 -c "
  CREATE ROLE uonify_craft_compdef_bktest NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  CREATE TABLE t(x int); INSERT INTO t VALUES (1),(2),(3);
  ALTER TABLE t OWNER TO uonify_craft_compdef_bktest;" >/dev/null

echo "1) copia correcta (host.env sin UONIFY_KMS_KEY_ARN)"
backup uonify-bktest "$VOL"
cat "$RUN/out.txt" | sed 's/^/     | /'
check "sale con 0" '[ "$(cat $RUN/rc)" = 0 ] && grep -q "uonify-pg-backup: OK" $RUN/out.txt'
BASE=$(cd "$RUN/s3/$BUCKET/pg" 2>/dev/null && ls *.manifest 2>/dev/null | sed 's/\.manifest$//')
P="$RUN/s3/$BUCKET/pg/$BASE"
check "tres objetos: roles.sql, dump, manifest" '[ -n "$BASE" ] && [ -s "$P.roles.sql" ] && [ -s "$P.dump" ] && [ -s "$P.manifest" ]'
check "subidas SIN cabeceras de cifrado; cifradas por el bucket con la CMK" 'python3 -I -c "
import json, sys
for ext in (\".roles.sql\", \".dump\", \".manifest\"):
    meta = json.load(open(sys.argv[1] + ext + \".sse.json\"))
    assert meta == {\"sse\": \"aws:kms\", \"kms\": sys.argv[2], \"requested_headers\": False}, (ext, meta)
" "$P" "$CMK"'
check "el log dice qué clave cifró y avisa de que no la fija" 'grep -q "SSE-KMS con $CMK" $RUN/out.txt && grep -q "sin UONIFY_KMS_KEY_ARN" $RUN/out.txt'
check "manifest con sha256 y bytes correctos" 'python3 -I - "$P" <<EOF
import hashlib, sys
base = sys.argv[1]
m = dict(l.split("=", 1) for l in open(base + ".manifest").read().splitlines())
for kind, ext in (("roles", ".roles.sql"), ("dump", ".dump")):
    data = open(base + ext, "rb").read()
    assert m[kind + "_sha256"] == hashlib.sha256(data).hexdigest(), kind
    assert int(m[kind + "_bytes"]) == len(data), kind
assert m["format"] == "uonify-dev-pg-backup-v1" and m["db_image"].startswith("sha256:")
EOF'
check "dump en formato custom (PGDMP)" '[ "$(head -c 5 "$P.dump")" = PGDMP ]'
check "roles: incluye el rol craft y ninguna contraseña" 'grep -q "CREATE ROLE uonify_craft_compdef_bktest" "$P.roles.sql" && ! grep -qi "password" "$P.roles.sql"'
check "la contraseña no aparece en la salida" '! grep -q "$PW" $RUN/out.txt'
check "no quedan contenedores efímeros" '[ -z "$(docker ps -aq --filter name=uonify-pg-backup-)" ]'

echo "2) simulacro de restauración CON propietarios en otro Postgres desechable"
docker run -d --name "$RESTORE" --network "$NET" --pull never -e POSTGRES_USER=uonify -e POSTGRES_DB=uonify \
  -e POSTGRES_PASSWORD="$PW" "$IMG" >/dev/null
wait_ready "$RESTORE" || echo "     (restore no arrancó)"
docker exec -i "$RESTORE" psql -q -U uonify -d uonify <"$P.roles.sql" >/dev/null 2>"$RUN/roles.err"
docker exec -i "$RESTORE" pg_restore -U uonify -d uonify --exit-on-error <"$P.dump" 2>"$RUN/restore.err"; rrc=$?
check "pg_restore sin --no-owner sale con 0" '[ $rrc = 0 ]'
check "la tabla conserva su propietario craft" '[ "$(docker exec "$RESTORE" psql -tA -U uonify -d uonify -c "select tableowner from pg_tables where tablename = '"'"'t'"'"'")" = uonify_craft_compdef_bktest ]'
check "y sus 3 filas" '[ "$(docker exec "$RESTORE" psql -tA -U uonify -d uonify -c "select count(*) from t")" = 3 ]'

echo "3) clave exacta (UONIFY_KMS_KEY_ARN = salida KmsKeyArn del stack)"
reset_s3
backup uonify-bktest "$VOL" "$CMK"
check "con la CMK fijada: sale con 0, 3 objetos y sin aviso" '[ "$(cat $RUN/rc)" = 0 ] && [ "$(objects)" = 3 ] && ! grep -q "sin UONIFY_KMS_KEY_ARN" $RUN/out.txt'
reset_s3
backup uonify-bktest "$VOL" "$CMK" "$OTHER_KEY"
check "el bucket cifra con OTRA clave (cifrado por defecto cambiado): error claro" '[ "$(cat $RUN/rc)" != 0 ] && grep -q "no con la CMK" $RUN/out.txt'
check "  y no sube manifest" '[ "$(manifests)" = 0 ]'
reset_s3
backup uonify-bktest "$VOL" alias/uonify-dev
check "UONIFY_KMS_KEY_ARN con el alias: error antes de subir nada" '[ "$(cat $RUN/rc)" != 0 ] && grep -q "nunca el alias" $RUN/out.txt && [ "$(objects)" = 0 ]'

echo "4) fallos: sin manifest y con error"
reset_s3
backup uonify-bktest "$BADVOL"
check "contraseña mala: sale con error" '[ "$(cat $RUN/rc)" != 0 ]'
check "contraseña mala: no sube manifest" '[ "$(manifests)" = 0 ]'
backup uonify-noexiste "$VOL"
check "sin contenedor db: sale con error claro" '[ "$(cat $RUN/rc)" != 0 ] && grep -q "esperaba 1 contenedor" $RUN/out.txt'
check "no quedan contenedores efímeros" '[ -z "$(docker ps -aq --filter name=uonify-pg-backup-)" ]'

echo
echo "RESULTADO uonify-pg-backup (bash $BASH_VERSION, $(docker exec "$DB" pg_dump --version)): $PASS ok, $FAILS fallos"
[ $FAILS = 0 ]
