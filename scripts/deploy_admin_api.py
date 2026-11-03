"""Normal DEV API deployment: native assembly, reviewed UPDATE-only change sets."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import boto3
from botocore.exceptions import WaiterError
from admin_api_model import assemble, guard, fingerprint
from stabilize_admin_api import inventory, OWNER, API

ROUTING = {'AWS::ApiGatewayV2::Api','AWS::ApiGatewayV2::Stage','AWS::ApiGatewayV2::Authorizer',
           'AWS::ApiGatewayV2::Route','AWS::ApiGatewayV2::Integration'}


def review(plan, before, candidate, additions_allowed):
    changes=[x['ResourceChange'] for x in plan.get('Changes',[])]
    for x in changes:
        name=x['LogicalResourceId']
        assert x['ResourceType'] in ROUTING, 'Unrelated resource update: '+name
        assert x['Action'] in ('Add','Modify') and x.get('Replacement','False')=='False', 'Delete/replacement forbidden'
        if x['Action']=='Add':
            assert additions_allowed and x['ResourceType'] in {'AWS::ApiGatewayV2::Route','AWS::ApiGatewayV2::Integration'}
        assert candidate['Resources'][name]['Type'] in ROUTING
    assert set(before['Resources'])<=set(candidate['Resources']), 'Removal forbidden'
    return [{k:x.get(k) for k in ('Action','LogicalResourceId','ResourceType','Replacement')} for x in changes]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase',choices=['prepare','execute','verify'],required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--allow-routing-additions',action='store_true')
    args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    s=boto3.Session(profile_name='mastererp-admin',region_name='us-west-1')
    assert s.client('sts').get_caller_identity()['Account']=='277352717693'
    c,a,store=(s.client(x) for x in ('cloudformation','apigatewayv2','s3'))
    state=c.describe_stacks(StackName=OWNER)['Stacks'][0]
    assert state['StackStatus'] in ('UPDATE_COMPLETE','IMPORT_COMPLETE')
    assert next(x['ParameterValue'] for x in state['Parameters'] if x['ParameterKey']=='Environment')=='dev'
    live=inventory(a);assert live['api']['ApiId']==API and live['api']['ProtocolType']=='HTTP'
    value=c.get_template(StackName=OWNER,TemplateStage='Original')['TemplateBody']
    before=json.loads(value) if isinstance(value,str) else value
    guard(before);candidate=assemble()
    if args.phase=='prepare':
        old_keys={r['Properties']['RouteKey'] for r in before['Resources'].values() if r['Type']=='AWS::ApiGatewayV2::Route'}
        foreign_keys={r['RouteKey'] for r in live['routes']}-old_keys
        assert not foreign_keys & {r['Properties']['RouteKey'] for r in candidate['Resources'].values() if r['Type']=='AWS::ApiGatewayV2::Route'}, 'Foreign route collision'
        finance=c.describe_stacks(StackName='mastererp-dev-finance')['Stacks'][0]
        bucket=next(x['ParameterValue'] for x in finance['Parameters'] if x['ParameterKey']=='ArtifactBucket')
        assert store.get_bucket_location(Bucket=bucket)['LocationConstraint']=='us-west-1'
        assert all(store.get_public_access_block(Bucket=bucket)['PublicAccessBlockConfiguration'].values())
        blob=json.dumps(candidate,sort_keys=True,separators=(',',':')).encode()
        key='mastererp/dev/admin-api/native/'+hashlib.sha256(blob).hexdigest()+'.json'
        store.put_object(Bucket=bucket,Key=key,Body=blob,ContentType='application/json',ServerSideEncryption='AES256')
        name='admin-api-native-'+str(int(time.time()))
        (out/'baseline.json').write_text(json.dumps(live,default=str,indent=2),encoding='utf-8')
        c.create_change_set(StackName=OWNER,ChangeSetName=name,ChangeSetType='UPDATE',
            TemplateURL='https://'+bucket+'.s3.us-west-1.amazonaws.com/'+key,
            Parameters=[{'ParameterKey':x['ParameterKey'],'UsePreviousValue':True} for x in state['Parameters']],Capabilities=['CAPABILITY_IAM'])
        try:c.get_waiter('change_set_create_complete').wait(StackName=OWNER,ChangeSetName=name)
        except WaiterError:
            plan=c.describe_change_set(StackName=OWNER,ChangeSetName=name)
            if 'contain changes' in plan.get('StatusReason',''):
                record={'status':'NO_CHANGES','change_set':name,'fingerprint':fingerprint(live)}
                (out/'plan.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps(record));return
            raise
        plan=c.describe_change_set(StackName=OWNER,ChangeSetName=name)
        changes=review(plan,before,candidate,args.allow_routing_additions)
        (out/'candidate.json').write_text(json.dumps(candidate,indent=2),encoding='utf-8')
        (out/'plan.json').write_text(json.dumps({'status':'AVAILABLE','change_set':name,'changes':changes,
                                               'additions_allowed':args.allow_routing_additions},indent=2),encoding='utf-8')
        print(json.dumps(changes))
    elif args.phase=='execute':
        record=json.loads((out/'plan.json').read_text());assert record['status']=='AVAILABLE'
        plan=c.describe_change_set(StackName=OWNER,ChangeSetName=record['change_set'])
        assert plan['ExecutionStatus']=='AVAILABLE'
        candidate=json.loads((out/'candidate.json').read_text());guard(candidate)
        review(plan,before,candidate,record['additions_allowed'])
        baseline=json.loads((out/'baseline.json').read_text());assert fingerprint(baseline)==fingerprint(live),'API changed after review'
        c.execute_change_set(StackName=OWNER,ChangeSetName=record['change_set'])
        c.get_waiter('stack_update_complete').wait(StackName=OWNER)
        current=inventory(a)
        before_ids={k:{r[k+'Id'] for r in live[k.lower()+'s']} for k in ('Route','Integration','Authorizer')}
        after_ids={k:{r[k+'Id'] for r in current[k.lower()+'s']} for k in ('Route','Integration','Authorizer')}
        assert all(before_ids[k]<=after_ids[k] for k in before_ids), 'Existing identity lost'
        (out/'after.json').write_text(json.dumps(current,default=str,indent=2),encoding='utf-8')
        print('UPDATE_COMPLETE; original API identities preserved')
    else:
        baseline=json.loads((out/'baseline.json').read_text())
        assert fingerprint(live)==fingerprint(baseline)
        print(json.dumps({'status':'passed','routes':len(live['routes']),'integrations':len(live['integrations']),
                          'identity_fingerprint':fingerprint(live)}))


if __name__=='__main__':main()
