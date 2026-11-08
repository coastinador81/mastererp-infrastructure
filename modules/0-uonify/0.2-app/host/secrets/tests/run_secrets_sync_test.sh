#!/bin/bash
# Lanza test_secrets_sync_in_container.sh en un contenedor DESECHABLE (--rm, --network none) con
# bash 5.2 y python 3.12 (la imagen uonify-dev-api, solo como entorno Debian; no se modifica).
# CAP_SYS_ADMIN solo para poder montar tmpfs dentro del contenedor. No toca el stack uonify-local-*.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd -P)
IMAGE=${TEST_IMAGE:-uonify-dev-api:devorigin-20261107}
exec docker run --rm --network none --pull never --user 0 --cap-add SYS_ADMIN \
  -v "$HERE:/t:ro" -v "$HERE/..:/s:ro" --entrypoint bash "$IMAGE" /t/test_secrets_sync_in_container.sh
