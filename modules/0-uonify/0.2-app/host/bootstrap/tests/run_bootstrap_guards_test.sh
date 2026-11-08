#!/bin/bash
# Lanza test_bootstrap_guards_in_container.sh en un contenedor DESECHABLE (--rm, --network none).
set -eu
HERE=$(cd "$(dirname "$0")" && pwd -P)
IMAGE=${TEST_IMAGE:-uonify-dev-api:devorigin-20261107}
exec docker run --rm --network none --pull never --user 0 \
  -v "$HERE:/t:ro" -v "$HERE/../..:/b:ro" --entrypoint bash "$IMAGE" /t/test_bootstrap_guards_in_container.sh
