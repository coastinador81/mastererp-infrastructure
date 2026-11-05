"""Review and update only DEV hosting publisher or Cognito callback URLs. No API imports."""
import argparse,copy,json,time
from pathlib import Path
import boto3,yaml
ROOT=Path(__file__).resolve().parents[1]
class Loader(yaml.SafeLoader):pass
def intrinsic(loader,tag,node):
    value=loader.construct_scalar(node) if isinstance(node,yaml.ScalarNode) else loader.construct_sequence(node) if isinstance(node,yaml.SequenceNode) else loader.construct_mapping(node)
    return {('Ref' if tag=='Ref' else 'Fn::'+tag):(value.split('.',1) if tag=='GetAtt' and isinstance(value,str) else value)}
Loader.add_multi_constructor('!',intrinsic)
def decode(value):return yaml.load(value,Loader=Loader) if isinstance(value,str) else value

def main():
    p=argparse.ArgumentParser();p.add_argument('domain',choices=['identity','hosting']);p.add_argument('action',choices=['prepare','execute']);p.add_argument('--output',type=Path,required=True);p.add_argument('--profile',default='andrea_madriz_mastererp');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    stack='mastererp-dev-identity' if a.domain=='identity' else 'mastererp-dev-uonify-hosting'
    source='modules/1.0-platform-base/1.2-platform-management/1.2.1-identity-access/resources.yml' if a.domain=='identity' else 'modules/0-uonify/resources.yml'
    s=boto3.Session(profile_name=a.profile,region_name='us-west-1');assert s.client('sts').get_caller_identity()['Account']=='277352717693'
    c=s.client('cloudformation');plan_file=a.output/(a.domain+'-plan.json')
    state=c.describe_stacks(StackName=stack)['Stacks'][0]
    if a.action=='prepare':
        before=decode(c.get_template(StackName=stack,TemplateStage='Original')['TemplateBody']);candidate=decode((ROOT/source).read_text(encoding='utf-8'))
        assert before['Resources'].keys()<=candidate['Resources'].keys() and 'Transform' not in candidate
        for key,value in before['Resources'].items():
            if a.domain=='identity' and key=='WebClient':
                expected=copy.deepcopy(value)
                if 'https://finanzas-dev.uonify.com/auth/callback' not in expected['Properties']['CallbackURLs']:expected['Properties']['CallbackURLs'].append('https://finanzas-dev.uonify.com/auth/callback')
                if 'https://finanzas-dev.uonify.com/' not in expected['Properties']['LogoutURLs']:expected['Properties']['LogoutURLs'].append('https://finanzas-dev.uonify.com/')
                assert candidate['Resources'][key]==expected
            else:assert candidate['Resources'][key]==value,key
        changes='integrated-finance-'+str(int(time.time()))
        parameters=[{'ParameterKey':x['ParameterKey'],'UsePreviousValue':True} for x in state.get('Parameters',[])]
        c.create_change_set(StackName=stack,ChangeSetName=changes,ChangeSetType='UPDATE',TemplateBody=json.dumps(candidate),Parameters=parameters,Capabilities=['CAPABILITY_NAMED_IAM'])
        try:c.get_waiter('change_set_create_complete').wait(StackName=stack,ChangeSetName=changes,WaiterConfig={'Delay':3,'MaxAttempts':100})
        except Exception:
            status=c.describe_change_set(StackName=stack,ChangeSetName=changes)
            if "didn't contain changes" in status.get('StatusReason','') or 'No updates' in status.get('StatusReason',''):
                plan_file.write_text(json.dumps({'stack':stack,'noop':True}));print('NO_CHANGES: '+stack);return
            raise
        plan=c.describe_change_set(StackName=stack,ChangeSetName=changes)
        result=[x['ResourceChange'] for x in plan['Changes']]
        allowed={'WebClient','StorefrontClient'} if a.domain=='identity' else {'FrontendPublisherRole'}
        assert all(x['LogicalResourceId'] in allowed and x['Action'] in ('Add','Modify') and x.get('Replacement','False')=='False' for x in result)
        records=c.list_stack_resources(StackName=stack)['StackResourceSummaries']
        plan_file.write_text(json.dumps({'stack':stack,'change':changes,'changes':result,'ids':{x['LogicalResourceId']:x['PhysicalResourceId'] for x in records}},indent=2))
        print(plan_file.read_text())
    else:
        record=json.loads(plan_file.read_text());assert record['stack']==stack
        if record.get('noop'):print('NO_CHANGES: '+stack);return
        plan=c.describe_change_set(StackName=stack,ChangeSetName=record['change'])
        assert [x['ResourceChange'] for x in plan['Changes']]==record['changes']
        c.execute_change_set(StackName=stack,ChangeSetName=record['change'])
        c.get_waiter('stack_update_complete').wait(StackName=stack)
        ids={x['LogicalResourceId']:x['PhysicalResourceId'] for x in c.list_stack_resources(StackName=stack)['StackResourceSummaries']}
        assert all(ids[k]==v for k,v in record['ids'].items())
        print('Updated '+stack+'; all pre-existing physical IDs preserved')
if __name__=='__main__':main()
