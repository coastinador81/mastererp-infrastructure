// gate-api.js · CloudFront Function cloudfront-js-2.0 · viewer-request del comportamiento /api/*
// de E4N1UCPZZ2F0 (origen origin-dev.uonify.com). KVS: uonify-dev-gate.
// Exige la cookie de puerta que emite gate-default.js, salvo GET/HEAD /api/health y
// POST /api/billing/stripe/webhook (billing_checkout.py: lo firma Stripe). Sin cookie válida:
// 401 JSON {"error":"gate_required"} SIN WWW-Authenticate (nunca sale el diálogo del navegador).
// Siempre borra Authorization y la cookie de puerta. NO toca la URI ni la query: el puente de
// voz (/api/uony/live, WebSocket) rechaza cualquier handshake con Authorization o con query.
import cf from 'cloudfront';
import crypto from 'crypto';

var COOKIE = '__Host-uonify_gate';
var TTL = 691200;
var SKEW = 300;
var K_HMAC = 'gate_hmac_key';
var OPEN = '|GET /api/health|HEAD /api/health|POST /api/billing/stripe/webhook|';
var kvs = cf.kvs();

function same(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  var d = 0;
  for (var i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

function sign(key, exp) {
  return crypto.createHmac('sha256', key).update('uonify-dev-gate|v1|' + exp).digest('hex');
}

async function cookieOk(c, now) {
  var e = c[COOKIE];
  if (!e) return false;
  var vals = e.multiValue || [e], key;
  try {
    key = await kvs.get(K_HMAC);
  } catch (err) {
    return false;
  }
  if (typeof key !== 'string' || key.length < 32) return false;
  for (var i = 0; i < vals.length && i < 4; i++) {
    var m = /^v1\.(\d{10})\.([0-9a-f]{64})$/.exec(vals[i].value || '');
    if (m && +m[1] > now && +m[1] <= now + TTL + SKEW && same(sign(key, m[1]), m[2])) return true;
  }
  return false;
}

async function handler(event) {
  var req = event.request, c = req.cookies || {};
  delete req.headers.authorization;
  var ok = req.uri.indexOf('|') < 0 && OPEN.indexOf('|' + req.method + ' ' + req.uri + '|') >= 0;
  if (!ok) ok = await cookieOk(c, Math.floor(Date.now() / 1000));
  if (!ok) {
    return {
      statusCode: 401,
      statusDescription: 'Unauthorized',
      headers: {
        'content-type': { value: 'application/json' },
        'cache-control': { value: 'no-store' },
        'x-content-type-options': { value: 'nosniff' }
      },
      body: { encoding: 'text', data: '{"error":"gate_required"}' }
    };
  }
  delete c[COOKIE];
  return req;
}
