"""One resource-managed HTTP API model. No OpenAPI/quick-create writers allowed."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ('AdminHttpApi', 'AdminHttpApiApiGatewayDefaultStage', 'AdminCognitoJwtAuthorizer')


def fingerprint(inventory):
    """Stable identity and functional configuration, excluding request/deployment timestamps."""
    api = inventory['api']
    cors = {k: sorted(v) if isinstance(v,list) else v for k,v in api.get('CorsConfiguration',{}).items()}
    clean = {'api_id':api['ApiId'], 'endpoint':api['ApiEndpoint'], 'protocol':api['ProtocolType'],
             'cors':cors, 'disabled':api.get('DisableExecuteApiEndpoint',False),
             'routes':sorted(inventory['routes'],key=lambda x:x['RouteId']),
             'integrations':sorted(inventory['integrations'],key=lambda x:x['IntegrationId']),
             'authorizers':sorted(inventory['authorizers'],key=lambda x:x['AuthorizerId']),
             'stages':[{k:v for k,v in x.items() if k not in ('CreatedDate','LastUpdatedDate','DeploymentId','LastDeploymentStatus','LastDeploymentStatusMessage')}
                       for x in sorted(inventory['stages'],key=lambda x:x['StageName'])]}
    return hashlib.sha256(json.dumps(clean,sort_keys=True,default=str).encode()).hexdigest()


def guard(template):
    assert 'Transform' not in template, 'SAM/Transform is not allowed in the resource-managed owner'
    def no_macro(value):
        if isinstance(value,dict):
            assert 'Fn::Transform' not in value, 'Implicit macro expansion is forbidden'
            for child in value.values():no_macro(child)
        elif isinstance(value,list):
            for child in value:no_macro(child)
    no_macro(template['Resources'])
    for key, resource in template['Resources'].items():
        props = resource.get('Properties',{})
        assert not resource['Type'].startswith('AWS::Serverless::'), key
        if resource['Type'] == 'AWS::ApiGatewayV2::Api':
            assert key=='AdminHttpApi', 'Foreign API in owner composition'
            assert not set(props) & {'Body','BodyS3Location','Target','RouteKey'}, 'Bulk/quick-create API writer: '+key
        if resource['Type'] in ('AWS::ApiGatewayV2::Route','AWS::ApiGatewayV2::Integration','AWS::ApiGatewayV2::Stage','AWS::ApiGatewayV2::Authorizer'):
            assert props.get('ApiId')=={'Ref':'AdminHttpApi'}, 'Foreign API binding: '+key
        assert 'Events' not in props, 'Implicit event route generation: '+key


def assemble():
    owner = json.loads((ROOT/'modules/1.0-platform-base/1.1-tenant-onboarding/resources.yml').read_text(encoding='utf-8'))
    shared = json.loads((ROOT/'modules/api-gateways.yml').read_text(encoding='utf-8'))
    result = copy.deepcopy(owner)
    assert set(shared['Resources'])==set(SHARED), 'Unselected/legacy shared resources cannot be deployed'
    for name in SHARED:
        assert name not in result['Resources'], 'Duplicate shared declaration: '+name
        result['Resources'][name] = copy.deepcopy(shared['Resources'][name])
    guard(result)
    return result


def transition(original_sam, processed, inventory, child_resources):
    """Adopt implicit live routes by ID; retain every pre-existing CF declaration verbatim."""
    imported = copy.deepcopy(original_sam)
    native_base = copy.deepcopy(processed)
    routes = {r['RouteKey']:r for r in inventory['routes']}
    integrations = {i['IntegrationId']:i for i in inventory['integrations']}
    owned = {r['PhysicalResourceId'] for r in child_resources
             if r['ResourceType'] in ('AWS::ApiGatewayV2::Route','AWS::ApiGatewayV2::Integration')}
    imports = []
    mapping = []
    for logical, resource in original_sam['Resources'].items():
        for event, cfg in resource.get('Properties',{}).get('Events',{}).items():
            if cfg['Type'] != 'HttpApi': continue
            props = cfg['Properties']
            route = routes[props['Method'].upper()+' '+props['Path']]
            integration_id = route['Target'].split('/')[1]
            integration = integrations[integration_id]
            assert route['RouteId'] not in owned and integration_id not in owned
            prefix = logical+event
            ikey, rkey = prefix+'Integration', prefix+'Route'
            assert ikey not in imported['Resources'] and rkey not in imported['Resources']
            iprops = {k:v for k,v in integration.items() if k not in ('IntegrationId',)}
            iprops['ApiId'] = {'Ref':'AdminHttpApi'}
            iprops['IntegrationUri'] = {'Fn::Sub':'arn:${AWS::Partition}:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${'+logical+'.Arn}/invocations'}
            assert integration['IntegrationUri'].endswith('/'+logical_function_name(processed,logical)+'/invocations') or (
                ':function:'+logical_function_name(processed,logical)+'/invocations') in integration['IntegrationUri']
            rprops = {k:v for k,v in route.items() if k not in ('RouteId','Target','ApiKeyRequired') and v not in ({},[])}
            rprops.update(ApiId={'Ref':'AdminHttpApi'},Target={'Fn::Join':['/',['integrations',{'Ref':ikey}]]})
            for key, kind, value, physical in [(ikey,'Integration',iprops,integration_id),(rkey,'Route',rprops,route['RouteId'])]:
                imported['Resources'][key] = {'Type':'AWS::ApiGatewayV2::'+kind,'DeletionPolicy':'Retain',
                                              'UpdateReplacePolicy':'Retain','Properties':value}
                native_base['Resources'][key] = copy.deepcopy(imported['Resources'][key])
                imports.append({'ResourceType':'AWS::ApiGatewayV2::'+kind,'LogicalResourceId':key,
                                'ResourceIdentifier':{'ApiId':inventory['api']['ApiId'],kind+'Id':physical}})
                mapping.append({'logical':key,'type':kind,'physical':physical,'route':route['RouteKey']})
    assert len(imports)==24 and len({json.dumps(x['ResourceIdentifier'],sort_keys=True) for x in imports})==24
    native = native_base
    api = inventory['api']
    # ProtocolType was never a template property of the imported OpenAPI API.
    # Adding that create-only property would replace it. Pin/read-check HTTP in
    # the deployment guard; this adopted template is UPDATE-only, never CREATE.
    native['Resources']['AdminHttpApi']['Properties'] = {
        'Name':{'Fn::Sub':'mastererp-${Environment}-admin-api'},
        'Description':'MasterERP admin API - resource-managed routes', 'CorsConfiguration':copy.deepcopy(api['CorsConfiguration']),
        'DisableExecuteApiEndpoint':api.get('DisableExecuteApiEndpoint',False),
        'Version':api.get('Version','1.0'),
        'Tags':{k:v for k,v in api.get('Tags',{}).items() if not k.startswith('aws:')}}
    native['Resources']['AdminHttpApi']['Metadata'] = {'MasterERP':{'Management':'native-resources','ExistingProtocolType':'HTTP','CreateForbidden':True}}
    guard(native)
    return imported, native, imports, mapping


def logical_function_name(processed, logical):
    value=processed['Resources'][logical]['Properties']['FunctionName']
    if isinstance(value,str):return value
    assert set(value)=={'Fn::Sub'} and isinstance(value['Fn::Sub'],str)
    return value['Fn::Sub'].replace('${Environment}','dev')
