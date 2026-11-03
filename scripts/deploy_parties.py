"""Selective DEV change sets: current API owner, then Finance -> Administration."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import boto3
import yaml
from deploy_administration import assemble

ROOT = Path(__file__).resolve().parents[1]
API_OWNER = 'mastererp-dev-onboarding'
FINANCE = 'mastererp-dev-finance'
CHILD = 'mastererp-dev-administration'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--phase', choices=['prepare-api','execute-api','prepare-finance','execute-finance'], required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--artifacts', type=Path)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    s = boto3.Session(profile_name='mastererp-admin', region_name='us-west-1')
    assert s.client('sts').get_caller_identity()['Account'] == '277352717693'
    c, api, lam, store = (s.client(x) for x in ('cloudformation','apigatewayv2','lambda','s3'))
    assert api.get_api(ApiId='qx8nmypdhi')['Name'] == 'mastererp-dev-admin-api'
    assert c.describe_stack_resource(StackName=API_OWNER, LogicalResourceId='AdminHttpApi')['StackResourceDetail']['PhysicalResourceId'] == 'qx8nmypdhi'
    is_api = args.phase.endswith('api')
    stack = API_OWNER if is_api else FINANCE
    record = args.output/('api-plan.json' if is_api else 'finance-plan.json')

    def template(name):
        value = c.get_template(StackName=name, TemplateStage='Original')['TemplateBody']
        return yaml.safe_load(value) if isinstance(value, str) else value

    def review(plan, allowed, additions):
        changes = [x['ResourceChange'] for x in plan.get('Changes', [])]
        for x in changes:
            assert x['LogicalResourceId'] in allowed, 'Unrelated resource: '+x['LogicalResourceId']
            assert x['Action'] in ('Add','Modify'), 'Deletion forbidden'
            assert x.get('Replacement','False') == 'False', 'Replacement forbidden'
            if x['Action'] == 'Add': assert x['LogicalResourceId'] in additions
        return [{k:x.get(k) for k in ('Action','LogicalResourceId','Replacement')} for x in changes]

    if args.phase.startswith('prepare'):
        state = c.describe_stacks(StackName=stack)['Stacks'][0]
        assert state['StackStatus'] == 'UPDATE_COMPLETE'
        old = template(stack)
        app = lam.get_function_configuration(FunctionName='mastererp-dev-uonify-google-connection-handler')
        env = app['Environment']['Variables']
        previous = {x['ParameterKey']:x['ParameterValue'] for x in state['Parameters']}
        values = dict(previous)
        if is_api:
            candidate = yaml.safe_load((ROOT/'modules/1.0-platform-base/1.1-tenant-onboarding/resources.yml').read_text(encoding='utf-8'))
            changed = {k for k in old['Resources'] if old['Resources'][k] != candidate['Resources'].get(k)}
            added = set(candidate['Resources'])-set(old['Resources'])
            assert changed == {'AdminHttpApi'} and added == {'AdminCognitoJwtAuthorizer'}
            assert set(old['Resources']) <= set(candidate['Resources'])
            a = old['Resources']['AdminHttpApi']['Properties']['CorsConfiguration']
            b = candidate['Resources']['AdminHttpApi']['Properties']['CorsConfiguration']
            for key in ('AllowOrigins','AllowHeaders','AllowMethods'):
                assert all(x in b[key] for x in a[key]), 'CORS contraction'
            values.update(AdminJwtIssuer=env['COGNITO_ISSUER'], AdminJwtAudience=env['COGNITO_APP_CLIENT_ID'])
            allowed = {'AdminHttpApi','AdminCognitoJwtAuthorizer'}
        else:
            assert args.artifacts
            child = c.describe_stacks(StackName=CHILD)['Stacks'][0]
            assert child['ParentId'] == state['StackId']
            owners, assembled = assemble()
            actual = template(CHILD)
            mutable = {cap.title()+suffix for cap in ('clientes','proveedores') for suffix in ('Function','Role','Integration')}
            changed = {k for k in actual['Resources'] if actual['Resources'][k] != assembled['Resources'].get(k)}
            removed = set(actual['Resources'])-set(assembled['Resources'])
            lost_file = args.output/'api-reimport-loss.json'
            lost = json.loads(lost_file.read_text()) if lost_file.exists() else []
            assert removed == {x['LogicalResourceId'] for x in lost}
            live_integrations={x['IntegrationId'] for x in api.get_integrations(ApiId='qx8nmypdhi')['Items']}
            live_routes={x['RouteId'] for x in api.get_routes(ApiId='qx8nmypdhi')['Items']}
            assert all(x['PhysicalResourceId'] not in (live_integrations if x['ResourceType'].endswith('Integration') else live_routes) for x in lost)
            assert changed <= mutable | removed
            additions = set(assembled['Resources'])-set(actual['Resources'])
            assert len(additions) == 16+len(removed) and all(assembled['Resources'][x]['Type'] in ('AWS::ApiGatewayV2::Route','AWS::Lambda::Permission','AWS::ApiGatewayV2::Integration') for x in additions)
            bucket = previous['ArtifactBucket']
            assert store.get_bucket_location(Bucket=bucket)['LocationConstraint'] == 'us-west-1'
            assert all(store.get_public_access_block(Bucket=bucket)['PublicAccessBlockConfiguration'].values())
            for cap in ('clientes','proveedores'):
                blob = (args.artifacts/('mastererp-dev-adm-'+cap+'.zip')).read_bytes()
                key = 'mastererp/dev/administration/parties/'+cap+'/'+hashlib.sha256(blob).hexdigest()+'.zip'
                store.put_object(Bucket=bucket,Key=key,Body=blob,ContentType='application/zip',ServerSideEncryption='AES256')
                values[cap.title()+'ArtifactKey'] = key
            blob = json.dumps(assembled,sort_keys=True,separators=(',',':')).encode()
            key = 'mastererp/dev/finance/templates/'+hashlib.sha256(blob).hexdigest()+'.json'
            store.put_object(Bucket=bucket,Key=key,Body=blob,ContentType='application/json',ServerSideEncryption='AES256')
            values['AdministrationTemplateUrl'] = 'https://'+bucket+'.s3.us-west-1.amazonaws.com/'+key
            authorizers = c.describe_stacks(StackName=API_OWNER)['Stacks'][0]['Outputs']
            values.update(PartyDatabaseHost=env['DATABASE_HOST'],PartyDatabaseSecretArn=env['DATABASE_SECRET_ARN'],
                          PartySubnetIds=','.join(app['VpcConfig']['SubnetIds']),PartySecurityGroupIds=','.join(app['VpcConfig']['SecurityGroupIds']),
                          PartyCognitoIssuer=env['COGNITO_ISSUER'],PartyClientId=env['COGNITO_APP_CLIENT_ID'],
                          AdminJwtAuthorizerId=next(x['OutputValue'] for x in authorizers if x['OutputKey']=='AdminJwtAuthorizerId'))
            candidate = json.loads((ROOT/'modules/2.2-finance/resources.yml').read_text())
            allowed, added = {'Administration'}, set()
            (args.output/'assembled-child.json').write_text(json.dumps(assembled,indent=2))
            (args.output/'child-review.json').write_text(json.dumps({'changed':sorted(changed),'added':sorted(additions)},indent=2))
        (args.output/('api-before.json' if is_api else 'finance-before.json')).write_text(json.dumps(old,indent=2))
        name = 'parties-'+str(int(time.time()))
        parameters = [{'ParameterKey':k,'ParameterValue':values[k]} for k in candidate['Parameters']]
        c.create_change_set(StackName=stack,ChangeSetName=name,ChangeSetType='UPDATE',TemplateBody=json.dumps(candidate),
                           Parameters=parameters,Capabilities=['CAPABILITY_IAM','CAPABILITY_AUTO_EXPAND'],IncludeNestedStacks=not is_api)
        c.get_waiter('change_set_create_complete').wait(StackName=stack,ChangeSetName=name)
        plan = c.describe_change_set(StackName=stack,ChangeSetName=name)
        reviewed = review(plan,allowed,added)
        record.write_text(json.dumps({'stack':stack,'change_set':name,'review':reviewed,'allowed':sorted(allowed),'additions':sorted(added)},indent=2))
        print(json.dumps(reviewed))
    else:
        saved = json.loads(record.read_text())
        plan = c.describe_change_set(StackName=saved['stack'],ChangeSetName=saved['change_set'])
        assert plan['ExecutionStatus'] == 'AVAILABLE'
        review(plan,set(saved['allowed']),set(saved['additions']))
        # Nested plans must also preserve every existing resource and physical ID.
        for entry in plan.get('Changes',[]):
            x = entry['ResourceChange']
            if x.get('ChangeSetId'):
                child_plan=c.describe_change_set(ChangeSetName=x['ChangeSetId'])
                changes=[y['ResourceChange'] for y in child_plan.get('Changes',[])]
                lost_file=args.output/'api-reimport-loss.json'
                lost=json.loads(lost_file.read_text()) if lost_file.exists() else []
                missing={x['LogicalResourceId']:x['PhysicalResourceId'] for x in lost}
                live_integrations={x['IntegrationId'] for x in api.get_integrations(ApiId='qx8nmypdhi')['Items']}
                live_routes={x['RouteId'] for x in api.get_routes(ApiId='qx8nmypdhi')['Items']}
                for y in changes:
                    assert y.get('Replacement','False')=='False'
                    if y['Action']=='Remove':
                        assert y['LogicalResourceId'] in missing
                        assert missing[y['LogicalResourceId']] not in live_integrations | live_routes
                    else:assert y['Action'] in ('Add','Modify')
                (args.output/'nested-change-set.json').write_text(json.dumps(child_plan,default=str,indent=2))
        c.execute_change_set(StackName=saved['stack'],ChangeSetName=saved['change_set'])
        c.get_waiter('stack_update_complete').wait(StackName=saved['stack'])
        print(json.dumps({'stack':saved['stack'],'status':'UPDATE_COMPLETE'}))


if __name__ == '__main__':
    main()
