#!/usr/bin/env bash
# Uonify DEV · hook de certbot --manual para DNS-01 en Route 53.
# Se instala en /usr/local/lib/uonify/certbot/uonify-acme-route53 (0750 root) y certbot lo guarda en
# /etc/letsencrypt/renewal/origin-dev.uonify.com.conf, así que las renovaciones lo reutilizan:
#   --manual-auth-hook    "/usr/local/lib/uonify/certbot/uonify-acme-route53 auth"
#   --manual-cleanup-hook "/usr/local/lib/uonify/certbot/uonify-acme-route53 cleanup"
#
# Solo toca el TXT _acme-challenge.origin-dev.uonify.com de la zona compartida Z08167243FAUSDUW0Z2KP
# (lo único que permite el rol de la instancia: UPSERT/DELETE de ese TXT, GetChange y
# ListHostedZonesByName). auth: UPSERT y espera a INSYNC. cleanup: DELETE; si falla solo avisa.
# El token de validación es público (acaba en el DNS); aun así no se pasa por la línea de órdenes.
set -Eeuo pipefail
umask 077
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME="${HOME:-/root}"
export AWS_REGION=eu-west-1 AWS_DEFAULT_REGION=eu-west-1 AWS_PAGER="" AWS_CLI_AUTO_PROMPT=off

readonly ZONE_ID=Z08167243FAUSDUW0Z2KP
readonly DOMAIN=origin-dev.uonify.com
readonly RECORD=_acme-challenge.origin-dev.uonify.com
readonly TTL=60
AWS=${UONIFY_AWS_BIN:-/usr/local/bin/aws}
WAIT_SECONDS=${UONIFY_ACME_WAIT_SECONDS:-600}
POLL_SECONDS=${UONIFY_ACME_POLL_SECONDS:-5}
SETTLE_SECONDS=${UONIFY_ACME_SETTLE_SECONDS:-15}

# certbot usa la salida estándar del hook auth como CERTBOT_AUTH_OUTPUT: los mensajes van a stderr.
log() { printf 'uonify-acme-route53: %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

build_batch() { # acción valor fichero
  python3 -I -c '
import json, sys
action, record, ttl, value, comment = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
json.dump({"Comment": comment, "Changes": [{"Action": action, "ResourceRecordSet": {
    "Name": record, "Type": "TXT", "TTL": ttl, "ResourceRecords": [{"Value": "\"" + value + "\""}]}}]},
    sys.stdout)
' "$1" "$RECORD" "$TTL" "$2" "certbot dns-01 $DOMAIN ($1)" >"$3"
}

change_record() { # acción -> imprime el id del cambio
  local action=$1 tmp id
  tmp=$(mktemp -d)
  if ! build_batch "$action" "$CERTBOT_VALIDATION" "$tmp/batch.json"; then
    rm -rf "$tmp"
    return 1
  fi
  if ! id=$("$AWS" route53 change-resource-record-sets --hosted-zone-id "$ZONE_ID" \
      --change-batch "file://$tmp/batch.json" --query 'ChangeInfo.Id' --output text); then
    rm -rf "$tmp"
    return 1
  fi
  rm -rf "$tmp"
  printf '%s' "$id"
}

wait_insync() {
  local id=$1 status deadline=$((SECONDS + WAIT_SECONDS))
  while :; do
    status=$("$AWS" route53 get-change --id "$id" --query 'ChangeInfo.Status' --output text)
    if [[ $status == INSYNC ]]; then
      return 0
    fi
    if (( SECONDS >= deadline )); then
      die "el cambio $id no llegó a INSYNC en ${WAIT_SECONDS}s (estado: $status)"
    fi
    sleep "$POLL_SECONDS"
  done
}

main() {
  local mode=${1:-} id
  [[ $mode == auth || $mode == cleanup ]] || die "uso: $0 auth|cleanup (lo llama certbot)"
  [[ ${CERTBOT_DOMAIN:-} == "$DOMAIN" ]] || die "dominio no permitido: '${CERTBOT_DOMAIN:-}' (solo $DOMAIN)"
  [[ ${CERTBOT_VALIDATION:-} =~ ^[A-Za-z0-9_-]{16,128}$ ]] || die "CERTBOT_VALIDATION con formato inesperado"
  [[ -x $AWS ]] || die "no encuentro la AWS CLI en $AWS"

  if [[ $mode == auth ]]; then
    id=$(change_record UPSERT) || die "Route 53 rechazó el UPSERT de $RECORD"
    log "UPSERT TXT $RECORD enviado ($id); esperando INSYNC"
    wait_insync "$id"
    log "INSYNC; margen de propagación de ${SETTLE_SECONDS}s"
    sleep "$SETTLE_SECONDS"
  else
    if id=$(change_record DELETE); then
      log "DELETE TXT $RECORD enviado ($id)"
    else
      log "aviso: no se pudo borrar $RECORD (quizá ya no existe); no bloquea el certificado"
    fi
  fi
}

main "$@"
