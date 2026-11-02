"""Update only the artifact parameter of the existing Uonify owner stack."""
import argparse,base64,hashlib,json,time
from pathlib import Path
import boto3
STACK='mastererp-dev-uonify-google-connection'
FUNCTION='mastererp-dev-uonify-google-connection-handler'
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifact',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--profile',default='mastererp-admin');p.add_argument('--execute',action='store_true');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    s=boto3.Session(profile_name=a.profile,region_name='us-west-1');assert s.client('sts').get_caller_identity()['Account']=='277352717693'
    c=s.client('cloudformation');l=s.client('lambda');api=s.client('apigatewayv2')
    stack=c.describe_stacks(StackName=STACK)['Stacks'][0];params={x['ParameterKey']:x['ParameterValue'] for x in stack['Parameters']}
    assert c.describe_stack_resource(StackName=STACK,LogicalResourceId='Function')['StackResourceDetail']['PhysicalResourceId']==FUNCTION
    bucket=params['ArtifactBucket'];raw=a.artifact.read_bytes();key='mastererp-dev-uonify/foundation/'+hashlib.sha256(raw).hexdigest()+'.zip'
    s3=s.client('s3');assert s3.get_bucket_location(Bucket=bucket)['LocationConstraint']=='us-west-1'
    before=l.get_function_configuration(FunctionName=FUNCTION)
    routes=api.get_routes(ApiId='ebn01q74hh')['Items'];integrations=api.get_integrations(ApiId='ebn01q74hh')['Items'];cors=api.get_api(ApiId='ebn01q74hh').get('CorsConfiguration')
    s3.put_object(Bucket=bucket,Key=key,Body=raw,ContentType='application/zip',ServerSideEncryption='AES256')
    values=[{'ParameterKey':k,'ParameterValue':key} if k=='ArtifactKey' else {'ParameterKey':k,'UsePreviousValue':True} for k in params]
    change='foundation-code-'+str(int(time.time()))
    c.create_change_set(StackName=STACK,ChangeSetName=change,ChangeSetType='UPDATE',UsePreviousTemplate=True,Parameters=values,Capabilities=['CAPABILITY_NAMED_IAM'])
    c.get_waiter('change_set_create_complete').wait(StackName=STACK,ChangeSetName=change)
    plan=c.describe_change_set(StackName=STACK,ChangeSetName=change)
    (a.output/'change-set.json').write_text(json.dumps(plan,default=str,indent=2),encoding='utf-8')
    changes=[x['ResourceChange'] for x in plan['Changes']]
    print(json.dumps([{'logical':x['LogicalResourceId'],'action':x['Action'],'replacement':x.get('Replacement')} for x in changes],indent=2))
    assert changes and all(x['Action']=='Modify' and x.get('Replacement','False')=='False' for x in changes)
    assert {x['LogicalResourceId'] for x in changes}.issubset({'Function','Integration','Route','SpacesRoute'})
    for item in changes:
        if item['LogicalResourceId']!='Function':
            assert all(x['Evaluation']=='Dynamic' and x['ChangeSource']=='ResourceAttribute' for x in item['Details'])
    if not a.execute: print('Prepared only: '+change);return
    c.execute_change_set(StackName=STACK,ChangeSetName=change);c.get_waiter('stack_update_complete').wait(StackName=STACK)
    after=l.get_function_configuration(FunctionName=FUNCTION)
    assert after['State']=='Active' and after['LastUpdateStatus']=='Successful'
    assert after['CodeSha256']==base64.b64encode(hashlib.sha256(raw).digest()).decode()
    for k in ('Role','VpcConfig','Environment','Runtime','MemorySize','Timeout'):assert before[k]==after[k],k
    assert api.get_routes(ApiId='ebn01q74hh')['Items']==routes
    assert api.get_integrations(ApiId='ebn01q74hh')['Items']==integrations
    assert api.get_api(ApiId='ebn01q74hh').get('CorsConfiguration')==cors
    print('Uonify code updated; configuration, routes, scopes, integration and CORS preserved.')
if __name__=='__main__':main()
