#!/usr/bin/env node
// test_gate.mjs · Banco de pruebas OFFLINE de la puerta de dev.uonify.com.
// Ejecuta gate-default.js y gate-api.js tal cual (solo se sustituyen los dos `import` por dobles:
// KVS en memoria y el crypto de Node) contra eventos CloudFront simulados, prueba
// set_gate_credentials.sh con un AWS CLI falso (test/fake-bin/aws, nunca llama a AWS) y comprueba
// que el bloque generado coincide con el dist. No usa red. Sale con 1 si falla algo.
//
//   node test_gate.mjs            (GATE_DIST, GATE_FRONT_SRC, GATE_BACKEND_SRC, GATE_ACORN opcionales)
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import * as gen from './build_gate.mjs';
import { deployTests } from './test/deploy_tests.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SCRATCH = path.resolve(HERE, '..', '..');
// Red de seguridad: todo lo que lance este banco usa el AWS CLI falso (test/fake-bin va primero en
// el PATH); aun así, si algo llegara al AWS CLI real, no tendría ni perfil ni credenciales.
for (const k of ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN', 'AWS_CONTAINER_CREDENTIALS_FULL_URI', 'AWS_CONTAINER_CREDENTIALS_RELATIVE_URI', 'AWS_WEB_IDENTITY_TOKEN_FILE']) delete process.env[k];
Object.assign(process.env, { AWS_CONFIG_FILE: '/dev/null', AWS_SHARED_CREDENTIALS_FILE: '/dev/null', AWS_PROFILE: 'perfil-de-prueba', AWS_EC2_METADATA_DISABLED: 'true' });
const DIST = process.env.GATE_DIST || path.join(SCRATCH, 'frontend-build/src-copy/dist');
const FRONT_SRC = process.env.GATE_FRONT_SRC || path.join(SCRATCH, 'frontend-build/src-copy/src');
const BACKEND_SRC = process.env.GATE_BACKEND_SRC || path.join(SCRATCH, 'dev-overlay/src-api/app');
const ACORN = process.env.GATE_ACORN || path.join(SCRATCH, 'frontend-build/src-copy/node_modules/acorn');
// GATE_*_FILE: solo para test/mutants.mjs (copias mutadas que deben FALLAR).
const DEFAULT_FILE = process.env.GATE_DEFAULT_FILE || path.join(HERE, 'gate-default.js');
const API_FILE = process.env.GATE_API_FILE || path.join(HERE, 'gate-api.js');
const SCRIPT = process.env.GATE_SCRIPT_FILE || path.join(HERE, 'set_gate_credentials.sh');
const RTF = process.env.GATE_RTF_FILE || path.join(HERE, 'run_test_function.mjs');
const DEPLOY = process.env.GATE_DEPLOY_FILE || path.join(HERE, 'deploy_edge.mjs');
const FAKE_BIN = path.join(HERE, 'test', 'fake-bin');
const TMP = path.join(HERE, 'test', 'tmp');

// ── mini runner ──────────────────────────────────────────────────────────────
const results = [];
let group = '';
async function test(name, fn) {
  try {
    await fn();
    results.push({ group, name, ok: true });
  } catch (error) {
    results.push({ group, name, ok: false, error: error.message });
  }
}
function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}
function eq(actual, expected, msg) {
  if (actual !== expected) throw new Error(`${msg}: esperado ${JSON.stringify(expected)}, obtenido ${JSON.stringify(actual)}`);
}
function deepEq(actual, expected, msg) {
  const a = JSON.stringify(actual);
  const b = JSON.stringify(expected);
  if (a !== b) throw new Error(`${msg}: esperado ${b}, obtenido ${a}`);
}

// ── secretos de PRUEBA (aleatorios en cada ejecución, nunca reales) ───────────
const USER = 'prueba-dev'; // usuario ficticio de la prueba local (nunca el real)
const PASS = crypto.randomBytes(18).toString('base64url');
const sha256 = (s) => crypto.createHash('sha256').update(s).digest('hex');
const HASH = sha256(USER + ':' + PASS);
const KEY = crypto.randomBytes(32).toString('hex');
const B64CRED = Buffer.from(USER + ':' + PASS).toString('base64');
const COOKIE = '__Host-uonify_gate';
const TTL = 691200;
const SECRETS = () => [PASS, HASH, KEY, B64CRED, ...EXTRA_SECRETS];
const EXTRA_SECRETS = [];

// ── carga de las funciones con dobles de `cloudfront` y `crypto` ─────────────
const STORE = {};
const KVS_READS = [];
const cfMock = {
  kvs: () => ({
    get: async (key) => {
      KVS_READS.push(key);
      if (!Object.prototype.hasOwnProperty.call(STORE, key)) throw new Error('KeyNotFound');
      return STORE[key];
    },
  }),
};
function resetStore(values = { gate_cred_sha256: HASH, gate_hmac_key: KEY }) {
  for (const k of Object.keys(STORE)) delete STORE[k];
  Object.assign(STORE, values);
}
function loadSource(src) {
  const body = src.replace(/^import cf from 'cloudfront';[ \t]*$/m, '').replace(/^import crypto from 'crypto';[ \t]*$/m, '');
  if (/^\s*import\s/m.test(body)) throw new Error('import inesperado en la función');
  const factory = new Function('cf', 'crypto', 'atob', '"use strict";\n' + body + '\nreturn handler;');
  return factory(cfMock, crypto, globalThis.atob);
}
const OUTPUTS = [];
function wrap(handler) {
  return async (event) => {
    const out = await handler(structuredClone(event));
    OUTPUTS.push(out);
    return out;
  };
}
const gateDefault = wrap(loadSource(fs.readFileSync(DEFAULT_FILE, 'utf8')));
const gateApi = wrap(loadSource(fs.readFileSync(API_FILE, 'utf8')));

// ── constructor de eventos CloudFront ────────────────────────────────────────
function headers(obj) {
  const h = {};
  for (const [k, v] of Object.entries(obj)) {
    if (v === undefined) continue;
    h[k.toLowerCase()] = Array.isArray(v) ? { value: v[0], multiValue: v.map((x) => ({ value: x })) } : { value: v };
  }
  return h;
}
function querystring(raw) {
  const out = {};
  if (!raw) return out;
  for (const part of raw.split('&')) {
    const i = part.indexOf('=');
    const k = i < 0 ? part : part.slice(0, i);
    const v = i < 0 ? '' : part.slice(i + 1);
    if (out[k]) {
      out[k].multiValue = out[k].multiValue || [{ value: out[k].value }];
      out[k].multiValue.push({ value: v });
    } else out[k] = { value: v };
  }
  return out;
}
function cookies(list) {
  const out = {};
  for (const [k, v] of list) {
    if (out[k]) {
      out[k].multiValue = out[k].multiValue || [{ value: out[k].value }];
      out[k].multiValue.push({ value: v });
    } else out[k] = { value: v };
  }
  return out;
}
function event({ method = 'GET', url, h = {}, c = [] }) {
  const i = url.indexOf('?');
  return {
    version: '1.0',
    context: { eventType: 'viewer-request', distributionId: 'E4N1UCPZZ2F0', distributionDomainName: 'd1example.cloudfront.net', requestId: 'test' },
    viewer: { ip: '203.0.113.7' },
    request: {
      method,
      uri: i < 0 ? url : url.slice(0, i),
      querystring: querystring(i < 0 ? '' : url.slice(i + 1)),
      headers: headers({ host: 'dev.uonify.com', 'user-agent': 'Mozilla/5.0 test', ...h }),
      cookies: cookies(c),
    },
  };
}
const NAV = { 'sec-fetch-mode': 'navigate', 'sec-fetch-dest': 'document', 'sec-fetch-site': 'none', 'sec-fetch-user': '?1', accept: 'text/html' };
const SUB = (dest, mode = 'no-cors') => ({ 'sec-fetch-mode': mode, 'sec-fetch-dest': dest, 'sec-fetch-site': 'same-origin' });
const basic = (u, p) => 'Basic ' + Buffer.from(u + ':' + p).toString('base64');
const now = () => Math.floor(Date.now() / 1000);
const sign = (exp, key = KEY) => crypto.createHmac('sha256', key).update('uonify-dev-gate|v1|' + exp).digest('hex');
const mint = (exp = now() + TTL, key = KEY) => 'v1.' + exp + '.' + sign(exp, key);
const SESSION = ['uonify_session', 'sesion-de-prueba-' + crypto.randomBytes(6).toString('hex')];

const isRequest = (o) => o && typeof o.uri === 'string' && o.statusCode === undefined;
function expectRequest(o, uri, msg) {
  assert(isRequest(o), `${msg}: se esperaba dejar pasar la petición y llegó ${o && o.statusCode}`);
  if (uri !== undefined) eq(o.uri, uri, `${msg} (uri)`);
  assert(!o.headers.authorization, `${msg}: Authorization no se ha borrado`);
  assert(!(o.cookies && o.cookies[COOKIE]), `${msg}: la cookie de puerta no se ha quitado`);
}
function expectChallenge(o, msg) {
  assert(o && o.statusCode === 401, `${msg}: se esperaba 401 y llegó ${isRequest(o) ? 'la petición' : o && o.statusCode}`);
  const w = o.headers['www-authenticate'];
  assert(w && w.value === 'Basic realm="Uonify DEV", charset="UTF-8"', `${msg}: falta el reto Basic`);
  eq(o.headers['cache-control'].value, 'no-store', `${msg} (cache-control)`);
}
function expect403(o, msg) {
  assert(o && o.statusCode === 403, `${msg}: se esperaba 403 y llegó ${isRequest(o) ? 'la petición' : o && o.statusCode}`);
  assert(!o.headers['www-authenticate'], `${msg}: un 403 no puede llevar WWW-Authenticate`);
  eq(o.headers['cache-control'].value, 'no-store', `${msg} (cache-control)`);
}
function expectGateJson(o, msg) {
  assert(o && o.statusCode === 401, `${msg}: se esperaba 401 JSON y llegó ${isRequest(o) ? 'la petición' : o && o.statusCode}`);
  assert(!o.headers['www-authenticate'], `${msg}: el 401 de /api no puede llevar WWW-Authenticate`);
  eq(o.headers['content-type'].value, 'application/json', `${msg} (content-type)`);
  eq(o.headers['cache-control'].value, 'no-store', `${msg} (cache-control)`);
  eq(o.body && o.body.data, '{"error":"gate_required"}', `${msg} (cuerpo)`);
  eq(o.body.encoding, 'text', `${msg} (encoding)`);
}

// ── «bucket» simulado: dist subido (sin lo excluido) + variantes + index.html raíz antiguo ──
const UPLOADED = new Set();
for (const f of fs.readdirSync(DIST, { recursive: true })) {
  const p = '/' + String(f).split(path.sep).join('/');
  if (fs.statSync(path.join(DIST, String(f))).isFile() && p !== '/index.html' && !gen.isNotUploaded(p)) UPLOADED.add(p);
}
const PAGES_DIR = path.join(HERE, 'public-pages');
if (fs.existsSync(PAGES_DIR)) for (const f of fs.readdirSync(PAGES_DIR, { recursive: true })) {
  const p = '/' + String(f).split(path.sep).join('/');
  if (fs.statSync(path.join(PAGES_DIR, String(f))).isFile()) UPLOADED.add(p);
}
UPLOADED.add('/index.html'); // el index.html raíz actual (meta-refresh a /web/…), que no se sustituye hasta el paso 19
const inBucket = (uri) => (uri === '/' ? UPLOADED.has('/index.html') : UPLOADED.has(uri));

const defaultSource = fs.readFileSync(DEFAULT_FILE, 'utf8');
// Modo de la raíz del gate-default.js que se prueba: pública (por defecto) o detrás de la puerta (--root-gated).
const ROOT_PUBLIC = /var ROOT_PUBLIC = true;/.test(defaultSource);
const generatedNow = gen.currentBlock(defaultSource);
const PUBLIC_ASSETS = /var PUBLIC_ASSETS = '\|(.*)\|';/.exec(generatedNow)[1].split('|');
const PRERENDERED = /var PRERENDERED = '\|(.*)\|';/.exec(generatedNow)[1].split('|');

// ════════════════════════════════════════════════════════════════════════════
async function run() {
  resetStore();

  group = '1 · rutas públicas (sin cookie)';
  await test('/privacidad sin cookie → variante sin JS, Authorization borrada', async () => {
    for (const url of ['/privacidad', '/privacidad/', '/privacidad/index.html']) {
      const o = await gateDefault(event({ url, h: { ...NAV, authorization: basic(USER, 'otra') } }));
      expectRequest(o, '/privacidad/index.nojs.html', url);
      assert(inBucket(o.uri), `${url}: el destino no estaría en el bucket`);
    }
  });
  await test('/terminos sin cookie → variante sin JS', async () => {
    for (const url of ['/terminos', '/terminos/', '/terminos/index.html']) expectRequest(await gateDefault(event({ url, h: NAV })), '/terminos/index.nojs.html', url);
  });
  await test('/privacidad y /terminos con cookie → página completa de la app', async () => {
    for (const page of ['privacidad', 'terminos']) {
      const o = await gateDefault(event({ url: '/' + page, h: NAV, c: [[COOKIE, mint()], SESSION] }));
      expectRequest(o, `/${page}/index.html`, page);
      assert(o.cookies.uonify_session, 'se ha perdido otra cookie');
    }
  });
  await test('la variante pública solo pide assets públicos que existen (escaneo src/href + url())', async () => {
    for (const page of gen.PUBLIC_PAGES) {
      const html = fs.readFileSync(path.join(PAGES_DIR, page, gen.NOJS_NAME), 'utf8');
      const wanted = new Set();
      for (const ref of gen.htmlRefs(html)) {
        const p = gen.sameOriginPath(ref.value, `/${page}/`);
        if (p) wanted.add(p);
      }
      for (const p of [...wanted]) if (p.endsWith('.css')) for (const r of gen.cssRefs(fs.readFileSync(path.join(DIST, p), 'utf8'))) {
        const q = gen.sameOriginPath(r, p.slice(0, p.lastIndexOf('/') + 1));
        if (q) wanted.add(q);
      }
      assert(wanted.size >= 5, `${page}: muy pocos recursos detectados (${wanted.size})`);
      for (const p of wanted) {
        assert(!/\.m?js$/.test(p), `${page}: la variante pública pide JS (${p})`);
        const dest = p.endsWith('.css') ? 'style' : 'image';
        const o = await gateDefault(event({ url: p, h: SUB(dest) }));
        expectRequest(o, p, `${page} → ${p}`);
        assert(inBucket(p), `${page}: ${p} no estaría en el bucket`);
      }
    }
  });
  await test('cada PUBLIC_ASSETS pasa sin cookie y existe en el bucket', async () => {
    assert(PUBLIC_ASSETS.length > 0, 'lista vacía');
    for (const p of PUBLIC_ASSETS) {
      expectRequest(await gateDefault(event({ url: p, h: SUB(p.endsWith('.css') ? 'style' : 'image') })), p, p);
      assert(inBucket(p), `${p} no estaría en el bucket`);
      assert(!gen.isNotUploaded(p), `${p} es un fichero que no se sube`);
    }
  });
  await test('el JS de la app (también el que pide la página legal original) NO es público', async () => {
    const original = fs.readFileSync(path.join(DIST, 'privacidad/index.html'), 'utf8');
    const js = gen.htmlRefs(original).map((r) => gen.sameOriginPath(r.value, '/privacidad/')).filter((p) => p && p.endsWith('.js'));
    assert(js.length >= 3, 'no se han encontrado los JS de la página original');
    const all = [...UPLOADED].filter((p) => p.endsWith('.js'));
    for (const p of new Set([...js, ...all])) expect403(await gateDefault(event({ url: p, h: SUB('script', 'cors') })), p);
  });
  await test(`/web/* y /robots.txt pasan sin cookie; «/» ${ROOT_PUBLIC ? 'también (ROOT_PUBLIC)' : 'pide la puerta (--root-gated: la app está en la raíz)'}`, async () => {
    for (const url of ['/web/home-v22-propuesta/index.html', '/web/home-v22-propuesta/index.html?view=espacio', '/web/home-v22-propuesta/app-shell.js', '/robots.txt']) {
      const o = await gateDefault(event({ url, h: url.endsWith('.js') ? SUB('script') : NAV }));
      expectRequest(o, url.split('?')[0], url);
    }
    for (const url of ['/', '/index.html', '/?utm_source=x']) {
      if (ROOT_PUBLIC) {
        expectRequest(await gateDefault(event({ url, h: NAV })), url.split('?')[0], url);
      } else {
        expectChallenge(await gateDefault(event({ url, h: NAV })), url);
        expect403(await gateDefault(event({ url, h: SUB('script', 'cors') })), url);
      }
    }
  });
  await test('trucos de ruta hacia contenido protegido no son públicos', async () => {
    const tricks = ['/web/../assets/index-CBBAzHmR.js', '/web/%2e%2e/assets/index-CBBAzHmR.js', '/web/..%2Fassets/index-CBBAzHmR.js', '/web/%2E%2E%2Fassets/x.js',
      '/web//assets/x.js', '/web/.%2e/assets/x.js', '/privacidad/../espacio', '/privacidad/..', '/assets/./ui-B_q764Gq.css', '/web\\..\\assets\\x.js',
      '/PRIVACIDAD', '/PRIVACIDAD.html', '/privacidad.htm', '/privacidad.html/', '/privacidad.html/x', '/x/privacidad.html', '/terminos.html.js', '/web',
      '/privacidad/index.nojs.html', '/assets/ui-B_q764Gq.css|/assets/x.js', '/?view=privacidad', '/index.html?view=espacio', '/index.html?view=Terminos'];
    for (const url of tricks) {
      expect403(await gateDefault(event({ url, h: SUB('script', 'cors') })), url);
      expectChallenge(await gateDefault(event({ url, h: NAV })), url);
    }
  });
  await test('enlaces antiguos a las legales sin cookie → 301 a la página pública (como LegacyRedirect en local)', async () => {
    const cases = [['/privacidad.html', '/privacidad'], ['/terminos.html', '/terminos'], ['/privacidad.html?v=20260922', '/privacidad'],
      ['/index.html?view=privacidad', '/privacidad'], ['/index.html?view=terminos&x=1', '/terminos']];
    for (const [url, loc] of cases) for (const h of [NAV, SUB('empty', 'cors'), {}]) {
      const o = await gateDefault(event({ url, h: { ...h, authorization: basic(USER, 'otra') } }));
      assert(o && o.statusCode === 301, `${url} ${JSON.stringify(h)}: se esperaba 301 y llegó ${isRequest(o) ? 'la petición' : o && o.statusCode}`);
      eq(o.headers.location.value, loc, `${url}: Location`);
      assert(!o.headers['www-authenticate'] && !o.cookies, `${url}: ni reto ni cookie`);
      eq(o.headers['cache-control'].value, 'no-store', `${url}: cache-control`);
      expectRequest(await gateDefault(event({ url: loc, h: NAV })), `${loc}/index.nojs.html`, `${url} → ${loc}`);
    }
  });

  group = '2 · puerta: navegaciones, subrecursos, Basic y cookie';
  await test('navegación sin cookie → reto Basic (variantes de Sec-Fetch-*)', async () => {
    const variants = [NAV, { 'sec-fetch-mode': 'navigate' }, { 'sec-fetch-dest': 'document' }, { 'sec-fetch-mode': 'navigate', 'sec-fetch-dest': 'iframe' },
      { 'sec-fetch-mode': 'Navigate', 'sec-fetch-dest': 'Document' }];
    for (const h of variants) {
      const o = await gateDefault(event({ url: '/espacio', h }));
      expectChallenge(o, JSON.stringify(h));
      assert(/Acceso restringido/.test(o.body.data), 'cuerpo del 401');
    }
  });
  await test('subrecursos sin cookie → 403 sin WWW-Authenticate', async () => {
    const cases = [SUB('script', 'cors'), SUB('style'), SUB('image'), SUB('font', 'cors'), SUB('empty', 'cors'), SUB('empty', 'same-origin'), SUB('manifest', 'cors'),
      SUB('worker', 'same-origin'), { 'sec-fetch-mode': 'websocket', 'sec-fetch-dest': 'websocket' }, {}, { accept: 'text/html' }];
    for (const h of cases) for (const url of ['/espacio', '/assets/HomePage-DZz_Bmyo.js', '/spa.html', '/']) {
      if (url === '/' && ROOT_PUBLIC) continue; // «/» es pública mientras ROOT_PUBLIC
      expect403(await gateDefault(event({ url, h })), `${url} ${JSON.stringify(h)}`);
    }
  });
  await test('Basic válido en subrecurso sin cookie → 403 (Basic solo en navegaciones)', async () => {
    expect403(await gateDefault(event({ url: '/assets/HomePage-DZz_Bmyo.js', h: { ...SUB('script', 'cors'), authorization: basic(USER, PASS) } })), 'script');
    expect403(await gateDefault(event({ url: '/espacio', h: { authorization: basic(USER, PASS) } })), 'sin Sec-Fetch (curl)');
  });
  await test('credenciales malas o mal formadas → reto Basic de nuevo', async () => {
    const bad = [basic(USER, PASS + 'x'), basic('otro', PASS), basic(USER.toUpperCase(), PASS), 'Basic !!!!', 'Basic ' + Buffer.from(USER + PASS).toString('base64'),
      'Bearer ' + B64CRED, 'Basic', 'Basic ' + B64CRED.slice(0, -1), 'Basic ' + Buffer.from(':' + PASS).toString('base64'),
      'Basic ' + Buffer.from(USER + ':' + PASS + 'ñ').toString('base64'), 'Basic ' + Buffer.from(USER + ':' + PASS + '\n').toString('base64'),
      'Basic ' + 'A'.repeat(800), 'Digest username="x"', ''];
    for (const value of bad) expectChallenge(await gateDefault(event({ url: '/espacio', h: { ...NAV, authorization: value } })), value.slice(0, 40));
  });
  let minted = '';
  await test('Basic válido en navegación → 302 a la misma URL con cookie de puerta correcta', async () => {
    const t0 = now();
    const o = await gateDefault(event({ url: '/espacio', h: { ...NAV, authorization: basic(USER, PASS) } }));
    eq(o.statusCode, 302, 'status');
    eq(o.headers.location.value, '/espacio', 'Location');
    eq(o.headers['cache-control'].value, 'no-store', 'cache-control');
    const c = o.cookies[COOKIE];
    assert(c, 'no hay Set-Cookie de puerta');
    const attrs = c.attributes.split(';').map((s) => s.trim());
    for (const a of ['Path=/', 'Secure', 'HttpOnly', 'SameSite=Lax']) assert(attrs.includes(a), `falta ${a}`);
    assert(!attrs.some((a) => /^domain=/i.test(a)), 'no debe llevar Domain');
    const maxAge = Number((attrs.find((a) => a.startsWith('Max-Age=')) || '').slice(8));
    assert(maxAge >= 7 * 86400, `Max-Age ${maxAge} < 7 días`);
    const m = /^v1\.(\d{10})\.([0-9a-f]{64})$/.exec(c.value);
    assert(m, 'formato de la cookie');
    const exp = Number(m[1]);
    assert(exp >= t0 + TTL && exp <= now() + TTL, 'caducidad = ahora + TTL');
    eq(m[2], sign(m[1]), 'firma HMAC de la caducidad');
    for (const s of SECRETS()) assert(!c.value.includes(s), 'la cookie contiene un secreto');
    minted = c.value;
  });
  await test('esquema "basic" en minúsculas y espacios extra → también vale', async () => {
    for (const value of ['basic ' + B64CRED, '  Basic   ' + B64CRED + '  ']) eq((await gateDefault(event({ url: '/espacio', h: { ...NAV, authorization: value } }))).statusCode, 302, value.slice(0, 8));
  });
  await test('el 302 conserva la query tal cual (vueltas de login, pago, Drive y Cloud)', async () => {
    const urls = ['/?auth=return', '/?auth=return&error=access_denied', '/?billing=manage', '/?billing=return', '/?drive=return', '/?cloud=error',
      '/espacio?estudio=clip', '/ayuda?q=a%20b%26c%3D1', '/?auth=return&grant=chatgpt-plan', '/espacio?a=1&a=2&b='];
    for (const url of urls) {
      const o = await gateDefault(event({ url, h: { ...NAV, authorization: basic(USER, PASS) } }));
      eq(o.statusCode, 302, url);
      eq(o.headers.location.value, url, `Location de ${url}`);
    }
  });
  await test('el 302 nunca redirige fuera del host (barras iniciales colapsadas)', async () => {
    for (const [url, loc] of [['//evil.example/x', '/evil.example/x'], ['///evil.example', '/evil.example'], ['/\\evil.example/x', '/evil.example/x']]) {
      const o = await gateDefault(event({ url, h: { ...NAV, authorization: basic(USER, PASS) } }));
      eq(o.statusCode, 302, url);
      eq(o.headers.location.value, loc, url);
    }
  });
  await test('flujo completo: reto → 302 → misma URL con cookie (y Basic aún adjunto) → app', async () => {
    expectChallenge(await gateDefault(event({ url: '/espacio', h: NAV })), 'paso 1');
    const second = await gateDefault(event({ url: '/espacio', h: { ...NAV, authorization: basic(USER, PASS) } }));
    eq(second.statusCode, 302, 'paso 2');
    const cookie = second.cookies[COOKIE].value;
    const third = await gateDefault(event({ url: '/espacio', h: { ...NAV, authorization: basic(USER, PASS) }, c: [[COOKIE, cookie], SESSION] }));
    expectRequest(third, '/spa.html', 'paso 3');
    eq(third.cookies.uonify_session.value, SESSION[1], 'la sesión del backend se conserva');
    expectRequest(await gateDefault(event({ url: '/assets/HomePage-DZz_Bmyo.js', h: SUB('script', 'cors'), c: [[COOKIE, cookie]] })), '/assets/HomePage-DZz_Bmyo.js', 'subrecurso con cookie');
    expectRequest(await gateApi(event({ url: '/api/auth/session', h: SUB('empty', 'cors'), c: [[COOKIE, cookie], SESSION] })), '/api/auth/session', 'API con la cookie emitida');
  });
  await test('cookie caducada → reto en navegación y 403 en subrecurso', async () => {
    for (const exp of [now() - 1, now() - 86400, now()]) {
      const c = [[COOKIE, mint(exp)]];
      expectChallenge(await gateDefault(event({ url: '/espacio', h: NAV, c })), `exp ${exp - now()}`);
      expect403(await gateDefault(event({ url: '/assets/HomePage-DZz_Bmyo.js', h: SUB('script', 'cors'), c })), `exp ${exp - now()}`);
    }
  });
  await test('cookie manipulada → rechazada', async () => {
    const good = mint();
    const [v, exp, sig] = good.split('.');
    const flip = (s, i) => s.slice(0, i) + (s[i] === 'a' ? 'b' : 'a') + s.slice(i + 1);
    const tampered = [`${v}.${exp}.${flip(sig, 0)}`, `${v}.${exp}.${flip(sig, 63)}`, `${v}.${Number(exp) + 1}.${sig}`, `${v}.${Number(exp) - 100}.${sig}`, `v2.${exp}.${sig}`,
      `${v}.${exp}.${sig.toUpperCase()}`, `${v}.${exp}.${sig}x`, `${v}.${exp}`, `${v}.${exp}.${sig.slice(0, 63)}`, `${v}..${sig}`, '', 'v1.9999999999.' + sig,
      mint(now() + 3600, crypto.randomBytes(32).toString('hex')), mint(now() + TTL + 3600), ` ${good}`, `${good};`, Buffer.from(good).toString('base64')];
    for (const value of tampered) {
      expectChallenge(await gateDefault(event({ url: '/espacio', h: NAV, c: [[COOKIE, value]] })), `default ${value.slice(0, 30)}`);
      expectGateJson(await gateApi(event({ url: '/api/auth/session', c: [[COOKIE, value]] })), `api ${value.slice(0, 30)}`);
    }
  });
  await test('cookie al límite: exp = ahora + TTL vale; con otro nombre no vale', async () => {
    expectRequest(await gateDefault(event({ url: '/espacio', h: NAV, c: [[COOKIE, mint(now() + TTL)]] })), '/spa.html', 'límite');
    expectChallenge(await gateDefault(event({ url: '/espacio', h: NAV, c: [['uonify_gate', mint()]] })), 'sin prefijo __Host-');
  });
  await test('cookies duplicadas (cookie tossing): una inválida delante no bloquea a la válida', async () => {
    expectRequest(await gateDefault(event({ url: '/espacio', h: NAV, c: [[COOKIE, 'basura'], [COOKIE, mint()]] })), '/spa.html', 'default');
    expectRequest(await gateApi(event({ url: '/api/auth/session', c: [[COOKIE, 'basura'], [COOKIE, mint()]] })), '/api/auth/session', 'api');
  });
  await test('rotación de la clave HMAC invalida todas las cookies anteriores', async () => {
    const old = mint();
    resetStore({ gate_cred_sha256: HASH, gate_hmac_key: crypto.randomBytes(32).toString('hex') });
    expectChallenge(await gateDefault(event({ url: '/espacio', h: NAV, c: [[COOKIE, old]] })), 'default');
    expectGateJson(await gateApi(event({ url: '/api/auth/session', c: [[COOKIE, old]] })), 'api');
    resetStore();
  });
  await test('KVS vacío o con valores inválidos → la puerta falla cerrada (lo público sigue)', async () => {
    const broken = [{}, { gate_cred_sha256: HASH }, { gate_hmac_key: KEY }, { gate_cred_sha256: HASH, gate_hmac_key: 'corta' }, { gate_cred_sha256: HASH, gate_hmac_key: '' },
      { gate_cred_sha256: 'no-es-hex', gate_hmac_key: KEY }, { gate_cred_sha256: HASH.toUpperCase(), gate_hmac_key: KEY }];
    for (const values of broken) {
      resetStore(values);
      const label = JSON.stringify(Object.keys(values));
      const withBasic = await gateDefault(event({ url: '/espacio', h: { ...NAV, authorization: basic(USER, PASS) } }));
      if (values.gate_cred_sha256 === HASH && values.gate_hmac_key === KEY) continue;
      expectChallenge(withBasic, `Basic con KVS ${label}`);
      if (values.gate_hmac_key !== KEY) {
        expectChallenge(await gateDefault(event({ url: '/espacio', h: NAV, c: [[COOKIE, mint()]] })), `cookie con KVS ${label}`);
        expectGateJson(await gateApi(event({ url: '/api/auth/session', c: [[COOKIE, mint()]] })), `api con KVS ${label}`);
        if (values.gate_hmac_key) {
          const forged = 'v1.' + (now() + 3600) + '.' + crypto.createHmac('sha256', values.gate_hmac_key).update('uonify-dev-gate|v1|' + (now() + 3600)).digest('hex');
          expectGateJson(await gateApi(event({ url: '/api/auth/session', c: [[COOKIE, forged]] })), `cookie forjada con clave corta ${label}`);
        }
      }
      expectRequest(await gateDefault(event({ url: '/privacidad', h: NAV })), '/privacidad/index.nojs.html', `público con KVS ${label}`);
      expectRequest(await gateApi(event({ url: '/api/health' })), '/api/health', `health con KVS ${label}`);
    }
    resetStore();
  });
  await test('rutas públicas y exentas no leen el KVS', async () => {
    KVS_READS.length = 0;
    await gateDefault(event({ url: '/web/home-v22-propuesta/index.html', h: NAV }));
    await gateDefault(event({ url: PUBLIC_ASSETS[0], h: SUB('style') }));
    await gateApi(event({ url: '/api/health' }));
    eq(KVS_READS.length, 0, 'lecturas del KVS');
  });
  await test('HEAD se trata igual que GET', async () => {
    expectRequest(await gateDefault(event({ method: 'HEAD', url: '/espacio', h: NAV, c: [[COOKIE, mint()]] })), '/spa.html', 'HEAD con cookie');
    expect403(await gateDefault(event({ method: 'HEAD', url: '/espacio', h: SUB('empty', 'cors') })), 'HEAD sin cookie');
  });

  group = '3 · reescrituras (con cookie)';
  const withCookie = (url, h = NAV) => gateDefault(event({ url, h, c: [[COOKIE, mint()], SESSION] }));
  await test('«/» con auth, billing, drive, cloud o view → /spa.html, query intacta', async () => {
    for (const url of ['/?auth=return', '/?auth=return&error=x', '/?billing=manage', '/?billing=return', '/?billing=cancel', '/?drive=return', '/?drive=error', '/?cloud=return',
      '/?cloud=error', '/?view=espacio&service=erp', '/index.html?auth=return', '/index.html?view=espacio', '/index.html?view=privacidad', '/index.html?view=terminos']) {
      const e = event({ url, h: NAV, c: [[COOKIE, mint()]] });
      const o = await gateDefault(e);
      expectRequest(o, '/spa.html', url);
      deepEq(o.querystring, e.request.querystring, `${url} (query)`);
    }
  });
  await test('«/» sin vuelta de app → objeto raíz del bucket (sin tocar)', async () => {
    for (const url of ['/', '/index.html', '/?utm_source=x', '/?authx=1']) expectRequest(await withCookie(url), url.split('?')[0], url);
  });
  await test('las 39 rutas prerenderizadas → su index.html (con y sin barra final)', async () => {
    eq(PRERENDERED.length, gen.listPrerendered(DIST).length, 'número de rutas');
    for (const r of PRERENDERED) {
      for (const url of [r, r + '/']) {
        const o = await withCookie(url);
        expectRequest(o, r + '/index.html', url);
        assert(inBucket(o.uri), `${o.uri} no estaría en el bucket`);
      }
    }
  });
  await test('rutas de la app sin prerender → /spa.html', async () => {
    for (const url of ['/espacio', '/espacio/', '/espacio/hilo/123', '/admin', '/admin/clientes', '/producto/ABC-1/ficha', '/ayuda/no-existe', '/onboarding', '/espacio?estudio=clip', '/assets', '/api']) {
      const o = await withCookie(url);
      expectRequest(o, '/spa.html', url);
      assert(inBucket(o.uri), 'spa.html no estaría en el bucket');
    }
  });
  await test('los 7 *.html del prototipo → /spa.html; index.html es alias de «/»', async () => {
    for (const name of ['producto', 'como-funciona', 'para-empresas', 'empresa', 'novedades', 'privacidad', 'terminos']) expectRequest(await withCookie(`/${name}.html`), '/spa.html', name);
    expectRequest(await withCookie('/index.html'), '/index.html', 'index.html');
  });
  await test('un .js/.css/… que no existe NUNCA se convierte en HTML', async () => {
    for (const url of ['/assets/no-existe-1234.js', '/assets/no-existe.css', '/assets/index-CBBAzHmR.js.map', '/assets/x.mjs', '/assets/data.json', '/assets/brands/nada.png', '/mockServiceWorker.js',
      '/assets/browser-pszBPX4d.js', '/assets/sobre-uonify/PROMPTS.md', '/nada.txt']) {
      const o = await withCookie(url, SUB(url.endsWith('.css') ? 'style' : 'script', 'cors'));
      expectRequest(o, url, url);
      assert(!inBucket(url), `${url} no debería estar en el bucket`);
    }
  });
  await test('ficheros existentes y /web/* con cookie → sin reescribir', async () => {
    for (const url of ['/spa.html', '/assets/HomePage-DZz_Bmyo.js', '/assets/index-Ct_aZtnx.css', '/robots.txt', '/web/home-v22-propuesta/index.html', '/sitemap.xml']) {
      const o = await withCookie(url, SUB('script', 'cors'));
      expectRequest(o, url, url);
    }
  });

  group = '4 · modos alternativos generados (--root-gated, --legal-js)';
  await test('--root-gated: «/» exige la puerta; con cookie sigue siendo el objeto raíz', async () => {
    const built = gen.build(DIST, { rootPublic: false, nojs: true });
    const handler = wrap(loadSource(gen.replaceBlock(defaultSource, built.block)));
    expectChallenge(await handler(event({ url: '/', h: NAV })), '/ sin cookie');
    expect403(await handler(event({ url: '/', h: SUB('empty', 'cors') })), '/ subrecurso');
    expectRequest(await handler(event({ url: '/', h: NAV, c: [[COOKIE, mint()]] })), '/', '/ con cookie');
    expectRequest(await handler(event({ url: '/privacidad', h: NAV })), '/privacidad/index.nojs.html', 'privacidad sigue pública');
  });
  await test('--legal-js: página legal original y cierre exacto de su JS públicos; el resto del JS no', async () => {
    const built = gen.build(DIST, { rootPublic: true, nojs: false });
    const src = gen.replaceBlock(defaultSource, built.block);
    assert(Buffer.byteLength(src) <= gen.MAX_FUNCTION_BYTES, 'tamaño en modo --legal-js');
    const handler = wrap(loadSource(src));
    expectRequest(await handler(event({ url: '/privacidad', h: NAV })), '/privacidad/index.html', 'privacidad');
    assert(built.assets.some((p) => /LegalPage-.*\.js$/.test(p)), 'falta el chunk perezoso de la ruta legal');
    for (const p of built.assets) expectRequest(await handler(event({ url: p, h: SUB('script', 'cors') })), p, p);
    expect403(await handler(event({ url: '/assets/HomePage-DZz_Bmyo.js', h: SUB('script', 'cors') })), 'HomePage');
    expect403(await handler(event({ url: '/assets/AdminApp-CzCffq3p.js', h: SUB('script', 'cors') })), 'AdminApp');
  });

  group = '5 · gate-api (/api/*, WebSocket de voz)';
  await test('GET/HEAD /api/health y POST del webhook de Stripe pasan sin cookie', async () => {
    for (const [method, url] of [['GET', '/api/health'], ['HEAD', '/api/health'], ['POST', '/api/billing/stripe/webhook']]) {
      const e = event({ method, url, h: { authorization: basic(USER, PASS), 'stripe-signature': 't=1,v1=abc', 'content-type': 'application/json' } });
      const o = await gateApi(e);
      expectRequest(o, url, `${method} ${url}`);
      deepEq(o.querystring, e.request.querystring, 'query');
      if (method === 'POST') eq(o.headers['stripe-signature'].value, 't=1,v1=abc', 'stripe-signature');
    }
  });
  await test('el resto de /api sin cookie → 401 JSON gate_required (sin WWW-Authenticate)', async () => {
    const cases = [['GET', '/api/auth/session'], ['POST', '/api/uony/messages'], ['GET', '/api/billing/stripe/webhook'], ['PUT', '/api/health'], ['GET', '/api/health/'],
      ['GET', '/api/HEALTH'], ['GET', '/api/health/../uony/messages'], ['GET', '/api/health|x'], ['POST', '/api/billing/stripe/webhook/'], ['GET', '/api/admin/auth/session'],
      ['GET', '/api/auth/google/callback?code=x&state=y'], ['OPTIONS', '/api/uony/messages']];
    for (const [method, url] of cases) expectGateJson(await gateApi(event({ method, url, h: NAV })), `${method} ${url}`);
  });
  await test('Basic válido nunca sustituye a la cookie en /api', async () => {
    expectGateJson(await gateApi(event({ url: '/api/auth/session', h: { ...NAV, authorization: basic(USER, PASS) } })), 'Basic en /api');
  });
  await test('con cookie: URI y query intactas, Authorization y cookie de puerta fuera, resto intacto', async () => {
    const e = event({
      method: 'POST', url: '/api/uony/messages',
      h: { origin: 'https://dev.uonify.com', 'content-type': 'application/json', 'content-length': '42', authorization: basic(USER, PASS), 'x-forwarded-for': '198.51.100.1' },
      c: [[COOKIE, mint()], SESSION, ['uonify_oauth', 'o']],
    });
    const o = await gateApi(e);
    expectRequest(o, '/api/uony/messages', 'messages');
    deepEq(o.querystring, {}, 'query');
    for (const k of ['origin', 'content-type', 'content-length', 'host', 'x-forwarded-for']) deepEq(o.headers[k], e.request.headers[k], k);
    deepEq(Object.keys(o.cookies).sort(), ['uonify_oauth', 'uonify_session'], 'cookies reenviadas');
  });
  await test('vuelta de Google (/api/auth/google/callback) con cookie: query idéntica', async () => {
    const e = event({ url: '/api/auth/google/callback?state=drive_abc123&code=4%2F0AbCdEf&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive.file', h: NAV, c: [[COOKIE, mint()]] });
    const o = await gateApi(e);
    expectRequest(o, '/api/auth/google/callback', 'callback');
    deepEq(o.querystring, e.request.querystring, 'query');
  });
  const bridgeAccepts = (req, origin = 'https://dev.uonify.com') => {
    // Réplica de las precondiciones de cabecera de uony_live_bridge._identity (imagen API, :175-176).
    const origins = req.headers.origin ? (req.headers.origin.multiValue || [req.headers.origin]).map((x) => x.value) : [];
    return JSON.stringify(origins) === JSON.stringify([origin]) && Object.keys(req.querystring || {}).length === 0 && !req.headers.authorization;
  };
  const wsEvent = (c, extra = {}) => event({
    url: '/api/uony/live',
    h: { origin: 'https://dev.uonify.com', 'sec-websocket-key': crypto.randomBytes(16).toString('base64'), 'sec-websocket-version': '13',
      'sec-websocket-extensions': 'permessage-deflate; client_max_window_bits', 'sec-fetch-mode': 'websocket', 'sec-fetch-dest': 'websocket',
      'sec-fetch-site': 'same-origin', authorization: basic(USER, PASS), ...extra },
    c,
  });
  await test('handshake WebSocket /api/uony/live con cookie → pasa sin Authorization ni query', async () => {
    const e = wsEvent([[COOKIE, mint()], SESSION]);
    assert(!bridgeAccepts(e.request), 'control: sin la función el puente lo rechazaría (Authorization)');
    const o = await gateApi(e);
    expectRequest(o, '/api/uony/live', 'ws');
    deepEq(o.querystring, {}, 'query');
    for (const k of ['sec-websocket-key', 'sec-websocket-version', 'sec-websocket-extensions', 'origin']) deepEq(o.headers[k], e.request.headers[k], k);
    eq(o.cookies.uonify_session.value, SESSION[1], 'cookie de sesión');
    assert(bridgeAccepts(o), 'el puente de voz rechazaría el handshake');
  });
  await test('handshake WebSocket sin cookie, caducada o manipulada → 401 JSON', async () => {
    for (const c of [[], [SESSION], [[COOKIE, mint(now() - 5)]], [[COOKIE, mint().replace(/.$/, (x) => (x === '0' ? '1' : '0'))]]]) expectGateJson(await gateApi(wsEvent(c)), JSON.stringify(c).slice(0, 40));
  });
  await test('cookie emitida por gate-default ↔ aceptada por gate-api (mismo formato)', async () => {
    assert(minted, 'no hay cookie emitida en el grupo 2');
    expectRequest(await gateApi(event({ url: '/api/auth/session', c: [[COOKIE, minted]] })), '/api/auth/session', 'api');
  });

  group = '6 · comprobaciones estáticas';
  await test('tamaño de cada función ≤ 10 KB (cuota de CloudFront Functions)', async () => {
    for (const f of [DEFAULT_FILE, API_FILE]) {
      const n = fs.statSync(f).size;
      assert(n <= gen.MAX_FUNCTION_BYTES, `${path.basename(f)} ocupa ${n} bytes`);
    }
  });
  await test('solo sintaxis y APIs del runtime cloudfront-js-2.0 (AST con acorn)', async () => {
    let acorn;
    try {
      acorn = createRequire(import.meta.url)(ACORN);
    } catch {
      throw new Error(`acorn no disponible en ${ACORN} (GATE_ACORN)`);
    }
    for (const f of [DEFAULT_FILE, API_FILE]) checkRuntime(acorn, fs.readFileSync(f, 'utf8'), path.basename(f));
  });
  await test('constantes compartidas idénticas en las dos funciones', async () => {
    const api = fs.readFileSync(API_FILE, 'utf8');
    for (const re of [/var COOKIE = '[^']+';/, /var TTL = \d+;/, /var SKEW = \d+;/, /var K_HMAC = '[^']+';/, /'uonify-dev-gate\|v1\|'/, /\/\^v1\\\.\(\\d\{10\}\)\\\.\(\[0-9a-f\]\{64\}\)\$\//]) {
      const a = re.exec(defaultSource);
      const b = re.exec(api);
      assert(a && b && a[0] === b[0], `difieren: ${re}`);
    }
  });
  await test('el bloque GENERATED y public-pages/ coinciden con el dist (build_gate --check)', async () => {
    const built = gen.build(DIST, { rootPublic: /var ROOT_PUBLIC = true;/.test(defaultSource), nojs: /var LEGAL_NOJS = true;/.test(defaultSource) });
    eq(generatedNow, built.block, 'bloque');
    for (const [name, html] of Object.entries(built.variants)) eq(fs.readFileSync(path.join(PAGES_DIR, name), 'utf8'), html, name);
  });
  await test('LEGACY = links.ts LEGACY_FILES (sin index.html, alias de «/»)', async () => {
    const links = fs.readFileSync(path.join(FRONT_SRC, 'modules/public-site/model/links.ts'), 'utf8');
    const pages = /LEGACY_PAGES[^=]*=\s*\[([^\]]*)\]/.exec(links)[1].match(/'([^']+)'/g).map((s) => s.slice(1, -1));
    assert(/LEGACY_FILES[^=]*=\s*\['index\.html',\s*\.\.\.LEGACY_PAGES/.test(links), 'LEGACY_FILES cambió de forma');
    const legacy = /var LEGACY = '\|(.*)\|';/.exec(defaultSource)[1].split('|');
    deepEq(legacy, pages.map((p) => `/${p}.html`), 'LEGACY');
  });
  await test('los 301 de las legales antiguas van a las rutas de la app (views.ts) y LegacyRedirect sigue igual', async () => {
    const views = fs.readFileSync(path.join(FRONT_SRC, 'modules/public-site/model/views.ts'), 'utf8');
    for (const page of ['privacidad', 'terminos']) {
      assert(new RegExp(`\\b${page}: \\{[^}]*?path: '/${page}'`).test(views), `PUBLIC_VIEWS.${page}.path ya no es /${page}`);
    }
    const links = fs.readFileSync(path.join(FRONT_SRC, 'modules/public-site/model/links.ts'), 'utf8');
    assert(/LEGACY_PAGES[^=]*=\s*\[[^\]]*'privacidad'[^\]]*'terminos'/.test(links), 'privacidad y terminos ya no están en LEGACY_PAGES');
    assert(/searchParams\.get\('view'\)/.test(links) && /isPublicViewKey\(requested\)/.test(links), 'toAppHref ya no traduce index.html?view=…');
  });
  await test('APPQ cubre todas las vueltas del backend a «/?…» (auth, billing, drive, cloud)', async () => {
    const keys = new Set();
    for (const f of fs.readdirSync(BACKEND_SRC).filter((x) => x.endsWith('.py'))) {
      const code = fs.readFileSync(path.join(BACKEND_SRC, f), 'utf8');
      for (const m of code.matchAll(/(?:origin\s*\+\s*'|origin\}|origin \+ ')\/\?([a-z]+)=/g)) keys.add(m[1]);
      for (const m of code.matchAll(/'\/\?([a-z]+)=/g)) keys.add(m[1]);
    }
    const settings = fs.readFileSync(path.join(BACKEND_SRC, 'settings.py'), 'utf8');
    for (const m of settings.matchAll(/origin \+ '\/\?([a-z]+)=/g)) keys.add(m[1]);
    for (const k of ['auth', 'billing', 'drive', 'cloud']) assert(keys.has(k), `no se ha encontrado la vuelta ${k} en el backend`);
    const appq = /var APPQ = \[([^\]]*)\];/.exec(defaultSource)[1];
    for (const k of keys) assert(appq.includes(`'${k}'`), `APPQ no incluye ${k}`);
  });
  await test('las rutas exentas existen en el backend (health y webhook de Stripe)', async () => {
    const main = fs.readFileSync(path.join(BACKEND_SRC, 'main.py'), 'utf8');
    const checkout = fs.readFileSync(path.join(BACKEND_SRC, 'billing_checkout.py'), 'utf8');
    assert(/@app\.get\('\/api\/health'\)/.test(main), 'GET /api/health');
    assert(/APIRouter\(prefix='\/api\/billing'\)/.test(checkout) && /@router\.post\('\/stripe\/webhook'\)/.test(checkout), 'POST /api/billing/stripe/webhook');
    const bridge = fs.readFileSync(path.join(BACKEND_SRC, 'uony_live_bridge.py'), 'utf8');
    assert(/websocket\.query_params/.test(bridge) && /headers\.get\('authorization'\)/.test(bridge), 'el puente sigue rechazando query/Authorization (precondición del test)');
  });
  await test('nombres de las claves del KVS iguales en el script y en las funciones', async () => {
    const sh = fs.readFileSync(SCRIPT, 'utf8');
    eq(/K_HASH="([^"]+)"/.exec(sh)[1], /var K_HASH = '([^']+)'/.exec(defaultSource)[1], 'K_HASH');
    eq(/K_HMAC="([^"]+)"/.exec(sh)[1], /var K_HMAC = '([^']+)'/.exec(defaultSource)[1], 'K_HMAC');
    eq(/KVS_NAME="\$\{KVS_NAME:-([^}]+)\}"/.exec(sh)[1], 'uonify-dev-gate', 'KVS_NAME');
  });

  group = '7 · set_gate_credentials.sh y run_test_function.mjs con AWS CLI falso';
  if (process.env.GATE_SKIP_SCRIPT !== '1') await scriptTests();

  group = '8 · deploy_edge.mjs (paso 13: KVS, funciones, /api/* y origen) con AWS CLI falso';
  if (process.env.GATE_SKIP_SCRIPT !== '1') {
    await deployTests({ test, assert, eq, deepEq, HERE, FAKE_BIN, TMP, DIST, DEPLOY });
    fs.rmSync(TMP, { recursive: true, force: true });
  }

  group = '9 · ninguna salida filtra secretos (todas las invocaciones anteriores)';
  await test('ni la clave HMAC, ni el hash, ni la contraseña, ni el Basic en ninguna salida', async () => {
    assert(OUTPUTS.length > 200, `pocas salidas analizadas (${OUTPUTS.length})`);
    const all = JSON.stringify(OUTPUTS);
    for (const s of SECRETS()) assert(!all.includes(s), 'una salida contiene un secreto');
    for (const o of OUTPUTS) if (!isRequest(o)) {
      const text = JSON.stringify(o);
      assert(!/gate_cred_sha256|gate_hmac_key|uonify-dev-gate\|v1/.test(text), 'una respuesta menciona el KVS o el mensaje firmado');
    }
  });
}

// ── reglas del runtime cloudfront-js-2.0 sobre el AST ────────────────────────
function checkRuntime(acorn, src, label) {
  const ast = acorn.parse(src, { ecmaVersion: 2022, sourceType: 'module' });
  const banned = new Set(['ClassDeclaration', 'ClassExpression', 'ObjectPattern', 'ArrayPattern', 'SpreadElement', 'ForOfStatement', 'AssignmentPattern',
    'ChainExpression', 'YieldExpression', 'TaggedTemplateExpression', 'MetaProperty', 'ImportExpression', 'WithStatement', 'ExportNamedDeclaration', 'ExportDefaultDeclaration']);
  const bannedGlobals = new Set(['Map', 'Set', 'WeakMap', 'WeakSet', 'Proxy', 'Reflect', 'setTimeout', 'setInterval', 'setImmediate', 'require', 'process', 'eval', 'Function',
    'console', 'fetch', 'XMLHttpRequest', 'Buffer', 'structuredClone', 'queueMicrotask', 'BigInt']);
  let handler = false;
  const visit = (node, parent) => {
    if (!node || typeof node.type !== 'string') return;
    if (banned.has(node.type)) throw new Error(`${label}: ${node.type} no está en cloudfront-js-2.0`);
    if (node.type === 'LogicalExpression' && node.operator === '??') throw new Error(`${label}: ?? no soportado`);
    if ((node.type === 'FunctionExpression' || node.type === 'ArrowFunctionExpression') && node.async) throw new Error(`${label}: closure async no soportada`);
    if (node.type === 'FunctionDeclaration' && node.async && parent.type !== 'Program') throw new Error(`${label}: async anidada`);
    if (node.generator) throw new Error(`${label}: generadores no soportados`);
    // Estilo conservador para njs: await solo como valor de una declaración o asignación simple.
    if (node.type === 'AwaitExpression' && !['VariableDeclarator', 'AssignmentExpression'].includes(parent.type)) throw new Error(`${label}: await dentro de una expresión (${parent.type})`);
    if (node.type === 'Literal' && node.regex && /[^gim]/.test(node.regex.flags)) throw new Error(`${label}: flag de regex ${node.regex.flags}`);
    if (node.type === 'ImportDeclaration') {
      if (!['cloudfront', 'crypto'].includes(node.source.value) || node.specifiers.length !== 1 || node.specifiers[0].type !== 'ImportDefaultSpecifier') throw new Error(`${label}: import no permitido`);
      return;
    }
    if (node.type === 'Identifier' && bannedGlobals.has(node.name)) throw new Error(`${label}: usa ${node.name}`);
    if (node.type === 'FunctionDeclaration' && node.id && node.id.name === 'handler' && parent.type === 'Program' && node.async) handler = true;
    for (const [key, value] of Object.entries(node)) {
      if (key === 'type' || key === 'start' || key === 'end') continue;
      if (node.type === 'MemberExpression' && key === 'property' && !node.computed) continue;
      if (node.type === 'Property' && key === 'key' && !node.computed) continue;
      if (Array.isArray(value)) value.forEach((child) => visit(child, node));
      else if (value && typeof value.type === 'string') visit(value, node);
    }
  };
  visit(ast, null);
  if (!handler) throw new Error(`${label}: falta async function handler(event) de primer nivel`);
}

// ── pruebas del script del dueño con el AWS CLI falso ────────────────────────
async function scriptTests() {
  fs.mkdirSync(TMP, { recursive: true });
  const state = path.join(TMP, 'kvs-state.json');
  const log = path.join(TMP, 'aws-argv.log');
  const scratchTmp = path.join(TMP, 'tmpdir');
  const reset = (items = {}) => {
    fs.writeFileSync(state, JSON.stringify({ etag: 'ETAG-0', items, status: 'READY' }));
    fs.writeFileSync(log, '');
    fs.rmSync(scratchTmp, { recursive: true, force: true });
    fs.mkdirSync(scratchTmp, { recursive: true });
  };
  const readState = () => JSON.parse(fs.readFileSync(state, 'utf8'));
  const runScript = (args, input, extraEnv = {}, bashArgs = []) => spawnSync('bash', [...bashArgs, SCRIPT, ...args], {
    input,
    encoding: 'utf8',
    env: { ...process.env, PATH: FAKE_BIN + ':' + process.env.PATH, FAKE_KVS_STATE: state, FAKE_AWS_LOG: log, TMPDIR: scratchTmp, AWS_PROFILE: 'perfil-de-prueba', ...extraEnv },
  });
  fs.chmodSync(path.join(FAKE_BIN, 'aws'), 0o755);
  const pass = 'Prueba-' + crypto.randomBytes(15).toString('base64url');
  const user = 'equipo.dev';
  EXTRA_SECRETS.push(pass, sha256(user + ':' + pass), Buffer.from(user + ':' + pass).toString('base64'));
  const noLeak = (r, label) => {
    const st = readState();
    const secrets = [pass, sha256(user + ':' + pass), ...Object.values(st.items)];
    const argv = fs.readFileSync(log, 'utf8');
    for (const s of secrets) {
      assert(!r.stdout.includes(s) && !r.stderr.includes(s), `${label}: la salida del script contiene un secreto`);
      assert(!argv.includes(s), `${label}: un secreto viaja como argumento de aws`);
    }
    assert(fs.readdirSync(scratchTmp).length === 0, `${label}: quedan temporales: ${fs.readdirSync(scratchTmp)}`);
  };

  await test('bash -n (sintaxis, bash 3.2 de macOS)', async () => {
    const r = spawnSync('/bin/bash', ['-n', SCRIPT], { encoding: 'utf8' });
    eq(r.status, 0, 'bash -n ' + r.stderr);
  });
  let firstKey = '';
  await test('alta: guarda SHA-256(usuario:contraseña) y una clave HMAC nueva, sin enseñar nada', async () => {
    reset();
    const r = runScript([], `${user}\n${pass}\n${pass}\n`);
    eq(r.status, 0, 'exit ' + r.stderr);
    const st = readState();
    eq(st.items.gate_cred_sha256, sha256(user + ':' + pass), 'hash guardado');
    assert(/^[0-9a-f]{64}$/.test(st.items.gate_hmac_key), 'clave HMAC de 64 hex');
    eq(st.putsFiles.length, 1, 'una sola escritura atómica');
    eq(st.putsFiles[0].mode, 0o600, 'permisos del fichero temporal');
    assert(!fs.existsSync(st.putsFiles[0].path), 'el fichero temporal sigue existiendo');
    noLeak(r, 'alta');
    assert(/Hecho/.test(r.stderr), 'mensaje final');
    firstKey = st.items.gate_hmac_key;
  });
  await test('integración: con lo que guarda el script, la puerta acepta ese usuario y contraseña', async () => {
    const st = readState();
    resetStore({ gate_cred_sha256: st.items.gate_cred_sha256, gate_hmac_key: st.items.gate_hmac_key });
    const o = await gateDefault(event({ url: '/espacio', h: { ...NAV, authorization: basic(user, pass) } }));
    eq(o.statusCode, 302, 'Basic con la contraseña del script');
    const cookie = o.cookies[COOKIE].value;
    expectRequest(await gateApi(event({ url: '/api/auth/session', c: [[COOKIE, cookie]] })), '/api/auth/session', 'cookie en /api');
    expectChallenge(await gateDefault(event({ url: '/espacio', h: { ...NAV, authorization: basic(user, pass + '!') } })), 'contraseña distinta');
    // --revoke: misma contraseña, clave nueva → la cookie anterior deja de valer
    const r = runScript(['--revoke'], '');
    eq(r.status, 0, 'revoke ' + r.stderr);
    const st2 = readState();
    eq(st2.items.gate_cred_sha256, st.items.gate_cred_sha256, 'el hash no cambia con --revoke');
    assert(st2.items.gate_hmac_key !== firstKey && /^[0-9a-f]{64}$/.test(st2.items.gate_hmac_key), 'clave rotada');
    noLeak(r, 'revoke');
    resetStore({ gate_cred_sha256: st2.items.gate_cred_sha256, gate_hmac_key: st2.items.gate_hmac_key });
    expectGateJson(await gateApi(event({ url: '/api/auth/session', c: [[COOKIE, cookie]] })), 'cookie anterior tras --revoke');
    eq((await gateDefault(event({ url: '/espacio', h: { ...NAV, authorization: basic(user, pass) } }))).statusCode, 302, 'la contraseña sigue valiendo');
    resetStore();
  });
  await test('entradas inválidas → no se escribe nada', async () => {
    const cases = [
      ['contraseñas distintas', `${user}\n${pass}\n${pass}x\n`],
      ['contraseña corta', `${user}\ncorta-123\ncorta-123\n`],
      ['contraseña con ñ', `${user}\nContraseñaMuyLarga-1234\nContraseñaMuyLarga-1234\n`],
      ['usuario con dos puntos', `equipo:dev\n${pass}\n${pass}\n`],
      ['usuario vacío', `\n${pass}\n${pass}\n`],
      ['contraseña = usuario', `usuario-muy-largo-123\nusuario-muy-largo-123\nusuario-muy-largo-123\n`],
      ['sin entrada', ''],
    ];
    for (const [label, input] of cases) {
      reset({ gate_cred_sha256: 'a'.repeat(64), gate_hmac_key: 'b'.repeat(64) });
      const r = runScript([], input);
      assert(r.status !== 0, `${label}: debería fallar`);
      const st = readState();
      deepEq(st.items, { gate_cred_sha256: 'a'.repeat(64), gate_hmac_key: 'b'.repeat(64) }, `${label}: se ha escrito algo`);
      assert(!r.stderr.includes(pass) && !r.stdout.includes(pass), `${label}: eco de la contraseña`);
      assert(fs.readdirSync(scratchTmp).length === 0, `${label}: quedan temporales`);
    }
  });
  await test('--check: dice qué claves existen sin enseñar valores', async () => {
    reset({ gate_cred_sha256: HASH, gate_hmac_key: KEY });
    const r = runScript(['--check'], '');
    eq(r.status, 0, 'exit');
    assert(/OK\s+gate_cred_sha256/.test(r.stderr) && /OK\s+gate_hmac_key/.test(r.stderr), 'salida de --check');
    assert(!r.stderr.includes(HASH) && !r.stderr.includes(KEY) && !r.stdout.includes(HASH) && !r.stdout.includes(KEY), 'enseña valores');
  });
  await test('ETag cambiado por otro → reintenta y guarda', async () => {
    reset();
    const r = runScript([], `${user}\n${pass}\n${pass}\n`, { FAKE_AWS_CONFLICT_ONCE: '1' });
    eq(r.status, 0, 'exit ' + r.stderr);
    eq(readState().items.gate_cred_sha256, sha256(user + ':' + pass), 'hash tras reintento');
    noLeak(r, 'reintento');
  });
  await test('API de datos del KVS inaccesible → sale ANTES de pedir usuario y contraseña, sin escribir', async () => {
    for (const code of ['AccessDeniedException', 'NoRegion']) {
      reset({ gate_cred_sha256: 'a'.repeat(64), gate_hmac_key: 'b'.repeat(64) });
      const r = runScript([], `${user}\n${pass}\n${pass}\n`, { FAKE_AWS_KVS_DATA_FAIL: code });
      assert(r.status !== 0, `${code}: debería fallar`);
      assert(r.stderr.includes(`(${code})`) && /no se ha cambiado nada/.test(r.stderr), `${code}: ${r.stderr}`);
      assert(!/Usuario de la puerta|Contraseña/.test(r.stderr), `${code}: ha pedido las credenciales antes de probar el API de datos`);
      deepEq(readState().items, { gate_cred_sha256: 'a'.repeat(64), gate_hmac_key: 'b'.repeat(64) }, `${code}: se ha escrito algo`);
      assert(fs.readdirSync(scratchTmp).length === 0, `${code}: quedan temporales`);
    }
  });
  await test('todas las llamadas al API de datos del KVS llevan --region us-east-1 (sin ella: NoRegion)', async () => {
    reset();
    eq(runScript([], `${user}\n${pass}\n${pass}\n`).status, 0, 'alta');
    eq(runScript(['--check'], '').status, 0, 'check');
    const data = fs.readFileSync(log, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)).filter((a) => a[0] === 'cloudfront-keyvaluestore');
    deepEq([...new Set(data.map((a) => a[1]))].sort(), ['describe-key-value-store', 'get-key', 'list-keys', 'update-keys'], 'operaciones del API de datos');
    for (const a of data) eq(a[a.indexOf('--region') + 1], 'us-east-1', `${a[1]} --region`);
  });
  await test('KeyValueStore inexistente o no READY → error claro, sin escribir', async () => {
    reset();
    fs.writeFileSync(state, JSON.stringify({ etag: 'E', items: {}, status: 'PROVISIONING' }));
    const r = runScript([], `${user}\n${pass}\n${pass}\n`);
    assert(r.status !== 0 && /no READY/.test(r.stderr), 'estado no READY');
    deepEq(readState().items, {}, 'no debe escribir');
    const r2 = runScript([], `${user}\n${pass}\n${pass}\n`, { KVS_NAME: 'otro-kvs' });
    assert(r2.status !== 0 && /no encuentro el KeyValueStore/.test(r2.stderr), 'KVS inexistente');
  });
  await test('también funciona si el dueño lo lanza con zsh o sh', async () => {
    for (const shell of ['/bin/zsh', '/bin/sh']) {
      reset();
      const r = spawnSync(shell, [SCRIPT], {
        input: `${user}\n${pass}\n${pass}\n`, encoding: 'utf8',
        env: { ...process.env, PATH: FAKE_BIN + ':' + process.env.PATH, FAKE_KVS_STATE: state, FAKE_AWS_LOG: log, TMPDIR: scratchTmp },
      });
      eq(r.status, 0, `${shell}: ${r.stderr}`);
      eq(readState().items.gate_cred_sha256, sha256(user + ':' + pass), `${shell}: hash`);
      noLeak(r, shell);
    }
  });
  await test('ejecutado con bash -x no filtra la contraseña ni el hash (set +x al inicio)', async () => {
    reset();
    const r = runScript([], `${user}\n${pass}\n${pass}\n`, {}, ['-x']);
    eq(r.status, 0, 'exit');
    noLeak(r, 'bash -x');
  });
  const KVS_ARN = 'arn:aws:cloudfront::123456789012:key-value-store/00000000-1111-2222-3333-444444444444'; // el del AWS CLI falso
  const rtfEnv = { ...process.env, PATH: FAKE_BIN + ':' + process.env.PATH, FAKE_KVS_STATE: state, FAKE_AWS_LOG: log, TMPDIR: scratchTmp };
  const rtf = (extra = []) => spawnSync(process.execPath, [RTF, '--default', 'uonify-dev-gate-default', '--api', 'uonify-dev-gate-api', ...extra], { encoding: 'utf8', env: rtfEnv });
  // Funciones «creadas» en el CloudFront falso con el código de la carpeta de run_test_function.mjs.
  const seedFunctions = (items, change = () => {}) => {
    const st = readState();
    st.items = items;
    st.functions = {};
    for (const [name, file] of [['uonify-dev-gate-default', 'gate-default.js'], ['uonify-dev-gate-api', 'gate-api.js']]) {
      const config = { Comment: 'x', Runtime: 'cloudfront-js-2.0', KeyValueStoreAssociations: { Quantity: 1, Items: [{ KeyValueStoreARN: KVS_ARN }] } };
      st.functions[name] = { DEVELOPMENT: { code: fs.readFileSync(path.join(path.dirname(RTF), file)).toString('base64'), config, etag: 'E-' + name } };
    }
    change(st);
    fs.writeFileSync(state, JSON.stringify(st));
  };
  await test('run_test_function.mjs (paso 13) con test-function simulado: comprobaciones previas y todos los casos OK', async () => {
    reset();
    seedFunctions({ gate_cred_sha256: HASH, gate_hmac_key: KEY });
    const r = rtf();
    eq(r.status, 0, 'exit ' + r.stdout + r.stderr);
    const m = /(\d+)\/(\d+) casos OK en DEVELOPMENT/.exec(r.stdout);
    assert(m && m[1] === m[2] && Number(m[2]) >= 18, r.stdout);
    assert(/OK\s+KeyValueStore uonify-dev-gate READY con gate_cred_sha256 y gate_hmac_key/.test(r.stdout), 'falta la comprobación de las claves');
    assert(/OK\s+uonify-dev-gate-api \(DEVELOPMENT\): cloudfront-js-2\.0, asociada a uonify-dev-gate, código = gate-api\.js/.test(r.stdout), 'falta la comprobación del código');
    assert(/\/privacidad\.html \(enlace antiguo\) sin cookie → 301/.test(r.stdout), 'falta el caso del 301');
    for (const s of [HASH, KEY]) assert(!r.stdout.includes(s) && !fs.readFileSync(log, 'utf8').includes(s), 'un valor del KVS sale o viaja');
    assert(fs.readdirSync(scratchTmp).length === 0, 'quedan eventos temporales');
    eq(spawnSync(process.execPath, [RTF, '--default', 'x'], { encoding: 'utf8', env: rtfEnv }).status, 64, 'uso incorrecto');
  });
  await test('run_test_function.mjs aborta (exit 2) sin ejecutar casos: sin claves en el KVS, KVS no READY, función sin ese KVS o con otro runtime, código distinto', async () => {
    const both = { gate_cred_sha256: HASH, gate_hmac_key: KEY };
    const cases = [
      ['KVS vacío', {}, () => {}, /faltan en el KeyValueStore: gate_cred_sha256, gate_hmac_key/],
      ['solo el hash', { gate_cred_sha256: HASH }, () => {}, /faltan en el KeyValueStore: gate_hmac_key/],
      ['KVS no READY', both, (st) => { st.status = 'PROVISIONING'; }, /no READY/],
      ['función sin el KVS', both, (st) => { st.functions['uonify-dev-gate-api'].DEVELOPMENT.config.KeyValueStoreAssociations = { Quantity: 0 }; }, /no está asociada solo al KeyValueStore/],
      ['runtime 1.0', both, (st) => { st.functions['uonify-dev-gate-default'].DEVELOPMENT.config.Runtime = 'cloudfront-js-1.0'; }, /no cloudfront-js-2\.0/],
      ['código distinto', both, (st) => { st.functions['uonify-dev-gate-default'].DEVELOPMENT.code = Buffer.from('// otro').toString('base64'); }, /no es gate-default\.js de esta carpeta/],
    ];
    for (const [label, items, change, message] of cases) {
      reset();
      seedFunctions(items, change);
      const r = rtf();
      eq(r.status, 2, `${label}: exit`);
      assert(message.test(r.stderr) && /No se ha probado ningún caso/.test(r.stderr), `${label}: ${r.stderr}`);
      assert(!fs.readFileSync(log, 'utf8').includes('test-function'), `${label}: ha ejecutado casos`);
      assert(fs.readdirSync(scratchTmp).length === 0, `${label}: quedan temporales`);
    }
  });
  fs.rmSync(TMP, { recursive: true, force: true });
}

// ════════════════════════════════════════════════════════════════════════════
await run();
let current = '';
let failed = 0;
for (const r of results) {
  if (r.group !== current) {
    current = r.group;
    console.log(`\n${current}`);
  }
  console.log(`  ${r.ok ? 'OK  ' : 'FALLO'} ${r.name}${r.ok ? '' : `\n        → ${r.error}`}`);
  if (!r.ok) failed += 1;
}
console.log(`\n${results.length - failed}/${results.length} pruebas OK · ${OUTPUTS.length} invocaciones de las funciones analizadas`);
process.exitCode = failed ? 1 : 0;
