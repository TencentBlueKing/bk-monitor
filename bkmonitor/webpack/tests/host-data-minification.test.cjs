const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '..');

async function gcFixture() {
  const ts = require('typescript');
  const babel = require('@babel/core');
  const terser = require('terser');
  process.env.APP = 'pc';
  process.env.NODE_ENV = 'production';
  const config = ts.getParsedCommandLineOfConfigFile(path.join(root, 'tsconfig.json'), {}, {
    ...ts.sys,
    onUnRecoverableConfigFileDiagnostic(error) {
      throw new Error(ts.flattenDiagnosticMessageText(error.messageText, '\n'));
    },
  });
  const optimization = require('@blueking/bkmonitor-cli/dist/utils/webpack/load-optimize.js').default(true);
  const minifier = optimization.minimizer.find(plugin => plugin.constructor.name === 'TerserPlugin');
  assert.ok(minifier, 'Production Terser configuration is required');
  const filename = path.join(root, 'src/monitor-pc/pages/host/host.tsx');
  const input = fs.readFileSync(filename, 'utf8');
  const ast = ts.createSourceFile(filename, input, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const factory = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'createHostData');
  const host = ast.statements.find(node => ts.isClassDeclaration(node) && node.name?.text === 'Host');
  const getter = host?.members.find(node => ts.isGetAccessorDeclaration(node) && node.name?.getText(ast) === 'hostData');
  assert.ok(factory && getter);
  const sdkData = [];

  function makeHosts(Host) {
    const refs = [];
    for (let index = 0; index < 8; index++) {
      const host = new Host();
      const data = host.hostData;
      data.setUnmountCallback(() => {});
      host.unmountCallback = undefined;
      data.setUnmountCallback = undefined;
      sdkData.push(data);
      refs.push(new WeakRef(host));
    }
    return refs;
  }

  async function compile(getterText) {
    // The SDK retains data after unmount. Compile the actual closures with the production transforms.
    const fixture = `globalThis.Host = (() => {
      const aiWhaleStore = globalThis.ai;
      ${factory.getText(ast)}
      class Host {
        unmountCallback?: () => void;
        get hostHost() { return 'https://example.test'; }
        ${getterText}
      }
      return Host;
    })();`;
    const tsOutput = ts.transpileModule(fixture, {
      compilerOptions: { ...config.options, module: ts.ModuleKind.ES2022 },
      fileName: filename,
    }).outputText;
    const babelOutput = babel.transformSync(tsOutput, {
      configFile: path.join(root, 'babel.config.js'), babelrc: false, envName: 'production', filename,
    }).code;
    const minified = await terser.minify(babelOutput, { ...minifier.options.minimizer.options });
    const shortcuts = [];
    const ai = { enableAiAssistant: true, setCustomFallbackShortcut: value => shortcuts.push(value) };
    const context = vm.createContext({ ai });
    vm.runInContext(minified.code, context);
    const refs = makeHosts(context.Host);
    const data = sdkData.at(-1);
    assert.equal(data.host, 'https://example.test');
    assert.equal(data.enableAiAssistant, true);
    ai.enableAiAssistant = false;
    assert.equal(data.enableAiAssistant, false);
    data.handleAIBluekingShortcut('shortcut');
    assert.deepEqual(shortcuts, ['shortcut']);
    return refs;
  }

  const fixed = await compile(getter.getText(ast));
  const inlined = await compile(getter.getText(ast).replace(/\/\*\s*[@#]__NOINLINE__\s*\*\//g, ''));
  // WeakRef targets survive their creation job; exit that job before forcing collection.
  for (let round = 0; round < 10; round++) {
    await new Promise(setImmediate);
    global.gc();
  }
  const retained = refs => refs.filter(ref => ref.deref() !== undefined).length;
  assert.equal(retained(inlined), 8, 'The unprotected production transform must reproduce Host retention');
  assert.equal(retained(fixed), 0, 'Retained SDK data must not retain Host after production minification');
  assert.equal(sdkData.length, 16);
}

if (process.argv[2] === '--gc-fixture') {
  gcFixture().catch(error => { console.error(error); process.exitCode = 1; });
} else {
  test('production minification preserves Host closure isolation and AI callbacks', () => {
    const result = spawnSync(process.execPath, ['--expose-gc', __filename, '--gc-fixture'], {
      cwd: root, encoding: 'utf8', timeout: 30000,
    });
    assert.equal(result.status, 0, result.stderr || String(result.error));
  });
}
