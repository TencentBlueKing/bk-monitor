#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

function help() {
  console.log(`Usage:
  pnpm e2e:delivery -- --phase <pr|tapd|all> --facts <delivery-facts.json> --delivery <delivery.json> --output <dir>

The pr phase creates pr-body.md. The tapd phase requires verified PR facts and creates tapd-comment.md.`);
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--') {
      continue;
    }
    if (token === '--help' || token === '-h') {
      args.help = true;
      continue;
    }
    if (!token.startsWith('--')) {
      throw new Error(`Unexpected argument: ${token}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) {
      throw new Error(`Missing value for ${token}`);
    }
    args[token.slice(2)] = value;
    index += 1;
  }
  return args;
}

function sanitizeInternal(value) {
  return String(value || '')
    .replace(/\/(?:Users|private\/tmp|tmp)\/\S+/g, '[已脱敏本地路径]')
    .replace(
      /\b(?:cookie|authorization|x-csrftoken|csrf[_-]?token|access[_-]?token|refresh[_-]?token|token|storageState|password|passwd|secret|api[_-]?key)\b\s*[:=]\s*\S+/gi,
      '[已脱敏凭据]'
    )
    .replace(/[\r\n]+/g, ' ')
    .trim();
}

function sanitizePublic(value) {
  return sanitizeInternal(value).replace(/https?:\/\/\S+/gi, '[已脱敏地址]');
}

function requireText(value, label, sanitizer = sanitizeInternal) {
  const text = sanitizer(value);
  if (!text) {
    throw new Error(`${label} is required.`);
  }
  return text;
}

function requirePublicText(value, label) {
  const raw = String(value || '').trim();
  const text = requireText(raw, label, sanitizePublic);
  if (text.includes('[已脱敏')) {
    throw new Error(`${label} contains a URL, local path or credential-like value. Provide a public semantic alias.`);
  }
  return text;
}

function requireTextList(value, label, sanitizer = sanitizeInternal) {
  if (!Array.isArray(value) || value.length === 0) {
    throw new Error(`${label} must be a non-empty array.`);
  }
  return value.map((item, index) => requireText(item, `${label}[${index}]`, sanitizer));
}

function requirePublicList(value, label) {
  if (!Array.isArray(value) || value.length === 0) {
    throw new Error(`${label} must be a non-empty array.`);
  }
  return value.map((item, index) => requirePublicText(item, `${label}[${index}]`));
}

function optionalPublicList(value, label) {
  if (value === undefined) {
    return [];
  }
  if (!Array.isArray(value)) {
    throw new Error(`${label} must be an array.`);
  }
  return value.map((item, index) => requirePublicText(item, `${label}[${index}]`));
}

function requireAttachmentUrl(value, label) {
  const raw = String(value || '').trim();
  const text = requireText(raw, label);
  let parsed;
  try {
    parsed = new URL(text);
  } catch {
    throw new Error(`${label} must be a verified http(s) attachment URL.`);
  }
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password || ['localhost', '127.0.0.1'].includes(parsed.hostname)) {
    throw new Error(`${label} must be a verified remote attachment URL.`);
  }
  const sensitiveParams = ['token', 'signature', 'credential', 'authorization'];
  if ([...parsed.searchParams.keys()].some(key => sensitiveParams.some(name => key.toLowerCase().includes(name)))) {
    throw new Error(`${label} must not contain an upload capability or credential.`);
  }
  return text;
}

function requireImageUrl(value, label) {
  const url = requireAttachmentUrl(value, label);
  if (/\/(?:bug|story|task)\/detail\//.test(new URL(url).pathname)) {
    throw new Error(`${label} must point to an image, not a work item detail page.`);
  }
  return url;
}

function escapeHtml(value) {
  return String(value).replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

function requireTapdAttachments(value, totalScenarios) {
  if (totalScenarios === 0 && !value?.length) {
    return [];
  }
  if (!Array.isArray(value) || value.length === 0) {
    throw new Error('delivery.internal.attachments must contain verified TAPD image and video attachments.');
  }
  const attachments = value.map((item, index) => {
    const kind = item?.kind;
    if (!['image', 'video'].includes(kind)) {
      throw new Error(`delivery.internal.attachments[${index}].kind must be image or video.`);
    }
    const role = item?.role || 'scenario';
    if (!['report', 'scenario'].includes(role) || (role === 'report' && (kind !== 'image' || !item.imageUrl))) {
      throw new Error(`delivery.internal.attachments[${index}] requires a valid role and inline URL for report images.`);
    }
    return {
      kind,
      role,
      name: requireText(item?.name, `delivery.internal.attachments[${index}].name`),
      url: requireAttachmentUrl(item?.url, `delivery.internal.attachments[${index}].url`),
      imageUrl: item?.imageUrl
        ? requireImageUrl(item.imageUrl, `delivery.internal.attachments[${index}].imageUrl`)
        : '',
    };
  });
  for (const kind of totalScenarios > 0 ? ['image', 'video'] : []) {
    if (!attachments.some(item => item.kind === kind && item.role !== 'report')) {
      throw new Error(`delivery.internal.attachments requires at least one verified ${kind} attachment.`);
    }
  }
  return attachments.filter(
    (item, index, items) =>
      items.findIndex(
        candidate => candidate.kind === item.kind && candidate.name === item.name && candidate.url === item.url
      ) === index
  );
}

function bulletLines(items) {
  return items.map(item => `- ${item}`);
}

const resultStatus = {
  passed: { icon: '✅', label: '通过' },
  failed: { icon: '❌', label: '失败' },
  timedOut: { icon: '❌', label: '超时' },
  interrupted: { icon: '⛔', label: '中断' },
  skipped: { icon: '⚠️', label: '未执行' },
  unknown: { icon: '❓', label: '待判断' },
  PASS: { icon: '✅', label: '通过' },
  FAILED: { icon: '❌', label: '失败' },
  SKIPPED: { icon: '⚠️', label: '未执行' },
  NOT_COVERED: { icon: '⚠️', label: '未覆盖' },
  UNCLASSIFIED: { icon: '❓', label: '待判断' },
};

const classificationLabel = {
  PASS: '通过',
  FAIL_PRODUCT: '产品失败',
  BLOCKED_ENV: '环境阻塞',
  INVALID_TEST: '测试无效',
  NOT_RUN: '未执行',
  UNCLASSIFIED: '待判断',
};

const deliveryHeadline = {
  PASS: '✅ 已完成，E2E 未发现交付阻断',
  FAIL_PRODUCT: '❌ 暂不交付，E2E 发现产品失败',
  BLOCKED_ENV: '⛔ 暂不交付，E2E 被环境阻塞',
  INVALID_TEST: '⚠️ 暂不交付，E2E 测试无效',
  NOT_RUN: '⚪ 待确认，本次未执行 E2E',
  UNCLASSIFIED: '❓ 待判断，E2E 尚未完成分类',
};

function statusOf(value) {
  return resultStatus[value] || resultStatus.unknown;
}

function renderPrBody(facts, delivery) {
  const publicDelivery = delivery.public || {};
  const publicFacts = facts.public || {};
  const stats = facts.stats || {};
  const background = requirePublicList(publicDelivery.background, 'delivery.public.background');
  const changes = requirePublicList(publicDelivery.changes, 'delivery.public.changes');
  const impact = requirePublicList(publicDelivery.impact, 'delivery.public.impact');
  const scope = requirePublicText(publicFacts.scope, 'facts.public.scope');
  const environment = requirePublicText(publicFacts.environment, 'facts.public.environment');
  const scenarios = Array.isArray(publicFacts.scenarios)
    ? publicFacts.scenarios.map((item, index) => ({
        label: requirePublicText(item?.label, `facts.public.scenarios[${index}].label`),
        status: item?.status || 'unknown',
      }))
    : [];
  if (scenarios.length === 0 && stats.total > 0) {
    throw new Error('facts.public.scenarios must contain at least one scenario.');
  }
  const risks = optionalPublicList(publicFacts.risks, 'facts.public.risks');
  const uncovered = optionalPublicList(publicFacts.uncovered, 'facts.public.uncovered');
  const gate = facts.gate || {};
  const gateIcon = requireText(gate.icon, 'facts.gate.icon');
  const gateLabel = requireText(gate.label, 'facts.gate.label');
  const lines = [
    '## 背景',
    '',
    ...bulletLines(background),
    '',
    '## 改动',
    '',
    ...bulletLines(changes),
    ...(publicDelivery.behavior?.before || publicDelivery.behavior?.after ? [
      '', '### 行为变化', '',
      `- 修改前：${requirePublicText(publicDelivery.behavior.before, 'delivery.public.behavior.before')}`,
      `- 修改后：${requirePublicText(publicDelivery.behavior.after, 'delivery.public.behavior.after')}`,
    ] : []),
    ...(publicDelivery.reviewFocus?.length ? [
      '', '### 审查重点', '',
      ...bulletLines(requirePublicList(publicDelivery.reviewFocus, 'delivery.public.reviewFocus')),
    ] : []),
    '',
    '## 影响面',
    '',
    ...bulletLines(impact),
    '',
    '## 测试',
    '',
    `### E2E：${gateIcon} ${gateLabel}`,
    '',
    `- 测试范围：${scope}`,
    `- 验收覆盖：${stats.coveredCriteria}/${stats.totalCriteria}`,
    `- 自动化场景：${stats.passed}/${stats.total} 通过`,
    `- 测试环境：${environment}`,
    ...bulletLines(optionalPublicList(publicFacts.checks, 'facts.public.checks')),
    ...scenarios.map(item => {
      const status = statusOf(item.status);
      return `- [${item.status === 'passed' ? 'x' : ' '}] ${item.label} — ${status.icon} ${status.label}`;
    }),
  ];

  if (Array.isArray(facts.internal?.repairHistory) && facts.internal.repairHistory.length > 0) {
    lines.push(`- 修复闭环：${requirePublicText(publicFacts.repair, 'facts.public.repair')}`);
  }
  if (facts.internal?.visual?.checked) {
    lines.push(`- 视觉还原：${requirePublicText(publicFacts.visual, 'facts.public.visual')}`);
  }
  if (uncovered.length || risks.length) {
    lines.push('', '### 未覆盖与残余风险', '');
    lines.push(...uncovered.map(item => `- 未覆盖：${item}`));
    lines.push(...risks.map(item => `- 残余风险：${item}`));
  }
  lines.push(
    '',
    '### 证据与追溯',
    '',
    '- 一次性测试脚本与测试证据仅保存在本地，不提交仓库。',
    ''
  );
  return lines.join('\n');
}

function collectAcceptanceScenarios(results) {
  const scenarios = [];
  for (const item of results || []) {
    for (const scenario of item?.scenarios || []) {
      const title = sanitizeInternal(scenario?.title) || '未命名场景';
      if (!scenarios.some(candidate => candidate.title === title)) {
        scenarios.push({ ...scenario, title });
      }
    }
  }
  return scenarios;
}

function renderScenarioResults(results) {
  const scenarios = collectAcceptanceScenarios(results);
  if (scenarios.length === 0) {
    return ['- ⚠️ 未映射自动化场景'];
  }
  return scenarios.map(scenario => {
    const status = statusOf(scenario?.status);
    const actual = sanitizeInternal(scenario?.actual) || '未填写实际结果';
    if (scenario?.status === 'passed') {
      return `- ${status.icon} ${scenario.title}：${actual}`;
    }
    const expected = sanitizeInternal(scenario?.expected) || '未填写预期结果';
    return `- ${status.icon} ${scenario.title}：预期 ${expected}；实际 ${actual}`;
  });
}

function renderAcceptanceCoverage(results) {
  if (!Array.isArray(results) || results.length === 0) {
    return ['- ⚠️ 未填写验收项，无法确认覆盖情况'];
  }
  return results.map((item, index) => {
    const status = statusOf(item?.status);
    return `${index + 1}. ${status.icon} ${sanitizeInternal(item?.criterion) || '未命名验收项'} — ${status.label}`;
  });
}

function renderTapdComment(facts, delivery) {
  const internalDelivery = delivery.internal || {};
  const internalFacts = facts.internal || {};
  const stats = facts.stats || {};
  const branch = requireText(internalDelivery.branch, 'delivery.internal.branch');
  const commit = requireText(internalDelivery.commit, 'delivery.internal.commit');
  const remoteBranch = requireText(internalDelivery.remoteBranch, 'delivery.internal.remoteBranch');
  const prUrl = requireText(internalDelivery.prUrl, 'delivery.internal.prUrl');
  const head = requireText(internalDelivery.head, 'delivery.internal.head');
  const base = requireText(internalDelivery.base, 'delivery.internal.base');
  const changes = requireTextList(internalDelivery.changes, 'delivery.internal.changes');
  const impact = requireTextList(internalDelivery.impact, 'delivery.internal.impact');
  const attachments = requireTapdAttachments(internalDelivery.attachments, (stats.total || 0) - (stats.skipped || 0));
  const reportArtifacts = (internalFacts.artifacts || []).filter(item => item.role === 'report');
  for (const artifact of reportArtifacts) {
    if (!attachments.some(item => item.role === 'report' && item.kind === 'image' && item.name === path.basename(artifact.runPath) && item.imageUrl)) {
      throw new Error(`Report image ${artifact.runPath} requires a verified inline imageUrl in TAPD attachments.`);
    }
  }
  const scope = requireText(internalFacts.scope, 'facts.internal.scope');
  const environment = requireText(internalFacts.environment, 'facts.internal.environment');
  const entry = requireText(internalFacts.entry, 'facts.internal.entry');
  const headline = deliveryHeadline[facts.classification] || deliveryHeadline.UNCLASSIFIED;
  const lines = [
    `## 交付结论：${headline}`,
    '',
    `验收项 ${stats.coveredCriteria}/${stats.totalCriteria}，自动化场景 ${stats.passed}/${stats.total} 通过。`,
    '',
    '### 交付信息',
    '',
    `- 分支：${branch}`,
    `- Commit：${commit}`,
    `- 远端分支：${remoteBranch}`,
    `- PR/MR：${prUrl}`,
    `- 合并方向：${head} → ${base}`,
    `- 测试页面：${entry}`,
    '',
    '### 本次改动',
    '',
    ...bulletLines(changes),
    '',
    '### 影响面',
    '',
    ...bulletLines(impact),
    '',
    '### 测试结果',
    '',
    `- 环境：${environment}`,
    `- 页面前检：${sanitizeInternal(internalFacts.preflightStatus) || '未执行'}`,
    '',
    ...renderScenarioResults(internalFacts.acceptanceResults),
    '',
  ];

  if (!attachments.some(item => item.role === 'report')) {
    lines.push('#### 验收覆盖', '', ...renderAcceptanceCoverage(internalFacts.acceptanceResults), '');
  }

  if (attachments.length > 0) {
    lines.push(
      '### 测试附件',
      '',
      ...attachments.map(item => `- ${item.kind === 'image' ? '🖼️' : '🎬'} [${item.name}](${item.url})`),
      ''
    );
    const reportImages = attachments.filter(item => item.role === 'report' && item.imageUrl);
    if (reportImages.length) {
      lines.push('### 完整报告截图', '', ...reportImages.flatMap(item => [
        `<p><img src="${escapeHtml(item.imageUrl)}" alt="${escapeHtml(item.name)}" /></p>`, '',
      ]));
    }
  }

  if (Array.isArray(internalFacts.repairHistory) && internalFacts.repairHistory.length > 0) {
    lines.push(
      '### 修复闭环',
      '',
      ...internalFacts.repairHistory.map(item =>
        `- 第 ${item.round} 轮：${sanitizeInternal(item.failureSummary)} → ${sanitizeInternal(item.repairSummary)} → 复测${
          classificationLabel[item.retestResult] || sanitizeInternal(item.retestResult)
        }`
      ),
      ''
    );
  }
  if (internalFacts.visual?.checked) {
    lines.push('### 视觉还原', '', `- 总结：${sanitizeInternal(internalFacts.visual.summary) || '未填写'}`);
    if (internalFacts.visual.diffRatioText && internalFacts.visual.diffRatioText !== '—') {
      lines.push(`- 像素差异率：${sanitizeInternal(internalFacts.visual.diffRatioText)}`);
    }
    for (const region of reportArtifacts.length ? [] : internalFacts.visual.regions || []) {
      const status = statusOf(region.status);
      lines.push(`- ${status.icon} ${sanitizeInternal(region.name)}：${sanitizeInternal(region.summary) || status.label}`);
    }
    lines.push('');
  }
  const risks = Array.isArray(internalFacts.risks) ? internalFacts.risks : [];
  const uncovered = Array.isArray(internalFacts.uncovered) ? internalFacts.uncovered : [];
  if (risks.length || uncovered.length) {
    lines.push('### 未覆盖与残余风险', '');
    lines.push(
      ...uncovered.map(item =>
        `- [未覆盖] ${sanitizeInternal(item.item)}${item.detail ? `：${sanitizeInternal(item.detail)}` : ''}`
      )
    );
    lines.push(
      ...risks.map(item =>
        `- [残余风险/${sanitizeInternal(item.levelLabel)}] ${sanitizeInternal(item.item)}${
          item.detail ? `：${sanitizeInternal(item.detail)}` : ''
        }`
      )
    );
    lines.push('');
  }
  lines.push(
    '### 测试追溯',
    '',
    `- 测试范围：${scope}`,
    `- 执行时间：${sanitizeInternal(facts.generatedAt)}`,
    `- Run ID：${sanitizeInternal(facts.runId)}`,
    attachments.length > 0
      ? `- 附件：已上传 ${attachments.filter(item => item.kind === 'image').length} 张图片、${
          attachments.filter(item => item.kind === 'video').length
        } 个视频；完整 HTML 报告与 trace 仍保留在本地。`
      : '- 附件：业务场景未执行，无可上传的测试图片或视频。',
    ''
  );
  return lines.join('\n');
}

const args = parseArgs(process.argv.slice(2));
if (args.help) {
  help();
  process.exit(0);
}
for (const name of ['facts', 'delivery', 'output']) {
  if (!args[name]) {
    throw new Error(`--${name} is required.`);
  }
}
const phase = args.phase || 'all';
if (!['pr', 'tapd', 'all'].includes(phase)) {
  throw new Error('--phase must be pr, tapd or all.');
}

const facts = JSON.parse(fs.readFileSync(path.resolve(args.facts), 'utf8'));
const delivery = JSON.parse(fs.readFileSync(path.resolve(args.delivery), 'utf8'));
const outputDir = path.resolve(args.output);
fs.mkdirSync(outputDir, { recursive: true });
const output = {};

if (phase === 'pr' || phase === 'all') {
  output.prBodyPath = path.join(outputDir, 'pr-body.md');
  fs.writeFileSync(output.prBodyPath, renderPrBody(facts, delivery), 'utf8');
}
if (phase === 'tapd' || phase === 'all') {
  output.tapdCommentPath = path.join(outputDir, 'tapd-comment.md');
  fs.writeFileSync(output.tapdCommentPath, renderTapdComment(facts, delivery), 'utf8');
}

console.log(JSON.stringify({ phase, ...output }, null, 2));
