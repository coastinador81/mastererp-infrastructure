"""DEV-only adoption of the existing Administration stack under Finance.

Prepare and review separate IMPORT and UPDATE change sets. Never recreate a child stack.
Requires the existing boto3 SDK; no SQL, Lambda deployment or credential provisioning.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import boto3
from botocore.exceptions import ClientError
from deploy_administration import assemble

ROOT = Path(__file__).resolve().parents[1]
REGION = 'us-west-1'
ACCOUNT = '277352717693'
PARENT = 'mastererp-dev-finance'
CHILD = 'mastererp-dev-administration'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default='mastererp-admin')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--action', choices=['prepare-import', 'execute-import', 'prepare-update', 'execute-update'], required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    session = boto3.Session(profile_name=args.profile, region_name=REGION)
    assert session.client('sts').get_caller_identity()['Account'] == ACCOUNT
    cf = session.client('cloudformation')
    child = cf.describe_stacks(StackName=CHILD)['Stacks'][0]
    assert child['StackStatus'] in ['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'IMPORT_COMPLETE']
    values = {p['ParameterKey']: p['ParameterValue'] for p in child['Parameters']}
    assert values['Environment'] == 'dev'
    assert values['ExistingAdminApiId'] == 'qx8nmypdhi'
    root_template = json.loads((ROOT / 'modules/2.2-finance/resources.yml').read_text())
    _, candidate = assemble()
    actual = cf.get_template(StackName=CHILD, TemplateStage='Original')['TemplateBody']
    actual = json.loads(actual) if isinstance(actual, str) else actual
    assert candidate['Resources'] == actual['Resources'], 'All existing resource properties must remain identical'
    assert len(actual['Resources']) == 48
    tags = {t['Key']: t['Value'] for t in child.get('Tags', [])}
    assert tags == {'Project': 'MasterERP', 'Environment': 'dev', 'Component': 'administration-health'}
    try:
        parent = cf.describe_stacks(StackName=PARENT)['Stacks'][0]
    except ClientError as error:
        if 'does not exist' not in error.response['Error'].get('Message', ''):
            raise
        parent = None
    if args.action.endswith('import'):
        assert not child.get('ParentId'), 'Child already nested; do not reimport'
        assert parent is None or parent['StackStatus'] == 'REVIEW_IN_PROGRESS'
    else:
        assert parent and child.get('ParentId') == parent['StackId']
        assert parent['StackStatus'] in ['IMPORT_COMPLETE', 'UPDATE_COMPLETE']

    phase = 'import' if args.action.endswith('import') else 'update'
    # IMPORT cannot add/change outputs. Publish the parent's outputs in the separate F2 UPDATE.
    if phase == 'import':
        root_template.pop('Outputs', None)
        # Nested import validates actual parameter values; bootstrap must use literals,
        # not parent Ref expressions. F2 restores the parameterized parent afterwards.
        properties = root_template['Resources']['Administration']['Properties']
        properties['Parameters'] = dict(values)
        # The API parameter was introduced later using its default, not supplied
        # explicitly to the original stack. Nested import expects the original ten
        # explicitly supplied parameters, not all effective DescribeStacks values.
        api_default = actual['Parameters']['ExistingAdminApiId']['Default']
        assert values['ExistingAdminApiId'] == api_default
        properties['Parameters'].pop('ExistingAdminApiId')
        properties['Tags'] = list(child.get('Tags', []))
    record = out / ('finance-' + phase + '-plan.json')
    if args.action.startswith('prepare'):
        # Upload exact deployed template for adoption; candidate only changes composition metadata/parameter constraints.
        template = actual if phase == 'import' else candidate
        data = (json.dumps(template, sort_keys=True, separators=(',', ':')) + '\n').encode()
        digest = hashlib.sha256(data).hexdigest()
        bucket = values['ArtifactBucket']
        s3 = session.client('s3')
        assert s3.get_bucket_location(Bucket=bucket)['LocationConstraint'] == REGION
        block = s3.get_public_access_block(Bucket=bucket)['PublicAccessBlockConfiguration']
        assert all(block.values())
        key = 'mastererp/dev/finance/templates/' + digest + '.json'
        s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType='application/json', ServerSideEncryption='AES256')
        url = 'https://' + bucket + '.s3.' + REGION + '.amazonaws.com/' + key
        parameters = [{'ParameterKey': k, 'ParameterValue': v} for k, v in values.items()]
        parameters.append({'ParameterKey': 'AdministrationTemplateUrl', 'ParameterValue': url})
        assert {p['ParameterKey'] for p in parameters} == set(root_template['Parameters'])
        cf.validate_template(TemplateBody=json.dumps(root_template))
        cf.validate_template(TemplateBody=json.dumps(template))
        request = dict(StackName=PARENT, ChangeSetName='finance-' + phase + '-' + str(time.time_ns()),
                       ChangeSetType='IMPORT' if phase == 'import' else 'UPDATE',
                       TemplateBody=json.dumps(root_template), Parameters=parameters,
                       Capabilities=['CAPABILITY_IAM'])
        if phase == 'import':
            request['ResourcesToImport'] = [{'ResourceType': 'AWS::CloudFormation::Stack',
                                            'LogicalResourceId': 'Administration',
                                            'ResourceIdentifier': {'StackId': child['StackId']}}]
        else:
            request['IncludeNestedStacks'] = True
        plan = cf.create_change_set(**request)
        deadline = time.monotonic() + 600
        while True:
            state = cf.describe_change_set(ChangeSetName=plan['Id'])
            if state['Status'] in ['CREATE_COMPLETE', 'FAILED']:
                break
            if time.monotonic() > deadline:
                raise TimeoutError('Change set still preparing')
            time.sleep(3)
        if state['Status'] != 'CREATE_COMPLETE':
            raise RuntimeError(state.get('StatusReason', 'Change set preparation failed'))
        changes = [x['ResourceChange'] for x in state['Changes']]
        # An UPDATE limited to outputs, metadata and effective-equivalent parameters
        # can validly contain zero resource changes. IMPORT must still adopt exactly one stack.
        assert len(changes) in ([1] if phase == 'import' else [0, 1])
        item = changes[0] if changes else None
        if item:
            assert item['LogicalResourceId'] == 'Administration'
            assert item['ResourceType'] == 'AWS::CloudFormation::Stack'
            assert item['Action'] == ('Import' if phase == 'import' else 'Modify')
            assert item.get('Replacement', 'False') == 'False'
        nested = []
        if item and item.get('ChangeSetId'):
            nested = cf.describe_change_set(ChangeSetName=item['ChangeSetId']).get('Changes', [])
            assert not nested, 'Nested resource changes are not allowed in this adoption'
        report = {'change_set': plan['Id'], 'phase': phase, 'child_stack_id': child['StackId'],
                  'child_template_sha256': digest, 'template_url': url, 'changes': changes,
                  'nested_changes': nested, 'parameters': parameters, 'status': 'prepared_not_executed'}
        record.write_text(json.dumps(report, default=str, indent=2) + '\n')
        print(json.dumps(report, default=str, indent=2), flush=True)
        return

    report = json.loads(record.read_text())
    assert report['child_stack_id'] == child['StackId']
    state = cf.describe_change_set(ChangeSetName=report['change_set'])
    assert state['Status'] == 'CREATE_COMPLETE' and state['ExecutionStatus'] == 'AVAILABLE'
    assert [x['ResourceChange'] for x in state['Changes']] == report['changes']
    cf.execute_change_set(ChangeSetName=report['change_set'])
    expected = 'IMPORT_COMPLETE' if phase == 'import' else 'UPDATE_COMPLETE'
    deadline = time.monotonic() + 1200
    while True:
        parent = cf.describe_stacks(StackName=PARENT)['Stacks'][0]
        status = parent['StackStatus']
        if status == expected:
            break
        if status.endswith(('FAILED', 'ROLLBACK_COMPLETE')):
            raise RuntimeError('Stop; inspect CloudFormation events: ' + status)
        if time.monotonic() > deadline:
            raise TimeoutError('Stop; inspect stack before starting another operation')
        time.sleep(5)
    after = cf.describe_stacks(StackName=CHILD)['Stacks'][0]
    assert after['StackId'] == report['child_stack_id'] and after['ParentId'] == parent['StackId']
    report.update({'status': status, 'parent_stack_id': parent['StackId'], 'verified_parent_id': after['ParentId']})
    record.write_text(json.dumps(report, default=str, indent=2) + '\n')
    print(json.dumps({'parent': PARENT, 'child': CHILD, 'status': status, 'child_id_preserved': True}, indent=2))


if __name__ == '__main__':
    main()
