/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import test from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { build } from 'esbuild';
import { loadTypeScript } from './helpers/load-typescript.mjs';
import { isTDesignVueModule, transformTDesignVueSource, tdesignVueCompatVitePlugin, tdesignVueCompatEsbuildPlugin } from '../tools/tdesign-vue-compat.mjs';
const root = new URL('../', import.meta.url).pathname;
const { preserveVue3ComponentModel } = loadTypeScript(new URL('../src/platform/compat/vue3-component-model.ts', import.meta.url));

test('TDesign facade preserves component identity, model/render modes, slots and setup exposure', () => {
  const facade = loadTypeScript(new URL('../src/platform/compat/tdesign/native-vue-runtime.ts', import.meta.url), {
    '../vue-runtime.mjs': Vue, '../vue3-component-model': { preserveVue3ComponentModel },
  });
  const exposed = {}, slots = { default: () => ['synthetic'] };
  const options = { name: 'SyntheticInput', compatConfig: { customFlag: true },
    setup(props, context) { context.expose(exposed); return () => context.slots.default(); } };
  const component = facade.defineComponent(options);
  assert.equal(component, options);
  assert.deepEqual(component.compatConfig, { customFlag: true, MODE: 3, COMPONENT_V_MODEL: false, RENDER_FUNCTION: false });
  let actual;
  const render = component.setup({}, { slots, expose: value => { actual = value; } });
  assert.equal(actual, exposed);
  assert.deepEqual(render(), ['synthetic']);
  assert.equal(facade.h, Vue.h);
});

test('production transform and development optimizer only redirect TDesign modules', () => {
  const source = `import { defineComponent } from 'vue'; export default defineComponent({});`;
  const plugin = tdesignVueCompatVitePlugin(root);
  const id = '/synthetic/node_modules/tdesign-vue-next/es/input/input.mjs';
  assert.equal(isTDesignVueModule(id), true);
  assert.equal(isTDesignVueModule(id.replaceAll('/', '\\')), true);
  assert.equal(isTDesignVueModule('/synthetic/src/input.ts'), false);
  assert.equal(plugin.transform(source, '/synthetic/src/input.ts'), undefined);
  assert.equal(plugin.transform(source, id).code, transformTDesignVueSource(source, root));
  assert.match(plugin.transform(source, id).code, /tdesign\/native-vue-runtime\.ts/);
  assert.equal(transformTDesignVueSource(source, root).includes("from 'vue'"), false);
});

test('unused public TDesign components remain tree-shakeable while lazy imports retain native metadata', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'bklog-entry-compat-'));
  try {
    const library = join(dir, 'node_modules/tdesign-vue-next');
    mkdirSync(join(library, 'es'), { recursive: true });
    writeFileSync(join(library, 'package.json'), JSON.stringify({ name: 'tdesign-vue-next', type: 'module', module: './es/index.js', sideEffects: false }));
    writeFileSync(join(library, 'es/index.js'), `export { default as Used } from './used.js'; export { default as Unused } from './unused.js';`);
    writeFileSync(join(library, 'es/used.js'), `import { defineComponent } from 'vue'; export default defineComponent({ name: 'SYNTHETIC_USED_COMPONENT' });`);
    writeFileSync(join(library, 'es/unused.js'), `import { defineComponent } from 'vue'; export default defineComponent({ name: 'SYNTHETIC_UNUSED_COMPONENT' });`);
    writeFileSync(join(dir, 'lazy.js'), `export { Used } from 'tdesign-vue-next';`);
    writeFileSync(join(dir, 'entry.js'), `export async function load() { return (await import('./lazy.js')).Used; }`);
    const result = await build({ entryPoints: [join(dir, 'entry.js')], bundle: true, platform: 'node', format: 'cjs', write: false,
      plugins: [tdesignVueCompatEsbuildPlugin(root)], logLevel: 'silent' });
    const code = result.outputFiles[0].text;
    assert.doesNotMatch(code, /SYNTHETIC_UNUSED_COMPONENT/);
    assert.match(code, /SYNTHETIC_USED_COMPONENT/);
    const file = join(dir, 'bundle.cjs');
    writeFileSync(file, code);
    const component = await createRequire(import.meta.url)(file).load();
    assert.equal(component.compatConfig.MODE, 3);
    assert.equal(component.compatConfig.COMPONENT_V_MODEL, false);
    assert.equal(component.compatConfig.RENDER_FUNCTION, false);
  } finally { rmSync(dir, { recursive: true, force: true }); }
});

const rumModule = sdk => loadTypeScript(new URL('../src/platform/observability/open-telemetry.ts', import.meta.url), {
  '@blueking/open-telemetry': sdk,
});
const withWindow = async (value, run) => {
  const previous = globalThis.window;
  globalThis.window = value;
  try { await run(); } finally {
    if (previous === undefined) delete globalThis.window;
    else globalThis.window = previous;
  }
};

test('disabled and Monitor RUM do not load or construct the optional SDK', async () => {
  for (const state of [
    { BKLOG_RUM: { enabled: false, endpoint: 'https://synthetic.invalid' } },
    { BKLOG_RUM: { enabled: true, endpoint: '' } },
    { __IS_MONITOR_COMPONENT__: true, BKLOG_RUM: { enabled: true, endpoint: 'https://synthetic.invalid' } },
  ]) await withWindow(state, async () => {
    const sdk = { get BkOpenTelemetry() { throw Error('SDK must stay unloaded'); } };
    assert.equal(await rumModule(sdk).initOpenTelemetry(), undefined);
  });
});

test('enabled RUM initializes once, retains privacy and request configuration, and retries failed imports', async () => {
  await withWindow({ BKLOG_RUM: { enabled: true, endpoint: 'https://synthetic.invalid', token: 'synthetic-only' },
    location: { href: 'https://app.invalid/#/retrieve/1', origin: 'https://app.invalid' } }, async () => {
    let loads = 0, constructions = 0, options;
    class FakeSdk { constructor(value) { constructions++; options = value; } }
    const sdk = { get BkOpenTelemetry() { loads++; if (loads === 1) throw Error('synthetic import failure'); return FakeSdk; } };
    const rum = rumModule(sdk);
    await assert.rejects(rum.initOpenTelemetry(), /synthetic import failure/);
    const [first, second] = await Promise.all([rum.initOpenTelemetry(), rum.initOpenTelemetry()]);
    assert.equal(first, second);
    assert.equal(await rum.initOpenTelemetry(), first);
    assert.equal(constructions, 1);
    assert.equal(loads, 2);
    assert.equal(options.transport.endpoint, 'https://synthetic.invalid');
    assert.equal(options.transport.token, 'synthetic-only');
    assert.equal(options.privacy.redactUrl('https://app.invalid/?token=synthetic'), 'https://app.invalid/?token=***');
    assert.equal(options.tracking.request.allowedTracingUrls[0]('https://app.invalid/api'), true);
    assert.equal(options.tracking.request.allowedTracingUrls[0]('https://other.invalid/api'), false);
    assert.equal(options.tracking.blankScreen.rootSelector, '#app');
  });
});

test('bootstrap waits for enabled instrumentation before APIs, while SDK failure does not strand the loading shell', async () => {
  const { readFileSync } = await import('node:fs');
  const source = readFileSync(new URL('../src/app/bootstrap/start.js', import.meta.url), 'utf8');
  const block = source.slice(source.indexOf('const startApplication ='), source.indexOf("if (process.env.NODE_ENV === 'development') {\n  ServicesInstance.meta.getEnvConstant()"));
  let ready;
  const pending = new Promise(resolve => { ready = resolve; }), events = [];
  const fixture = new Function('initOpenTelemetry', 'mountedVueInstance', 'console', 'let rumInstance;\n' + block + '\nreturn { start: startApplication, instance: () => rumInstance };');
  const app = fixture(() => pending, () => events.push(['api', app.instance()]), { warn() {} });
  const run = app.start();
  assert.deepEqual(events, []);
  const sdk = { synthetic: true };
  ready(sdk); await run;
  assert.deepEqual(events, [['api', sdk]]);
  let mounted = 0, warned = 0;
  const failure = fixture(async () => { throw Error('synthetic network failure'); }, () => mounted++, { warn: () => warned++ });
  await failure.start();
  assert.equal(mounted, 1); assert.equal(warned, 1);
});
