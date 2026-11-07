"""Selective DEV Sales update through the existing Finance parent; native routes only."""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import time
import boto3
from deploy_administration import assemble


PARENT, CHILD, API = "mastererp-dev-finance", "mastererp-dev-administration", "qx8nmypdhi"
ADDITIONS = {"VentasListRoute", "VentasDetailRoute", "VentasListPermission", "VentasDetailPermission"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact", type=Path)
    p.add_argument("--source-commit")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    session = boto3.Session(profile_name="mastererp-admin", region_name="us-west-1")
    assert session.client("sts").get_caller_identity()["Account"] == "277352717693"
    cf, api, lam, store = (session.client(name) for name in ("cloudformation", "apigatewayv2", "lambda", "s3"))
    assert api.get_api(ApiId=API)["Name"] == "mastererp-dev-admin-api"
    assert cf.describe_stack_resource(StackName="mastererp-dev-onboarding", LogicalResourceId="AdminHttpApi")["StackResourceDetail"]["PhysicalResourceId"] == API

    def resources(stack):
        return {r["LogicalResourceId"]: r["PhysicalResourceId"] for page in cf.get_paginator("list_stack_resources").paginate(StackName=stack) for r in page["StackResourceSummaries"]}

    def routes():
        return {r["RouteId"]: r for page in api.get_paginator("get_routes").paginate(ApiId=API) for r in page["Items"]}

    def review(changes, allowed, additions):
        result = []
        for change in changes:
            r = change["ResourceChange"]
            assert r["LogicalResourceId"] in allowed, "Unrelated resource: " + r["LogicalResourceId"]
            assert r["Action"] in ("Add", "Modify") and r.get("Replacement", "False") == "False"
            if r["Action"] == "Add":
                assert r["LogicalResourceId"] in additions
            result.append({k: r.get(k) for k in ("LogicalResourceId", "Action", "Replacement")})
        return result

    if not args.execute:
        assert args.artifact and args.source_commit and len(args.source_commit) == 40
        parent = cf.describe_stacks(StackName=PARENT)["Stacks"][0]
        child = cf.describe_stacks(StackName=CHILD)["Stacks"][0]
        assert child["ParentId"] == parent["StackId"]
        old = cf.get_template(StackName=CHILD, TemplateStage="Original")["TemplateBody"]
        old = json.loads(old) if isinstance(old, str) else old
        _, desired = assemble()
        candidate = copy.deepcopy(old)
        owned = {key for key in desired["Resources"] if key.startswith("Ventas")}
        assert owned - set(old["Resources"]) == ADDITIONS
        for key in owned:
            candidate["Resources"][key] = desired["Resources"][key]
        for key, value in desired["Parameters"].items():
            assert key in old["Parameters"] and old["Parameters"][key] == value, "Existing parameter contract must remain unchanged"
        before_routes = routes()
        assert not any(r["RouteKey"] in ("GET /v1/administration/ventas", "GET /v1/administration/ventas/{id}") for r in before_routes.values()), "Route already exists: inspect ownership"
        parameters = {x["ParameterKey"]: x["ParameterValue"] for x in parent["Parameters"]}
        bucket = parameters["ArtifactBucket"]
        assert store.get_bucket_location(Bucket=bucket)["LocationConstraint"] == "us-west-1"
        assert all(store.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"].values())
        blob = args.artifact.read_bytes()
        checksum = hashlib.sha256(blob).hexdigest()
        artifact_key = f"mastererp/dev/administration/sales/{args.source_commit}/{checksum}.zip"
        store.put_object(Bucket=bucket, Key=artifact_key, Body=blob, ContentType="application/zip", ServerSideEncryption="AES256")
        body = json.dumps(candidate, sort_keys=True, separators=(",", ":")).encode()
        template_key = "mastererp/dev/finance/templates/" + hashlib.sha256(body).hexdigest() + ".json"
        store.put_object(Bucket=bucket, Key=template_key, Body=body, ContentType="application/json", ServerSideEncryption="AES256")
        changes = {"VentasArtifactKey": artifact_key, "AdministrationTemplateUrl": f"https://{bucket}.s3.us-west-1.amazonaws.com/{template_key}"}
        response = cf.create_change_set(StackName=PARENT, ChangeSetName="sales-read-" + str(int(time.time())),
            ChangeSetType="UPDATE", UsePreviousTemplate=True, IncludeNestedStacks=True,
            Capabilities=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            Parameters=[{"ParameterKey": k, **({"ParameterValue": changes[k]} if k in changes else {"UsePreviousValue": True})} for k in parameters])
        cf.get_waiter("change_set_create_complete").wait(ChangeSetName=response["Id"], WaiterConfig={"Delay": 5, "MaxAttempts": 80})
        plan = {"change_set": response["Id"], "source_commit": args.source_commit, "artifact_sha256": checksum,
                "parent_ids": resources(PARENT), "child_ids": resources(CHILD), "routes_before": before_routes,
                "cors_before": api.get_api(ApiId=API).get("CorsConfiguration"), "owned": sorted(owned),
                "previous_artifact_key": parameters["VentasArtifactKey"], "previous_template_url": parameters["AdministrationTemplateUrl"]}
        args.plan.parent.mkdir(parents=True, exist_ok=True)
        args.plan.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    else:
        plan = json.loads(args.plan.read_text())
        assert resources(PARENT) == plan["parent_ids"] and resources(CHILD) == plan["child_ids"]
        assert routes() == plan["routes_before"]
    root_plan = cf.describe_change_set(ChangeSetName=plan["change_set"])
    summary = review(root_plan["Changes"], {"Administration"}, set())
    nested = []
    for change in root_plan["Changes"]:
        r = change["ResourceChange"]
        assert r.get("ChangeSetId"), "Nested change set review is required"
        nested_plan = cf.describe_change_set(ChangeSetName=r["ChangeSetId"])
        nested += review(nested_plan["Changes"], set(plan["owned"]), ADDITIONS)
    print(json.dumps({"root": summary, "child": nested, "source_commit": plan["source_commit"]}))
    if args.execute:
        cf.execute_change_set(ChangeSetName=plan["change_set"])
        cf.get_waiter("stack_update_complete").wait(StackName=PARENT, WaiterConfig={"Delay": 5, "MaxAttempts": 120})
        assert resources(PARENT) == plan["parent_ids"]
        after = resources(CHILD)
        assert all(after.get(k) == v for k, v in plan["child_ids"].items())
        after_routes = routes()
        assert all(after_routes.get(k) == v for k, v in plan["routes_before"].items())
        assert api.get_api(ApiId=API).get("CorsConfiguration") == plan["cors_before"]
        config = lam.get_function_configuration(FunctionName="mastererp-dev-adm-ventas")
        assert config["State"] == "Active" and config["LastUpdateStatus"] == "Successful"
        assert config["CodeSha256"] == base64.b64encode(bytes.fromhex(plan["artifact_sha256"])).decode()
        plan["result"] = {"state": config["State"], "code_sha256": config["CodeSha256"], "ids_and_previous_routes_preserved": True}
        args.plan.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(plan["result"]))


if __name__ == "__main__":
    main()
