#!/usr/bin/env node
// deploy_edge.mjs · Paso 13 del plan (Tanda AWS 5): el borde de https://dev.uonify.com en CloudFront.
// Lo ejecuta el CEO con el OK del dueño en el chat. Las fases con escrituras exigen --apply; sin él
// solo leen y enseñan lo que harían. Orden:
//   1. node deploy_edge.mjs plan                    estado y cambios previstos (solo lectura)
//   2. node deploy_edge.mjs functions --apply       KVS uonify-dev-gate y las 2 funciones en DEVELOPMENT
//                                                   (antes pasa test_gate.mjs); nada llega aún al tráfico
//   3. EL DUEÑO: ./set_gate_credentials.sh  y después  ./set_gate_credentials.sh --check
//   4. node deploy_edge.mjs publish --apply         run_test_function.mjs en DEVELOPMENT (exige las 2
//                                                   claves del KVS y el código de esta carpeta) y, si
//                                                   todo da OK, publica las 2 funciones en LIVE
//   5. node deploy_edge.mjs distribution --apply    E4N1UCPZZ2F0: origen origin-dev, /api/* y las dos
//                                                   funciones; copia previa SIN secretos; espera al
//                                                   despliegue y ejecuta verify
//   6. paso 15, tras subir el dist: node deploy_edge.mjs legal --apply  y  node deploy_edge.mjs verify
// Otras: backup [--out f] · rollback --from f [--apply] · verify [--base-url u] [--http-url u|off]
//
// Contrato con nginx (runtime/nginx.conf): /api/* va a origin-dev.uonify.com:443 en https-only con
// TLSv1.2; SNI y Host = origin-dev (Managed-AllViewerExceptHostHeader: reenvía las demás cabeceras,
// las cookies y la query del visor, Sec-WebSocket-* incluidas); sin caché (Managed-CachingDisabled);
// lectura 60 s y keep-alive 60 s (< 75 s de nginx); 7 métodos; https-only también para el visor; y la
// cabecera de origen X-Origin-Verify con el valor de SSM /uonify/dev/edge/origin-verify (eu-west-1).
// Con 2 líneas en SSM (rotación: actual + nueva) pone la ÚLTIMA; nginx acepta las dos mientras tanto.
//
// El secreto de borde va de la AWS CLI a la memoria de este proceso y de ahí a un fichero 0600, en un
// directorio 0700 que se borra al salir: nunca a argv, a la pantalla, a una copia ni a un log.
// get-distribution-config devuelve esa cabecera EN CLARO: este script solo guarda copias con las
// cabeceras de origen en blanco. Después del paso 13, NO ejecutar get-distribution-config a mano sin
// --query ETag; para copiar o restaurar, usar backup y rollback.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import https from 'node:https';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ACCOUNT = '277352717693';
const DIST_ID = 'E4N1UCPZZ2F0';
const ALIAS = 'dev.uonify.com';
const BUCKET = 'uonify-dev-web-277352717693';
const KVS_NAME = 'uonify-dev-gate';
const KVS_KEYS = ['gate_cred_sha256', 'gate_hmac_key'];
const FUNCTIONS = {
  default: { name: 'uonify-dev-gate-default', file: 'gate-default.js', comment: 'dev.uonify.com gate and rewrites (default behavior)' },
  api: { name: 'uonify-dev-gate-api', file: 'gate-api.js', comment: 'dev.uonify.com gate for /api/* and the voice WebSocket' },
};
const ORIGIN_ID = 'uonify-dev-origin';
const ORIGIN_DOMAIN = 'origin-dev.uonify.com';
const EDGE_PARAM = '/uonify/dev/edge/origin-verify';
const EDGE_REGION = 'eu-west-1';
const EDGE_HEADER = 'X-Origin-Verify';
const EDGE_RE = /^[A-Za-z0-9_-]{32,256}$/; // el formato que acepta uonify_secrets_render.py
const API_PATH = '/api/*';
const API_METHODS = ['GET', 'HEAD', 'OPTIONS', 'PUT', 'POST', 'PATCH', 'DELETE'];
const POLICIES = {
  cache: ['Managed-CachingDisabled', '4135ea2d-6df8-44a3-9df3-4b5a84be39ad'],
  origin: ['Managed-AllViewerExceptHostHeader', 'b689b0a8-53d0-40ab-baf2-68738e2966ac'],
};
// Cabeceras de seguridad para el visor (revisión adversaria del 08-11, SEG-F2): HSTS de 1 año SIN
// includeSubDomains (otros equipos usan subdominios de uonify.com), nosniff, sin marcos (el backend ya
// manda X-Frame-Options DENY en /api) y noindex (DEV no se indexa). Política propia, buscada por nombre.
const HEADERS_POLICY_NAME = 'uonify-dev-security-headers';
const HSTS_MAX_AGE = 31536000;
const HEADERS_POLICY_PENDING = '«se crea con --apply»';
const headersPolicyConfig = () => ({
  Name: HEADERS_POLICY_NAME,
  Comment: 'dev.uonify.com: HSTS 31536000 s sin subdominios, nosniff, sin marcos y noindex',
  SecurityHeadersConfig: {
    StrictTransportSecurity: { Override: true, IncludeSubdomains: false, Preload: false, AccessControlMaxAgeSec: HSTS_MAX_AGE },
    ContentTypeOptions: { Override: true },
    FrameOptions: { Override: true, FrameOption: 'DENY' },
  },
  CustomHeadersConfig: { Quantity: 1, Items: [{ Header: 'X-Robots-Tag', Value: 'noindex, nofollow', Override: true }] },
});
const REDACTED = '__REDACTED__ ver SSM ' + EDGE_PARAM;
const LEGAL_PAGES = ['privacidad', 'terminos'];
const MAX_FUNCTION_BYTES = 10240;
const POLL_MS = Number(process.env.EDGE_POLL_MS || 5000);

const argv = process.argv.slice(2);
const cmd = argv[0];
const flag = (name) => argv.includes(name);
const opt = (name, fallback) => {
  const i = argv.indexOf(name);
  return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : fallback;
};
const APPLY = flag('--apply');

// ── salida: ningún valor de SECRETS puede salir, pase lo que pase ────────────
const SECRETS = new Set();
function scrub(text) {
  let s = String(text);
  for (const v of SECRETS) if (v) s = s.split(v).join('«secreto»');
  return s;
}
const say = (message = '') => process.stdout.write(scrub(message) + '\n');
class Fatal extends Error {}
class AwsError extends Fatal {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}
const fatal = (message) => {
  throw new Fatal(message);
};

// ── directorio privado (0700) que se borra siempre ───────────────────────────
let WORK = null;
function work() {
  if (!WORK) {
    WORK = fs.mkdtempSync(path.join(os.tmpdir(), 'uonify-edge-'));
    fs.chmodSync(WORK, 0o700);
  }
  return WORK;
}
function cleanup() {
  if (WORK) fs.rmSync(WORK, { recursive: true, force: true });
  WORK = null;
}
process.on('exit', cleanup);
for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(signal, () => {
  cleanup();
  process.exit(130);
});
function writePrivate(name, text) {
  const file = path.join(work(), `${crypto.randomBytes(6).toString('hex')}-${name}`);
  fs.writeFileSync(file, text, { mode: 0o600, flag: 'wx' });
  return file;
}

// ── AWS CLI: la salida se queda en memoria; de los errores solo sale el código y una línea ──
const AWS_ENV = { ...process.env, AWS_PAGER: '' };
function aws(args, { json = true } = {}) {
  const r = spawnSync('aws', json ? [...args, '--output', 'json'] : args, { encoding: 'utf8', env: AWS_ENV, maxBuffer: 64 << 20 });
  if (r.error) fatal(`no puedo ejecutar la AWS CLI (${r.error.code})`);
  if (r.status !== 0) {
    const m = /An error occurred \(([^)]+)\)[^:\n]*:?[ \t]*([^\n]*)/.exec(r.stderr || '');
    const code = m ? m[1] : `exit ${r.status}`;
    const detail = (m ? m[2] : (r.stderr || '').trim().split('\n')[0] || '').slice(0, 240);
    throw new AwsError(code, `aws ${args[0]} ${args[1]}: ${code}${detail ? ' · ' + detail : ''}`);
  }
  if (!json) return r.stdout.trim();
  return r.stdout.trim() ? JSON.parse(r.stdout) : null;
}
const sha = (buf) => crypto.createHash('sha256').update(buf).digest('hex');
const clone = (value) => JSON.parse(JSON.stringify(value));
const items = (list) => (list && list.Items) || [];
const sleep = (ms) => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
const gateSource = () => fs.readFileSync(path.join(HERE, FUNCTIONS.default.file), 'utf8');

let accountChecked = false;
function checkAccount() {
  if (accountChecked) return;
  const id = aws(['sts', 'get-caller-identity', '--region', 'us-east-1']);
  if (id.Account !== ACCOUNT) fatal(`la AWS CLI apunta a la cuenta ${id.Account}, no a ${ACCOUNT}: revisa AWS_PROFILE`);
  say(`Cuenta ${id.Account} · ${id.Arn}`);
  accountChecked = true;
}

// ── KeyValueStore y funciones ────────────────────────────────────────────────
function kvsInfo() {
  try {
    return aws(['cloudfront', 'describe-key-value-store', '--name', KVS_NAME]).KeyValueStore;
  } catch (error) {
    if (error.code === 'EntityNotFound') return null;
    throw error;
  }
}
function waitKvsReady() {
  for (let i = 0; i < 60; i += 1) {
    const kvs = kvsInfo();
    if (kvs && kvs.Status === 'READY') return kvs;
    sleep(POLL_MS);
  }
  return fatal(`el KeyValueStore ${KVS_NAME} no llega a READY`);
}
function kvsKeys(arn) {
  // Solo los nombres: la consulta se filtra en la CLI y los valores nunca llegan a este proceso.
  return aws(['cloudfront-keyvaluestore', 'list-keys', '--kvs-arn', arn, '--region', 'us-east-1', '--query', 'Items[].Key']) || [];
}
function describeFunction(name, stage) {
  try {
    return aws(['cloudfront', 'describe-function', '--name', name, '--stage', stage]);
  } catch (error) {
    if (error.code === 'NoSuchFunctionExists') return null;
    throw error;
  }
}
function deployedCode(name, stage) {
  const file = path.join(work(), `${crypto.randomBytes(6).toString('hex')}-${name}-${stage}.js`);
  aws(['cloudfront', 'get-function', '--name', name, '--stage', stage, file], { json: false });
  const code = fs.readFileSync(file);
  fs.rmSync(file, { force: true });
  return code;
}
function localCode(fn) {
  const code = fs.readFileSync(path.join(HERE, fn.file));
  if (code.length > MAX_FUNCTION_BYTES) fatal(`${fn.file} ocupa ${code.length} bytes (límite ${MAX_FUNCTION_BYTES})`);
  return code;
}
function functionConfig(fn, kvsArn) {
  return { Comment: fn.comment, Runtime: 'cloudfront-js-2.0', KeyValueStoreAssociations: { Quantity: 1, Items: [{ KeyValueStoreARN: kvsArn }] } };
}
function sameConfig(a, b) {
  const arns = (c) => items(c.KeyValueStoreAssociations).map((i) => i.KeyValueStoreARN).join(',');
  return a.Runtime === b.Runtime && a.Comment === b.Comment && arns(a) === arns(b);
}
function runBench() {
  if (flag('--skip-bench')) {
    say('AVISO: --skip-bench: NO se ha pasado el banco offline test_gate.mjs');
    return;
  }
  const bench = process.env.EDGE_BENCH || path.join(HERE, 'test_gate.mjs');
  const r = spawnSync(process.execPath, [bench], { encoding: 'utf8', env: process.env, maxBuffer: 64 << 20 });
  const last = (r.stdout || '').trim().split('\n').pop() || `exit ${r.status}`;
  if (r.status !== 0) fatal(`el banco offline test_gate.mjs no pasa (${last}): no se sube nada`);
  say(`OK  banco offline: ${last}`);
}

function phaseFunctions() {
  checkAccount();
  runBench();
  let kvs = kvsInfo();
  if (!kvs) {
    if (!APPLY) say(`+ KeyValueStore ${KVS_NAME}: se creará vacío`);
    else {
      aws(['cloudfront', 'create-key-value-store', '--name', KVS_NAME, '--comment', 'dev.uonify.com gate: credential hash and cookie HMAC key (set_gate_credentials.sh)']);
      kvs = waitKvsReady();
      say(`+ KeyValueStore ${KVS_NAME} creado (READY, vacío)`);
    }
  } else if (kvs.Status !== 'READY') {
    if (APPLY) kvs = waitKvsReady();
    say(`= KeyValueStore ${KVS_NAME}: ${kvs.Status}`);
  } else say(`= KeyValueStore ${KVS_NAME}: READY`);
  for (const fn of Object.values(FUNCTIONS)) {
    const code = localCode(fn);
    const config = functionConfig(fn, kvs ? kvs.ARN : 'pendiente');
    const createArgs = ['--function-config', JSON.stringify(config), '--function-code', 'fileb://' + path.join(HERE, fn.file)];
    const dev = describeFunction(fn.name, 'DEVELOPMENT');
    if (!dev) {
      if (!APPLY) say(`+ ${fn.name}: se creará en DEVELOPMENT (${code.length} B, cloudfront-js-2.0, KVS ${KVS_NAME})`);
      else {
        aws(['cloudfront', 'create-function', '--name', fn.name, ...createArgs]);
        say(`+ ${fn.name}: creada en DEVELOPMENT (${code.length} B)`);
      }
      continue;
    }
    const same = sha(deployedCode(fn.name, 'DEVELOPMENT')) === sha(code) && sameConfig(dev.FunctionSummary.FunctionConfig, config);
    if (same) say(`= ${fn.name}: DEVELOPMENT ya tiene ${fn.file} y esta configuración`);
    else if (!APPLY) say(`~ ${fn.name}: se actualizará DEVELOPMENT con ${fn.file} (${code.length} B)`);
    else {
      aws(['cloudfront', 'update-function', '--name', fn.name, '--if-match', dev.ETag, ...createArgs]);
      say(`~ ${fn.name}: DEVELOPMENT actualizada con ${fn.file}`);
    }
  }
  if (!APPLY) say('\n(simulación: con --apply se aplica)');
  else say('\nSiguiente: el dueño ejecuta ./set_gate_credentials.sh (y --check); después, publish --apply.');
  return 0;
}

function phasePublish() {
  checkAccount();
  const kvs = kvsInfo();
  if (!kvs || kvs.Status !== 'READY') fatal(`el KeyValueStore ${KVS_NAME} no está READY: antes, functions --apply`);
  say('test-function en DEVELOPMENT (run_test_function.mjs):');
  const r = spawnSync(process.execPath, [path.join(HERE, 'run_test_function.mjs'), '--default', FUNCTIONS.default.name, '--api', FUNCTIONS.api.name,
    '--stage', 'DEVELOPMENT', '--kvs', KVS_NAME], { encoding: 'utf8', env: AWS_ENV, maxBuffer: 16 << 20 });
  process.stdout.write(scrub(r.stdout || ''));
  process.stdout.write(scrub(r.stderr || ''));
  if (r.status !== 0) fatal('test-function no ha dado todo OK: no se publica nada');
  for (const fn of Object.values(FUNCTIONS)) {
    const dev = describeFunction(fn.name, 'DEVELOPMENT');
    if (!dev || sha(deployedCode(fn.name, 'DEVELOPMENT')) !== sha(localCode(fn))) fatal(`${fn.name}: DEVELOPMENT ha cambiado tras el test: no se publica`);
    const live = describeFunction(fn.name, 'LIVE');
    if (live && sha(deployedCode(fn.name, 'LIVE')) === sha(localCode(fn)) && sameConfig(live.FunctionSummary.FunctionConfig, dev.FunctionSummary.FunctionConfig)) {
      say(`= ${fn.name}: LIVE ya es ${fn.file}`);
      continue;
    }
    if (!APPLY) {
      say(`~ ${fn.name}: se publicará DEVELOPMENT → LIVE`);
      continue;
    }
    aws(['cloudfront', 'publish-function', '--name', fn.name, '--if-match', dev.ETag]);
    if (sha(deployedCode(fn.name, 'LIVE')) !== sha(localCode(fn))) fatal(`${fn.name}: LIVE no coincide con ${fn.file} tras publicar`);
    say(`+ ${fn.name}: publicada en LIVE (si ya está asociada a la distribución, el cambio llega al tráfico ahora)`);
  }
  if (!APPLY) say('\n(simulación: con --apply se publica)');
  return 0;
}

// ── distribución ─────────────────────────────────────────────────────────────
function headerValues(cfg) {
  return items(cfg.Origins).flatMap((o) => items(o.CustomHeaders).map((h) => h.HeaderValue));
}
function getConfig() {
  // La respuesta lleva las cabeceras de origen EN CLARO: solo en memoria, y sus valores a SECRETS.
  const r = aws(['cloudfront', 'get-distribution-config', '--id', DIST_ID]);
  for (const v of headerValues(r.DistributionConfig)) SECRETS.add(v);
  return { etag: r.ETag, config: r.DistributionConfig };
}
function edgeSecret() {
  let p;
  try {
    p = aws(['ssm', 'get-parameter', '--region', EDGE_REGION, '--name', EDGE_PARAM, '--with-decryption']).Parameter;
  } catch (error) {
    if (error.code === 'ParameterNotFound') fatal(`no existe ${EDGE_PARAM} en SSM (${EDGE_REGION}): el dueño lo crea con upload_dev_secrets.sh --with-edge-secret`);
    throw error;
  }
  const lines = String(p.Value).split('\n').map((l) => l.replace(/\r$/, '')).filter((l) => l.trim());
  for (const l of lines) SECRETS.add(l);
  if (p.Type !== 'SecureString') fatal(`${EDGE_PARAM} no es SecureString`);
  if (lines.length < 1 || lines.length > 2 || !lines.every((l) => EDGE_RE.test(l))) fatal(`${EDGE_PARAM} no tiene el formato esperado (1 o 2 líneas [A-Za-z0-9_-]{32,256})`);
  return { value: lines[lines.length - 1], all: lines, version: p.Version };
}
function managedPolicies() {
  const cache = items(aws(['cloudfront', 'list-cache-policies', '--type', 'managed']).CachePolicyList).find((i) => i.CachePolicy.CachePolicyConfig.Name === POLICIES.cache[0]);
  const origin = items(aws(['cloudfront', 'list-origin-request-policies', '--type', 'managed']).OriginRequestPolicyList)
    .find((i) => i.OriginRequestPolicy.OriginRequestPolicyConfig.Name === POLICIES.origin[0]);
  if (!cache || cache.CachePolicy.Id !== POLICIES.cache[1]) fatal(`la política gestionada ${POLICIES.cache[0]} no tiene el id esperado ${POLICIES.cache[1]}`);
  if (!origin || origin.OriginRequestPolicy.Id !== POLICIES.origin[1]) fatal(`la política gestionada ${POLICIES.origin[0]} no tiene el id esperado ${POLICIES.origin[1]}`);
  return { cache: POLICIES.cache[1], origin: POLICIES.origin[1] };
}
function headersPolicyMatches(c) {
  const sec = (c && c.SecurityHeadersConfig) || {};
  const sts = sec.StrictTransportSecurity || {};
  const custom = items(c && c.CustomHeadersConfig);
  return sts.Override === true && sts.IncludeSubdomains === false && !sts.Preload && sts.AccessControlMaxAgeSec === HSTS_MAX_AGE
    && !!sec.ContentTypeOptions && sec.ContentTypeOptions.Override === true
    && !!sec.FrameOptions && sec.FrameOptions.Override === true && sec.FrameOptions.FrameOption === 'DENY'
    && custom.length === 1 && custom[0].Header === 'X-Robots-Tag' && custom[0].Value === 'noindex, nofollow' && custom[0].Override === true
    && !c.CorsConfig && items(c.RemoveHeadersConfig).length === 0;
}
// Devuelve el id de la política propia. Sin --apply no crea nada (marca «se crea con --apply»). Si la
// distribución ya tiene OTRA política o la propia no es la esperada, falla cerrada. Si después falla
// update-distribution, la política queda creada y sin usar: la siguiente ejecución la reutiliza.
function ensureHeadersPolicy(cfg) {
  const found = items(aws(['cloudfront', 'list-response-headers-policies', '--type', 'custom']).ResponseHeadersPolicyList)
    .map((i) => i.ResponseHeadersPolicy)
    .filter((p) => p && p.ResponseHeadersPolicyConfig && p.ResponseHeadersPolicyConfig.Name === HEADERS_POLICY_NAME);
  if (found.length > 1) fatal(`hay ${found.length} políticas de cabeceras llamadas ${HEADERS_POLICY_NAME}: no se toca nada`);
  const mine = found[0];
  for (const b of [cfg.DefaultCacheBehavior, ...items(cfg.CacheBehaviors)]) {
    if (b.ResponseHeadersPolicyId && (!mine || b.ResponseHeadersPolicyId !== mine.Id)) {
      fatal(`${b.PathPattern ? 'el comportamiento ' + b.PathPattern : 'el comportamiento por defecto'} ya tiene otra política de cabeceras (${b.ResponseHeadersPolicyId}): no se toca nada`);
    }
  }
  if (mine) {
    if (!headersPolicyMatches(mine.ResponseHeadersPolicyConfig)) fatal(`la política de cabeceras ${HEADERS_POLICY_NAME} (${mine.Id}) existe pero no es la esperada: no se cambia sola, revísala a mano`);
    return mine.Id;
  }
  if (!APPLY) return HEADERS_POLICY_PENDING;
  const file = writePrivate('headers-policy.json', JSON.stringify(headersPolicyConfig()));
  try {
    const r = aws(['cloudfront', 'create-response-headers-policy', '--response-headers-policy-config', 'file://' + file]);
    say(`+ política de cabeceras ${HEADERS_POLICY_NAME} creada (${r.ResponseHeadersPolicy.Id})`);
    return r.ResponseHeadersPolicy.Id;
  } finally {
    fs.rmSync(file, { force: true });
  }
}
function liveFunctions() {
  const arns = {};
  for (const [k, fn] of Object.entries(FUNCTIONS)) {
    const live = describeFunction(fn.name, 'LIVE');
    if (!live) fatal(`${fn.name} no está publicada en LIVE: antes, publish --apply`);
    if (sha(deployedCode(fn.name, 'LIVE')) !== sha(localCode(fn))) fatal(`el código LIVE de ${fn.name} no es ${fn.file} de esta carpeta: antes, functions --apply y publish --apply`);
    arns[k] = live.FunctionSummary.FunctionMetadata.FunctionARN;
  }
  return arns;
}
function checkConfig(cfg) {
  const problems = [];
  if (!items(cfg.Aliases).includes(ALIAS)) problems.push(`no sirve ${ALIAS}`);
  if (cfg.CustomErrorResponses && cfg.CustomErrorResponses.Quantity > 0) problems.push('tiene respuestas de error personalizadas: convertirían los errores JSON de /api en HTML (quitarlas antes)');
  if (cfg.Staging || cfg.ContinuousDeploymentPolicyId) problems.push('está en despliegue continuo o es staging');
  if (cfg.OriginGroups && cfg.OriginGroups.Quantity > 0) problems.push('tiene grupos de origen');
  const d = cfg.DefaultCacheBehavior;
  const s3 = items(cfg.Origins).find((o) => o.Id === d.TargetOriginId);
  if (!s3 || !String(s3.DomainName).startsWith(BUCKET + '.s3.')) problems.push(`el comportamiento por defecto no va al bucket ${BUCKET}`);
  for (const o of items(cfg.Origins)) {
    if (o === s3) continue;
    if (o.Id !== ORIGIN_ID) problems.push(`origen inesperado «${o.Id}»`);
    else if (o.DomainName !== ORIGIN_DOMAIN) problems.push(`el origen ${ORIGIN_ID} apunta a ${o.DomainName}`);
  }
  for (const b of items(cfg.CacheBehaviors)) if (b.PathPattern !== API_PATH) problems.push(`comportamiento inesperado «${b.PathPattern}»`);
  if (d.LambdaFunctionAssociations && d.LambdaFunctionAssociations.Quantity > 0) problems.push('el comportamiento por defecto tiene Lambda@Edge');
  if (problems.length) fatal(`${DIST_ID} no está como se espera; no se toca nada:\n  - ${problems.join('\n  - ')}`);
}
function buildConfig(cfg, live, policies, headerValue, headersPolicyId) {
  const next = clone(cfg);
  const origin = {
    Id: ORIGIN_ID,
    DomainName: ORIGIN_DOMAIN,
    OriginPath: '',
    CustomHeaders: { Quantity: 1, Items: [{ HeaderName: EDGE_HEADER, HeaderValue: headerValue }] },
    CustomOriginConfig: {
      HTTPPort: 80,
      HTTPSPort: 443,
      OriginProtocolPolicy: 'https-only',
      OriginSslProtocols: { Quantity: 1, Items: ['TLSv1.2'] },
      OriginReadTimeout: 60,
      OriginKeepaliveTimeout: 60,
    },
    ConnectionAttempts: 3,
    ConnectionTimeout: 10,
    OriginShield: { Enabled: false },
    OriginAccessControlId: '',
  };
  const origins = items(next.Origins);
  const i = origins.findIndex((o) => o.Id === ORIGIN_ID);
  if (i < 0) origins.push(origin);
  else origins[i] = { ...origins[i], ...origin, CustomOriginConfig: { ...origins[i].CustomOriginConfig, ...origin.CustomOriginConfig } };
  next.Origins = { Quantity: origins.length, Items: origins };

  const behavior = {
    PathPattern: API_PATH,
    TargetOriginId: ORIGIN_ID,
    TrustedSigners: { Enabled: false, Quantity: 0 },
    TrustedKeyGroups: { Enabled: false, Quantity: 0 },
    ViewerProtocolPolicy: 'https-only', // con redirect-to-https un POST por http perdería el cuerpo
    AllowedMethods: { Quantity: API_METHODS.length, Items: API_METHODS, CachedMethods: { Quantity: 2, Items: ['GET', 'HEAD'] } },
    SmoothStreaming: false,
    Compress: false,
    LambdaFunctionAssociations: { Quantity: 0 },
    FunctionAssociations: { Quantity: 1, Items: [{ FunctionARN: live.api, EventType: 'viewer-request' }] },
    FieldLevelEncryptionId: '',
    CachePolicyId: policies.cache,
    OriginRequestPolicyId: policies.origin,
    ResponseHeadersPolicyId: headersPolicyId,
    GrpcConfig: { Enabled: false },
  };
  const behaviors = items(next.CacheBehaviors);
  const j = behaviors.findIndex((b) => b.PathPattern === API_PATH);
  if (j < 0) behaviors.unshift(behavior);
  else {
    // Repetir el paso no cambia nada: se conservan los campos que añada el API (y el orden en que
    // devuelve los métodos); los de TTL heredados no pueden convivir con una política de caché.
    const old = behaviors[j];
    const merged = { ...old, ...behavior };
    for (const k of ['ForwardedValues', 'MinTTL', 'DefaultTTL', 'MaxTTL']) delete merged[k];
    const sameSet = (a, b) => a.length === b.length && a.every((x) => b.includes(x));
    const methods = old.AllowedMethods || {};
    if (sameSet(items(methods), API_METHODS) && sameSet(items(methods.CachedMethods), ['GET', 'HEAD'])) merged.AllowedMethods = methods;
    behaviors[j] = merged;
  }
  next.CacheBehaviors = { Quantity: behaviors.length, Items: behaviors };

  const d = next.DefaultCacheBehavior;
  const fa = items(d.FunctionAssociations);
  const k = fa.findIndex((a) => a.EventType === 'viewer-request');
  const gate = { FunctionARN: live.default, EventType: 'viewer-request' };
  if (k >= 0) fa[k] = gate;
  else fa.unshift(gate);
  d.FunctionAssociations = { Quantity: fa.length, Items: fa };
  d.ResponseHeadersPolicyId = headersPolicyId;
  return next;
}

// Copia para comparar o enseñar: cada cabecera de origen se sustituye por una marca.
function redactForDiff(cfg, edge) {
  const c = clone(cfg);
  for (const o of items(c.Origins)) for (const h of items(o.CustomHeaders)) {
    if (!edge) h.HeaderValue = '«secreto»';
    else if (h.HeaderValue === edge.value) h.HeaderValue = `«valor de SSM ${EDGE_PARAM} v${edge.version}${edge.all.length > 1 ? ', línea 2 de 2' : ''}»`;
    else if (edge.all.includes(h.HeaderValue)) h.HeaderValue = '«valor anterior de SSM, línea 1 de 2»';
    else h.HeaderValue = '«valor que ya no está en SSM»';
  }
  return c;
}
function keyed(list) {
  if (!Array.isArray(list) || !list.length || !list.every((x) => x && typeof x === 'object')) return null;
  for (const k of ['Id', 'PathPattern', 'EventType', 'HeaderName']) if (list.every((x) => typeof x[k] === 'string')) return k;
  return null;
}
function diff(a, b, where, out) {
  const short = (v) => {
    const s = JSON.stringify(v);
    return s === undefined ? '(nada)' : s.length > 1500 ? s.slice(0, 1500) + '…' : s;
  };
  if (JSON.stringify(a) === JSON.stringify(b)) return out;
  const k = Array.isArray(a) && Array.isArray(b) ? keyed(a.concat(b)) : null;
  if (k) {
    const ma = new Map(a.map((x) => [x[k], x]));
    const mb = new Map(b.map((x) => [x[k], x]));
    for (const [id, x] of ma) if (!mb.has(id)) out.push(`- ${where}[${id}] = ${short(x)}`);
    for (const [id, x] of mb) {
      if (!ma.has(id)) out.push(`+ ${where}[${id}] = ${short(x)}`);
      else diff(ma.get(id), x, `${where}[${id}]`, out);
    }
    return out;
  }
  const isObj = (v) => v && typeof v === 'object' && !Array.isArray(v);
  if (isObj(a) && isObj(b)) {
    for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) diff(a[key], b[key], where ? `${where}.${key}` : key, out);
    return out;
  }
  out.push(`~ ${where}: ${short(a)} → ${short(b)}`);
  return out;
}
function redactForFile(cfg) {
  const c = clone(cfg);
  const list = [];
  for (const o of items(c.Origins)) for (const h of items(o.CustomHeaders)) {
    h.HeaderValue = REDACTED;
    list.push({ OriginId: o.Id, HeaderName: h.HeaderName });
  }
  return { config: c, list };
}
function saveBackup(cur, file) {
  const { config, list } = redactForFile(cur.config);
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const target = path.resolve(file || path.join(HERE, 'backups', `${DIST_ID}-${stamp}.json`));
  if (fs.existsSync(target)) fatal(`la copia ${target} ya existe: elige otro --backup/--out`);
  fs.mkdirSync(path.dirname(target), { recursive: true, mode: 0o700 });
  const text = JSON.stringify({ ETag: cur.etag, SavedAt: new Date().toISOString(), RedactedHeaders: list, DistributionConfig: config }, null, 2) + '\n';
  for (const v of SECRETS) if (v && text.includes(v)) fatal('la copia contendría un secreto: no se guarda');
  fs.writeFileSync(target, text, { mode: 0o600, flag: 'wx' });
  return target;
}
function applyConfig(next, etag) {
  const file = writePrivate('distribution-config.json', JSON.stringify(next));
  try {
    const status = aws(['cloudfront', 'update-distribution', '--id', DIST_ID, '--if-match', etag, '--distribution-config', 'file://' + file,
      '--query', 'Distribution.Status', '--output', 'text'], { json: false });
    say(`update-distribution: ${status}. Esperando al despliegue (CloudFront tarda unos minutos)…`);
  } catch (error) {
    if (error.code === 'PreconditionFailed') fatal(`${DIST_ID} ha cambiado desde que se leyó (ETag): no se ha aplicado nada; vuelve a ejecutar`);
    throw error;
  } finally {
    fs.rmSync(file, { force: true });
  }
  aws(['cloudfront', 'wait', 'distribution-deployed', '--id', DIST_ID], { json: false });
  say('Desplegado.');
}
function legalVariants() {
  if (!/var LEGAL_NOJS = true;/.test(gateSource())) return [];
  return LEGAL_PAGES.map((page) => ({ key: `${page}/index.nojs.html`, file: path.join(HERE, 'public-pages', page, 'index.nojs.html') }));
}
function headObject(key) {
  try {
    return aws(['s3api', 'head-object', '--bucket', BUCKET, '--key', key, '--checksum-mode', 'ENABLED', '--region', 'us-east-1']);
  } catch (error) {
    if (['404', 'NotFound', 'NoSuchKey'].includes(error.code)) return null;
    throw error;
  }
}

async function phaseDistribution() {
  checkAccount();
  const live = liveFunctions();
  const policies = managedPolicies();
  const edge = edgeSecret();
  const cur = getConfig();
  checkConfig(cur.config);
  const headersId = ensureHeadersPolicy(cur.config);
  const next = buildConfig(cur.config, live, policies, edge.value, headersId);
  const changes = diff(redactForDiff(cur.config, edge), redactForDiff(next, edge), '', []);
  say(`\n${DIST_ID} (${ALIAS}) · contrato de /api/*:`);
  say(`  origen ${ORIGIN_ID} → ${ORIGIN_DOMAIN}:443 · https-only · TLSv1.2 · lectura 60 s · keep-alive 60 s`);
  say(`  cabecera de origen ${EDGE_HEADER}: valor de SSM ${EDGE_PARAM} (versión ${edge.version}${edge.all.length > 1 ? ', 2 líneas: se usa la segunda' : ''}; nunca se muestra)`);
  say(`  ${API_PATH} → ${ORIGIN_ID} · visor https-only · ${API_METHODS.join(' ')} · ${POLICIES.cache[0]} + ${POLICIES.origin[0]} · viewer-request ${FUNCTIONS.api.name}`);
  say(`  comportamiento por defecto → viewer-request ${FUNCTIONS.default.name}; el resto, sin tocar`);
  say(`  cabeceras de respuesta en «/» y en ${API_PATH}: ${HEADERS_POLICY_NAME} (HSTS ${HSTS_MAX_AGE} s sin includeSubDomains, nosniff, X-Frame-Options DENY, X-Robots-Tag noindex)${headersId === HEADERS_POLICY_PENDING ? ' · ' + HEADERS_POLICY_PENDING : ''}`);
  for (const v of legalVariants()) if (!headObject(v.key)) say(`AVISO: falta s3://${BUCKET}/${v.key}: /${v.key.split('/')[0]} sin cookie dará 403 hasta «legal --apply» (paso 15)`);
  if (!changes.length) {
    say('\n= Ya está así: nada que cambiar.');
    return 0;
  }
  say(`\nCambios (${changes.length}):`);
  for (const line of changes) say('  ' + line);
  if (!APPLY) {
    say('\n(simulación: con --apply se aplica)');
    return 0;
  }
  say(`\nCopia previa, sin secretos: ${saveBackup(cur, opt('--backup'))}`);
  applyConfig(next, cur.etag);
  if (flag('--skip-verify')) return 0;
  return phaseVerify();
}

function phaseBackup() {
  checkAccount();
  const cur = getConfig();
  say(`Copia de ${DIST_ID} (ETag ${cur.etag}) con las cabeceras de origen en blanco: ${saveBackup(cur, opt('--out'))}`);
  return 0;
}

async function phaseRollback() {
  const from = opt('--from');
  if (!from) fatal('falta --from <copia>');
  const saved = JSON.parse(fs.readFileSync(from, 'utf8'));
  const target = clone(saved.DistributionConfig || saved);
  for (const v of headerValues(target)) if (v !== REDACTED) SECRETS.add(v);
  checkAccount();
  const cur = getConfig();
  if (target.CallerReference !== cur.config.CallerReference) fatal(`la copia no es de ${DIST_ID} (CallerReference distinto)`);
  if (!items(target.Aliases).includes(ALIAS)) fatal(`la copia no sirve ${ALIAS}`);
  let edge = null;
  for (const o of items(target.Origins)) for (const h of items(o.CustomHeaders)) {
    if (h.HeaderValue !== REDACTED) continue;
    if (o.Id !== ORIGIN_ID || h.HeaderName !== EDGE_HEADER) fatal(`la copia tiene en blanco ${o.Id} ${h.HeaderName}, que no sé rellenar`);
    edge = edge || edgeSecret();
    h.HeaderValue = edge.value;
  }
  const changes = diff(redactForDiff(cur.config, edge), redactForDiff(target, edge), '', []);
  if (!changes.length) {
    say('= La distribución ya coincide con la copia.');
    return 0;
  }
  say(`Cambios para volver a ${path.basename(from)} (${changes.length}):`);
  for (const line of changes) say('  ' + line);
  if (!APPLY) {
    say('\n(simulación: con --apply se aplica)');
    return 0;
  }
  say(`\nCopia previa, sin secretos: ${saveBackup(cur, opt('--backup'))}`);
  applyConfig(target, cur.etag);
  say('Hecho. Si la copia es de antes del paso 13, la puerta y /api/* ya no están: compruébalo por la UI.');
  return 0;
}

function phaseLegal() {
  const variants = legalVariants();
  if (!variants.length) {
    say('gate-default.js está en modo --legal-js: no hay variantes sin JS que subir.');
    return 0;
  }
  checkAccount();
  for (const v of variants) {
    if (!fs.existsSync(v.file)) fatal(`falta ${v.file}: node build_gate.mjs --dist <dist> --write`);
    const want = crypto.createHash('sha256').update(fs.readFileSync(v.file)).digest('base64');
    const head = headObject(v.key);
    if (head && head.ChecksumSHA256 === want && /^text\/html/.test(head.ContentType || '')) {
      say(`= s3://${BUCKET}/${v.key}: ya está al día`);
      continue;
    }
    if (!APPLY) {
      say(`${head ? '~' : '+'} s3://${BUCKET}/${v.key}: se subirá (text/html; charset=utf-8, no-cache)`);
      continue;
    }
    aws(['s3api', 'put-object', '--bucket', BUCKET, '--key', v.key, '--body', v.file, '--content-type', 'text/html; charset=utf-8',
      '--cache-control', 'no-cache', '--checksum-algorithm', 'SHA256', '--region', 'us-east-1']);
    const after = headObject(v.key);
    if (!after || after.ChecksumSHA256 !== want) fatal(`s3://${BUCKET}/${v.key}: la comprobación tras subir no coincide`);
    say(`+ s3://${BUCKET}/${v.key}: subido`);
  }
  if (!APPLY) say('\n(simulación: con --apply se sube)');
  return 0;
}

// ── verify: de punta a punta por internet, solo GET y sin credenciales ───────
function request(url, headers = {}) {
  return new Promise((resolve) => {
    const u = new URL(url);
    const lib = u.protocol === 'https:' ? https : http;
    const req = lib.request(u, { method: 'GET', agent: false, timeout: 20000, headers: { 'user-agent': 'uonify-deploy-edge-verify/1', ...headers } }, (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        if (body.length < 65536) body += chunk;
      });
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body }));
    });
    req.on('upgrade', (res, socket) => {
      socket.destroy();
      resolve({ status: 101, headers: res.headers, body: '' });
    });
    req.on('timeout', () => req.destroy(new Error('tiempo agotado')));
    req.on('error', (error) => resolve({ error: error.code || error.message }));
    req.end();
  });
}
const NAV = { 'sec-fetch-mode': 'navigate', 'sec-fetch-dest': 'document', 'sec-fetch-site': 'none', accept: 'text/html' };
const GATE_JSON = '{"error":"gate_required"}';
function apiDiagnosis(r) {
  if (r.error) return `sin respuesta (${r.error})`;
  if (r.status === 403 && /"forbidden"/.test(r.body)) return `nginx rechaza: ${EDGE_HEADER} falta o no coincide con ${EDGE_PARAM} (¿se cambió SSM sin uonify-secrets-sync en el host? ¿rotación a medias?)`;
  if (r.status === 403) return `403 de CloudFront: ¿falta el comportamiento ${API_PATH}?`;
  if (r.status === 401) return `gate-api no deja pasar /api/health (revisar OPEN)`;
  if (r.status === 502) return `CloudFront no consigue TLS con ${ORIGIN_DOMAIN}: ¿se reenvía el Host del visor?, ¿certificado caducado?, ¿DNS de ${ORIGIN_DOMAIN}?`;
  if (r.status === 503) return 'nginx responde pero el contenedor api no (caído o arrancando)';
  if (r.status === 504) return 'tiempo agotado hacia el origen: ¿instancia parada?, ¿security group?, ¿nginx caído?';
  return `respuesta inesperada ${r.status}`;
}
async function phaseVerify() {
  const base = opt('--base-url', 'https://' + ALIAS).replace(/\/+$/, '');
  const httpUrl = opt('--http-url', 'http://' + ALIAS);
  const source = gateSource();
  const rootPublic = /var ROOT_PUBLIC = true;/.test(source);
  const nojs = /var LEGAL_NOJS = true;/.test(source);
  const wsKey = crypto.randomBytes(16).toString('base64');
  const checks = [
    ['/api/health → 200 (origen, TLS, Host y X-Origin-Verify)', () => request(base + '/api/health', { accept: 'application/json' }),
      (r) => (r.status === 200 && /"status"\s*:\s*"ok"/.test(r.body) ? ['OK'] : ['FALLO', apiDiagnosis(r)])],
    ['/api/auth/session sin cookie → 401 gate_required, sin WWW-Authenticate', () => request(base + '/api/auth/session', { accept: 'application/json' }),
      (r) => (r.status === 401 && r.body.trim() === GATE_JSON && !r.headers['www-authenticate'] ? ['OK'] : ['FALLO', r.error || `llega ${r.status} ${r.body.slice(0, 80)}`])],
    ['voz: handshake WebSocket /api/uony/live sin cookie → 401 gate_required', () => request(base + '/api/uony/live', {
      connection: 'Upgrade', upgrade: 'websocket', 'sec-websocket-key': wsKey, 'sec-websocket-version': '13', origin: 'https://' + ALIAS,
      'sec-fetch-mode': 'websocket', 'sec-fetch-dest': 'websocket', 'sec-fetch-site': 'same-origin',
    }), (r) => (r.status === 401 && r.body.trim() === GATE_JSON ? ['OK'] : ['FALLO', r.error || `llega ${r.status}${r.status === 101 ? ': ¡el WebSocket se abre sin puerta!' : ''}`])],
    ['/espacio (navegación) sin cookie → 401 con reto Basic', () => request(base + '/espacio', NAV),
      (r) => (r.status === 401 && /^Basic realm="Uonify DEV"/.test(r.headers['www-authenticate'] || '') ? ['OK'] : ['FALLO', r.error || `llega ${r.status}`])],
    ['/espacio (subrecurso) sin cookie → 403 de la puerta, sin WWW-Authenticate', () => request(base + '/espacio', { 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty' }),
      (r) => (r.status === 403 && r.body === 'Acceso restringido.' && !r.headers['www-authenticate'] ? ['OK'] : ['FALLO', r.error || `llega ${r.status} ${String(r.body).slice(0, 60)}`])],
    ['/web/home-v22-propuesta/index.html → 200 (pública)', () => request(base + '/web/home-v22-propuesta/index.html', NAV),
      (r) => (r.status === 200 ? ['OK'] : ['FALLO', r.error || `llega ${r.status}`])],
    [`HSTS (${HSTS_MAX_AGE} s, sin subdominios) y nosniff en una página servida por S3`, () => request(base + '/web/home-v22-propuesta/index.html', NAV),
      (r) => (r.headers && r.headers['strict-transport-security'] === `max-age=${HSTS_MAX_AGE}` && r.headers['x-content-type-options'] === 'nosniff'
        ? ['OK'] : ['FALLO', r.error || `strict-transport-security=${r.headers['strict-transport-security'] || '(falta)'} · x-content-type-options=${r.headers['x-content-type-options'] || '(falta)'}: ¿falta ${HEADERS_POLICY_NAME} en el comportamiento por defecto?`])],
    [`HSTS en /api/health (respuesta del origen)`, () => request(base + '/api/health', { accept: 'application/json' }),
      (r) => (r.headers && r.headers['strict-transport-security'] === `max-age=${HSTS_MAX_AGE}`
        ? ['OK'] : ['FALLO', r.error || `strict-transport-security=${r.headers['strict-transport-security'] || '(falta)'}`])],
    [rootPublic ? '«/» → 200 (pública mientras ROOT_PUBLIC)' : '«/» sin cookie → 401 con reto Basic', () => request(base + '/', NAV),
      (r) => ((rootPublic ? r.status === 200 : r.status === 401 && r.headers['www-authenticate']) ? ['OK'] : ['FALLO', r.error || `llega ${r.status}`])],
    ['/privacidad.html (enlace antiguo) sin cookie → 301 a /privacidad', () => request(base + '/privacidad.html', NAV),
      (r) => (r.status === 301 && r.headers.location === '/privacidad' ? ['OK'] : ['FALLO', r.error || `llega ${r.status} ${r.headers && r.headers.location ? '→ ' + r.headers.location : ''}`])],
    [`/privacidad sin cookie → 200 HTML${nojs ? ' sin el JS de la app' : ''}`, () => request(base + '/privacidad', NAV), (r) => {
      if (r.status === 403) return ['AVISO', 'S3 da 403: faltan las variantes o el dist (legal --apply / paso 15)'];
      if (r.status !== 200 || !/data-prerendered=/.test(r.body)) return ['FALLO', r.error || `llega ${r.status}`];
      return nojs && /<script\b[^>]*type=["']?module/i.test(r.body) ? ['FALLO', 'la página pública lleva el JS de la app'] : ['OK'];
    }],
  ];
  if (httpUrl !== 'off') {
    checks.push(['http:// /api/health → 403 (el visor solo entra por https)', () => request(httpUrl.replace(/\/+$/, '') + '/api/health'),
      (r) => (r.error ? ['AVISO', `sin respuesta por http (${r.error})`] : r.status === 403 ? ['OK'] : ['FALLO', `llega ${r.status}: ${API_PATH} no está en https-only`])]);
  }
  say(`\nverify ${base}`);
  const tally = { OK: 0, AVISO: 0, FALLO: 0 };
  for (const [label, run, judge] of checks) {
    const [verdict, detail] = judge(await run());
    tally[verdict] += 1;
    say(`${verdict.padEnd(5)} ${label}${detail ? ' · ' + detail : ''}`);
  }
  say(`\n${tally.OK}/${checks.length} OK · ${tally.AVISO} avisos · ${tally.FALLO} fallos`);
  return tally.FALLO ? 1 : 0;
}

// ── plan: estado y cambios previstos, solo lectura ───────────────────────────
async function phasePlan() {
  checkAccount();
  const kvs = kvsInfo();
  say(kvs ? `KeyValueStore ${KVS_NAME}: ${kvs.Status}` : `KeyValueStore ${KVS_NAME}: no existe (lo crea functions --apply)`);
  if (kvs && kvs.Status === 'READY') {
    const keys = kvsKeys(kvs.ARN);
    for (const k of KVS_KEYS) say(keys.includes(k) ? `  OK    ${k}` : `  FALTA ${k} (el dueño: ./set_gate_credentials.sh)`);
  }
  for (const fn of Object.values(FUNCTIONS)) for (const stage of ['DEVELOPMENT', 'LIVE']) {
    const d = describeFunction(fn.name, stage);
    if (!d) {
      say(`${fn.name} ${stage}: no existe`);
      continue;
    }
    const same = sha(deployedCode(fn.name, stage)) === sha(localCode(fn));
    const kvsOk = kvs && sameConfig(d.FunctionSummary.FunctionConfig, functionConfig(fn, kvs.ARN));
    say(`${fn.name} ${stage}: ${same ? `= ${fn.file}` : `código DISTINTO de ${fn.file}`}${kvsOk ? '' : ' · configuración o KVS distintos'}`);
  }
  // Solo metadatos (tipo y versión): describe-parameters nunca devuelve el valor.
  const param = aws(['ssm', 'describe-parameters', '--region', EDGE_REGION, '--parameter-filters', `Key=Name,Values=${EDGE_PARAM}`]).Parameters || [];
  say(param.length ? `SSM ${EDGE_PARAM}: ${param[0].Type}, versión ${param[0].Version}` : `SSM ${EDGE_PARAM}: NO existe (upload_dev_secrets.sh --with-edge-secret)`);
  for (const v of legalVariants()) say(`s3://${BUCKET}/${v.key}: ${headObject(v.key) ? 'existe' : 'falta (legal --apply, paso 15)'}`);
  try {
    await phaseDistribution();
  } catch (error) {
    if (!(error instanceof Fatal)) throw error;
    say(`\nDistribución: todavía no se puede preparar: ${error.message}`);
  }
  return 0;
}

const PHASES = { plan: phasePlan, functions: phaseFunctions, publish: phasePublish, distribution: phaseDistribution, legal: phaseLegal, verify: phaseVerify, backup: phaseBackup, rollback: phaseRollback };
async function main() {
  if (!PHASES[cmd]) {
    console.error('Uso: node deploy_edge.mjs plan | functions [--apply] | publish [--apply] | distribution [--apply] | legal [--apply] | verify | backup [--out f] | rollback --from f [--apply]');
    return 64;
  }
  if (cmd === 'plan' && APPLY) {
    console.error('plan es solo lectura: no admite --apply');
    return 64;
  }
  try {
    return await PHASES[cmd]();
  } catch (error) {
    console.error('ERROR: ' + scrub(error instanceof Fatal ? error.message : (error && error.stack) || error));
    return 2;
  } finally {
    cleanup();
  }
}
process.exitCode = await main();
