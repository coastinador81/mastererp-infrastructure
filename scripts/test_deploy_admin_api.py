"""Review safety tests; never connect to AWS."""
import unittest
from deploy_admin_api import review


class ReviewTests(unittest.TestCase):
    def test_non_routing_mutations_are_rejected(self):
        resource={'Type':'AWS::Lambda::Function'}
        plan={'Changes':[{'ResourceChange':{'LogicalResourceId':'Function','ResourceType':resource['Type'],'Action':'Modify','Replacement':'False'}}]}
        with self.assertRaises(AssertionError):review(plan,{'Resources':{'Function':resource}},{'Resources':{'Function':resource}},False)

    def test_delete_and_replace_are_rejected(self):
        resource={'Type':'AWS::ApiGatewayV2::Route'}
        for action,replacement in [('Remove','False'),('Modify','True'),('Modify','Conditional')]:
            with self.subTest(action=action,replacement=replacement),self.assertRaises(AssertionError):
                review({'Changes':[{'ResourceChange':{'LogicalResourceId':'Route','ResourceType':resource['Type'],'Action':action,'Replacement':replacement}}]},
                       {'Resources':{'Route':resource}},{'Resources':{'Route':resource}},False)

    def test_additions_require_explicit_scope(self):
        resource={'Type':'AWS::ApiGatewayV2::Route'}
        plan={'Changes':[{'ResourceChange':{'LogicalResourceId':'Route','ResourceType':resource['Type'],'Action':'Add'}}]}
        with self.assertRaises(AssertionError):review(plan,{'Resources':{}},{'Resources':{'Route':resource}},False)
        self.assertEqual(len(review(plan,{'Resources':{}},{'Resources':{'Route':resource}},True)),1)


if __name__=='__main__':unittest.main()
