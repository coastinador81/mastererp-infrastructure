#!/usr/bin/env python3
"""Casos de listas piloto compartidos por las pruebas (UUID FICTICIOS; ningún dato real).

Cada caso: (etiqueta, nombre del fichero en /run/uonify, contenido en bytes, ¿lo acepta settings.py?).
La verdad de referencia es pilot_users() de app/settings.py: pilot_parity_in_container.py la comprueba
contra load_settings() de las imágenes api, clips y conv y contra uonify_secrets_render.py;
test_upload_dev_secrets.sh, contra el validador de upload_dev_secrets.sh.

  python3 -I pilot_cases.py write DIR   escribe DIR/NN.json e imprime «NN<TAB>nombre<TAB>1|0<TAB>etiqueta»
"""
import json
import os
import sys

A = '11111111-2222-4333-8444-555555555555'
B = '66666666-7777-4888-9999-000000000000'
ADK = 'adk-pilot-users.json'
LIVE = 'live-pilot-users.json'


def doc(value):
    return json.dumps(value).encode('utf-8')


def padded(size):
    base = doc({'userIds': [A]})
    return base + b' ' * (size - len(base))


CASES = [
    ('válida', ADK, doc({'userIds': [A]}), True),
    ('vacía', ADK, doc({'userIds': []}), True),
    ('dos ids y salto de línea final', 'creative-upload-pilot-users.json', doc({'userIds': [A, B]}) + b'\n', True),
    ('UUID en mayúsculas', 'material-adk-pilot-users.json', doc({'userIds': [A.upper()]}), True),
    ('UUID sin guiones', 'creative-execution-pilot-users.json', doc({'userIds': [A.replace('-', '')]}), True),
    ('clave repetida: vale la última', 'creative-provider-dispatch-pilot-users.json',
     b'{"userIds": ["no-uuid"], "userIds": ["' + A.encode() + b'"]}', True),
    ('exactamente 4096 bytes', ADK, padded(4096), True),
    ('live válida', LIVE, doc({'userIds': [A], 'sessionLimit': 20}), True),
    ('live límite 1', LIVE, doc({'userIds': [A], 'sessionLimit': 1}), True),
    ('live límite 200', LIVE, doc({'userIds': [A], 'sessionLimit': 200}), True),
    ('live-adk válida', 'live-adk-users.json', doc({'userIds': [A]}), True),
    ('live-gateway válida', 'live-gateway-users.json', doc({'userIds': [B]}), True),
    ('clave de más', ADK, doc({'userIds': [A], 'extra': 1}), False),
    ('sin userIds', ADK, doc({'users': [A]}), False),
    ('no es objeto', ADK, doc([A]), False),
    ('null', ADK, b'null', False),
    ('userIds no es lista', ADK, doc({'userIds': A}), False),
    ('id no UUID', ADK, doc({'userIds': ['no-es-un-uuid']}), False),
    ('id no texto', ADK, doc({'userIds': [123]}), False),
    ('id anidado', ADK, doc({'userIds': [[A]]}), False),
    ('duplicado exacto', ADK, doc({'userIds': [A, A]}), False),
    ('duplicado tras normalizar', ADK, doc({'userIds': [A, '{' + A.upper() + '}']}), False),
    ('sessionLimit en lista no live', 'live-adk-users.json', doc({'userIds': [A], 'sessionLimit': 5}), False),
    ('live sin sessionLimit', LIVE, doc({'userIds': [A]}), False),
    ('live límite 0', LIVE, doc({'userIds': [A], 'sessionLimit': 0}), False),
    ('live límite 201', LIVE, doc({'userIds': [A], 'sessionLimit': 201}), False),
    ('live límite booleano', LIVE, doc({'userIds': [A], 'sessionLimit': True}), False),
    ('live límite decimal', LIVE, doc({'userIds': [A], 'sessionLimit': 20.0}), False),
    ('live límite texto', LIVE, doc({'userIds': [A], 'sessionLimit': '20'}), False),
    ('JSON roto', 'live-gateway-users.json', b'{"userIds": [', False),
    ('con BOM UTF-8', ADK, b'\xef\xbb\xbf' + doc({'userIds': [A]}), False),
    ('UTF-8 no válido', 'creative-provider-dispatch-pilot-users.json', b'{"userIds": ["\xff"]}', False),
    ('4097 bytes', ADK, padded(4097), False),
]


def write(directory):
    os.makedirs(directory, exist_ok=True)
    for index, (label, name, content, valid) in enumerate(CASES, 1):
        with open(os.path.join(directory, f'{index:02d}.json'), 'wb') as handle:
            handle.write(content)
        print(f'{index:02d}\t{name}\t{1 if valid else 0}\t{label}')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'write':
        write(sys.argv[2])
    else:
        sys.exit('uso: pilot_cases.py write DIR')
