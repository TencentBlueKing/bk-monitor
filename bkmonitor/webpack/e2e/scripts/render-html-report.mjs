export function renderHtmlReport(model) {
  const tone = statusTone(model.classification);
  const styles = [
    ':root{--ink:#101826;--muted:#647084;--line:#dfe4ea;--paper:#f3f5f7;--panel:#fff;--pass:#16805a;--pass-soft:#dff5ea;--fail:#c33f38;--fail-soft:#fde8e6;--warn:#a66507;--warn-soft:#fff1d8;--accent:#155eef;--navy:#14243a}',
    '*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:"Avenir Next","PingFang SC","Microsoft YaHei",sans-serif;font-size:14px;line-height:1.6}',
    'body:before{content:"";position:fixed;inset:0;pointer-events:none;background-image:linear-gradient(rgba(16,24,38,.026) 1px,transparent 1px),linear-gradient(90deg,rgba(16,24,38,.026) 1px,transparent 1px);background-size:32px 32px}',
    '.shell{position:relative;max-width:1280px;margin:0 auto;padding:34px 28px 80px}.hero{display:grid;grid-template-columns:1fr auto;gap:32px;align-items:end;padding:38px 42px;background:var(--navy);color:#fff;border-radius:4px;box-shadow:0 18px 45px rgba(20,36,58,.18);overflow:hidden;position:relative}',
    '.hero:after{content:"";position:absolute;width:360px;height:360px;border:1px solid rgba(255,255,255,.14);border-radius:50%;right:-160px;top:-200px;box-shadow:0 0 0 58px rgba(255,255,255,.025),0 0 0 116px rgba(255,255,255,.018)}',
    '.eyebrow{font:600 11px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.18em;color:#91b5ff}.hero h1{font-size:34px;line-height:1.18;margin:10px 0 12px;max-width:780px;letter-spacing:-.025em}.hero p{margin:0;color:#b9c5d6}.verdict{position:relative;z-index:1;text-align:right;min-width:170px}.verdict span{display:block;font:600 10px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.14em;color:#9eb0c7}.verdict strong{display:block;font:700 34px ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:7px}.status-pass .verdict strong{color:#6ee7b7}.status-fail .verdict strong{color:#fda4af}.status-warn .verdict strong{color:#fcd34d}',
    '.metric-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:18px 0 28px}.metric{background:var(--panel);border:1px solid var(--line);border-top:3px solid #9aa4b2;padding:18px 20px;min-height:116px}.metric span,.metric small{display:block;color:var(--muted)}.metric span{font:600 10px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.12em;text-transform:uppercase}.metric strong{display:block;font-size:27px;line-height:1.2;margin:10px 0 4px}.metric-pass{border-top-color:var(--pass)}.metric-fail{border-top-color:var(--fail)}.metric-warn{border-top-color:var(--warn)}',
    '.section{background:var(--panel);border:1px solid var(--line);margin-top:18px}.section-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-end;padding:24px 28px 18px;border-bottom:1px solid var(--line)}.section-head div>span{font:600 10px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.16em;color:var(--accent)}.section-head h2{font-size:21px;margin:4px 0 0;letter-spacing:-.015em}.section-head p{margin:0;color:var(--muted);max-width:560px;text-align:right}.section-body{padding:26px 28px}',
    '.scope-grid{display:grid;grid-template-columns:1.2fr 1fr;gap:30px}.scope-grid h3,.scenario-body h4{font-size:12px;margin:0 0 9px;text-transform:uppercase;letter-spacing:.08em}.scope-copy{font-size:17px;margin:0 0 22px;max-width:760px}.meta-list{display:grid;grid-template-columns:120px 1fr;gap:9px 16px;margin:0}.meta-list dt{color:var(--muted)}.meta-list dd{margin:0;font-weight:600}.chip-list{display:flex;flex-wrap:wrap;gap:7px}.chip{font:500 11px ui-monospace,SFMono-Regular,Menlo,monospace;background:#eef2f7;border:1px solid #d9e0e8;padding:5px 8px}',
    'table{width:100%;border-collapse:collapse}th{text-align:left;font:600 10px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.12em;color:var(--muted);padding:0 12px 11px;border-bottom:1px solid var(--line)}td{padding:15px 12px;border-bottom:1px solid #edf0f3;vertical-align:top}.criterion-index{font:600 11px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--accent)}.scenario-link{display:block;color:#334155;margin-bottom:3px}.empty-cell{text-align:center;color:var(--muted);padding:30px}',
    '.badge{display:inline-flex;align-items:center;gap:7px;font-size:12px;font-weight:700;white-space:nowrap}.badge i{width:8px;height:8px;border-radius:50%;background:#8792a2}.badge-pass{color:var(--pass)}.badge-pass i{background:var(--pass)}.badge-fail{color:var(--fail)}.badge-fail i{background:var(--fail)}.badge-warn{color:var(--warn)}.badge-warn i{background:var(--warn)}',
    '.scenario-card{border:1px solid var(--line);margin-bottom:12px;background:#fff}.scenario-card summary{list-style:none;display:grid;grid-template-columns:42px 1fr auto 20px;align-items:center;gap:12px;padding:18px 20px;cursor:pointer}.scenario-card summary::-webkit-details-marker{display:none}.scenario-no{font:700 12px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted)}.scenario-title strong,.scenario-title small{display:block}.scenario-title small{font-size:12px;color:var(--muted);margin-top:2px}.chevron{font-size:18px;color:var(--muted)}.scenario-card[open] .chevron{transform:rotate(180deg)}.scenario-body{border-top:1px solid var(--line);padding:22px 24px 25px;background:#fafbfc}.scenario-pass{border-left:4px solid var(--pass)}.scenario-fail{border-left:4px solid var(--fail)}.scenario-warn{border-left:4px solid var(--warn)}',
    '.scenario-grid,.observation-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.plain-list{margin:0;padding-left:18px}.empty,.muted{color:var(--muted)}.observation-grid{margin:20px 0}.observation-grid>div{padding:16px;border:1px solid var(--line);background:#fff}.observation-grid span{font:700 10px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.12em}.observation-grid p{margin:8px 0 0}.expectation span{color:var(--accent)}.actual span{color:var(--pass)}',
    '.steps{list-style:none;padding:0;margin:0}.steps li{display:grid;grid-template-columns:38px 1fr;gap:10px;padding:12px 0;border-bottom:1px dashed var(--line)}.step-no{font:700 11px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--accent)}.steps p{margin:3px 0;color:var(--muted)}.error-box{margin-top:18px;background:var(--fail-soft);border-left:3px solid var(--fail);padding:15px}.error-box pre{white-space:pre-wrap;word-break:break-word;font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;margin:8px 0 0;max-height:250px;overflow:auto}.evidence-row{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-top:18px}.evidence-link{color:var(--accent);text-decoration:none;border-bottom:1px solid #9dbafa}',
    '.timeline{position:relative;padding-left:28px}.timeline:before{content:"";position:absolute;left:8px;top:8px;bottom:8px;width:1px;background:#b7c1ce}.timeline article{position:relative;padding:0 0 28px 18px}.timeline article:last-child{padding-bottom:0}.timeline-dot{position:absolute;left:-25px;top:7px;width:12px;height:12px;border-radius:50%;background:#fff;border:3px solid var(--accent)}.timeline-meta{font:600 10px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.12em;color:var(--accent)}.timeline h3{margin:4px 0 9px}.timeline p{margin:4px 0;color:#425066}',
    '.visual-summary{display:flex;gap:14px;align-items:center;margin-bottom:20px;padding:15px 17px;background:#f6f8fb;border:1px solid var(--line)}.visual-summary>span:last-child{margin-left:auto;font:600 11px ui-monospace,SFMono-Regular,Menlo,monospace}.region-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.region-grid article{border:1px solid var(--line);padding:15px}.region-grid article>div{display:flex;gap:10px;align-items:center}.region-grid p{margin:8px 0 0;color:var(--muted)}.visual-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-top:20px}.visual-grid figure{margin:0;border:1px solid var(--line);background:#f7f8fa}.visual-grid img{display:block;width:100%;max-height:420px;object-fit:contain}.visual-grid figcaption{padding:10px 12px;font-weight:600}',
    '.risk-columns{display:grid;grid-template-columns:1fr 1fr;gap:28px}.risk-columns h3{margin-top:0}.risk-list article{display:grid;grid-template-columns:70px 1fr;gap:12px;border-top:1px solid var(--line);padding:13px 0}.risk-list p{margin:3px 0;color:var(--muted)}.risk-level{font:700 10px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase}.risk-high{color:var(--fail)}.risk-medium{color:var(--warn)}.risk-low{color:var(--pass)}',
    '.empty-panel{padding:22px;border:1px dashed #bdc6d2;background:#fafbfc}.empty-panel p{margin:4px 0 0;color:var(--muted)}.empty-panel.compact{padding:15px}.evidence-index{display:flex;gap:12px;flex-wrap:wrap}.evidence-index a{display:inline-flex;align-items:center;gap:8px;text-decoration:none;background:var(--navy);color:#fff;padding:10px 14px}.footer{display:flex;justify-content:space-between;gap:20px;margin-top:22px;color:var(--muted);font-size:12px}.footer code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}',
    '@media(max-width:900px){.metric-grid{grid-template-columns:repeat(2,1fr)}.scope-grid,.scenario-grid,.observation-grid,.risk-columns{grid-template-columns:1fr}.hero{grid-template-columns:1fr}.verdict{text-align:left}.section-head{display:block}.section-head p{text-align:left;margin-top:8px}.region-grid,.visual-grid{grid-template-columns:1fr}}',
    '@media print{body{background:#fff}.shell{max-width:none;padding:0}.hero,.section,.metric{box-shadow:none;break-inside:avoid}.scenario-card{break-inside:avoid}.evidence-link,.evidence-index{display:none}}',
  ].join('');

  const evidenceIndex =
    '<div class="evidence-index">' +
    model.evidenceIndex.map(item => `<a href="${escapeHtml(item.href)}">↗ ${escapeHtml(item.label)}</a>`).join('') +
    '</div>';
  const changedFiles = model.changedFiles.length
    ? '<div class="chip-list">' +
      model.changedFiles.map(file => `<span class="chip">${escapeHtml(file)}</span>`).join('') +
      '</div>'
    : '<p class="empty">未记录改动文件。</p>';

  return [
    '<!doctype html>',
    '<html lang="zh-CN"><head><meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    `<title>${escapeHtml(model.title)} · E2E Report</title>`,
    `<style>${styles}</style></head>`,
    `<body class="status-${tone}"><div class="shell">`,
    '<header class="hero"><div><div class="eyebrow">BK MONITOR · SCOPED E2E VERIFICATION</div><h1>' +
      escapeHtml(model.title) +
      '</h1><p>' +
      escapeHtml(model.scopeText) +
      '</p></div><div class="verdict"><span>FINAL VERDICT</span><strong>' +
      escapeHtml(model.classification) +
      '</strong></div></header>',
    '<section class="metric-grid">',
    renderMetric('Scenarios', `${model.passed}/${model.total}`, `${model.failed} 失败 · ${model.skipped} 跳过`, tone),
    renderMetric(
      'Acceptance Coverage',
      model.coverageText,
      `${model.coveredCriteria}/${model.totalCriteria} 条验收项有场景`,
      model.coveragePercent === 100 ? 'pass' : 'warn'
    ),
    renderMetric(
      'Visual',
      model.visual.checked ? statusLabel(model.visual.classification) : '不适用',
      model.visual.diffRatioText,
      model.visual.checked ? statusTone(model.visual.classification) : 'neutral'
    ),
    renderMetric(
      'Repair Rounds',
      String(model.repairHistory.length),
      model.repairHistory.length ? '已保留完整闭环' : '未触发产品修复'
    ),
    renderMetric('Duration', model.durationText, model.environment),
    '</section>',
    '<section class="section"><div class="section-head"><div><span>01 · SCOPE</span><h2>验证边界</h2></div><p>只解释这次需求与代码改动直接相关的验证范围。</p></div><div class="section-body scope-grid">',
    '<div><h3>需求与范围</h3><p class="scope-copy">' +
      escapeHtml(model.requirement || model.scopeText) +
      '</p><h3>改动文件</h3>' +
      changedFiles +
      '</div>',
    '<dl class="meta-list"><dt>应用 / 模式</dt><dd>' +
      escapeHtml(model.environment) +
      '</dd><dt>测试阶段</dt><dd>' +
      escapeHtml(model.testPhase) +
      '</dd><dt>页面前检</dt><dd>' +
      escapeHtml(model.preflightStatus) +
      '</dd><dt>入口</dt><dd>' +
      escapeHtml(model.entry) +
      '</dd><dt>改动区域</dt><dd>' +
      escapeHtml(model.changedArea) +
      '</dd><dt>运行 ID</dt><dd><code>' +
      escapeHtml(model.runId) +
      '</code></dd></dl>',
    '</div></section>',
    '<section class="section"><div class="section-head"><div><span>02 · COVERAGE</span><h2>验收覆盖矩阵</h2></div><p>每条验收要求必须能追到具体自动化场景，未映射项会明确标红。</p></div><div class="section-body"><table><thead><tr><th>#</th><th>验收项</th><th>关联场景</th><th>状态</th></tr></thead><tbody>' +
      renderCoverageRows(model.coverage) +
      '</tbody></table></div></section>',
    '<section class="section"><div class="section-head"><div><span>03 · SCENARIOS</span><h2>场景执行明细</h2></div><p>展开查看前置条件、操作步骤、预期结果、实际观察与本地证据。</p></div><div class="section-body">' +
      (model.scenarios.length
        ? model.scenarios.map(renderScenario).join('')
        : '<div class="empty-panel"><strong>没有可汇总的测试场景</strong></div>') +
      '</div></section>',
    '<section class="section"><div class="section-head"><div><span>04 · REPAIR</span><h2>失败与修复时间线</h2></div><p>不会用最终绿色结论覆盖首轮失败。</p></div><div class="section-body">' +
      renderRepairHistory(model.repairHistory) +
      '</div></section>',
    '<section class="section"><div class="section-head"><div><span>05 · VISUAL</span><h2>视觉验收证据</h2></div><p>设计还原使用差异对比；布局回归使用几何断言与最终截图。</p></div><div class="section-body">' +
      renderVisualEvidence(model.visual) +
      '</div></section>',
    '<section class="section"><div class="section-head"><div><span>06 · RISK</span><h2>风险与未覆盖项</h2></div><p>明确说明这份报告没有证明什么。</p></div><div class="section-body risk-columns"><div><h3>残余风险</h3>' +
      renderRisks(model.risks, 'risk') +
      '</div><div><h3>未覆盖项</h3>' +
      renderRisks(model.uncovered, 'uncovered') +
      '</div></div></section>',
    '<section class="section"><div class="section-head"><div><span>07 · EVIDENCE</span><h2>本地证据索引</h2></div><p>证据可能包含业务信息，只在本机查看，不进入公开 PR。</p></div><div class="section-body">' +
      evidenceIndex +
      '</div></section>',
    '<footer class="footer"><span>Generated ' +
      escapeHtml(model.generatedAt) +
      '</span><span><code>' +
      escapeHtml(model.runId) +
      '</code> · local-only evidence</span></footer>',
    '</div></body></html>',
  ].join('');
}

function badge(status) {
  const tone = statusTone(status);
  return `<span class="badge badge-${tone}"><i></i>${escapeHtml(statusLabel(status))}</span>`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function renderCoverageRows(coverage) {
  if (!coverage.length) {
    return '<tr><td colspan="4" class="empty-cell">scope.json 尚未填写验收项，无法计算覆盖关系。</td></tr>';
  }
  return coverage
    .map(
      item =>
        '<tr>' +
        '<td><span class="criterion-index">' +
        String(item.index).padStart(2, '0') +
        '</span></td>' +
        '<td><strong>' +
        escapeHtml(item.criterion) +
        '</strong></td>' +
        '<td>' +
        (item.scenarios.length
          ? item.scenarios.map(title => `<span class="scenario-link">${escapeHtml(title)}</span>`).join('')
          : '<span class="muted">没有映射到测试场景</span>') +
        '</td>' +
        '<td>' +
        badge(item.status) +
        '</td>' +
        '</tr>'
    )
    .join('');
}

function renderEvidence(evidence) {
  if (!evidence?.length) return '<span class="muted">无额外附件</span>';
  return evidence
    .map(item => `<a class="evidence-link" href="${escapeHtml(item.href)}">${escapeHtml(item.label)}</a>`)
    .join('');
}

function renderList(items, emptyText) {
  if (!items?.length) return `<p class="empty">${escapeHtml(emptyText)}</p>`;
  return `<ul class="plain-list">${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
}

function renderMetric(label, value, hint, tone = 'neutral') {
  return [
    `<article class="metric metric-${tone}">`,
    `<span>${escapeHtml(label)}</span>`,
    `<strong>${escapeHtml(value)}</strong>`,
    `<small>${escapeHtml(hint)}</small>`,
    '</article>',
  ].join('');
}

function renderRepairHistory(history) {
  if (!history.length) {
    return '<div class="empty-panel"><strong>本次没有触发产品修复</strong><p>测试在首轮通过，或失败后未进入授权修复。</p></div>';
  }
  return (
    '<div class="timeline">' +
    history
      .map(
        item =>
          '<article>' +
          '<span class="timeline-dot"></span>' +
          '<div class="timeline-meta">ROUND ' +
          escapeHtml(item.round) +
          ' · 已授权</div>' +
          '<h3>' +
          escapeHtml(item.failureClassification) +
          ' → ' +
          escapeHtml(item.retestResult) +
          '</h3>' +
          '<p><strong>发现：</strong>' +
          escapeHtml(item.failureSummary) +
          '</p>' +
          '<p><strong>修复：</strong>' +
          escapeHtml(item.repairSummary) +
          '</p>' +
          '</article>'
      )
      .join('') +
    '</div>'
  );
}

function renderRisks(items, type) {
  if (!items.length) {
    return (
      '<div class="empty-panel compact"><strong>' +
      (type === 'risk' ? '未记录额外风险' : '没有声明未覆盖项') +
      '</strong></div>'
    );
  }
  return (
    '<div class="risk-list">' +
    items
      .map(
        item =>
          '<article><span class="risk-level risk-' +
          escapeHtml(item.level) +
          '">' +
          escapeHtml(item.levelLabel) +
          '</span><div><strong>' +
          escapeHtml(item.item) +
          '</strong><p>' +
          escapeHtml(item.detail) +
          '</p></div></article>'
      )
      .join('') +
    '</div>'
  );
}

function renderScenario(scenario, index) {
  const tone = statusTone(scenario.status);
  return [
    `<details class="scenario-card scenario-${tone}" open>`,
    '<summary>',
    `<span class="scenario-no">${String(index + 1).padStart(2, '0')}</span>`,
    '<span class="scenario-title"><strong>' +
      escapeHtml(scenario.title) +
      '</strong><small>' +
      escapeHtml(scenario.durationText) +
      ' · ' +
      escapeHtml(String(scenario.attempts)) +
      ' 次执行</small></span>',
    badge(scenario.status),
    '<span class="chevron">⌄</span>',
    '</summary>',
    '<div class="scenario-body">',
    '<div class="scenario-grid">',
    `<div><h4>关联验收项</h4>${renderList(scenario.acceptanceCriteria, '未建立验收项映射。')}</div>`,
    `<div><h4>前置条件</h4>${renderList(scenario.preconditions, '无特殊前置条件。')}</div>`,
    '</div>',
    '<div class="observation-grid">',
    '<div class="expectation"><span>EXPECTED</span><p>' +
      escapeHtml(scenario.expected || '未补充明确预期。') +
      '</p></div>',
    `<div class="actual"><span>ACTUAL</span><p>${escapeHtml(scenario.actual || '未补充实际观察。')}</p></div>`,
    '</div>',
    '<h4>执行步骤</h4>',
    renderSteps(scenario.steps),
    scenario.error
      ? `<div class="error-box"><strong>失败信息</strong><pre>${escapeHtml(scenario.error)}</pre></div>`
      : '',
    `<div class="evidence-row"><strong>证据</strong>${renderEvidence(scenario.evidence)}</div>`,
    '</div>',
    '</details>',
  ].join('');
}

function renderSteps(steps) {
  if (!steps?.length) return '<p class="empty">未补充操作步骤。</p>';
  return (
    '<ol class="steps">' +
    steps
      .map(
        (step, index) =>
          '<li>' +
          '<span class="step-no">' +
          String(index + 1).padStart(2, '0') +
          '</span>' +
          '<div><strong>' +
          escapeHtml(step.action) +
          '</strong>' +
          (step.expected ? `<p>预期：${escapeHtml(step.expected)}</p>` : '') +
          (step.actual ? `<p>实际：${escapeHtml(step.actual)}</p>` : '') +
          '</div></li>'
      )
      .join('') +
    '</ol>'
  );
}

function renderVisualEvidence(visual) {
  if (!visual.checked) {
    return '<div class="empty-panel"><strong>本次无视觉验收或尚未执行</strong><p>交互测试结果不等同于设计还原或布局回归结论。</p></div>';
  }
  const regions = visual.regions?.length
    ? '<div class="region-grid">' +
      visual.regions
        .map(
          region =>
            '<article><div>' +
            badge(region.status) +
            '<strong>' +
            escapeHtml(region.name) +
            '</strong></div><p>' +
            escapeHtml(region.summary) +
            '</p></article>'
        )
        .join('') +
      '</div>'
    : '<p class="empty">尚未补充视觉分区检查。</p>';
  const images = visual.evidence?.length
    ? '<div class="visual-grid">' +
      visual.evidence
        .map(
          item =>
            '<figure><a href="' +
            escapeHtml(item.href) +
            '"><img src="' +
            escapeHtml(item.href) +
            '" alt="' +
            escapeHtml(item.label) +
            '"></a><figcaption>' +
            escapeHtml(item.label) +
            '</figcaption></figure>'
        )
        .join('') +
      '</div>'
    : '<p class="empty">没有可展示的本地视觉图片。</p>';
  return (
    '<div class="visual-summary">' +
    badge(visual.classification) +
    '<span>' +
    escapeHtml(visual.mode) +
    '</span>' +
    '<strong>' +
    escapeHtml(visual.summary) +
    '</strong>' +
    '<span>diff ratio ' +
    escapeHtml(visual.diffRatioText) +
    '</span></div>' +
    regions +
    images
  );
}

function statusLabel(status) {
  const labels = {
    PASS: '通过',
    PASSED: '通过',
    FAIL_PRODUCT: '产品失败',
    FAILED: '失败',
    TIMEDOUT: '超时',
    INTERRUPTED: '中断',
    BLOCKED_ENV: '环境阻塞',
    INVALID_TEST: '测试无效',
    SKIPPED: '跳过',
    NOT_COVERED: '未覆盖',
    NOT_RUN: '未执行',
    UNCLASSIFIED: '待分类',
  };
  return labels[String(status || '').toUpperCase()] || String(status || '未知');
}

function statusTone(status) {
  const value = String(status || '').toUpperCase();
  if (['PASS', 'PASSED'].includes(value)) return 'pass';
  if (['FAIL_PRODUCT', 'FAILED', 'TIMEDOUT', 'INTERRUPTED'].includes(value)) return 'fail';
  if (['BLOCKED_ENV', 'INVALID_TEST', 'SKIPPED', 'NOT_COVERED'].includes(value)) return 'warn';
  return 'neutral';
}
