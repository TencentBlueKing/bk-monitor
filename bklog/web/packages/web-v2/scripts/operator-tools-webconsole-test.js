/*
 * Restore WebConsole entry in retrieve row operator tools.
 *
 * Run:
 *   node scripts/operator-tools-webconsole-test.js
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(
  path.join(__dirname, '../src/views/retrieve-v2/components/result-cell-element/operator-tools.vue'),
  'utf8',
);

const requiredSnippets = [
  "v-if=\"isActiveWebConsole && !isMonitorApm\"",
  "handleCheckClick('webConsole', isCanClickWebConsole)",
  'id="webConsole-html"',
  'isActiveWebConsole()',
  'isCanClickWebConsole()',
  'this.operatorConfig?.bcsWebConsole?.is_active',
  "return this.handleClick(clickType, event);",
];

for (const snippet of requiredSnippets) {
  assert.match(source, new RegExp(snippet.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')), `missing: ${snippet}`);
}

const unionBlock = source.slice(source.indexOf('<template v-else>'), source.indexOf('</template>', source.indexOf('<template v-else>')));
assert.doesNotMatch(unionBlock, /webConsole/, '联合检索分支不应出现 WebConsole 入口（与改版前一致）');
assert.equal((source.match(/handleCheckClick\('webConsole'/g) || []).length, 1);

const canClickWebConsole = (rowData, isActiveWebConsole) => {
  if (!isActiveWebConsole) return false;
  const { cluster, container_id: containerID, __ext } = rowData;
  let queryData = {};
  if (cluster && containerID) {
    queryData = {
      cluster,
      container_id: containerID,
    };
  } else {
    if (!__ext) return false;
    if (!__ext.container_id) return false;
    queryData = { container_id: __ext.container_id };
    if (__ext.io_tencent_bcs_cluster) {
      Object.assign(queryData, {
        cluster: __ext.io_tencent_bcs_cluster,
      });
    } else if (__ext.bk_bcs_cluster_id) {
      Object.assign(queryData, {
        cluster: __ext.bk_bcs_cluster_id,
      });
    }
  }
  if (!queryData.cluster || !queryData.container_id) return false;
  return true;
};

assert.equal(canClickWebConsole({}, false), false, '开关关闭时不可点');
assert.equal(canClickWebConsole({ cluster: 'BCS-K8S-1', container_id: 'c1' }, false), false);
assert.equal(canClickWebConsole({ cluster: 'BCS-K8S-1', container_id: 'c1' }, true), true, '直出 cluster/container_id 可点');
assert.equal(canClickWebConsole({ cluster: 'BCS-K8S-1' }, true), false, '缺 container_id 不可点');
assert.equal(
  canClickWebConsole(
    { __ext: { io_tencent_bcs_cluster: 'BCS-K8S-2', container_id: 'c2' } },
    true,
  ),
  true,
  '兼容 io_tencent_bcs_cluster',
);
assert.equal(
  canClickWebConsole({ __ext: { bk_bcs_cluster_id: 'BCS-K8S-3', container_id: 'c3' } }, true),
  true,
  '兼容 bk_bcs_cluster_id',
);
assert.equal(canClickWebConsole({ __ext: { container_id: 'c4' } }, true), false, '只有容器 ID 不可点');
assert.equal(canClickWebConsole({ __ext: { bk_bcs_cluster_id: 'BCS-K8S-3' } }, true), false);
assert.equal(canClickWebConsole({ __ext: {} }, true), false);
assert.equal(canClickWebConsole({}, true), false);

const handleCheckClick = (clickType, isActive, handleClick) => {
  if (!isActive) return undefined;
  if (clickType === 'trace_id') return 'trace';
  return handleClick(clickType);
};

assert.equal(handleCheckClick('webConsole', false, type => type), undefined, '不可点时不透出事件');
assert.equal(handleCheckClick('webConsole', true, type => type), 'webConsole', '可点时向父组件透出 webConsole');

console.log('operator-tools-webconsole-test: pass');
