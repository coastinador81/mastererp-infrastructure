// test/deploy_tests.mjs · Pruebas de deploy_edge.mjs (paso 13) con el AWS CLI falso (test/fake-bin/aws,
// nunca llama a AWS) y, para verify, con el emulador local del borde. Las ejecuta test_gate.mjs.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn, spawnSync } from 'node:child_process';

const EDGE_PARAM = '/uonify/dev/edge/origin-verify';
const KVS_ARN = 'arn:aws:cloudfront::123456789012:key-value-store/00000000-1111-2222-3333-444444444444';
const FN = { d: 'uonify-dev-gate-default', a: 'uonify-dev-gate-api' };
const CACHE_DISABLED = '4135ea2d-6df8-44a3-9df3-4b5a84be39ad';
const ALL_VIEWER_EXCEPT_HOST = 'b689b0a8-53d0-40ab-baf2-68738e2966ac';

export async function deployTests({ test, assert, eq, deepEq, HERE, FAKE_BIN, TMP, DIST, DEPLOY }) {
  const dir = path.join(TMP, 'deploy');
  const state = path.join(dir, 'state.json');
  const log = path.join(dir, 'aws-argv.log');
  const tmpdir = path.join(dir, 'tmpdir');
  const out = path.join(dir, 'out');
  const fixture = JSON.parse(fs.readFileSync(path.join(HERE, 'test', 'fixtures', 'e4n1-config.json'), 'utf8'));
  const EDGE1 = crypto.randomBytes(48).toString('base64url');
  const EDGE2 = crypto.randomBytes(48).toString('base64url');
  const KVS_HASH = crypto.randomBytes(32).toString('hex');
  const KVS_KEY = crypto.randomBytes(32).toString('hex');
  const SECRETS = [EDGE1, EDGE2, KVS_HASH, KVS_KEY];
  const local = { d: fs.readFileSync(path.join(HERE, 'gate-default.js')), a: fs.readFileSync(path.join(HERE, 'gate-api.js')) };
  const benchOk = path.join(dir, 'bench-ok.mjs');
  const benchFail = path.join(dir, 'bench-fail.mjs');
  const homeBackups = path.join(path.dirname(DEPLOY), 'backups');
  const homeBackupsBefore = fs.existsSync(homeBackups);

  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(benchOk, "console.log('61/61 pruebas OK (banco simulado)');\n");
  fs.writeFileSync(benchFail, "console.log('60/61 pruebas OK (banco simulado)'); process.exitCode = 1;\n");

  const read = () => JSON.parse(fs.readFileSync(state, 'utf8'));
  const write = (s) => fs.writeFileSync(state, JSON.stringify(s));
  const reset = (extra = {}) => {
    write({
      etag: 'ETAG-0', items: {}, status: 'READY', kvsMissing: true, functions: {},
      distribution: { etag: fixture.ETag, config: structuredClone(fixture.DistributionConfig) },
      ssm: { [EDGE_PARAM]: { Type: 'SecureString', Value: EDGE1, Version: 1 } }, s3: {}, ...extra,
    });
    fs.writeFileSync(log, '');
    fs.rmSync(tmpdir, { recursive: true, force: true });
    fs.mkdirSync(tmpdir, { recursive: true });
  };
  const patch = (fn) => {
    const s = read();
    fn(s);
    write(s);
  };
  const run = (args, env = {}) => spawnSync(process.execPath, [DEPLOY, ...args], {
    encoding: 'utf8',
    env: {
      ...process.env, PATH: FAKE_BIN + ':' + process.env.PATH, FAKE_KVS_STATE: state, FAKE_AWS_LOG: log, TMPDIR: tmpdir, EDGE_BENCH: benchOk,
      EDGE_POLL_MS: '5', AWS_PROFILE: 'perfil-de-prueba', AWS_CONFIG_FILE: '/dev/null', AWS_SHARED_CREDENTIALS_FILE: '/dev/null', ...env,
    },
  });
  const calls = () => fs.readFileSync(log, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  const WRITE_OPS = /^(create-|update-|publish-|put-|delete-)/;
  const writes = () => calls().filter((a) => WRITE_OPS.test(a[1] || ''));
  const clearLog = () => fs.writeFileSync(log, '');
  const noLeak = (r, label) => {
    const argvText = fs.readFileSync(log, 'utf8');
    for (const s of SECRETS) {
      assert(!r.stdout.includes(s) && !r.stderr.includes(s), `${label}: la salida contiene un secreto`);
      assert(!argvText.includes(s), `${label}: un secreto viaja como argumento de aws`);
    }
    assert(fs.readdirSync(tmpdir).length === 0, `${label}: quedan temporales: ${fs.readdirSync(tmpdir)}`);
  };
  const ok = (r, label) => eq(r.status, 0, `${label}: exit (${(r.stderr || r.stdout).trim().split('\n').slice(-2).join(' | ')})`);
  const seedPublished = () => patch((s) => {
    s.kvsMissing = false;
    s.items = { gate_cred_sha256: KVS_HASH, gate_hmac_key: KVS_KEY };
    for (const k of ['d', 'a']) {
      const f = { code: local[k].toString('base64'), config: { Comment: 'x', Runtime: 'cloudfront-js-2.0', KeyValueStoreAssociations: { Quantity: 1, Items: [{ KeyValueStoreARN: KVS_ARN }] } }, etag: 'E-' + k };
      s.functions[FN[k]] = { DEVELOPMENT: f, LIVE: { ...f, etag: 'EL-' + k } };
    }
  });
  const arn = (name) => `arn:aws:cloudfront::277352717693:function/${name}`;
  const apiOrigin = (cfg) => cfg.Origins.Items.find((o) => o.Id === 'uonify-dev-origin');

  await test('plan: solo lectura, sin secretos; dice qué falta', async () => {
    reset();
    const r = run(['plan']);
    ok(r, 'plan');
    eq(writes().length, 0, 'escrituras en AWS');
    assert(/no existe \(lo crea functions --apply\)/.test(r.stdout) && /todavía no se puede preparar/.test(r.stdout), r.stdout);
    noLeak(r, 'plan');
    eq(run(['plan', '--apply']).status, 64, 'plan --apply');
  });
  await test('functions --apply: pasa el banco, crea el KVS y las 2 funciones en DEVELOPMENT; repetir no cambia nada', async () => {
    reset();
    eq(run(['functions']).status, 0, 'simulación');
    eq(writes().length, 0, 'la simulación escribe');
    const r = run(['functions', '--apply']);
    ok(r, 'functions');
    assert(/banco simulado/.test(r.stdout), 'no ha pasado el banco');
    const s = read();
    assert(!s.kvsMissing && s.status === 'READY', 'KVS');
    for (const k of ['d', 'a']) {
      const f = s.functions[FN[k]];
      assert(f && f.DEVELOPMENT && !f.LIVE, `${FN[k]}: solo DEVELOPMENT`);
      eq(f.DEVELOPMENT.code, local[k].toString('base64'), `${FN[k]}: código`);
      eq(f.DEVELOPMENT.config.Runtime, 'cloudfront-js-2.0', 'runtime');
      deepEq(f.DEVELOPMENT.config.KeyValueStoreAssociations, { Quantity: 1, Items: [{ KeyValueStoreARN: KVS_ARN }] }, 'KVS asociado');
    }
    clearLog();
    ok(run(['functions', '--apply']), 'repetir');
    eq(writes().length, 0, 'repetir escribe');
    patch((st) => { st.functions[FN.a].DEVELOPMENT.code = Buffer.from('// otro código').toString('base64'); });
    const etag = read().functions[FN.a].DEVELOPMENT.etag;
    clearLog();
    ok(run(['functions', '--apply']), 'actualizar');
    const upd = writes();
    eq(upd.length, 1, 'una sola actualización');
    eq(upd[0][1], 'update-function', 'operación');
    eq(upd[0][upd[0].indexOf('--if-match') + 1], etag, 'con el ETag leído');
    eq(read().functions[FN.a].DEVELOPMENT.code, local.a.toString('base64'), 'código actualizado');
  });
  await test('functions: si el banco offline falla no se sube nada', async () => {
    reset();
    const r = run(['functions', '--apply'], { EDGE_BENCH: benchFail });
    eq(r.status, 2, 'exit');
    assert(/banco offline/.test(r.stderr), r.stderr);
    eq(writes().length, 0, 'escrituras');
  });
  await test('publish: sin las claves del KVS no publica; con ellas, test-function todo OK y LIVE = código local', async () => {
    reset();
    ok(run(['functions', '--apply']), 'functions');
    clearLog();
    const r1 = run(['publish', '--apply']);
    eq(r1.status, 2, 'sin claves');
    assert(/faltan en el KeyValueStore: gate_cred_sha256, gate_hmac_key/.test(r1.stdout + r1.stderr), r1.stdout + r1.stderr);
    eq(writes().length, 0, 'ha publicado sin claves');
    patch((s) => { s.items = { gate_cred_sha256: KVS_HASH, gate_hmac_key: KVS_KEY }; });
    const r2 = run(['publish', '--apply']);
    ok(r2, 'publish');
    assert(/(\d+)\/\1 casos OK en DEVELOPMENT/.test(r2.stdout), r2.stdout);
    const s = read();
    for (const k of ['d', 'a']) eq(s.functions[FN[k]].LIVE.code, local[k].toString('base64'), `${FN[k]} LIVE`);
    deepEq(s.published.sort(), [FN.a, FN.d].sort(), 'publicadas');
    noLeak(r2, 'publish');
    clearLog();
    ok(run(['publish', '--apply']), 'repetir');
    eq(writes().length, 0, 'repetir publica');
  });
  await test('distribution sin --apply: enseña el contrato y los cambios, sin secretos y sin escribir', async () => {
    reset();
    seedPublished();
    clearLog();
    const r = run(['distribution']);
    ok(r, 'distribution');
    eq(writes().length, 0, 'escrituras');
    for (const s of ['X-Origin-Verify', 'Managed-AllViewerExceptHostHeader', 'Managed-CachingDisabled', 'https-only', 'TLSv1.2', 'simulación', '«valor de SSM', 'uonify-dev-security-headers', 'HSTS 31536000 s sin includeSubDomains', '«se crea con --apply»']) assert(r.stdout.includes(s), `falta «${s}» en la salida`);
    assert(!read().headersPolicies, 'la simulación ha creado la política de cabeceras');
    noLeak(r, 'distribution');
  });
  await test('distribution --apply: contrato exacto de /api/* y del origen; el resto de la configuración intacto', async () => {
    reset();
    seedPublished();
    const backup = path.join(out, 'antes-paso13.json');
    const r = run(['distribution', '--apply', '--backup', backup, '--skip-verify']);
    ok(r, 'distribution --apply');
    const s = read();
    const cfg = s.distribution.config;
    const o = apiOrigin(cfg);
    assert(o, 'falta el origen uonify-dev-origin');
    eq(o.DomainName, 'origin-dev.uonify.com', 'DomainName');
    deepEq(o.CustomHeaders, { Quantity: 1, Items: [{ HeaderName: 'X-Origin-Verify', HeaderValue: EDGE1 }] }, 'cabecera de origen = SSM');
    const c = o.CustomOriginConfig;
    eq(c.OriginProtocolPolicy, 'https-only', 'protocolo hacia el origen');
    eq(c.HTTPSPort, 443, 'puerto');
    deepEq(c.OriginSslProtocols, { Quantity: 1, Items: ['TLSv1.2'] }, 'TLS');
    assert(c.OriginReadTimeout >= 30 && c.OriginReadTimeout <= 60, 'lectura ≤ 60 s (cuota) y ≤ 180 s (nginx)');
    assert(c.OriginKeepaliveTimeout < 75, 'keep-alive < 75 s (nginx)');
    eq(cfg.CacheBehaviors.Quantity, 1, 'comportamientos');
    const b = cfg.CacheBehaviors.Items[0];
    eq(b.PathPattern, '/api/*', 'PathPattern');
    eq(b.TargetOriginId, 'uonify-dev-origin', 'destino');
    eq(b.ViewerProtocolPolicy, 'https-only', 'visor https-only');
    deepEq([...b.AllowedMethods.Items].sort(), ['DELETE', 'GET', 'HEAD', 'OPTIONS', 'PATCH', 'POST', 'PUT'], '7 métodos');
    deepEq([...b.AllowedMethods.CachedMethods.Items].sort(), ['GET', 'HEAD'], 'métodos cacheados');
    eq(b.CachePolicyId, CACHE_DISABLED, 'Managed-CachingDisabled');
    eq(b.OriginRequestPolicyId, ALL_VIEWER_EXCEPT_HOST, 'Managed-AllViewerExceptHostHeader (sin el Host del visor)');
    assert(!b.ForwardedValues && b.MinTTL === undefined, 'sin ajustes heredados');
    deepEq(b.FunctionAssociations, { Quantity: 1, Items: [{ FunctionARN: arn(FN.a), EventType: 'viewer-request' }] }, 'gate-api en /api/*');
    deepEq(cfg.DefaultCacheBehavior.FunctionAssociations, { Quantity: 1, Items: [{ FunctionARN: arn(FN.d), EventType: 'viewer-request' }] }, 'gate-default');
    const hp = Object.values(s.headersPolicies || {});
    eq(hp.length, 1, 'una política de cabeceras');
    const hc = hp[0].ResponseHeadersPolicyConfig;
    eq(hc.Name, 'uonify-dev-security-headers', 'nombre de la política');
    deepEq(hc.SecurityHeadersConfig.StrictTransportSecurity, { Override: true, IncludeSubdomains: false, Preload: false, AccessControlMaxAgeSec: 31536000 }, 'HSTS 1 año sin subdominios ni preload');
    deepEq(hc.SecurityHeadersConfig.ContentTypeOptions, { Override: true }, 'nosniff');
    deepEq(hc.SecurityHeadersConfig.FrameOptions, { Override: true, FrameOption: 'DENY' }, 'sin marcos');
    deepEq(hc.CustomHeadersConfig, { Quantity: 1, Items: [{ Header: 'X-Robots-Tag', Value: 'noindex, nofollow', Override: true }] }, 'noindex');
    assert(!hc.CorsConfig && !hc.RemoveHeadersConfig, 'la política no toca CORS ni quita cabeceras');
    eq(b.ResponseHeadersPolicyId, hp[0].Id, 'política en /api/*');
    eq(cfg.DefaultCacheBehavior.ResponseHeadersPolicyId, hp[0].Id, 'política en el comportamiento por defecto');
    const rest = structuredClone(cfg);
    rest.Origins = { Quantity: 1, Items: rest.Origins.Items.filter((x) => x.Id !== 'uonify-dev-origin') };
    rest.CacheBehaviors = { Quantity: 0 };
    rest.DefaultCacheBehavior.FunctionAssociations = { Quantity: 0 };
    delete rest.DefaultCacheBehavior.ResponseHeadersPolicyId;
    deepEq(rest, fixture.DistributionConfig, 'el resto de la configuración ha cambiado');
    const f = s.configFiles[s.configFiles.length - 1];
    eq(f.mode, 0o600, 'permisos del fichero con el secreto');
    eq(f.dirMode, 0o700, 'permisos de su directorio');
    assert(!fs.existsSync(f.path), 'el fichero con el secreto sigue existiendo');
    eq(fs.statSync(backup).mode & 0o777, 0o600, 'permisos de la copia');
    const saved = JSON.parse(fs.readFileSync(backup, 'utf8'));
    eq(saved.ETag, fixture.ETag, 'ETag de la copia');
    deepEq(saved.DistributionConfig, fixture.DistributionConfig, 'la copia es la configuración previa');
    noLeak(r, 'distribution --apply');
    assert(!fs.existsSync(homeBackups) || homeBackupsBefore, 'la prueba ha escrito en backups/ de la carpeta');
  });
  await test('distribution repetida: nada que cambiar (no llama a update-distribution)', async () => {
    clearLog();
    const r = run(['distribution', '--apply', '--backup', path.join(out, 'no-debe-existir.json'), '--skip-verify']);
    ok(r, 'repetir');
    assert(/nada que cambiar/.test(r.stdout), r.stdout);
    eq(writes().length, 0, 'escrituras');
    assert(!fs.existsSync(path.join(out, 'no-debe-existir.json')), 'copia innecesaria');
  });
  await test('rotación (2 líneas en SSM): pone la segunda; la copia previa lleva la cabecera en blanco', async () => {
    patch((s) => { s.ssm[EDGE_PARAM] = { Type: 'SecureString', Value: `${EDGE1}\n${EDGE2}\n`, Version: 2 }; });
    const backup = path.join(out, 'antes-rotacion.json');
    const r = run(['distribution', '--apply', '--backup', backup, '--skip-verify']);
    ok(r, 'rotación');
    eq(apiOrigin(read().distribution.config).CustomHeaders.Items[0].HeaderValue, EDGE2, 'cabecera = línea 2');
    assert(/línea 2 de 2/.test(r.stdout) && /valor anterior de SSM/.test(r.stdout), r.stdout);
    const text = fs.readFileSync(backup, 'utf8');
    assert(!text.includes(EDGE1) && !text.includes(EDGE2), 'la copia contiene el secreto');
    const saved = JSON.parse(text);
    deepEq(saved.RedactedHeaders, [{ OriginId: 'uonify-dev-origin', HeaderName: 'X-Origin-Verify' }], 'RedactedHeaders');
    assert(/^__REDACTED__/.test(apiOrigin(saved.DistributionConfig).CustomHeaders.Items[0].HeaderValue), 'marca de cabecera en blanco');
    noLeak(r, 'rotación');
  });
  await test('backup: copia 0600 con las cabeceras de origen en blanco', async () => {
    const file = path.join(out, 'backup.json');
    const r = run(['backup', '--out', file]);
    ok(r, 'backup');
    const text = fs.readFileSync(file, 'utf8');
    for (const s of SECRETS) assert(!text.includes(s), 'la copia contiene un secreto');
    eq(fs.statSync(file).mode & 0o777, 0o600, 'permisos');
    noLeak(r, 'backup');
  });
  await test('rollback: desde una copia en blanco reinyecta la cabecera de SSM; desde la de antes del paso 13 lo deja como estaba', async () => {
    patch((s) => { s.ssm[EDGE_PARAM] = { Type: 'SecureString', Value: EDGE1, Version: 3 }; });
    clearLog();
    const dry = run(['rollback', '--from', path.join(out, 'backup.json')]);
    ok(dry, 'simulación');
    eq(writes().length, 0, 'la simulación escribe');
    const r1 = run(['rollback', '--from', path.join(out, 'backup.json'), '--apply', '--backup', path.join(out, 'antes-rollback-1.json')]);
    ok(r1, 'rollback 1');
    eq(apiOrigin(read().distribution.config).CustomHeaders.Items[0].HeaderValue, EDGE1, 'cabecera reinyectada desde SSM');
    noLeak(r1, 'rollback 1');
    const r2 = run(['rollback', '--from', path.join(HERE, 'test', 'fixtures', 'e4n1-config.json'), '--apply', '--backup', path.join(out, 'antes-rollback-2.json')]);
    ok(r2, 'rollback 2');
    deepEq(read().distribution.config, fixture.DistributionConfig, 'configuración de antes del paso 13');
    noLeak(r2, 'rollback 2');
    const otra = structuredClone(fixture);
    otra.DistributionConfig.CallerReference = 'otra-distribucion';
    fs.writeFileSync(path.join(out, 'otra.json'), JSON.stringify(otra));
    eq(run(['rollback', '--from', path.join(out, 'otra.json'), '--apply']).status, 2, 'copia de otra distribución');
  });
  await test('política de cabeceras: si la propia no es la esperada o la distribución ya tiene otra, falla cerrada sin escribir', async () => {
    const cases = [
      ['política propia con includeSubDomains', (s) => {
        s.headersPolicies = { 'p-1': { Id: 'p-1', ResponseHeadersPolicyConfig: { Name: 'uonify-dev-security-headers', SecurityHeadersConfig: { StrictTransportSecurity: { Override: true, IncludeSubdomains: true, Preload: false, AccessControlMaxAgeSec: 31536000 }, ContentTypeOptions: { Override: true }, FrameOptions: { Override: true, FrameOption: 'DENY' } }, CustomHeadersConfig: { Quantity: 1, Items: [{ Header: 'X-Robots-Tag', Value: 'noindex, nofollow', Override: true }] } } } };
      }, /no es la esperada/],
      ['otra política en el comportamiento por defecto', (s) => {
        s.headersPolicies = { 'otra': { Id: 'otra', ResponseHeadersPolicyConfig: { Name: 'de-otro-equipo' } } };
        s.distribution.config.DefaultCacheBehavior.ResponseHeadersPolicyId = 'otra';
      }, /ya tiene otra política de cabeceras \(otra\)/],
    ];
    for (const [label, mutate, message] of cases) {
      reset();
      seedPublished();
      patch(mutate);
      const before = read();
      clearLog();
      const r = run(['distribution', '--apply', '--backup', path.join(out, `cabeceras-${crypto.randomBytes(3).toString('hex')}.json`), '--skip-verify']);
      eq(r.status, 2, `${label}: exit`);
      assert(message.test(r.stderr), `${label}: ${r.stderr}`);
      eq(writes().length, 0, `${label}: escrituras`);
      deepEq(read().distribution, before.distribution, `${label}: la distribución ha cambiado`);
      deepEq(read().headersPolicies, before.headersPolicies, `${label}: las políticas han cambiado`);
      noLeak(r, label);
    }
  });
  await test('distribution falla cerrada sin tocar nada (estado inesperado, ETag, SSM, cuenta, código LIVE)', async () => {
    const cases = [
      ['respuestas de error personalizadas', (s) => { s.distribution.config.CustomErrorResponses = { Quantity: 1, Items: [{ ErrorCode: 403, ResponsePagePath: '/index.html', ResponseCode: '200', ErrorCachingMinTTL: 10 }] }; }, {}, /respuestas de error personalizadas/],
      ['comportamiento inesperado', (s) => { s.distribution.config.CacheBehaviors = { Quantity: 1, Items: [{ ...s.distribution.config.DefaultCacheBehavior, PathPattern: '/otra/*' }] }; }, {}, /comportamiento inesperado/],
      ['otro cambio se adelanta (ETag)', () => {}, { FAKE_AWS_DIST_CONFLICT: '1' }, /ha cambiado desde que se leyó/],
      ['SSM con formato malo', (s) => { s.ssm[EDGE_PARAM].Value = 'corto'; }, {}, /formato esperado/],
      ['SSM sin el parámetro', (s) => { delete s.ssm[EDGE_PARAM]; }, {}, /no existe \/uonify\/dev\/edge\/origin-verify/],
      ['otra cuenta', (s) => { s.account = '111111111111'; }, {}, /no a 277352717693/],
      ['código LIVE distinto del local', (s) => { s.functions[FN.d].LIVE.code = Buffer.from('// otro').toString('base64'); }, {}, /código LIVE/],
      ['error de AWS que repite el secreto', () => {}, { FAKE_AWS_ECHO_SECRET: '1' }, /«secreto»/],
    ];
    for (const [label, mutate, env, message] of cases) {
      reset();
      seedPublished();
      patch(mutate);
      const before = read().distribution;
      const r = run(['distribution', '--apply', '--backup', path.join(out, `fallo-${crypto.randomBytes(3).toString('hex')}.json`), '--skip-verify'], env);
      eq(r.status, 2, `${label}: exit`);
      assert(message.test(r.stderr), `${label}: ${r.stderr}`);
      deepEq(read().distribution, before, `${label}: la distribución ha cambiado`);
      noLeak(r, label);
    }
  });
  await test('legal --apply: sube las 2 variantes sin JS (text/html, no-cache); repetir no sube', async () => {
    reset();
    clearLog();
    ok(run(['legal']), 'simulación');
    eq(writes().length, 0, 'la simulación escribe');
    ok(run(['legal', '--apply']), 'legal');
    const s = read();
    for (const page of ['privacidad', 'terminos']) {
      const o = s.s3[`${page}/index.nojs.html`];
      assert(o, `falta ${page}`);
      eq(o.ContentType, 'text/html; charset=utf-8', 'Content-Type');
      eq(o.CacheControl, 'no-cache', 'Cache-Control');
      eq(o.body, fs.readFileSync(path.join(HERE, 'public-pages', page, 'index.nojs.html')).toString('base64'), 'contenido');
    }
    clearLog();
    ok(run(['legal', '--apply']), 'repetir');
    eq(writes().length, 0, 'repetir sube');
  });
  await test('verify contra el emulador local: todo OK; con nginx sin X-Origin-Verify o sin la política de cabeceras → FALLO con diagnóstico', async () => {
    for (const mode of ['ok', 'forbidden', 'no-headers']) {
      const forbidden = mode === 'forbidden';
      const extra = forbidden ? ['--origin-forbidden'] : mode === 'no-headers' ? ['--no-headers-policy'] : [];
      const child = spawn(process.execPath, [path.join(HERE, 'test', 'serve_emulation.mjs'), '--port', '0', ...extra], {
        env: { ...process.env, GATE_DIST: DIST }, stdio: ['ignore', 'pipe', 'pipe'],
      });
      try {
        const url = await new Promise((resolve, reject) => {
          let text = '';
          const timer = setTimeout(() => reject(new Error('el emulador no arranca')), 10000);
          child.stdout.on('data', (chunk) => {
            text += chunk;
            const m = /en (http:\/\/127\.0\.0\.1:\d+)/.exec(text);
            if (m) {
              clearTimeout(timer);
              resolve(m[1]);
            }
          });
          child.on('exit', () => reject(new Error('el emulador ha terminado')));
        });
        const r = await new Promise((resolve) => {
          const p = spawn(process.execPath, [DEPLOY, 'verify', '--base-url', url, '--http-url', 'off'], { env: process.env });
          let stdout = '';
          let stderr = '';
          p.stdout.on('data', (c) => { stdout += c; });
          p.stderr.on('data', (c) => { stderr += c; });
          p.on('close', (status) => resolve({ status, stdout, stderr }));
        });
        if (mode === 'ok') {
          eq(r.status, 0, 'verify ' + r.stdout);
          assert(/(\d+)\/\1 OK · 0 avisos · 0 fallos/.test(r.stdout), r.stdout);
          assert(/OK\s+HSTS \(31536000 s, sin subdominios\) y nosniff/.test(r.stdout) && /OK\s+HSTS en \/api\/health/.test(r.stdout), r.stdout);
        } else if (mode === 'no-headers') {
          eq(r.status, 1, 'verify sin la política de cabeceras');
          assert(/FALLO\s+HSTS \(31536000 s, sin subdominios\) y nosniff.*\(falta\)/.test(r.stdout), r.stdout);
          assert(/FALLO\s+HSTS en \/api\/health/.test(r.stdout), r.stdout);
        } else {
          eq(r.status, 1, 'verify con nginx que rechaza');
          assert(/FALLO\s+\/api\/health.*X-Origin-Verify falta o no coincide/.test(r.stdout), r.stdout);
          assert(/OK\s+\/api\/auth\/session/.test(r.stdout), 'la puerta de /api sigue respondiendo antes que el origen');
        }
      } finally {
        child.kill();
      }
    }
  });
  fs.rmSync(dir, { recursive: true, force: true });
}
