#!/usr/bin/env node
// upload_dist.mjs · Paso 15 del plan: sube el dist APROBADO (OK visual del dueño, 07-11) al bucket de
// https://dev.uonify.com. Por defecto es un ENSAYO; con --apply sube, comprueba cada objeto e invalida
// la caché de CloudFront.
//   - SIN el index.html raíz: la raíz sigue en /web/home-v22-propuesta hasta la revisión final del dueño.
//   - SIN los ficheros internos que build_gate.mjs marca como no publicables (chunk de MSW,
//     mockServiceWorker.js, .md y .DS_Store).
//   - SIN --delete: no borra nada del bucket (además, el bucket guarda versiones).
//   - Content-Type por extensión (los módulos JS con text/javascript; una extensión desconocida para
//     la subida) y Cache-Control por tipo:
//       *.html                                            no-cache
//       /assets/<nombre>-<huella de Vite>.<ext>
//       /assets/prerender/<huella>.css                    public, max-age=31536000, immutable
//       /assets/vendor/<nombre con versión x.y.z>         public, max-age=86400
//       el resto (imágenes, modelos, vídeo, robots...)    public, max-age=300
//   - Antes de nada: build_gate.mjs --check, para que la puerta publicada sea la generada para ESTE dist.
//   - Idempotente: un objeto con la misma suma SHA-256, tipo y caché no se vuelve a subir.
//   --root: sube SOLO el index.html raíz (la portada del frontend aprobado). Exige que gate-default.js
//   esté en modo --root-gated y que https://dev.uonify.com/ sin cookie responda ya 401 con reto Basic:
//   el JavaScript de la app nunca queda público (D-PROTECCIÓN). Invalida «/» e «/index.html».
// Uso: node upload_dist.mjs [--dist ruta] [--root] [--apply]
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import https from 'node:https';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { isNotUploaded } from './build_gate.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ACCOUNT = '277352717693';
const BUCKET = 'uonify-dev-web-277352717693';
const REGION = 'us-east-1';
const DIST_ID = 'E4N1UCPZZ2F0';
const argv = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = argv.indexOf(name);
  return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : fallback;
};
const APPLY = argv.includes('--apply');
const ROOT = argv.includes('--root');
const DIST = path.resolve(opt('--dist', path.resolve(HERE, '../../frontend-build/src-copy/dist')));

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.map': 'application/json', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
  '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.woff': 'font/woff', '.glb': 'model/gltf-binary',
  '.hdr': 'application/octet-stream', '.mp4': 'video/mp4', '.webm': 'video/webm', '.txt': 'text/plain; charset=utf-8',
  '.xml': 'application/xml', '.wasm': 'application/wasm', '.webmanifest': 'application/manifest+json',
};
const IMMUTABLE = 'public, max-age=31536000, immutable';
function cacheControl(p) {
  if (p.endsWith('.html')) return 'no-cache';
  if (/^\/assets\/[^/]+-[A-Za-z0-9_-]{8}\.[a-z0-9]+$/.test(p) || /^\/assets\/prerender\/[0-9a-f]{10}\.css$/.test(p)) return IMMUTABLE;
  if (/^\/assets\/vendor\/[^/]*\d+\.\d+\.\d+[^/]*$/.test(p)) return 'public, max-age=86400';
  return 'public, max-age=300';
}

const fail = (message) => {
  console.error('ERROR: ' + message);
  process.exit(2);
};
const sleep = (ms) => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
function aws(args, { json = true } = {}) {
  for (let attempt = 1; ; attempt += 1) {
    const r = spawnSync('aws', json ? [...args, '--output', 'json'] : args, { encoding: 'utf8', env: { ...process.env, AWS_PAGER: '' }, maxBuffer: 16 << 20 });
    if (r.error) fail(`no puedo ejecutar la AWS CLI (${r.error.code})`);
    if (r.status === 0) return json ? (r.stdout.trim() ? JSON.parse(r.stdout) : null) : r.stdout.trim();
    const m = /An error occurred \(([^)]+)\)/.exec(r.stderr || '');
    const code = m ? m[1] : `exit ${r.status}`;
    if (['404', 'NotFound', 'NoSuchKey'].includes(code)) return null;
    // Con «aws login», muchas llamadas seguidas pueden recibir 429 al renovar el token: se reintenta.
    if (attempt < 4 && /429|Throttl|Rate exceeded|SlowDown/i.test(code + ' ' + (r.stderr || ''))) {
      sleep(2000 * attempt);
      continue;
    }
    fail(`aws ${args[0]} ${args[1]}: ${code} · ${(r.stderr || '').trim().split('\n').pop().slice(0, 200)}`);
  }
}
function walk(dir, base = dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, base, out);
    else if (entry.isFile()) out.push('/' + path.relative(base, full).split(path.sep).join('/'));
  }
  return out.sort();
}
const sha256 = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('base64');

if (!fs.existsSync(path.join(DIST, 'spa.html'))) fail(`${DIST} no parece el dist (falta spa.html)`);
const rootGated = /var ROOT_PUBLIC = false;/.test(fs.readFileSync(path.join(HERE, 'gate-default.js'), 'utf8'));
if (ROOT && !rootGated) fail('la raíz solo se sube con la puerta cerrada en «/»: build_gate.mjs --root-gated --write, después deploy_edge.mjs functions y publish');
const check = spawnSync(process.execPath, [path.join(HERE, 'build_gate.mjs'), '--dist', DIST, '--check', ...(rootGated ? ['--root-gated'] : [])], { encoding: 'utf8' });
if (check.status !== 0) fail(`build_gate.mjs --check: la puerta no se generó para este dist; no se sube nada\n${(check.stderr || check.stdout).trim()}`);
const fingerprint = (/huella (\S+)/.exec(check.stdout) || [])[1] || '?';
const id = aws(['sts', 'get-caller-identity', '--region', REGION]);
if (id.Account !== ACCOUNT) fail(`la AWS CLI apunta a la cuenta ${id.Account}, no a ${ACCOUNT}`);
console.log(`Cuenta ${id.Account} · ${id.Arn}`);
console.log(`dist ${DIST} · huella de la puerta ${fingerprint} (build_gate.mjs --check OK)`);

if (ROOT) {
  // La puerta publicada (LIVE) tiene que pedir usuario y contraseña en «/» ANTES de subir la portada.
  const live = await new Promise((resolve) => {
    const req = https.request('https://dev.uonify.com/', { method: 'GET', agent: false, timeout: 20000,
      headers: { 'sec-fetch-mode': 'navigate', 'sec-fetch-dest': 'document', accept: 'text/html', 'user-agent': 'uonify-upload-dist/1' } }, (res) => {
      res.resume();
      resolve({ status: res.statusCode, challenge: res.headers['www-authenticate'] || '' });
    });
    req.on('timeout', () => req.destroy(new Error('tiempo agotado')));
    req.on('error', (error) => resolve({ status: 0, challenge: '', error: error.message }));
    req.end();
  });
  if (live.status !== 401 || !/^Basic realm="Uonify DEV"/.test(live.challenge)) {
    fail(`https://dev.uonify.com/ sin cookie responde ${live.status || live.error}: la puerta todavía no cierra «/»; no se sube la portada`);
  }
  console.log('https://dev.uonify.com/ sin cookie → 401 con reto Basic: la puerta ya cierra «/»');
}
const plan = [];
const skipped = [];
for (const p of walk(DIST)) {
  if (ROOT && p !== '/index.html') continue;
  if ((p === '/index.html' && !ROOT) || isNotUploaded(p)) {
    skipped.push(p);
    continue;
  }
  const type = TYPES[path.extname(p).toLowerCase()];
  if (!type) fail(`extensión desconocida, no se sube nada: ${p}`);
  plan.push({ key: p.slice(1), file: path.join(DIST, p), type, cache: cacheControl(p), bytes: fs.statSync(path.join(DIST, p)).size });
}
const byCache = {};
for (const item of plan) {
  byCache[item.cache] = byCache[item.cache] || { files: 0, bytes: 0 };
  byCache[item.cache].files += 1;
  byCache[item.cache].bytes += item.bytes;
}
console.log(`\n${plan.length} ficheros para s3://${BUCKET}/ (${(plan.reduce((n, i) => n + i.bytes, 0) / 1048576).toFixed(1)} MB):`);
for (const [cache, v] of Object.entries(byCache)) console.log(`  ${String(v.files).padStart(4)} · ${(v.bytes / 1048576).toFixed(1).padStart(6)} MB · Cache-Control: ${cache}`);
console.log(`No se suben (${skipped.length}): ${skipped.join(' ')}`);

let uploaded = 0;
let same = 0;
for (const [n, item] of plan.entries()) {
  const want = sha256(item.file);
  const head = aws(['s3api', 'head-object', '--bucket', BUCKET, '--key', item.key, '--checksum-mode', 'ENABLED', '--region', REGION]);
  if (head && head.ChecksumSHA256 === want && head.ContentType === item.type && head.CacheControl === item.cache) {
    same += 1;
    continue;
  }
  if (!APPLY) {
    uploaded += 1;
    continue;
  }
  aws(['s3api', 'put-object', '--bucket', BUCKET, '--key', item.key, '--body', item.file, '--content-type', item.type,
    '--cache-control', item.cache, '--checksum-algorithm', 'SHA256', '--region', REGION]);
  const after = aws(['s3api', 'head-object', '--bucket', BUCKET, '--key', item.key, '--checksum-mode', 'ENABLED', '--region', REGION]);
  if (!after || after.ChecksumSHA256 !== want || after.ContentType !== item.type || after.CacheControl !== item.cache || after.ContentLength !== item.bytes) {
    fail(`s3://${BUCKET}/${item.key}: la comprobación tras subir no coincide (suma, tipo, caché o tamaño)`);
  }
  uploaded += 1;
  if (uploaded % 25 === 0) console.log(`  … ${uploaded} subidos (${n + 1}/${plan.length} revisados)`);
}
if (!APPLY) {
  console.log(`\nENSAYO: ${uploaded} por subir y ${same} ya al día. Con --apply se sube e invalida la caché de ${DIST_ID}.`);
  process.exit(0);
}
console.log(`\nSubidos y comprobados: ${uploaded} · ya al día: ${same}`);
if (uploaded > 0) {
  const paths = ROOT ? ['/', '/index.html'] : ['/*'];
  const inv = aws(['cloudfront', 'create-invalidation', '--distribution-id', DIST_ID, '--paths', ...paths, '--query', 'Invalidation.Id', '--output', 'text'], { json: false });
  console.log(`Invalidación ${inv} de ${DIST_ID} (${paths.join(' ')}): esperando a que termine…`);
  aws(['cloudfront', 'wait', 'invalidation-completed', '--distribution-id', DIST_ID, '--id', inv], { json: false });
  console.log('Invalidación completada.');
}
