import assert from 'node:assert/strict';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const captureDir = join(root, '.ai-native/ui-align/captures');
const reportPath = join(captureDir, 'report.json');

const FULL_SHOTS = [
  'v3-retrieve.png',
  'v3-retrieve-highlight.png',
  'v3-retrieve-expand.png',
  'v3-collection.png',
  'v3-collection-wizard.png',
  'v3-manage-clean.png',
];
function assertPng(path, name, minSize) {
  assert.ok(existsSync(path), `missing screenshot ${name}`);
  const stat = statSync(path);
  assert.ok(stat.size > minSize, `${name} too small to be a capture: ${stat.size}`);
  const header = readFileSync(path).subarray(0, 8);
  assert.deepEqual([...header], [137, 80, 78, 71, 13, 10, 26, 10], `${name} is not PNG`);
}

const REGION_SHOTS = [
  'v3-retrieve-favorite.png',
  'v3-retrieve-searchbar.png',
  'v3-retrieve-result.png',
  'v3-retrieve-chips.png',
  'v3-retrieve-sql.png',
  'v3-retrieve-history.png',
  'v3-collection-left.png',
  'v3-manage-nav.png',
];

describe('UI screenshot compare (forbidden to pass without shots)', () => {
  it('refuses blind pass when captures are missing', () => {
    assert.ok(existsSync(reportPath), 'run npm run ui:align first; screenshot report is required');
    const report = JSON.parse(readFileSync(reportPath, 'utf8'));
    assert.ok(Array.isArray(report.shots) && report.shots.length > 0, 'report must list screenshot paths');
  });

  it('each required screenshot exists and is a real PNG', () => {
    for (const name of FULL_SHOTS) {
      assertPng(join(captureDir, name), name, 8_000);
    }
    for (const name of REGION_SHOTS) {
      assertPng(join(captureDir, name), name, 1_000);
    }
  });

  it('rendered colors from screenshots/report match v2 tokens', () => {
    const report = JSON.parse(readFileSync(reportPath, 'utf8'));
    const colorChecks = report.pages.flatMap(page => page.checks).filter(check => (
      check.id === 'favorite-bg-from-render'
      || check.id === 'collection-left-bg-from-render'
      || check.id === 'header-bg-from-render'
    ));
    assert.ok(colorChecks.length >= 3, 'color checks must come from rendered pages');
    for (const check of colorChecks) {
      assert.equal(check.ok, true, `${check.id} actual=${check.detail?.actual}`);
    }
  });

  it('requires real v2 retrieve/collection screenshots from local mock', () => {
    assertPng(join(captureDir, 'v2-retrieve.png'), 'v2-retrieve.png', 20_000);
    assertPng(join(captureDir, 'v2-collection.png'), 'v2-collection.png', 8_000);
    const report = JSON.parse(readFileSync(reportPath, 'utf8'));
    assert.equal(report.v2?.ok, true, `v2 compare must pass with mock shots: ${report.v2?.reason}`);
    const v2Page = report.pages.find(page => page.name === 'v2-retrieve');
    assert.ok(v2Page, 'report must include v2-retrieve page');
    assert.ok(v2Page.checks.every(check => check.ok), 'v2 retrieve chrome checks must pass');
  });

  it('records v2 vs v3 comparison instead of v3-only pass', () => {
    const report = JSON.parse(readFileSync(reportPath, 'utf8'));
    const compares = report.compare ?? report.pages.filter(page => String(page.name).startsWith('compare-'));
    assert.ok(compares.length > 0, 'v2/v3 comparison result is required');
    for (const item of compares) {
      assert.ok(item.checks.every(check => check.ok), `${item.name} comparison failed`);
    }
  });

  it('requires side-by-side v2/v3 effect screenshots', () => {
    assertPng(join(captureDir, 'compare-retrieve.png'), 'compare-retrieve.png', 20_000);
    assertPng(join(captureDir, 'compare-collection.png'), 'compare-collection.png', 20_000);
  });

  it('requires compiled CSS to keep v2 tokens and values', () => {
    const compiledPath = join(captureDir, 'compiled-css.json');
    assert.ok(existsSync(compiledPath), 'run npm run build && npm run ui:compiled first');
    const compiled = JSON.parse(readFileSync(compiledPath, 'utf8'));
    assert.equal(compiled.ok, true, JSON.stringify(compiled.checks));
  });
});
