#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

import { renderHtmlReport } from './render-html-report.mjs';

function collectSpecs(suites, parentTitles = []) {
  const collected = [];
  for (const suite of suites || []) {
    const titles = suite.title ? [...parentTitles, suite.title] : parentTitles;
    for (const spec of suite.specs || []) {
      for (const test of spec.tests || []) {
        const results = test.results || [];
        const last = results.at(-1);
        let status = last?.status || (spec.ok ? 'passed' : 'unknown');
        if (test.expectedStatus === 'skipped' || status === 'skipped') {
          status = 'skipped';
        }
        const projectSuffix = test.projectName ? ` [${test.projectName}]` : '';
        collected.push({
          rawTitle: spec.title,
          title: `${[...titles, spec.title].filter(Boolean).join(' › ')}${projectSuffix}`,
          status,
          attempts: results.length,
          duration: last?.duration || 0,
          error: (last?.errors || []).map(error => error.message || error.value || String(error)).join('\n'),
          attachments: last?.attachments || [],
        });
      }
    }
    collected.push(...collectSpecs(suite.suites, titles));
  }
  return collected;
}

function formatDuration(milliseconds) {
  if (!Number.isFinite(milliseconds) || milliseconds <= 0) {
    return '0 ms';
  }
  if (milliseconds < 1000) {
    return `${Math.round(milliseconds)} ms`;
  }
  return `${(milliseconds / 1000).toFixed(milliseconds < 10_000 ? 1 : 0)} s`;
}

function formatEnvironment(environment = {}) {
  return [environment.app, environment.mode, environment.browser, environment.viewport]
    .map(sanitizeInternal)
    .filter(Boolean)
    .join(' / ');
}

function formatRepairHistory(history) {
  if (history === undefined) {
    return [];
  }
  if (!Array.isArray(history)) {
    throw new Error('repairHistory must be an array.');
  }
  return history.map((item, index) => {
    if (!item || typeof item !== 'object') {
      throw new Error(`repairHistory[${index}] must be an object.`);
    }
    if (item.authorized !== true) {
      throw new Error(`repairHistory[${index}] requires authorized=true.`);
    }
    const round = Number.isInteger(item.round) && item.round > 0 ? item.round : index + 1;
    const failureClassification = sanitizeInternal(item.failureClassification);
    const failureSummary = sanitizeInternal(item.failureSummary);
    const repairSummary = sanitizeInternal(item.repairSummary);
    const retestResult = sanitizeInternal(item.retestResult);
    if (!failureClassification || !failureSummary || !repairSummary || !retestResult) {
      throw new Error(`repairHistory[${index}] is incomplete.`);
    }
    return { round, failureClassification, failureSummary, repairSummary, retestResult };
  });
}

function help() {
  console.log(`Usage:
  pnpm e2e:report -- [--results <results.json>] --scope <scope.json> --output <dir>

Creates a visual index.html, a detailed report.md, delivery-facts.json and review fragments.
--results may be omitted only for BLOCKED_ENV or NOT_RUN reports.`);
}

function localEvidenceLink(filePath, label, runDir, outputDir) {
  if (!filePath) {
    return null;
  }
  const absolutePath = path.isAbsolute(filePath) ? path.resolve(filePath) : path.resolve(runDir, filePath);
  const relativeToRun = path.relative(runDir, absolutePath);
  if (relativeToRun.startsWith('..') || path.isAbsolute(relativeToRun) || !fs.existsSync(absolutePath)) {
    return null;
  }
  const href = path.relative(outputDir, absolutePath).split(path.sep).map(encodeURIComponent).join('/');
  return {
    label: sanitizeInternal(label || path.basename(filePath)),
    href,
    runPath: relativeToRun.split(path.sep).join('/'),
    mediaType: mediaTypeForPath(absolutePath),
  };
}

function mediaTypeForPath(filePath) {
  const extension = path.extname(filePath).toLowerCase();
  if (['.png', '.jpg', '.jpeg', '.webp', '.gif'].includes(extension)) {
    return 'image';
  }
  if (['.webm', '.mp4', '.mov'].includes(extension)) {
    return 'video';
  }
  if (extension === '.zip') {
    return 'trace';
  }
  return 'other';
}

function normalizeRiskItems(value, defaultLevel = 'medium') {
  if (!Array.isArray(value)) {
    return [];
  }
  const levelLabels = { high: '高', medium: '中', low: '低' };
  return value
    .map(item => {
      if (typeof item === 'string') {
        return { item: sanitizeInternal(item), detail: '', level: defaultLevel, levelLabel: levelLabels[defaultLevel] };
      }
      const level = ['high', 'medium', 'low'].includes(item?.level) ? item.level : defaultLevel;
      return {
        item: sanitizeInternal(item?.item || item?.title),
        detail: sanitizeInternal(item?.detail || item?.reason || item?.mitigation),
        level,
        levelLabel: levelLabels[level],
      };
    })
    .filter(item => item.item);
}

function normalizeScenarioDetails(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map(item => ({
      testTitle: sanitizeInternal(item?.testTitle || item?.title),
      acceptanceCriteria: normalizeTextList(item?.acceptanceCriteria),
      preconditions: normalizeTextList(item?.preconditions),
      steps: normalizeSteps(item?.steps),
      expected: sanitizeInternal(item?.expected),
      actual: sanitizeInternal(item?.actual),
      evidence: Array.isArray(item?.evidence) ? item.evidence : [],
    }))
    .filter(item => item.testTitle);
}

function normalizeSteps(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map(step => {
      if (typeof step === 'string') {
        return { action: sanitizeInternal(step), expected: '', actual: '' };
      }
      return {
        action: sanitizeInternal(step?.action),
        expected: sanitizeInternal(step?.expected),
        actual: sanitizeInternal(step?.actual),
      };
    })
    .filter(step => step.action);
}

function normalizeTextList(value) {
  return Array.isArray(value) ? value.map(sanitizeInternal).filter(Boolean) : [];
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

const args = parseArgs(process.argv.slice(2));
if (args.help) {
  help();
  process.exit(0);
}
for (const name of ['scope', 'output']) {
  if (!args[name]) {
    throw new Error(`--${name} is required.`);
  }
}

const resultsPath = args.results ? path.resolve(args.results) : '';
const scopePath = path.resolve(args.scope);
const scope = JSON.parse(fs.readFileSync(scopePath, 'utf8'));
const classification = sanitizeInternal(scope.classification || 'UNCLASSIFIED');
if (!resultsPath && !['BLOCKED_ENV', 'NOT_RUN'].includes(classification)) {
  throw new Error('--results may be omitted only when classification is BLOCKED_ENV or NOT_RUN.');
}
const results = resultsPath ? JSON.parse(fs.readFileSync(resultsPath, 'utf8')) : { suites: [] };
const outputDir = path.resolve(args.output);
const runDir = resultsPath ? path.dirname(resultsPath) : path.dirname(scopePath);
const specs = collectSpecs(results.suites);
const passed = specs.filter(item => item.status === 'passed').length;
const failed = specs.filter(item => ['failed', 'timedOut', 'interrupted', 'unknown'].includes(item.status)).length;
const skipped = specs.filter(item => item.status === 'skipped').length;
const total = specs.length;
const testPhase = sanitizeInternal(scope.testPhase || 'reconnaissance');
const repairHistory = formatRepairHistory(scope.repairHistory);
const visual = scope.visual || {};
const visualMode = sanitizeInternal(visual.mode || (visual.checked ? 'design-diff' : 'not-applicable'));
const allowedClassifications = new Set([
  'PASS',
  'FAIL_PRODUCT',
  'BLOCKED_ENV',
  'INVALID_TEST',
  'NOT_RUN',
  'UNCLASSIFIED',
]);
const allowedTestPhases = new Set(['reconnaissance', 'acceptance']);
const allowedVisualModes = new Set(['not-applicable', 'design-diff', 'layout-regression']);
if (!allowedClassifications.has(classification)) {
  throw new Error(`Unsupported scope classification: ${classification}`);
}
if (!allowedTestPhases.has(testPhase)) {
  throw new Error(`Unsupported scope testPhase: ${testPhase}`);
}
if (!allowedVisualModes.has(visualMode)) {
  throw new Error(`Unsupported visual mode: ${visualMode}`);
}
for (const [index, item] of repairHistory.entries()) {
  if (item.failureClassification !== 'FAIL_PRODUCT') {
    throw new Error(`repairHistory[${index}] failureClassification must be FAIL_PRODUCT.`);
  }
  if (!allowedClassifications.has(item.retestResult)) {
    throw new Error(`repairHistory[${index}] has an unsupported retestResult.`);
  }
}
if (classification === 'PASS' && (total === 0 || failed > 0 || skipped > 0 || passed !== total)) {
  throw new Error('PASS requires at least one executed scenario and no failed or skipped scenarios.');
}
if (classification === 'PASS' && testPhase !== 'acceptance') {
  throw new Error('PASS requires scope.testPhase="acceptance"; reconnaissance runs cannot be released.');
}
if (
  classification === 'PASS' &&
  scope.visual?.checked &&
  scope.visual.classification &&
  scope.visual.classification !== 'PASS'
) {
  throw new Error('PASS conflicts with the visual classification.');
}
if (repairHistory.length > 0 && repairHistory.at(-1).retestResult !== classification) {
  throw new Error('The last repairHistory retestResult must match the final classification.');
}

const environment = formatEnvironment(scope.environment);
const scopeText =
  (scope.scopeBasis || []).map(sanitizeInternal).filter(Boolean).join('；') || sanitizeInternal(scope.changedArea);
const visualText = visual.checked
  ? `${visualMode}；${sanitizeInternal(visual.classification)}；${sanitizeInternal(visual.summary)}${
      typeof visual.diffRatio === 'number' ? `；diffRatio=${visual.diffRatio.toFixed(4)}` : ''
    }${visual.masks?.length ? `；mask=${visual.masks.map(sanitizeInternal).join('、')}` : ''}`
  : '不适用或未执行';
const publicSummary = scope.publicSummary && typeof scope.publicSummary === 'object' ? scope.publicSummary : {};
const publicScenarioLabels = Array.isArray(publicSummary.scenarios) ? publicSummary.scenarios : [];
const publicRisks = Array.isArray(publicSummary.risks) ? publicSummary.risks.map(sanitizePublic).filter(Boolean) : [];
const publicUncovered = Array.isArray(publicSummary.uncovered)
  ? publicSummary.uncovered.map(sanitizePublic).filter(Boolean)
  : [];
const caseLines = specs.length
  ? specs.map(
      (item, index) =>
        `- [${item.status === 'passed' ? 'x' : ' '}] ${sanitizePublic(publicScenarioLabels[index] || item.title)} — ${
          item.status
        }`
    )
  : ['- [ ] 没有可汇总的 E2E 场景'];
const repairLines = repairHistory.length
  ? repairHistory.map(
      item =>
        `- 第 ${item.round} 轮：${item.failureClassification}（${item.failureSummary}）→ ${item.repairSummary} → 复测 ${item.retestResult}`
    )
  : ['- 未触发产品修复'];
const repairSummaryText = repairHistory.length
  ? repairHistory
      .map(
        item =>
          `第 ${item.round} 轮 ${item.failureClassification}（${item.failureSummary}）→ ${item.repairSummary} → ${item.retestResult}`
      )
      .join('；')
  : '未触发';

const scenarioDetails = normalizeScenarioDetails(scope.scenarioDetails);
const scenarios = specs.map(spec => {
  const detail = scenarioDetails.find(
    item => spec.rawTitle.includes(item.testTitle) || spec.title.includes(item.testTitle)
  );
  const attachmentEvidence = spec.attachments
    .map(item => localEvidenceLink(item.path, item.name || item.contentType, runDir, outputDir))
    .filter(Boolean);
  const declaredEvidence = (detail?.evidence || [])
    .map(item =>
      typeof item === 'string'
        ? localEvidenceLink(item, path.basename(item), runDir, outputDir)
        : localEvidenceLink(item?.path, item?.label, runDir, outputDir)
    )
    .filter(Boolean);
  return {
    title: sanitizeInternal(spec.rawTitle || spec.title),
    status: spec.status,
    attempts: spec.attempts,
    duration: spec.duration,
    durationText: formatDuration(spec.duration),
    error: sanitizeInternal(spec.error).slice(0, 3000),
    acceptanceCriteria: detail?.acceptanceCriteria || [],
    preconditions: detail?.preconditions || [],
    steps: detail?.steps || [],
    expected: detail?.expected || '',
    actual: detail?.actual || '',
    evidence: [...declaredEvidence, ...attachmentEvidence],
    hasDetail: Boolean(detail),
  };
});
for (const scenario of scenarios.filter(item => item.status !== 'skipped')) {
  for (const mediaType of ['image', 'video']) {
    if (!scenario.evidence.some(item => item.mediaType === mediaType)) {
      throw new Error(`Executed scenario "${scenario.title}" requires local ${mediaType} evidence.`);
    }
  }
}
const uploadArtifacts = scenarios
  .flatMap(scenario =>
    scenario.evidence
      .filter(item => ['image', 'video'].includes(item.mediaType))
      .map(item => ({
        scenario: scenario.title,
        label: item.label,
        mediaType: item.mediaType,
        runPath: item.runPath,
      }))
  )
  .filter(
    (item, index, items) => items.findIndex(candidate => candidate.runPath === item.runPath) === index
  );
const acceptanceCriteria = normalizeTextList(scope.acceptanceCriteria);
const coverage = acceptanceCriteria.map((criterion, index) => {
  const linkedScenarios = scenarios.filter(item => item.acceptanceCriteria.includes(criterion));
  let status = 'NOT_COVERED';
  if (linkedScenarios.length > 0) {
    if (linkedScenarios.every(item => item.status === 'passed')) {
      status = 'PASS';
    } else if (linkedScenarios.some(item => ['failed', 'timedOut', 'interrupted'].includes(item.status))) {
      status = 'FAILED';
    } else if (linkedScenarios.every(item => item.status === 'skipped')) {
      status = 'SKIPPED';
    } else {
      status = 'UNCLASSIFIED';
    }
  }
  return {
    index: index + 1,
    criterion,
    status,
    scenarios: linkedScenarios.map(item => item.title),
  };
});
const coveredCriteria = coverage.filter(item => item.status !== 'NOT_COVERED').length;
const coveragePercent = coverage.length ? Math.round((coveredCriteria / coverage.length) * 100) : null;
const coverageText = coveragePercent === null ? '未填写' : `${coveragePercent}%`;
const totalDuration = specs.reduce((sum, item) => sum + item.duration, 0);
const risks = normalizeRiskItems(scope.risks, 'medium');
const uncovered = normalizeRiskItems(scope.uncovered, 'medium');
const visualRegions = Array.isArray(visual.regions)
  ? visual.regions
      .map(item => ({
        name: sanitizeInternal(item?.name),
        status: sanitizeInternal(item?.status || 'UNCLASSIFIED'),
        summary: sanitizeInternal(item?.summary),
      }))
      .filter(item => item.name)
  : [];
const rawVisualEvidence = Array.isArray(visual.evidence)
  ? visual.evidence
  : Object.entries(visual.evidence || {}).map(([label, filePath]) => ({ label, path: filePath }));
const visualEvidence = rawVisualEvidence
  .map(item =>
    typeof item === 'string'
      ? localEvidenceLink(item, path.basename(item), runDir, outputDir)
      : localEvidenceLink(item?.path, item?.label, runDir, outputDir)
  )
  .filter(Boolean);
const preflightPath = path.join(runDir, 'preflight.json');
let preflightStatus = '';
if (fs.existsSync(preflightPath)) {
  try {
    preflightStatus = sanitizeInternal(JSON.parse(fs.readFileSync(preflightPath, 'utf8')).status);
  } catch {
    preflightStatus = 'INVALID_PREFLIGHT_RESULT';
  }
}
if (classification === 'PASS' && acceptanceCriteria.length === 0) {
  throw new Error('PASS requires at least one acceptance criterion.');
}
if (classification === 'PASS' && coveredCriteria !== acceptanceCriteria.length) {
  throw new Error('PASS requires every acceptance criterion to map to an executed scenario.');
}
if (
  classification === 'PASS' &&
  scenarios.some(item => !item.hasDetail || item.steps.length === 0 || !item.expected || !item.actual)
) {
  throw new Error('PASS requires scenarioDetails with steps, expected and actual observations for every scenario.');
}
if (classification === 'PASS' && visualMode !== 'not-applicable' && !visual.checked) {
  throw new Error(`PASS requires visual.checked=true when visual.mode is ${visualMode}.`);
}
if (visual.checked && visualMode === 'not-applicable') {
  throw new Error('visual.checked=true requires visual.mode to be design-diff or layout-regression.');
}
const minimumVisualEvidence = visualMode === 'design-diff' ? 2 : visualMode === 'layout-regression' ? 1 : 0;
if (
  classification === 'PASS' &&
  visual.checked &&
  (visualRegions.length === 0 ||
    visualRegions.some(item => item.status !== 'PASS') ||
    visualEvidence.length < minimumVisualEvidence)
) {
  throw new Error(
    `Visual PASS requires passing region checks and at least ${minimumVisualEvidence} local evidence image(s).`
  );
}
const evidenceIndex = [
  { label: 'Markdown 详细报告', href: 'report.md' },
  localEvidenceLink(path.join(runDir, 'html-report/index.html'), 'Playwright 交互报告', runDir, outputDir),
  resultsPath ? localEvidenceLink(resultsPath, 'Playwright JSON 原始结果', runDir, outputDir) : null,
  localEvidenceLink(preflightPath, '页面前检结果', runDir, outputDir),
  localEvidenceLink(path.join(runDir, 'preflight.png'), '页面前检截图', runDir, outputDir),
]
  .filter(Boolean)
  .concat(scenarios.flatMap(item => item.evidence))
  .filter((item, index, items) => items.findIndex(candidate => candidate.href === item.href) === index);
const generatedAt = new Date().toISOString();
const runId = sanitizeInternal(scope.runId || path.basename(runDir));
const reportModel = {
  title: sanitizeInternal(scope.title || '一次性 E2E 测试报告'),
  runId,
  generatedAt,
  classification,
  testPhase,
  preflightStatus: preflightStatus || '未执行',
  requirement: sanitizeInternal(scope.requirement),
  scopeText: scopeText || '未填写',
  changedArea: sanitizeInternal(scope.changedArea) || '未填写',
  changedFiles: normalizeTextList(scope.changedFiles),
  entry: sanitizeInternal(scope.entry) || '未填写',
  environment: environment || '未填写',
  passed,
  failed,
  skipped,
  total,
  durationText: formatDuration(totalDuration),
  acceptanceCriteria,
  coverage,
  coveredCriteria,
  totalCriteria: coverage.length,
  coveragePercent,
  coverageText,
  scenarios,
  repairHistory,
  visual: {
    mode: visualMode,
    checked: Boolean(visual.checked),
    classification: sanitizeInternal(visual.classification || 'NOT_RUN'),
    summary: sanitizeInternal(visual.summary) || '未填写',
    diffRatioText: typeof visual.diffRatio === 'number' ? visual.diffRatio.toFixed(4) : '—',
    regions: visualRegions,
    evidence: visualEvidence,
  },
  risks,
  uncovered,
  evidenceIndex,
};
const coverageLines = coverage.length
  ? [
      '| 验收项 | 关联场景 | 状态 |',
      '| --- | --- | --- |',
      ...coverage.map(item => `| ${item.criterion} | ${item.scenarios.join('、') || '未映射'} | ${item.status} |`),
    ]
  : ['- 未填写验收项，无法计算覆盖率。'];
const scenarioDetailLines = scenarios.length
  ? scenarios.flatMap((item, index) => [
      `### ${index + 1}. ${item.title}`,
      '',
      `- 状态：${item.status}；耗时：${item.durationText}；执行：${item.attempts} 次`,
      `- 验收项：${item.acceptanceCriteria.join('；') || '未映射'}`,
      `- 前置条件：${item.preconditions.join('；') || '无特殊前置条件'}`,
      `- 预期：${item.expected || '未填写'}`,
      `- 实际：${item.actual || '未填写'}`,
      ...(item.steps.length
        ? ['- 步骤：', ...item.steps.map((step, stepIndex) => `  ${stepIndex + 1}. ${step.action}`)]
        : ['- 步骤：未填写']),
      ...(item.error ? [`- 失败信息：${item.error}`] : []),
      '',
    ])
  : ['- 没有可汇总的 E2E 场景。'];
const visualRegionLines = visual.checked
  ? visualRegions.length
    ? visualRegions.map(item => `- [${item.status}] ${item.name}：${item.summary || '未填写'}`)
    : ['- 已执行视觉检查，但未填写分区结论。']
  : ['- 本次无视觉验收，或尚未执行视觉检查。'];
const riskLines = risks.length
  ? risks.map(item => `- [${item.levelLabel}] ${item.item}${item.detail ? `：${item.detail}` : ''}`)
  : ['- 未记录额外风险。'];
const uncoveredLines = uncovered.length
  ? uncovered.map(item => `- ${item.item}${item.detail ? `：${item.detail}` : ''}`)
  : ['- 没有声明未覆盖项。'];

const localReport = [
  `# ${sanitizeInternal(scope.title || '一次性 E2E 测试报告')}`,
  '',
  `- 分类：${classification}`,
  `- 阶段：${testPhase}`,
  `- 页面前检：${preflightStatus || '未执行'}`,
  `- 范围：${scopeText || '未填写'}`,
  `- 改动区域：${sanitizeInternal(scope.changedArea) || '未填写'}`,
  `- 入口：${sanitizeInternal(scope.entry) || '未填写'}`,
  `- 环境：${environment || '未填写'}`,
  `- 结果：${passed}/${total} 通过，${failed} 失败，${skipped} 跳过`,
  `- 视觉：${visualText}`,
  '',
  '## 验收覆盖矩阵',
  '',
  ...coverageLines,
  '',
  '## 场景执行明细',
  '',
  ...scenarioDetailLines,
  '',
  '## 修复闭环',
  '',
  ...repairLines,
  '',
  '## 视觉还原',
  '',
  ...visualRegionLines,
  '',
  '## 风险与未覆盖项',
  '',
  '### 残余风险',
  '',
  ...riskLines,
  '',
  '### 未覆盖项',
  '',
  ...uncoveredLines,
  '',
  '## 证据',
  '',
  resultsPath
    ? '- Playwright HTML、JSON、截图、视频与 trace 保存在本次 `.e2e-runs/` 运行目录中，仅供本地排障。'
    : '- 页面前检在业务场景前结束；已保留 preflight 结果，未生成 Playwright HTML、JSON、视频或 trace。',
  '- 一次性测试脚本与证据未写入 Git；公共 E2E 基础设施维护在仓库 `e2e/` 目录。',
  '',
  '## 备注',
  '',
  ...((scope.notes || []).length ? scope.notes.map(note => `- ${sanitizeInternal(note)}`) : ['- 无']),
  '',
].join('\n');

const prSummary = [
  '### 一次性 E2E 自动化',
  `- 范围：${sanitizePublic(publicSummary.scope || scopeText) || '未填写'}`,
  `- 环境：${sanitizePublic(publicSummary.environment || environment) || '未填写'}`,
  `- 结果：${classification}；${passed}/${total} 通过，${failed} 失败，${skipped} 跳过`,
  `- 验收覆盖：${coverageText}（${coveredCriteria}/${coverage.length}）`,
  `- 修复闭环：${sanitizePublic(publicSummary.repair || repairSummaryText)}`,
  ...caseLines,
  `- 视觉还原：${sanitizePublic(publicSummary.visual || visualText)}`,
  '- 说明：一次性测试脚本与证据仅保存在本地；公共 E2E 基础设施由仓库统一维护。',
  '',
].join('\n');

const tapdStatus = {
  PASS: { icon: '✅', label: '通过', gate: '本次需求关联功能未发现 E2E 交付阻断。' },
  FAIL_PRODUCT: { icon: '❌', label: '产品失败', gate: '存在产品行为与验收不一致，阻断交付并等待修复复测。' },
  BLOCKED_ENV: { icon: '⛔', label: '环境阻塞', gate: '测试被环境、权限或数据阻塞，暂时无法给出放行结论。' },
  INVALID_TEST: { icon: '⚠️', label: '测试无效', gate: '测试本身无效，需要修正测试并重新执行。' },
  NOT_RUN: { icon: '⚪', label: '未执行', gate: '本次未建立 E2E 验证证据。' },
  UNCLASSIFIED: { icon: '❓', label: '待判断', gate: '结果尚未完成分类，需要人工判断。' },
}[classification];
const tapdAcceptanceLines = coverage.length
  ? coverage.map((item, index) => {
      const statusIcon = item.status === 'PASS' ? '✅' : item.status === 'FAILED' ? '❌' : '⚠️';
      return `${index + 1}. ${statusIcon} ${item.criterion}`;
    })
  : ['- ⚠️ 未填写验收项，无法确认覆盖情况'];
const tapdScenarioLines = scenarios.length
  ? scenarios.map(scenario => {
      const statusIcon = scenario.status === 'passed' ? '✅' : scenario.status === 'skipped' ? '⚠️' : '❌';
      const observation = scenario.actual || '未填写实际结果';
      if (scenario.status === 'passed') {
        return `- ${statusIcon} ${scenario.title}：${observation}`;
      }
      return `- ${statusIcon} ${scenario.title}：预期 ${scenario.expected || '未填写'}；实际 ${observation}`;
    })
  : ['- ⚠️ 没有可汇总的 E2E 场景'];
const tapdVisualLines = visual.checked
  ? visualRegions.length
    ? visualRegions.map(item => `- [${item.status}] ${item.name}：${item.summary || '未填写'}`)
    : [`- ${visualText}`]
  : ['- 不适用或未执行'];
const tapdRiskLines = [
  ...risks.map(item => `- [残余风险/${item.levelLabel}] ${item.item}${item.detail ? `：${item.detail}` : ''}`),
  ...uncovered.map(item => `- [未覆盖] ${item.item}${item.detail ? `：${item.detail}` : ''}`),
];
const tapdCommentLines = [
  `### E2E 验证：${tapdStatus.icon} ${tapdStatus.label}`,
  '',
  `> E2E 门禁：${tapdStatus.gate}验收覆盖 ${coveredCriteria}/${coverage.length}，自动化场景 ${passed}/${total} 通过。`,
  '',
  `- 测试范围：${scopeText || '未填写'}`,
  `- 执行环境：${environment || '未填写'}`,
  `- 测试入口：${sanitizeInternal(scope.entry) || '未填写'}`,
  `- 页面前检：${preflightStatus || '未执行'}`,
  `- 执行时间：${generatedAt}`,
  `- Run ID：${runId}`,
  '',
  '#### 场景结果',
  '',
  ...tapdScenarioLines,
  '',
  '#### 验收结果',
  '',
  ...tapdAcceptanceLines,
  '',
];
if (repairHistory.length) {
  tapdCommentLines.push('#### 修复闭环', '', ...repairLines, '');
}
if (visual.checked) {
  tapdCommentLines.push('#### 视觉还原', '', ...tapdVisualLines, '');
}
if (tapdRiskLines.length) {
  tapdCommentLines.push('#### 未覆盖与残余风险', '', ...tapdRiskLines, '');
}
tapdCommentLines.push(
  '#### 追溯信息',
  '',
  `- 最终分类：${classification}`,
  `- 场景统计：${passed}/${total} 通过，${failed} 失败，${skipped} 跳过`,
  resultsPath
    ? '- 本地证据：Playwright HTML、截图、视频与 trace 已保留；截图和视频已进入 TAPD 待上传清单。'
    : '- 本地证据：已保留页面前检结果；业务场景未执行，因此没有 Playwright 结果与 trace。',
  '',
  '> TAPD 为内网记录，可保留业务上下文和内网地址；凭据、Cookie、Token 与本地绝对路径仍不会写入评论。',
  ''
);
const tapdComment = tapdCommentLines.join('\n');

const deliveryFacts = {
  version: 1,
  runId,
  generatedAt,
  classification,
  testPhase,
  gate: tapdStatus,
  stats: {
    passed,
    failed,
    skipped,
    total,
    coveredCriteria,
    totalCriteria: coverage.length,
    coverageText,
  },
  public: {
    scope: sanitizePublic(publicSummary.scope || scopeText),
    environment: sanitizePublic(publicSummary.environment || environment),
    scenarios: scenarios.map((scenario, index) => ({
      label: sanitizePublic(publicScenarioLabels[index] || scenario.title),
      status: scenario.status,
    })),
    checks: normalizeTextList(publicSummary.checks).map(sanitizePublic),
    repair: sanitizePublic(publicSummary.repair || repairSummaryText),
    visual: sanitizePublic(publicSummary.visual || visualText),
    risks: publicRisks,
    uncovered: publicUncovered,
  },
  internal: {
    title: reportModel.title,
    requirement: reportModel.requirement,
    scope: reportModel.scopeText,
    environment: reportModel.environment,
    entry: reportModel.entry,
    testPhase,
    preflightStatus: reportModel.preflightStatus,
    acceptanceResults: coverage.map(item => ({
      index: item.index,
      criterion: item.criterion,
      status: item.status,
      scenarios: scenarios
        .filter(scenario => scenario.acceptanceCriteria.includes(item.criterion))
        .map(scenario => ({
          title: scenario.title,
          status: scenario.status,
          preconditions: scenario.preconditions,
          steps: scenario.steps,
          expected: scenario.expected,
          actual: scenario.actual,
        })),
    })),
    repairHistory,
    visual: reportModel.visual,
    risks,
    uncovered,
    artifacts: uploadArtifacts,
  },
};

fs.mkdirSync(outputDir, { recursive: true });
const reportPath = path.join(outputDir, 'report.md');
const prSummaryPath = path.join(outputDir, 'pr-summary.md');
const tapdTestFragmentPath = path.join(outputDir, 'tapd-test-fragment.md');
const deliveryFactsPath = path.join(outputDir, 'delivery-facts.json');
const visualReportPath = path.join(outputDir, 'index.html');
fs.writeFileSync(reportPath, localReport, 'utf8');
fs.writeFileSync(prSummaryPath, prSummary, 'utf8');
fs.writeFileSync(tapdTestFragmentPath, tapdComment, 'utf8');
fs.writeFileSync(deliveryFactsPath, `${JSON.stringify(deliveryFacts, null, 2)}\n`, 'utf8');
fs.writeFileSync(visualReportPath, renderHtmlReport(reportModel), 'utf8');
console.log(
  JSON.stringify(
    {
      visualReportPath,
      reportPath,
      prSummaryPath,
      tapdTestFragmentPath,
      deliveryFactsPath,
      classification,
      passed,
      failed,
      skipped,
      total,
    },
    null,
    2
  )
);
