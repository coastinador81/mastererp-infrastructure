"""Local guards: reject bulk API writers and preserve identity during adoption."""
import copy
import unittest
from admin_api_model import guard, fingerprint, transition


def fixture():
    events={}
    routes=[]
    integrations=[]
    for n in range(12):
        events['Event'+str(n)]={'Type':'HttpApi','Properties':{'Method':'GET','Path':'/v1/test/'+str(n)}}
        routes.append({'RouteId':'r'+str(n),'RouteKey':'GET /v1/test/'+str(n),
                       'Target':'integrations/i'+str(n),'AuthorizationType':'NONE'})
        integrations.append({'IntegrationId':'i'+str(n),'IntegrationType':'AWS_PROXY','IntegrationMethod':'POST',
                             'IntegrationUri':'arn:aws:apigateway:us-west-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-west-1:277352717693:function:mastererp-dev-test/invocations',
                             'PayloadFormatVersion':'2.0','TimeoutInMillis':30000,'ConnectionType':'INTERNET'})
    sam={'Transform':'AWS::Serverless-2016-10-31','Resources':{
        'TestFunction':{'Type':'AWS::Serverless::Function','Properties':{'Events':events}},
        'AdminHttpApi':{'Type':'AWS::Serverless::HttpApi','Properties':{'Description':'Prueba'}}}}
    processed={'Resources':{
        'TestFunction':{'Type':'AWS::Lambda::Function','Properties':{'FunctionName':{'Fn::Sub':'mastererp-${Environment}-test'},'Code':{'S3Key':'unchanged'}}},
        'AdminHttpApi':{'Type':'AWS::ApiGatewayV2::Api','Properties':{'Body':{'openapi':'3.0.1'}}}}}
    inventory={'api':{'ApiId':'api','ApiEndpoint':'https://unit.invalid','ProtocolType':'HTTP',
                      'CorsConfiguration':{'AllowOrigins':['https://unit.invalid']}},
               'routes':routes,'integrations':integrations,'authorizers':[],
               'stages':[{'StageName':'$default','AutoDeploy':True,'DeploymentId':'old','LastDeploymentStatusMessage':'Successfully deployed old'}]}
    return sam,processed,inventory


class ModelTests(unittest.TestCase):
    def test_guard_rejects_each_bulk_or_implicit_writer(self):
        for prop in ('Body','BodyS3Location','Target','RouteKey'):
            with self.subTest(prop=prop),self.assertRaises(AssertionError):
                guard({'Resources':{'AdminHttpApi':{'Type':'AWS::ApiGatewayV2::Api','Properties':{prop:{}}}}})
        with self.assertRaises(AssertionError):guard({'Transform':'SAM','Resources':{}})
        with self.assertRaises(AssertionError):guard({'Resources':{'Function':{'Type':'AWS::Serverless::Function'}}})


    def test_foreign_api_binding_and_macros_are_rejected(self):
        with self.assertRaises(AssertionError):
            guard({'Resources':{'ForeignRoute':{'Type':'AWS::ApiGatewayV2::Route','Properties':{'ApiId':'other-api','RouteKey':'GET /'}}}})
        with self.assertRaises(AssertionError):
            guard({'Resources':{'AdminHttpApi':{'Type':'AWS::ApiGatewayV2::Api','Properties':{'Description':{'Fn::Transform':{'Name':'Include'}}}}}})

    def test_adoption_does_not_rewrite_existing_sam_or_runtime(self):
        sam,processed,live=fixture()
        imported,native,imports,mapping=transition(sam,processed,live,[])
        self.assertEqual(len(imports),24)
        self.assertEqual(len(mapping),24)
        for name,value in sam['Resources'].items():self.assertEqual(imported['Resources'][name],value)
        self.assertEqual(native['Resources']['TestFunction'],processed['Resources']['TestFunction'])
        guard(native)
        self.assertNotIn('ProtocolType',native['Resources']['AdminHttpApi']['Properties'])

    def test_foreign_owned_resource_cannot_be_imported(self):
        sam,processed,live=fixture()
        with self.assertRaises(AssertionError):
            transition(sam,processed,live,[{'ResourceType':'AWS::ApiGatewayV2::Route','PhysicalResourceId':'r0'}])

    def test_fingerprint_detects_identity_auth_target_or_cors_changes(self):
        _,_,live=fixture()
        for field,value in [('RouteId','different'),('AuthorizationType','JWT'),('Target','integrations/wrong')]:
            changed=copy.deepcopy(live);changed['routes'][0][field]=value
            self.assertNotEqual(fingerprint(live),fingerprint(changed))
        changed=copy.deepcopy(live);changed['api']['CorsConfiguration']['AllowOrigins']=[]
        self.assertNotEqual(fingerprint(live),fingerprint(changed))
        changed=copy.deepcopy(live);changed['integrations'][0]['IntegrationUri']='wrong'
        self.assertNotEqual(fingerprint(live),fingerprint(changed))

    def test_fingerprint_ignores_only_nonfunctional_description_and_deployment_ids(self):
        _,_,live=fixture();changed=copy.deepcopy(live)
        changed['api']['Description']='metadata probe';changed['stages'][0]['DeploymentId']='new';changed['stages'][0]['LastDeploymentStatusMessage']='Successfully deployed new'
        self.assertEqual(fingerprint(live),fingerprint(changed))


if __name__=='__main__':unittest.main()
