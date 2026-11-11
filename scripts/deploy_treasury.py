"""Selective DEV Treasury artifact and JWT routes deployment."""
import argparse,base64,copy,hashlib,json,time
from pathlib import Path
import boto3
from deploy_administration import assemble

PARENT,CHILD,API="mastererp-dev-finance","mastererp-dev-administration","qx8nmypdhi"
FUNCTION="mastererp-dev-adm-tesoreria"
ALLOWED={"TesoreriaRole","TesoreriaFunction","TesoreriaIntegrationRecovered","TesoreriaReceiptsApiPermission","PendingReceiptsRoute","ReviewReceiptRoute"}
ADDITIONS={"TesoreriaReceiptsApiPermission","PendingReceiptsRoute","ReviewReceiptRoute"}

def main():
 p=argparse.ArgumentParser();p.add_argument('--artifact',type=Path);p.add_argument('--source-commit');p.add_argument('--plan',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--profile',default='andrea_madriz_mastererp');a=p.parse_args()
 s=boto3.Session(profile_name=a.profile,region_name='us-west-1');assert s.client('sts').get_caller_identity()['Account']=='277352717693'
 cf,api,lam,store=(s.client(x) for x in ('cloudformation','apigatewayv2','lambda','s3'))
 def resources(stack):return {r['LogicalResourceId']:r['PhysicalResourceId'] for page in cf.get_paginator('list_stack_resources').paginate(StackName=stack) for r in page['StackResourceSummaries']}
 def routes():return {r['RouteKey']:r for page in api.get_paginator('get_routes').paginate(ApiId=API) for r in page['Items']}
 if not a.execute:
  assert a.artifact and a.source_commit and len(a.source_commit)==40
  parent=cf.describe_stacks(StackName=PARENT)['Stacks'][0];child=cf.describe_stacks(StackName=CHILD)['Stacks'][0];assert child['ParentId']==parent['StackId']
  old=cf.get_template(StackName=CHILD,TemplateStage='Original')['TemplateBody'];old=json.loads(old) if isinstance(old,str) else old
  _,desired=assemble();candidate=copy.deepcopy(old)
  assert ADDITIONS.isdisjoint(old['Resources'])
  for key in ADDITIONS|{'TesoreriaRole','TesoreriaFunction'}:candidate['Resources'][key]=desired['Resources'][key]
  before=routes();assert not any('/finance/receipts' in key for key in before)
  params={x['ParameterKey']:x['ParameterValue'] for x in parent['Parameters']};bucket=params['ArtifactBucket'];assert all(store.get_public_access_block(Bucket=bucket)['PublicAccessBlockConfiguration'].values())
  digest=hashlib.sha256(a.artifact.read_bytes()).hexdigest();artifact_key=f'mastererp/dev/administration/treasury/{a.source_commit}/{digest}.zip';store.upload_file(str(a.artifact),bucket,artifact_key)
  body=json.dumps(candidate,sort_keys=True,separators=(',',':')).encode();template_key='mastererp/dev/finance/templates/'+hashlib.sha256(body).hexdigest()+'.json';store.put_object(Bucket=bucket,Key=template_key,Body=body,ContentType='application/json',ServerSideEncryption='AES256')
  changes={'TesoreriaArtifactKey':artifact_key,'AdministrationTemplateUrl':f'https://{bucket}.s3.us-west-1.amazonaws.com/{template_key}'}
  response=cf.create_change_set(StackName=PARENT,ChangeSetName='treasury-review-'+str(int(time.time())),ChangeSetType='UPDATE',UsePreviousTemplate=True,IncludeNestedStacks=True,Capabilities=['CAPABILITY_IAM','CAPABILITY_AUTO_EXPAND'],Parameters=[{'ParameterKey':k,**({'ParameterValue':changes[k]} if k in changes else {'UsePreviousValue':True})} for k in params])
  cf.get_waiter('change_set_create_complete').wait(ChangeSetName=response['Id'],WaiterConfig={'Delay':5,'MaxAttempts':80})
  plan={'change_set':response['Id'],'source_commit':a.source_commit,'sha256':digest,'parent':resources(PARENT),'child':resources(CHILD),'routes':before};a.plan.parent.mkdir(parents=True,exist_ok=True);a.plan.write_text(json.dumps(plan,indent=2)+'\n')
 else:
  plan=json.loads(a.plan.read_text());assert resources(PARENT)==plan['parent'] and resources(CHILD)==plan['child'] and routes()==plan['routes']
 root=cf.describe_change_set(ChangeSetName=plan['change_set']);assert root['ExecutionStatus']=='AVAILABLE';assert {x['ResourceChange']['LogicalResourceId'] for x in root['Changes']}=={'Administration'}
 nested=cf.describe_change_set(ChangeSetName=root['Changes'][0]['ResourceChange']['ChangeSetId'])['Changes'];summary=[]
 for item in nested:
  r=item['ResourceChange'];assert r['LogicalResourceId'] in ALLOWED and r['Action'] in ('Add','Modify') and r.get('Replacement','False')=='False';assert r['Action']!='Add' or r['LogicalResourceId'] in ADDITIONS;summary.append([r['LogicalResourceId'],r['Action']])
 print(json.dumps({'changes':summary,'source_commit':plan['source_commit'],'sha256':plan['sha256']}))
 if a.execute:
  cf.execute_change_set(ChangeSetName=plan['change_set']);cf.get_waiter('stack_update_complete').wait(StackName=PARENT,WaiterConfig={'Delay':5,'MaxAttempts':120})
  assert all(routes()[key]['AuthorizationType']=='JWT' for key in ('GET /v1/companies/{company_id}/finance/receipts/pending','POST /v1/companies/{company_id}/finance/receipts/{order_id}/review'))
  current=lam.get_function_configuration(FunctionName=FUNCTION);assert current['State']=='Active' and current['LastUpdateStatus']=='Successful' and current['CodeSha256']==base64.b64encode(bytes.fromhex(plan['sha256'])).decode();print('UPDATE_COMPLETE; Treasury identities preserved')
if __name__=='__main__':main()
