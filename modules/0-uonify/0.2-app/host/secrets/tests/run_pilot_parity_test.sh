#!/bin/bash
# Paridad de las reglas de las listas piloto: lanza pilot_parity_in_container.py en un contenedor
# DESECHABLE (--rm, --network none, sin pull) de cada imagen del backend que lee /run/uonify (api,
# clips, conv), usando su load_settings() real. Las imágenes solo se usan como entorno; no se
# modifican y no se toca el stack uonify-local-*.
set -u
HERE=$(cd "$(dirname "$0")" && pwd -P)
IMAGES=${TEST_IMAGES:-"uonify-dev-api:devorigin-20261107 uonify-dev-clips:devorigin-20261107 uonify-dev-conv:devorigin-20261107"}
rc=0
for image in $IMAGES; do
  echo "== $image"
  # api y clips leen las 8 listas (fijan el veredicto estricto); conv solo 4.
  case $image in *-api:*|*-clips:*) all=1 ;; *) all=0 ;; esac
  docker run --rm --network none --pull never --user 0 -e IMAGE_LABEL="$image" -e EXPECT_ALL_LISTS=$all \
    -v "$HERE:/t:ro" -v "$HERE/..:/s:ro" --entrypoint python "$image" -I -B /t/pilot_parity_in_container.py || rc=1
done
exit $rc
