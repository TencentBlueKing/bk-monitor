/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

test('compat class translator has the installed signature without resurrecting removed UI services', () => {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const fixture = `${root}tests/__class_translator_contract__.ts`;
  const source = `import { Component } from 'vue-tsx-support';
class Example extends Component<{ id: string }, { onSelect: string }, {}> {
  translate(): string { return this.$t('{n} entries', { n: 0 }, { locale: 'en' }); }
  prop(): string { return this.$props.id; }
  verify() {
    // @ts-expect-error Translation keys must be strings.
    this.$t(123);
    // @ts-expect-error Translation options retain their actual runtime contract.
    this.$t('key', {}, { locale: 123 });
    // @ts-expect-error Removed UI services are not installed on this component.
    this.$bkPopover(document.body, {});
    // @ts-expect-error Original required prop type is preserved.
    const invalid: number = this.$props.id;
  }
}`;
  const config = ts.readConfigFile(`${root}tsconfig.json`, ts.sys.readFile);
  const { options } = ts.parseJsonConfigFileContent(config.config, ts.sys, root);
  options.noEmit = true;
  const host = ts.createCompilerHost(options);
  const original = host.getSourceFile.bind(host);
  host.getSourceFile = (name, languageVersion, onError, shouldCreateNewSourceFile) =>
    name === fixture
      ? ts.createSourceFile(name, source, languageVersion, true)
      : original(name, languageVersion, onError, shouldCreateNewSourceFile);
  const program = ts.createProgram([fixture, `${root}src/platform/compat/class-component-jsx.d.ts`], options, host);
  const diagnostics = ts.getPreEmitDiagnostics(program);
  assert.equal(
    diagnostics.length,
    0,
    ts.formatDiagnosticsWithColorAndContext(diagnostics, {
      getCanonicalFileName: (name) => name,
      getCurrentDirectory: () => root,
      getNewLine: () => '\n',
    }),
  );
});
