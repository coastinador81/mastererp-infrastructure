#!/usr/bin/env python3
"""Stub LOCAL de la AWS CLI (route53) para probar el hook DNS-01 sin tocar Route 53.

Registra cada llamada en /tmp/r53-calls.jsonl (con el change batch leído). get-change devuelve
PENDING las N primeras veces (/tmp/r53-pending, por defecto 2) y luego INSYNC. Si existe
/tmp/r53-fail-delete, el DELETE falla como en Route 53 cuando el registro ya no existe.
"""
import json
import os
import sys

args = sys.argv[1:]


def option(name):
    return args[args.index(name) + 1] if name in args else None


record = {'args': args}
if args[:2] == ['route53', 'change-resource-record-sets']:
    batch_ref = option('--change-batch')
    assert batch_ref.startswith('file://'), batch_ref
    batch = json.load(open(batch_ref[len('file://'):]))
    record['batch'] = batch
    action = batch['Changes'][0]['Action']
    with open('/tmp/r53-calls.jsonl', 'a') as log:
        log.write(json.dumps(record) + '\n')
    if action == 'DELETE' and os.path.exists('/tmp/r53-fail-delete'):
        print('An error occurred (InvalidChangeBatch) when calling the ChangeResourceRecordSets '
              'operation: Tried to delete resource record set but it was not found', file=sys.stderr)
        sys.exit(254)
    assert option('--hosted-zone-id') == 'Z08167243FAUSDUW0Z2KP'
    assert option('--query') == 'ChangeInfo.Id' and option('--output') == 'text'
    print('/change/C0FAKE' + action)
elif args[:2] == ['route53', 'get-change']:
    with open('/tmp/r53-calls.jsonl', 'a') as log:
        log.write(json.dumps(record) + '\n')
    try:
        pending = int(open('/tmp/r53-pending').read())
    except FileNotFoundError:
        pending = 2
    open('/tmp/r53-pending', 'w').write(str(pending - 1))
    print('PENDING' if pending > 0 else 'INSYNC')
else:
    print('stub: unsupported call', file=sys.stderr)
    sys.exit(2)
