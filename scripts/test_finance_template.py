import copy,json,unittest
from pathlib import Path
from finance_template import backend_template

class FinanceProjectionTests(unittest.TestCase):
    def source(self):return json.loads((Path(__file__).resolve().parents[1]/'modules/2.2-finance/resources.yml').read_text())
    def test_current_owner_excludes_hosting_and_its_parameters(self):
        source=self.source();actual=backend_template(source)
        self.assertEqual(set(actual['Resources']),{'Administration'})
        self.assertIn('Environment',actual['Parameters'])
        self.assertFalse(any(k.startswith('Frontend') for k in actual['Parameters']))
        self.assertEqual(actual['Resources']['Administration'],source['Resources']['Administration'])
        self.assertNotIn('FrontendUrl',actual['Outputs'])
    def test_projection_does_not_mutate_shared_source(self):
        source=self.source();old=copy.deepcopy(source);backend_template(source);self.assertEqual(source,old)
    def test_unknown_backend_resource_requires_review(self):
        source=self.source();source['Resources']['Unexpected']={'Type':'AWS::S3::Bucket'}
        with self.assertRaises(ValueError):backend_template(source)
    def test_backend_condition_and_sub_parameters_are_retained(self):
        source=self.source();source['Parameters']['BackendSwitch']={'Type':'String'}
        source.setdefault('Conditions',{})['BackendEnabled']={'Fn::Equals':[{'Ref':'BackendSwitch'},'yes']}
        source['Resources']['Administration']['Condition']='BackendEnabled'
        source['Resources']['Administration']['Properties']['TemplateURL']={'Fn::Sub':'https://${ArtifactBucket}/template.json'}
        actual=backend_template(source);self.assertIn('BackendSwitch',actual['Parameters']);self.assertIn('BackendEnabled',actual['Conditions']);self.assertIn('ArtifactBucket',actual['Parameters'])
    def test_missing_ownership_manifest_fails_closed(self):
        source=self.source();source.pop('Metadata')
        with self.assertRaises(ValueError):backend_template(source)

if __name__=='__main__':unittest.main()
