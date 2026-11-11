"""DEV: change only OrdersArtifactKey on its existing native CloudFormation owner."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import struct
import zipfile
import boto3


STACK = "mastererp-dev-operations"
FUNCTION = "mastererp-dev-orders"
ACCOUNT = "277352717693"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--add-notes-route", action="store_true")
    parser.add_argument("--add-bulk-route", action="store_true")
    parser.add_argument("--profile", default="andrea_madriz_mastererp")
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile, region_name="us-west-1")
    assert session.client("sts").get_caller_identity()["Account"] == ACCOUNT
    cfn, s3, lam, api = (session.client(name) for name in ("cloudformation", "s3", "lambda", "apigatewayv2"))

    def resources():
        rows = [r for page in cfn.get_paginator("list_stack_resources").paginate(StackName=STACK)
                for r in page["StackResourceSummaries"]]
        return {r["LogicalResourceId"]: r["PhysicalResourceId"] for r in rows}

    def config():
        c = lam.get_function_configuration(FunctionName=FUNCTION)
        return {key: c.get(key) for key in ("Role", "Runtime", "Handler", "MemorySize", "Timeout", "VpcConfig", "Environment", "Architectures")}

    def api_state(api_id, integration_id):
        integration = api.get_integration(ApiId=api_id, IntegrationId=integration_id)
        integration.pop("ResponseMetadata", None)
        routes = [r for page in api.get_paginator("get_routes").paginate(ApiId=api_id) for r in page["Items"]]
        return {"integration": integration, "routes": sorted(routes, key=lambda r: r["RouteId"]),
                "cors": api.get_api(ApiId=api_id).get("CorsConfiguration")}

    def assert_api_after(plan):
        current = api_state(plan["api_id"], plan["physical_ids_before"]["OrdersIntegration"])
        assert current["integration"] == plan["api_before"]["integration"]
        assert current["cors"] == plan["api_before"]["cors"]
        before = {route["RouteKey"]: route for route in plan["api_before"]["routes"]}
        after = {route["RouteKey"]: route for route in current["routes"]}
        assert all(after.get(key) == value for key, value in before.items())
        expected = set()
        if plan.get("add_notes_route"):
            expected.add("POST /v1/companies/{company_id}/orders/{order_id}/notes")
        if plan.get("add_bulk_route"):
            expected.add("POST /v1/companies/{company_id}/orders/bulk-transitions")
        added = set(after) - set(before)
        assert added == expected
        for key in added:
            route = after[key]
            assert route["AuthorizationType"] == "JWT" and route["AuthorizerId"]
            assert route["Target"] == "integrations/" + plan["physical_ids_before"]["OrdersIntegration"]

    if not args.execute:
        assert args.artifact and args.source_commit and len(args.source_commit) == 40
        stack = cfn.describe_stacks(StackName=STACK)["Stacks"][0]
        params = {p["ParameterKey"]: p["ParameterValue"] for p in stack["Parameters"]}
        before = resources()
        assert before["OrdersFunction"] == FUNCTION
        assert config()["Architectures"] == ["arm64"]
        with zipfile.ZipFile(args.artifact) as archive:
            libs = [n for n in archive.namelist() if ".so" in n]
            assert libs and all(struct.unpack("<H", archive.read(n)[18:20])[0] == 183 for n in libs), "Linux ARM64 binaries required"
        digest = hashlib.sha256(args.artifact.read_bytes()).hexdigest()
        key = f"mastererp/dev/orders-sales/{args.source_commit}/{digest}.zip"
        s3.upload_file(str(args.artifact), params["ArtifactBucket"], key)
        name = "orders-sales-" + str(int(time.time()))
        change_args = {}
        if args.add_notes_route or args.add_bulk_route:
            template = cfn.get_template(StackName=STACK, TemplateStage="Original")["TemplateBody"]
            source = json.loads((Path(__file__).resolve().parents[1] /
                "modules/2.3-ecommerce/2.3.1-orders/resources.yml").read_text())
            additions = (["OrdersNotesRoute"] if args.add_notes_route else []) + (["OrdersBulkTransitionRoute"] if args.add_bulk_route else [])
            for logical_id in additions:
                assert logical_id not in template["Resources"]
                template["Resources"][logical_id] = source["Resources"][logical_id]
            change_args["TemplateBody"] = json.dumps(template)
        else:
            change_args["UsePreviousTemplate"] = True
        change = cfn.create_change_set(StackName=STACK, ChangeSetName=name,
            ChangeSetType="UPDATE", Capabilities=["CAPABILITY_NAMED_IAM"], **change_args,
            Parameters=[{"ParameterKey": k, **({"ParameterValue": key} if k == "OrdersArtifactKey"
                         else {"UsePreviousValue": True})} for k in params])
        cfn.get_waiter("change_set_create_complete").wait(ChangeSetName=change["Id"], WaiterConfig={"Delay": 3, "MaxAttempts": 40})
        plan = {"stack": STACK, "stack_id": stack["StackId"], "change_set": change["Id"],
                "artifact_sha256": digest, "source_commit": args.source_commit, "artifact_key": key,
                "old_artifact_key": params["OrdersArtifactKey"], "physical_ids_before": before,
                "api_id": params["ExistingAdminApiId"],
                "api_before": api_state(params["ExistingAdminApiId"], before["OrdersIntegration"]),
                "add_notes_route": args.add_notes_route,
                "add_bulk_route": args.add_bulk_route,
                "configuration_sha256": hashlib.sha256(json.dumps(config(), sort_keys=True).encode()).hexdigest()}
        args.plan.parent.mkdir(parents=True, exist_ok=True)
        args.plan.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    else:
        plan = json.loads(args.plan.read_text())
        assert plan["stack"] == STACK
        assert cfn.describe_stacks(StackName=STACK)["Stacks"][0]["StackId"] == plan["stack_id"]
        assert resources() == plan["physical_ids_before"]
        assert hashlib.sha256(json.dumps(config(), sort_keys=True).encode()).hexdigest() == plan["configuration_sha256"]
    changes = cfn.describe_change_set(ChangeSetName=plan["change_set"])["Changes"]
    by_id = {r["ResourceChange"]["LogicalResourceId"]: r["ResourceChange"] for r in changes}
    allowed = {"OrdersFunction", "OrdersIntegration"}
    if plan.get("add_notes_route"):
        allowed.add("OrdersNotesRoute")
    if plan.get("add_bulk_route"):
        allowed.add("OrdersBulkTransitionRoute")
    assert set(by_id) <= allowed and "OrdersFunction" in by_id
    resource = by_id["OrdersFunction"]
    assert resource["LogicalResourceId"] == "OrdersFunction" and resource["Action"] == "Modify"
    assert resource["Replacement"] == "False"
    assert all(d["Target"].get("Name") == "Code" for d in resource.get("Details", []))
    if "OrdersIntegration" in by_id:
        integration = by_id["OrdersIntegration"]
        assert integration["Action"] == "Modify" and integration["Replacement"] == "False"
        assert all(d["Evaluation"] == "Dynamic" and d["ChangeSource"] == "ResourceAttribute"
                   and d["CausingEntity"] == "OrdersFunction.Arn" and d["Target"]["Name"] == "IntegrationUri"
                   for d in integration["Details"])
    if plan.get("add_notes_route"):
        notes = by_id.get("OrdersNotesRoute")
        assert notes and notes["Action"] == "Add" and notes.get("Replacement", "False") == "False"
    if plan.get("add_bulk_route"):
        bulk = by_id.get("OrdersBulkTransitionRoute")
        assert bulk and bulk["Action"] == "Add" and bulk.get("Replacement", "False") == "False"
    print(json.dumps({"stack": STACK, "changes": [{"LogicalResourceId": r["LogicalResourceId"],
                      "Action": r["Action"], "Replacement": r.get("Replacement", "False")} for r in by_id.values()],
                      "source_commit": plan["source_commit"], "artifact_sha256": plan["artifact_sha256"]}))
    if args.execute:
        cfn.execute_change_set(ChangeSetName=plan["change_set"])
        cfn.get_waiter("stack_update_complete").wait(StackName=STACK, WaiterConfig={"Delay": 5, "MaxAttempts": 120})
        current_resources = resources()
        assert {key: current_resources[key] for key in plan["physical_ids_before"]} == plan["physical_ids_before"]
        if plan.get("add_notes_route") or plan.get("add_bulk_route"):
            if plan.get("add_notes_route"): assert "OrdersNotesRoute" in current_resources
            if plan.get("add_bulk_route"): assert "OrdersBulkTransitionRoute" in current_resources
            assert_api_after(plan)
        else:
            assert api_state(plan["api_id"], plan["physical_ids_before"]["OrdersIntegration"]) == plan["api_before"]
        assert hashlib.sha256(json.dumps(config(), sort_keys=True).encode()).hexdigest() == plan["configuration_sha256"]
        actual = lam.get_function_configuration(FunctionName=FUNCTION)
        assert actual["State"] == "Active" and actual["LastUpdateStatus"] == "Successful"
        plan["result"] = {"state": actual["State"], "code_sha256": actual["CodeSha256"], "physical_ids_preserved": True}
        args.plan.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(plan["result"]))


if __name__ == "__main__":
    main()
