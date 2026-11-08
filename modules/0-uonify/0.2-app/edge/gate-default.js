// gate-default.js · CloudFront Function cloudfront-js-2.0 · viewer-request del comportamiento por
// defecto de E4N1UCPZZ2F0 (S3). Puerta D-PROTECCION + reescritura de rutas. KVS: uonify-dev-gate.
// Reto Basic solo en navegaciones; Basic válido → 302 a la misma URL con cookie firmada (HMAC de
// la caducidad, nunca la contraseña). Subrecursos sin cookie → 403 sin WWW-Authenticate.
// Públicos: /web/*, /robots.txt, «/» sin vuelta de app (ROOT_PUBLIC), /privacidad, /terminos y
// PUBLIC_ASSETS; los enlaces antiguos a las legales responden 301 a ellas si no hay cookie.
// Las listas las genera build_gate.mjs desde el dist: regenerar en cada build.
import cf from 'cloudfront';
import crypto from 'crypto';

var COOKIE = '__Host-uonify_gate';
var TTL = 691200; // 8 días ≥ sesión del backend (7 días)
var SKEW = 300;
var K_HASH = 'gate_cred_sha256';
var K_HMAC = 'gate_hmac_key';
// links.ts LEGACY_FILES sin index.html, que es alias de «/» (ver target).
var LEGACY = '|/producto.html|/como-funciona.html|/para-empresas.html|/empresa.html|/novedades.html|/privacidad.html|/terminos.html|';
var APPQ = ['auth', 'billing', 'drive', 'cloud', 'view'];
// BEGIN GENERATED por build_gate.mjs (no editar a mano) · dist 888d9335768a36a2
var ROOT_PUBLIC = false;
var LEGAL_NOJS = true;
var PRERENDERED = '|/ayuda|/ayuda/cancelar-la-renovacion|/ayuda/conectar-cuenta-amazon|/ayuda/conectar-google-drive|/ayuda/crear-imagen-o-video|/ayuda/creditos-de-google|/ayuda/darse-de-baja|/ayuda/el-alta-paso-a-paso|/ayuda/elegir-tus-archivos|/ayuda/entrar-en-uonify|/ayuda/entrenar-la-ia|/ayuda/exportar-o-borrar-tus-datos|/ayuda/hablar-con-uony|/ayuda/lo-que-uony-puede-hacer|/ayuda/los-elementos|/ayuda/nexus-y-desconectar|/ayuda/precio-maximo-y-visto-bueno|/ayuda/precio-y-pago|/ayuda/preparar-una-ficha|/ayuda/que-cobra-uonify-y-cada-proveedor|/ayuda/que-datos-de-drive-usa-uony|/ayuda/que-es-uonify-y-uony|/ayuda/que-ve-uony-y-que-no|/ayuda/quien-paga-imagenes-y-videos|/ayuda/revisar-y-enviar-a-amazon|/ayuda/si-algo-falla|/ayuda/tu-proyecto-de-google|/ayuda/tus-derechos-de-privacidad|/ayuda/versiones-biblioteca-y-publicar|/como-funciona|/lo-que-puedes-hacer|/novedades|/para-empresas|/precios|/privacidad|/productos|/seguridad|/sobre-uonify|/terminos|';
var PUBLIC_ASSETS = '|/assets/billing-D_32RTDA.css|/assets/brands/uonify-favicon-3d.png|/assets/brands/uonify-isotipo-3d.webp|/assets/brands/uonify-wordmark-3d.webp|/assets/index-Ct_aZtnx.css|/assets/prerender/1db7fc56b2.css|/assets/prerender/7b6b67e91e.css|/assets/ui-B_q764Gq.css|';
// END GENERATED
var kvs = cf.kvs();

function inList(list, p) {
  return p.indexOf('|') < 0 && list.indexOf('|' + p + '|') >= 0;
}

function same(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  var d = 0;
  for (var i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

function appQuery(qs) {
  for (var i = 0; i < APPQ.length; i++) if (qs[APPQ[i]]) return true;
  return false;
}

// Objeto que se pide a S3. «/» e «/index.html» son indistinguibles (el objeto raíz puede aplicarse
// antes de la función): siguen en el index.html del bucket salvo vuelta de login/pago/Drive/Cloud.
function target(uri, qs) {
  if (uri.indexOf('/web/') === 0) return uri;
  if (uri === '/' || uri === '/index.html') return appQuery(qs) ? '/spa.html' : uri;
  if (inList(LEGACY, uri)) return '/spa.html';
  if (uri.slice(uri.lastIndexOf('/') + 1).indexOf('.') >= 0) return uri; // fichero: nunca HTML
  var r = uri.replace(/\/+$/, '');
  return inList(PRERENDERED, r) ? r + '/index.html' : '/spa.html';
}

function legal(uri) {
  var r = uri.replace(/\/(index\.html)?$/, '');
  return r === '/privacidad' || r === '/terminos' ? r : '';
}

// Enlaces antiguos a las legales (links.ts toAppHref: /privacidad.html, /index.html?view=terminos…).
// En local acaban en la página pública; aquí, sin cookie, 301 a ella (con cookie: /spa.html, igual).
function oldLegal(uri, qs) {
  var m = /^\/(privacidad|terminos)\.html$/.exec(uri);
  if (m) return '/' + m[1];
  var v = uri === '/index.html' && qs.view ? qs.view.value : '';
  return v === 'privacidad' || v === 'terminos' ? '/' + v : '';
}

function isPublic(uri, qs) {
  if (/\/\/|\\|\/\.\.?(\/|$)|%(2e|2f|5c|00)/i.test(uri)) return false;
  if (uri.indexOf('/web/') === 0 || uri === '/robots.txt') return true;
  if (uri === '/' || uri === '/index.html') return ROOT_PUBLIC && !appQuery(qs);
  return legal(uri) !== '' || inList(PUBLIC_ASSETS, uri);
}

function isNav(h) {
  var mode = h['sec-fetch-mode'], dest = h['sec-fetch-dest'];
  return (mode && String(mode.value).toLowerCase() === 'navigate') ||
    (dest && String(dest.value).toLowerCase() === 'document');
}

function sign(key, exp) {
  return crypto.createHmac('sha256', key).update('uonify-dev-gate|v1|' + exp).digest('hex');
}

async function hmacKey() {
  try {
    var k = await kvs.get(K_HMAC);
    return typeof k === 'string' && k.length >= 32 ? k : null;
  } catch (e) {
    return null;
  }
}

async function cookieOk(c, now) {
  var e = c[COOKIE];
  if (!e) return false;
  var vals = e.multiValue || [e];
  var key = await hmacKey();
  if (!key) return false;
  for (var i = 0; i < vals.length && i < 4; i++) {
    var m = /^v1\.(\d{10})\.([0-9a-f]{64})$/.exec(vals[i].value || '');
    if (m && +m[1] > now && +m[1] <= now + TTL + SKEW && same(sign(key, m[1]), m[2])) return true;
  }
  return false;
}

async function basicOk(v) {
  var m = /^\s*basic\s+([A-Za-z0-9+\/]{4,700}={0,2})\s*$/i.exec(v);
  if (!m || m[1].length % 4) return false;
  var s, h;
  try {
    s = atob(m[1]);
  } catch (e) {
    return false;
  }
  if (!/^[\x20-\x7e]+$/.test(s) || s.indexOf(':') < 1) return false;
  try {
    h = await kvs.get(K_HASH);
  } catch (e) {
    return false;
  }
  return /^[0-9a-f]{64}$/.test(h || '') && same(crypto.createHash('sha256').update(s).digest('hex'), h);
}

function res(code, desc, h, body) {
  h['cache-control'] = { value: 'no-store' };
  var r = { statusCode: code, statusDescription: desc, headers: h };
  if (body) r.body = { encoding: 'text', data: body };
  return r;
}

function challenge() {
  return res(401, 'Unauthorized', {
    'www-authenticate': { value: 'Basic realm="Uonify DEV", charset="UTF-8"' },
    'content-type': { value: 'text/html; charset=utf-8' }
  }, '<!doctype html><meta charset="utf-8"><title>Uonify</title><p>Acceso restringido.</p>');
}

async function grant(req, now) {
  var key = await hmacKey();
  if (!key) return challenge();
  var exp = String(now + TTL), q = [], qs = req.querystring;
  for (var k in qs) {
    var vs = qs[k].multiValue || [qs[k]];
    for (var i = 0; i < vs.length; i++) q.push(k + '=' + vs[i].value);
  }
  // Ruta relativa al propio host; las barras iniciales se colapsan (sin redirección abierta).
  var r = res(302, 'Found', { location: { value: '/' + req.uri.replace(/^[\/\\]+/, '') + (q.length ? '?' + q.join('&') : '') } });
  r.cookies = {};
  r.cookies[COOKIE] = { value: 'v1.' + exp + '.' + sign(key, exp), attributes: 'Path=/; Max-Age=' + TTL + '; Secure; HttpOnly; SameSite=Lax' };
  return r;
}

async function handler(event) {
  var req = event.request, h = req.headers, c = req.cookies || {}, uri = req.uri, qs = req.querystring || {};
  var auth = h.authorization ? h.authorization.value : '';
  delete h.authorization;
  var now = Math.floor(Date.now() / 1000);
  var pub = isPublic(uri, qs), page = pub && LEGAL_NOJS ? legal(uri) : '', old = pub ? '' : oldLegal(uri, qs);
  var ok = false;
  if (!pub || page) ok = await cookieOk(c, now);
  if (old && !ok) return res(301, 'Moved Permanently', { location: { value: old } });
  if (!pub && !ok) {
    if (!isNav(h)) {
      return res(403, 'Forbidden', { 'content-type': { value: 'text/plain; charset=utf-8' } }, 'Acceso restringido.');
    }
    var valid = await basicOk(auth);
    if (!valid) return challenge();
    var granted = await grant(req, now);
    return granted;
  }
  delete c[COOKIE];
  // Sin cookie, la página legal se sirve sin el JS de la app (variante generada por build_gate.mjs).
  var dest = page && !ok ? page + '/index.nojs.html' : target(uri, qs);
  if (dest !== uri) req.uri = dest;
  return req;
}
