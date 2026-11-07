"""DEV: change only OrdersArtifactKey on its existing native CloudFormation owner."""
import argparse
import hashlib
import json
from pathlib import Path
import time
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
    args = parser.parse_args()
    session = boto3.Session(profile_name="mastererp-admin", region_name="us-west-1")
    assert session.client("sts").get_caller_identity()["Account"] == ACCOUNT
    cfn, s3, lam = (session.client(name) for name in ("cloudformation", "s3", "lambda"))

    def resources():
        rows = [r for page in cfn.get_paginator("list_stack_resources").paginate(StackName=STACK)
                for r in page["StackResourceSummaries"]]
        return {r["LogicalResourceId"]: r["PhysicalResourceId"] for r in rows}

    def config():
        c = lam.get_function_configuration(FunctionName=FUNCTION)
        return {key: c.get(key) for key in ("Role", "Runtime", "Handler", "MemorySize", "Timeout", "VpcConfig", "Environment")}

    if not args.execute:
        assert args.artifact and args.source_commit and len(args.source_commit) == 40
        stack = cfn.describe_stacks(StackName=STACK)["Stacks"][0]
        params = {p["ParameterKey"]: p["ParameterValue"] for p in stack["Parameters"]}
        before = resources()
        assert before["OrdersFunction"] == FUNCTION
        digest = hashlib.sha256(args.artifact.read_bytes()).hexdigest()
        key = f"mastererp/dev/orders-sales/{args.source_commit}/{digest}.zip"
        s3.upload_file(str(args.artifact), params["ArtifactBucket"], key)
        name = "orders-sales-" + str(int(time.time()))
        change = cfn.create_change_set(StackName=STACK, ChangeSetName=name,
            ChangeSetType="UPDATE", UsePreviousTemplate=True, Capabilities=["CAPABILITY_NAMED_IAM"],
            Parameters=[{"ParameterKey": k, **({"ParameterValue": key} if k == "OrdersArtifactKey"
                         else {"UsePreviousValue": True})} for k in params])
        cfn.get_waiter("change_set_create_complete").wait(ChangeSetName=change["Id"], WaiterConfig={"Delay": 3, "MaxAttempts": 40})
        plan = {"stack": STACK, "stack_id": stack["StackId"], "change_set": change["Id"],
                "artifact_sha256": digest, "source_commit": args.source_commit, "artifact_key": key,
                "old_artifact_key": params["OrdersArtifactKey"], "physical_ids_before": before,
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
    assert len(changes) == 1, "Only OrdersFunction may change"
    resource = changes[0]["ResourceChange"]
    assert resource["LogicalResourceId"] == "OrdersFunction" and resource["Action"] == "Modify"
    assert resource["Replacement"] == "False"
    assert all(d["Target"].get("Name") == "Code" for d in resource.get("Details", []))
    print(json.dumps({"stack": STACK, "changes": [{k: resource[k] for k in ("LogicalResourceId", "Action", "Replacement")}],
                      "source_commit": plan["source_commit"], "artifact_sha256": plan["artifact_sha256"]}))
    if args.execute:
        cfn.execute_change_set(ChangeSetName=plan["change_set"])
        cfn.get_waiter("stack_update_complete").wait(StackName=STACK, WaiterConfig={"Delay": 5, "MaxAttempts": 120})
        assert resources() == plan["physical_ids_before"]
        assert hashlib.sha256(json.dumps(config(), sort_keys=True).encode()).hexdigest() == plan["configuration_sha256"]
        actual = lam.get_function_configuration(FunctionName=FUNCTION)
        assert actual["State"] == "Active" and actual["LastUpdateStatus"] == "Successful"
        plan["result"] = {"state": actual["State"], "code_sha256": actual["CodeSha256"], "physical_ids_preserved": True}
        args.plan.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(plan["result"]))


if __name__ == "__main__":
    main()
