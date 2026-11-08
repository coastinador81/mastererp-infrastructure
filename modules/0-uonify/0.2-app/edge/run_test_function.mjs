#!/usr/bin/env node
// run_test_function.mjs · Paso 13 del plan (lo lanza deploy_edge.mjs publish, o el CEO a mano, con el
// OK de la tanda AWS 5): prueba las dos funciones YA CREADAS en CloudFront con
// `aws cloudfront test-function`, con eventos SIN secretos y su resultado esperado. Solo lee y
// ejecuta: no escribe nada en AWS.
//
// ORDEN: se ejecuta DESPUÉS de que el dueño guarde las claves con set_gate_credentials.sh. Antes de
// los casos comprueba, y si algo falla aborta con exit 2 sin probar nada:
//  - que el KeyValueStore (uonify-dev-gate) está READY y tiene gate_cred_sha256 y gate_hmac_key.
//    Sin ellas, los casos de Basic y de cookie falsos darían el mismo 401 sin pasar nunca por el
//    SHA-256 ni por el HMAC, y un «todo OK» no probaría esos caminos;
//  - que las dos funciones son cloudfront-js-2.0 y están asociadas a ESE KeyValueStore (y a ningún otro);
//  - que el código de la etapa probada es idéntico, byte a byte, a gate-default.js y gate-api.js de
//    esta carpeta (lo que ha pasado test_gate.mjs).
// Con eso, los casos de Basic o cookie falsos fuerzan en el runtime real la lectura del KVS, el
// HMAC, el SHA-256 y atob. Los casos con credenciales buenas no se pueden probar aquí sin
// exponerlas: los cubre test_gate.mjs (offline) y la QA por la UI.
//
//   node run_test_function.mjs --default <función por defecto> --api <función /api/*> [--stage DEVELOPMENT|LIVE] [--kvs <nombre>]
// Sale con 1 si algún caso no da lo esperado o si la utilización de cómputo pasa de 70.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const names = { d: opt('--default'), a: opt('--api') };
const stage = opt('--stage', 'DEVELOPMENT');
const kvsName = opt('--kvs', 'uonify-dev-gate');
if (!names.d || !names.a || !['DEVELOPMENT', 'LIVE'].includes(stage) || !kvsName) {
  console.error('Uso: node run_test_function.mjs --default <nombre> --api <nombre> [--stage DEVELOPMENT|LIVE] [--kvs <nombre>]');
  process.exit(64);
}
const LOCAL = { d: path.join(HERE, 'gate-default.js'), a: path.join(HERE, 'gate-api.js') };
const KVS_KEYS = ['gate_cred_sha256', 'gate_hmac_key'];

const source = fs.readFileSync(LOCAL.d, 'utf8');
const rootPublic = /var ROOT_PUBLIC = true;/.test(source);
const nojs = /var LEGAL_NOJS = true;/.test(source);
const publicAsset = /var PUBLIC_ASSETS = '\|([^|]+)\|/.exec(source)[1];
const NAV = { 'sec-fetch-mode': 'navigate', 'sec-fetch-dest': 'document' };
const now = Math.floor(Date.now() / 1000);
const fakeCookie = 'v1.' + (now + 3600) + '.' + '0'.repeat(64);
const wrongBasic = 'Basic ' + Buffer.from('nadie:contrasena-que-no-es-1234').toString('base64');

function ev(method, url, h = {}, c = {}) {
  const [uri, q = ''] = url.split('?');
  const querystring = {};
  for (const kv of q ? q.split('&') : []) querystring[kv.split('=')[0]] = { value: kv.split('=')[1] || '' };
  const headers = { host: { value: 'dev.uonify.com' } };
  for (const [k, v] of Object.entries(h)) headers[k] = { value: v };
  const cookies = {};
  for (const [k, v] of Object.entries(c)) cookies[k] = { value: v };
  return { version: '1.0', context: { eventType: 'viewer-request' }, viewer: { ip: '198.51.100.10' }, request: { method, uri, querystring, headers, cookies } };
}

// [función, descripción, evento, esperado]  esperado: { uri } (petición) o { status, www?, body?, location? }
const cases = [
  ['d', '/privacidad sin cookie', ev('GET', '/privacidad', NAV), { uri: nojs ? '/privacidad/index.nojs.html' : '/privacidad/index.html' }],
  ['d', '/terminos/ sin cookie', ev('GET', '/terminos/', NAV), { uri: nojs ? '/terminos/index.nojs.html' : '/terminos/index.html' }],
  ['d', '/privacidad.html (enlace antiguo) sin cookie → 301', ev('GET', '/privacidad.html', NAV), { status: 301, www: false, location: '/privacidad' }],
  ['d', '/index.html?view=terminos (enlace antiguo) sin cookie → 301', ev('GET', '/index.html?view=terminos', NAV), { status: 301, www: false, location: '/terminos' }],
  ['d', 'asset público sin cookie', ev('GET', publicAsset, { 'sec-fetch-mode': 'no-cors', 'sec-fetch-dest': 'style' }), { uri: publicAsset }],
  ['d', '/web/ sin cookie', ev('GET', '/web/home-v22-propuesta/index.html', NAV), { uri: '/web/home-v22-propuesta/index.html' }],
  ['d', '«/» sin cookie', ev('GET', '/', NAV), rootPublic ? { uri: '/' } : { status: 401, www: true }],
  ['d', '/espacio navegación sin cookie', ev('GET', '/espacio', NAV), { status: 401, www: true }],
  ['d', '/espacio subrecurso sin cookie', ev('GET', '/espacio', { 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty' }), { status: 403, www: false }],
  ['d', 'un .js sin cookie', ev('GET', '/assets/cualquiera.js', { 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'script' }), { status: 403, www: false }],
  ['d', 'Basic incorrecto (KVS + SHA-256 + atob)', ev('GET', '/espacio', { ...NAV, authorization: wrongBasic }), { status: 401, www: true }],
  ['d', 'cookie falsa (KVS + HMAC)', ev('GET', '/espacio', NAV, { '__Host-uonify_gate': fakeCookie }), { status: 401, www: true }],
  ['d', '?auth=return sin cookie', ev('GET', '/?auth=return', NAV), { status: 401, www: true }],
  ['a', 'GET /api/health', ev('GET', '/api/health', { authorization: wrongBasic }), { uri: '/api/health' }],
  ['a', 'POST webhook de Stripe', ev('POST', '/api/billing/stripe/webhook', { 'stripe-signature': 't=1,v1=x' }), { uri: '/api/billing/stripe/webhook' }],
  ['a', '/api/auth/session sin cookie', ev('GET', '/api/auth/session'), { status: 401, www: false, body: '{"error":"gate_required"}' }],
  ['a', 'WebSocket /api/uony/live sin cookie', ev('GET', '/api/uony/live', { origin: 'https://dev.uonify.com', 'sec-websocket-key': 'dGhlIHNhbXBsZSBub25jZQ==', 'sec-websocket-version': '13', authorization: wrongBasic }), { status: 401, www: false, body: '{"error":"gate_required"}' }],
  ['a', 'cookie falsa en /api (KVS + HMAC)', ev('GET', '/api/auth/session', {}, { '__Host-uonify_gate': fakeCookie }), { status: 401, www: false, body: '{"error":"gate_required"}' }],
];

class Precheck extends Error {}

function aws(cliArgs) {
  const r = spawnSync('aws', cliArgs, { encoding: 'utf8', env: { ...process.env, AWS_PAGER: '' }, maxBuffer: 16 << 20 });
  if (r.error) throw new Error(`no puedo ejecutar la AWS CLI (${r.error.code})`);
  if (r.status !== 0) throw new Error(((r.stderr || '').match(/An error occurred \([A-Za-z0-9]+\)[^\n]*/) || ['aws ' + cliArgs[1] + ' ha fallado'])[0]);
  return r.stdout;
}
const awsJson = (cliArgs) => JSON.parse(aws([...cliArgs, '--output', 'json']));
const sha256 = (buf) => crypto.createHash('sha256').update(buf).digest('hex');

// Comprobaciones previas: devuelve los ETag de la etapa probada.
function preflight(work) {
  let kvs;
  try {
    kvs = awsJson(['cloudfront', 'describe-key-value-store', '--name', kvsName]).KeyValueStore;
  } catch (error) {
    throw new Precheck(`no encuentro el KeyValueStore «${kvsName}» (${error.message})`);
  }
  if (kvs.Status !== 'READY') throw new Precheck(`el KeyValueStore «${kvsName}» está ${kvs.Status}, no READY`);
  // Solo los nombres de las claves (la consulta filtra en la CLI: los valores nunca llegan aquí).
  const keys = awsJson(['cloudfront-keyvaluestore', 'list-keys', '--kvs-arn', kvs.ARN, '--region', 'us-east-1', '--query', 'Items[].Key']) || [];
  const missing = KVS_KEYS.filter((k) => !keys.includes(k));
  if (missing.length) throw new Precheck(`faltan en el KeyValueStore: ${missing.join(', ')}. Primero el dueño ejecuta ./set_gate_credentials.sh (y --check); sin ellas este test no probaría el HMAC ni el SHA-256`);
  console.log(`OK    KeyValueStore ${kvsName} READY con ${KVS_KEYS.join(' y ')}`);
  const etags = {};
  for (const k of ['d', 'a']) {
    const d = awsJson(['cloudfront', 'describe-function', '--name', names[k], '--stage', stage]);
    const cfg = d.FunctionSummary.FunctionConfig;
    if (cfg.Runtime !== 'cloudfront-js-2.0') throw new Precheck(`${names[k]} (${stage}) usa ${cfg.Runtime}, no cloudfront-js-2.0`);
    const arns = ((cfg.KeyValueStoreAssociations && cfg.KeyValueStoreAssociations.Items) || []).map((i) => i.KeyValueStoreARN);
    if (arns.length !== 1 || arns[0] !== kvs.ARN) throw new Precheck(`${names[k]} (${stage}) no está asociada solo al KeyValueStore «${kvsName}»`);
    const file = path.join(work, `codigo-${k}.js`);
    aws(['cloudfront', 'get-function', '--name', names[k], '--stage', stage, file]);
    if (sha256(fs.readFileSync(file)) !== sha256(fs.readFileSync(LOCAL[k]))) {
      throw new Precheck(`el código de ${names[k]} en ${stage} no es ${path.basename(LOCAL[k])} de esta carpeta: súbelo (deploy_edge.mjs functions) antes de probar`);
    }
    console.log(`OK    ${names[k]} (${stage}): cloudfront-js-2.0, asociada a ${kvsName}, código = ${path.basename(LOCAL[k])}`);
    etags[k] = d.ETag;
  }
  return etags;
}

const work = fs.mkdtempSync(path.join(os.tmpdir(), 'uonify-tf-'));
let failed = 0;
try {
  let etags;
  try {
    etags = preflight(work);
  } catch (error) {
    console.error(`ERROR: ${error.message}. No se ha probado ningún caso.`);
    process.exitCode = 2;
  }
  if (etags) {
    cases.forEach(([k, label, event, want], i) => {
      const file = path.join(work, `evento-${i}.json`);
      fs.writeFileSync(file, JSON.stringify(event));
      let line;
      try {
        const result = awsJson(['cloudfront', 'test-function', '--name', names[k], '--if-match', etags[k], '--stage', stage, '--event-object', 'fileb://' + file]).TestResult;
        if (result.FunctionErrorMessage) throw new Error('error de la función: ' + result.FunctionErrorMessage);
        const parsed = JSON.parse(result.FunctionOutput);
        const out = parsed.response || parsed.request || parsed;
        const utilization = Number(result.ComputeUtilization);
        const problems = [];
        if (want.uri !== undefined) {
          if (out.statusCode !== undefined || out.uri !== want.uri) problems.push(`esperaba la petición a ${want.uri}`);
          if (out.headers && out.headers.authorization) problems.push('Authorization no borrada');
        } else {
          if (out.statusCode !== want.status) problems.push(`esperaba ${want.status}, llega ${out.statusCode === undefined ? 'la petición' : out.statusCode}`);
          const www = !!(out.headers && out.headers['www-authenticate']);
          if (www !== want.www) problems.push(want.www ? 'falta WWW-Authenticate' : 'sobra WWW-Authenticate');
          const body = out.body && (out.body.data !== undefined ? out.body.data : out.body);
          if (want.body !== undefined && body !== undefined && body !== want.body) problems.push('cuerpo distinto');
          const location = out.headers && out.headers.location && out.headers.location.value;
          if (want.location !== undefined && location !== want.location) problems.push(`Location ${location} en vez de ${want.location}`);
        }
        if (utilization > 70) problems.push(`utilización de cómputo ${utilization} > 70`);
        line = `${problems.length ? 'FALLO' : 'OK   '} [${names[k]}] ${label} · cómputo ${utilization}${problems.length ? ' · ' + problems.join('; ') : ''}`;
        if (problems.length) failed += 1;
      } catch (error) {
        failed += 1;
        line = `FALLO [${names[k]}] ${label} · ${error.message}`;
      }
      console.log(line);
    });
    console.log(`\n${cases.length - failed}/${cases.length} casos OK en ${stage}`);
    process.exitCode = failed ? 1 : 0;
  }
} finally {
  fs.rmSync(work, { recursive: true, force: true });
}
