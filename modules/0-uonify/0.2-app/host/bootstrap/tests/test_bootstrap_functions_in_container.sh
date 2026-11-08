#!/bin/bash
# Se ejecuta DENTRO de un contenedor desechable (root, --network none) lanzado por
# run_bootstrap_functions_test.sh. Carga bootstrap.sh con «source» (no ejecuta ningún paso) y prueba
# funciones sueltas con entradas sintéticas: verificación del estado de gpg, localización del volumen
# por su id de EBS (árboles /dev y /sys FALSOS), install_file idempotente y el bloqueo de arranques.
set -u
PASS=0; FAILS=0
ok() { PASS=$((PASS + 1)); echo "  ok   $*"; }
ko() { FAILS=$((FAILS + 1)); echo "  FAIL $*"; }
check() { if eval "$2"; then ok "$1"; else ko "$1"; fi; }
# shellcheck source=/dev/null
source /b/bootstrap/bootstrap.sh
set +e
trap - ERR

FPR=FB5DB77FD5C118B80511ADA8A6310ACC4672475C
OTHER=0000000000000000000000000000000000000000
valid="[GNUPG:] NEWSIG
[GNUPG:] KEY_CONSIDERED $FPR 0
[GNUPG:] SIG_ID abc 2026-08-28 1787941445
[GNUPG:] GOODSIG A6310ACC4672475C AWS CLI Team <aws-cli@amazon.com>
[GNUPG:] VALIDSIG $FPR 2026-08-28 1787941445 0 4 0 1 10 00 $FPR
[GNUPG:] TRUST_UNDEFINED 0 pgp"
expired=${valid/GOODSIG/EXPKEYSIG}
echo "1) check_gpg_status"
check "GOODSIG + VALIDSIG de la huella: acepta" 'check_gpg_status "$valid" "$FPR"'
check "EXPKEYSIG + VALIDSIG de la huella: acepta" 'check_gpg_status "$expired" "$FPR"'
check "VALIDSIG de otra huella: rechaza" '! check_gpg_status "${valid//$FPR/$OTHER}" "$FPR"'
check "BADSIG: rechaza" '! check_gpg_status "$(printf "%s\n%s" "$valid" "[GNUPG:] BADSIG A6310ACC4672475C x")" "$FPR"'
check "ERRSIG: rechaza" '! check_gpg_status "[GNUPG:] ERRSIG A6310ACC4672475C 1 10 00 1787941445 9" "$FPR"'
check "REVKEYSIG: rechaza" '! check_gpg_status "${valid/GOODSIG/REVKEYSIG}" "$FPR"'
check "sin VALIDSIG: rechaza" '! check_gpg_status "$(grep -v VALIDSIG <<<"$valid")" "$FPR"'
check "vacío: rechaza" '! check_gpg_status "" "$FPR"'

echo "2) find_data_device con árboles falsos"
F=/tmp/fakedev; rm -rf "$F"; mkdir -p "$F/by-id" "$F/sys/nvme0n1/device" "$F/sys/nvme1n1/device" "$F/sys/nvme2n1/device" "$F/dev"
touch "$F/dev/nvme1n1" "$F/dev/nvme2n1"
printf 'vol0aaaaaaaaaaaaaaaa \n' >"$F/sys/nvme0n1/device/serial"
printf 'vol0bbbbbbbbbbbbbbbb \n' >"$F/sys/nvme1n1/device/serial"
printf 'vol0cccccccccccccccc \n' >"$F/sys/nvme2n1/device/serial"
ln -s "$F/dev/nvme2n1" "$F/by-id/nvme-Amazon_Elastic_Block_Store_vol0cccccccccccccccc"
BY_ID_DIR=$F/by-id SYS_BLOCK_DIR=$F/sys
DATA_VOLUME_ID=vol-0cccccccccccccccc
check "por enlace de udev (vol- -> vol)" '[ "$(find_data_device)" = "$F/dev/nvme2n1" ]'
DATA_VOLUME_ID=vol-0bbbbbbbbbbbbbbbb
check "sin enlace: por el serial de sysfs (no por orden de nombres)" '[ "$(find_data_device)" = /dev/nvme1n1 ]'
DATA_VOLUME_ID=vol-0dddddddddddddddd
check "volumen no adjunto: falla" '! find_data_device >/dev/null'
BY_ID_DIR=/dev/disk/by-id SYS_BLOCK_DIR=/sys/block

echo "3) install_file idempotente"
TMP_ROOT=$(mktemp -d); CHANGED=()
printf 'a\n' >"$TMP_ROOT/src"
install_file "$TMP_ROOT/src" "$TMP_ROOT/out/dst" 0640 >/dev/null
check "primera vez instala con modo y dueño" '[ "$(stat -c "%a %U %G" "$TMP_ROOT/out/dst")" = "640 root root" ] && [ ${#CHANGED[@]} = 1 ]'
install_file "$TMP_ROOT/src" "$TMP_ROOT/out/dst" 0640 >/dev/null
check "segunda vez no cambia nada" '[ ${#CHANGED[@]} = 1 ]'
chmod 0644 "$TMP_ROOT/out/dst"
install_file "$TMP_ROOT/src" "$TMP_ROOT/out/dst" 0640 >/dev/null
check "corrige el modo si alguien lo cambió" '[ "$(stat -c %a "$TMP_ROOT/out/dst")" = 640 ] && [ ${#CHANGED[@]} = 2 ]'

echo "4) set_host_env (UONIFY_KMS_KEY_ARN en host.env)"
ARN=arn:aws:kms:eu-west-1:277352717693:key/11111111-2222-4333-8444-555555555555
ARN2=arn:aws:kms:eu-west-1:277352717693:key/99999999-8888-4777-8666-555555555555
HOST_ENV_FILE=$TMP_ROOT/host.env
install -m 0644 /b/bootstrap/files/host.env "$HOST_ENV_FILE"
LINES=$(wc -l <"$HOST_ENV_FILE")
set_host_env UONIFY_KMS_KEY_ARN "$ARN" >/dev/null
check "rellena la línea vacía de la plantilla, sin añadir ni quitar líneas" '[ "$(grep -c "^UONIFY_KMS_KEY_ARN=" "$HOST_ENV_FILE")" = 1 ] && grep -qx "UONIFY_KMS_KEY_ARN=$ARN" "$HOST_ENV_FILE" && [ "$(wc -l <"$HOST_ENV_FILE")" = "$LINES" ]'
check "el resto de host.env queda igual" '[ "$(grep -v "^UONIFY_KMS_KEY_ARN=" "$HOST_ENV_FILE")" = "$(grep -v "^UONIFY_KMS_KEY_ARN=" /b/bootstrap/files/host.env)" ]'
check "root 0644 (lo exige uonify-pg-backup al cargarlo)" '[ "$(stat -c "%a %U" "$HOST_ENV_FILE")" = "644 root" ]'
INODE=$(stat -c %i "$HOST_ENV_FILE")
set_host_env UONIFY_KMS_KEY_ARN "$ARN" >/dev/null
check "idempotente: mismo valor, no reescribe (mismo inodo)" '[ "$(stat -c %i "$HOST_ENV_FILE")" = "$INODE" ]'
set_host_env UONIFY_KMS_KEY_ARN "$ARN2" >/dev/null
check "cambia el valor si se pasa otro ARN" 'grep -qx "UONIFY_KMS_KEY_ARN=$ARN2" "$HOST_ENV_FILE" && [ "$(grep -c "^UONIFY_KMS_KEY_ARN=" "$HOST_ENV_FILE")" = 1 ]'
grep -v '^UONIFY_KMS_KEY_ARN=' "$HOST_ENV_FILE" >"$TMP_ROOT/h2"; cp "$TMP_ROOT/h2" "$HOST_ENV_FILE"
set_host_env UONIFY_KMS_KEY_ARN "$ARN" >/dev/null
check "la añade si un host.env antiguo no la tiene" '[ "$(tail -n 1 "$HOST_ENV_FILE")" = "UONIFY_KMS_KEY_ARN=$ARN" ]'
printf 'UONIFY_KMS_KEY_ARN=%s\n' "$ARN2" >>"$HOST_ENV_FILE"
set_host_env UONIFY_KMS_KEY_ARN "$ARN" >/dev/null
check "deja una sola línea si había repetidas" '[ "$(grep -c "^UONIFY_KMS_KEY_ARN=" "$HOST_ENV_FILE")" = 1 ] && grep -qx "UONIFY_KMS_KEY_ARN=$ARN" "$HOST_ENV_FILE"'
check "ningún temporal olvidado" '[ -z "$(ls "$TMP_ROOT" | grep "^host.env\.")" ]'
HOST_ENV_FILE=/etc/uonify/host.env

echo "5) with_no_service_start"
# Las imágenes Docker de Debian traen su propio policy-rc.d (los hosts Ubuntu de EC2, no): se aparta.
if [ -e /usr/sbin/policy-rc.d ]; then mv /usr/sbin/policy-rc.d /tmp/policy-rc.d.image; fi
check "policy-rc.d activo durante la orden y retirado después" 'with_no_service_start sh -c "[ -x /usr/sbin/policy-rc.d ] && /usr/sbin/policy-rc.d; [ \$? = 101 ]" && [ ! -e /usr/sbin/policy-rc.d ]'
check "propaga el código de error y limpia" '! with_no_service_start false && [ ! -e /usr/sbin/policy-rc.d ]'
printf '#!/bin/sh\nexit 0\n' >/usr/sbin/policy-rc.d; chmod 0755 /usr/sbin/policy-rc.d
check "respeta un policy-rc.d previo (no lo borra ni lo cambia)" 'with_no_service_start true && grep -q "exit 0" /usr/sbin/policy-rc.d'

echo "6) step_hardening (systemctl, usermod, id y ss simulados)"
CALLS=$(mktemp)
systemctl() { echo "systemctl $*" >>"$CALLS"; return 0; }
usermod() { echo "usermod $*" >>"$CALLS"; return 0; }
id() { if [ "${1:-}" = ubuntu ]; then return 0; fi; command id "$@"; }
ss() { return 0; }
step_hardening >/dev/null 2>&1
check "apaga y enmascara ssh.socket y ssh.service" 'grep -qx "systemctl disable --now ssh.socket ssh.service" "$CALLS" && grep -qx "systemctl mask ssh.socket ssh.service" "$CALLS"'
check "bloquea ubuntu y le quita la shell" 'grep -qx "usermod --lock --shell /usr/sbin/nologin ubuntu" "$CALLS"'
ss() { echo "LISTEN 0 4096 0.0.0.0:22 0.0.0.0:*"; }
check "si el 22 sigue escuchando, falla" '! ( step_hardening >/dev/null 2>&1 )'
: >"$CALLS"
id() { if [ "${1:-}" = ubuntu ]; then return 1; fi; command id "$@"; }
ss() { return 0; }
step_hardening >/dev/null 2>&1
check "sin usuario ubuntu no llama a usermod" '! grep -q "^usermod" "$CALLS"'
unset -f systemctl usermod id ss
rm -f "$CALLS"

echo
echo "RESULTADO funciones de bootstrap.sh (bash $BASH_VERSION): $PASS ok, $FAILS fallos"
[ $FAILS = 0 ]
