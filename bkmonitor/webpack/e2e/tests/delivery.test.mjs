import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { captureReport } from '../scripts/capture-report.mjs';

const renderer = fileURLToPath(new URL('../scripts/render-delivery.mjs', import.meta.url));

function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'delivery-test-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const facts = {
    classification: 'PASS', runId: 'local-fixture', generatedAt: '2026-01-01T00:00:00Z',
    gate: { icon: '✅', label: '通过' },
    stats: { total: 1, passed: 1, skipped: 0, totalCriteria: 1, coveredCriteria: 1 },
    public: { scope: '图例布局', environment: 'Chromium', scenarios: [{ label: '布局断言', status: 'passed' }], checks: ['图例与列表边界不重叠'] },
    internal: { scope: '图例布局', environment: 'Chromium', entry: '事件详情页', artifacts: [], acceptanceResults: [
      { criterion: '无重叠', status: 'PASS', scenarios: [{ title: '布局断言', status: 'passed', actual: '边界分离' }] },
    ] },
  };
  const delivery = {
    public: {
      background: ['分组后图例遮挡列表'], changes: ['src/example.scss：给图例增加可换行弹性布局'],
      impact: ['局部样式'], behavior: { before: '图例遮挡列表', after: '图例撑开容器' }, reviewFocus: ['检查样式作用域'],
    },
    internal: {
      branch: 'fix/example', commit: 'abcdef', remoteBranch: 'origin/fix/example',
      prUrl: 'https://example.invalid/pull/1', head: 'origin:fix/example', base: 'origin:main',
      changes: ['调整局部布局'], impact: ['事件详情页'], attachments: [
        { kind: 'image', name: 'scene.png', url: 'https://example.invalid/bug/detail/1' },
        { kind: 'video', name: 'scene.webm', url: 'https://example.invalid/bug/detail/1' },
      ],
    },
  };
  function render(phase = 'all') {
    fs.writeFileSync(path.join(dir, 'facts.json'), JSON.stringify(facts));
    fs.writeFileSync(path.join(dir, 'delivery.json'), JSON.stringify(delivery));
    return spawnSync(process.execPath, [renderer, '--phase', phase, '--facts', path.join(dir, 'facts.json'),
      '--delivery', path.join(dir, 'delivery.json'), '--output', path.join(dir, 'output')], { encoding: 'utf8' });
  }
  function addReport(name = 'report-page-01.png') {
    facts.internal.artifacts.push({ role: 'report', mediaType: 'image', runPath: `report/${name}` });
    delivery.internal.attachments.push({ kind: 'image', role: 'report', name,
      url: `https://example.invalid/images/${name}`, imageUrl: `https://example.invalid/images/${name}` });
  }
  return { dir, facts, delivery, render, addReport,
    read: name => fs.readFileSync(path.join(dir, 'output', name), 'utf8') };
}

test('PR includes implementation, behavior change and verified checks', t => {
  const f = fixture(t);
  assert.equal(f.render('pr').status, 0);
  const body = f.read('pr-body.md');
  for (const value of [f.delivery.public.changes[0], f.delivery.public.behavior.before,
    f.delivery.public.behavior.after, f.delivery.public.reviewFocus[0], f.facts.public.checks[0]]) {
    assert.ok(body.includes(value));
  }
  f.delivery.public.behavior = { before: '', after: '' };
  assert.equal(f.render('pr').status, 0);
  f.delivery.public.changes = ['参考 https://internal.example/private'];
  assert.notEqual(f.render('pr').status, 0);
});

test('same detail URL preserves separate image and video attachments', t => {
  const f = fixture(t);
  assert.equal(f.render('tapd').status, 0);
  assert.ok(f.read('tapd-comment.md').includes('scene.png'));
  assert.ok(f.read('tapd-comment.md').includes('scene.webm'));
});

test('every report image needs an inline image address', t => {
  const f = fixture(t);
  f.addReport();
  f.addReport('report-page-02.png');
  assert.equal(f.render('tapd').status, 0);
  const body = f.read('tapd-comment.md');
  assert.equal((body.match(/<img /g) || []).length, 2);
  assert.ok(!body.includes('#### 验收覆盖'));
  delete f.delivery.internal.attachments.at(-1).imageUrl;
  assert.notEqual(f.render('tapd').status, 0);
});

test('report image cannot replace scenario image or use bug detail as image URL', t => {
  const f = fixture(t);
  f.addReport();
  f.delivery.internal.attachments.at(-1).imageUrl = 'https://example.invalid/bug/detail/1';
  assert.notEqual(f.render('tapd').status, 0);
  f.delivery.internal.attachments.at(-1).imageUrl = 'https://example.invalid/image.png';
  f.delivery.internal.attachments.shift();
  assert.notEqual(f.render('tapd').status, 0);
});

test('unexecuted report permits report screenshots without pretending a video exists', t => {
  const f = fixture(t);
  f.facts.classification = 'NOT_RUN';
  f.facts.stats = { total: 0, passed: 0, skipped: 0, coveredCriteria: 0, totalCriteria: 1 };
  f.facts.public.scenarios = [];
  f.facts.internal.acceptanceResults = [];
  f.delivery.internal.attachments = [];
  f.addReport();
  assert.equal(f.render().status, 0);
  assert.ok(f.read('tapd-comment.md').includes('本次未执行 E2E'));
  assert.ok(!f.read('tapd-comment.md').includes('scene.webm'));
});

test('capture expands details, paginates, preserves facts and replaces its own manifest entries', async t => {
  const f = fixture(t);
  const reportDir = path.join(f.dir, 'report');
  fs.mkdirSync(reportDir);
  fs.writeFileSync(path.join(reportDir, 'index.html'), '<!doctype html><meta charset="utf-8"><h1>验证报告</h1><details><summary>明细</summary><div style="height:3600px">断言与结果</div></details>');
  fs.writeFileSync(path.join(reportDir, 'delivery-facts.json'), JSON.stringify(f.facts));
  const artifacts = await captureReport(f.dir);
  assert.ok(artifacts.length >= 3);
  for (const item of artifacts) {
    const png = fs.readFileSync(path.join(f.dir, item.runPath));
    assert.equal(png.readUInt32BE(16), 1440);
    assert.ok(png.readUInt32BE(20) <= 1800);
  }
  await captureReport(f.dir);
  const updated = JSON.parse(fs.readFileSync(path.join(reportDir, 'delivery-facts.json')));
  assert.deepEqual(updated.stats, f.facts.stats);
  assert.equal(updated.classification, f.facts.classification);
  assert.equal(updated.internal.artifacts.length, artifacts.length);
});
