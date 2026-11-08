#!/usr/bin/env python3
"""Se ejecuta DENTRO de un contenedor desechable (--rm, --network none) de una imagen del backend
(uonify-dev-api, -clips o -conv, solo como entorno; no se modifica), lanzado por
run_pilot_parity_test.sh.

Para cada caso de pilot_cases.py comprueba que coinciden tres veredictos:
  1. load_settings() REAL de app/settings.py de ESA imagen (lanza RuntimeError con el nombre de la lista);
  2. pilot_problem() de uonify_secrets_render.py (lo que el host vuelca o rechaza);
  3. el veredicto esperado escrito en pilot_cases.py (el que también comprueba el validador del Mac).
Una imagen que NO lee una lista (la conv lee 4 de las 8) la acepta sea como sea: para ella se exige
que load_settings() no falle; el veredicto estricto lo fijan las que la leen (api y clips leen las 8).
Solo valores ficticios.
"""
import base64
import importlib.util
import os
import re
import sys
import tempfile

sys.path.insert(0, '/app')
from app.settings import load_settings  # noqa: E402


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cases = load('/t/pilot_cases.py', 'pilot_cases')
render = load('/s/uonify_secrets_render.py', 'uonify_secrets_render')
image = os.environ.get('IMAGE_LABEL', '?')
assert render.PILOT_LISTS == {name for _l, name, _c, _v in cases.CASES}, 'el corpus no cubre las 8 listas'
with open('/app/app/settings.py', encoding='utf-8') as handle:
    read_by_image = set(re.findall(r"pilot_users\('([a-z0-9-]+\.json)'", handle.read()))
unknown = read_by_image - render.PILOT_LISTS
assert not unknown, f'la imagen lee listas piloto que el renderizador no conoce: {sorted(unknown)}'
print(f'  {image} lee {len(read_by_image)} de 8 listas: {", ".join(sorted(read_by_image))}')
if os.environ.get('EXPECT_ALL_LISTS') == '1':
    assert read_by_image == render.PILOT_LISTS, 'se esperaba que esta imagen leyera las 8 listas'
passed = failed = 0
for label, name, content, expected in cases.CASES:
    with tempfile.TemporaryDirectory() as directory:
        for file_name, data in (
                ('google-oauth.json', b'{"web": {"client_id": "1-fake.apps.googleusercontent.com", '
                                      b'"client_secret": "fake-client-secret"}}'),
                ('encryption-key', base64.urlsafe_b64encode(b'F' * 32)),
                ('postgres-password', b'fake-password-0123456789'),
                (name, content)):
            with open(os.path.join(directory, file_name), 'wb') as handle:
                handle.write(data)
        os.environ['UONIFY_SECRETS_DIR'] = directory
        reason = ''
        try:
            load_settings()
            backend = True
        except RuntimeError as exc:
            backend, reason = False, str(exc)
    renderer = render.pilot_problem(name, content) is None
    backend_expected = expected if name in read_by_image else True
    # Un rechazo del backend solo cuenta si es por ESTA lista (si no, la prueba no valdría).
    if not backend and name not in reason:
        print(f'  FAIL {label} ({name}): load_settings falló por otra causa: {reason}')
        failed += 1
    elif backend == backend_expected and renderer == expected:
        note = '' if name in read_by_image else ' (esta imagen no la lee)'
        print(f'  ok   {label} ({name}): settings={backend} render={renderer}{note}')
        passed += 1
    else:
        print(f'  FAIL {label} ({name}): esperado={expected} settings={backend} render={renderer}')
        failed += 1
print(f'RESULTADO paridad listas piloto en {image} (Python {sys.version.split()[0]}): {passed} ok, {failed} fallos')
sys.exit(1 if failed else 0)
