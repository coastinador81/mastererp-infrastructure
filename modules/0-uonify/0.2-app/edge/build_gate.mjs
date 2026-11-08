#!/usr/bin/env node
// build_gate.mjs · Genera el bloque GENERATED de gate-default.js (y las variantes sin JS de las
// páginas legales) a partir del dist aprobado. Solo lee el dist; escribe únicamente en esta carpeta.
//
//   node build_gate.mjs --dist <dist>             resumen, no escribe nada
//   node build_gate.mjs --dist <dist> --write     reescribe el bloque y public-pages/
//   node build_gate.mjs --dist <dist> --check     exit 1 si el bloque o public-pages/ no coinciden
//   --legal-js     modo «cierre exacto»: /privacidad y /terminos con su JS (público también el JS)
//   --root-gated   ROOT_PUBLIC=false (paso 19 del plan: la puerta cubre también «/»)
//
// Qué genera:
//  - PRERENDERED: rutas con dist/<ruta>/index.html, sin la raíz (la raíz sigue siendo el index.html
//    del bucket hasta la revisión final del dueño).
//  - PUBLIC_ASSETS: los ficheros EXACTOS que pide la página legal que ve un visitante sin cookie,
//    sacados por escaneo src/href (sin <a>, <meta>, canonical, alternate ni preconnect) más los
//    url()/@import de cada CSS de la lista.
//    · Modo por defecto (LEGAL_NOJS): la página que ve el visitante sin cookie es
//      public-pages/<página>/index.nojs.html = el HTML prerenderizado sin <script> de la app ni
//      modulepreload (se conserva el JSON-LD). Resultado: solo CSS e imágenes públicos; TODO el JS
//      de la app queda detrás de la puerta (D-PROTECCION).
//    · Modo --legal-js: el HTML original. El router carga la página con una ruta perezosa, así que
//      además del src/href hacen falta el chunk de esa ruta, sus dependencias (__vite__mapDeps) y
//      los import estáticos de cada JS: sin ellos la página se rompe al hidratar (import() → 403).
//      Con el build actual eso hace público el núcleo de la app (index, vendor, billing…).
// Falla (exit 2) si no encuentra lo que espera, si un asset no existe en el dist, si cae en lo que
// no se sube (MSW, mockServiceWorker.js, *.md, .DS_Store) o si la función pasa de 10 KB.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TARGET = path.join(HERE, 'gate-default.js');
const PAGES_DIR = path.join(HERE, 'public-pages');
export const PUBLIC_PAGES = ['privacidad', 'terminos'];
export const NOJS_NAME = 'index.nojs.html';
const SITE_ORIGINS = ['https://dev.uonify.com'];
export const MAX_FUNCTION_BYTES = 10240;
const BEGIN = '// BEGIN GENERATED';
const END = '// END GENERATED';
// Lo que NO se sube al bucket (instrucción del CEO y revisión 1): nunca puede ser público.
const NOT_UPLOADED = [/^\/assets\/browser-[^/]*\.js$/, /^\/mockServiceWorker\.js$/, /\.md$/i, /(^|\/)\.DS_Store$/];
const LINK_RELS = new Set(['stylesheet', 'modulepreload', 'preload', 'prefetch', 'icon', 'shortcut', 'apple-touch-icon', 'mask-icon', 'manifest']);
const SAFE_PATH = /^\/[A-Za-z0-9._~\/-]+$/;

export function isNotUploaded(p) {
  return NOT_UPLOADED.some((re) => re.test(p));
}

function fail(message) {
  const error = new Error(message);
  error.code = 'BUILD_GATE';
  throw error;
}

function walk(dir, base = dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, base, out);
    else out.push('/' + path.relative(base, full).split(path.sep).join('/'));
  }
  return out;
}

export function listPrerendered(dist) {
  return walk(dist)
    .filter((p) => p.endsWith('/index.html') && p !== '/index.html' && !isNotUploaded(p))
    .map((p) => p.slice(0, -'/index.html'.length))
    .sort();
}

function decodeEntities(value) {
  return value.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>');
}

function attributes(raw) {
  const attrs = {};
  const re = /([^\s=/]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g;
  let m;
  while ((m = re.exec(raw))) attrs[m[1].toLowerCase()] = decodeEntities(m[2] ?? m[3] ?? m[4] ?? '');
  return attrs;
}

/**
 * Referencias src/href de recursos de una página (no enlaces de navegación).
 * Devuelve [{ value, entry }]; entry=true para <script type="module" src>.
 */
export function htmlRefs(html) {
  const refs = [];
  const clean = html.replace(/<!--[\s\S]*?-->/g, '').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, (s) => s.slice(0, s.indexOf('>') + 1));
  const re = /<([a-zA-Z][a-zA-Z0-9-]*)\b([^>]*)>/g;
  let m;
  while ((m = re.exec(clean))) {
    const tag = m[1].toLowerCase();
    if (tag === 'a' || tag === 'area' || tag === 'base' || tag === 'form' || tag === 'meta') continue;
    const attrs = attributes(m[2]);
    if (tag === 'link') {
      const rels = (attrs.rel || '').toLowerCase().split(/\s+/).filter(Boolean);
      if (!rels.some((rel) => LINK_RELS.has(rel))) continue;
    }
    const entry = tag === 'script' && (attrs.type || '').toLowerCase() === 'module';
    for (const name of ['src', 'href', 'poster']) if (attrs[name]) refs.push({ value: attrs[name], entry: entry && name === 'src' });
    for (const name of ['srcset', 'imagesrcset']) {
      if (attrs[name]) for (const part of attrs[name].split(',')) if (part.trim()) refs.push({ value: part.trim().split(/\s+/)[0], entry: false });
    }
  }
  return refs;
}

/** HTML prerenderizado sin el JS de la app: fuera <script> (salvo JSON-LD) y modulepreload. */
export function nojsVariant(html) {
  const out = html
    .replace(/[ \t]*<script\b(?![^>]*type=["']?application\/ld\+json)[^>]*>[\s\S]*?<\/script>[ \t]*\r?\n?/gi, '')
    .replace(/[ \t]*<link\b[^>]*\brel=["']?modulepreload\b[^>]*>[ \t]*\r?\n?/gi, '');
  if (/<script\b(?![^>]*application\/ld\+json)/i.test(out) || /modulepreload/i.test(out)) fail('La variante sin JS aún contiene <script> o modulepreload');
  if (htmlRefs(out).some((ref) => /\.m?js(?:[?#]|$)/i.test(ref.value))) fail('La variante sin JS aún referencia un .js');
  if (!/data-prerendered=/.test(out)) fail('La página no tiene contenido prerenderizado (data-prerendered)');
  return out;
}

/** Normaliza una referencia a ruta del mismo origen, o null si es externa / data: / ancla. */
export function sameOriginPath(ref, basePath) {
  const value = ref.trim();
  if (!value || value.startsWith('#') || /^(data|blob|mailto|tel|javascript):/i.test(value)) return null;
  let parsed;
  try {
    parsed = new URL(value, 'https://dev.uonify.com' + basePath);
  } catch {
    return null;
  }
  if (!SITE_ORIGINS.includes(parsed.origin)) return null;
  return parsed.pathname;
}

export function jsStaticImports(code) {
  const out = [];
  const re = /\b(?:import|export)\s*(?:\{[^}]*\}\s*from\s*|\*\s*(?:as\s+[\w$]+\s*)?from\s*|[\w$]+\s*(?:,\s*(?:\{[^}]*\}|\*\s*as\s+[\w$]+)\s*)?from\s*)?["'](\.{1,2}\/[^"']+)["']/g;
  let m;
  while ((m = re.exec(code))) out.push(m[1]);
  return out;
}

export function cssRefs(css) {
  const out = [];
  let m;
  const url = /url\(\s*(["']?)([^"')]+)\1\s*\)/g;
  while ((m = url.exec(css))) out.push(m[2]);
  const imp = /@import\s+(?:url\(\s*)?["']([^"']+)["']/g;
  while ((m = imp.exec(css))) out.push(m[1]);
  return out;
}

/** Tabla de __vite__mapDeps del chunk de entrada: índice → "assets/…". */
function mapDepsTable(entry) {
  const m = /m\.f=(\[[^\]]*\])/.exec(entry);
  return m ? JSON.parse(m[1]) : null;
}

/** Chunk perezoso de la ruta `page` y sus dependencias declaradas, como rutas absolutas. */
export function lazyRouteFiles(entry, page) {
  const table = mapDepsTable(entry);
  const start = entry.search(new RegExp('path:[`"\']' + page.replace(/[-/]/g, '\\$&') + '[`"\'],lazy:'));
  if (!table || start < 0) return null;
  const next = entry.indexOf('{path:', start + 6);
  const slice = entry.slice(start, next > start ? next : start + 1200);
  const chunk = /import\([`"']\.\/([^`"']+)[`"']\)/.exec(slice);
  const deps = /__vite__mapDeps\(\[([0-9,\s]*)\]\)/.exec(slice);
  if (!chunk || !deps) return null;
  const files = ['/assets/' + chunk[1]];
  for (const index of deps[1].split(',').map((s) => s.trim()).filter(Boolean)) {
    const item = table[Number(index)];
    if (typeof item !== 'string') return null;
    files.push('/' + item);
  }
  return files;
}

/** Lista exacta de assets públicos. nojs=true: la de la variante sin JS (solo CSS e imágenes). */
export function publicAssets(dist, { nojs = true, pages = PUBLIC_PAGES } = {}) {
  const set = new Set();
  const queue = [];
  const add = (p, why) => {
    if (!p || set.has(p)) return;
    if (!SAFE_PATH.test(p)) fail(`Ruta con caracteres no admitidos en la lista pública: ${p} (${why})`);
    if (isNotUploaded(p)) fail(`La página pública necesita un fichero que no se sube: ${p} (${why})`);
    const file = path.join(dist, p);
    if (!fs.existsSync(file) || !fs.statSync(file).isFile()) fail(`No existe en el dist: ${p} (${why})`);
    set.add(p);
    queue.push(p);
  };
  for (const page of pages) {
    const htmlPath = path.join(dist, page, 'index.html');
    if (!fs.existsSync(htmlPath)) fail(`Falta la página prerenderizada /${page}`);
    const original = fs.readFileSync(htmlPath, 'utf8');
    const html = nojs ? nojsVariant(original) : original;
    const entries = [];
    for (const ref of htmlRefs(html)) {
      const p = sameOriginPath(ref.value, `/${page}/`);
      if (!p || p === `/${page}` || p === `/${page}/`) continue;
      add(p, `/${page} src/href`);
      if (ref.entry && p.endsWith('.js')) entries.push(p);
    }
    if (nojs) continue;
    if (!entries.length) fail(`/${page} no tiene módulo de entrada <script type=module src>`);
    let found = false;
    for (const entry of entries) {
      const files = lazyRouteFiles(fs.readFileSync(path.join(dist, entry), 'utf8'), page);
      if (files) {
        found = true;
        for (const f of files) add(f, `ruta perezosa de /${page}`);
      }
    }
    if (!found) fail(`No encuentro la ruta perezosa de /${page} en ${entries.join(', ')}: revisar el formato del bundle`);
  }
  while (queue.length) {
    const p = queue.shift();
    const file = path.join(dist, p);
    const dir = p.slice(0, p.lastIndexOf('/') + 1);
    if (p.endsWith('.js')) {
      for (const spec of jsStaticImports(fs.readFileSync(file, 'utf8'))) add(sameOriginPath(spec, dir), `import estático de ${p}`);
    } else if (p.endsWith('.css')) {
      for (const ref of cssRefs(fs.readFileSync(file, 'utf8'))) add(sameOriginPath(ref, dir), `url() de ${p}`);
    }
  }
  const list = [...set].sort();
  if (nojs && list.some((p) => /\.m?js$/.test(p))) fail('Modo sin JS con un .js en la lista pública');
  return list;
}

export function renderBlock({ prerendered, assets, rootPublic, nojs, fingerprint }) {
  for (const p of [...prerendered, ...assets]) if (p.includes('|') || p.includes("'") || p.includes('\\')) fail(`Ruta no serializable: ${p}`);
  return [
    `${BEGIN} por build_gate.mjs (no editar a mano) · dist ${fingerprint}`,
    `var ROOT_PUBLIC = ${rootPublic ? 'true' : 'false'};`,
    `var LEGAL_NOJS = ${nojs ? 'true' : 'false'};`,
    `var PRERENDERED = '|${prerendered.join('|')}|';`,
    `var PUBLIC_ASSETS = '|${assets.join('|')}|';`,
    END,
  ].join('\n');
}

export function fingerprintOf(dist, prerendered, assets) {
  const hash = crypto.createHash('sha256');
  for (const p of [...prerendered.map((r) => r + '/index.html'), ...assets, '/spa.html']) {
    hash.update(p + '\0');
    hash.update(fs.readFileSync(path.join(dist, p)));
  }
  return hash.digest('hex').slice(0, 16);
}

export function build(dist, { rootPublic = true, nojs = true } = {}) {
  if (!fs.existsSync(path.join(dist, 'spa.html'))) fail('El dist no tiene spa.html');
  const prerendered = listPrerendered(dist);
  for (const page of PUBLIC_PAGES) if (!prerendered.includes('/' + page)) fail(`Falta /${page} en el dist`);
  const assets = publicAssets(dist, { nojs });
  const fingerprint = fingerprintOf(dist, prerendered, assets);
  const variants = {};
  if (nojs) for (const page of PUBLIC_PAGES) variants[`${page}/${NOJS_NAME}`] = nojsVariant(fs.readFileSync(path.join(dist, page, 'index.html'), 'utf8'));
  return { prerendered, assets, fingerprint, variants, block: renderBlock({ prerendered, assets, rootPublic, nojs, fingerprint }) };
}

export function replaceBlock(source, block) {
  const a = source.indexOf(BEGIN);
  const b = source.indexOf(END);
  if (a < 0 || b < a) fail('gate-default.js no tiene el bloque GENERATED');
  return source.slice(0, a) + block + source.slice(b + END.length);
}

export function currentBlock(source) {
  const a = source.indexOf(BEGIN);
  const b = source.indexOf(END);
  return a < 0 || b < a ? null : source.slice(a, b + END.length);
}

function main(argv) {
  const args = argv.slice(2);
  const distIndex = args.indexOf('--dist');
  if (distIndex < 0 || !args[distIndex + 1]) {
    console.error('Uso: node build_gate.mjs --dist <ruta/al/dist> [--write | --check] [--legal-js] [--root-gated]');
    return 64;
  }
  const dist = path.resolve(args[distIndex + 1]);
  const nojs = !args.includes('--legal-js');
  const result = build(dist, { rootPublic: !args.includes('--root-gated'), nojs });
  const source = fs.readFileSync(TARGET, 'utf8');
  const next = replaceBlock(source, result.block);
  const bytes = Buffer.byteLength(next, 'utf8');
  const js = result.assets.filter((p) => p.endsWith('.js'));
  const jsBytes = js.reduce((n, p) => n + fs.statSync(path.join(dist, p)).size, 0);
  console.log(`dist ${dist}`);
  console.log(`modo ${nojs ? 'LEGAL_NOJS (páginas legales sin JS para quien no tiene cookie)' : '--legal-js (cierre exacto con JS)'}`);
  console.log(`huella ${result.fingerprint} · ${result.prerendered.length} rutas prerenderizadas · ${result.assets.length} assets públicos (${js.length} JS, ${jsBytes} bytes de JS)`);
  for (const p of result.assets) console.log(`  público ${p} (${fs.statSync(path.join(dist, p)).size} B)`);
  for (const name of Object.keys(result.variants)) console.log(`  variante public-pages/${name} → subir al bucket como /${name}`);
  console.log(`gate-default.js resultante: ${bytes} bytes (límite ${MAX_FUNCTION_BYTES})`);
  if (bytes > MAX_FUNCTION_BYTES) fail(`gate-default.js pasaría de ${MAX_FUNCTION_BYTES} bytes`);
  if (args.includes('--check')) {
    let ok = currentBlock(source) === result.block;
    for (const [name, html] of Object.entries(result.variants)) {
      const file = path.join(PAGES_DIR, name);
      if (!fs.existsSync(file) || fs.readFileSync(file, 'utf8') !== html) ok = false;
    }
    if (!ok) {
      console.error('gate-default.js o public-pages/ NO coinciden con este dist: ejecutar con --write.');
      return 1;
    }
    console.log('OK: bloque GENERATED y public-pages/ coinciden con el dist.');
  } else if (args.includes('--write')) {
    fs.writeFileSync(TARGET, next);
    fs.rmSync(PAGES_DIR, { recursive: true, force: true });
    for (const [name, html] of Object.entries(result.variants)) {
      fs.mkdirSync(path.dirname(path.join(PAGES_DIR, name)), { recursive: true });
      fs.writeFileSync(path.join(PAGES_DIR, name), html);
    }
    console.log('Escrito el bloque GENERATED en gate-default.js' + (nojs ? ' y las variantes en public-pages/' : ''));
  }
  return 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.exitCode = main(process.argv);
  } catch (error) {
    if (error.code !== 'BUILD_GATE') throw error;
    console.error('ERROR: ' + error.message);
    process.exitCode = 2;
  }
}
