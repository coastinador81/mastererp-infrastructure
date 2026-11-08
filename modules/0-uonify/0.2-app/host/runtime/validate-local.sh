#!/bin/bash
# Uonify DEV runtime: local validation on a workstation with Docker. Never run it on the DEV host.
# Only throwaway objects named devhost-rt-check-* (containers, one volume, one internal network);
# it never touches the uonify-local-* stack and needs no AWS access. The secret used here is a
# fixed test value, the certificate is a self-signed RSA 2048 placeholder (certbot on the host
# issues RSA 2048) generated in the volume.
#   1. docker compose config (default and "armed" profiles) with dummy variables
#   2. nginx -t with --network none, the exact hardening of the nginx service and the runtime
#      files as installed on the host (root:root 0640/0750); files of another owner are refused
#   3. nginx-entrypoint.sh fails closed on bad secret files
#   4. gate, JSON errors, logs without query strings, TLS (--network none)
#   5. header rewriting, re-resolution of "api" and the host check recipe of compose.yaml (header
#      value only through stdin, never in an argument list) against a fake upstream
#   6. backend smoke with compose.yaml itself and the secrets layout of uonify-secrets-sync
# Usage: bash validate-local.sh     (exit 0 only if every check passes; SKIP_SMOKE=1 skips 6)
set -u
here=$(cd "$(dirname "$0")" && pwd)
NGINX_IMAGE=docker.io/library/nginx:1.30.6-alpine@sha256:583b7f2fce1cdb8da5ad5c39ebd3c33b98b87d493190e548bdee1fa8c619c311
PY_IMAGE=${PY_IMAGE:-uonify-dev-api:devorigin-20261107}   # any local image with python + cryptography
ECHO_IMAGE=${ECHO_IMAGE:-python:3.12-slim}
SECRET=TestOriginVerify_only-for-local-validation_0123456789abcdefABCDEF
SECOND=Rotation_next_value_for_local_validation_0123456789
passed=0
failed=0

check() { # name expected actual
    if [ "$2" = "$3" ]; then
        echo "PASS  $1"; passed=$((passed + 1))
    else
        echo "FAIL  $1 (expected: $2 | got: $3)"; failed=$((failed + 1))
    fi
}

cleanup() {
    docker compose -p devhost-rt-check down -v --remove-orphans >/dev/null 2>&1
    docker volume rm devhost-rt-check-secrets >/dev/null 2>&1
    docker stop devhost-rt-check-nginx devhost-rt-check-nginx2 devhost-rt-check-api1 \
        devhost-rt-check-api2 >/dev/null 2>&1
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        [ -z "$(docker ps -aq --filter name=devhost-rt-check-)" ] && break
        sleep 1
    done
    docker volume rm devhost-rt-check-fixtures >/dev/null 2>&1
    docker network rm devhost-rt-check-net >/dev/null 2>&1
}
trap cleanup EXIT
cleanup

# Same hardening and mounts as the nginx service of compose.yaml. Everything comes from the
# throwaway volume: nginx.conf and nginx-entrypoint.sh copied with the owner and modes they get on
# the host (root:root 0640/0750, the bundle's extract modes), the secret file and the two
# certificate dirs.
HARDEN=(--read-only --cap-drop ALL --cap-add CHOWN --cap-add SETGID --cap-add SETUID
    --security-opt no-new-privileges:true
    --tmpfs /run:size=1m --tmpfs /var/cache/nginx:size=128m --tmpfs /tmp:size=16m)
fixture() { # target in the container, path in the fixtures volume
    echo "type=volume,src=devhost-rt-check-fixtures,dst=$1,volume-subpath=$2,readonly"
}
secret_mount() {
    fixture /run/secrets/origin-verify "$1"
}
CERTS=(--mount "$(fixture /etc/letsencrypt/live/origin-dev.uonify.com letsencrypt/live/origin-dev.uonify.com)"
    --mount "$(fixture /etc/letsencrypt/archive/origin-dev.uonify.com letsencrypt/archive/origin-dev.uonify.com)")
MOUNTS=(--mount "$(fixture /etc/nginx/nginx.conf host/nginx.conf)"
    --mount "$(fixture /opt/uonify/nginx-entrypoint.sh host/nginx-entrypoint.sh)" "${CERTS[@]}")
ENTRY=(--entrypoint /bin/sh "$NGINX_IMAGE" /opt/uonify/nginx-entrypoint.sh)

echo "== 1. docker compose config"
dummy=sha256:0000000000000000000000000000000000000000000000000000000000000000
export API_DIGEST=$dummy CLIPS_DIGEST=$dummy CONV_DIGEST=$dummy UONIFY_TEST_PROJECT_IDS=
export UONIFY_CREATIVE_OUTPUT_BUCKETS=dummy-bucket UONIFY_CREATIVE_OUTPUT_LOCATION=US-CENTRAL1
docker compose -f "$here/compose.yaml" --env-file /dev/null config -q
check "compose config (default profile)" 0 $?
docker compose -f "$here/compose.yaml" --env-file /dev/null --profile armed config -q
check "compose config (profile armed)" 0 $?
check "clips-worker only in profile armed" "no yes" "$(docker compose -f "$here/compose.yaml" --env-file /dev/null config --services | grep -qx clips-worker && echo yes || echo no) $(docker compose -f "$here/compose.yaml" --env-file /dev/null --profile armed config --services | grep -qx clips-worker && echo yes || echo no)"
rendered=$(docker compose -f "$here/compose.yaml" --env-file /dev/null --profile armed config --format json)
check "no UONIFY_ADMIN_DEV_SIMPLE_LOGIN anywhere" 0 "$(printf '%s' "$rendered" | grep -c UONIFY_ADMIN_DEV_SIMPLE_LOGIN)"
check "FORWARDED_ALLOW_IPS == edge subnet, edge only nginx+api" "True api,nginx" "$(printf '%s' "$rendered" | python3 -I -c '
import json, sys
p = json.load(sys.stdin)
cidr = p["networks"]["edge"]["ipam"]["config"][0]["subnet"]
on_edge = sorted(n for n, s in p["services"].items() if "edge" in (s.get("networks") or {}))
print(p["services"]["api"]["environment"]["FORWARDED_ALLOW_IPS"] == cidr, ",".join(on_edge))')"
unset API_DIGEST CLIPS_DIGEST CONV_DIGEST UONIFY_TEST_PROJECT_IDS UONIFY_CREATIVE_OUTPUT_BUCKETS UONIFY_CREATIVE_OUTPUT_LOCATION

echo "== fixtures (self-signed RSA 2048 placeholder certificate, runtime files, test secret files)"
docker volume create devhost-rt-check-fixtures >/dev/null
docker run --rm --network none --read-only --cap-drop ALL --cap-add CHOWN --user 0:0 \
    -e CHECK_SECRET="$SECRET" -e CHECK_SECOND="$SECOND" -v devhost-rt-check-fixtures:/fx \
    -v "$here:/src:ro" --entrypoint python "$PY_IMAGE" -I -c '
import datetime, os, shutil
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
secret, second = os.environ["CHECK_SECRET"], os.environ["CHECK_SECOND"]
# RSA 2048: the key type certbot uses on the host (bootstrap.sh --key-type rsa --rsa-key-size 2048).
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "origin-dev.uonify.com")])
now = datetime.datetime.now(datetime.timezone.utc)
cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("origin-dev.uonify.com")]), critical=False)
        .sign(key, hashes.SHA256()))
arch, live = "/fx/letsencrypt/archive/origin-dev.uonify.com", "/fx/letsencrypt/live/origin-dev.uonify.com"
os.makedirs(arch, mode=0o700); os.makedirs(live, mode=0o700)
os.chmod("/fx/letsencrypt", 0o700); os.chmod("/fx/letsencrypt/archive", 0o700); os.chmod("/fx/letsencrypt/live", 0o700)
def write(path, data, mode):
    with open(path, "wb") as handle:
        handle.write(data)
    os.chmod(path, mode)
write(arch + "/fullchain1.pem", cert.public_bytes(serialization.Encoding.PEM), 0o644)
write(arch + "/privkey1.pem", key.private_bytes(serialization.Encoding.PEM,
      serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), 0o600)
os.symlink("../../archive/origin-dev.uonify.com/fullchain1.pem", live + "/fullchain.pem")
os.symlink("../../archive/origin-dev.uonify.com/privkey1.pem", live + "/privkey.pem")
files = {"origin-verify": secret + "\n", "origin-verify-rotation": secret + "\n" + second + "\n",
         "pos-crlf": secret + "\r\n", "neg-empty": "", "neg-blank-lines": "\n\n",
         "neg-badchar": "abc$def" + "x" * 40 + "\n", "neg-short": "short_value\n",
         "neg-three": secret + "\n" + second + "\n" + second + "x\n", "neg-space": secret + " \n"}
for fname, content in files.items():
    write("/fx/" + fname, content.encode(), 0o400)
# Runtime files: "host" = as installed on the host (root:root, bundle modes); "uid1000" = the same
# files owned by another user with owner-only bits, which the nginx master (root without
# CAP_DAC_OVERRIDE) cannot read.
for folder, conf_mode, entry_mode, owner in (("host", 0o640, 0o750, 0), ("uid1000", 0o600, 0o600, 1000)):
    os.makedirs("/fx/" + folder, mode=0o755)
    for fname, mode in (("nginx.conf", conf_mode), ("nginx-entrypoint.sh", entry_mode)):
        shutil.copyfile("/src/" + fname, "/fx/" + folder + "/" + fname)
        os.chmod("/fx/" + folder + "/" + fname, mode)
        os.chown("/fx/" + folder + "/" + fname, owner, owner)
'
check "fixtures generated" 0 $?

echo "== 2. nginx -t (--network none, compose hardening)"
out=$(docker run --rm --network none "${HARDEN[@]}" "${MOUNTS[@]}" --mount "$(secret_mount origin-verify)" \
    "${ENTRY[@]}" nginx -t 2>&1)
code=$?
printf '%s\n' "$out" | sed 's/^/      /'
check "nginx -t exit code" 0 "$code"
check "nginx -t reports success" 1 "$(printf '%s\n' "$out" | grep -c 'test is successful')"
check "secret value absent from nginx -t output" 0 "$(printf '%s\n' "$out" | grep -c "$SECRET")"
docker run --rm --network none "${HARDEN[@]}" "${MOUNTS[@]}" --mount "$(secret_mount pos-crlf)" \
    "${ENTRY[@]}" nginx -t >/dev/null 2>&1
check "entrypoint accepts a CRLF-terminated value" 0 $?
# Install contract of compose.yaml: the runtime files must be root's (or world-readable).
out=$(docker run --rm --network none "${HARDEN[@]}" --mount "$(fixture /etc/nginx/nginx.conf host/nginx.conf)" \
    --mount "$(fixture /opt/uonify/nginx-entrypoint.sh uid1000/nginx-entrypoint.sh)" "${CERTS[@]}" \
    --mount "$(secret_mount origin-verify)" "${ENTRY[@]}" nginx -t 2>&1)
code=$?
check "entrypoint owned 1000:1000 0600 -> stops before nginx" "nonzero 1 0" \
    "$([ "$code" -ne 0 ] && echo nonzero || echo zero) $(printf '%s\n' "$out" | grep -c -m1 -F "can't open '/opt/uonify/nginx-entrypoint.sh': Permission denied") $(printf '%s\n' "$out" | grep -c 'test is successful')"
out=$(docker run --rm --network none "${HARDEN[@]}" --mount "$(fixture /etc/nginx/nginx.conf uid1000/nginx.conf)" \
    --mount "$(fixture /opt/uonify/nginx-entrypoint.sh host/nginx-entrypoint.sh)" "${CERTS[@]}" \
    --mount "$(secret_mount origin-verify)" "${ENTRY[@]}" nginx -t 2>&1)
code=$?
# nginx prints this [emerg] twice (its default error log is stderr too): count it once.
check "nginx.conf owned 1000:1000 0600 -> nginx refuses it" "nonzero 1 0" \
    "$([ "$code" -ne 0 ] && echo nonzero || echo zero) $(printf '%s\n' "$out" | grep -c -m1 -F '"/etc/nginx/nginx.conf" failed (13: Permission denied)') $(printf '%s\n' "$out" | grep -c 'test is successful')"

echo "== 3. entrypoint fails closed on bad secret files"
for bad in neg-empty neg-blank-lines neg-badchar neg-short neg-three neg-space; do
    out=$(docker run --rm --network none "${HARDEN[@]}" "${MOUNTS[@]}" --mount "$(secret_mount $bad)" \
        "${ENTRY[@]}" nginx -t 2>&1)
    code=$?
    check "$bad refused before nginx starts" "1 0" "$code $(printf '%s\n' "$out" | grep -c 'test is successful')"
done
out=$(docker run --rm --network none "${HARDEN[@]}" "${MOUNTS[@]}" "${ENTRY[@]}" nginx -t 2>&1)
check "missing secret file refused" "1" "$(printf '%s\n' "$out" | grep -c 'missing /run/secrets/origin-verify')"

echo "== 4. gate and responses (--network none: api is unresolvable on purpose)"
docker run -d --rm --name devhost-rt-check-nginx --network none "${HARDEN[@]}" "${MOUNTS[@]}" \
    --mount "$(secret_mount origin-verify-rotation)" "${ENTRY[@]}" nginx -g 'daemon off;' >/dev/null
for _ in $(seq 1 20); do
    docker exec devhost-rt-check-nginx wget -q -O /dev/null http://127.0.0.1:8081/nginx-health 2>/dev/null && break
    sleep 1
done
req() { # status code and body of one request made inside the container
    docker exec devhost-rt-check-nginx sh -c 'curl -sk -o /tmp/body -w "%{http_code}" "$@"; printf " "; cat /tmp/body' sh "$@"
}
check "internal health 8081" "ok" "$(docker exec devhost-rt-check-nginx wget -q -O - http://127.0.0.1:8081/nginx-health | tr -d '\n')"
check "no header -> 403" '403 {"error":"forbidden"}' "$(req https://127.0.0.1:8443/api/health)"
check "wrong header -> 403" '403 {"error":"forbidden"}' "$(req -H 'X-Origin-Verify: wrong-value-wrong-value-wrong-value-00' https://127.0.0.1:8443/api/health)"
lower=$(printf '%s' "$SECRET" | tr 'A-Z' 'a-z')
check "case variant of the secret -> 403" "403" "$(req -H "X-Origin-Verify: $lower" https://127.0.0.1:8443/api/health | cut -c1-3)"
check "secret with suffix -> 403" "403" "$(req -H "X-Origin-Verify: ${SECRET}x" https://127.0.0.1:8443/api/health | cut -c1-3)"
check "voice WebSocket without header -> 403" "403" "$(req -H 'Connection: Upgrade' -H 'Upgrade: websocket' https://127.0.0.1:8443/api/uony/live | cut -c1-3)"
check "current value passes the gate (api down -> JSON 503)" '503 {"error":"service_unavailable"' "$(req -H "X-Origin-Verify: $SECRET" https://127.0.0.1:8443/api/health | cut -c1-34)"
check "next value (rotation) passes the gate" "503" "$(req -H "X-Origin-Verify: $SECOND" https://127.0.0.1:8443/api/health | cut -c1-3)"
check "non-/api path -> JSON 404" '404 {"error":"not_found"}' "$(req -H "X-Origin-Verify: $SECRET" https://127.0.0.1:8443/index.html)"
hsts() { # value of Strict-Transport-Security in the answer to one request made inside the container
    docker exec devhost-rt-check-nginx curl -sk -o /dev/null -D - "$@" | tr -d '\r' \
        | awk -F': ' 'tolower($1)=="strict-transport-security"{print $2}'
}
check "HSTS on the gate 403" "max-age=31536000" "$(hsts https://127.0.0.1:8443/api/health)"
check "HSTS on the JSON 404" "max-age=31536000" "$(hsts -H "X-Origin-Verify: $SECRET" https://127.0.0.1:8443/index.html)"
check "HSTS on the JSON 503 (api down)" "max-age=31536000" "$(hsts -H "X-Origin-Verify: $SECRET" https://127.0.0.1:8443/api/health)"
check "body over 20 MiB -> JSON 413" '413 {"error":"body_too_large","message":"Petición demasiado grande."}' "$(docker exec devhost-rt-check-nginx sh -c 'head -c 22020096 /dev/zero | curl -sk -o /tmp/body -w "%{http_code}" -H "X-Origin-Verify: $1" -H "Content-Type: application/octet-stream" --data-binary @- https://127.0.0.1:8443/api/connections/google-drive/upload; printf " "; cat /tmp/body' sh "$SECRET")"
req -H "X-Origin-Verify: $SECRET" 'https://127.0.0.1:8443/api/auth/google/callback?code=QUERYCODE123&state=QUERYSTATE456' >/dev/null
check "TLS 1.1 refused" "35" "$(docker exec devhost-rt-check-nginx sh -c 'curl -sk --tls-max 1.1 -o /dev/null https://127.0.0.1:8443/ ; echo $?')"
check "TLS 1.2 accepted" "403" "$(docker exec devhost-rt-check-nginx curl -sk --tlsv1.2 --tls-max 1.2 -o /dev/null -w '%{http_code}' https://127.0.0.1:8443/)"
check "TLS 1.3 accepted" "403" "$(docker exec devhost-rt-check-nginx curl -sk --tlsv1.3 -o /dev/null -w '%{http_code}' https://127.0.0.1:8443/)"
# An ECDHE-RSA suite can only be negotiated with the RSA certificate (the one certbot issues).
tls12=$(docker exec devhost-rt-check-nginx sh -c 'curl -sk -v --tlsv1.2 --tls-max 1.2 -o /dev/null https://127.0.0.1:8443/ 2>&1 | grep -m1 "SSL connection using"')
[[ $tls12 =~ TLSv1\.2\ /\ ECDHE-RSA-(AES128-GCM-SHA256|AES256-GCM-SHA384|CHACHA20-POLY1305) ]] && r=yes || r="no ($tls12)"
check "TLS 1.2 with the RSA 2048 certificate: ECDHE-RSA AEAD suite" yes "$r"
check "map rendered 0400 root, 2 regex lines" "400 root 2" "$(docker exec devhost-rt-check-nginx sh -c 'stat -c "%a %U" /run/nginx-uonify/origin-verify.map; grep -c "^\"~^[A-Za-z0-9_-]\{32,\}\\$\" 1;$" /run/nginx-uonify/origin-verify.map' | tr '\n' ' ' | sed 's/ $//')"
check "workers run as nginx" "nginx" "$(docker exec devhost-rt-check-nginx sh -c 'ps -o user,args | grep "worker process" | grep -v grep | awk "{print \$1}" | sort -u')"
logs=$(docker logs devhost-rt-check-nginx 2>&1)
check "access log has the callback path" 1 "$(printf '%s\n' "$logs" | grep -c '"path":"/api/auth/google/callback"')"
check "access log has no query string" 0 "$(printf '%s\n' "$logs" | grep -c 'QUERYCODE123\|QUERYSTATE456')"
check "logs never contain the secret" 0 "$(printf '%s\n' "$logs" | grep -c "$SECRET")"
check "health 200 lines not logged, failures logged" "1" "$(printf '%s\n' "$logs" | grep '"path":"/api/health"' | grep -c '"status":503' | awk '{print ($1 >= 1)}')"
check "no error-level lines (query-safe)" 0 "$(printf '%s\n' "$logs" | grep -c '\[error\]')"
docker stop devhost-rt-check-nginx >/dev/null

echo "== 5. header rewriting and re-resolution of api (throwaway internal network)"
ECHO_PY='
import http.server, json, socket, time
class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def answer(self):
        length = int(self.headers.get("Content-Length") or 0)
        body_len = len(self.rfile.read(length)) if length else 0
        if self.path.startswith("/api/slow"):
            time.sleep(3)
        if self.path.startswith("/api/cookie-test"):
            self.send_response(200)
            self.send_header("Set-Cookie", "uonify_session=abc; HttpOnly; SameSite=Lax; Path=/")
            self.send_header("Set-Cookie", "uonify_csrf=xyz; Path=/")
            self.send_header("Set-Cookie", "already=1; Secure; Path=/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path.startswith("/api/redirect-test"):
            self.send_response(307)
            self.send_header("Location", "https://api/api/target")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        data = json.dumps({"server": socket.gethostbyname(socket.gethostname()), "method": self.command,
                           "path": self.path, "body_len": body_len,
                           "headers": {k.lower(): v for k, v in self.headers.items()}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    do_GET = do_POST = answer
    def log_message(self, *args):
        pass
http.server.ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
'
docker network create --internal --subnet 10.233.99.0/24 devhost-rt-check-net >/dev/null
docker run -d --rm --name devhost-rt-check-api1 --network devhost-rt-check-net --network-alias api \
    --ip 10.233.99.10 --read-only --cap-drop ALL --user 1000:1000 "$ECHO_IMAGE" python -I -c "$ECHO_PY" >/dev/null
docker run -d --rm --name devhost-rt-check-nginx2 --network devhost-rt-check-net --ip 10.233.99.5 \
    "${HARDEN[@]}" "${MOUNTS[@]}" --mount "$(secret_mount origin-verify)" "${ENTRY[@]}" nginx -g 'daemon off;' >/dev/null
for _ in $(seq 1 20); do
    docker exec devhost-rt-check-nginx2 sh -c 'curl -sk -o /dev/null -w "%{http_code}" -H "X-Origin-Verify: $1" https://127.0.0.1:8443/api/ready' sh "$SECRET" 2>/dev/null | grep -q 200 && break
    sleep 1
done
up() { # one request through nginx with the gate header; prints what curl prints
    docker exec devhost-rt-check-nginx2 sh -c 's=$1; shift; curl -sk -H "X-Origin-Verify: $s" "$@"' sh "$SECRET" "$@"
}
seen=$(up -H 'X-Forwarded-For: 198.51.100.7, 203.0.113.9' -H 'X-Forwarded-Proto: http' \
    -H 'Authorization: Basic Zm9vOmJhcg==' -H 'Forwarded: for=192.0.2.1' -H 'X-Forwarded-Host: evil.example' \
    -H 'X-Real-IP: 192.0.2.2' -H 'Host: anything.example' -H 'Origin: https://dev.uonify.com' \
    -H 'Cookie: uonify_session=abc' 'https://127.0.0.1:8443/api/auth/session?a=1&b=2')
check "plain request as the api sees it" \
    "GET|/api/auth/session?a=1&b=2|api|203.0.113.9|https|close|-|-|-|-|-|-|-|https://dev.uonify.com|uonify_session=abc" \
    "$(printf '%s' "$seen" | python3 -I -c '
import json, sys
d = json.load(sys.stdin); h = d["headers"]
keys = ["host", "x-forwarded-for", "x-forwarded-proto", "connection", "upgrade", "authorization",
        "x-origin-verify", "forwarded", "x-forwarded-host", "x-forwarded-port", "x-real-ip", "origin", "cookie"]
print("|".join([d["method"], d["path"]] + [h.get(k, "-") for k in keys]))')"
seen=$(up -H 'Connection: Upgrade' -H 'Upgrade: websocket' -H 'Sec-WebSocket-Version: 13' \
    -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' -H 'Origin: https://dev.uonify.com' \
    -H 'Authorization: Basic Zm9vOmJhcg==' https://127.0.0.1:8443/api/uony/live)
check "voice WebSocket handshake as the api sees it" \
    "/api/uony/live|websocket|upgrade|dGhlIHNhbXBsZSBub25jZQ==|13|https://dev.uonify.com|-" \
    "$(printf '%s' "$seen" | python3 -I -c '
import json, sys
d = json.load(sys.stdin); h = d["headers"]
keys = ["upgrade", "connection", "sec-websocket-key", "sec-websocket-version", "origin", "authorization"]
print("|".join([d["path"]] + [h.get(k, "-") for k in keys]))')"
seen=$(docker exec devhost-rt-check-nginx2 sh -c 'head -c 1048576 /dev/zero | curl -sk -H "X-Origin-Verify: $1" -H "Content-Type: application/octet-stream" --data-binary @- https://127.0.0.1:8443/api/uony/messages' sh "$SECRET")
check "1 MiB POST body reaches the api with Content-Length" "POST|1048576|1048576" \
    "$(printf '%s' "$seen" | python3 -I -c '
import json, sys
d = json.load(sys.stdin)
print("|".join([d["method"], d["headers"].get("content-length", "-"), str(d["body_len"])]))')"
check "framework redirect rewritten to the public origin" "307|https://dev.uonify.com/api/target" \
    "$(up -o /dev/null -w '%{http_code}|%{redirect_url}' https://127.0.0.1:8443/api/redirect-test)"
check "upstream Server header hidden" "nginx" \
    "$(up -o /dev/null -D - https://127.0.0.1:8443/api/x | tr -d '\r' | awk -F': ' 'tolower($1)=="server"{print $2}')"
check "HSTS on a proxied answer" "max-age=31536000" \
    "$(up -o /dev/null -D - https://127.0.0.1:8443/api/x | tr -d '\r' | awk -F': ' 'tolower($1)=="strict-transport-security"{print $2}')"
check "every cookie of the api leaves with Secure exactly once, other flags kept" "3 3 HttpOnly SameSite=Lax" \
    "$(up -o /dev/null -D - https://127.0.0.1:8443/api/cookie-test | tr -d '\r' | python3 -I -c '
import sys
lines = [l.split(":", 1)[1] for l in sys.stdin.read().splitlines() if l.lower().startswith("set-cookie:")]
parts = [[p.strip() for p in l.split(";")] for l in lines]
secure = sum(1 for p in parts if [x.lower() for x in p].count("secure") == 1)
session = next(p for p in parts if p[0] == "uonify_session=abc")
print(len(lines), secure, " ".join(x for x in session if x in ("HttpOnly", "SameSite=Lax")))')"
check "health check through the gate -> 200" "200" "$(up -o /dev/null -w '%{http_code}' https://127.0.0.1:8443/api/health)"
check "successful health checks are not logged" 0 "$(docker logs devhost-rt-check-nginx2 2>&1 | grep -c '"path":"/api/health"')"
check "viewer in the access log = last X-Forwarded-For element" 1 \
    "$(docker logs devhost-rt-check-nginx2 2>&1 | grep '"path":"/api/auth/session"' | grep -c '"viewer":"203.0.113.9"')"
echo "      sample access log line: $(docker logs devhost-rt-check-nginx2 2>&1 | grep -m1 '"path":"/api/auth/session"')"
# Host check recipe of compose.yaml, run as written there but inside this nginx container (port
# 8443 instead of the published 443; the self-signed RSA fixture as the CA, so curl verifies the
# certificate and the name origin-dev.uonify.com exactly as on the host, without -k).
recipe() { # path [with-header]
    docker exec devhost-rt-check-nginx2 sh -c '
        opts="--cacert /etc/letsencrypt/live/origin-dev.uonify.com/fullchain.pem --resolve origin-dev.uonify.com:8443:127.0.0.1"
        if [ "${2:-}" = with-header ]; then
            IFS= read -r v < /run/secrets/origin-verify; printf "X-Origin-Verify: %s\n" "$v" \
              | curl -sS -o /dev/null -w "%{http_code}" -H @- $opts "https://origin-dev.uonify.com:8443$1"
        else
            curl -sS -o /dev/null -w "%{http_code}" $opts "https://origin-dev.uonify.com:8443$1"
        fi' sh "$@"
}
check "host check without the header -> 403 (certificate verified for origin-dev)" "403" "$(recipe /api/health)"
check "host check, header read from the file and sent through stdin -> 200" "200" "$(recipe /api/health with-header)"
# While curl waits on a slow answer, no process argument list in the container holds the value.
scan=$(docker exec devhost-rt-check-nginx2 sh -c '
    IFS= read -r v < /run/secrets/origin-verify; printf "X-Origin-Verify: %s\n" "$v" \
      | curl -sS -o /dev/null -H @- --cacert /etc/letsencrypt/live/origin-dev.uonify.com/fullchain.pem \
          --resolve origin-dev.uonify.com:8443:127.0.0.1 https://origin-dev.uonify.com:8443/api/slow &
    sleep 1
    for f in /proc/[0-9]*/cmdline; do tr "\0" " " < "$f" 2>/dev/null; echo; done
    wait')
check "header value never in an argument list (curl running during the scan)" "0 1" \
    "$(printf '%s\n' "$scan" | grep -c -F "$SECRET") $(printf '%s\n' "$scan" | grep -c '^curl .*api/slow')"
check "api answered from its first address" "10.233.99.10" \
    "$(up https://127.0.0.1:8443/api/x | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["server"])')"
docker stop devhost-rt-check-api1 >/dev/null
check "api gone -> JSON 503" "503" "$(up -o /dev/null -w '%{http_code}' https://127.0.0.1:8443/api/x)"
docker run -d --rm --name devhost-rt-check-api2 --network devhost-rt-check-net --network-alias api \
    --ip 10.233.99.20 --read-only --cap-drop ALL --user 1000:1000 "$ECHO_IMAGE" python -I -c "$ECHO_PY" >/dev/null
sleep 12
check "recreated api (new IP) found again without reloading nginx" "10.233.99.20" \
    "$(up https://127.0.0.1:8443/api/x | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["server"])')"

docker stop devhost-rt-check-nginx2 devhost-rt-check-api2 >/dev/null

if [ "${SKIP_SMOKE:-0}" != 1 ]; then
echo "== 6. backend smoke with compose.yaml itself (DEV images, empty DB, fake secrets, no egress)"
# Same services and hardening as on the host; the override only swaps what cannot exist on a
# workstation: awslogs -> local logs, ECR digests -> the local DEV tags, host paths -> throwaway
# volumes, and every network becomes internal (no internet: nothing can reach Google or Stripe).
# Fake secrets in the layout uonify-secrets-sync writes on the host (secrets/uonify_secrets_render.py):
# dirs 0711 root:root, backend files 1000:1000 0400, db password 70:0 0440.
docker volume create devhost-rt-check-secrets >/dev/null
docker run --rm --network none --read-only --cap-drop ALL --cap-add CHOWN --cap-add FOWNER --user 0:0 \
    -v devhost-rt-check-secrets:/fx --entrypoint python "$PY_IMAGE" -I -c '
import json, os, secrets
from cryptography.fernet import Fernet
password = secrets.token_urlsafe(24)
os.makedirs("/fx/backend"); os.makedirs("/fx/db")
def write(path, data, mode, uid, gid):
    with open(path, "w") as handle:
        handle.write(data)
    os.chown(path, uid, gid); os.chmod(path, mode)
write("/fx/backend/google-oauth.json", json.dumps({"web": {"client_id": "smoke.apps.googleusercontent.com", "client_secret": "smoke"}}), 0o400, 1000, 1000)
write("/fx/backend/encryption-key", Fernet.generate_key().decode(), 0o400, 1000, 1000)
write("/fx/backend/postgres-password", password, 0o400, 1000, 1000)
write("/fx/db/postgres-password", password, 0o440, 70, 0)
for folder in ("/fx/backend", "/fx/db"):
    os.chown(folder, 0, 0); os.chmod(folder, 0o711)
'
check "fake secrets generated" 0 $?
SECRETS_VOLUME='[{type: volume, source: smoke-secrets, target: /run/uonify, read_only: true, volume: {subpath: backend}}]'
SMOKE_OVERRIDE="
services:
  db:
    logging: !reset {}
    volumes: !override
      - {type: volume, source: smoke-pgdata, target: /var/lib/postgresql/data}
      - {type: volume, source: smoke-secrets, target: /run/secrets/postgres-password, read_only: true, volume: {subpath: db/postgres-password}}
  redis:
    logging: !reset {}
    volumes: !override
      - {type: volume, source: smoke-redis, target: /data}
  mailpit:
    logging: !reset {}
    ports: !reset []
  api:
    image: uonify-dev-api:devorigin-20261107
    logging: !reset {}
    volumes: !override $SECRETS_VOLUME
  conversation-worker:
    image: uonify-dev-conv:devorigin-20261107
    logging: !reset {}
    volumes: !override $SECRETS_VOLUME
  materials-worker:
    image: uonify-dev-api:devorigin-20261107
    logging: !reset {}
    volumes: !override $SECRETS_VOLUME
  billing-worker:
    image: uonify-dev-api:devorigin-20261107
    logging: !reset {}
    volumes: !override $SECRETS_VOLUME
  clips-worker:
    image: uonify-dev-clips:devorigin-20261107
    logging: !reset {}
    volumes: !override $SECRETS_VOLUME
networks:
  outbound: {internal: true}
  edge: {internal: true}
  mailpit-ui: {internal: true}
volumes:
  smoke-pgdata: {}
  smoke-redis: {}
  smoke-secrets: {external: true, name: devhost-rt-check-secrets}
"
smoke() {
    printf '%s' "$SMOKE_OVERRIDE" | API_DIGEST=$dummy CLIPS_DIGEST=$dummy CONV_DIGEST=$dummy \
        UONIFY_TEST_PROJECT_IDS= UONIFY_CREATIVE_OUTPUT_BUCKETS= UONIFY_CREATIVE_OUTPUT_LOCATION= \
        docker compose -p devhost-rt-check -f "$here/compose.yaml" -f - --env-file /dev/null --profile armed "$@"
}
out=$(smoke up -d --quiet-pull db redis mailpit api conversation-worker materials-worker billing-worker clips-worker 2>&1)
code=$?
[ "$code" -eq 0 ] || printf '%s\n' "$out" | tail -5 | sed 's/^/      /'
check "smoke stack started (compose up)" 0 "$code"
for _ in $(seq 1 90); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' devhost-rt-check-api-1 2>/dev/null)" = healthy ] && break
    sleep 2
done
sleep 20   # let the workers run a few loops
for service in db redis mailpit api; do
    check "$service healthy" "healthy" "$(docker inspect -f '{{.State.Health.Status}}' devhost-rt-check-$service-1 2>/dev/null)"
done
for service in conversation-worker materials-worker billing-worker clips-worker; do
    check "$service running read-only, never restarted" "true true 0" \
        "$(docker inspect -f '{{.State.Running}} {{.HostConfig.ReadonlyRootfs}} {{.RestartCount}}' devhost-rt-check-$service-1 2>/dev/null)"
done
check "api hardening as declared" "1000:1000 true [ALL] [no-new-privileges:true] map[/tmp:size=256m]" \
    "$(docker inspect -f '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.CapDrop}} {{.HostConfig.SecurityOpt}} {{.HostConfig.Tmpfs}}' devhost-rt-check-api-1)"
check "db: read-only with 5 capabilities" "true [ALL] [CAP_CHOWN CAP_DAC_OVERRIDE CAP_FOWNER CAP_SETGID CAP_SETUID]" \
    "$(docker inspect -f '{{.HostConfig.ReadonlyRootfs}} {{.HostConfig.CapDrop}} {{.HostConfig.CapAdd}}' devhost-rt-check-db-1)"
check "api sees the host secrets layout (dir 711 root, file 1000:1000 0400, dir not listable)" \
    "711 0:0|400 1000:1000|denied" "$(docker exec devhost-rt-check-api-1 python -I -c '
import os, stat
d, f = os.stat("/run/uonify"), os.stat("/run/uonify/encryption-key")
try:
    os.listdir("/run/uonify"); listing = "listed"
except PermissionError:
    listing = "denied"
print(f"{stat.S_IMODE(d.st_mode):o} {d.st_uid}:{d.st_gid}|{stat.S_IMODE(f.st_mode):o} {f.st_uid}:{f.st_gid}|{listing}")' 2>&1)"
check "db password file as on the host (70:0 0440)" "440 70:0" \
    "$(docker exec devhost-rt-check-db-1 stat -c '%a %u:%g' /run/secrets/postgres-password 2>&1)"
check "no traceback or crash in any service log" 0 \
    "$(smoke logs --no-color 2>&1 | grep -c 'Traceback\|RuntimeError\|Read-only file system\|No usable temporary directory\|Permission denied')"
# Empty creative-execution pilot list: every claim raises "El coordinador creativo permanece
# desactivado" in claim_creative_step; the worker logs only the code, type and frames (no message).
check "clips worker idles fail-closed (empty pilot lists)" 1 \
    "$(smoke logs --no-color clips-worker 2>&1 | grep -c -m1 'Clips-only worker failure:.*ValueError.*claim_creative_step')"
echo "      memory after start (idle, empty DB):"
docker stats --no-stream --format '        {{.Name}} {{.MemUsage}}' $(docker ps -q --filter label=com.docker.compose.project=devhost-rt-check)
smoke down -v --remove-orphans >/dev/null 2>&1
docker volume rm devhost-rt-check-secrets >/dev/null 2>&1
fi

echo "== result: $passed passed, $failed failed"
[ "$failed" -eq 0 ]
