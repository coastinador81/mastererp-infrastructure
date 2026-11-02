"""Assemble functional owner templates, deploy one DEV stack and verify by IAM invocation.

Requires Python standard library and existing AWS CLI. Reuses the Admin API; no SQL.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STACK = 'mastererp-dev-administration'
REGION = 'us-west-1'
ACCOUNT = '277352717693'


def assemble():
    owners = json.loads((ROOT / 'scripts/administration_lambdas.json').read_text())
    result = {'AWSTemplateFormatVersion': '2010-09-09',
              'Description': 'MasterERP DEV Administration diagnostics using existing Admin API; no database',
              'Parameters': {}, 'Resources': {}, 'Outputs': {}}
    for capability, owner in owners.items():
        source = json.loads((ROOT / 'modules' / owner / 'resources.yml').read_text())
        for section in ('Parameters', 'Resources', 'Outputs'):
            for key, value in source[section].items():
                if key in result[section] and (section != 'Parameters' or result[section][key] != value):
                    raise ValueError('Duplicate or inconsistent declaration: ' + key)
                result[section][key] = value
        function = source['Resources'][capability.title() + 'Function']['Properties']
        assert function['FunctionName']['Fn::Sub'] == 'mastererp-${Environment}-adm-' + capability
    assert len(owners) == 8 and len(result['Resources']) == 48
    assert {x['Type'] for x in result['Resources'].values()} == {
        'AWS::Lambda::Function', 'AWS::IAM::Role', 'AWS::Logs::LogGroup',
        'AWS::ApiGatewayV2::Integration',
        'AWS::ApiGatewayV2::Route', 'AWS::Lambda::Permission'}
    return owners, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile')
    parser.add_argument('--platform-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bucket', required=True, help='Existing private artifact bucket in us-west-1')
    parser.add_argument('--deploy', action='store_true', help='Upload and execute reviewed change set')
    parser.add_argument('--verify', action='store_true', help='Invoke only these technical Lambdas after deployment')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    platform = args.platform_root.resolve()
    owners, template = assemble()
    assert json.loads((platform / 'scripts/administration_lambdas.json').read_text()) == owners
    subprocess.run([sys.executable, str(platform / 'scripts/package_administration.py'),
                    '--output', str(output)], check=True)
    template_path = output / 'administration.json'
    template_path.write_text(json.dumps(template, indent=2) + '\n')
    if not args.deploy:
        print('Prepared locally; no AWS changes. ' + str(template_path))
        return

    def aws(*command, optional=False):
        cmd = ['aws', '--region', REGION, '--output', 'json', '--no-cli-pager']
        if args.profile:
            cmd += ['--profile', args.profile]
        run = subprocess.run(cmd + list(command), capture_output=True, text=True)
        if run.returncode:
            # Only the expected not-found responses permit creation; auth/network errors must stop.
            if optional and ('ResourceNotFoundException' in run.stderr or
                             'does not exist' in run.stderr or 'ResourceNotFound' in run.stderr):
                return None
            raise RuntimeError(run.stderr.strip())
        return json.loads(run.stdout) if run.stdout.strip() else {}

    assert aws('sts', 'get-caller-identity')['Account'] == ACCOUNT
    api_id = template['Parameters']['ExistingAdminApiId']['Default']
    api = aws('apigatewayv2', 'get-api', '--api-id', api_id)
    assert api['Name'] == 'mastererp-dev-admin-api'
    owner = aws('cloudformation', 'describe-stack-resource', '--stack-name',
                'mastererp-dev-onboarding', '--logical-resource-id', 'AdminHttpApi')
    assert owner['StackResourceDetail']['PhysicalResourceId'] == api_id
    assert aws('apigatewayv2', 'get-stage', '--api-id', api_id, '--stage-name', '$default')['AutoDeploy']
    location = aws('s3api', 'get-bucket-location', '--bucket', args.bucket)['LocationConstraint']
    assert location == REGION, 'Artifact bucket must be in us-west-1'
    block = aws('s3api', 'get-public-access-block', '--bucket', args.bucket)['PublicAccessBlockConfiguration']
    assert all(block.get(k) for k in ('BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets'))
    existing = aws('cloudformation', 'describe-stacks', '--stack-name', STACK, optional=True)
    current = aws('cloudformation', 'list-stack-resources', '--stack-name', STACK)['StackResourceSummaries'] if existing else []
    expected_names = {'mastererp-dev-adm-' + cap for cap in owners}
    owned_names = {r['PhysicalResourceId'] for r in current if r['ResourceType'] == 'AWS::Lambda::Function'}
    for name in expected_names:
        found = aws('lambda', 'get-function', '--function-name', name, optional=True)
        if found and name not in owned_names:
            raise RuntimeError('Existing function owned outside this stack: ' + name)
    if current:
        assert {r['LogicalResourceId'] for r in current} <= set(template['Resources']), 'Unexpected existing resources'
    current_ids = {r['LogicalResourceId'] for r in current}
    routes = aws('apigatewayv2', 'get-routes', '--api-id', api_id)['Items']
    for cap in owners:
        if cap.title() + 'HealthRoute' not in current_ids:
            assert not any(r['RouteKey'] == 'GET /v1/administration/' + cap + '/health' for r in routes), 'Route owned elsewhere'
    aws('cloudformation', 'validate-template', '--template-body', 'file://' + str(template_path))
    parameters = [{'ParameterKey': 'Environment', 'ParameterValue': 'dev'},
                  {'ParameterKey': 'ArtifactBucket', 'ParameterValue': args.bucket}]
    for cap in owners:
        name = 'mastererp-dev-adm-' + cap
        archive = output / (name + '.zip')
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        key = 'mastererp/dev/administration/' + name + '/' + digest + '.zip'
        aws('s3api', 'put-object', '--bucket', args.bucket, '--key', key,
            '--body', str(archive), '--content-type', 'application/zip', '--server-side-encryption', 'AES256')
        parameters.append({'ParameterKey': cap.title() + 'ArtifactKey', 'ParameterValue': key})
    change = 'administration-' + str(time.time_ns())
    aws('cloudformation', 'create-change-set', '--stack-name', STACK, '--change-set-name', change,
        '--change-set-type', 'UPDATE' if existing else 'CREATE', '--capabilities', 'CAPABILITY_IAM',
        '--template-body', 'file://' + str(template_path), '--parameters', json.dumps(parameters),
        '--tags', 'Key=Project,Value=MasterERP', 'Key=Environment,Value=dev', 'Key=Component,Value=administration-health')
    # Poll in short intervals so interruption remains possible; do not retry failed deployments.
    deadline = time.monotonic() + 600
    while True:
        plan = aws('cloudformation', 'describe-change-set', '--stack-name', STACK, '--change-set-name', change)
        if plan['Status'] in ('CREATE_COMPLETE', 'FAILED'):
            break
        if time.monotonic() > deadline:
            raise TimeoutError('Change set preparation timed out')
        time.sleep(3)
    if plan['Status'] == 'FAILED':
        if existing and "didn't contain changes" in plan.get('StatusReason', ''):
            print('No infrastructure changes required.')
        else:
            raise RuntimeError(plan.get('StatusReason', 'Change set failed'))
    else:
        changes = [x['ResourceChange'] for x in plan['Changes']]
        for item in changes:
            assert item['LogicalResourceId'] in template['Resources']
            assert item['ResourceType'] == template['Resources'][item['LogicalResourceId']]['Type']
            assert item['Action'] in ('Add', 'Modify') and item.get('Replacement', 'False') == 'False'
        (output / 'changeset.json').write_text(json.dumps(changes, indent=2) + '\n')
        print(json.dumps({'reviewed_changes': changes}, indent=2), flush=True)
        aws('cloudformation', 'execute-change-set', '--stack-name', STACK, '--change-set-name', change)
        deadline = time.monotonic() + 1200
        while True:
            status = aws('cloudformation', 'describe-stacks', '--stack-name', STACK)['Stacks'][0]['StackStatus']
            if status in ('CREATE_COMPLETE', 'UPDATE_COMPLETE'):
                break
            if status.endswith(('FAILED', 'ROLLBACK_COMPLETE')):
                events = aws('cloudformation', 'describe-stack-events', '--stack-name', STACK)
                raise RuntimeError(json.dumps(events['StackEvents'][:8]))
            if time.monotonic() > deadline:
                raise TimeoutError('Deployment still in progress; inspect stack, do not run concurrently')
            time.sleep(5)
    report = []
    for cap in owners:
        name = 'mastererp-dev-adm-' + cap
        config = aws('lambda', 'get-function-configuration', '--function-name', name)
        assert config['State'] == 'Active'
        assert config.get('LastUpdateStatus', 'Successful') == 'Successful'
        assert config['Runtime'] == 'python3.12' and config['MemorySize'] == 128 and config['Timeout'] == 5
        assert not config.get('VpcConfig', {}).get('SubnetIds') and not config.get('Environment', {}).get('Variables')
        digest = hashlib.sha256((output / (name + '.zip')).read_bytes()).digest()
        assert config['CodeSha256'] == base64.b64encode(digest).decode()
        item = {'name': name, 'arn': config['FunctionArn'], 'state': config['State'], 'code_sha256': config['CodeSha256']}
        if args.verify:
            response_path = output / (name + '-response.json')
            meta = aws('lambda', 'invoke', '--function-name', name, '--cli-binary-format', 'raw-in-base64-out',
                       '--payload', '{}', str(response_path))
            assert not meta.get('FunctionError'), meta
            response = json.loads(response_path.read_text())
            assert response['statusCode'] == 200
            assert json.loads(response['body']) == {'status': 'ok', 'lambda': name}
            item.update({'invocation_status': meta['StatusCode'], 'handler_status': response['statusCode'], 'body': json.loads(response['body'])})
        report.append(item)
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'stack': STACK, 'region': REGION, 'functions': report}, indent=2))


if __name__ == '__main__':
    main()
