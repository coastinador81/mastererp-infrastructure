"""Prepare/review/execute a selective update of the current Onboarding owner stack.
Never creates a stack or changes API definitions or the five missing functions.
"""
import argparse,base64,hashlib,json,time
from pathlib import Path
import boto3,yaml
from admin_api_model import assemble, guard, fingerprint
from stabilize_admin_api import inventory
ROOT=Path(__file__).resolve().parents[1]
STACK='mastererp-dev-onboarding'
ALLOWED={'OnboardingSessionManagerFunction','OnboardingSessionManagerFunctionRole',
         'OnboardingProgressTrackerFunction','OnboardingProgressTrackerFunctionRole'}
FUNCTIONS={'OnboardingSessionManagerFunction':'mastererp-dev-onboarding-session-manager',
           'OnboardingProgressTrackerFunction':'mastererp-dev-onboarding-progress-tracker'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',default='mastererp-admin');parser.add_argument('--artifact',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    s=boto3.Session(profile_name=args.profile,region_name='us-west-1')
    assert s.client('sts').get_caller_identity()['Account']=='277352717693'
    c=s.client('cloudformation');l=s.client('lambda');a=s.client('apigatewayv2');s3=s.client('s3')
    stack=c.describe_stacks(StackName=STACK)['Stacks'][0]
    assert stack['StackStatus'] in ('CREATE_COMPLETE','UPDATE_COMPLETE','UPDATE_ROLLBACK_COMPLETE')
    original=c.get_template(StackName=STACK,TemplateStage='Original')['TemplateBody']
    original=yaml.safe_load(original) if isinstance(original,str) else original
    candidate=assemble()
    guard(original);guard(candidate)
    changed={k for k in original['Resources'] if original['Resources'][k]!=candidate['Resources'].get(k)}
    assert changed.issubset(FUNCTIONS) and set(original['Resources'])==set(candidate['Resources'])
    for k in original:
        if k not in ('Resources','Parameters','Metadata'): assert original[k]==candidate[k],k
    assert {k:v for k,v in original['Parameters'].items() if k not in ('ReviewedArtifactBucket','ReviewedArtifactKey')}=={k:v for k,v in candidate['Parameters'].items() if k not in ('ReviewedArtifactBucket','ReviewedArtifactKey')}
    for logical,name in FUNCTIONS.items():
        assert c.describe_stack_resource(StackName=STACK,LogicalResourceId=logical)['StackResourceDetail']['PhysicalResourceId']==name
        config=l.get_function_configuration(FunctionName=name)
        assert config['Runtime']=='python3.12' and config['Architectures']==['x86_64']
    api_id=c.describe_stack_resource(StackName=STACK,LogicalResourceId='AdminHttpApi')['StackResourceDetail']['PhysicalResourceId']
    assert api_id=='qx8nmypdhi' and a.get_api(ApiId=api_id)['Name']=='mastererp-dev-admin-api'
    baseline=inventory(a)
    (args.output/'original.json').write_text(json.dumps(original,indent=2))
    previous={x['ParameterKey']:x['ParameterValue'] for x in stack['Parameters']}
    bucket=previous.get('ReviewedArtifactBucket') or previous['OnboardingCodeUri'].removeprefix('s3://').split('/')[0]
    assert s3.get_bucket_location(Bucket=bucket)['LocationConstraint']=='us-west-1'
    raw=args.artifact.read_bytes();sha=hashlib.sha256(raw).hexdigest();key='mastererp-dev-onboarding/reviewed/'+sha+'.zip'
    s3.put_object(Bucket=bucket,Key=key,Body=raw,ContentType='application/zip',ServerSideEncryption='AES256')
    params=[{'ParameterKey':x['ParameterKey'],'UsePreviousValue':True} for x in stack['Parameters'] if x['ParameterKey'] not in ('ReviewedArtifactBucket','ReviewedArtifactKey')]
    params += [{'ParameterKey':'ReviewedArtifactBucket','ParameterValue':bucket},{'ParameterKey':'ReviewedArtifactKey','ParameterValue':key}]
    change='foundation-repair-'+str(int(time.time()))
    result=c.create_change_set(StackName=STACK,ChangeSetName=change,ChangeSetType='UPDATE',
        TemplateBody=json.dumps(candidate),Parameters=params,Capabilities=['CAPABILITY_IAM','CAPABILITY_AUTO_EXPAND'])
    c.get_waiter('change_set_create_complete').wait(StackName=STACK,ChangeSetName=change)
    plan=c.describe_change_set(StackName=STACK,ChangeSetName=change)
    (args.output/'change-set.json').write_text(json.dumps(plan,default=str,indent=2))
    changes=[x['ResourceChange'] for x in plan['Changes']]
    print(json.dumps([{'action':x['Action'],'logical':x['LogicalResourceId'],'replacement':x.get('Replacement')} for x in changes],indent=2))
    # Native API resources cannot regenerate routes on a function-code update.
    # Existing integration URI references may be predicted dynamically, but their
    # declarations and all API properties must remain identical.
    before=c.get_template(StackName=STACK,TemplateStage='Processed')['TemplateBody']
    after=c.get_template(StackName=STACK,ChangeSetName=change,TemplateStage='Processed')['TemplateBody']
    before=yaml.safe_load(before) if isinstance(before,str) else before
    after=yaml.safe_load(after) if isinstance(after,str) else after
    assert before['Resources']['AdminHttpApi']==after['Resources']['AdminHttpApi'],'API definition changed'
    for item in changes:
        assert item['Action']=='Modify' and item.get('Replacement','False')=='False','Unsafe replacement/add/delete'
        name=item['LogicalResourceId']
        if item['ResourceType']=='AWS::ApiGatewayV2::Integration':
            assert original['Resources'][name]==candidate['Resources'][name]
            assert item['Details'] and all(detail['Evaluation']=='Dynamic'
                and detail.get('CausingEntity') in {key+'.Arn' for key in FUNCTIONS}
                and detail['Target']['Name']=='IntegrationUri' for detail in item['Details'])
        else:
            assert name in ALLOWED,'Unexpected resource change'

    if not args.execute:
        print('Reviewed change set prepared, not executed: '+change);return
    c.execute_change_set(StackName=STACK,ChangeSetName=change)
    c.get_waiter('stack_update_complete').wait(StackName=STACK)
    assert fingerprint(inventory(a))==fingerprint(baseline), 'API graph/configuration changed'
    for name in FUNCTIONS.values():
        conf=l.get_function_configuration(FunctionName=name)
        assert conf['State']=='Active' and conf['LastUpdateStatus']=='Successful'
        assert conf['CodeSha256']==base64.b64encode(hashlib.sha256(raw).digest()).decode()
        assert set(conf['VpcConfig']['SubnetIds'])=={'subnet-03588dfad2cf9d1e1','subnet-06fc0b76f1e6167ad'}
        assert conf['VpcConfig']['SecurityGroupIds']==['sg-00d5917aa994d3753']
    print('Selective Onboarding repair complete; API routes/integrations/CORS preserved.')

if __name__=='__main__':main()
