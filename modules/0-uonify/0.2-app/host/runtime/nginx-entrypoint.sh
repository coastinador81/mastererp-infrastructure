#!/bin/sh
# Uonify DEV: entrypoint of the nginx service (compose.yaml). Runs as root inside the container,
# before nginx, with nginx's capabilities only (CHOWN, SETGID, SETUID) and a read-only root.
#
# It turns the X-Origin-Verify secret file (mounted read-only from the host tmpfs
# /run/uonify-edge/origin-verify) into the map include that nginx.conf loads, in the /run tmpfs:
#     "~^<value>$" 1;
# one line per accepted value: 1, or 2 while the CloudFront origin header is being rotated.
# Matching is exact and case-sensitive (regex), because plain strings in an nginx map ignore case.
#
# The value only passes through shell builtins (read, case, printf): it never shows up in a
# process argument list, on stdout or in the logs. Any problem stops the container (fail closed).
# A new value needs a container restart (docker restart uonify-dev-nginx-1); a HUP only reloads
# the configuration and the certificate, not this file. Rotation without downtime: write current
# + next (2 lines), restart, switch the CloudFront origin header, leave only next, restart again.
set -eu

src=/run/secrets/origin-verify
dir=/run/nginx-uonify
map=$dir/origin-verify.map

fail() {
    echo "nginx-entrypoint: $1; nginx not started" >&2
    exit 1
}

[ -f "$src" ] || fail "missing $src"
[ -r "$src" ] || fail "cannot read $src"

umask 077
mkdir -p "$dir"
tmp=$(mktemp "$dir/.origin-verify.XXXXXX")
cr=$(printf '\r')
count=0
while IFS= read -r value || [ -n "$value" ]; do
    value=${value%"$cr"}
    [ -n "$value" ] || continue
    count=$((count + 1))
    [ "$count" -le 2 ] || fail "more than 2 values in $src"
    case $value in
        *[!A-Za-z0-9_-]*) fail "value $count has characters outside A-Z a-z 0-9 _ -" ;;
    esac
    [ "${#value}" -ge 32 ] || fail "value $count is shorter than 32 characters"
    [ "${#value}" -le 256 ] || fail "value $count is longer than 256 characters"
    printf '"~^%s$" 1;\n' "$value" >> "$tmp"
done < "$src"
[ "$count" -ge 1 ] || fail "$src holds no value"

chmod 0400 "$tmp"
mv -f "$tmp" "$map"
exec "$@"
