"""Read-only preservation checks and real technical HTTP probes for Finance adoption."""
import argparse
import json
from pathlib import Path
import urllib.error
import urllib.request

import boto3


def snapshot(session):
    cf = session.client('cloudformation')
    api = session.client('apigatewayv2')
    functions = session.client('lambda')
    result = {'apis': {}, 'functions': {}, 'administration_resources': {}}
    for item in api.get_apis()['Items']:
        aid = item['ApiId']
        result['apis'][aid] = {'api': item}
        for operation, field, key in [('get_routes', 'routes', 'RouteId'),
                                      ('get_integrations', 'integrations', 'IntegrationId'),
                                      ('get_authorizers', 'authorizers', 'AuthorizerId')]:
            rows = []
            args = {'ApiId': aid}
            while True:
                page = getattr(api, operation)(**args)
                rows.extend(page.get('Items', []))
                if not page.get('NextToken'):
                    break
                args['NextToken'] = page['NextToken']
            result['apis'][aid][field] = {row[key]: row for row in rows}
    for page in functions.get_paginator('list_functions').paginate():
        for fn in page['Functions']:
            if fn['FunctionName'].startswith('mastererp-'):
                result['functions'][fn['FunctionName']] = {k: fn[k] for k in [
                    'FunctionArn', 'CodeSha256', 'Runtime', 'Role', 'MemorySize', 'Timeout', 'LastModified']}
    for page in cf.get_paginator('list_stack_resources').paginate(StackName='mastererp-dev-administration'):
        for resource in page['StackResourceSummaries']:
            result['administration_resources'][resource['LogicalResourceId']] = {
                k: resource[k] for k in ['PhysicalResourceId', 'ResourceType']}
    db = session.client('rds').describe_db_instances(DBInstanceIdentifier='mastererp-dev-data')['DBInstances'][0]
    result['database'] = {k: db[k] for k in ['DBInstanceArn', 'DBInstanceIdentifier', 'DBName',
                                           'Endpoint', 'DBInstanceClass', 'AllocatedStorage', 'EngineVersion']}
    result['http'] = []
    for capability in ['clientes', 'ventas', 'proveedores', 'compras', 'cartera', 'tesoreria', 'conciliacion', 'gastos']:
        url = 'https://qx8nmypdhi.execute-api.us-west-1.amazonaws.com/v1/administration/' + capability + '/health'
        with urllib.request.urlopen(url, timeout=30) as response:
            body = json.load(response)
            assert response.status == 200 and body == {'status': 'ok', 'lambda': 'mastererp-dev-adm-' + capability}
            result['http'].append({'url': url, 'http': response.status, 'body': body})
    for path in ['/v1/uonify/spaces', '/v1/uonify/google/connection/status']:
        url = 'https://ebn01q74hh.execute-api.us-west-1.amazonaws.com' + path
        try:
            urllib.request.urlopen(url, timeout=30)
        except urllib.error.HTTPError as error:
            assert error.code == 401
            result['http'].append({'url': url, 'without_token': error.code})
        else:
            raise AssertionError('Protected Uonify route no longer rejects missing token')
    return json.loads(json.dumps(result, default=str))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default='mastererp-admin')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=['before', 'after-import', 'after-update'], required=True)
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile, region_name='us-west-1')
    assert session.client('sts').get_caller_identity()['Account'] == '277352717693'
    now = snapshot(session)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.phase != 'before':
        baseline = json.loads((args.output / 'preservation-before.json').read_text())
        assert now == baseline, 'Resource configuration, identifiers or HTTP results changed'
    (args.output / ('preservation-' + args.phase + '.json')).write_text(json.dumps(now, indent=2) + '\n')
    print(json.dumps({'phase': args.phase, 'apis': len(now['apis']), 'lambdas': len(now['functions']),
                      'administration_resources': len(now['administration_resources']),
                      'health_http_200': 8, 'protected_uonify_without_token_401': 2,
                      'database_metadata_unchanged': args.phase != 'before',
                      'credentials_used': False, 'sql_executed': False}))


if __name__ == '__main__':
    main()
