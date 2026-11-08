#!/bin/bash
# Uonify DEV · genera bootstrap/dist/uonify-dev-host-bundle.sh: UN solo script autoextraíble con
# secrets/, bootstrap/ y runtime/ (sin pruebas, sin dist/, sin upload_dev_secrets.sh, que es del Mac
# del dueño, y sin runtime/validate-local.sh, que es solo de la estación de trabajo),
# para entregarlo al host por SSM (AWS-RunRemoteScript desde S3, o Session Manager).
# Se ejecuta en el Mac (bash 3.2 + python3). No toca AWS. El tar es reproducible: mismo contenido,
# mismo sha256 (orden fijo, uid/gid 0, mtime fijo; 0755 para scripts y 0644 para el resto).
#
# En el host (root):  bash uonify-dev-host-bundle.sh --data-volume-id vol-... [opciones de bootstrap.sh]
#   comprueba el sha256 embebido, extrae en /opt/uonify/bundle/<sha256[0:12]> y ejecuta bootstrap.sh.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd -P)
ROOT=$(cd "$HERE/.." && pwd -P)
OUT="$HERE/dist/uonify-dev-host-bundle.sh"
mkdir -p "$HERE/dist"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/uonify-bundle.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

python3 -I - "$ROOT" "$TMP/bundle.tgz" <<'PY'
import gzip, io, os, sys, tarfile
root, out = sys.argv[1], sys.argv[2]
skip_dirs = {'secrets/tests', 'bootstrap/tests', 'bootstrap/dist'}
skip_files = {'secrets/upload_dev_secrets.sh', 'bootstrap/make_host_bundle.sh', 'runtime/validate-local.sh'}
members = []
for top in ('secrets', 'bootstrap', 'runtime'):
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, top)):
        rel_dir = os.path.relpath(dirpath, root)
        dirnames[:] = sorted(d for d in dirnames if os.path.join(rel_dir, d) not in skip_dirs and not d.startswith('.'))
        for name in sorted(filenames):
            rel = os.path.join(rel_dir, name)
            if rel in skip_files or name.startswith('.') or name.startswith('._'):
                continue
            members.append(rel)
buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode='w', format=tarfile.PAX_FORMAT) as tar:
    for rel in sorted(members):
        data = open(os.path.join(root, rel), 'rb').read()
        info = tarfile.TarInfo(rel)
        info.size, info.mtime, info.uid, info.gid, info.uname, info.gname = len(data), 1700000000, 0, 0, 'root', 'root'
        info.mode = 0o755 if rel.endswith(('.sh', '.py')) else 0o644
        tar.addfile(info, io.BytesIO(data))
with open(out, 'wb') as handle:
    with gzip.GzipFile(fileobj=handle, mode='wb', mtime=0) as gz:
        gz.write(buffer.getvalue())
print('\n'.join(sorted(members)))
PY

SHA=$(python3 -I -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$TMP/bundle.tgz")
{
  cat <<EOF
#!/usr/bin/env bash
# Uonify DEV · paquete autoextraíble del host (generado por make_host_bundle.sh, $(date -u +%Y-%m-%dT%H:%M:%SZ)).
# Uso (root, por SSM): bash uonify-dev-host-bundle.sh --data-volume-id vol-... [opciones de bootstrap.sh]
# Contiene secrets/ y bootstrap/ (código y configuración; NINGÚN secreto). sha256 del tar.gz: ${SHA}
set -Eeuo pipefail
readonly BUNDLE_SHA256=${SHA}
EOF
  cat <<'EOF'
readonly DEST=/opt/uonify/bundle/${BUNDLE_SHA256:0:12}
[[ $EUID -eq 0 ]] || { echo "hay que ejecutarlo como root" >&2; exit 1; }
SELF=$(readlink -f -- "${BASH_SOURCE[0]}")
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
sed -n '/^__UONIFY_BUNDLE_BELOW__$/,$p' "$SELF" | tail -n +2 | base64 -d >"$TMP/bundle.tgz"
echo "${BUNDLE_SHA256}  $TMP/bundle.tgz" | sha256sum -c --quiet - || { echo "paquete corrupto: sha256 distinto" >&2; exit 1; }
if [[ ! -d $DEST ]]; then
  install -d -m 0755 /opt/uonify /opt/uonify/bundle
  install -d -m 0750 "$TMP/x"
  tar -xzf "$TMP/bundle.tgz" -C "$TMP/x" --no-same-owner --no-same-permissions
  find "$TMP/x" -type f \( -name '*.sh' -o -name '*.py' \) -exec chmod 0750 {} +
  find "$TMP/x" -type f ! \( -name '*.sh' -o -name '*.py' \) -exec chmod 0640 {} +
  mv "$TMP/x" "$DEST"
fi
echo "[uonify-bundle] paquete ${BUNDLE_SHA256:0:12} en $DEST"
bash "$DEST/bootstrap/bootstrap.sh" "$@"
exit $?
__UONIFY_BUNDLE_BELOW__
EOF
  base64 <"$TMP/bundle.tgz" | fold -w 76
} >"$OUT"
chmod 0644 "$OUT"
echo "generado $OUT ($(wc -c <"$OUT" | tr -d ' ') bytes; tar.gz sha256 $SHA)"
