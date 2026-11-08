#!/bin/bash
# Lanza las pruebas de los hooks de certbot en un contenedor DESECHABLE (--rm, --network none):
# bash 5.2, python 3.12 y openssl de Debian (la imagen uonify-dev-api solo como entorno; no se
# modifica). No toca el stack uonify-local-* ni AWS.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd -P)
IMAGE=${TEST_IMAGE:-uonify-dev-api:devorigin-20261107}
exec docker run --rm --network none --pull never --user 0 \
  -v "$HERE:/t:ro" -v "$HERE/..:/b:ro" --entrypoint bash "$IMAGE" /t/test_certbot_hooks_in_container.sh
