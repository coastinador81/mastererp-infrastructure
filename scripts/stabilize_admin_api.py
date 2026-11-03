"""DEV-only adoption of implicit API resources; no bulk reimport, SQL or Lambda update."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import time
import boto3
import yaml
from botocore.exceptions import WaiterError
from admin_api_model import transition, fingerprint, guard, assemble, SHARED, ROOT

OWNER = 'mastererp-dev-onboarding'
CHILD = 'mastererp-dev-administration'
API = 'qx8nmypdhi'


def inventory(client):
    def items(method):
        return [r for p in client.get_paginator(method).paginate(ApiId=API) for r in p.get('Items',[])]
    return {'api':client.get_api(ApiId=API), 'routes':items('get_routes'), 'integrations':items('get_integrations'),
            'authorizers':items('get_authorizers'), 'stages':items('get_stages')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',required=True,choices=['prepare-import','execute-import','prepare-native','execute-native',
                                                       'prepare-repeat','execute-repeat','prepare-noop','verify'])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    s=boto3.Session(profile_name='mastererp-admin',region_name='us-west-1')
    assert s.client('sts').get_caller_identity()['Account']=='277352717693'
    c,a,store=(s.client(x) for x in ('cloudformation','apigatewayv2','s3'))
    assert a.get_api(ApiId=API)['Name']=='mastererp-dev-admin-api'
    assert a.get_api(ApiId=API)['ProtocolType']=='HTTP'
    assert c.describe_stack_resource(StackName=OWNER,LogicalResourceId='AdminHttpApi')['StackResourceDetail']['PhysicalResourceId']==API
    state=c.describe_stacks(StackName=OWNER)['Stacks'][0]
    assert next(x['ParameterValue'] for x in state['Parameters'] if x['ParameterKey']=='Environment')=='dev'

    def read_template(stage):
        value=c.get_template(StackName=OWNER,TemplateStage=stage)['TemplateBody']
        return yaml.safe_load(value) if isinstance(value,str) else value

    def save(name,value):
        (out/name).write_text(json.dumps(value,default=str,indent=2)+'\n',encoding='utf-8')

    def check_ids(checkpoint):
        before=json.loads((out/'baseline-inventory.json').read_text(encoding='utf-8'))
        current=inventory(a)
        assert fingerprint(before)==fingerprint(current),'API identity/configuration changed at '+checkpoint
        old=json.loads((out/'baseline-stack.json').read_text(encoding='utf-8'))
        current_resources={x['LogicalResourceId']:x for x in c.list_stack_resources(StackName=OWNER)['StackResourceSummaries']}
        assert all(current_resources[x['LogicalResourceId']]['PhysicalResourceId']==x['PhysicalResourceId'] for x in old['resources'])
        assert c.describe_stacks(StackName=OWNER)['Stacks'][0]['StackId']==old['stack']['StackId']
        save(checkpoint+'-inventory.json',current)
        report={'checkpoint':checkpoint,'fingerprint_schema':'resource-graph-v2','identity_fingerprint':fingerprint(current),'routes':len(current['routes']),
                'integrations':len(current['integrations']),'authorizers':len(current['authorizers']),
                'original_stack_resources_preserved':len(old['resources']),'status':'passed'}
        save(checkpoint+'-verification.json',report);print(json.dumps(report))

    def upload(template):
        finance=c.describe_stacks(StackName='mastererp-dev-finance')['Stacks'][0]
        bucket=next(x['ParameterValue'] for x in finance['Parameters'] if x['ParameterKey']=='ArtifactBucket')
        assert store.get_bucket_location(Bucket=bucket)['LocationConstraint']=='us-west-1'
        assert all(store.get_public_access_block(Bucket=bucket)['PublicAccessBlockConfiguration'].values())
        data=json.dumps(template,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        key='mastererp/dev/admin-api/native/'+hashlib.sha256(data).hexdigest()+'.json'
        store.put_object(Bucket=bucket,Key=key,Body=data,ContentType='application/json',ServerSideEncryption='AES256')
        return 'https://'+bucket+'.s3.us-west-1.amazonaws.com/'+key

    def review(plan,phase):
        changes=[x['ResourceChange'] for x in plan.get('Changes',[])]
        if phase=='import':
            expected={x['LogicalResourceId'] for x in json.loads((out/'resources-to-import.json').read_text())}
            assert len(changes)==24 and {x['LogicalResourceId'] for x in changes}==expected
            assert all(x['Action']=='Import' for x in changes)
        else:
            assert changes and all(x['Action']=='Modify' and x['LogicalResourceId']=='AdminHttpApi'
                                   and x.get('Replacement')=='False' for x in changes),'Unexpected change/replacement'
        return [{k:x.get(k) for k in ('Action','LogicalResourceId','ResourceType','Replacement')} for x in changes]

    if args.phase.startswith('prepare'):
        assert state['StackStatus'] in ('UPDATE_COMPLETE','IMPORT_COMPLETE')
        phase=args.phase.removeprefix('prepare-')
        if phase=='import':
            if (out/'baseline-inventory.json').exists():
                previous=json.loads((out/'baseline-stack.json').read_text(encoding='utf-8'))
                assert state['StackStatus']=='UPDATE_COMPLETE'
                assert read_template('Original')==previous['original'], 'Owner changed since baseline'
                check_ids('reprepare-import')
            live=inventory(a);original=read_template('Original');processed=read_template('Processed')
            child=c.list_stack_resources(StackName=CHILD)['StackResourceSummaries']
            candidate,native,resources,mapping=transition(original,processed,live,child)
            if not (out/'baseline-inventory.json').exists():
                save('baseline-inventory.json',live)
                save('baseline-stack.json',{'stack':state,'resources':c.list_stack_resources(StackName=OWNER)['StackResourceSummaries'],
                                            'original':original,'processed':processed})
            save('import-candidate.json',candidate);save('native-candidate.json',native)
            save('resources-to-import.json',resources);save('resource-map.json',mapping)
        else:
            check_ids('before-'+phase)
            candidate=assemble()
            if phase=='native':
                expected=json.loads((out/'native-candidate.json').read_text(encoding='utf-8'))
                assert candidate['Resources']==expected['Resources'], 'Native source differs from reviewed transition'
            guard(candidate)
            if phase=='repeat':
                # Actual UpdateApi operation, but no functional setting changes.
                candidate['Resources']['AdminHttpApi']['Properties']['Description']+=' Resource ownership verified.'
                save('repeat-candidate.json',candidate)
            if phase=='noop':
                assert candidate==read_template('Original'),'Source differs from deployed template'
        name='admin-native-'+phase+'-'+str(int(time.time()))
        request={'StackName':OWNER,'ChangeSetName':name,'ChangeSetType':'IMPORT' if phase=='import' else 'UPDATE',
                 'TemplateURL':upload(candidate),'Parameters':[{'ParameterKey':x['ParameterKey'],'UsePreviousValue':True} for x in state['Parameters']],
                 'Capabilities':['CAPABILITY_IAM','CAPABILITY_AUTO_EXPAND']}
        if phase=='import':request['ResourcesToImport']=resources
        c.create_change_set(**request)
        try:c.get_waiter('change_set_create_complete').wait(StackName=OWNER,ChangeSetName=name)
        except WaiterError:
            plan=c.describe_change_set(StackName=OWNER,ChangeSetName=name)
            if phase=='noop' and 'contain changes' in plan.get('StatusReason',''):
                save('noop-plan.json',{'change_set':name,'status':'NO_CHANGES','reason':plan['StatusReason']})
                check_ids('after-noop');return
            save(phase+'-rejected-plan.json',plan);raise
        plan=c.describe_change_set(StackName=OWNER,ChangeSetName=name)
        changes=review(plan,phase)
        save(phase+'-plan.json',{'change_set':name,'changes':changes,'template':request['TemplateURL']})
        print(json.dumps(changes,indent=2))
    elif args.phase.startswith('execute'):
        phase=args.phase.removeprefix('execute-')
        record=json.loads((out/(phase+'-plan.json')).read_text())
        plan=c.describe_change_set(StackName=OWNER,ChangeSetName=record['change_set'])
        assert plan['ExecutionStatus']=='AVAILABLE'
        review(plan,phase);check_ids('immediately-before-'+phase)
        execute={'StackName':OWNER,'ChangeSetName':record['change_set']}
        if phase=='native':execute['DisableRollback']=True  # Never roll back to destructive Body reimport.
        c.execute_change_set(**execute)
        waiter='stack_import_complete' if phase=='import' else 'stack_update_complete'
        c.get_waiter(waiter).wait(StackName=OWNER)
        check_ids('after-'+phase)
    else:
        guard(read_template('Original'));check_ids('final')


if __name__=='__main__':
    main()
