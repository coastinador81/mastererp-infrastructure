#!/usr/bin/env python3
"""Stub LOCAL de la AWS CLI para probar upload_dev_secrets.sh sin tocar AWS (solo valores ficticios).

Guarda los parámetros en FAKE_AWS_STORE (JSON) y registra cada argv en FAKE_AWS_ARGV_LOG para
comprobar que ningún valor viaja por la línea de órdenes.
"""
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ['FAKE_AWS_ARGV_LOG'], 'a', encoding='utf-8') as log:
    log.write(json.dumps(args) + '\n')


def load():
    try:
        with open(os.environ['FAKE_AWS_STORE'], encoding='utf-8') as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}


def save(data):
    with open(os.environ['FAKE_AWS_STORE'], 'w', encoding='utf-8') as handle:
        json.dump(data, handle)


def option(name):
    return args[args.index(name) + 1] if name in args else None


def fail(code, message):
    print(f'An error occurred ({code}) when calling the operation: {message}', file=sys.stderr)
    sys.exit(254)


if args[:1] == ['--version']:
    print('aws-cli/2.36.34 Python/3.13.0 Darwin/27.2.0 exe/arm64')
elif args[:3] == ['configure', 'get', 'cli_history']:
    if os.environ.get('FAKE_CLI_HISTORY'):
        print(os.environ['FAKE_CLI_HISTORY'])
    else:
        sys.exit(1)
elif args[:2] == ['sts', 'get-caller-identity']:
    print(os.environ.get('FAKE_ACCOUNT', '277352717693'))
elif args[:2] == ['kms', 'describe-key']:
    if option('--key-id') != 'alias/uonify-dev':
        fail('NotFoundException', 'alias')
    print('Enabled')
elif args[:2] == ['ssm', 'describe-parameters']:
    for name, item in sorted(load().items()):
        print(f"{name}\t{item['Version']}\tSecureString")
elif args[:2] == ['ssm', 'put-parameter']:
    source = option('--cli-input-json') or ''
    if '--value' in args or not source.startswith('file://'):
        fail('ValidationException', 'the stub only accepts --cli-input-json file://<fichero>')
    path = source[len('file://'):]
    # Como la AWS CLI 2.36 real (comprobado el 08-11-2026): una tubería (/dev/stdin, /dev/fd/0) da
    # «Invalid JSON received» y un FIFO la deja colgada. Solo vale un fichero normal.
    if not os.path.isfile(path):
        fail('ParamValidation', "Error parsing parameter 'cli-input-json': Invalid JSON received.")
    # El documento lleva el valor: exige fichero 0600 dentro de una carpeta 0700.
    if (os.stat(path).st_mode & 0o777 != 0o600
            or os.stat(os.path.dirname(path)).st_mode & 0o777 != 0o700):
        fail('ValidationException', 'the put-parameter document must be 0600 inside a 0700 directory')
    with open(path, encoding='utf-8') as handle:
        document = json.loads(handle.read())
    store = load()
    name = document['Name']
    if (document.get('Type') != 'SecureString' or document.get('KeyId') != 'alias/uonify-dev'
            or document.get('Tier') != 'Standard'):
        fail('ValidationException', 'type/key/tier')
    if not document.get('Value'):
        fail('ValidationException', 'empty value')
    if len(document['Value'].encode('utf-8')) > 4096:
        fail('ValidationException', 'too large')
    if document.get('Overwrite') and document.get('Tags'):
        fail('ValidationException', 'tags and overwrite')
    if name in store and not document.get('Overwrite'):
        fail('ParameterAlreadyExists', 'The parameter already exists.')
    version = store.get(name, {}).get('Version', 0) + 1
    store[name] = {'Value': document['Value'], 'Version': version}
    save(store)
    print(version)
else:
    print('stub: unsupported call ' + ' '.join(args), file=sys.stderr)
    sys.exit(2)
