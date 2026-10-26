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
  'v3-collection-left.png',
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
      check.id === 'favorite-bg-from-render' || check.id === 'collection-left-bg-from-render'
    ));
    assert.ok(colorChecks.length >= 2, 'color checks must come from rendered pages');
    for (const check of colorChecks) {
      assert.equal(check.ok, true, `${check.id} actual=${check.detail?.actual}`);
    }
  });

  it('does not claim v2 e2e passed without a v2 shot', () => {
    const report = JSON.parse(readFileSync(reportPath, 'utf8'));
    if (!existsSync(join(captureDir, 'v2-retrieve.png'))) {
      assert.equal(report.v2?.ok, false);
    }
  });
});
