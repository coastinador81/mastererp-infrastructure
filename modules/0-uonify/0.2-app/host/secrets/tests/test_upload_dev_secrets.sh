#!/bin/bash
# Prueba LOCAL de upload_dev_secrets.sh con el bash 3.2 de macOS y un stub de la AWS CLI.
# Solo valores ficticios; no llama a AWS ni lee platform/backend/.local.
set -u
HERE=$(cd "$(dirname "$0")" && pwd -P)
SCRIPT="$HERE/../upload_dev_secrets.sh"
RUN="$HERE/.run-upload"
rm -rf "$RUN"; mkdir -p "$RUN/bin" "$RUN/local"
trap 'rm -rf "$RUN"' EXIT
cp "$HERE/fake_aws_ssm.py" "$RUN/bin/aws"; chmod +x "$RUN/bin/aws"
export PATH="$RUN/bin:$PATH" FAKE_AWS_STORE="$RUN/store.json" FAKE_AWS_ARGV_LOG="$RUN/argv.log"
PASS=0; FAILS=0
ok() { PASS=$((PASS + 1)); echo "  ok   $*"; }
ko() { FAILS=$((FAILS + 1)); echo "  FAIL $*"; }
check() { if eval "$2"; then ok "$1"; else ko "$1"; fi; }
store() { python3 -I -c "import json,sys; d=json.load(open('$RUN/store.json')); $1" 2>/dev/null; }
run() { /bin/bash "$SCRIPT" "$@" >"$RUN/out.txt" 2>&1; echo $? >"$RUN/rc"; }

printf 'sk_test_FAKEsecretKEY0123456789abcdefXYZ\n' >"$RUN/local/stripe-test-key"
printf 'pk_test_FAKEpublishable0123456789abcdef\n' >"$RUN/local/stripe-test-publishable-key"
: >"$RUN/local/stripe-test-vat21"
# Clientes OAuth FICTICIOS. El local está también en <local-dir>/google-oauth.json, como en el Mac.
DEV_ID=210987654321-zyxwvutsrqponmlkjihgfedcba543210.apps.googleusercontent.com
LOCAL_ID=123456789012-abcdefghijklmnopqrstuvwxyz012345.apps.googleusercontent.com
cat >"$RUN/oauth-dev.json" <<EOF
{"web":{"client_id":"$DEV_ID","project_id":"fake","client_secret":"GOCSPX-FAKEdevSECRETvalue123","redirect_uris":["https://dev.uonify.com/api/auth/google/callback"],"javascript_origins":["https://dev.uonify.com"]}}
EOF
cat >"$RUN/oauth-local.json" <<EOF
{"web":{"client_id":"$LOCAL_ID","client_secret":"GOCSPX-FAKElocalSECRETvalue1","redirect_uris":["http://127.0.0.1:5173/api/auth/google/callback"],"javascript_origins":["http://127.0.0.1:5173"]}}
EOF
cp "$RUN/oauth-local.json" "$RUN/local/google-oauth.json"
cat >"$RUN/oauth-nocallback.json" <<'EOF'
{"web":{"client_id":"777777777777-nocallbackclient.apps.googleusercontent.com","client_secret":"GOCSPX-FAKEnocallback1","redirect_uris":["https://staging.example.test/api/auth/google/callback"],"javascript_origins":["https://dev.uonify.com"]}}
EOF
printf '{"userIds":["11111111-2222-3333-4444-555555555555"]}' >"$RUN/adk.json"
COMMON="--local-dir $RUN/local --oauth-json $RUN/oauth-dev.json"

echo "1) ensayo por defecto"
run $COMMON
check "ensayo sale con 0" '[ "$(cat $RUN/rc)" = 0 ]'
check "ensayo no escribe" '[ ! -f $RUN/store.json ]'
check "ensayo lo anuncia" 'grep -q "ENSAYO terminado" $RUN/out.txt'
check "plan con 6 parámetros a crear" '[ "$(grep -c "^  crear " $RUN/out.txt)" = 6 ]'

echo "2) escritura"
run $COMMON --apply --yes
check "apply sale con 0" '[ "$(cat $RUN/rc)" = 0 ]'
check "6 parámetros en el almacén" '[ "$(store "print(len(d))")" = 6 ]'
check "encryption-key es Fernet de 32 bytes" '[ "$(store "import base64; print(len(base64.urlsafe_b64decode(d[\"/uonify/dev/run/encryption-key\"][\"Value\"])))")" = 32 ]'
check "postgres-password: 64 hex" '[ "$(store "import re; print(bool(re.fullmatch(\"[0-9a-f]{64}\", d[\"/uonify/dev/run/postgres-password\"][\"Value\"])))")" = True ]'
check "vat21 es el marcador" '[ "$(store "print(d[\"/uonify/dev/run/stripe-test-vat21\"][\"Value\"])")" = __UONIFY_EMPTY_FILE__ ]'
check "stripe-test-key copiada tal cual" '[ "$(store "print(repr(d[\"/uonify/dev/run/stripe-test-key\"][\"Value\"]))")" = "$(python3 -c "print(repr(open(\"$RUN/local/stripe-test-key\").read()))")" ]'
check "google-oauth.json copiado tal cual" 'store "import sys; sys.exit(0 if d[\"/uonify/dev/run/google-oauth.json\"][\"Value\"] == open(\"$RUN/oauth-dev.json\").read() else 1)"'

echo "3) ningún valor en la salida ni en la línea de órdenes del stub"
store 'print("\n".join(v["Value"] for v in d.values() if len(v["Value"]) > 8))' >"$RUN/values.txt"
leak=0
while IFS= read -r value; do
  [ -z "$value" ] && continue
  case $value in \{*) value=GOCSPX-FAKEdevSECRETvalue123 ;; esac
  if grep -qF -- "$value" "$RUN/out.txt" "$RUN/argv.log"; then leak=1; fi
done <"$RUN/values.txt"
check "sin fugas de valores" '[ $leak = 0 ]'
check "solo --cli-input-json (nunca --value)" '! grep -q "\"--value\"" $RUN/argv.log'
tmp_docs_gone() {
  local p found=0
  for p in $(grep -o 'file://[^"]*' "$RUN/argv.log" | sed 's|^file://||' | sort -u); do
    found=1
    [ -e "$p" ] && return 1
  done
  [ $found = 1 ]
}
check "documento temporal 0600 en carpeta 0700 y borrado al terminar" 'tmp_docs_gone'

echo "4) re-ejecución idempotente"
run $COMMON --apply --yes
check "re-ejecución sale con 0" '[ "$(cat $RUN/rc)" = 0 ]'
check "nada que escribir" 'grep -q "Nada que escribir" $RUN/out.txt'
check "versiones siguen en 1" '[ "$(store "print(max(v[\"Version\"] for v in d.values()))")" = 1 ]'

echo "5) --force sobrescribe lo aportado pero NO regenera claves sin --only"
KEY1=$(store 'print(d["/uonify/dev/run/encryption-key"]["Value"])')
run $COMMON --apply --yes --force
check "force sale con 0" '[ "$(cat $RUN/rc)" = 0 ]'
check "oauth pasa a v2" '[ "$(store "print(d[\"/uonify/dev/run/google-oauth.json\"][\"Version\"])")" = 2 ]'
check "encryption-key intacta (v1)" '[ "$(store "print(d[\"/uonify/dev/run/encryption-key\"][\"Version\"])")" = 1 ]'
check "encryption-key mismo valor" '[ "$(store "print(d[\"/uonify/dev/run/encryption-key\"][\"Value\"])")" = "$KEY1" ]'

echo "6) --force --only encryption-key regenera solo esa clave"
run --local-dir "$RUN/local" --apply --yes --force --only encryption-key
check "regenerar sale con 0" '[ "$(cat $RUN/rc)" = 0 ]'
check "encryption-key v2 y distinta" '[ "$(store "print(d[\"/uonify/dev/run/encryption-key\"][\"Version\"])")" = 2 ] && [ "$(store "print(d[\"/uonify/dev/run/encryption-key\"][\"Value\"])")" != "$KEY1" ]'
check "avisa del riesgo" 'grep -q "rompe el descifrado" $RUN/out.txt'
check "postgres-password intacta" '[ "$(store "print(d[\"/uonify/dev/run/postgres-password\"][\"Version\"])")" = 1 ]'

echo "7) --extra-file y secreto de borde"
run --local-dir "$RUN/local" --extra-file "adk-pilot-users.json=$RUN/adk.json" --with-edge-secret --apply --yes
check "extra sale con 0" '[ "$(cat $RUN/rc)" = 0 ]'
check "lista piloto creada" '[ "$(store "print(d[\"/uonify/dev/run/adk-pilot-users.json\"][\"Version\"])")" = 1 ]'
check "secreto de borde de 64 caracteres url-safe" '[ "$(store "import re; print(bool(re.fullmatch(\"[A-Za-z0-9_-]{64}\", d[\"/uonify/dev/edge/origin-verify\"][\"Value\"])))")" = True ]'
EDGE=$(store 'print(d["/uonify/dev/edge/origin-verify"]["Value"])')
check "secreto de borde no aparece en la salida" '! grep -qF -- "$EDGE" $RUN/out.txt $RUN/argv.log'

echo "8) rechazos sin escribir nada"
cp "$RUN/store.json" "$RUN/store.before"
run --local-dir "$RUN/local" --oauth-json "$RUN/oauth-nocallback.json" --only google-oauth.json --force --apply --yes
check "JSON sin la URI de DEV: sale con error" '[ "$(cat $RUN/rc)" != 0 ] && grep -q "redirect_uris no incluye" $RUN/out.txt'
run --local-dir "$RUN/local" --extra-file "jev-api-key=$RUN/adk.json" --apply --yes
check "jev-api-key rechazado" '[ "$(cat $RUN/rc)" != 0 ] && grep -q "excluido de DEV" $RUN/out.txt'
run --local-dir "$RUN/local" --extra-file "encryption-key=$RUN/adk.json" --apply --yes
check "nombre reservado rechazado" '[ "$(cat $RUN/rc)" != 0 ]'
FAKE_ACCOUNT=111111111111 run $COMMON --apply --yes
check "otra cuenta rechazada" '[ "$(cat $RUN/rc)" != 0 ] && grep -q "no de 277352717693" $RUN/out.txt'
FAKE_CLI_HISTORY=enabled run $COMMON --apply --yes
check "cli_history activado: rechazado" '[ "$(cat $RUN/rc)" != 0 ] && grep -q "cli_history" $RUN/out.txt'
/bin/bash -x "$SCRIPT" $COMMON >"$RUN/out.txt" 2>&1; echo $? >"$RUN/rc"
check "xtrace rechazado" '[ "$(cat $RUN/rc)" = 2 ] && grep -q "xtrace" $RUN/out.txt'
printf 'mk_live_NOPE\n' >"$RUN/bad-key"; mkdir -p "$RUN/local2"; cp "$RUN/bad-key" "$RUN/local2/stripe-test-key"
run --local-dir "$RUN/local2" --only stripe-test-key --force --apply --yes
check "clave de Stripe no de pruebas rechazada" '[ "$(cat $RUN/rc)" != 0 ] && grep -q "clave de PRUEBAS" $RUN/out.txt && ! grep -q mk_live_NOPE $RUN/out.txt'
check "el almacén no cambió con los rechazos" 'cmp -s $RUN/store.json $RUN/store.before'

echo "9) cliente OAuth NUEVO: nunca el del entorno local, ni con --skip-oauth-uri-check"
: >"$RUN/oauth-all-out.txt"
oauth_run() { run "$@"; cat "$RUN/out.txt" >>"$RUN/oauth-all-out.txt"; }
oauth_run --local-dir "$RUN/local" --oauth-json "$RUN/oauth-local.json" --only google-oauth.json --force --skip-oauth-uri-check --apply --yes
check "JSON del cliente local + --skip-oauth-uri-check: rechazado" '[ "$(cat $RUN/rc)" != 0 ] && grep -q "MISMO cliente OAuth" $RUN/out.txt'
python3 -I - "$RUN/oauth-local.json" "$RUN/oauth-local-plus-dev.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d['web']['redirect_uris'].append('https://dev.uonify.com/api/auth/google/callback')
d['web']['javascript_origins'].append('https://dev.uonify.com')
json.dump(d, open(sys.argv[2], 'w'))
PY
oauth_run --local-dir "$RUN/local" --oauth-json "$RUN/oauth-local-plus-dev.json" --only google-oauth.json --force --apply --yes
check "cliente local con la URI de DEV añadida: rechazado (mismo client_id)" '[ "$(cat $RUN/rc)" != 0 ] && grep -q "MISMO cliente OAuth" $RUN/out.txt'
cat >"$RUN/oauth-other-local.json" <<'EOF'
{"web":{"client_id":"555555555555-otherlocalclient.apps.googleusercontent.com","client_secret":"GOCSPX-FAKEotherLOCAL1","redirect_uris":["http://localhost:5173/api/auth/google/callback","http://127.0.0.1:5173/api/auth/google/callback"]}}
EOF
oauth_run --local-dir "$RUN/local" --oauth-json "$RUN/oauth-other-local.json" --only google-oauth.json --force --skip-oauth-uri-check --apply --yes
check "otro cliente con TODAS las URI locales + skip: rechazado" '[ "$(cat $RUN/rc)" != 0 ] && grep -q "todas sus URI de vuelta son locales" $RUN/out.txt'
cat >"$RUN/oauth-dev-nouri.json" <<EOF
{"web":{"client_id":"$DEV_ID","client_secret":"GOCSPX-FAKEdevSECRETvalue123","javascript_origins":["https://dev.uonify.com"]}}
EOF
oauth_run --local-dir "$RUN/local" --oauth-json "$RUN/oauth-dev-nouri.json" --only google-oauth.json --force --skip-oauth-uri-check
check "cliente NUEVO sin URI en el JSON + skip (la añadió después): pasa con aviso" '[ "$(cat $RUN/rc)" = 0 ] && grep -q "comprobación saltada" $RUN/out.txt && grep -q "OK    google-oauth.json" $RUN/out.txt'
mkdir -p "$RUN/local3"; cp "$RUN/local/stripe-test-key" "$RUN/local/stripe-test-publishable-key" "$RUN/local3/"
printf 'esto no es JSON' >"$RUN/local3/google-oauth.json"
oauth_run --local-dir "$RUN/local3" --oauth-json "$RUN/oauth-dev.json" --only google-oauth.json --force --apply --yes
check "google-oauth.json local ilegible: rechazado (no puede comparar)" '[ "$(cat $RUN/rc)" != 0 ] && grep -q "no puedo leer el client_id" $RUN/out.txt'
mkdir -p "$RUN/local4"; cp "$RUN/local/stripe-test-key" "$RUN/local/stripe-test-publishable-key" "$RUN/local4/"
oauth_run --local-dir "$RUN/local4" --oauth-json "$RUN/oauth-dev.json" --only google-oauth.json --force
check "sin google-oauth.json local: avisa de que no puede comparar" '[ "$(cat $RUN/rc)" = 0 ] && grep -q "no puedo comparar el client_id" $RUN/out.txt'
check "ningún client_id ni client_secret en la salida" '! grep -Eq "$DEV_ID|$LOCAL_ID|555555555555-other|GOCSPX-" "$RUN/oauth-all-out.txt"'
check "el almacén no cambió" 'cmp -s $RUN/store.json $RUN/store.before'

echo "10) listas piloto: mismas reglas que pilot_users() de app/settings.py (corpus compartido)"
python3 -I "$HERE/pilot_cases.py" write "$RUN/pilots" >"$RUN/pilots.idx"
: >"$RUN/pilot-out.txt"
total=0; mismatch=0
TAB=$(printf '\t')
while IFS=$TAB read -r idx pname pvalid plabel; do
  total=$((total + 1))
  FAKE_AWS_STORE="$RUN/store-pilot.json" run --local-dir "$RUN/local" --only stripe-test-vat21 \
    --extra-file "$pname=$RUN/pilots/$idx.json" </dev/null
  rm -f "$RUN/store-pilot.json"
  got=1; [ "$(cat "$RUN/rc")" = 0 ] || got=0
  if [ "$got" != "$pvalid" ]; then
    mismatch=$((mismatch + 1)); echo "     discrepancia: $plabel ($pname): esperado $pvalid, obtenido $got"
  fi
  cat "$RUN/out.txt" >>"$RUN/pilot-out.txt"
done <"$RUN/pilots.idx"
check "$total casos: el validador coincide con settings.py en todos" '[ $mismatch = 0 ] && [ $total -ge 30 ]'
check "explica el motivo sin mostrar el contenido" 'grep -q "rechazarían al arrancar: sessionLimit debe ser un entero entre 1 y 200" "$RUN/pilot-out.txt" && ! grep -Eq "11111111-2222|66666666-7777" "$RUN/pilot-out.txt"'
bad=$(awk -F"$TAB" '$4 == "live límite 0" { print $1 }' "$RUN/pilots.idx")
run --local-dir "$RUN/local" --only stripe-test-vat21 --extra-file "live-pilot-users.json=$RUN/pilots/$bad.json" --force --apply --yes
check "lista no válida con --apply --force: rechazada y nada escrito" '[ -n "$bad" ] && [ "$(cat $RUN/rc)" != 0 ] && cmp -s $RUN/store.json $RUN/store.before'

echo
echo "RESULTADO upload_dev_secrets.sh (bash $(/bin/bash -c 'echo $BASH_VERSION')): $PASS ok, $FAILS fallos"
[ $FAILS = 0 ]
