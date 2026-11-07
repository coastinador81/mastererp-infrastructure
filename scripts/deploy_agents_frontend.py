"""Prepare/review/execute change sets for Agent Center static hosting (agentes-dev.uonify.com)."""
import argparse
import json
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = "277352717693"
STACK_CERT = "mastererp-dev-agents-frontend-certificate"
STACK_HOSTING = "mastererp-dev-agents-frontend"
DEFAULT_AGENT_DOMAIN = "agentes-dev.uonify.com"

def load_template(name: str) -> dict:
    path = ROOT / "modules/2.6-agent-center" / name
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["certificate", "hosting"])
    parser.add_argument("action", choices=["prepare", "execute"])
    parser.add_argument("--profile")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--domain",
        default=DEFAULT_AGENT_DOMAIN,
        help=f"Certificado y alias CloudFront/DNS (por defecto {DEFAULT_AGENT_DOMAIN})",
    )
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile)
    assert session.client("sts").get_caller_identity()["Account"] == ACCOUNT
    region = "us-east-1" if args.phase == "certificate" else "us-west-1"
    cf = session.client("cloudformation", region_name=region)
    name = STACK_CERT if args.phase == "certificate" else STACK_HOSTING
    args.output.mkdir(parents=True, exist_ok=True)
    plan = args.output / (args.phase + "-plan.json")
    if args.action == "prepare":
        template = load_template(
            "agents-frontend-certificate.json" if args.phase == "certificate" else "agents-frontend-hosting.json"
        )
        parameters = [{"ParameterKey": "FrontendDomainName", "ParameterValue": args.domain}]
        if args.phase == "hosting":
            certificate = session.client("cloudformation", region_name="us-east-1").describe_stacks(
                StackName=STACK_CERT
            )["Stacks"][0]
            assert certificate["StackStatus"] in ("CREATE_COMPLETE", "UPDATE_COMPLETE"), "Esperar a que termine el stack del certificado antes de preparar hosting"
            arn = next(o["OutputValue"] for o in certificate["Outputs"] if o["OutputKey"] == "CertificateArn")
            issued = session.client("acm", region_name="us-east-1").describe_certificate(CertificateArn=arn)["Certificate"]
            assert issued["Status"] == "ISSUED" and args.domain in issued.get("SubjectAlternativeNames", []), "El certificado debe estar emitido para el dominio solicitado"
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
        cf.create_change_set(
            StackName=name,
            ChangeSetName=change,
            ChangeSetType="UPDATE" if exists else "CREATE",
            TemplateBody=body,
            Parameters=parameters,
            Capabilities=["CAPABILITY_NAMED_IAM"],
            Tags=[
                {"Key": "Project", "Value": "MasterERP"},
                {"Key": "Environment", "Value": "dev"},
                {"Key": "Component", "Value": "agents-frontend"},
            ],
        )
        try:
            cf.get_waiter("change_set_create_complete").wait(
                StackName=name, ChangeSetName=change, WaiterConfig={"Delay": 3, "MaxAttempts": 100}
            )
        except Exception:
            detail = cf.describe_change_set(StackName=name, ChangeSetName=change)
            if "didn't contain changes" in detail.get("StatusReason", "") or "No updates" in detail.get(
                "StatusReason", ""
            ):
                print("NO_CHANGES: resources preserved")
                plan.write_text(json.dumps({"no_changes": True}))
                return
            raise
        detail = cf.describe_change_set(StackName=name, ChangeSetName=change)
        changes = [item["ResourceChange"] for item in detail["Changes"]]

        def _change_ok(c: dict) -> bool:
            if c["Action"] == "Remove":
                return False
            if c.get("Replacement", "False") == "False":
                return True
            # Cambiar el FQDN del certificado ACM fuerza sustitución del recurso Certificate
            return args.phase == "certificate" and c.get("ResourceType") == "AWS::CertificateManager::Certificate"

        assert all(_change_ok(c) for c in changes), "Cambio inesperado (p. ej. borrado o reemplazo no permitido); no ejecutar"
        plan.write_text(json.dumps({"stack": name, "change_set": change, "region": region, "changes": changes}, indent=2))
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
