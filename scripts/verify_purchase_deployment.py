"""Read-only before/after preservation checks for the DEV purchase batch."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import boto3


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--phase', choices=['before', 'after'], required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    s = boto3.Session(profile_name='mastererp-admin', region_name='us-west-1')
    assert s.client('sts').get_caller_identity()['Account'] == '277352717693'
    api, lam = s.client('apigatewayv2'), s.client('lambda')
    def items(operation):
        return [x for page in api.get_paginator(operation).paginate(ApiId='qx8nmypdhi') for x in page['Items']]
    state = {'routes': {r['RouteKey']: r for r in items('get_routes')},
             'integrations': {r['IntegrationId']: r for r in items('get_integrations')},
             'authorizers': {r['AuthorizerId']: r for r in items('get_authorizers')},
             'cors': api.get_api(ApiId='qx8nmypdhi').get('CorsConfiguration'), 'lambdas': {}}
    for cap in ('clientes', 'ventas', 'proveedores', 'compras', 'cartera', 'tesoreria', 'conciliacion', 'gastos'):
        c = lam.get_function_configuration(FunctionName='mastererp-dev-adm-' + cap)
        state['lambdas'][cap] = {k: c.get(k) for k in ('FunctionArn', 'Role', 'CodeSha256')}
        assert c['State'] == 'Active' and c['LastUpdateStatus'] == 'Successful'
    with urllib.request.urlopen('https://app-dev.uonify.com/', timeout=20) as response:
        state['uonify_entry_sha256'] = hashlib.sha256(response.read()).hexdigest()
    if args.phase == 'after':
        before = json.loads((args.output / 'resources-before.json').read_text())
        for key, route in before['routes'].items():
            assert state['routes'].get(key) == route, 'Existing route changed: ' + key
        assert state['integrations'] == before['integrations'], 'Existing integrations changed'
        assert state['authorizers'] == before['authorizers'] and state['cors'] == before['cors']
        for cap, config in before['lambdas'].items():
            assert state['lambdas'][cap]['FunctionArn'] == config['FunctionArn']
            assert state['lambdas'][cap]['Role'] == config['Role']
            if cap != 'compras':
                assert state['lambdas'][cap]['CodeSha256'] == config['CodeSha256'], 'Unrelated function changed: ' + cap
        assert state['uonify_entry_sha256'] == before['uonify_entry_sha256'], 'Uonify entry changed'
        additions = set(state['routes']) - set(before['routes'])
        expected = {'GET /v1/administration/compras/opciones'}
        for collection in ('solicitudes', 'ordenes', 'facturas'):
            expected |= {m + ' /v1/administration/compras/' + collection + tail
                         for m, tail in [('GET', ''), ('GET', '/{id}'), ('POST', ''), ('PATCH', '/{id}')]}
        assert additions == expected, 'Unexpected route additions'
        for key in additions:
            assert state['routes'][key]['AuthorizationType'] == 'JWT'
    (args.output / ('resources-' + args.phase + '.json')).write_text(json.dumps(state, indent=2))
    print(json.dumps({'phase': args.phase, 'status': 'passed', 'routes': len(state['routes']),
                      'integrations': len(state['integrations']), 'lambdas': len(state['lambdas'])}))


if __name__ == '__main__':
    main()
