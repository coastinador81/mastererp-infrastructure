"""Upload immutable artifacts and prepare, never execute, Phase 7 change sets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from phase7_templates import MANIFEST, assemble

ACCOUNT = "277352717693"
REGION = "us-west-1"
ADMIN_API = "qx8nmypdhi"
CLIENT_API = "btqqku792c"
AUTHORIZER = "49et65"
REFERENCE_FUNCTION = "mastererp-dev-adm-proveedores"


def aws(profile, *command, optional=False):
    cmd = ["aws", "--region", REGION, "--profile", profile, "--output", "json",
           "--no-cli-pager", *command]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        if optional and ("does not exist" in result.stderr or
                         "ResourceNotFound" in result.stderr or "NotFound" in result.stderr):
            return None
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout) if result.stdout.strip() else {}


def environment(profile, bucket):
    identity = aws(profile, "sts", "get-caller-identity")
    if identity["Account"] != ACCOUNT:
        raise ValueError("Exact DEV account required")
    location = aws(profile, "s3api", "get-bucket-location", "--bucket", bucket)["LocationConstraint"]
    if location != REGION:
        raise ValueError("Artifact bucket must be in us-west-1")
    block = aws(profile, "s3api", "get-public-access-block", "--bucket", bucket)["PublicAccessBlockConfiguration"]
    if not all(block.get(key) for key in
               ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")):
        raise ValueError("Artifact bucket must block all public access")
    authorizers = aws(profile, "apigatewayv2", "get-authorizers", "--api-id", ADMIN_API)["Items"]
    if not any(item["AuthorizerId"] == AUTHORIZER and
               item["Name"] == "mastererp-dev-admin-jwt" and item["AuthorizerType"] == "JWT"
               for item in authorizers):
        raise ValueError("Exact shared Admin JWT authorizer required")
    for api_id, name in ((ADMIN_API, "mastererp-dev-admin-api"),
                         (CLIENT_API, "mastererp-dev-client-api")):
        if aws(profile, "apigatewayv2", "get-api", "--api-id", api_id)["Name"] != name:
            raise ValueError("Shared API identity mismatch")
    config = aws(profile, "lambda", "get-function-configuration",
                 "--function-name", REFERENCE_FUNCTION)
    values = config["Environment"]["Variables"]
    if config["Architectures"] != ["arm64"] or config["Runtime"] != "python3.12":
        raise ValueError("Reference Lambda runtime mismatch")
    return {"Environment": "dev", "ArtifactBucket": bucket,
            "ExistingAdminApiId": ADMIN_API, "ExistingClientApiId": CLIENT_API,
            "AdminJwtAuthorizerId": AUTHORIZER, "DatabaseHost": values["DATABASE_HOST"],
            "DatabaseSecretArn": values["DATABASE_SECRET_ARN"],
            "PrivateSubnetIds": ",".join(config["VpcConfig"]["SubnetIds"]),
            "SecurityGroupIds": ",".join(config["VpcConfig"]["SecurityGroupIds"]),
            "CognitoIssuer": values["COGNITO_ISSUER"],
            "CognitoClientId": values["COGNITO_APP_CLIENT_ID"]}


def ensure_additive(profile, stack, template):
    if aws(profile, "cloudformation", "describe-stacks", "--stack-name", stack, optional=True):
        raise ValueError("Phase 7 stack already exists: " + stack)
    for item in template["Resources"].values():
        if item["Type"] == "AWS::Lambda::Function":
            name = item["Properties"]["FunctionName"]["Fn::Sub"].replace("${Environment}", "dev")
            if aws(profile, "lambda", "get-function", "--function-name", name, optional=True):
                raise ValueError("Lambda already exists outside Phase 7 stack: " + name)
    actual = {}
    for api_id in (ADMIN_API, CLIENT_API):
        actual[api_id] = {item["RouteKey"] for item in
                          aws(profile, "apigatewayv2", "get-routes", "--api-id", api_id)["Items"]}
    for item in template["Resources"].values():
        if item["Type"] != "AWS::ApiGatewayV2::Route":
            continue
        props = item["Properties"]
        api_id = CLIENT_API if props["ApiId"] == {"Ref": "ExistingClientApiId"} else ADMIN_API
        if props["RouteKey"] in actual[api_id]:
            raise ValueError("Route already exists: " + props["RouteKey"])


def prepare_domain(args, domain, base, artifact_manifest):
    stack, template = assemble(domain); ensure_additive(args.profile, stack, template)
    template_path = args.output / f"{stack}.json"
    template_path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    parameters = []
    for key in template["Parameters"]:
        if key.endswith("ArtifactKey"):
            module = key[:-11].lower(); item = artifact_manifest[module]
            archive = args.artifacts / item["file"]
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            if digest != item["sha256"]:
                raise ValueError("Artifact hash mismatch: " + module)
            object_key = f"mastererp/dev/phase7/{args.platform_commit}/{module}/{digest}.zip"
            aws(args.profile, "s3api", "put-object", "--bucket", args.bucket, "--key", object_key,
                "--body", str(archive), "--content-type", "application/zip",
                "--server-side-encryption", "AES256")
            value = object_key
        else:
            value = base[key]
        parameters.append({"ParameterKey": key, "ParameterValue": value})
    name = f"phase7-{domain}-{args.infrastructure_commit[:12]}"
    aws(args.profile, "cloudformation", "create-change-set", "--stack-name", stack,
        "--change-set-name", name, "--change-set-type", "CREATE",
        "--capabilities", "CAPABILITY_IAM", "--template-body", "file://" + str(template_path),
        "--parameters", json.dumps(parameters), "--tags", "Key=Project,Value=MasterERP",
        "Key=Environment,Value=dev", f"Key=Domain,Value={domain}")
    deadline = time.monotonic() + 600
    while True:
        plan = aws(args.profile, "cloudformation", "describe-change-set", "--stack-name", stack,
                   "--change-set-name", name)
        if plan["Status"] in ("CREATE_COMPLETE", "FAILED"):
            break
        if time.monotonic() > deadline:
            raise TimeoutError("Change set preparation timed out: " + stack)
        time.sleep(3)
    if plan["Status"] != "CREATE_COMPLETE":
        raise RuntimeError(plan.get("StatusReason", "Change set failed"))
    changes = [item["ResourceChange"] for item in plan["Changes"]]
    if len(changes) != len(template["Resources"]):
        raise ValueError("Change set does not contain the exact composed resources")
    for change in changes:
        expected = template["Resources"].get(change["LogicalResourceId"])
        if not expected or change["Action"] != "Add" or change["ResourceType"] != expected["Type"]:
            raise ValueError("Non-additive change set rejected")
    record = {"stack": stack, "change_set": name, "status": plan["Status"],
              "platform_commit": args.platform_commit,
              "infrastructure_commit": args.infrastructure_commit, "changes": changes}
    (args.output / f"{stack}-plan.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"REVIEW_ONLY: {stack}, {len(changes)} Add changes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True); parser.add_argument("--bucket", required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--platform-commit", required=True); parser.add_argument("--infrastructure-commit", required=True)
    parser.add_argument("--domain", action="append", choices=json.loads(MANIFEST.read_text()).keys())
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    for value in (args.platform_commit, args.infrastructure_commit):
        if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("Full lowercase Git commits required")
    artifact_manifest = json.loads((args.artifacts / "manifest.json").read_text())
    base = environment(args.profile, args.bucket)
    for domain in args.domain or json.loads(MANIFEST.read_text()).keys():
        prepare_domain(args, domain, base, artifact_manifest)


if __name__ == "__main__":
    main()
