"""Prepare/review/execute Finance-only change sets. Never deploy the full Finance parent."""
import argparse
import copy
import json
from pathlib import Path
import time
import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = "277352717693"

def assemble():
    source = json.loads((ROOT / "modules/2.2-finance/resources.yml").read_text())
    manifest = source["Metadata"]["FinanceFrontendComposition"]
    result = {"AWSTemplateFormatVersion": "2010-09-09", "Description": "MasterERP Finance independent frontend hosting"}
    for section, keys in manifest.items():
        result[section] = {key: copy.deepcopy(source[section][key]) for key in keys if key != "FrontendEnabled"}
    for section in ("Resources", "Outputs"):
        for value in result[section].values():
            value.pop("Condition", None)
    assert all(not key.startswith("Administration") for key in result["Resources"])
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["certificate", "hosting"])
    parser.add_argument("action", choices=["prepare", "execute"])
    parser.add_argument("--profile")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile)
    assert session.client("sts").get_caller_identity()["Account"] == ACCOUNT
    region = "us-east-1" if args.phase == "certificate" else "us-west-1"
    cf = session.client("cloudformation", region_name=region)
    name = "mastererp-dev-finance-frontend" + ("-certificate" if args.phase == "certificate" else "")
    args.output.mkdir(parents=True, exist_ok=True)
    plan = args.output / (args.phase + "-plan.json")
    if args.action == "prepare":
        template = json.loads((ROOT / "modules/2.2-finance/certificate.yml").read_text()) if args.phase == "certificate" else assemble()
        parameters = []
        if args.phase == "hosting":
            certificate = session.client("cloudformation", region_name="us-east-1").describe_stacks(StackName="mastererp-dev-finance-frontend-certificate")["Stacks"][0]
            arn = next(o["OutputValue"] for o in certificate["Outputs"] if o["OutputKey"] == "CertificateArn")
            parameters.append({"ParameterKey": "FrontendCertificateArn", "ParameterValue": arn})
        body = json.dumps(template)
        cf.validate_template(TemplateBody=body)
        try:
            stack = cf.describe_stacks(StackName=name)["Stacks"][0]
            exists = stack["StackStatus"] != "REVIEW_IN_PROGRESS"
        except ClientError as error:
            if "does not exist" not in str(error):
                raise
            exists = False
        change = name + "-" + str(int(time.time()))
        cf.create_change_set(StackName=name, ChangeSetName=change, ChangeSetType="UPDATE" if exists else "CREATE", TemplateBody=body, Parameters=parameters, Capabilities=["CAPABILITY_NAMED_IAM"], Tags=[{"Key":"Project","Value":"MasterERP"},{"Key":"Environment","Value":"dev"},{"Key":"Component","Value":"finance-frontend"}])
        try:
            cf.get_waiter("change_set_create_complete").wait(StackName=name, ChangeSetName=change, WaiterConfig={"Delay":3,"MaxAttempts":100})
        except Exception:
            detail = cf.describe_change_set(StackName=name, ChangeSetName=change)
            if "didn't contain changes" in detail.get("StatusReason", "") or "No updates" in detail.get("StatusReason", ""):
                print("NO_CHANGES: resources preserved")
                plan.write_text(json.dumps({"no_changes":True}))
                return
            raise
        detail = cf.describe_change_set(StackName=name, ChangeSetName=change)
        changes = [item["ResourceChange"] for item in detail["Changes"]]
        assert all(c["Action"] != "Remove" and c.get("Replacement", "False") == "False" for c in changes), "Unexpected removal/replacement; do not execute"
        plan.write_text(json.dumps({"stack":name,"change_set":change,"region":region,"changes":changes},indent=2))
        print(plan.read_text())
    else:
        data = json.loads(plan.read_text())
        if data.get("no_changes"):
            print("NO_CHANGES: nothing to execute")
            return
        assert data["stack"] == name and data["region"] == region
        detail = cf.describe_change_set(StackName=name, ChangeSetName=data["change_set"])
        assert [item["ResourceChange"] for item in detail["Changes"]] == data["changes"]
        assert detail["Status"] == "CREATE_COMPLETE"
        cf.execute_change_set(StackName=name, ChangeSetName=data["change_set"])
        print("Change set executed; inspect stack status before publishing")

if __name__ == "__main__":
    main()
