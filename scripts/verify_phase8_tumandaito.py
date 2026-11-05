"""Authenticated, read-only Phase 8 smoke over the migrated Tumandaito tenant."""
import argparse
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

import boto3
from botocore.config import Config

ADMIN_API = "https://qx8nmypdhi.execute-api.us-west-1.amazonaws.com"
CLIENT_API = "https://btqqku792c.execute-api.us-west-1.amazonaws.com"
SOURCE_SHA = "6a6d9c5030bd7c63070a91876b9114b0d8d36553cddf8c15bc103589084a212d"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--platform", type=Path, required=True)
    parser.add_argument("--profile", default="andrea_madriz_mastererp")
    args = parser.parse_args()
    sys.path.insert(0, str(args.platform.resolve() / "scripts"))
    import identity_qa_client as qa

    session = boto3.Session(profile_name=args.profile, region_name="us-west-1")
    if session.client("sts").get_caller_identity()["Account"] != "277352717693":
        raise RuntimeError("Unexpected AWS account")
    secret = session.client("secretsmanager").get_secret_value(
        SecretId="mastererp/dev/qa/identity-validation"
    )
    bundle = json.loads(secret["SecretString"])
    token = qa.tokens(bundle["actors"]["admin_a"])["access_token"]
    client = session.client("lambda", config=Config(read_timeout=310, retries={"max_attempts": 0}))
    nonce = str(uuid.uuid4())
    results = []
    prepared = False

    def invoke(action, **values):
        payload = {"action": action, **values}
        response = client.invoke(
            FunctionName="mastererp-dev-database-migrator",
            Payload=json.dumps(payload).encode(),
        )
        body = json.load(response["Payload"])
        if response.get("FunctionError") or body.get("status") != "succeeded":
            raise RuntimeError(action + " failed")
        return body

    def request(base, path, tenant, auth=True):
        headers = {"Origin": "https://app-dev.uonify.com", "X-Tenant-Id": tenant}
        if auth:
            headers["Authorization"] = "Bearer " + token
        try:
            response = urllib.request.urlopen(
                urllib.request.Request(base + path, headers=headers), timeout=30
            )
        except urllib.error.HTTPError as error:
            response = error
        raw = response.read()
        try:
            body = json.loads(raw) if raw else {}
        except ValueError:
            body = {}
        return response.status, body

    def check(name, response, expected, predicate=lambda body: True):
        status, body = response
        passed = status == expected and predicate(body)
        results.append({"case": name, "http": status, "expected": expected,
                        "result": "passed" if passed else "failed"})
        return body

    try:
        scope = invoke("inspect_business_tenant", name="Tumandaito")
        tenant = scope["tenants"][0]
        company = tenant["companies"][0]["id"]
        tenant_id = tenant["id"]
        snapshot = invoke("inspect_phase6", name="Tumandaito", source_sha256=SOURCE_SHA)
        nodes = [row["target_id"] for row in snapshot["snapshot"]["nodes"]]
        domain = snapshot["snapshot"]["stores"][0]["domain"]

        initial = request(ADMIN_API, "/v1/catalog/categories", tenant_id)
        if initial[0] == 200:
            invoke("qa_phase8_membership", run=bundle["run"], operation="cleanup", nonce=nonce)
            results.append({"case": "interrupted_membership_recovered", "result": "passed"})
            initial = request(ADMIN_API, "/v1/catalog/categories", tenant_id)
        check("before_membership_denied", initial, 403)
        prepared = True
        invoke("qa_phase8_membership", run=bundle["run"], operation="prepare", nonce=nonce)
        invoke("qa_phase8_membership", run=bundle["run"], operation="inspect", nonce=nonce)

        reads = (
            ("categories", "/v1/catalog/categories", snapshot["counts"]["categories"]),
            ("products", "/v1/products", snapshot["counts"]["products"]),
            ("nodes", f"/v1/companies/{company}/nodes", snapshot["counts"]["nodes"]),
            ("drivers", f"/v1/companies/{company}/drivers", snapshot["counts"]["drivers"]),
            ("orders", f"/v1/companies/{company}/orders", snapshot["counts"]["orders"]),
            ("routes", f"/v1/companies/{company}/routes", snapshot["counts"]["routes"]),
            ("stores", f"/v1/companies/{company}/stores", snapshot["counts"]["stores"]),
        )
        for name, path, count in reads:
            check(name, request(ADMIN_API, path, tenant_id), 200,
                  lambda body, expected=count: len(body.get("items", [])) == expected)
        check("preparations", request(ADMIN_API, f"/v1/companies/{company}/preparations", tenant_id), 200,
              lambda body: isinstance(body.get("items"), list))

        inventory_count = 0
        inventory_ok = True
        for node in nodes:
            status, body = request(ADMIN_API, f"/v1/companies/{company}/nodes/{node}/inventory", tenant_id)
            inventory_ok = inventory_ok and status == 200 and isinstance(body.get("items"), list)
            inventory_count += len(body.get("items", []))
        results.append({"case": "inventory", "http": 200 if inventory_ok else 500,
                        "expected": 200, "count": inventory_count,
                        "expected_count": snapshot["counts"]["inventories"],
                        "result": "passed" if inventory_ok and inventory_count == snapshot["counts"]["inventories"] else "failed"})

        public_path = "/v1/storefront/catalog?" + urllib.parse.urlencode({"domain": domain})
        check("public_storefront", request(CLIENT_API, public_path, tenant_id, auth=False), 200,
              lambda body: not body.get("error"))
        check("foreign_tenant_denied", request(ADMIN_API, "/v1/catalog/categories", bundle["tenants"]["b"]), 403)
    except Exception as error:
        results.append({"case": "runner", "result": "failed", "error": type(error).__name__})
    finally:
        if prepared:
            try:
                invoke("qa_phase8_membership", run=bundle["run"], operation="cleanup", nonce=nonce)
                results.append({"case": "temporary_membership_removed", "result": "passed"})
                check("after_cleanup_denied", request(ADMIN_API, "/v1/catalog/categories", tenant_id), 403)
            except Exception:
                results.append({"case": "temporary_membership_removed", "result": "failed"})
        report = {"environment": "DEV", "region": "us-west-1", "read_only": True,
                  "source_sha256": SOURCE_SHA, "results": results,
                  "status": "passed" if results and all(row["result"] == "passed" for row in results) else "failed"}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
