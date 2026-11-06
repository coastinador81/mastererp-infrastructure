"""Read-only verification of Agent Center landing (agents.uonify.com)."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import ssl
import urllib.error
import urllib.request

import boto3

DOMAIN = "agents.uonify.com"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile, region_name="us-west-1")
    assert session.client("sts").get_caller_identity()["Account"] == "277352717693"
    cf = session.client("cloudformation")
    stack = cf.describe_stacks(StackName="mastererp-dev-agents-frontend")["Stacks"][0]
    assert stack["StackStatus"] in ("CREATE_COMPLETE", "UPDATE_COMPLETE")
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}
    bucket = outputs["FrontendBucketName"]
    distribution = outputs["FrontendDistributionId"]
    resources = {
        r["LogicalResourceId"]: r["PhysicalResourceId"] for r in cf.list_stack_resources(StackName=stack["StackId"])["StackResourceSummaries"]
    }
    report = {"url": "https://" + DOMAIN, "stack": stack["StackId"], "resources": resources}
    report["dns"] = sorted({s[4][0] for s in socket.getaddrinfo(DOMAIN, 443)})
    with socket.create_connection((DOMAIN, 443), timeout=20) as tcp:
        with ssl.create_default_context().wrap_socket(tcp, server_hostname=DOMAIN) as tls:
            report["tls"] = {"version": tls.version(), "subjectAltName": tls.getpeercert()["subjectAltName"]}
    with urllib.request.urlopen("https://" + DOMAIN + "/", timeout=30) as response:
        html = response.read()
        report["https"] = {
            "status": response.status,
            "content_type": response.headers["Content-Type"],
            "sha256": hashlib.sha256(html).hexdigest(),
        }
        assert response.status == 200 and "text/html" in response.headers["Content-Type"]
    text = html.decode("utf-8")
    assert "Centro de Agentes" in text
    report["scope"] = "página estática mínima; UI completa comprobada aparte"
    try:
        urllib.request.build_opener(NoRedirect()).open("http://" + DOMAIN + "/", timeout=30)
        raise AssertionError("HTTP did not redirect")
    except urllib.error.HTTPError as error:
        assert error.code in (301, 302, 307, 308) and error.headers["Location"] == "https://" + DOMAIN + "/"
        report["http_redirect"] = error.code
    try:
        urllib.request.urlopen("https://" + bucket + ".s3.us-west-1.amazonaws.com/index.html", timeout=30)
        raise AssertionError("Anonymous S3 object read succeeded")
    except urllib.error.HTTPError as error:
        assert error.code == 403
        report["anonymous_s3"] = error.code
    s3 = session.client("s3")
    report["public_access_block"] = s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
    assert all(report["public_access_block"].values())
    assert s3.get_bucket_policy_status(Bucket=bucket)["PolicyStatus"]["IsPublic"] is False
    head = s3.head_object(Bucket=bucket, Key="index.html")
    assert "text/html" in head["ContentType"]
    body = s3.get_object(Bucket=bucket, Key="index.html")["Body"].read()
    assert body == html
    report["s3_html_matches_https"] = True
    dist = session.client("cloudfront").get_distribution(Id=distribution)["Distribution"]
    assert dist["Status"] == "Deployed"
    assert dist["DistributionConfig"]["Aliases"]["Items"] == [DOMAIN]
    config = dist["DistributionConfig"]
    assert config["DefaultCacheBehavior"]["ViewerProtocolPolicy"] == "redirect-to-https"
    assert config["ViewerCertificate"]["MinimumProtocolVersion"] == "TLSv1.2_2021"
    origin = config["Origins"]["Items"][0]
    assert origin["DomainName"] == bucket + ".s3.us-west-1.amazonaws.com"
    oac = session.client("cloudfront").get_origin_access_control(Id=origin["OriginAccessControlId"])["OriginAccessControl"][
        "OriginAccessControlConfig"
    ]
    assert oac["SigningBehavior"] == "always" and oac["SigningProtocol"] == "sigv4"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
