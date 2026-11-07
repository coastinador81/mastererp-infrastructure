"""Register tienda-dev.uonify.com on the Tumandaito DEV store (admin PATCH)."""
import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import boto3
from botocore.config import Config

ADMIN_API = "https://qx8nmypdhi.execute-api.us-west-1.amazonaws.com"
TENANT = "9095f990-c1f7-4ccb-953d-f84083331bd6"
COMPANY = "8a13adba-1594-46e3-a41b-488fd91ea896"
STORE = "8064d270-09a9-4fcc-b304-9842b8df117c"
DOMAIN = "tienda-dev.uonify.com"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", type=Path, required=True)
    parser.add_argument("--profile", default="mastererp-admin")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(args.platform.resolve() / "scripts"))
    import identity_qa_client as qa

    session = boto3.Session(profile_name=args.profile, region_name="us-west-1")
    bundle = json.loads(session.client("secretsmanager").get_secret_value(SecretId="mastererp/dev/qa/identity-validation")["SecretString"])
    token = qa.tokens(bundle["actors"]["admin_a"])["access_token"]
    client = session.client("lambda", config=Config(read_timeout=310, retries={"max_attempts": 0}))
    nonce = str(uuid.uuid4())

    def invoke(action, **values):
        response = client.invoke(
            FunctionName="mastererp-dev-database-migrator",
            Payload=json.dumps({"action": action, **values}).encode(),
        )
        body = json.load(response["Payload"])
        if response.get("FunctionError") or body.get("status") != "succeeded":
            raise RuntimeError(f"{action} failed: {body}")
        return body

    def request(method, path, body=None):
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": TENANT,
            "Origin": "https://app-dev.uonify.com",
            "Content-Type": "application/json",
        }
        data = json.dumps(body).encode() if body is not None else None
        try:
            response = urllib.request.urlopen(
                urllib.request.Request(ADMIN_API + path, data=data, headers=headers, method=method),
                timeout=45,
            )
        except urllib.error.HTTPError as error:
            payload = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} -> {error.code}: {payload}") from error
        raw = response.read()
        return json.loads(raw) if raw else {}

    invoke("qa_phase8_membership", run=bundle["run"], operation="prepare", nonce=nonce)
    try:
        store = request("GET", f"/v1/companies/{COMPANY}/stores/{STORE}")
        patch = {
            "version": store["version"],
            "node_id": store["node_id"],
            "name": store["name"],
            "domain": DOMAIN,
            "changes": {"status": store.get("status", "ACTIVE")},
        }
        print(json.dumps({"current_domain": store.get("domain"), "patch": patch}, indent=2))
        if args.dry_run:
            return
        updated = request("PATCH", f"/v1/companies/{COMPANY}/stores/{STORE}", patch)
        print(json.dumps({"domain": updated.get("domain"), "status": updated.get("status")}, indent=2))
    finally:
        invoke("qa_phase8_membership", run=bundle["run"], operation="cleanup", nonce=nonce)


if __name__ == "__main__":
    main()
