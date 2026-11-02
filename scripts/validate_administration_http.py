"""Verify public technical health routes; no credentials or tokens used."""
import argparse
import json
from pathlib import Path
import urllib.error
import urllib.request

API = 'https://qx8nmypdhi.execute-api.us-west-1.amazonaws.com'


def request(path, method='GET', origin=None):
    headers = {}
    if origin:
        headers = {'Origin': origin, 'Access-Control-Request-Method': 'GET',
                   'Access-Control-Request-Headers': 'authorization'}
    req = urllib.request.Request(API + path, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    raw = response.read()
    return response.code, {k.lower(): v for k,v in response.headers.items()}, json.loads(raw) if raw else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    owners = json.loads((Path(__file__).parent/'administration_lambdas.json').read_text())
    results = []
    for cap in owners:
        path = '/v1/administration/' + cap + '/health'
        code, headers, body = request(path)
        checks = [{'case': 'public_no_token', 'http': code, 'passed': code == 200 and
                   body == {'status': 'ok', 'lambda': 'mastererp-dev-adm-' + cap} and
                   headers.get('cache-control') == 'no-store'}]
        code, headers, _ = request(path, method='OPTIONS', origin='https://admin.dev.mastererp.local')
        checks.append({'case': 'existing_cors_preflight', 'http': code, 'passed': code == 204 and
                       headers.get('access-control-allow-origin') == 'https://admin.dev.mastererp.local' and
                       'GET' in headers.get('access-control-allow-methods', '')})
        results.append({'capability': cap, 'url': API + path, 'checks': checks})
    report = {'api_id': 'qx8nmypdhi', 'api_owner_stack': 'mastererp-dev-onboarding',
              'integration_stack': 'mastererp-dev-administration', 'authentication': 'NONE',
              'decision': 'Owner requested public technical health routes; JWT deferred',
              'business_capabilities_implemented': False, 'results': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    if not all(c['passed'] for r in results for c in r['checks']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
