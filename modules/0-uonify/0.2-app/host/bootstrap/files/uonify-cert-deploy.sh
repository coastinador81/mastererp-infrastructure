#!/usr/bin/env bash
# Uonify DEV · deploy hook de certbot (se instala en /usr/local/lib/uonify/certbot/uonify-cert-deploy).
# certbot lo ejecuta tras emitir o renovar el certificado de origin-dev.uonify.com (RENEWED_LINEAGE).
# bootstrap.sh también lo ejecuta, idempotente.
#
# 1. Comprueba que el certificado es de origin-dev.uonify.com, está vigente y casa con la clave.
# 2. Si el certificado cambió desde el último despliegue (huella en UONIFY_STATE_DIR), envía HUP al
#    contenedor nginx del proyecto (recarga configuración y certificado sin cortar conexiones).
#    runtime/compose.yaml monta /etc/letsencrypt/{live,archive}/origin-dev.uonify.com directamente.
# 3. Solo si UONIFY_TLS_DIR tiene valor (vacío por defecto en /etc/uonify/host.env): copia también
#    fullchain.pem y privkey.pem ahí como UONIFY_TLS_UID:GID 0440, para un nginx que no corra como
#    root (p. ej. nginx-unprivileged, uid 101).
# Nunca imprime la clave privada.
set -Eeuo pipefail
umask 077
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

readonly DOMAIN=origin-dev.uonify.com
readonly HOST_ENV=/etc/uonify/host.env
EXPECTED_LINEAGE=${UONIFY_CERT_LINEAGE:-/etc/letsencrypt/live/$DOMAIN}
STATE_DIR=${UONIFY_STATE_DIR:-/var/lib/uonify}

log() { printf 'uonify-cert-deploy: %s\n' "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

load_host_env() {
  [[ -r $HOST_ENV ]] || return 0
  local meta
  meta=$(stat -c '%u %a' "$HOST_ENV")
  [[ ${meta%% *} == 0 && $(( 8#${meta##* } & 8#022 )) -eq 0 ]] || die "$HOST_ENV debe ser de root y no escribible por grupo/otros"
  set -a
  # shellcheck source=/dev/null
  . "$HOST_ENV"
  set +a
}

needs_copy() { # origen destino uid gid
  [[ -f $2 && ! -L $2 ]] || return 0
  cmp -s "$1" "$2" || return 0
  [[ $(stat -c '%u %g %a' "$2") == "$3 $4 440" ]] || return 0
  return 1
}

TLS_COPIED=0
# Se llama como orden normal (no en una condición) para que set -e siga activo dentro.
copy_tls() { # linaje
  local lineage=$1 dir=$UONIFY_TLS_DIR uid=${UONIFY_TLS_UID:-101} gid=${UONIFY_TLS_GID:-0} name
  [[ $uid =~ ^[0-9]+$ && $gid =~ ^[0-9]+$ ]] || die "UONIFY_TLS_UID/GID deben ser numéricos"
  install -d -m 0750 -o "$uid" -g "$gid" "$dir"
  for name in privkey.pem fullchain.pem; do
    if needs_copy "$lineage/$name" "$dir/$name" "$uid" "$gid"; then
      install -m 0440 -o "$uid" -g "$gid" "$lineage/$name" "$dir/.$name.new"
      mv -f "$dir/.$name.new" "$dir/$name"
      TLS_COPIED=1
    fi
  done
  if (( TLS_COPIED )); then log "copiado a $dir (${uid}:${gid}, 0440)"; fi
}

reload_nginx() {
  local project=${UONIFY_COMPOSE_PROJECT:-uonify-dev} service=${UONIFY_NGINX_SERVICE:-nginx} ids id
  if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    log "Docker no está activo: nginx cogerá el certificado al arrancar"
    return 0
  fi
  ids=$(docker ps -q --filter "label=com.docker.compose.project=${project}" \
    --filter "label=com.docker.compose.service=${service}" --filter status=running || true)
  if [[ -z $ids ]]; then
    log "nginx no está en marcha: cogerá el certificado al arrancar"
    return 0
  fi
  for id in $ids; do
    docker kill --signal=HUP "$id" >/dev/null
  done
  log "nginx recargado (HUP)"
}

main() {
  [[ $EUID -eq 0 ]] || die "hay que ejecutarlo como root"
  load_host_env
  local lineage=${RENEWED_LINEAGE:-$EXPECTED_LINEAGE}
  [[ $lineage == "$EXPECTED_LINEAGE" ]] || die "certificado inesperado: $lineage (solo $EXPECTED_LINEAGE)"
  local chain=$lineage/fullchain.pem key=$lineage/privkey.pem
  [[ -r $chain && -r $key ]] || die "faltan fullchain.pem o privkey.pem en $lineage"

  openssl x509 -in "$chain" -noout -checkend 0 >/dev/null || die "el certificado ha caducado"
  openssl x509 -in "$chain" -noout -ext subjectAltName \
    | grep -Eq "(^|[[:space:],])DNS:${DOMAIN//./\\.}(,|[[:space:]]*$)" \
    || die "el certificado no es de $DOMAIN"
  [[ $(openssl x509 -in "$chain" -noout -pubkey | sha256sum) == "$(openssl pkey -in "$key" -pubout | sha256sum)" ]] \
    || die "la clave privada no casa con el certificado"
  log "certificado de $DOMAIN válido hasta $(openssl x509 -in "$chain" -noout -enddate | cut -d= -f2)"

  local reload=0 current previous=""
  if [[ -n ${UONIFY_TLS_DIR:-} ]]; then
    copy_tls "$lineage"
  fi
  if (( TLS_COPIED )); then reload=1; fi
  current=$(sha256sum "$chain" | cut -d' ' -f1)
  if [[ -r $STATE_DIR/origin-cert.sha256 ]]; then previous=$(<"$STATE_DIR/origin-cert.sha256"); fi
  if [[ $current != "$previous" ]]; then reload=1; fi
  if (( reload )); then
    reload_nginx
    install -d -m 0755 "$STATE_DIR"
    printf '%s\n' "$current" >"$STATE_DIR/origin-cert.sha256"
  else
    log "nginx ya usa este certificado: nada que recargar"
  fi
}

main "$@"
