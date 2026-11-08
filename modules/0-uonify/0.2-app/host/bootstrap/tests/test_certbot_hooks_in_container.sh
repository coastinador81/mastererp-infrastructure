#!/bin/bash
# Se ejecuta DENTRO de un contenedor desechable (root, --network none) lanzado por run_host_tests.sh.
# Prueba el hook DNS-01 (auth/cleanup) con un stub de Route 53 y el deploy hook con un certificado
# autofirmado de prueba (nunca el real). Sin Docker en el contenedor: el HUP a nginx se omite.
set -u
PASS=0; FAILS=0
ok() { PASS=$((PASS + 1)); echo "  ok   $*"; }
ko() { FAILS=$((FAILS + 1)); echo "  FAIL $*"; }
check() { if eval "$2"; then ok "$1"; else ko "$1"; fi; }
HOOK=/b/files/uonify-acme-route53.sh
DEPLOY=/b/files/uonify-cert-deploy.sh
install -D -m 0755 /t/fake_aws_route53.py /usr/local/bin/fake-aws
export UONIFY_AWS_BIN=/usr/local/bin/fake-aws UONIFY_ACME_POLL_SECONDS=0 UONIFY_ACME_SETTLE_SECONDS=0
TOKEN=AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd

echo "1) auth: UPSERT del TXT exacto y espera a INSYNC"
rm -f /tmp/r53-*
CERTBOT_DOMAIN=origin-dev.uonify.com CERTBOT_VALIDATION=$TOKEN bash "$HOOK" auth >/tmp/out 2>/tmp/err; rc=$?
check "sale con 0" '[ $rc = 0 ]'
check "stdout vacío (CERTBOT_AUTH_OUTPUT)" '[ ! -s /tmp/out ]'
check "batch: UPSERT TXT _acme-challenge.origin-dev.uonify.com TTL 60 con comillas" 'python3 -I -c "
import json
calls = [json.loads(l) for l in open(\"/tmp/r53-calls.jsonl\")]
rrs = calls[0][\"batch\"][\"Changes\"][0]
assert len(calls[0][\"batch\"][\"Changes\"]) == 1
assert rrs[\"Action\"] == \"UPSERT\"
r = rrs[\"ResourceRecordSet\"]
assert r == {\"Name\": \"_acme-challenge.origin-dev.uonify.com\", \"Type\": \"TXT\", \"TTL\": 60, \"ResourceRecords\": [{\"Value\": \"\\\"$TOKEN\\\"\"}]}, r
"'
check "consulta get-change hasta INSYNC (3 llamadas)" '[ "$(grep -c get-change /tmp/r53-calls.jsonl)" = 3 ]'
check "el token no va en la línea de órdenes" '! grep "\"args\"" /tmp/r53-calls.jsonl | python3 -I -c "import json,sys; sys.exit(0 if any(\"$TOKEN\" in a for l in sys.stdin for a in json.loads(l)[\"args\"]) else 1)"'

echo "2) cleanup: DELETE; si falla solo avisa"
rm -f /tmp/r53-*
CERTBOT_DOMAIN=origin-dev.uonify.com CERTBOT_VALIDATION=$TOKEN bash "$HOOK" cleanup 2>/tmp/err; rc=$?
check "DELETE enviado y sale con 0" '[ $rc = 0 ] && grep -q "\"DELETE\"" /tmp/r53-calls.jsonl'
touch /tmp/r53-fail-delete
CERTBOT_DOMAIN=origin-dev.uonify.com CERTBOT_VALIDATION=$TOKEN bash "$HOOK" cleanup 2>/tmp/err; rc=$?
check "DELETE fallido: sale con 0 y avisa" '[ $rc = 0 ] && grep -q "aviso: no se pudo borrar" /tmp/err'

echo "3) rechazos"
CERTBOT_DOMAIN=dev.uonify.com CERTBOT_VALIDATION=$TOKEN bash "$HOOK" auth 2>/tmp/err; rc=$?
check "otro dominio rechazado" '[ $rc != 0 ] && grep -q "dominio no permitido" /tmp/err'
CERTBOT_DOMAIN=origin-dev.uonify.com CERTBOT_VALIDATION='x"; rm -rf /' bash "$HOOK" auth 2>/tmp/err; rc=$?
check "token con caracteres raros rechazado" '[ $rc != 0 ] && grep -q "formato inesperado" /tmp/err'
bash "$HOOK" 2>/tmp/err; rc=$?
check "sin modo: error de uso" '[ $rc != 0 ]'

echo "4) deploy hook con certificado de prueba autofirmado"
L=/tmp/le/live/origin-dev.uonify.com
mkdir -p "$L"
openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj /CN=origin-dev.uonify.com \
  -addext subjectAltName=DNS:origin-dev.uonify.com -keyout "$L/privkey.pem" -out "$L/fullchain.pem" 2>/dev/null
export UONIFY_CERT_LINEAGE=$L UONIFY_STATE_DIR=/tmp/state
RENEWED_LINEAGE=$L bash "$DEPLOY" >/tmp/out 2>&1; rc=$?
check "sin copia (contrato del runtime): sale con 0 y no crea /etc/uonify/tls" '[ $rc = 0 ] && [ ! -e /etc/uonify/tls ]'
check "certificado nuevo: intenta recargar nginx (sin Docker lo dice)" 'grep -q "Docker no está activo" /tmp/out'
check "guarda la huella del certificado desplegado" '[ "$(cat /tmp/state/origin-cert.sha256)" = "$(sha256sum "$L/fullchain.pem" | cut -d" " -f1)" ]'
check "la clave privada no sale en el log" '! grep -q "PRIVATE KEY" /tmp/out'
RENEWED_LINEAGE=$L bash "$DEPLOY" >/tmp/out 2>&1; rc=$?
check "re-ejecución: nada que recargar" '[ $rc = 0 ] && grep -q "nada que recargar" /tmp/out'
RENEWED_LINEAGE=$L UONIFY_TLS_DIR=/tmp/tls bash "$DEPLOY" >/tmp/out 2>&1; rc=$?
check "con UONIFY_TLS_DIR: copia 101:0 0440 y recarga" '[ $rc = 0 ] && [ "$(stat -c "%u:%g %a" /tmp/tls/fullchain.pem /tmp/tls/privkey.pem | sort -u)" = "101:0 440" ] && grep -q "copiado a /tmp/tls" /tmp/out && grep -q "Docker no está activo" /tmp/out'
check "directorio 101:0 0750 y contenido idéntico" '[ "$(stat -c "%u:%g %a" /tmp/tls)" = "101:0 750" ] && cmp -s "$L/fullchain.pem" /tmp/tls/fullchain.pem && cmp -s "$L/privkey.pem" /tmp/tls/privkey.pem'
RENEWED_LINEAGE=$L UONIFY_TLS_DIR=/tmp/tls bash "$DEPLOY" >/tmp/out 2>&1; rc=$?
check "con copia al día: nada que recargar" '[ $rc = 0 ] && grep -q "nada que recargar" /tmp/out'
export UONIFY_TLS_DIR=/tmp/tls
RENEWED_LINEAGE=/tmp/le/live/otro bash "$DEPLOY" >/tmp/out 2>&1; rc=$?
check "otro linaje rechazado" '[ $rc != 0 ] && grep -q "certificado inesperado" /tmp/out'
openssl genrsa -out "$L/privkey.pem" 2048 2>/dev/null
RENEWED_LINEAGE=$L bash "$DEPLOY" >/tmp/out 2>&1; rc=$?
check "clave que no casa: rechazada" '[ $rc != 0 ] && grep -q "no casa" /tmp/out'
openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj /CN=origin-dev.uonify.com.evil.test \
  -addext subjectAltName=DNS:origin-dev.uonify.com.evil.test -keyout "$L/privkey.pem" -out "$L/fullchain.pem" 2>/dev/null
RENEWED_LINEAGE=$L bash "$DEPLOY" >/tmp/out 2>&1; rc=$?
check "dominio parecido rechazado" '[ $rc != 0 ] && grep -q "no es de origin-dev.uonify.com" /tmp/out'
check "la copia válida anterior sigue intacta" 'openssl x509 -in /tmp/tls/fullchain.pem -noout -ext subjectAltName | grep -q "DNS:origin-dev.uonify.com$"'

echo
echo "RESULTADO hooks de certbot (bash $BASH_VERSION): $PASS ok, $FAILS fallos"
[ $FAILS = 0 ]
