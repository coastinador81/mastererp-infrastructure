import unittest
from phase7_templates import assemble


class Phase7TemplatesTest(unittest.TestCase):
    def test_domains_are_additive_and_authorized(self):
        expected = {"catalog": 6, "operations": 4, "transport": 1, "digital-sales": 1}
        for domain, functions in expected.items():
            stack, template = assemble(domain)
            self.assertEqual(stack, "mastererp-dev-" + domain)
            self.assertEqual(sum(item["Type"] == "AWS::Lambda::Function"
                                 for item in template["Resources"].values()), functions)

    def test_public_storefront_uses_client_api(self):
        _, template = assemble("digital-sales")
        route = template["Resources"]["PublicCatalogRoute"]["Properties"]
        self.assertEqual(route["ApiId"], {"Ref": "ExistingClientApiId"})
        self.assertEqual(route["AuthorizationType"], "NONE")


if __name__ == "__main__":
    unittest.main()
