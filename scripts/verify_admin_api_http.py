"""Real DEV health/JWT/CORS probes. Credentials stay in memory; no business writes."""
import argparse
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request
import boto3

API='https://qx8nmypdhi.execute-api.us-west-1.amazonaws.com'
ORIGIN='https://app-dev.uonify.com'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--platform',type=Path,required=True)
    p.add_argument('--profile',default='andrea_madriz_mastererp')
    args=p.parse_args();results=[]
    sys.path.insert(0,str(args.platform.resolve()/'scripts'))
    import identity_qa_client as qa
    session=boto3.Session(profile_name=args.profile,region_name='us-west-1')
    assert session.client('sts').get_caller_identity()['Account']=='277352717693'
    bundle=json.loads(session.client('secretsmanager').get_secret_value(SecretId='mastererp/dev/qa/identity-validation')['SecretString'])
    id_token=qa.tokens(bundle['actors']['admin_a'])['id_token']
    def request(path,method='GET',token=None,origin=ORIGIN):
        headers={'Origin':origin}
        if token:headers['Authorization']='Bearer '+token
        if method=='OPTIONS':headers.update({'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type,idempotency-key,x-mastererp-tenant-id,x-tenant-id'})
        try:r=urllib.request.urlopen(urllib.request.Request(API+path,method=method,headers=headers),timeout=30)
        except urllib.error.HTTPError as e:r=e
        body=r.read();return r.status,{k.lower():v for k,v in r.headers.items()},json.loads(body) if body else {}
    def check(name,actual,expected,condition=True):
        results.append({'case':name,'http':actual,'expected':expected,'result':'passed' if actual==expected and condition else 'failed'})
    for cap in ['clientes','ventas','proveedores','compras','cartera','tesoreria','conciliacion','gastos']:
        status,_,body=request('/v1/administration/'+cap+'/health')
        check('health_'+cap,status,200,body.get('lambda')=='mastererp-dev-adm-'+cap)
    for cap in ('clientes','proveedores'):
        base='/v1/administration/'+cap
        status,_,_=request(base);check(cap+'_no_token',status,401)
        status,_,_=request(base,token='invalid');check(cap+'_invalid_token',status,401)
        status,_,_=request(base,token=id_token);check(cap+'_id_token_rejected',status,403)
        status,headers,_=request(base,method='OPTIONS')
        allowed={x.strip().lower() for x in headers.get('access-control-allow-headers','').split(',')}
        methods={x.strip().upper() for x in headers.get('access-control-allow-methods','').split(',')}
        check(cap+'_preflight',status,204,headers.get('access-control-allow-origin')==ORIGIN
              and {'authorization','content-type','idempotency-key','x-mastererp-tenant-id','x-tenant-id'}<=allowed
              and {'GET','POST','PATCH','OPTIONS'}<=methods)
        status,headers,_=request(base,method='OPTIONS',origin='https://untrusted.invalid')
        check(cap+'_foreign_origin_not_allowed',status,204,'access-control-allow-origin' not in headers)
    report={'environment':'DEV us-west-1','results':results,'status':'passed' if all(x['result']=='passed' for x in results) else 'failed'}
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
