#!/usr/bin/env python3
"""Stub LOCAL de la AWS CLI (s3 cp / s3api head-object) para probar uonify-pg-backup sin S3.

Reproduce el cifrado del bucket de copias del stack (stack/uonify-dev-backend.yaml):
  - cifrado por defecto SSE-KMS con la CMK (FAKE_S3_CMK_ARN): una subida SIN cabeceras de cifrado
    queda cifrada con ella;
  - política DenyRequestedEncryptionOtherThanDataKey: si la subida lleva cabecera de cifrado
    (--sse / --sse-kms-key-id) y el id de clave no es EXACTAMENTE el ARN de la CMK -> AccessDenied.
    S3 compara la cabecera tal cual: un alias, un id corto, aws:kms sin id o AES256 se deniegan;
  - SSE-C bloqueado en el bucket.
Guarda los objetos en FAKE_S3_DIR/<bucket>/<clave> y, al lado, <clave>.sse.json con el cifrado
aplicado y si la petición llevaba cabeceras de cifrado. head-object responde como la CLI real con
--query '[ServerSideEncryption, SSEKMSKeyId, ContentLength]' --output text.
"""
import json
import os
import shutil
import sys

DEFAULT_CMK = 'arn:aws:kms:eu-west-1:277352717693:key/11111111-2222-4333-8444-555555555555'
args = sys.argv[1:]
root = os.environ['FAKE_S3_DIR']
cmk = os.environ.get('FAKE_S3_CMK_ARN', DEFAULT_CMK)


def option(name):
    return args[args.index(name) + 1] if name in args else None


def target(url):
    assert url.startswith('s3://'), url
    bucket, key = url[5:].split('/', 1)
    path = os.path.join(root, bucket, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def denied(source, dest):
    print(f'upload failed: {source} to {dest} An error occurred (AccessDenied) when calling the '
          'PutObject operation: User: arn:aws:sts::277352717693:assumed-role/uonify-dev-host/i-0fake '
          f'is not authorized to perform: s3:PutObject on resource: "arn:aws:s3:::{dest[5:]}" '
          'with an explicit deny in a resource-based policy', file=sys.stderr)
    sys.exit(1)


if args[:2] == ['s3', 'cp']:
    source, dest = args[2], args[3]
    sse, key_id = option('--sse'), option('--sse-kms-key-id')
    if '--sse-c' in args or '--sse-c-key' in args:
        denied(source, dest)
    requested = sse is not None or key_id is not None
    if requested and not (sse == 'aws:kms' and key_id == cmk):
        denied(source, dest)
    path = target(dest)
    if source == '-':
        with open(path, 'wb') as out:
            shutil.copyfileobj(sys.stdin.buffer, out, 1 << 20)
    else:
        shutil.copyfile(source, path)
    with open(path + '.sse.json', 'w') as meta:
        json.dump({'sse': 'aws:kms', 'kms': cmk, 'requested_headers': requested}, meta)
elif args[:2] == ['s3api', 'head-object']:
    path = os.path.join(root, option('--bucket'), option('--key'))
    assert option('--query') == '[ServerSideEncryption, SSEKMSKeyId, ContentLength]', option('--query')
    assert option('--output') == 'text'
    meta = json.load(open(path + '.sse.json'))
    print(f"{meta['sse']}\t{meta['kms']}\t{os.path.getsize(path)}")
else:
    print('stub: unsupported call ' + ' '.join(args), file=sys.stderr)
    sys.exit(2)
