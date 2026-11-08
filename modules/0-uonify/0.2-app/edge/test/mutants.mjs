#!/usr/bin/env node
// test/mutants.mjs · Comprueba que test_gate.mjs DETECTA fallos: introduce errores a propósito en
// copias (en test/mut-tmp, que se borra al acabar) de las funciones, del script del dueño, de
// run_test_function.mjs y de deploy_edge.mjs, y exige que el banco falle con cada una. Un mutante
// «superviviente» = una regla sin prueba que la defienda.
//   d gate-default.js · a gate-api.js · s set_gate_credentials.sh · r run_test_function.mjs · e deploy_edge.mjs
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const TMP = path.join(HERE, 'mut-tmp');
const files = {
  d: path.join(ROOT, 'gate-default.js'), a: path.join(ROOT, 'gate-api.js'), s: path.join(ROOT, 'set_gate_credentials.sh'),
  r: path.join(ROOT, 'run_test_function.mjs'), e: path.join(ROOT, 'deploy_edge.mjs'),
};
const only = process.argv.includes('--only') ? process.argv[process.argv.indexOf('--only') + 1] : null;

const mutants = [
  ['d', 'no borra Authorization (default)', 'delete h.authorization;', ''],
  ['d', 'toda petición es navegación', "return (mode && String(mode.value).toLowerCase() === 'navigate') ||", 'return true ||'],
  ['d', 'ignora la caducidad', '+m[1] > now && ', ''],
  ['d', 'sin tope de caducidad', ' && +m[1] <= now + TTL + SKEW', ''],
  ['d', 'sin guarda de rutas trucadas', 'if (/\\/\\/|', 'if (false && /\\/\\/|'],
  ['d', '403 con WWW-Authenticate', "return res(403, 'Forbidden', { 'content-type'", "return res(403, 'Forbidden', { 'www-authenticate': { value: 'Basic realm=\"x\"' }, 'content-type'"],
  ['d', 'fichero inexistente → spa.html', "if (uri.slice(uri.lastIndexOf('/') + 1).indexOf('.') >= 0) return uri;", ''],
  ['d', 'la clave HMAC viaja en la cookie', "value: 'v1.' + exp + '.' + sign(key, exp)", "value: 'v1.' + exp + '.' + sign(key, exp) + key"],
  ['d', 'redirección abierta', "'/' + req.uri.replace(/^[\\/\\\\]+/, '')", 'req.uri'],
  ['d', 'cookie de 6 días', 'var TTL = 691200;', 'var TTL = 518400;'],
  ['d', 'SameSite=None', 'SameSite=Lax', 'SameSite=None'],
  ['d', 'cookie con Domain', "attributes: 'Path=/;", "attributes: 'Domain=uonify.com; Path=/;"],
  ['d', 'Basic aceptado en subrecursos', 'if (!isNav(h)) {', 'if (!isNav(h) && !(await basicOk(auth))) {'],
  ['d', '/web sin barra pública', "uri.indexOf('/web/') === 0 || uri === '/robots.txt'", "uri.indexOf('/web') === 0 || uri === '/robots.txt'"],
  ['d', 'páginas legales por prefijo', "return r === '/privacidad' || r === '/terminos' ? r : '';", "return r.indexOf('/privacidad') === 0 || r === '/terminos' ? r : '';"],
  ['d', 'ignora LEGAL_NOJS', 'var dest = page && !ok ?', 'var dest = false ?'],
  ['d', 'APPQ sin billing', "var APPQ = ['auth', 'billing', 'drive', 'cloud', 'view'];", "var APPQ = ['auth', 'drive', 'cloud', 'view'];"],
  ['d', 'comparación siempre cierta', 'return d === 0;', 'return true;'],
  ['d', 'acepta claves HMAC cortas', 'k.length >= 32 ? k : null', 'k.length >= 0 ? k : null'],
  ['d', 'sin cache-control', "h['cache-control'] = { value: 'no-store' };", ''],
  ['d', 'reto sin charset UTF-8', 'Basic realm="Uonify DEV", charset="UTF-8"', 'Basic realm="Uonify DEV"'],
  ['d', 'no quita la cookie de puerta', 'delete c[COOKIE];\n  // Sin cookie', '// Sin cookie'],
  ['d', 'prerender ignorado', "return inList(PRERENDERED, r) ? r + '/index.html' : '/spa.html';", "return '/spa.html';"],
  ['d', 'legacy no va a spa.html', "if (inList(LEGACY, uri)) return '/spa.html';", ''],
  ['d', 'raíz con vuelta de app no va a spa.html', "return appQuery(qs) ? '/spa.html' : uri;", 'return uri;'],
  ['d', 'pierde la query en el 302', "(q.length ? '?' + q.join('&') : '')", "''"],
  ['d', 'legales antiguas sin 301 (piden la contraseña)', "  if (old && !ok) return res(301, 'Moved Permanently', { location: { value: old } });\n", ''],
  ['d', 'legales antiguas: 301 también con cookie', 'if (old && !ok) return res(301', 'if (old) return res(301'],
  ['d', 'legales antiguas: index.html?view= no reconocido', "var v = uri === '/index.html' && qs.view ? qs.view.value : '';", "var v = '';"],
  ['d', 'legales antiguas por prefijo', 'var m = /^\\/(privacidad|terminos)\\.html$/.exec(uri);', 'var m = /^\\/(privacidad|terminos)\\.html/.exec(uri);'],
  ['a', 'no borra Authorization (api)', 'delete req.headers.authorization;', ''],
  ['a', 'añade query', '  delete c[COOKIE];\n  return req;', "  delete c[COOKIE];\n  req.querystring = 'x=1';\n  return req;"],
  ['a', 'toca la URI', '  delete c[COOKIE];\n  return req;', "  delete c[COOKIE];\n  req.uri = req.uri + '/';\n  return req;"],
  ['a', '401 con WWW-Authenticate', "'content-type': { value: 'application/json' },", "'www-authenticate': { value: 'Basic' }, 'content-type': { value: 'application/json' },"],
  ['a', 'exención por prefijo', "OPEN.indexOf('|' + req.method + ' ' + req.uri + '|') >= 0", "req.uri.indexOf('/api/health') === 0"],
  ['a', 'exención sin método', "'|' + req.method + ' ' + req.uri + '|'", "'|GET ' + req.uri + '|'"],
  ['a', 'no quita la cookie de puerta (api)', '  delete c[COOKIE];\n  return req;', '  return req;'],
  ['a', 'ignora la caducidad (api)', '+m[1] > now && ', ''],
  ['a', 'otro cuerpo JSON', `data: '{"error":"gate_required"}'`, `data: '{"error":"unauthorized"}'`],
  ['a', 'acepta claves HMAC cortas (api)', 'key.length < 32) return false;', 'key.length < 0) return false;'],
  ['s', 'update-keys sin --region (NoRegion)', 'update-keys --kvs-arn "$arn" --region "$KVS_REGION"', 'update-keys --kvs-arn "$arn"'],
  ['s', 'ETag del KVS sin --region', 'describe-key-value-store --kvs-arn "$1" --region "$KVS_REGION"', 'describe-key-value-store --kvs-arn "$1"'],
  ['s', 'get-key sin --region', 'get-key --kvs-arn "$arn" --region "$KVS_REGION"', 'get-key --kvs-arn "$arn"'],
  ['s', 'list-keys sin --region', 'list-keys --kvs-arn "$arn" --region "$KVS_REGION"', 'list-keys --kvs-arn "$arn"'],
  ['s', 'pide la contraseña antes de probar el API de datos', '  kvs_etag "$arn" >/dev/null || exit 1\n', ''],
  ['r', 'no exige las claves del KVS', 'if (missing.length) throw new Precheck(', 'if (false) throw new Precheck('],
  ['r', 'no exige la asociación al KVS', 'if (arns.length !== 1 || arns[0] !== kvs.ARN) throw', 'if (false) throw'],
  ['r', 'no compara el código desplegado', 'if (sha256(fs.readFileSync(file)) !== sha256(fs.readFileSync(LOCAL[k]))) {', 'if (false) {'],
  ['e', 'reenvía el Host del visor (Managed-AllViewer)', "origin: ['Managed-AllViewerExceptHostHeader', 'b689b0a8-53d0-40ab-baf2-68738e2966ac']", "origin: ['Managed-AllViewer', '216adef6-5c7f-47e4-b989-5492eafa07d3']"],
  ['e', 'API con caché (CachingOptimized)', "cache: ['Managed-CachingDisabled', '4135ea2d-6df8-44a3-9df3-4b5a84be39ad']", "cache: ['Managed-CachingOptimized', '658327ea-f89d-4fab-a63d-7e88639e58f6']"],
  ['e', 'origen sin X-Origin-Verify', 'CustomHeaders: { Quantity: 1, Items: [{ HeaderName: EDGE_HEADER, HeaderValue: headerValue }] },', 'CustomHeaders: { Quantity: 0 },'],
  ['e', 'origen match-viewer', "      OriginProtocolPolicy: 'https-only',", "      OriginProtocolPolicy: 'match-viewer',"],
  ['e', 'visor redirect-to-https en /api', "ViewerProtocolPolicy: 'https-only', // con redirect", "ViewerProtocolPolicy: 'redirect-to-https', // con redirect"],
  ['e', 'keep-alive 75 s (nginx cierra antes)', 'OriginKeepaliveTimeout: 60,', 'OriginKeepaliveTimeout: 75,'],
  ['e', 'rotación: usa la línea 1 de SSM', 'value: lines[lines.length - 1]', 'value: lines[0]'],
  ['e', 'copia sin tapar la cabecera', '    h.HeaderValue = REDACTED;\n', ''],
  ['e', 'no tapa el secreto en los errores', "for (const v of SECRETS) if (v) s = s.split(v).join('«secreto»');", ''],
  ['e', 'update-distribution sin --if-match', "'--if-match', etag, '--distribution-config'", "'--distribution-config'"],
  ['e', 'escribe sin --apply', "const APPLY = flag('--apply');", 'const APPLY = true;'],
  ['e', 'publica aunque test-function falle', "  if (r.status !== 0) fatal('test-function no ha dado todo OK: no se publica nada');\n", ''],
  ['e', 'acepta respuestas de error personalizadas', 'if (cfg.CustomErrorResponses && cfg.CustomErrorResponses.Quantity > 0) problems.push(', 'if (false) problems.push('],
  ['e', 'fichero del secreto legible por otros', "fs.writeFileSync(file, text, { mode: 0o600, flag: 'wx' });\n  return file;", "fs.writeFileSync(file, text, { mode: 0o644, flag: 'wx' });\n  return file;"],
  ['e', 'HSTS con includeSubDomains', 'IncludeSubdomains: false, Preload: false, AccessControlMaxAgeSec', 'IncludeSubdomains: true, Preload: false, AccessControlMaxAgeSec'],
  ['e', 'sin política de cabeceras en /api/*', '    ResponseHeadersPolicyId: headersPolicyId,\n', ''],
  ['e', 'sin política de cabeceras en el comportamiento por defecto', '  d.ResponseHeadersPolicyId = headersPolicyId;\n', ''],
  ['e', 'acepta una política propia distinta', 'if (!headersPolicyMatches(mine.ResponseHeadersPolicyConfig)) fatal(', 'if (false) fatal('],
  ['e', 'pisa la política de otro', 'if (b.ResponseHeadersPolicyId && (!mine || b.ResponseHeadersPolicyId !== mine.Id)) {', 'if (false) {'],
  ['e', 'crea la política sin --apply', '  if (!APPLY) return HEADERS_POLICY_PENDING;\n', ''],
  ['e', 'verify no mira HSTS ni nosniff', "r.headers['strict-transport-security'] === `max-age=${HSTS_MAX_AGE}` && r.headers['x-content-type-options'] === 'nosniff'", 'true'],
  ['e', 'verify no detecta el 403 de nginx', "(r) => (r.status === 200 && /\"status\"\\s*:\\s*\"ok\"/.test(r.body) ? ['OK']", "(r) => (r.status > 0 ? ['OK']"],
];

// r y e se ejecutan desde su carpeta (leen gate-*.js, run_test_function.mjs y public-pages/ de al
// lado): cada mutante lleva su copia completa de esos ficheros.
const SIBLINGS = ['gate-default.js', 'gate-api.js', 'run_test_function.mjs', 'deploy_edge.mjs'];
const ENV = { d: 'GATE_DEFAULT_FILE', a: 'GATE_API_FILE', s: 'GATE_SCRIPT_FILE' };

fs.rmSync(TMP, { recursive: true, force: true });
let survived = 0;
let tried = 0;
let index = 0;
for (const [which, name, from, to] of mutants) {
  index += 1;
  if (only && !only.includes(which)) continue;
  tried += 1;
  const source = fs.readFileSync(files[which], 'utf8');
  const count = source.split(from).length - 1;
  if (count !== 1) {
    console.log(`  ¿?   ${name}: el texto a mutar aparece ${count} veces (actualizar el mutante)`);
    survived += 1;
    continue;
  }
  const dir = path.join(TMP, String(index));
  fs.mkdirSync(dir, { recursive: true });
  const env = { ...process.env };
  if (which === 'r' || which === 'e') {
    for (const f of SIBLINGS) fs.copyFileSync(path.join(ROOT, f), path.join(dir, f));
    fs.cpSync(path.join(ROOT, 'public-pages'), path.join(dir, 'public-pages'), { recursive: true });
    env.GATE_RTF_FILE = path.join(dir, 'run_test_function.mjs');
    env.GATE_DEPLOY_FILE = path.join(dir, 'deploy_edge.mjs');
  } else {
    env[ENV[which]] = path.join(dir, path.basename(files[which]));
  }
  if (which === 'd' || which === 'a') env.GATE_SKIP_SCRIPT = '1';
  const target = path.join(dir, path.basename(files[which]));
  fs.writeFileSync(target, source.split(from).join(to), { mode: fs.statSync(files[which]).mode });
  const r = spawnSync(process.execPath, [path.join(ROOT, 'test_gate.mjs')], { env, encoding: 'utf8', maxBuffer: 64 << 20 });
  const failedTests = (r.stdout.match(/FALLO/g) || []).length;
  if (r.status === 1 && failedTests > 0) console.log(`  MUERTO     [${which}] ${name} (${failedTests} pruebas fallan)`);
  else {
    survived += 1;
    console.log(`  SOBREVIVE  [${which}] ${name} (exit ${r.status})${r.stderr ? ' ' + r.stderr.split('\n')[0] : ''}`);
  }
}
fs.rmSync(TMP, { recursive: true, force: true });
console.log(`\n${tried - survived}/${tried} mutantes detectados`);
process.exitCode = survived ? 1 : 0;
