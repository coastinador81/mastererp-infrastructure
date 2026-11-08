#!/bin/bash
# Se ejecuta DENTRO de un contenedor desechable (root, CAP_SYS_ADMIN, --network none) lanzado por
# run_secrets_sync_test.sh. Prueba uonify-secrets-sync + uonify_secrets_render.py con un stub de la
# AWS CLI y valores ficticios: montajes tmpfs, dueños y modos, marcador vacío, pgpass, puerta de
# nginx, refresco en caliente, reintentos, fallos cerrados y ausencia de fugas en la salida.
set -u
PASS=0; FAILS=0
ok() { PASS=$((PASS + 1)); echo "  ok   $*"; }
ko() { FAILS=$((FAILS + 1)); echo "  FAIL $*"; }
check() { if eval "$2"; then ok "$1"; else ko "$1"; fi; }

install -D -m 0750 /s/uonify-secrets-sync.sh /usr/local/sbin/uonify-secrets-sync
install -D -m 0644 /s/uonify_secrets_render.py /usr/local/lib/uonify/uonify_secrets_render.py
install -D -m 0755 /t/fake_aws_host.py /usr/local/bin/fake-aws
export UONIFY_AWS_BIN=/usr/local/bin/fake-aws UONIFY_SECRETS_ATTEMPTS=4
OUT=/tmp/out.txt
rm -f /tmp/fail_first /tmp/counter

fixture() { # python que modifica d (dict) antes de guardarlo
  python3 -I - "$1" <<'PY'
import base64, json, sys
d = {
  '/uonify/dev/run/google-oauth.json': {'Type': 'SecureString', 'Version': 1, 'Value': json.dumps({'web': {
      'client_id': '123-abc.apps.googleusercontent.com', 'client_secret': 'GOCSPX-FAKEoauthSECRET999'}})},
  '/uonify/dev/run/encryption-key': {'Type': 'SecureString', 'Version': 1,
      'Value': base64.urlsafe_b64encode(b'F' * 32).decode()},
  '/uonify/dev/run/postgres-password': {'Type': 'SecureString', 'Version': 1, 'Value': 'ab12' * 16},
  '/uonify/dev/run/stripe-test-key': {'Type': 'SecureString', 'Version': 1, 'Value': 'sk_test_FAKEstripeSECRET777\n'},
  '/uonify/dev/run/stripe-test-publishable-key': {'Type': 'SecureString', 'Version': 1, 'Value': 'pk_test_FAKEpub1234567890abcd\n'},
  '/uonify/dev/run/stripe-test-vat21': {'Type': 'SecureString', 'Version': 1, 'Value': '__UONIFY_EMPTY_FILE__'},
  '/uonify/dev/run/adk-pilot-users.json': {'Type': 'SecureString', 'Version': 1,
      'Value': '{"userIds":["11111111-2222-3333-4444-555555555555"]}'},
  '/uonify/dev/run/creative-clips-only-rate-snapshots.json': {'Type': 'SecureString', 'Version': 1, 'Value': '{"rate":1}'},
  '/uonify/dev/run/plain-text-param': {'Type': 'String', 'Version': 1, 'Value': 'should-not-be-written'},
  '/uonify/dev/run/UPPER.json': {'Type': 'SecureString', 'Version': 1, 'Value': '{}'},
  '/uonify/dev/edge/origin-verify': {'Type': 'SecureString', 'Version': 3, 'Value': 'EdgeFAKEsecret_' + 'x' * 49},
}
exec(sys.argv[1])
json.dump(d, open('/tmp/fixture.json', 'w'))
PY
}
sync() { /usr/local/sbin/uonify-secrets-sync >"$OUT" 2>&1; echo $? >/tmp/rc; }
rc() { cat /tmp/rc; }
meta() { stat -c '%u:%g %a' "$1"; }
as() { local uid=$1; shift; setpriv --reuid "$uid" --regid "$uid" --clear-groups "$@" >/dev/null 2>&1; }

echo "A) faltan secretos obligatorios: falla cerrado"
install -d -m 1777 /run/lock; chmod 1777 /run/lock
fixture "del d['/uonify/dev/run/encryption-key']"
sync
check "sale con error" '[ "$(rc)" = 1 ]'
check "dice qué falta" 'grep -q "faltan en SSM.*encryption-key" $OUT'
check "no escribe nada" '[ -z "$(ls -A /run/uonify)" ]'

echo "B) volcado completo"
fixture ""
sync
check "sale con 0" '[ "$(rc)" = 0 ]'
for d in /run/uonify /run/uonify-db /run/uonify-edge; do
  check "$d es tmpfs noexec,nosuid,nodev" '[ "$(findmnt -n -o FSTYPE --mountpoint $d)" = tmpfs ] && findmnt -n -o OPTIONS --mountpoint $d | grep -q noexec && findmnt -n -o OPTIONS --mountpoint $d | grep -q nosuid && findmnt -n -o OPTIONS --mountpoint $d | grep -q nodev'
  check "$d modo 711 root" '[ "$(meta $d)" = "0:0 711" ]'
done
check "ficheros del backend 1000:1000 0400" '[ "$(for f in /run/uonify/*; do meta $f; done | sort -u)" = "1000:1000 400" ]'
check "8 ficheros en /run/uonify" '[ "$(ls -A /run/uonify | wc -l)" = 8 ]'
check "contenido idéntico (stripe-test-key)" '[ "$(cat /run/uonify/stripe-test-key)" = sk_test_FAKEstripeSECRET777 ]'
check "stripe-test-vat21 existe y está vacío" '[ -f /run/uonify/stripe-test-vat21 ] && [ ! -s /run/uonify/stripe-test-vat21 ]'
check "parámetro String NO volcado" '[ ! -e /run/uonify/plain-text-param ] && grep -q "no es SecureString" $OUT'
check "nombre no permitido ignorado" '[ ! -e /run/uonify/UPPER.json ]'
check "postgres-password para db 70:0 0440" '[ "$(meta /run/uonify-db/postgres-password)" = "70:0 440" ]'
check "root SIN capacidades DAC lee postgres-password (fase root del entrypoint)" 'setpriv --inh-caps=-all --bounding-set=-dac_override,-dac_read_search cat /run/uonify-db/postgres-password >/dev/null 2>&1'
check "pgpass 70:70 0400 y formato" '[ "$(meta /run/uonify-db/pgpass)" = "70:70 400" ] && [ "$(cat /run/uonify-db/pgpass)" = "*:*:*:uonify:$(printf "ab12%.0s" {1..16})" ]'
check "secreto de borde 0:0 0400, 1 línea exacta" '[ "$(meta /run/uonify-edge/origin-verify)" = "0:0 400" ] && [ "$(cat /run/uonify-edge/origin-verify)" = "EdgeFAKEsecret_$(printf "x%.0s" {1..49})" ] && [ "$(wc -l </run/uonify-edge/origin-verify)" = 1 ]'
check "log: 1 valor, versión 3" 'grep -q "puerta de origen: 1 valor(es) X-Origin-Verify en /run/uonify-edge/origin-verify (/uonify/dev/edge/origin-verify versión 3)" $OUT'
check "uid 1000 lee sus ficheros" 'as 1000 cat /run/uonify/encryption-key'
check "uid 1000 NO lista /run/uonify" '! as 1000 ls /run/uonify'
check "uid 1000 NO lee pgpass ni el secreto de borde" '! as 1000 cat /run/uonify-db/pgpass && ! as 1000 cat /run/uonify-edge/origin-verify'
check "uid 70 lee pgpass y postgres-password" 'as 70 cat /run/uonify-db/pgpass && as 70 cat /run/uonify-db/postgres-password'
check "root SIN capacidades DAC lee el secreto de borde (entrypoint de nginx)" 'setpriv --inh-caps=-all --bounding-set=-dac_override,-dac_read_search cat /run/uonify-edge/origin-verify >/dev/null 2>&1'
check "cerrojo en /run y /run/lock intacto (sigue 1777)" '[ -f /run/uonify-secrets.lock ] && [ "$(stat -c %a /run/lock)" = 1777 ] && [ ! -e /run/lock/uonify-secrets.lock ]'
cp "$OUT" /tmp/out-B.txt

echo "C) refresco en caliente: cambia la tarifa y se retira la lista piloto"
INODE=$(stat -c %i /run/uonify/google-oauth.json)
fixture "d['/uonify/dev/run/creative-clips-only-rate-snapshots.json'].update(Value='{\"rate\":2}', Version=2); del d['/uonify/dev/run/adk-pilot-users.json']"
sync
check "sale con 0" '[ "$(rc)" = 0 ]'
check "informa del cambio y de la retirada" 'grep -q "cambiados: creative-clips-only-rate-snapshots.json" $OUT && grep -q "retirados: adk-pilot-users.json" $OUT'
check "tarifa nueva" '[ "$(cat /run/uonify/creative-clips-only-rate-snapshots.json)" = "{\"rate\":2}" ]'
check "lista piloto retirada" '[ ! -e /run/uonify/adk-pilot-users.json ]'
check "fichero sin cambios no se reescribe (mismo inodo)" '[ "$(stat -c %i /run/uonify/google-oauth.json)" = "$INODE" ]'
check "sin montajes apilados" '[ "$(findmnt -n --mountpoint /run/uonify | wc -l)" = 1 ]'
cp "$OUT" /tmp/out-C.txt

echo "D) secreto de borde: rotación, valores no válidos y ausencia (falla cerrado)"
fixture "d['/uonify/dev/edge/origin-verify']['Value'] = 'A'*40 + '\r\n' + 'B'*40 + '\n'"
sync
check "rotación: 2 líneas normalizadas" '[ "$(rc)" = 0 ] && [ "$(cat /run/uonify-edge/origin-verify)" = "$(printf "%s\n%s" "$(printf "A%.0s" {1..40})" "$(printf "B%.0s" {1..40})")" ] && grep -q "2 valor(es)" $OUT'
fixture "d['/uonify/dev/edge/origin-verify']['Value'] = '\n'.join(['C'*40] * 3)"
sync
check "3 líneas: rechazado, sin fichero, el backend sigue (sale con 0)" '[ "$(rc)" = 0 ] && [ ! -e /run/uonify-edge/origin-verify ] && grep -q "formato no válido" $OUT && [ -s /run/uonify/encryption-key ]'
fixture "d['/uonify/dev/edge/origin-verify']['Value'] = 'D'*40 + ';\$x'"
sync
check "caracteres fuera de [A-Za-z0-9_-]: rechazado" '[ ! -e /run/uonify-edge/origin-verify ] && grep -q "formato no válido" $OUT'
fixture ""
sync
check "vuelve a aparecer con un valor válido" '[ -s /run/uonify-edge/origin-verify ]'
fixture "del d['/uonify/dev/edge/origin-verify']"
sync
check "sin parámetro: sale con 0 y retira el fichero" '[ "$(rc)" = 0 ] && [ ! -e /run/uonify-edge/origin-verify ] && grep -q "retirados: origin-verify" $OUT'
check "log: nginx no arrancará (falla cerrado)" 'grep -q "nginx no arrancará hasta que exista" $OUT'

echo "E) fallos transitorios de SSM: reintenta"
fixture ""
echo 0 >/tmp/counter; echo 2 >/tmp/fail_first
sync
rm -f /tmp/fail_first
check "sale con 0 tras reintentos" '[ "$(rc)" = 0 ] && grep -q "reintento" $OUT && grep -q "EndpointUnreachable" $OUT'

echo "F) encryption-key no válida: falla y no toca lo vivo"
BEFORE=$(sha256sum /run/uonify/encryption-key)
fixture "d['/uonify/dev/run/encryption-key']['Value'] = 'not-a-fernet-key'"
sync
check "sale con error" '[ "$(rc)" = 1 ] && grep -q "encryption-key no es una clave Fernet" $OUT'
check "fichero vivo intacto" '[ "$(sha256sum /run/uonify/encryption-key)" = "$BEFORE" ]'

echo "G) SSM inaccesible: agota reintentos y no toca nada"
fixture ""
echo 0 >/tmp/counter; echo 99 >/tmp/fail_first
UONIFY_SECRETS_ATTEMPTS=2 sync
rm -f /tmp/fail_first
check "sale con error" '[ "$(rc)" = 1 ] && grep -q "falló tras 2 intentos" $OUT'
check "ficheros vivos intactos" '[ "$(sha256sum /run/uonify/encryption-key)" = "$BEFORE" ]'

echo "H) listas piloto que la API rechazaría: no se vuelcan; se conserva la anterior válida"
fixture ""
sync
GOOD_SHA=$(sha256sum /run/uonify/adk-pilot-users.json)
fixture "d['/uonify/dev/run/adk-pilot-users.json'].update(Version=2, Value='{\"userIds\":[\"11111111-2222-3333-4444-555555555555\"],\"extra\":1}'); d['/uonify/dev/run/live-pilot-users.json'] = {'Type': 'SecureString', 'Version': 1, 'Value': '{\"userIds\":[\"11111111-2222-3333-4444-555555555555\"],\"sessionLimit\":0}'}"
sync
check "sale con 0 (una lista mal escrita no impide arrancar Docker)" '[ "$(rc)" = 0 ]'
check "lista no válida con anterior válida: se conserva la anterior intacta" '[ "$(sha256sum /run/uonify/adk-pilot-users.json)" = "$GOOD_SHA" ] && grep -q "adk-pilot-users.json (SSM versión 2) NO es una lista piloto válida" $OUT && grep -q "se conserva el fichero anterior" $OUT'
check "lista no válida sin anterior: no se vuelca (piloto apagado)" '[ ! -e /run/uonify/live-pilot-users.json ] && grep -q "live-pilot-users.json (SSM versión 1) NO es una lista piloto válida para el backend (sessionLimit debe ser un entero entre 1 y 200); no se vuelca" $OUT'
check "el resumen final avisa" 'grep -q "listo CON AVISOS" $OUT'
cp "$OUT" /tmp/out-H.txt
printf '{"userIds":["no-uuid"]}' >/tmp/bad-prev; install -m 0400 -o 1000 -g 1000 /tmp/bad-prev /run/uonify/adk-pilot-users.json
sync
check "si la anterior tampoco es válida, se retira (la API arranca sin ella)" '[ ! -e /run/uonify/adk-pilot-users.json ] && grep -q "retirados: adk-pilot-users.json" $OUT && grep -q "no se vuelca" $OUT'
fixture "d['/uonify/dev/run/live-pilot-users.json'] = {'Type': 'SecureString', 'Version': 2, 'Value': '{\"userIds\":[\"11111111-2222-3333-4444-555555555555\"],\"sessionLimit\":20}'}"
sync
check "corregidas en SSM: se vuelcan y sin avisos" '[ -s /run/uonify/adk-pilot-users.json ] && [ -s /run/uonify/live-pilot-users.json ] && [ "$(meta /run/uonify/live-pilot-users.json)" = "1000:1000 400" ] && ! grep -q "AVISO" $OUT && grep -q "^uonify-secrets: listo\. " $OUT'

echo "I) ninguna salida contiene valores"
cat /tmp/out-B.txt /tmp/out-C.txt /tmp/out-H.txt "$OUT" >/tmp/all-out.txt
check "sin fugas" '! grep -Eq "GOCSPX-FAKE|sk_test_FAKE|pk_test_FAKE|EdgeFAKEsecret|ab12ab12|RkZGRkZG|11111111-2222|no-uuid" /tmp/all-out.txt'
echo "--- salida de ejemplo (escenario B) ---"
cat /tmp/out-B.txt
echo
echo "RESULTADO uonify-secrets-sync (bash $BASH_VERSION, $(python3 --version)): $PASS ok, $FAILS fallos"
[ $FAILS = 0 ]
