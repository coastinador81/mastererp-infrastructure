#!/bin/bash
# Se ejecuta DENTRO de un contenedor desechable (Debian, --network none, sin IMDS) lanzado por
# run_bootstrap_guards_test.sh. Comprueba que bootstrap.sh se para ANTES de tocar nada cuando faltan
# argumentos, el SO no es Ubuntu 24.04 o no hay IMDS (no es la EC2 del stack).
set -u
PASS=0; FAILS=0
ok() { PASS=$((PASS + 1)); echo "  ok   $*"; }
ko() { FAILS=$((FAILS + 1)); echo "  FAIL $*"; }
check() { if eval "$2"; then ok "$1"; else ko "$1"; fi; }
B=/b/bootstrap/bootstrap.sh
run() { bash "$B" "$@" >/tmp/out 2>&1; echo $? >/tmp/rc; }
# Como en Ubuntu: /run/lock es 1777 y nadie debe cambiarlo.
install -d /run/lock; chmod 1777 /run/lock
ARN=arn:aws:kms:eu-west-1:277352717693:key/11111111-2222-4333-8444-555555555555

run --help
check "--help sale con 0" '[ "$(cat /tmp/rc)" = 0 ] && grep -q "data-volume-id" /tmp/out'
run
check "sin --data-volume-id: error" '[ "$(cat /tmp/rc)" = 1 ] && grep -q "obligatorio" /tmp/out'
run --data-volume-id vol-XYZ
check "id de volumen mal formado: error" '[ "$(cat /tmp/rc)" = 1 ]'
run --data-volume-id vol-0123456789abcdef0 --acme-email no-es-correo
check "correo ACME mal formado: error" '[ "$(cat /tmp/rc)" = 1 ] && grep -q "no parece un correo" /tmp/out'
run --data-volume-id vol-0123456789abcdef0 --bogus
check "opción desconocida: error" '[ "$(cat /tmp/rc)" = 1 ]'
run --data-volume-id vol-0123456789abcdef0 --kms-key-arn alias/uonify-dev
check "--kms-key-arn con el alias: error" '[ "$(cat /tmp/rc)" = 1 ] && grep -q "no el alias" /tmp/out'
run --data-volume-id vol-0123456789abcdef0 --kms-key-arn arn:aws:kms:us-east-1:277352717693:key/11111111-2222-4333-8444-555555555555
check "--kms-key-arn de otra región: error" '[ "$(cat /tmp/rc)" = 1 ] && grep -q "no el alias" /tmp/out'
run --data-volume-id vol-0123456789abcdef0 --kms-key-arn "$ARN"
check "Debian (no Ubuntu 24.04): se para en preflight" '[ "$(cat /tmp/rc)" = 1 ] && grep -q "se esperaba Ubuntu 24.04" /tmp/out'
cp /etc/os-release /tmp/os-release.bak
printf 'ID=ubuntu\nVERSION_ID=24.04\n' >/etc/os-release
run --data-volume-id vol-0123456789abcdef0 --kms-key-arn "$ARN"
check "sin IMDS (no es la EC2): se para en preflight" '[ "$(cat /tmp/rc)" = 1 ] && grep -q "no hay IMDSv2" /tmp/out'
cp /tmp/os-release.bak /etc/os-release
check "no ha creado nada en el sistema" '[ ! -e /etc/apt/sources.list.d/docker.sources ] && [ ! -e /etc/uonify ] && [ ! -e /var/backups/uonify ] && ! grep -q /data /etc/fstab 2>/dev/null'
check "ni el cerrojo, y /run/lock sigue 1777" '[ ! -e /run/uonify-bootstrap.lock ] && [ ! -e /run/lock/uonify-bootstrap.lock ] && [ "$(stat -c %a /run/lock)" = 1777 ]'
echo
echo "RESULTADO guardas de bootstrap.sh: $PASS ok, $FAILS fallos"
[ $FAILS = 0 ]
