"""Compose and validate additive Phase 7 templates without changing AWS."""
import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts/phase7_domains.json"
ALLOWED_TYPES = {"AWS::ApiGatewayV2::Integration", "AWS::ApiGatewayV2::Route",
                 "AWS::IAM::Role", "AWS::Lambda::Function", "AWS::Lambda::Permission",
                 "AWS::Logs::LogGroup"}
COMMON_PARAMETERS = {"Environment", "ArtifactBucket", "ExistingAdminApiId",
                     "AdminJwtAuthorizerId", "DatabaseHost", "DatabaseSecretArn",
                     "PrivateSubnetIds", "SecurityGroupIds", "CognitoIssuer", "CognitoClientId"}


def _merge(target, source, section):
    for key, value in source.get(section, {}).items():
        if key in target and target[key] != value:
            raise ValueError(f"Conflicting {section} declaration: {key}")
        target[key] = copy.deepcopy(value)


def assemble(domain):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if domain not in manifest:
        raise ValueError("Unknown Phase 7 domain: " + domain)
    result = {"AWSTemplateFormatVersion": "2010-09-09",
              "Description": "MasterERP DEV additive " + domain + " APIs",
              "Metadata": {"MasterERP": {"Phase": 7, "Domain": domain,
                                           "Composition": manifest[domain]["modules"]}},
              "Parameters": {}, "Resources": {}, "Outputs": {}}
    for module in manifest[domain]["modules"]:
        source = json.loads((ROOT / "modules" / module / "resources.yml").read_text(encoding="utf-8"))
        for section in ("Parameters", "Resources", "Outputs"):
            _merge(result[section], source, section)
    validate(domain, result)
    return manifest[domain]["stack"], result


def validate(domain, template):
    resources = template["Resources"]
    if not resources or not {item["Type"] for item in resources.values()} <= ALLOWED_TYPES:
        raise ValueError("Unexpected or empty Phase 7 resources")
    routes = [item["Properties"] for item in resources.values()
              if item["Type"] == "AWS::ApiGatewayV2::Route"]
    keys = [route["RouteKey"] for route in routes]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate route in composed template")
    for route in routes:
        public = route["RouteKey"] == "GET /v1/storefront/catalog"
        expected_api = "ExistingClientApiId" if public else "ExistingAdminApiId"
        if route["ApiId"] != {"Ref": expected_api}:
            raise ValueError("Route uses the wrong shared API: " + route["RouteKey"])
        if route["AuthorizationType"] != ("NONE" if public else "JWT"):
            raise ValueError("Invalid route authorization: " + route["RouteKey"])
        if not public and route.get("AuthorizerId") != {"Ref": "AdminJwtAuthorizerId"}:
            raise ValueError("Administrative route lacks the shared JWT authorizer")
    expected = COMMON_PARAMETERS | ({"ExistingClientApiId"} if domain == "digital-sales" else set())
    artifacts = {key for key in template["Parameters"] if key.endswith("ArtifactKey")}
    if set(template["Parameters"]) != expected | artifacts:
        raise ValueError("Unexpected parameter contract")
    expected_vpc = {"SubnetIds": {"Ref": "PrivateSubnetIds"},
                    "SecurityGroupIds": {"Ref": "SecurityGroupIds"}}
    for item in resources.values():
        if item["Type"] == "AWS::Lambda::Function":
            properties = item["Properties"]
            if properties.get("Architectures") != ["arm64"] or properties.get("Runtime") != "python3.12":
                raise ValueError("Lambda runtime contract mismatch")
            if properties.get("VpcConfig") != expected_vpc:
                raise ValueError("Lambda must use the application VPC contract")


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--domain", choices=manifest.keys(), action="append")
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    for domain in args.domain or manifest.keys():
        stack, template = assemble(domain)
        path = args.output / f"{stack}.json"
        path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
        print(f"Prepared locally: {stack} ({len(template['Resources'])} resources)")


if __name__ == "__main__":
    main()
