#!/usr/bin/env bash
# =====================================================================================================
# Uonify DEV · bootstrap del host (D-DEV-HOSTING-20261107)
# EC2 t4g.medium arm64 · Ubuntu 24.04 · eu-west-1 · stack uonify-dev-backend · sin SSH: solo por SSM.
#
# Uso (como root, por SSM Run Command o una sesión de Session Manager), desde el paquete desplegado
# con las carpetas hermanas secrets/ y bootstrap/. Lo más simple es el script único que genera
# make_host_bundle.sh (bootstrap/dist/uonify-dev-host-bundle.sh): comprueba su sha256, se extrae en
# /opt/uonify/bundle/<sha> y llama a este script con los mismos argumentos.
#   bash /opt/uonify/bundle/<sha>/bootstrap/bootstrap.sh --data-volume-id vol-0123456789abcdef0 \
#        --kms-key-arn arn:aws:kms:eu-west-1:277352717693:key/<id>
#   bash ... --data-volume-id vol-... --issue-cert [--acme-email correo]   # certificado del origen
#   bash ... --data-volume-id vol-... --cert-dry-run                        # ensayo DNS-01 (staging)
# El id del volumen y el ARN de la clave salen de las salidas DataVolumeId y KmsKeyArn del stack (el rol
# no puede describir volúmenes ni la clave). El ARN se guarda en /etc/uonify/host.env y basta pasarlo
# una vez: la copia nocturna comprueba con él que S3 cifró cada objeto con esa CMK.
#
# Idempotente y seguro de repetir: cada paso comprueba el estado antes de cambiar nada.
#   1. apt solo por HTTPS (https://ports.ubuntu.com/ubuntu-ports; no hay salida al puerto 80)
#   2. paquetes base, chrony contra Amazon Time Sync (169.254.169.123)
#   3. volumen de datos localizado por su ID de EBS (número de serie NVMe), nunca por orden de nombre;
#      ext4 SOLO si está en blanco; montado en /data por UUID; jamás toca el disco raíz
#   4. AWS CLI v2 de awscli.amazonaws.com con la firma PGP verificada contra la huella fijada
#   5. ficheros del host: servicio de secretos (tmpfs), hooks de certbot, copia nocturna de Postgres
#   5b. endurecimiento: ssh.socket y ssh.service apagados y enmascarados (sin SSH: solo SSM) y el
#      usuario ubuntu (uid 1000, dueño de /run/uonify) sin login
#   6. Docker CE 29.7.2 + containerd 2.3.3 + compose 5.4.0 (las versiones del Mac), almacén containerd,
#      amazon-ecr-credential-helper para uonify-dev/* en ECR
#   7. arranque: uonify-secrets (antes de Docker) y Docker; si faltan secretos, Docker NO arranca
#   8. certbot (DNS-01 en Route 53) solo con --issue-cert; renovación con certbot.timer
# No muestra secretos: los únicos que toca el host los maneja uonify-secrets-sync, que solo imprime
# nombres y versiones.
# =====================================================================================================
set -Eeuo pipefail
umask 022
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME="${HOME:-/root}"
export AWS_REGION=eu-west-1 AWS_DEFAULT_REGION=eu-west-1 AWS_PAGER="" AWS_CLI_AUTO_PROMPT=off
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_SUSPEND=1

readonly EXPECTED_ACCOUNT=277352717693
readonly EXPECTED_REGION=eu-west-1
readonly ORIGIN_FQDN=origin-dev.uonify.com
readonly ECR_REGISTRY=277352717693.dkr.ecr.eu-west-1.amazonaws.com
readonly DATA_MOUNT=/data
readonly DATA_LABEL=uonify-data
readonly DOCKER_ENGINE_VERSION=29.7.2
readonly DOCKER_APT_VERSION="5:29.7.2-1~ubuntu.24.04~noble"
readonly CONTAINERD_APT_VERSION="2.3.3-1~ubuntu.24.04~noble"
readonly COMPOSE_APT_VERSION="5.4.0-1~ubuntu.24.04~noble"
readonly COMPOSE_VERSION=5.4.0
readonly DOCKER_GPG_FPR=9DC858229FC7DD38854AE2D88D81803C0EBFCD88
readonly AWSCLI_VERSION=2.36.34
readonly AWSCLI_GPG_FPR=FB5DB77FD5C118B80511ADA8A6310ACC4672475C
# ARN de una clave KMS de una sola región (MultiRegion: false en el stack) de la cuenta y región del DEV.
readonly KMS_ARN_RE='^arn:aws:kms:eu-west-1:277352717693:key/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
readonly BASE_PACKAGES=(ca-certificates curl gnupg unzip openssl python3 chrony nvme-cli e2fsprogs
  util-linux certbot amazon-ecr-credential-helper)

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
BUNDLE_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd -P)
readonly SCRIPT_DIR BUNDLE_DIR
readonly FILES=$SCRIPT_DIR/files SECRETS=$BUNDLE_DIR/secrets RUNTIME=$BUNDLE_DIR/runtime
readonly RUNTIME_DIR=/opt/uonify/runtime COMPOSE_ENV_FILE=/etc/uonify/compose.env

BY_ID_DIR=/dev/disk/by-id
SYS_BLOCK_DIR=/sys/block
HOST_ENV_FILE=/etc/uonify/host.env
DATA_VOLUME_ID=""
KMS_KEY_ARN=""
ISSUE_CERT=0
CERT_DRY_RUN=0
ACME_EMAIL=""
SKIP_DOCKER_START=0
FORMAT_CONFIRM=""
CURRENT_STEP=inicio
CHANGED=()
UNITS_CHANGED=0
DAEMON_JSON_CHANGED=0
SECRETS_READY=0
TMP_ROOT=""

log() { printf '[uonify-bootstrap] %s\n' "$*"; }
warn() { printf '[uonify-bootstrap] AVISO: %s\n' "$*" >&2; }
die() { printf '[uonify-bootstrap] ERROR (%s): %s\n' "$CURRENT_STEP" "$*" >&2; exit 1; }
step() { CURRENT_STEP=$1; log "== $1: $2"; }
cleanup() { if [[ -n $TMP_ROOT ]]; then rm -rf "$TMP_ROOT"; fi; }
trap 'printf "[uonify-bootstrap] ERROR en la línea %s (paso %s)\n" "$LINENO" "$CURRENT_STEP" >&2' ERR
trap cleanup EXIT

usage() {
  cat <<'EOF'
Uso: bootstrap.sh --data-volume-id vol-XXXXXXXX [opciones]
  --data-volume-id ID  volumen de datos de EBS (salida DataVolumeId del stack). Obligatorio.
  --kms-key-arn ARN    ARN de la CMK (salida KmsKeyArn del stack, no el alias). Se guarda en
                       /etc/uonify/host.env; la copia nocturna comprueba que S3 cifró con ella.
  --issue-cert         emitir el certificado Let's Encrypt de origin-dev.uonify.com por DNS-01
                       (acepta los términos de Let's Encrypt; aprobado en el plan D-DEV-HOSTING)
  --acme-email CORREO  correo para la cuenta ACME (opcional)
  --cert-dry-run       ensayo DNS-01 contra el entorno staging de Let's Encrypt, sin guardar nada
  --skip-docker-start  instalar todo sin arrancar Docker
  --format-unrecognized-data-volume ID
                       confirma que el volumen ID (el mismo de --data-volume-id), sin sistema de
                       ficheros, particiones ni firmas, es nuevo y puede formatearse aunque no se lea
                       a ceros: un volumen EBS cifrado recién creado devuelve datos aleatorios en los
                       bloques nunca escritos. Comprobar ANTES fuera del host que VolumeWriteBytes del
                       volumen es 0 en CloudWatch desde su creación.
  -h, --help           esta ayuda
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case $1 in
      --data-volume-id) [[ $# -ge 2 ]] || die "falta el valor de --data-volume-id"; DATA_VOLUME_ID=$2; shift 2 ;;
      --kms-key-arn) [[ $# -ge 2 ]] || die "falta el valor de --kms-key-arn"; KMS_KEY_ARN=$2; shift 2 ;;
      --issue-cert) ISSUE_CERT=1; shift ;;
      --acme-email) [[ $# -ge 2 ]] || die "falta el valor de --acme-email"; ACME_EMAIL=$2; shift 2 ;;
      --cert-dry-run) CERT_DRY_RUN=1; shift ;;
      --skip-docker-start) SKIP_DOCKER_START=1; shift ;;
      --format-unrecognized-data-volume) [[ $# -ge 2 ]] || die "falta el valor de --format-unrecognized-data-volume"; FORMAT_CONFIRM=$2; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) usage >&2; die "opción desconocida: $1" ;;
    esac
  done
  [[ $DATA_VOLUME_ID =~ ^vol-[0-9a-f]{8,17}$ ]] || { usage >&2; die "--data-volume-id vol-... es obligatorio"; }
  if [[ -n $KMS_KEY_ARN && ! $KMS_KEY_ARN =~ $KMS_ARN_RE ]]; then
    die "--kms-key-arn debe ser la salida KmsKeyArn del stack (arn:aws:kms:eu-west-1:277352717693:key/<id>), no el alias"
  fi
  if [[ -n $ACME_EMAIL && ! $ACME_EMAIL =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; then
    die "--acme-email no parece un correo"
  fi
}

# ------------------------------------------------------------------------------------------- utilidades
apt_get() {
  apt-get -y -q -o DPkg::Lock::Timeout=600 -o Acquire::Retries=5 \
    -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold "$@"
}

apt_update() {
  # Error-Mode=any: si alguna fuente falla (p. ej. un espejo por http), apt-get update falla.
  apt_get -o APT::Update::Error-Mode=any update
}

fetch() { # url destino
  curl --proto '=https' --tlsv1.2 -fsSL --retry 5 --retry-delay 3 --connect-timeout 20 -o "$2" "$1"
}

install_file() { # origen destino modo [propietario grupo]
  local src=$1 dst=$2 mode=$3 owner=${4:-root} group=${5:-root}
  [[ -f $src ]] || die "falta $src en el paquete"
  if [[ -f $dst ]] && cmp -s "$src" "$dst" \
      && [[ $(stat -c '%a %U %G' "$dst") == "${mode#0} $owner $group" ]]; then
    return 0
  fi
  install -D -m "$mode" -o "$owner" -g "$group" "$src" "$dst"
  CHANGED+=("$dst")
  log "instalado $dst"
}

imds() { # ruta
  local token
  token=$(curl -fsS -m 5 -X PUT http://169.254.169.254/latest/api/token \
    -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')
  curl -fsS -m 5 -H "X-aws-ec2-metadata-token: ${token}" "http://169.254.169.254/latest/$1"
}

with_no_service_start() { # orden...
  local created=0 rc=0
  if [[ ! -e /usr/sbin/policy-rc.d ]]; then
    printf '#!/bin/sh\n# uonify-bootstrap: no arrancar servicios durante la instalación\nexit 101\n' >/usr/sbin/policy-rc.d
    chmod 0755 /usr/sbin/policy-rc.d
    created=1
  fi
  "$@" || rc=$?
  if (( created )); then rm -f /usr/sbin/policy-rc.d; fi
  return "$rc"
}

pkg_version() { dpkg-query -W -f='${Version}' "$1" 2>/dev/null || true; }

# Fija CLAVE=valor en host.env: sustituye la primera línea CLAVE=... (y quita repeticiones) o la añade.
# Solo valores ya validados por quien llama (sin espacios, comillas ni barras invertidas). Atómico.
set_host_env() { # clave valor
  local key=$1 value=$2 tmp
  if [[ $(grep -c "^${key}=" "$HOST_ENV_FILE" || true) -eq 1 ]] && grep -qxF -- "${key}=${value}" "$HOST_ENV_FILE"; then
    return 0
  fi
  tmp=$(mktemp "${HOST_ENV_FILE}.XXXXXX")
  awk -v k="$key" -v v="$value" '
    index($0, k "=") == 1 { if (!done) print k "=" v; done = 1; next }
    { print }
    END { if (!done) print k "=" v }' "$HOST_ENV_FILE" >"$tmp"
  chmod 0644 "$tmp"
  mv -f -- "$tmp" "$HOST_ENV_FILE"
  log "$HOST_ENV_FILE: ${key}=${value}"
}

# Salida de `gpg --status-fd 1 --verify`: exige firma criptográficamente válida (VALIDSIG) de la huella
# fijada y GOODSIG o EXPKEYSIG (la copia de la clave puede tener una autofirma de caducidad antigua;
# la huella es el ancla de confianza). Rechaza BADSIG, ERRSIG, REVKEYSIG, EXPSIG y NO_PUBKEY.
check_gpg_status() { # salida_status huella
  local status=$1 fpr=$2
  if grep -Eq '^\[GNUPG:\] (BADSIG|ERRSIG|REVKEYSIG|EXPSIG|NO_PUBKEY) ' <<<"$status"; then
    return 1
  fi
  grep -Eq '^\[GNUPG:\] (GOODSIG|EXPKEYSIG) ' <<<"$status" || return 1
  awk '$1 == "[GNUPG:]" && $2 == "VALIDSIG" { print $3; print $NF }' <<<"$status" | grep -qx "$fpr"
}

bundle_digest() {
  (cd "$BUNDLE_DIR" && find secrets bootstrap -type f ! -path '*/tests/*' ! -path '*/dist/*' \
    ! -name 'upload_dev_secrets.sh' ! -name 'make_host_bundle.sh' ! -name '.*' -print0 \
    | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)
}

# ---------------------------------------------------------------------------------------------- pasos
step_preflight() {
  step preflight "comprobaciones previas"
  [[ $EUID -eq 0 ]] || die "hay que ejecutarlo como root"
  # shellcheck source=/dev/null
  . /etc/os-release
  [[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 24.04 ]] || die "se esperaba Ubuntu 24.04 (hay ${ID:-?} ${VERSION_ID:-?})"
  [[ $(dpkg --print-architecture) == arm64 ]] || die "se esperaba arm64"
  local f
  for f in "$SECRETS/uonify-secrets.service" "$SECRETS/uonify-secrets-sync.sh" \
      "$SECRETS/uonify_secrets_render.py" "$FILES/aws-cli-team-pubkey.asc" "$FILES/ubuntu.sources" \
      "$FILES/docker.sources" "$FILES/docker-daemon.json" "$FILES/docker-10-uonify.conf" \
      "$FILES/uonify-acme-route53.sh" "$FILES/uonify-cert-deploy.sh" "$FILES/uonify-pg-backup.sh" \
      "$FILES/uonify-pg-backup.service" "$FILES/uonify-pg-backup.timer" "$FILES/host.env" \
      "$FILES/uonify-amazon-time-sync.sources" "$FILES/99-uonify-apt-https.cfg"; do
    [[ -f $f ]] || die "paquete incompleto: falta $f"
  done
  local identity account region instance arch
  identity=$(imds dynamic/instance-identity/document) || die "no hay IMDSv2: ¿es la EC2 del stack?"
  read -r account region instance arch < <(python3 -I -c '
import json, sys
d = json.load(sys.stdin)
print(d["accountId"], d["region"], d["instanceId"], d["architecture"])' <<<"$identity")
  [[ $account == "$EXPECTED_ACCOUNT" && $region == "$EXPECTED_REGION" ]] \
    || die "esta instancia es de la cuenta $account en $region; se esperaba $EXPECTED_ACCOUNT en $EXPECTED_REGION"
  [[ $arch == arm64 ]] || die "arquitectura $arch; se esperaba arm64"
  # Hasta aquí no se ha escrito nada. El cerrojo va en /run (root 0755), no en /run/lock (tmpfs 1777
  # de Ubuntu que usan otros programas; no se le cambia el modo).
  exec 8>/run/uonify-bootstrap.lock
  flock -n 8 || die "ya hay otro bootstrap en curso"
  TMP_ROOT=$(mktemp -d)
  log "instancia $instance · cuenta $account · $region · paquete $(bundle_digest)"
}

step_apt_https() {
  step apt "fuentes de apt solo por HTTPS"
  install -d -m 0755 /var/backups/uonify
  if ! cmp -s "$FILES/ubuntu.sources" /etc/apt/sources.list.d/ubuntu.sources; then
    if [[ -f /etc/apt/sources.list.d/ubuntu.sources && ! -f /var/backups/uonify/ubuntu.sources.orig ]]; then
      cp -p /etc/apt/sources.list.d/ubuntu.sources /var/backups/uonify/ubuntu.sources.orig
    fi
  fi
  install_file "$FILES/ubuntu.sources" /etc/apt/sources.list.d/ubuntu.sources 0644
  if [[ -f /etc/apt/sources.list ]] && grep -Eq '^[[:space:]]*deb(-src)?[[:space:]]' /etc/apt/sources.list; then
    [[ -f /var/backups/uonify/sources.list.orig ]] || cp -p /etc/apt/sources.list /var/backups/uonify/sources.list.orig
    printf '# Uonify DEV: las fuentes están en /etc/apt/sources.list.d/ubuntu.sources (solo HTTPS).\n' >/etc/apt/sources.list
    log "sources.list antiguo desactivado (copia en /var/backups/uonify)"
  fi
  install_file "$FILES/99-uonify-apt-https.cfg" /etc/cloud/cloud.cfg.d/99-uonify-apt-https.cfg 0644
  if grep -RsnE '^[[:space:]]*(deb(-src)?[[:space:]].*http://|URIs:.*http://)' \
      /etc/apt/sources.list /etc/apt/sources.list.d/ >&2; then
    die "quedan fuentes de apt por http:// (arriba): sin salida al puerto 80 fallarían"
  fi
  apt_update
}

step_base_packages() {
  step paquetes "paquetes base"
  apt_get install --no-install-recommends "${BASE_PACKAGES[@]}"
}

step_chrony() {
  step hora "chrony contra Amazon Time Sync (169.254.169.123)"
  local changed=0 f
  install_file "$FILES/uonify-amazon-time-sync.sources" /etc/chrony/sources.d/uonify-amazon-time-sync.sources 0644
  [[ ${CHANGED[*]:-} == *uonify-amazon-time-sync.sources* ]] && changed=1
  for f in /etc/chrony/chrony.conf /etc/chrony/sources.d/*.sources; do
    [[ -f $f && $f != */uonify-amazon-time-sync.sources ]] || continue
    if grep -Eq '^[[:space:]]*(pool|server|peer)[[:space:]]' "$f"; then
      sed -i -E 's/^([[:space:]]*)(pool|server|peer)([[:space:]])/\1#uonify-off# \2\3/' "$f"
      log "fuentes NTP públicas desactivadas en $f (no hay salida UDP 123)"
      changed=1
    fi
  done
  systemctl enable chrony.service >/dev/null 2>&1 || true
  if (( changed )) || ! systemctl is-active --quiet chrony.service; then
    systemctl restart chrony.service
  fi
  local i
  for i in $(seq 1 45); do
    if chronyc -n sources 2>/dev/null | grep -Eq '^\^\*[[:space:]]+169\.254\.169\.123'; then
      log "hora sincronizada con 169.254.169.123"
      return 0
    fi
    sleep 2
  done
  warn "chrony aún no ha seleccionado 169.254.169.123 (revisa: chronyc sources). Sigo."
}

# En Nitro el número de serie NVMe de un volumen EBS es su id sin guion (vol0123...). Se busca primero
# el enlace de udev y, si no está, el serial en sysfs. Nunca por orden de nombres (nvme1n1...).
find_data_device() {
  local serial="vol${DATA_VOLUME_ID#vol-}" link s
  link="$BY_ID_DIR/nvme-Amazon_Elastic_Block_Store_${serial}"
  udevadm settle -t 30 >/dev/null 2>&1 || true
  if [[ -e $link ]]; then
    readlink -f "$link"
    return 0
  fi
  for s in "$SYS_BLOCK_DIR"/nvme*/device/serial; do
    [[ -r $s ]] || continue
    if [[ $(tr -d '[:space:]' <"$s") == "$serial" ]]; then
      printf '/dev/%s\n' "$(basename "$(dirname "$(dirname "$s")")")"
      return 0
    fi
  done
  return 1
}

step_data_volume() {
  step datos "volumen de datos $DATA_VOLUME_ID en $DATA_MOUNT"
  local dev root_src root_parent root_disk where fstype label uuid line existing size
  dev=$(find_data_device) || die "no encuentro el volumen $DATA_VOLUME_ID: ¿está adjunto a esta instancia?"
  [[ -b $dev ]] || die "$dev no es un dispositivo de bloques"
  [[ $(lsblk -dn -o TYPE "$dev") == disk ]] || die "$dev no es un disco completo"
  root_src=$(findmnt -n -o SOURCE /)
  root_parent=$(lsblk -n -o PKNAME "$root_src" 2>/dev/null | head -n 1 || true)
  root_disk=/dev/${root_parent:-$(basename "$root_src")}
  [[ $(readlink -f "$dev") != "$(readlink -f "$root_disk")" ]] \
    || die "$DATA_VOLUME_ID resuelve al disco RAÍZ ($dev): no lo toco"
  [[ $(lsblk -n -o NAME "$dev" | wc -l) -eq 1 ]] || die "$dev tiene particiones: no lo toco"
  where=$(findmnt -n -o TARGET -S "$dev" | head -n 1 || true)
  [[ -z $where || $where == "$DATA_MOUNT" ]] || die "$dev ya está montado en $where"
  size=$(lsblk -bdn -o SIZE "$dev")
  log "volumen $DATA_VOLUME_ID -> $dev ($(( size / 1024 / 1024 / 1024 )) GiB)"

  fstype=$(blkid -p -o value -s TYPE "$dev" 2>/dev/null || true)
  label=$(blkid -p -o value -s LABEL "$dev" 2>/dev/null || true)
  if [[ -z $fstype ]]; then
    [[ -z $(wipefs --noheadings --output TYPE "$dev" 2>/dev/null) ]] \
      || die "$dev tiene firmas que no reconozco: no lo formateo"
    if ! cmp -s -n 1048576 "$dev" /dev/zero; then
      # Un volumen EBS CIFRADO recién creado no se lee a ceros: los bloques nunca escritos devuelven
      # datos aleatorios (visto el 07-11-2026: 0 bytes escritos en CloudWatch y todo el disco con
      # datos aleatorios salvo el bloque 0). Sin firmas ni particiones, solo se formatea con la
      # confirmación expresa del operador, que antes ha comprobado VolumeWriteBytes=0 fuera del host.
      [[ -n $FORMAT_CONFIRM && $FORMAT_CONFIRM == "$DATA_VOLUME_ID" ]] \
        || die "$dev no está en blanco y no reconozco su formato: no lo formateo (si es un volumen nuevo y VolumeWriteBytes es 0 en CloudWatch desde su creación, repite con --format-unrecognized-data-volume $DATA_VOLUME_ID)"
      warn "$dev no se lee a ceros y no tiene firmas ni particiones: se formatea por confirmación expresa del operador ($FORMAT_CONFIRM)"
    fi
    log "formateando $dev (en blanco) como ext4 con etiqueta $DATA_LABEL"
    mkfs.ext4 -q -L "$DATA_LABEL" -m 1 "$dev"
    udevadm settle -t 30 >/dev/null 2>&1 || true
    fstype=$(blkid -p -o value -s TYPE "$dev")
    label=$(blkid -p -o value -s LABEL "$dev")
  fi
  [[ $fstype == ext4 && $label == "$DATA_LABEL" ]] \
    || die "$dev tiene ${fstype:-?}/${label:-sin etiqueta}: no es el volumen de datos de Uonify, no lo toco"
  uuid=$(blkid -p -o value -s UUID "$dev")
  [[ $uuid =~ ^[0-9a-f-]{36}$ ]] || die "UUID inesperado en $dev"

  line="UUID=$uuid $DATA_MOUNT ext4 defaults,noatime,nosuid,nodev,nofail,x-systemd.device-timeout=30s 0 2"
  existing=$(awk -v m="$DATA_MOUNT" '$1 !~ /^#/ && $2 == m' /etc/fstab)
  if [[ -z $existing ]]; then
    cp -p /etc/fstab "/var/backups/uonify/fstab.$(date -u +%Y%m%dT%H%M%SZ)"
    printf '# Uonify DEV: volumen de datos %s (Postgres). nofail: Docker exige el montaje.\n%s\n' \
      "$DATA_VOLUME_ID" "$line" >>/etc/fstab
    systemctl daemon-reload
    log "añadido a /etc/fstab por UUID"
  elif [[ $existing != "UUID=$uuid "* ]]; then
    die "/etc/fstab ya tiene otra entrada para $DATA_MOUNT: $existing"
  fi

  if ! mountpoint -q "$DATA_MOUNT"; then
    [[ -d $DATA_MOUNT ]] || install -d -m 0755 "$DATA_MOUNT"
    # Con el volumen desmontado, el directorio del disco raíz queda inmutable: nada puede escribir
    # ahí por error (p. ej. un bind mount de Postgres creando una BD vacía en el disco raíz).
    if [[ -z $(ls -A "$DATA_MOUNT") ]]; then
      chattr +i "$DATA_MOUNT" 2>/dev/null || warn "no pude marcar $DATA_MOUNT como inmutable"
    fi
    mount "$DATA_MOUNT"
  fi
  [[ $(readlink -f "$(findmnt -n -o SOURCE "$DATA_MOUNT")") == "$(readlink -f "$dev")" ]] \
    || die "$DATA_MOUNT no está montado desde $dev"
  install -d -m 0700 -o 70 -g 70 "$DATA_MOUNT/postgres"
  install -d -m 0700 -o 999 -g 999 "$DATA_MOUNT/redis"
  log "$DATA_MOUNT listo: postgres/ (70:70 0700), redis/ (999:999 0700)"
}

step_awscli() {
  step awscli "AWS CLI v2 $AWSCLI_VERSION con firma verificada"
  if [[ ! -f /root/.aws/config ]]; then
    install -d -m 0700 /root/.aws
    printf '[default]\nregion = %s\n' "$EXPECTED_REGION" >/root/.aws/config
  fi
  if [[ -x /usr/local/bin/aws ]] && /usr/local/bin/aws --version 2>/dev/null | grep -q "^aws-cli/${AWSCLI_VERSION} "; then
    log "AWS CLI $AWSCLI_VERSION ya instalada"
    return 0
  fi
  local dir=$TMP_ROOT/awscli url status primary
  install -d -m 0700 "$dir" "$dir/gnupg"
  url="https://awscli.amazonaws.com/awscli-exe-linux-aarch64-${AWSCLI_VERSION}.zip"
  fetch "$url" "$dir/awscliv2.zip"
  fetch "$url.sig" "$dir/awscliv2.zip.sig"
  gpg --batch --quiet --homedir "$dir/gnupg" --import "$FILES/aws-cli-team-pubkey.asc" 2>/dev/null
  primary=$(gpg --batch --homedir "$dir/gnupg" --with-colons --list-keys 2>/dev/null \
    | awk -F: '$1 == "pub" { p = 1; next } $1 == "fpr" && p { print $10; exit }')
  [[ $primary == "$AWSCLI_GPG_FPR" ]] || die "la clave pública de la AWS CLI del paquete no tiene la huella fijada"
  status=$(gpg --batch --homedir "$dir/gnupg" --status-fd 1 --verify "$dir/awscliv2.zip.sig" \
    "$dir/awscliv2.zip" 2>/dev/null || true)
  gpgconf --homedir "$dir/gnupg" --kill all >/dev/null 2>&1 || true
  check_gpg_status "$status" "$AWSCLI_GPG_FPR" || die "la firma del instalador de la AWS CLI NO es válida"
  if grep -q '^\[GNUPG:\] EXPKEYSIG ' <<<"$status"; then
    log "firma válida de la clave fijada (la copia de la clave pública tiene la caducidad antigua)"
  else
    log "firma válida de la clave fijada"
  fi
  (cd "$dir" && unzip -q awscliv2.zip)
  "$dir/aws/install" --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli --update >/dev/null
  /usr/local/bin/aws --version | grep -q "^aws-cli/${AWSCLI_VERSION} " || die "la AWS CLI instalada no es la $AWSCLI_VERSION"
  log "AWS CLI $AWSCLI_VERSION instalada"
}

step_host_files() {
  step ficheros "secretos en tmpfs, hooks de certbot, copia nocturna y runtime de compose"
  local before=${#CHANGED[@]}
  # Runtime de compose en una ruta ESTABLE (nginx.conf y su entrypoint son fuentes de bind mount):
  # root:root, 0640/0750, legibles por el master de nginx (root sin CAP_DAC_OVERRIDE, es el dueño).
  install_file "$RUNTIME/compose.yaml" "$RUNTIME_DIR/compose.yaml" 0640
  install_file "$RUNTIME/nginx.conf" "$RUNTIME_DIR/nginx.conf" 0640
  install_file "$RUNTIME/nginx-entrypoint.sh" "$RUNTIME_DIR/nginx-entrypoint.sh" 0750
  install_file "$RUNTIME/compose.env.example" "$RUNTIME_DIR/compose.env.example" 0640
  if [[ ! -f $COMPOSE_ENV_FILE ]]; then
    install -D -m 0600 -o root -g root "$RUNTIME/compose.env.example" "$COMPOSE_ENV_FILE"
    log "creado $COMPOSE_ENV_FILE desde la plantilla (digests e IDs, sin secretos; no se sobrescribe en re-ejecuciones)"
  fi
  install_file "$SECRETS/uonify-secrets-sync.sh" /usr/local/sbin/uonify-secrets-sync 0750
  install_file "$SECRETS/uonify_secrets_render.py" /usr/local/lib/uonify/uonify_secrets_render.py 0644
  install_file "$SECRETS/uonify-secrets.service" /etc/systemd/system/uonify-secrets.service 0644
  install_file "$FILES/docker-10-uonify.conf" /etc/systemd/system/docker.service.d/10-uonify.conf 0644
  install_file "$FILES/uonify-acme-route53.sh" /usr/local/lib/uonify/certbot/uonify-acme-route53 0750
  install_file "$FILES/uonify-cert-deploy.sh" /usr/local/lib/uonify/certbot/uonify-cert-deploy 0750
  install_file "$FILES/uonify-pg-backup.sh" /usr/local/sbin/uonify-pg-backup 0750
  install_file "$FILES/uonify-pg-backup.service" /etc/systemd/system/uonify-pg-backup.service 0644
  install_file "$FILES/uonify-pg-backup.timer" /etc/systemd/system/uonify-pg-backup.timer 0644
  if [[ ! -f $HOST_ENV_FILE ]]; then
    install -D -m 0644 "$FILES/host.env" "$HOST_ENV_FILE"
    log "creado $HOST_ENV_FILE (valores no secretos; no se sobrescribe en re-ejecuciones)"
  fi
  if [[ -n $KMS_KEY_ARN ]]; then
    set_host_env UONIFY_KMS_KEY_ARN "$KMS_KEY_ARN"
  elif ! grep -Eq '^UONIFY_KMS_KEY_ARN=arn:' "$HOST_ENV_FILE"; then
    warn "sin --kms-key-arn: la copia nocturna no podrá exigir la CMK exacta (pasa la salida KmsKeyArn del stack)"
  fi
  if (( ${#CHANGED[@]} > before )); then
    UNITS_CHANGED=1
    systemctl daemon-reload
  fi
}

docker_key_ok() { # fichero
  local home=$TMP_ROOT/gnupg-docker fprs
  install -d -m 0700 "$home"
  fprs=$(gpg --batch --homedir "$home" --show-keys --with-colons "$1" 2>/dev/null \
    | awk -F: '$1 == "pub" { p = 1; next } $1 == "fpr" && p { print $10; p = 0 }')
  gpgconf --homedir "$home" --kill all >/dev/null 2>&1 || true
  [[ $fprs == "$DOCKER_GPG_FPR" ]]
}

step_hardening() {
  step endurecimiento "sin SSH (solo SSM) y el usuario ubuntu sin login"
  # Ubuntu 24.04 arranca sshd por socket: ssh.service sale «inactive» pero ssh.socket escucha en el 22.
  # El security group ya lo cierra; esto lo apaga también en el host. SSM no usa SSH.
  systemctl disable --now ssh.socket ssh.service >/dev/null 2>&1 || true
  systemctl mask ssh.socket ssh.service >/dev/null 2>&1 || warn "no pude enmascarar ssh.socket y ssh.service"
  # uid 1000 es «ubuntu» en el host y el usuario de los contenedores: sigue siendo el dueño de
  # /run/uonify, pero sin contraseña válida ni shell.
  if id ubuntu >/dev/null 2>&1; then
    usermod --lock --shell /usr/sbin/nologin ubuntu || warn "no pude bloquear el usuario ubuntu"
  fi
  if [[ -n $(ss -H -ltn 'sport = :22' 2>/dev/null) ]]; then
    die "el puerto 22 sigue escuchando después de apagar SSH"
  fi
  log "SSH apagado y enmascarado; ubuntu sin login"
}

step_docker() {
  step docker "Docker CE $DOCKER_ENGINE_VERSION (containerd), compose $COMPOSE_VERSION, credenciales de ECR"
  if [[ ! -f /etc/apt/keyrings/docker.asc ]] || ! docker_key_ok /etc/apt/keyrings/docker.asc; then
    fetch https://download.docker.com/linux/ubuntu/gpg "$TMP_ROOT/docker.asc"
    docker_key_ok "$TMP_ROOT/docker.asc" || die "la clave del repositorio de Docker no tiene la huella $DOCKER_GPG_FPR"
    install -D -m 0644 "$TMP_ROOT/docker.asc" /etc/apt/keyrings/docker.asc
    log "clave del repositorio de Docker verificada por huella"
  fi
  local before=${#CHANGED[@]}
  install_file "$FILES/docker.sources" /etc/apt/sources.list.d/docker.sources 0644
  if (( ${#CHANGED[@]} > before )) || [[ -z $(apt-cache madison docker-ce 2>/dev/null) ]]; then apt_update; fi
  before=${#CHANGED[@]}
  install_file "$FILES/docker-daemon.json" /etc/docker/daemon.json 0644
  if (( ${#CHANGED[@]} > before )); then DAEMON_JSON_CHANGED=1; fi

  if [[ $(pkg_version docker-ce) == "$DOCKER_APT_VERSION" && $(pkg_version docker-ce-cli) == "$DOCKER_APT_VERSION" \
      && $(pkg_version containerd.io) == "$CONTAINERD_APT_VERSION" \
      && $(pkg_version docker-compose-plugin) == "$COMPOSE_APT_VERSION" ]]; then
    log "Docker ya está en las versiones fijadas"
  else
    with_no_service_start apt_get install --no-install-recommends --allow-change-held-packages \
      --allow-downgrades "docker-ce=$DOCKER_APT_VERSION" "docker-ce-cli=$DOCKER_APT_VERSION" \
      "containerd.io=$CONTAINERD_APT_VERSION" "docker-compose-plugin=$COMPOSE_APT_VERSION"
    log "Docker instalado en las versiones fijadas"
  fi
  apt-mark hold docker-ce docker-ce-cli containerd.io docker-compose-plugin >/dev/null

  command -v docker-credential-ecr-login >/dev/null || die "falta docker-credential-ecr-login"
  python3 -I - "$ECR_REGISTRY" <<'PY'
import json, os, sys
path, registry = '/root/.docker/config.json', sys.argv[1]
try:
    with open(path) as handle:
        config = json.load(handle)
except FileNotFoundError:
    config = {}
helpers = config.setdefault('credHelpers', {})
if helpers.get(registry) != 'ecr-login':
    helpers[registry] = 'ecr-login'
    os.makedirs('/root/.docker', mode=0o700, exist_ok=True)
    temp = path + '.tmp'
    with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as handle:
        json.dump(config, handle, indent=2)
        handle.write('\n')
    os.replace(temp, path)
    print('[uonify-bootstrap] credHelpers: ' + registry + ' -> ecr-login')
PY
}

step_services() {
  step servicios "secretos en tmpfs y arranque de Docker"
  systemctl daemon-reload
  if systemd-analyze verify /etc/systemd/system/uonify-secrets.service \
      /etc/systemd/system/uonify-pg-backup.service /etc/systemd/system/uonify-pg-backup.timer \
      docker.service >"$TMP_ROOT/verify.txt" 2>&1; then
    log "systemd-analyze verify: sin errores (uonify-secrets, uonify-pg-backup, docker + drop-in)"
  else
    warn "systemd-analyze verify señala algo (revísalo; no bloquea):"
    sed 's/^/    /' "$TMP_ROOT/verify.txt" >&2
  fi
  systemctl enable uonify-secrets.service >/dev/null 2>&1
  systemctl enable containerd.service docker.service docker.socket >/dev/null 2>&1
  systemctl enable --now uonify-pg-backup.timer >/dev/null 2>&1
  if systemctl is-active --quiet uonify-secrets.service; then
    log "uonify-secrets ya activo: refresco en caliente (sin reiniciar Docker)"
    /usr/local/sbin/uonify-secrets-sync || warn "el refresco falló; se mantienen los ficheros anteriores"
    SECRETS_READY=1
  elif systemctl start uonify-secrets.service; then
    SECRETS_READY=1
  else
    journalctl -u uonify-secrets.service -b -n 40 --no-pager -o cat >&2 || true
    warn "uonify-secrets falló (arriba, solo nombres): Docker NO arranca hasta que existan los secretos."
    warn "El dueño ejecuta upload_dev_secrets.sh --apply y después se repite este bootstrap."
  fi
  if (( ! SECRETS_READY )); then
    return 0
  fi
  if (( DAEMON_JSON_CHANGED )) && systemctl is-active --quiet docker.service; then
    log "daemon.json cambió: reinicio de Docker (live-restore conserva los contenedores)"
    systemctl restart docker.service
  fi
  if (( SKIP_DOCKER_START )); then
    log "--skip-docker-start: Docker queda instalado sin arrancar"
    return 0
  fi
  systemctl start docker.socket docker.service
  local version
  version=$(docker version --format '{{.Server.Version}}')
  [[ $version == "$DOCKER_ENGINE_VERSION" ]] || die "Docker $version en marcha; se esperaba $DOCKER_ENGINE_VERSION"
  docker info --format '{{json .DriverStatus}}' | grep -q 'io.containerd.snapshotter.v1' \
    || die "Docker no usa el almacén de imágenes containerd"
  [[ $(docker compose version --short) == "$COMPOSE_VERSION" ]] || die "docker compose no es la $COMPOSE_VERSION"
  log "Docker $version con almacén containerd y compose $COMPOSE_VERSION en marcha"
}

step_certificate() {
  step certificado "certificado del origen $ORIGIN_FQDN (DNS-01, Route 53)"
  local live=/etc/letsencrypt/live/$ORIGIN_FQDN
  systemctl enable --now certbot.timer >/dev/null 2>&1 || warn "no pude activar certbot.timer"
  if (( CERT_DRY_RUN )); then
    log "ensayo DNS-01 contra el staging de Let's Encrypt (no guarda nada)"
    certbot certonly --dry-run --non-interactive --agree-tos --register-unsafely-without-email \
      --manual --preferred-challenges dns \
      --manual-auth-hook "/usr/local/lib/uonify/certbot/uonify-acme-route53 auth" \
      --manual-cleanup-hook "/usr/local/lib/uonify/certbot/uonify-acme-route53 cleanup" \
      --cert-name "$ORIGIN_FQDN" -d "$ORIGIN_FQDN" --key-type rsa --rsa-key-size 2048
  fi
  if [[ -f $live/fullchain.pem ]]; then
    RENEWED_LINEAGE=$live /usr/local/lib/uonify/certbot/uonify-cert-deploy
  elif (( ISSUE_CERT )); then
    local account=(--register-unsafely-without-email)
    if [[ -n $ACME_EMAIL ]]; then account=(--email "$ACME_EMAIL" --no-eff-email); fi
    certbot certonly --non-interactive --agree-tos "${account[@]}" \
      --manual --preferred-challenges dns \
      --manual-auth-hook "/usr/local/lib/uonify/certbot/uonify-acme-route53 auth" \
      --manual-cleanup-hook "/usr/local/lib/uonify/certbot/uonify-acme-route53 cleanup" \
      --deploy-hook /usr/local/lib/uonify/certbot/uonify-cert-deploy \
      --cert-name "$ORIGIN_FQDN" -d "$ORIGIN_FQDN" --key-type rsa --rsa-key-size 2048
    [[ -f $live/fullchain.pem ]] || die "certbot no dejó el certificado en $live"
  else
    log "sin certificado todavía: re-ejecuta con --issue-cert cuando toque (paso 10 del plan)"
  fi
}

step_summary() {
  step resumen "estado final"
  log "paquete: $(bundle_digest)"
  log "/data: $(findmnt -n -o SOURCE,FSTYPE,LABEL "$DATA_MOUNT" | tr -s ' ') · libre $(df -h --output=avail "$DATA_MOUNT" | tail -n 1 | tr -d ' ')"
  log "hora: $(chronyc -n tracking 2>/dev/null | awk -F': ' '/^Reference ID/ { print $2 }')"
  log "AWS CLI: $(/usr/local/bin/aws --version 2>&1 | cut -d' ' -f1)"
  log "Docker: $(pkg_version docker-ce) · containerd.io $(pkg_version containerd.io) · compose $(pkg_version docker-compose-plugin)"
  log "uonify-secrets: $(systemctl is-active uonify-secrets.service || true) · docker: $(systemctl is-active docker.service || true)"
  log "copia nocturna: $(systemctl show -p NextElapseUSecRealtime --value uonify-pg-backup.timer 2>/dev/null || true)"
  if [[ -f /etc/letsencrypt/live/$ORIGIN_FQDN/fullchain.pem ]]; then
    log "certificado: $(openssl x509 -in "/etc/letsencrypt/live/$ORIGIN_FQDN/fullchain.pem" -noout -enddate)"
  else
    log "certificado: no emitido"
  fi
  install -d -m 0755 /etc/uonify
  printf 'bundle_sha256=%s\nbootstrap_utc=%s\n' "$(bundle_digest)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    >/etc/uonify/bootstrap.stamp
  if (( ! SECRETS_READY )); then
    die "bootstrap incompleto: faltan los secretos en SSM (Docker no arrancado)"
  fi
  log "bootstrap completo"
}

main() {
  parse_args "$@"
  step_preflight
  step_apt_https
  step_base_packages
  step_chrony
  step_data_volume
  step_awscli
  step_host_files
  step_hardening
  step_docker
  step_services
  step_certificate
  step_summary
}

# Ejecutado (no «source»): las pruebas cargan las funciones sin lanzar ningún paso.
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  main "$@"
fi
