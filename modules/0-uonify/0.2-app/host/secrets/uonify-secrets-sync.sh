#!/usr/bin/env bash
# Uonify DEV · uonify-secrets-sync (se instala en /usr/local/sbin/uonify-secrets-sync, 0750 root).
#
# Lo arranca uonify-secrets.service ANTES de docker.service (Before= y RequiredBy=docker.service).
# También se puede ejecutar a mano para refrescar en caliente, sin reiniciar Docker:
#   sudo /usr/local/sbin/uonify-secrets-sync
# (p. ej. tras subir una tarifa del clip o una lista piloto a SSM; después reinicia SOLO los
#  contenedores que lean ese fichero, porque el backend lee /run/uonify al arrancar).
#
# Qué hace:
#   1. Monta (si no lo están) tres tmpfs pequeños, noexec/nosuid/nodev, modo 0711 root:
#        /run/uonify        -> se monta en api y workers (directorio entero, solo lectura)
#        /run/uonify-db     -> postgres-password (uid 70) para POSTGRES_PASSWORD_FILE y pgpass para copias
#        /run/uonify-edge   -> origin-verify: valor(es) de la cabecera X-Origin-Verify de CloudFront
#                              (contrato de runtime/compose.yaml; nginx-entrypoint.sh lo convierte en map)
#      Nunca desmonta ni vuelve a montar: los contenedores vivos siguen viendo el mismo tmpfs.
#   2. Ejecuta uonify_secrets_render.py, que lee SSM (/uonify/dev/run/*, /uonify/dev/edge/origin-verify)
#      con get-parameters-by-path --with-decryption y escribe los ficheros de forma atómica.
#   3. Si cambió el secreto de borde y Docker está activo, REINICIA el contenedor nginx del proyecto
#      (su entrypoint genera el map solo al arrancar; un HUP no basta). Así se aplica la rotación:
#      SSM con 2 líneas (actual + nueva) -> sync -> cambiar CloudFront -> SSM solo nueva -> sync.
#
# No imprime valores: los secretos nunca pasan por este script (van de la AWS CLI al proceso Python).
set -Eeuo pipefail
set +x
umask 077
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME="${HOME:-/root}"
export AWS_REGION=eu-west-1 AWS_DEFAULT_REGION=eu-west-1 AWS_PAGER="" AWS_CLI_AUTO_PROMPT=off

readonly RENDER=/usr/local/lib/uonify/uonify_secrets_render.py
readonly HOST_ENV=/etc/uonify/host.env
readonly EDGE_FILE=/run/uonify-edge/origin-verify

log() { printf 'uonify-secrets-sync: %s\n' "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

load_host_env() {
  # Valores NO secretos (proyecto compose, nombre del servicio nginx). Solo si es de root y no escribible por otros.
  [[ -r $HOST_ENV ]] || return 0
  local meta
  meta=$(stat -c '%u %a' "$HOST_ENV")
  [[ ${meta%% *} == 0 && $(( 8#${meta##* } & 8#022 )) -eq 0 ]] || die "$HOST_ENV debe ser de root y no escribible por grupo/otros"
  set -a
  # shellcheck source=/dev/null
  . "$HOST_ENV"
  set +a
}

ensure_tmpfs() {
  local dir=$1 opts=$2 fstype
  [[ ! -L $dir ]] || die "$dir es un enlace simbólico"
  if [[ ! -d $dir ]]; then
    install -d -m 0711 -o root -g root "$dir"
  fi
  fstype=$(findmnt -n -o FSTYPE --mountpoint "$dir" | tail -n 1 || true)
  if [[ -z $fstype ]]; then
    mount -t tmpfs -o "mode=0711,uid=0,gid=0,nosuid,nodev,noexec,${opts}" tmpfs "$dir"
    log "montado tmpfs en $dir"
  elif [[ $fstype != tmpfs ]]; then
    die "$dir está montado como $fstype (se esperaba tmpfs): no escribo secretos ahí"
  fi
}

file_digest() {
  if [[ -f $1 ]]; then sha256sum "$1" | cut -d' ' -f1; else printf 'none'; fi
}

docker_active() {
  command -v docker >/dev/null 2>&1 && command -v systemctl >/dev/null 2>&1 \
    && systemctl is-active --quiet docker.service
}

restart_nginx() {
  local project=${UONIFY_COMPOSE_PROJECT:-uonify-dev} service=${UONIFY_NGINX_SERVICE:-nginx} ids id
  ids=$(docker ps -aq --filter "label=com.docker.compose.project=${project}" \
    --filter "label=com.docker.compose.service=${service}" || true)
  if [[ -z $ids ]]; then
    log "no hay contenedor nginx todavía: cogerá el secreto de borde al crearse"
    return 0
  fi
  for id in $ids; do
    docker restart --time 10 "$id" >/dev/null
  done
  log "nginx reiniciado: aplica el secreto de borde nuevo"
}

main() {
  [[ $EUID -eq 0 ]] || die "hay que ejecutarlo como root"
  [[ -r $RENDER ]] || die "falta $RENDER (re-ejecuta bootstrap.sh)"
  load_host_env
  # Cerrojo en /run (root 0755). No se toca /run/lock: en Ubuntu es un tmpfs 1777 que usan otros.
  exec 9>/run/uonify-secrets.lock
  flock -w 300 9 || die "otro volcado de secretos sigue en curso"

  ensure_tmpfs /run/uonify size=1m,nr_inodes=256
  ensure_tmpfs /run/uonify-db size=64k,nr_inodes=32
  ensure_tmpfs /run/uonify-edge size=64k,nr_inodes=32

  local before after
  before=$(file_digest "$EDGE_FILE")
  python3 -I "$RENDER"
  after=$(file_digest "$EDGE_FILE")
  if [[ $before != "$after" ]] && docker_active; then
    restart_nginx
  fi
}

main "$@"
