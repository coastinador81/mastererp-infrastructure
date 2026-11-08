#!/usr/bin/python3 -I
"""Uonify DEV · vuelca los parámetros SecureString de SSM a los tmpfs del host.

Lo ejecuta /usr/local/sbin/uonify-secrets-sync (servicio uonify-secrets, antes de docker.service).
Se instala en /usr/local/lib/uonify/uonify_secrets_render.py.

Contrato (D-DEV-HOSTING-20261107):
  /uonify/dev/run/<fichero>        -> /run/uonify/<fichero>             1000:1000 0400 (api y workers)
  /uonify/dev/run/postgres-password -> /run/uonify-db/postgres-password    70:0    0440 (POSTGRES_PASSWORD_FILE)
                                    -> /run/uonify-db/pgpass               70:70   0400 (copias/restauración)
  /uonify/dev/edge/origin-verify    -> /run/uonify-edge/origin-verify       0:0    0400 (cabecera X-Origin-Verify)
  Un valor igual a EMPTY_MARKER se escribe como fichero VACÍO (stripe-test-vat21: SSM no admite vacíos).
  El fichero de borde lleva 1 valor por línea (2 mientras se rota la cabecera de CloudFront), cada uno
  [A-Za-z0-9_-]{32,256}: es el contrato de runtime/compose.yaml, cuyo nginx-entrypoint.sh lo convierte
  al arrancar en un map exacto (regex) para nginx.

Garantías:
  - Nunca escribe valores en stdout/stderr ni en ficheros de log: solo nombres y versiones.
  - Los valores viajan de la salida de `aws` (en memoria) a ficheros en tmpfs; jamás a disco.
  - Valida y prepara TODO antes de escribir; cada fichero se sustituye de forma atómica (rename).
  - Sin google-oauth.json, encryption-key o postgres-password válidos termina con error y no toca nada.
  - Sin secreto de borde válido NO hay /run/uonify-edge/origin-verify: nginx no arranca (falla cerrado).
  - Una lista piloto que pilot_users() de app/settings.py rechazaría (la API y los workers no
    arrancarían) NO se vuelca: se conserva el fichero anterior si era válido o la lista queda ausente
    (piloto apagado). Avisa y termina con 0: una lista mal escrita no impide arrancar Docker.
"""
import base64
import json
import os
import re
import stat
import subprocess
import sys
import time
import uuid

REGION = 'eu-west-1'
AWS = os.environ.get('UONIFY_AWS_BIN', '/usr/local/bin/aws')
RUN_PATH = '/uonify/dev/run'
EDGE_PARAM = '/uonify/dev/edge/origin-verify'
EMPTY_MARKER = '__UONIFY_EMPTY_FILE__'

BACKEND_DIR = '/run/uonify'
DB_DIR = '/run/uonify-db'
EDGE_DIR = '/run/uonify-edge'
BACKEND_OWNER = (1000, 1000, 0o400)
# postgres-password: dueño 70 (postgres) y grupo 0, para que la fase root del entrypoint oficial lo lea
# sin CAP_DAC_OVERRIDE. pgpass: libpq exige que no sea legible por grupo ni otros (0400).
DB_PASSWORD_OWNER = (70, 0, 0o440)
PGPASS_OWNER = (70, 70, 0o400)
# Lo lee el entrypoint de nginx como root (sin CAP_DAC_OVERRIDE): dueño root.
EDGE_OWNER = (0, 0, 0o400)
EDGE_FILE = 'origin-verify'

REQUIRED = ('google-oauth.json', 'encryption-key', 'postgres-password')
NAME_RE = re.compile(r'[a-z0-9][a-z0-9._-]{0,99}')
EDGE_RE = re.compile(r'[A-Za-z0-9_-]{32,256}')
PASSWORD_RE = re.compile(r'[\x21-\x7e]{12,512}')
MAX_VALUE = 64 * 1024
ATTEMPTS = int(os.environ.get('UONIFY_SECRETS_ATTEMPTS', '10'))
# Listas que lee pilot_users() de app/settings.py (igual en api, clips y conv).
PILOT_LISTS = frozenset({
    'adk-pilot-users.json', 'material-adk-pilot-users.json', 'live-pilot-users.json',
    'live-adk-users.json', 'live-gateway-users.json', 'creative-execution-pilot-users.json',
    'creative-provider-dispatch-pilot-users.json', 'creative-upload-pilot-users.json'})
LIVE_PILOT_LIST = 'live-pilot-users.json'
PILOT_MAX_BYTES = 4096


class Fatal(Exception):
    """Error sin valores secretos en el mensaje."""


def log(message):
    print('uonify-secrets: ' + message, flush=True)


def aws_env():
    env = {key: value for key, value in os.environ.items()
           if key in ('PATH', 'HOME', 'LANG', 'LC_ALL', 'AWS_PROFILE', 'AWS_CONFIG_FILE',
                      'AWS_SHARED_CREDENTIALS_FILE', 'AWS_EC2_METADATA_SERVICE_ENDPOINT')}
    env.setdefault('HOME', '/root')
    env.setdefault('PATH', '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')
    env.update({'AWS_REGION': REGION, 'AWS_DEFAULT_REGION': REGION, 'AWS_PAGER': '',
                'AWS_CLI_AUTO_PROMPT': 'off'})
    return env


def error_code(stderr):
    """Solo el código de error de AWS (p. ej. AccessDeniedException), nunca el texto completo."""
    text = stderr.decode('utf-8', 'replace') if isinstance(stderr, bytes) else str(stderr)
    match = re.search(r'An error occurred \(([A-Za-z0-9.]+)\)', text)
    if match:
        return match.group(1)
    for hint, code in (('Unable to locate credentials', 'NoCredentials'),
                       ('Could not connect to the endpoint URL', 'EndpointUnreachable'),
                       ('Connect timeout', 'ConnectTimeout'), ('Read timeout', 'ReadTimeout')):
        if hint in text:
            return code
    return 'error desconocido'


def aws_json(args, what):
    command = [AWS, *args, '--region', REGION, '--output', 'json', '--no-cli-pager']
    delay = 2
    for attempt in range(1, ATTEMPTS + 1):
        try:
            proc = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                  timeout=90, env=aws_env(), check=False)
        except FileNotFoundError as exc:
            raise Fatal(f'no encuentro la AWS CLI en {AWS}') from exc
        except subprocess.TimeoutExpired:
            code = 'timeout'
        else:
            if proc.returncode == 0:
                try:
                    return json.loads(proc.stdout or b'{}')
                except ValueError as exc:
                    raise Fatal(f'{what}: la AWS CLI no devolvió JSON') from exc
            code = error_code(proc.stderr)
        if attempt == ATTEMPTS:
            raise Fatal(f'{what}: falló tras {ATTEMPTS} intentos ({code})')
        log(f'aviso: {what} falló (intento {attempt}/{ATTEMPTS}: {code}); reintento en {delay}s')
        time.sleep(delay)
        delay = min(delay * 2, 30)
    raise Fatal(f'{what}: sin respuesta')


def fetch_run_parameters():
    data = aws_json(['ssm', 'get-parameters-by-path', '--path', RUN_PATH, '--with-decryption'],
                    f'get-parameters-by-path {RUN_PATH}')
    files, notes = {}, []
    for item in data.get('Parameters') or []:
        full = item.get('Name') or ''
        name = full[len(RUN_PATH) + 1:] if full.startswith(RUN_PATH + '/') else ''
        if not NAME_RE.fullmatch(name) or '..' in name:
            notes.append(f'ignorado (nombre no permitido): {full!r}')
            continue
        if item.get('Type') != 'SecureString':
            notes.append(f'ignorado (no es SecureString, no se vuelca): {name}')
            continue
        value = item.get('Value')
        if not isinstance(value, str):
            notes.append(f'ignorado (sin valor): {name}')
            continue
        content = b'' if value == EMPTY_MARKER else value.encode('utf-8')
        if len(content) > MAX_VALUE:
            notes.append(f'ignorado (demasiado grande): {name}')
            continue
        files[name] = (content, item.get('Version'), value == EMPTY_MARKER)
    return files, notes


def fetch_edge_secret():
    data = aws_json(['ssm', 'get-parameters', '--names', EDGE_PARAM, '--with-decryption'],
                    f'get-parameters {EDGE_PARAM}')
    for item in data.get('Parameters') or []:
        if item.get('Name') != EDGE_PARAM:
            continue
        value = item.get('Value')
        if item.get('Type') != 'SecureString':
            return None, item.get('Version'), 'no es SecureString'
        if not isinstance(value, str):
            return None, item.get('Version'), 'sin valor'
        lines = [line.rstrip('\r') for line in value.split('\n') if line.strip()]
        if not 1 <= len(lines) <= 2 or not all(EDGE_RE.fullmatch(line) for line in lines):
            return None, item.get('Version'), 'formato no válido (1 o 2 líneas [A-Za-z0-9_-]{32,256})'
        return ('\n'.join(lines) + '\n').encode('ascii'), item.get('Version'), len(lines)
    return None, None, 'no existe'


def validate_core(files):
    missing = [name for name in REQUIRED if name not in files or files[name][2]]
    if missing:
        raise Fatal('faltan en SSM (' + RUN_PATH + '): ' + ', '.join(missing)
                    + '. El dueño debe ejecutar upload_dev_secrets.sh --apply.')
    try:
        client = json.loads(files['google-oauth.json'][0].decode('utf-8'))
        web = client.get('web') if isinstance(client, dict) else None
        if not (isinstance(web, dict) and isinstance(web.get('client_id'), str) and web['client_id']
                and isinstance(web.get('client_secret'), str) and web['client_secret']):
            raise ValueError
    except (ValueError, UnicodeError) as exc:
        raise Fatal('google-oauth.json no es un cliente OAuth web válido (valor no mostrado)') from exc
    try:
        key = base64.urlsafe_b64decode(files['encryption-key'][0].strip())
        if len(key) != 32:
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise Fatal('encryption-key no es una clave Fernet válida (valor no mostrado)') from exc
    password = files['postgres-password'][0].decode('utf-8', 'replace').rstrip('\r\n')
    if not PASSWORD_RE.fullmatch(password):
        raise Fatal('postgres-password no es válida: 12-512 caracteres ASCII imprimibles sin espacios')
    for name, (content, _version, _empty) in files.items():
        if name.endswith('.json') and name not in REQUIRED and name not in PILOT_LISTS and content:
            try:
                json.loads(content.decode('utf-8'))
            except (ValueError, UnicodeError):
                log(f'aviso: {name} no es JSON válido; se vuelca igual y el backend decidirá')
    return password


def pilot_problem(name, content):
    """Motivo (sin valores) por el que pilot_users() de settings.py rechazaría la lista, o None.

    Mismas reglas: como mucho 4096 bytes; JSON (UTF-8 sin BOM) con EXACTAMENTE la clave userIds (y
    sessionLimit en live-pilot-users.json); userIds lista de UUID en texto, sin repetir tras
    normalizar; sessionLimit entero (no booleano) entre 1 y 200.
    """
    if len(content) > PILOT_MAX_BYTES:
        return 'ocupa más de 4096 bytes'
    try:
        data = json.loads(content.decode('utf-8'))
    except (ValueError, UnicodeError):
        return 'no es JSON válido (UTF-8 sin BOM)'
    live = name == LIVE_PILOT_LIST
    expected = {'userIds', 'sessionLimit'} if live else {'userIds'}
    if not isinstance(data, dict) or set(data) != expected:
        return 'debe ser un objeto JSON con exactamente las claves ' + ' y '.join(sorted(expected, reverse=True))
    if not isinstance(data['userIds'], list):
        return 'userIds debe ser una lista'
    seen = set()
    for position, value in enumerate(data['userIds'], 1):
        try:
            if not isinstance(value, str):
                raise ValueError
            normalized = str(uuid.UUID(value))
        except ValueError:
            return f'el id n.º {position} de userIds no es un UUID en texto'
        if normalized in seen:
            return 'userIds tiene ids repetidos'
        seen.add(normalized)
    if live and (type(data['sessionLimit']) is not int or not 1 <= data['sessionLimit'] <= 200):
        return 'sessionLimit debe ser un entero entre 1 y 200'
    return None


def read_current(path):
    """Contenido actual de un fichero regular (sin seguir enlaces), o None."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
            if sum(len(part) for part in chunks) > MAX_VALUE:
                return None
        return b''.join(chunks)
    finally:
        os.close(fd)


def pgpass_line(password):
    escaped = password.replace('\\', '\\\\').replace(':', '\\:')
    return ('*:*:*:uonify:' + escaped + '\n').encode('utf-8')


def check_directory(directory):
    info = os.lstat(directory)
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise Fatal(f'{directory} no es un directorio')
    if info.st_uid != 0:
        raise Fatal(f'{directory} no pertenece a root')
    os.chmod(directory, 0o711)


def current_matches(path, content, owner):
    uid, gid, mode = owner
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return False
    except OSError:
        return False
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_gid != gid
                or stat.S_IMODE(info.st_mode) != mode or info.st_size != len(content)):
            return False
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        return b''.join(chunks) == content
    finally:
        os.close(fd)


def write_atomic(directory, name, content, owner):
    uid, gid, mode = owner
    temp = os.path.join(directory, f'.tmp-{name}-{os.getpid()}')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        view = memoryview(content)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fchown(fd, uid, gid)
        os.fchmod(fd, mode)
    except BaseException:
        os.close(fd)
        os.unlink(temp)
        raise
    os.close(fd)
    os.replace(temp, os.path.join(directory, name))


def sync_directory(directory, wanted, keep=frozenset()):
    """wanted: {nombre: (contenido, (uid, gid, modo))}; keep: nombres que no se escriben ni se retiran.

    Devuelve (cambiados, iguales, retirados).
    """
    check_directory(directory)
    changed, same, removed = [], [], []
    for name in sorted(wanted):
        content, owner = wanted[name]
        if current_matches(os.path.join(directory, name), content, owner):
            same.append(name)
        else:
            write_atomic(directory, name, content, owner)
            changed.append(name)
    with os.scandir(directory) as entries:
        leftovers = [entry for entry in entries if entry.name not in wanted and entry.name not in keep]
    for entry in leftovers:
        if entry.is_dir(follow_symlinks=False):
            log(f'aviso: {directory}/{entry.name} es un directorio inesperado; no lo toco')
            continue
        os.unlink(os.path.join(directory, entry.name))
        removed.append(entry.name)
    return changed, same, removed


def main():
    if os.geteuid() != 0:
        raise Fatal('hay que ejecutarlo como root')
    files, notes = fetch_run_parameters()
    for note in notes:
        log('aviso: ' + note)
    password = validate_core(files)
    edge_content, edge_version, edge_detail = fetch_edge_secret()

    # Listas piloto que la API rechazaría: no se vuelcan. Se conserva el fichero anterior solo si
    # también cumple las reglas; si no, se retira (lista ausente = piloto apagado, la API arranca).
    rejected, kept = {}, set()
    for name in sorted(PILOT_LISTS & set(files)):
        problem = pilot_problem(name, files[name][0])
        if problem:
            rejected[name] = problem
            previous = read_current(os.path.join(BACKEND_DIR, name))
            if previous is not None and pilot_problem(name, previous) is None:
                kept.add(name)

    backend = {name: (content, BACKEND_OWNER) for name, (content, _v, _e) in files.items()
               if name not in rejected}
    database = {'postgres-password': (files['postgres-password'][0], DB_PASSWORD_OWNER),
                'pgpass': (pgpass_line(password), PGPASS_OWNER)}
    edge = {EDGE_FILE: (edge_content, EDGE_OWNER)} if edge_content is not None else {}

    for directory, wanted, keep in ((BACKEND_DIR, backend, frozenset(kept)), (DB_DIR, database, frozenset()),
                                    (EDGE_DIR, edge, frozenset())):
        changed, same, removed = sync_directory(directory, wanted, keep)
        log(f'{directory}: {len(wanted)} fichero(s); cambiados: {", ".join(changed) or "ninguno"}; '
            f'sin cambios: {len(same)}; retirados: {", ".join(removed) or "ninguno"}')
    for name in sorted(files):
        _content, version, empty = files[name]
        log(f'  {name} (versión {version}){" [vacío por marcador]" if empty else ""}')
    for name, problem in sorted(rejected.items()):
        outcome = ('se conserva el fichero anterior' if name in kept
                   else 'no se vuelca: queda ausente (piloto apagado)')
        log(f'AVISO: {name} (SSM versión {files[name][1]}) NO es una lista piloto válida para el backend '
            f'({problem}); {outcome}. Corrígela con upload_dev_secrets.sh --extra-file ... --force --apply.')
    if edge_content is None:
        log(f'puerta de origen: SIN {EDGE_DIR}/{EDGE_FILE} ({EDGE_PARAM} {edge_detail}); '
            'nginx no arrancará hasta que exista (falla cerrado)')
    else:
        log(f'puerta de origen: {edge_detail} valor(es) X-Origin-Verify en {EDGE_DIR}/{EDGE_FILE} '
            f'({EDGE_PARAM} versión {edge_version})')
    log(('listo CON AVISOS (listas piloto no válidas, arriba). ' if rejected else 'listo. ')
        + 'Los contenedores leen /run/uonify al arrancar: reinicia los que deban ver un cambio.')


if __name__ == '__main__':
    try:
        main()
    except Fatal as problem:
        log('ERROR: ' + str(problem))
        sys.exit(1)
