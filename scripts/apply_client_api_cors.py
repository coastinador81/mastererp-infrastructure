"""Apply storefront Client API CORS from modules/2.4-digital-sales/2.4.2-ecommerce/client-api-cors-dev.json."""
import argparse
import json
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "modules/2.4-digital-sales/2.4.2-ecommerce/client-api-cors-dev.json"
ACCOUNT = "277352717693"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    spec = json.loads(SOURCE.read_text(encoding="utf-8"))
    api_id = spec["ApiId"]
    cors = spec["CorsConfiguration"]
    session = boto3.Session(profile_name=args.profile, region_name="us-west-1")
    assert session.client("sts").get_caller_identity()["Account"] == ACCOUNT
    api = session.client("apigatewayv2")
    before = api.get_api(ApiId=api_id).get("CorsConfiguration")
    if before == cors:
        print("NO_CHANGES: CORS already matches", SOURCE.name)
        return
    print("Before:", json.dumps(before, indent=2))
    print("After:", json.dumps(cors, indent=2))
    if args.dry_run:
        return
    api.update_api(ApiId=api_id, CorsConfiguration=cors)
    after = api.get_api(ApiId=api_id).get("CorsConfiguration")
    assert after == cors
    print("Client API CORS updated:", api_id)


if __name__ == "__main__":
    main()
