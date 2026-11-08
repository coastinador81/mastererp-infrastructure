#!/usr/bin/env python3
"""Stub LOCAL de la AWS CLI para probar uonify-secrets-sync dentro de un contenedor desechable.

El renderizador pasa a `aws` un entorno mínimo (lista blanca), así que el stub lee su configuración
de rutas fijas del contenedor de prueba:
  /tmp/fixture.json   parámetros {nombre: {Value, Version, Type}}
  /tmp/fail_first     (opcional) número de llamadas iniciales que fallan, para probar reintentos
  /tmp/counter        contador de llamadas
"""
import json
import sys

args = sys.argv[1:]
try:
    calls = int(open('/tmp/counter').read() or 0)
except FileNotFoundError:
    calls = 0
open('/tmp/counter', 'w').write(str(calls + 1))
try:
    fail_first = int(open('/tmp/fail_first').read() or 0)
except FileNotFoundError:
    fail_first = 0
if calls < fail_first:
    print('Could not connect to the endpoint URL: "https://ssm.eu-west-1.amazonaws.com/"', file=sys.stderr)
    sys.exit(255)

with open('/tmp/fixture.json', encoding='utf-8') as handle:
    fixture = json.load(handle)


def option(name):
    return args[args.index(name) + 1] if name in args else None


if not ('--with-decryption' in args and option('--region') == 'eu-west-1' and option('--output') == 'json'):
    print('stub: unexpected flags ' + ' '.join(args), file=sys.stderr)
    sys.exit(2)
if args[:2] == ['ssm', 'get-parameters-by-path']:
    path = option('--path').rstrip('/') + '/'
    params = [dict(Name=name, **item) for name, item in sorted(fixture.items())
              if name.startswith(path) and '/' not in name[len(path):]]
    print(json.dumps({'Parameters': params}))
elif args[:2] == ['ssm', 'get-parameters']:
    name = option('--names')
    if name in fixture:
        print(json.dumps({'Parameters': [dict(Name=name, **fixture[name])], 'InvalidParameters': []}))
    else:
        print(json.dumps({'Parameters': [], 'InvalidParameters': [name]}))
else:
    print('stub: unsupported call', file=sys.stderr)
    sys.exit(2)
