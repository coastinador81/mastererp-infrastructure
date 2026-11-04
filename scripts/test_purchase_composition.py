"""One shared purchase Lambda, native private routes, functional resource ownership."""
import json
from pathlib import Path
import unittest
from deploy_administration import assemble


class CompositionTest(unittest.TestCase):
    def test_purchase_routes_are_private_and_reuse_one_integration(self):
        _, template = assemble()
        routes = [r['Properties'] for r in template['Resources'].values()
                  if r['Type'] == 'AWS::ApiGatewayV2::Route' and '/compras/' in r['Properties']['RouteKey']]
        self.assertEqual(len(routes), 14)  # existing health, options, 3 x CRUD
        for route in routes:
            self.assertEqual(route['Target']['Fn::Join'][1][1], {'Ref': 'ComprasIntegrationRecovered'})
            if not route['RouteKey'].endswith('/health'):
                self.assertEqual(route['AuthorizationType'], 'JWT')
                self.assertEqual(route['AuthorizerId'], {'Ref': 'AdminJwtAuthorizerId'})
        self.assertEqual(sum(r['Type'] == 'AWS::Lambda::Function' for r in template['Resources'].values()), 8)

    def test_resources_are_declared_at_functional_roots(self):
        root = Path(__file__).resolve().parents[1] / 'modules/2.2-finance/2.2.1-administration/2.2.1.2-gestion-compras'
        parent = json.loads((root / 'resources.yml').read_text())
        self.assertIn('ComprasFunction', parent['Resources'])
        for relative in parent['Metadata']['MasterERP']['Composition']:
            child = json.loads((root / relative).read_text())
            self.assertEqual(len(child['Resources']), 8)
            self.assertFalse(any(r['Type'] == 'AWS::Lambda::Function' for r in child['Resources'].values()))


if __name__ == '__main__':
    unittest.main()
