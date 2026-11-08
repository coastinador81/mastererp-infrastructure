#!/usr/bin/env node
// test/serve_emulation.mjs · Emulador LOCAL del borde (solo 127.0.0.1) para probar la puerta en un
// navegador real. Cada petición pasa por el código real de gate-default.js / gate-api.js (con un
// KVS en memoria y credenciales de PRUEBA aleatorias) y luego se sirve como lo haría S3:
// objeto exacto o 403 XML (OAC sin ListBucket), sin respuestas de error personalizadas. /api/*
// llega a un origen simulado (/api/health → 200, como nginx + api), también el handshake WebSocket.
//   node test/serve_emulation.mjs --port 8792            puerta
//   node test/serve_emulation.mjs --port 8793 --raw      dist sin puerta (para comparar)
//   --port 0                 puerto libre (lo imprime la primera línea)
//   --origin-forbidden       el origen responde como nginx sin X-Origin-Verify (403 forbidden)
// Variables: GATE_DIST (dist), GATE_TEST_USER / GATE_TEST_PASS (credenciales de prueba).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { isNotUploaded } from '../build_gate.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const DIST = process.env.GATE_DIST || path.resolve(ROOT, '../../frontend-build/src-copy/dist');
const PAGES = path.join(ROOT, 'public-pages');
const args = process.argv.slice(2);
const PORT = args.includes('--port') ? Number(args[args.indexOf('--port') + 1]) : 8792;
const RAW = args.includes('--raw');
const ORIGIN_FORBIDDEN = args.includes('--origin-forbidden');
// La política de cabeceras de deploy_edge.mjs (uonify-dev-security-headers), aplicada a lo que sale de
// S3 y del origen; --no-headers-policy emula la distribución sin ella.
const POLICY_HEADERS = args.includes('--no-headers-policy') || RAW ? {}
  : { 'strict-transport-security': 'max-age=31536000', 'x-content-type-options': 'nosniff', 'x-frame-options': 'DENY', 'x-robots-tag': 'noindex, nofollow' };
const OLD_WEB = '<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Uonify (propuesta)</title></head><body><p>Propuesta /web/</p></body></html>';
const USER = process.env.GATE_TEST_USER || 'prueba';
const PASS = process.env.GATE_TEST_PASS || crypto.randomBytes(18).toString('base64url');
const STORE = {
  gate_cred_sha256: crypto.createHash('sha256').update(USER + ':' + PASS).digest('hex'),
  gate_hmac_key: crypto.randomBytes(32).toString('hex'),
};
const cfMock = { kvs: () => ({ get: async (k) => { if (!(k in STORE)) throw new Error('KeyNotFound'); return STORE[k]; } }) };
function load(file) {
  const body = fs.readFileSync(path.join(ROOT, file), 'utf8').replace(/^import cf from 'cloudfront';\s*$/m, '').replace(/^import crypto from 'crypto';\s*$/m, '');
  return new Function('cf', 'crypto', 'atob', '"use strict";\n' + body + '\nreturn handler;')(cfMock, crypto, globalThis.atob);
}
const gateDefault = load('gate-default.js');
const gateApi = load('gate-api.js');
const OLD_ROOT = '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=/web/home-v22-propuesta/index.html"><title>Uonify</title></head><body><p><a href="/web/home-v22-propuesta/index.html">Abrir Uonify</a></p></body></html>';
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.json': 'application/json', '.txt': 'text/plain', '.xml': 'application/xml', '.jpg': 'image/jpeg', '.mp4': 'video/mp4', '.glb': 'model/gltf-binary', '.hdr': 'application/octet-stream', '.woff2': 'font/woff2' };

function object(uri) {
  if (uri === '/' || uri === '/index.html') return RAW ? path.join(DIST, 'index.html') : null;
  if (isNotUploaded(uri) || uri.includes('..')) return undefined;
  const variant = path.join(PAGES, uri);
  if (!RAW && (uri.startsWith('/privacidad/index.nojs') || uri.startsWith('/terminos/index.nojs'))) return fs.existsSync(variant) ? variant : undefined;
  const file = path.join(DIST, decodeURIComponent(uri));
  return fs.existsSync(file) && fs.statSync(file).isFile() ? file : undefined;
}

function toEvent(req) {
  const [p, q = ''] = req.url.split('?');
  const headers = {};
  for (const [k, v] of Object.entries(req.headers)) if (k !== 'cookie' && k !== 'connection' && k !== 'upgrade') headers[k] = { value: Array.isArray(v) ? v[0] : v };
  const cookies = {};
  for (const part of (req.headers.cookie || '').split(';')) {
    const i = part.indexOf('=');
    if (i < 0) continue;
    const k = part.slice(0, i).trim();
    const v = part.slice(i + 1).trim();
    if (cookies[k]) (cookies[k].multiValue = cookies[k].multiValue || [{ value: cookies[k].value }]).push({ value: v });
    else cookies[k] = { value: v };
  }
  const querystring = {};
  for (const kv of q ? q.split('&') : []) {
    const i = kv.indexOf('=');
    const k = i < 0 ? kv : kv.slice(0, i);
    querystring[k] = { value: i < 0 ? '' : kv.slice(i + 1) };
  }
  return { version: '1.0', context: { eventType: 'viewer-request' }, viewer: { ip: '127.0.0.1' }, request: { method: req.method, uri: p, querystring, headers, cookies } };
}

function send(res, status, type, body, extra = {}) {
  res.writeHead(status, { 'content-type': type, ...extra });
  res.end(body);
}
// Respuesta de S3 o del origen: lleva las cabeceras de la política.
function origin(res, status, type, body, extra = {}) {
  send(res, status, type, body, { ...extra, ...POLICY_HEADERS });
}

const server = http.createServer(async (req, res) => {
  const tag = `${req.method} ${req.url} · mode=${req.headers['sec-fetch-mode'] || '-'} dest=${req.headers['sec-fetch-dest'] || '-'}`;
  let uri = req.url.split('?')[0];
  if (RAW) {
    if (uri.startsWith('/api/')) return send(res, 404, 'application/json', '{"error":"not_found"}');
    if (!path.extname(uri)) uri = fs.existsSync(path.join(DIST, uri, 'index.html')) && uri !== '/' ? uri.replace(/\/$/, '') + '/index.html' : uri === '/' ? '/index.html' : '/spa.html';
  } else {
    const fn = uri.startsWith('/api/') ? gateApi : gateDefault;
    const out = await fn(toEvent(req));
    if (out.statusCode) {
      const extra = {};
      for (const [k, v] of Object.entries(out.headers || {})) extra[k] = v.value;
      const setCookie = Object.entries(out.cookies || {}).map(([k, v]) => `${k}=${v.value}; ${v.attributes}`);
      if (setCookie.length) extra['set-cookie'] = setCookie;
      console.log(`${tag} → ${out.statusCode}${extra.location ? ' → ' + extra.location : ''}`);
      return send(res, out.statusCode, extra['content-type'] || 'text/plain', out.body ? out.body.data : '', extra);
    }
    if (uri.startsWith('/api/')) {
      console.log(`${tag} → función deja pasar → backend simulado`);
      if (ORIGIN_FORBIDDEN) return origin(res, 403, 'application/json', '{"error":"forbidden"}');
      if (out.uri === '/api/health') return origin(res, 200, 'application/json', '{"status":"ok","database":"ok"}');
      if (out.uri === '/api/auth/session') return origin(res, 200, 'application/json', '{"authenticated":false}');
      return origin(res, 404, 'application/json', '{"error":"no_backend_in_emulator"}');
    }
    uri = out.uri;
  }
  if (uri.startsWith('/web/home-v22-propuesta/')) return origin(res, 200, 'text/html; charset=utf-8', OLD_WEB);
  const file = object(uri);
  if (file === null) {
    console.log(`${tag} → ${uri} (objeto raíz antiguo) 200`);
    return origin(res, 200, 'text/html; charset=utf-8', OLD_ROOT);
  }
  if (!file) {
    console.log(`${tag} → ${uri} → 403 S3`);
    return origin(res, 403, 'application/xml', '<?xml version="1.0" encoding="UTF-8"?><Error><Code>AccessDenied</Code><Message>Access Denied</Message></Error>');
  }
  console.log(`${tag} → ${uri} 200`);
  origin(res, 200, TYPES[path.extname(file)] || 'application/octet-stream', fs.readFileSync(file), { 'cache-control': 'no-store' });
});
// Handshake WebSocket (/api/uony/live): pasa por la función como en CloudFront; si la función
// responde, esa respuesta sale tal cual; si deja pasar, el origen simulado acepta el upgrade.
server.on('upgrade', async (req, socket) => {
  const uri = req.url.split('?')[0];
  const out = await (uri.startsWith('/api/') ? gateApi : gateDefault)(toEvent(req));
  if (out.statusCode) {
    const body = out.body ? out.body.data : '';
    const lines = [`HTTP/1.1 ${out.statusCode} ${out.statusDescription || ''}`];
    for (const [k, v] of Object.entries(out.headers || {})) lines.push(`${k}: ${v.value}`);
    lines.push(`content-length: ${Buffer.byteLength(body)}`, 'connection: close', '', body);
    console.log(`UPGRADE ${req.url} → ${out.statusCode}`);
    return socket.end(lines.join('\r\n'));
  }
  console.log(`UPGRADE ${req.url} → 101`);
  socket.end('HTTP/1.1 101 Switching Protocols\r\nupgrade: websocket\r\nconnection: Upgrade\r\n\r\n');
});
server.listen(PORT, '127.0.0.1', () => console.log(`emulador ${RAW ? 'SIN puerta (dist)' : 'con puerta'} en http://127.0.0.1:${server.address().port} · usuario de prueba ${USER}`));
