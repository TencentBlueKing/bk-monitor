<!--
  Tencent is pleased to support the open source community by making
  蓝鲸智云PaaS平台 (BlueKing PaaS) available.

  Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.

  蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.

  License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
  ---------------------------------------------------
  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  documentation files (the "Software"), to deal in the Software without restriction, including without limitation
  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
  to permit persons to whom the Software is furnished to do so, subject to the following conditions:
  The above copyright notice and this permission notice shall be included in all copies or substantial portions of
  the Software.
  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
  THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
  CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
  IN THE SOFTWARE.
-->
<template>
  <section class="retrieve-shell" data-ui="retrieve-root">
    <retrieve-favorite-panel
      v-if="toolbar.favoriteShown"
      :state="favorite"
      :visible-groups="visibleGroups"
      @filter="onFavoriteFilter"
      @current-only="onCurrentOnly"
      @apply="onApplyFavorite"
      @remove="onRemoveFavorite"
      @save="openSave"
      @collapse="onToggleFavorite"
    />
    <section class="retrieve-main">
      <retrieve-toolbar
        :toolbar="toolbar"
        :index-set-id="workspace.indexSetId"
        :index-set-options="indexSetOptions"
        @toggle-favorite="onToggleFavorite"
        @change-index-set="onChangeIndexSet"
        @change-time="onChangeTime"
        @auto-refresh="onAutoRefresh"
        @save-favorite="openSave"
        @open-share="openShare"
        @open-field-config="openFieldConfig"
        @open-global-settings="openGlobalSettings"
        @open-more="openMore"
        @open-help="openHelp"
        @open-history="openHistory"
      />
      <retrieve-searchbar
        ref="searchbarRef"
        v-model:keyword="keyword"
        :loading="search.uiState === 'loading'"
        :history="searchHistory"
        @search="onSearch"
        @apply-history="onApplyHistory"
      />
      <retrieve-scene-bar :state="scene" @change="onScene" @filter="onSceneFilter" />
      <t-alert v-if="search.uiState === 'error'" theme="error" :message="search.error" />
      <section class="retrieve-result">
        <retrieve-field-panel :state="fields" @toggle="onToggleField" @filter="onFieldFilter" @refresh="refreshFields" />
        <section class="retrieve-result__main" data-ui="result-panel">
          <nav class="retrieve-result__tabs" data-ui="result-tabs">
            <button type="button" :class="{ 'is-active': workspace.tab === 'origin' }" data-ui="tab-origin" @click="onTab('origin')">原始日志</button>
            <button type="button" :class="{ 'is-active': workspace.tab === 'clustering' }" data-ui="tab-clustering" @click="onTab('clustering')">日志聚类</button>
            <button type="button" :class="{ 'is-active': workspace.tab === 'graph' }" data-ui="tab-graph" @click="onTab('graph')">图表分析</button>
            <button type="button" :class="{ 'is-active': workspace.tab === 'grep' }" data-ui="tab-grep" @click="onTab('grep')">Grep 模式</button>
          </nav>
          <div v-if="workspace.tab === 'origin'" class="retrieve-result__meta">
            <span>检索 {{ search.total }} 条结果，用时 {{ searchCostText }}</span>
            <span class="retrieve-result__tools">
              <span>汇聚周期：auto</span>
              <t-input
                v-model="extraHighlight"
                class="retrieve-result__highlight"
                size="small"
                placeholder="高亮关键字"
                data-ui="page-highlight"
              />
              <button type="button" title="字段设置" data-ui="result-field-setting" @click="openFieldConfig"><i class="bklog-icon bklog-set-icon" /></button>
              <button type="button" title="下载" data-ui="download-entry" @click="openDownload"><i class="bklog-icon bklog-download" /></button>
            </span>
          </div>
          <section v-if="workspace.tab === 'origin'" class="retrieve-result__trend" data-ui="result-trend">
            <header class="retrieve-result__trend-head">
              <span>总趋势</span>
              <strong>{{ search.total }}</strong>
              <small>{{ formatTime(toolbar.timeRange.startTime) }} - {{ formatTime(toolbar.timeRange.endTime) }}</small>
            </header>
            <div class="retrieve-result__trend-body">
              <button
                v-for="bucket in originTrendBuckets"
                :key="bucket.startTime"
                type="button"
                class="retrieve-result__trend-bar"
                :title="`${formatTime(bucket.startTime)} · ${bucket.count}`"
              >
                <span :style="{ height: `${trendHeight(bucket.count)}%` }" />
              </button>
            </div>
            <footer class="retrieve-result__trend-axis">
              <span v-for="label in trendAxisLabels" :key="label">{{ label }}</span>
            </footer>
          </section>
          <t-loading :loading="search.uiState === 'loading' || bootstrapping">
            <template v-if="workspace.tab === 'origin'">
              <t-empty v-if="search.uiState === 'empty'" description="没有匹配的日志" />
              <div v-else data-ui="origin-table">
              <div class="retrieve-result__view-switch" data-ui="origin-view-switch">
                <button type="button" :class="{ 'is-active': resultView === 'raw' }" data-ui="origin-view-raw" @click="resultView = 'raw'">原始</button>
                <button type="button" :class="{ 'is-active': resultView === 'table' }" data-ui="origin-view-table" @click="resultView = 'table'">表格</button>
                <button type="button" :class="{ 'is-active': logSortDesc }" data-ui="log-sort" @click="logSortDesc = !logSortDesc">日志排序</button>
                <label><input v-model="showLineNo" type="checkbox" /> 显示行号</label>
                <label><input v-model="wrapLog" type="checkbox" /> 换行</label>
                <label><input v-model="grepExcludeEnabled" type="checkbox" /> 摘除</label>
              </div>
              <t-alert
                v-if="displayRecords.length > renderLimit"
                theme="warning"
                :message="`当前结果 ${displayRecords.length} 条，首屏仅渲染前 ${renderLimit} 条以保持滚动性能`"
              />
              <t-table
                class="retrieve-origin-table"
                :class="{ 'is-wrap': wrapLog }"
                style="height: auto"
                row-key="id"
                size="small"
                :data="renderedRecords"
                :columns="originColumns"
                :empty="search.uiState === 'idle' ? '正在加载日志' : '暂无数据'"
              >
                <template #dtEventTimeStamp="{ row }">
                  {{ formatTime(row.dtEventTimeStamp) }}
                </template>
                <template #lineNo="{ rowIndex }">
                  {{ Number(rowIndex) + 1 }}
                </template>
                <template #log="{ row }">
                  <div class="retrieve-log-cell-wrap">
                    <button
                      type="button"
                      :class="['retrieve-log-expand', { 'is-open': expandedId === String(row.id) }]"
                      data-ui="log-expand"
                      @click="toggleExpand(row.id)"
                    >
                      <i :class="['bklog-icon', 'bklog-arrow-down-filled', 'retrieve-log-caret', { 'is-open': expandedId === String(row.id) }]" />
                      <pre class="retrieve-log-cell"><template v-for="part in highlightLog(row.log)" :key="part.key"><mark v-if="part.mark">{{ part.text }}</mark><span v-else>{{ part.text }}</span></template></pre>
                    </button>
                    <dl v-if="expandedId === String(row.id)" class="retrieve-log-detail" data-ui="log-detail">
                      <div v-for="entry in kvEntries(row)" :key="entry.key" class="retrieve-log-kv">
                        <dt>{{ entry.key }}</dt>
                        <dd>
                          <template v-if="entry.highlight">
                            <template v-for="part in highlightLog(entry.value)" :key="part.key">
                              <mark v-if="part.mark">{{ part.text }}</mark>
                              <span v-else>{{ part.text }}</span>
                            </template>
                          </template>
                          <template v-else>{{ entry.value }}</template>
                        </dd>
                      </div>
                    </dl>
                  </div>
                </template>
                <template #op="{ row }">
                  <t-button variant="text" data-ui="log-full-row" @click="openFullRow(row)">全量</t-button>
                  <t-button variant="text" data-ui="log-context" @click="openContext(row.id)">上下文</t-button>
                  <t-button variant="text" data-ui="log-realtime" @click="openRealtime(row)">实时</t-button>
                </template>
              </t-table>
              </div>
            </template>
            <div v-else-if="workspace.tab === 'clustering'" data-ui="cluster-table">
              <t-table
                row-key="pattern"
                :data="clusterGroups"
                :columns="clusterColumns"
              />
            </div>
            <retrieve-graph-panel
              v-else-if="workspace.tab === 'graph'"
              :buckets="graphBuckets"
            />
            <retrieve-grep-panel
              v-else-if="workspace.tab === 'grep'"
              :state="grep"
              @field="onGrepField"
              @pattern="onGrepPattern"
              @run="onRunGrep"
            />
          </t-loading>
        </section>
      </section>
      <t-drawer v-model:visible="contextVisible" header="上下文日志" size="560px" @close="closeContext">
        <t-alert v-if="context.uiState === 'waiting'" theme="warning" message="主检索进行中，上下文等待完成后再展开" />
        <t-empty v-else-if="context.uiState === 'empty'" description="找不到锚点日志" />
        <t-table v-else row-key="id" :data="contextRows" :columns="contextColumns" />
      </t-drawer>
      <t-drawer v-model:visible="realtimeVisible" header="实时日志" size="560px" @close="stopRealtime">
        <t-tag>{{ realtime.uiState }}</t-tag>
        <t-table row-key="id" :data="realtime.records" :columns="contextColumns" />
      </t-drawer>
      <t-dialog
        :visible="fullRowVisible"
        header="查看全量日志"
        :confirm-btn="null"
        cancel-btn="关闭"
        width="860px"
        data-ui="full-row-dialog"
        @close="closeFullRow"
      >
        <section class="retrieve-full-row">
          <div class="retrieve-full-row__tools">
            <t-input v-model="fullRowKeyword" placeholder="搜索" clearable data-ui="full-row-search" />
            <t-button variant="outline" @click="copyFullRow">复制</t-button>
          </div>
          <pre class="retrieve-full-row__content"><template v-for="part in highlightFullRow" :key="part.key"><mark v-if="part.mark">{{ part.text }}</mark><span v-else>{{ part.text }}</span></template></pre>
        </section>
      </t-dialog>
    </section>
    <div class="retrieve-dialog-host" data-ui="dialog-host" />
    <t-dialog
      :visible="helpVisible"
      header="检索说明"
      :confirm-btn="null"
      cancel-btn="关闭"
      :z-index="helpZIndex"
      @close="closeHelp"
    >
      <p>关键字会自动去除首尾空白；条件或时间变化后分页重置为 1；旧请求不会覆盖新结果。</p>
      <p>收藏按分组展示，应用后回填关键字并重新检索；自动刷新不重置分页。</p>
    </t-dialog>
    <t-dialog
      :visible="saveVisible"
      header="保存收藏"
      confirm-btn="保存"
      cancel-btn="取消"
      :z-index="saveZIndex"
      @confirm="onSaveFavorite"
      @close="closeSave"
    >
      <t-form>
        <t-form-item label="名称">
          <t-input v-model="saveName" placeholder="输入收藏名称" />
        </t-form-item>
      </t-form>
    </t-dialog>
    <t-dialog
      :visible="shareVisible"
      header="分享检索"
      confirm-btn="复制链接"
      cancel-btn="关闭"
      :z-index="shareZIndex"
      data-ui="share-dialog"
      @confirm="copyShare"
      @close="closeShare"
    >
      <p>当前检索链接可分享给有权限的成员。</p>
      <t-input :model-value="shareUrl" readonly />
    </t-dialog>
    <t-dialog
      :visible="fieldConfigVisible"
      header="索引配置"
      confirm-btn="完成"
      cancel-btn="关闭"
      :z-index="fieldConfigZIndex"
      data-ui="field-config-dialog"
      @confirm="closeFieldConfig"
      @close="closeFieldConfig"
    >
      <p>字段模板、批量编辑别名、显示字段和隐藏无数据能力已挂载在当前字段面板。</p>
      <t-checkbox v-model="hideEmptyFields">隐藏无数据字段</t-checkbox>
      <t-checkbox v-model="useDisplayFields">启用当前显示字段</t-checkbox>
    </t-dialog>
    <t-dialog
      :visible="globalSettingsVisible"
      header="全局设置"
      confirm-btn="保存"
      cancel-btn="关闭"
      :z-index="globalSettingsZIndex"
      data-ui="global-settings-dialog"
      @confirm="closeGlobalSettings"
      @close="closeGlobalSettings"
    >
      <t-checkbox v-model="showLineNo">显示行号</t-checkbox>
      <t-checkbox v-model="wrapLog">日志换行</t-checkbox>
      <t-checkbox v-model="extraHighlightEnabled">启用高亮</t-checkbox>
    </t-dialog>
    <t-dialog
      :visible="downloadVisible"
      header="下载日志"
      confirm-btn="开始下载"
      cancel-btn="关闭"
      :z-index="downloadZIndex"
      data-ui="download-dialog"
      @confirm="closeDownload"
      @close="closeDownload"
    >
      <ul class="retrieve-popup-list">
        <li v-for="item in downloadOptions" :key="item.id">
          <button type="button" :data-ui="`download-${item.id}`" @click="selectedDownload = item.id">{{ item.label }}</button>
        </li>
      </ul>
      <div class="retrieve-popup-field-scope">
        <label><input v-model="downloadFieldScope" type="radio" value="display" /> 当前显示字段</label>
        <label><input v-model="downloadFieldScope" type="radio" value="all" /> 全部字段</label>
        <label><input v-model="downloadFieldScope" type="radio" value="custom" /> 指定字段</label>
      </div>
      <p class="retrieve-popup-tip">当前选择：{{ currentDownloadLabel }}</p>
      <pre class="retrieve-popup-code">{{ downloadPayload }}</pre>
    </t-dialog>
    <t-dialog
      :visible="moreVisible"
      header="更多"
      :confirm-btn="null"
      cancel-btn="关闭"
      :z-index="moreZIndex"
      data-ui="more-dialog"
      @close="closeMore"
    >
      <ul class="retrieve-popup-list">
        <li><button type="button" data-ui="more-legacy" @click="openLegacy">回到旧版</button></li>
        <li><button type="button" data-ui="more-guide">新手指引</button></li>
        <li><button type="button" data-ui="more-syntax" @click="openHelp">检索语法说明</button></li>
        <li><button type="button" data-ui="more-feedback">问题反馈</button></li>
      </ul>
    </t-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';

import { overlayManager } from '../../shared/overlay/overlay-manager';
import { ClusteringController } from './clustering-controller';
import { ContextController, type ContextSnapshot } from './context-controller';
import { FavoriteController, type FavoriteSnapshot } from './favorite-controller';
import { FieldController, type FieldSnapshot } from './field-controller';
import { GraphController } from './graph-controller';
import { GrepController, type GrepSnapshot } from './grep-controller';
import { IndexSetController } from './index-set-controller';
import { RealtimeController, type RealtimeSnapshot } from './realtime-controller';
import RetrieveFavoritePanel from './retrieve-favorite-panel.vue';
import RetrieveFieldPanel from './retrieve-field-panel.vue';
import RetrieveGraphPanel from './retrieve-graph-panel.vue';
import RetrieveGrepPanel from './retrieve-grep-panel.vue';
import RetrieveSceneBar from './retrieve-scene-bar.vue';
import RetrieveSearchbar from './retrieve-searchbar.vue';
import { SceneController, type SceneId, type SceneSnapshot } from './scene-controller';
import { highlightParts, parseSearchChips } from './search-query';
import { buildDialogPayload, createDevSearchFetcher, fetchRetrieveHistogram, loadRetrieveBootstrap, parseRetrieveRoute, type TrendBucket } from './retrieve-data-adapter';
import {
  RetrieveSearchController,
  type LogRecord,
  type RetrieveSnapshot,
} from './retrieve-search-controller';
import RetrieveToolbar from './retrieve-toolbar.vue';
import {
  ToolbarController,
  type SearchIntent,
  type TimePreset,
  type ToolbarSnapshot,
} from './toolbar-controller';
import { RetrieveWorkbenchController } from './retrieve-workbench-controller';
import { WorkspaceController, type RetrieveTab, type WorkspaceSnapshot } from './workspace-controller';

const routeState = parseRetrieveRoute();
const workbenchController = new RetrieveWorkbenchController(routeState);
const searchController = new RetrieveSearchController(createDevSearchFetcher(routeState));
const favoriteController = new FavoriteController();
const indexSetController = new IndexSetController(undefined, routeState.indexSetId);
const fieldController = new FieldController();
const workspaceController = new WorkspaceController(routeState.indexSetId);
const clusteringController = new ClusteringController();
const graphController = new GraphController();
const contextController = new ContextController();
const realtimeController = new RealtimeController(8);
const toolbarController = new ToolbarController(intent => {
  void submitSearch(intent);
});

const keyword = ref('');
const searchbarRef = ref<{ openHistory?: () => void } | null>(null);
const extraHighlight = ref('');
const saveName = ref('');
const searchHistory = ref<string[]>(['error', 'login', 'timeout']);
const expandedId = ref<string | null>(null);
const bootstrapping = ref(true);
const grepController = new GrepController();
const sceneController = new SceneController();
const search = reactive<RetrieveSnapshot>(searchController.getState());
const favorite = reactive<FavoriteSnapshot>(favoriteController.getState());
const toolbar = reactive<ToolbarSnapshot>(toolbarController.getState());
const grep = reactive<GrepSnapshot>(grepController.getState());
const scene = reactive<SceneSnapshot>(sceneController.getState());
const fields = reactive<FieldSnapshot>(fieldController.getState());
const workspace = reactive<WorkspaceSnapshot>(workspaceController.getState());
const context = reactive<ContextSnapshot>(contextController.getState());
const realtime = reactive<RealtimeSnapshot>(realtimeController.getState());
const visibleGroups = computed(() => favoriteController.getVisibleGroups());
const indexSetOptions = computed(() => indexSetController.getVisibleItems().map(item => ({
  label: item.tableId ? `${item.name} (${item.tableId})` : item.name,
  value: item.id,
})));
const clusterGroups = computed(() => clusteringController.group(search.records, keyword.value));
const graphBuckets = computed(() => graphController.bucket(search.records));
const remoteTrendBuckets = ref<TrendBucket[]>([]);
const originTrendBuckets = computed(() => (remoteTrendBuckets.value.length ? remoteTrendBuckets.value : graphController.bucket(search.records, 30_000)));
const trendMaxCount = computed(() => Math.max(1, ...originTrendBuckets.value.map(item => item.count)));
const trendAxisLabels = computed(() => {
  const buckets = originTrendBuckets.value;
  if (!buckets.length) {
    return ['暂无数据'];
  }
  const first = buckets[0];
  const last = buckets[buckets.length - 1];
  return [first, last].map(item => {
    const date = new Date(item.startTime);
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  });
});
const contextVisible = ref(false);
const realtimeVisible = ref(false);
const fullRowVisible = ref(false);
const helpVisible = ref(false);
const saveVisible = ref(false);
const shareVisible = ref(false);
const fieldConfigVisible = ref(false);
const globalSettingsVisible = ref(false);
const downloadVisible = ref(false);
const moreVisible = ref(false);
const helpZIndex = ref(2500);
const saveZIndex = ref(2510);
const shareZIndex = ref(2520);
const fieldConfigZIndex = ref(2530);
const globalSettingsZIndex = ref(2540);
const downloadZIndex = ref(2550);
const moreZIndex = ref(2560);
const resultView = ref<'raw' | 'table'>('raw');
const showLineNo = ref(false);
const wrapLog = ref(false);
const logSortDesc = ref(false);
const grepExcludeEnabled = ref(false);
const hideEmptyFields = ref(false);
const useDisplayFields = ref(true);
const extraHighlightEnabled = ref(true);
const fullRowKeyword = ref('');
const fullRowText = ref('');
const selectedDownload = ref('full');
const downloadFieldScope = ref<'display' | 'all' | 'custom'>('display');
const downloadOptions = [
  { id: 'full', label: '全文下载' },
  { id: 'fast', label: '快速下载（提速100%+）' },
  { id: 'sample', label: '取样下载（前1万条）' },
];
const currentDownloadLabel = computed(() => downloadOptions.find(item => item.id === selectedDownload.value)?.label ?? '全文下载');
const downloadPayload = computed(() => JSON.stringify({
  index_set_id: workspace.indexSetId,
  keyword: keyword.value,
  mode: selectedDownload.value,
  fields: downloadFieldScope.value,
  start_time: toolbar.timeRange.startTime,
  end_time: toolbar.timeRange.endTime,
  workbench: buildDialogPayload(workbenchController.getState(), fieldController.getVisibleFields(), Boolean(fields.error)),
}, null, 2));
const shareUrl = computed(() => {
  const url = new URL(window.location.href);
  const params = new URLSearchParams({
    spaceUid: routeState.spaceUid,
    bizId: routeState.bizId,
    tab: workspace.tab,
    keyword: keyword.value,
    startTime: String(toolbar.timeRange.startTime),
    endTime: String(toolbar.timeRange.endTime),
  });
  url.hash = `/retrieve/${workspace.indexSetId}?${params.toString()}`;
  return url.toString();
});
const searchCostText = computed(() => (search.uiState === 'loading' ? '检索中' : '0 秒钟'));
const displayRecords = computed(() => {
  const records = grepExcludeEnabled.value && extraHighlight.value
    ? search.records.filter(item => !item.log.includes(extraHighlight.value))
    : search.records;
  return logSortDesc.value
    ? [...records].sort((left, right) => right.dtEventTimeStamp - left.dtEventTimeStamp)
    : records;
});
const renderLimit = 500;
const renderedRecords = computed(() => displayRecords.value.slice(0, renderLimit));
const fieldTitle: Record<string, string> = { id: 'ID', dtEventTimeStamp: '时间', log: '日志' };
const originColumns = computed(() => [
  ...(showLineNo.value ? [{ colKey: 'lineNo', title: '#', cell: 'lineNo', width: 64 }] : []),
  ...fieldController.getVisibleFields().filter(field => resultView.value === 'table' || ['id', 'dtEventTimeStamp', 'log'].includes(field.name)).map(field => ({
    colKey: field.name,
    title: fieldTitle[field.name] ?? field.name,
    ...(field.name === 'dtEventTimeStamp' || field.name === 'log' ? { cell: field.name } : {}),
    width: field.name === 'id' ? 80 : field.name === 'dtEventTimeStamp' ? 168 : undefined,
  })),
  { colKey: 'op', title: '操作', cell: 'op', width: 140 },
]);

const highlightLog = (log: string) => highlightParts(log, [
  ...parseSearchChips(keyword.value).map(chip => chip.value),
  extraHighlightEnabled.value ? extraHighlight.value : '',
]);
const highlightFullRow = computed(() => highlightParts(fullRowText.value, [fullRowKeyword.value]));

const toggleExpand = (id: string | number) => {
  const nextId = String(id);
  expandedId.value = expandedId.value === nextId ? null : nextId;
};

const formatTime = (value: number) => {
  const date = new Date(value);
  const pad = (item: number) => String(item).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
};

const parseLogJsonEntries = (log: string) => {
  const jsonStart = log.indexOf('{');
  if (jsonStart < 0) {
    return [];
  }
  try {
    const parsed = JSON.parse(log.slice(jsonStart));
    return Object.entries(parsed).map(([key, value]) => ({
      key: `json.${key}`,
      value: typeof value === 'string' ? value : JSON.stringify(value),
      highlight: true,
    }));
  } catch {
    return [];
  }
};
const kvEntries = (row: LogRecord) => [
  { key: 'id', value: row.id },
  { key: 'dtEventTimeStamp', value: formatTime(row.dtEventTimeStamp) },
  { key: 'log', value: row.log, highlight: true },
  ...parseLogJsonEntries(row.log),
  { key: 'serverIp', value: row.serverIp ?? '' },
  { key: 'path', value: row.path ?? '' },
  { key: 'status', value: row.status == null ? '' : String(row.status) },
].filter(item => item.value !== '');
const openFullRow = (row: LogRecord) => {
  fullRowText.value = JSON.stringify({
    id: row.id,
    dtEventTimeStamp: formatTime(row.dtEventTimeStamp),
    log: row.log,
    serverIp: row.serverIp,
    path: row.path,
    status: row.status,
  }, null, 2);
  fullRowKeyword.value = '';
  fullRowVisible.value = true;
};
const closeFullRow = () => {
  fullRowVisible.value = false;
};
const copyFullRow = () => {
  void navigator.clipboard?.writeText(fullRowText.value);
};
const trendHeight = (count: number) => Math.max(12, Math.round((count / trendMaxCount.value) * 100));
const clusterColumns = [
  { colKey: 'pattern', title: '模式' },
  { colKey: 'count', title: '数量', width: 100 },
  { colKey: 'sample', title: '样例' },
];
const contextColumns = [
  { colKey: 'id', title: 'ID', width: 80 },
  { colKey: 'log', title: '日志' },
];
const contextRows = computed(() => [
  ...context.before,
  ...search.records.filter(item => item.id === context.anchorId),
  ...context.after,
]);

const syncSearch = (next: RetrieveSnapshot) => {
  Object.assign(search, next);
};

const syncFavorite = (next: FavoriteSnapshot) => {
  Object.assign(favorite, next);
};

const syncToolbar = (next: ToolbarSnapshot) => {
  Object.assign(toolbar, next);
};

const syncGrep = (next: GrepSnapshot) => {
  Object.assign(grep, next);
};

const refreshGrep = () => {
  syncGrep(grepController.search(search.records, search.uiState === 'loading'));
};

const submitSearch = async (intent?: SearchIntent) => {
  const timeRange = intent?.timeRange ?? toolbar.timeRange;
  const page = intent?.resetPage ? 1 : search.page;
  workbenchController.dispatch({ type: 'time/change', timeRange });
  syncSearch(await searchController.submit({
    keyword: keyword.value,
    page,
    startTime: timeRange.startTime,
    endTime: timeRange.endTime,
    indexSetId: workspace.indexSetId,
  }));
  remoteTrendBuckets.value = await fetchRetrieveHistogram({ ...routeState, indexSetId: workspace.indexSetId }, timeRange).catch(() => []);
  refreshGrep();
};

const onTab = (tab: RetrieveTab) => {
  workbenchController.dispatch({ type: 'tab/change', tab });
  Object.assign(workspace, workspaceController.setTab(tab));
};

const onChangeIndexSet = async (id: string) => {
  const nextIndex = indexSetController.select(id);
  if (nextIndex.uiState === 'error') {
    return;
  }
  workbenchController.dispatch({ type: 'route/replace', route: { ...routeState, indexSetId: id, tab: workspace.tab } });
  Object.assign(workspace, workspaceController.setIndexSet(id));
  await submitSearch({ resetPage: true, timeRange: toolbar.timeRange });
};

const onToggleField = (name: string, visible: boolean) => {
  Object.assign(fields, fieldController.toggle(name, visible));
};

const onFieldFilter = (value: string) => {
  Object.assign(fields, fieldController.setFilterQuery(value));
};

const refreshFields = async () => {
  const bootstrap = await loadRetrieveBootstrap({ ...routeState, indexSetId: workspace.indexSetId });
  Object.assign(fields, fieldController.replaceFields(bootstrap.fields));
  if (bootstrap.errors.fields) {
    Object.assign(fields, fieldController.setError(bootstrap.errors.fields));
  }
};

const openContext = (id: string) => {
  overlayManager.open({ id: 'retrieve-context', kind: 'drawer', group: 'retrieve-related' });
  Object.assign(context, contextController.open(search.records, id, search.uiState === 'loading'));
  contextVisible.value = true;
};

const closeContext = () => {
  overlayManager.close('retrieve-context');
  contextVisible.value = false;
};

const openRealtime = (row: LogRecord) => {
  overlayManager.open({ id: 'retrieve-realtime', kind: 'drawer', group: 'retrieve-related' });
  realtimeController.start();
  Object.assign(realtime, realtimeController.append(row));
  realtimeVisible.value = true;
};

const stopRealtime = () => {
  Object.assign(realtime, realtimeController.stop());
  overlayManager.close('retrieve-realtime');
  realtimeVisible.value = false;
};

const rememberHistory = () => {
  const value = keyword.value.trim();
  if (!value || searchHistory.value.includes(value)) {
    return;
  }
  searchHistory.value = [value, ...searchHistory.value].slice(0, 8);
};

const onSearch = async () => {
  workbenchController.dispatch({ type: 'query/change', keyword: keyword.value });
  workbenchController.dispatch({ type: 'query/submit' });
  rememberHistory();
  await submitSearch({ resetPage: false, timeRange: toolbar.timeRange });
};

const onApplyHistory = async (value: string) => {
  keyword.value = value;
  await onSearch();
};

const openHistory = () => {
  searchbarRef.value?.openHistory?.();
};

const onToggleFavorite = () => {
  syncToolbar(toolbarController.toggleFavoriteShown());
};

const onChangeTime = async (preset: TimePreset) => {
  const { state, intent } = toolbarController.setTimePreset(preset);
  syncToolbar(state);
  await submitSearch(intent);
};

const onAutoRefresh = (enabled: boolean) => {
  syncToolbar(toolbarController.setAutoRefresh(enabled));
};

const onFavoriteFilter = (value: string) => {
  syncFavorite(favoriteController.setFilterQuery(value));
};

const onCurrentOnly = (value: boolean) => {
  syncFavorite(favoriteController.setCurrentOnly(value));
};

const onApplyFavorite = async (id: string) => {
  const result = favoriteController.apply(id);
  syncFavorite(result.state);
  if (result.keyword) {
    keyword.value = result.keyword;
    rememberHistory();
    await submitSearch({ resetPage: true, timeRange: toolbar.timeRange });
  }
};

const onRemoveFavorite = (id: string) => {
  syncFavorite(favoriteController.remove(id));
};

const onScene = (value: SceneId) => {
  Object.assign(scene, sceneController.setScene(value));
};

const onSceneFilter = (key: string, value: string) => {
  Object.assign(scene, sceneController.setFilter(key, value));
};

const onGrepField = (value: string) => {
  syncGrep(grepController.setField(value));
};

const onGrepPattern = (value: string) => {
  syncGrep(grepController.setPattern(value));
};

const onRunGrep = () => {
  refreshGrep();
};

const openHelp = () => {
  const record = overlayManager.open({ id: 'retrieve-help', kind: 'dialog', group: 'retrieve-help' });
  helpZIndex.value = record.zIndex;
  helpVisible.value = true;
};

const closeHelp = () => {
  overlayManager.close('retrieve-help');
  helpVisible.value = false;
};

const openSave = () => {
  const record = overlayManager.open({ id: 'retrieve-save-favorite', kind: 'dialog', group: 'retrieve-save' });
  saveZIndex.value = record.zIndex;
  saveName.value = keyword.value.trim();
  saveVisible.value = true;
};

const closeSave = () => {
  overlayManager.close('retrieve-save-favorite');
  saveVisible.value = false;
};

const openShare = () => {
  workbenchController.dispatch({ type: 'dialog/open', dialog: 'share' });
  const record = overlayManager.open({ id: 'retrieve-share', kind: 'dialog', group: 'retrieve-toolbar' });
  shareZIndex.value = record.zIndex;
  shareVisible.value = true;
};

const closeShare = () => {
  workbenchController.dispatch({ type: 'dialog/close' });
  overlayManager.close('retrieve-share');
  shareVisible.value = false;
};

const copyShare = () => {
  void navigator.clipboard?.writeText(shareUrl.value);
  closeShare();
};

const openFieldConfig = () => {
  const record = overlayManager.open({ id: 'retrieve-field-config', kind: 'dialog', group: 'retrieve-toolbar' });
  fieldConfigZIndex.value = record.zIndex;
  fieldConfigVisible.value = true;
};

const closeFieldConfig = () => {
  overlayManager.close('retrieve-field-config');
  fieldConfigVisible.value = false;
};

const openGlobalSettings = () => {
  const record = overlayManager.open({ id: 'retrieve-global-settings', kind: 'dialog', group: 'retrieve-toolbar' });
  globalSettingsZIndex.value = record.zIndex;
  globalSettingsVisible.value = true;
};

const closeGlobalSettings = () => {
  overlayManager.close('retrieve-global-settings');
  globalSettingsVisible.value = false;
};

const openDownload = () => {
  workbenchController.dispatch({ type: 'dialog/open', dialog: 'download' });
  const record = overlayManager.open({ id: 'retrieve-download', kind: 'dialog', group: 'retrieve-result' });
  downloadZIndex.value = record.zIndex;
  downloadVisible.value = true;
};

const closeDownload = () => {
  workbenchController.dispatch({ type: 'dialog/close' });
  overlayManager.close('retrieve-download');
  downloadVisible.value = false;
};

const openMore = () => {
  const record = overlayManager.open({ id: 'retrieve-more', kind: 'dialog', group: 'retrieve-toolbar' });
  moreZIndex.value = record.zIndex;
  moreVisible.value = true;
};

const closeMore = () => {
  overlayManager.close('retrieve-more');
  moreVisible.value = false;
};

const openLegacy = () => {
  window.open(`/#/retrieve/${workspace.indexSetId}?spaceUid=${routeState.spaceUid}&bizId=${routeState.bizId}&tab=${workspace.tab}`, '_blank', 'noopener');
  closeMore();
};

const onSaveFavorite = () => {
  const next = favoriteController.save({
    name: saveName.value,
    keyword: keyword.value,
    groupId: 'private',
    indexSetId: workspace.indexSetId,
  });
  syncFavorite(next);
  if (next.uiState !== 'error') {
    closeSave();
  }
};

const onEscape = (event: KeyboardEvent) => {
  if (event.key !== 'Escape') {
    return;
  }
  const closed = overlayManager.handleEscape();
  if (closed?.id === 'retrieve-help') {
    helpVisible.value = false;
  }
  if (closed?.id === 'retrieve-save-favorite') {
    saveVisible.value = false;
  }
  if (closed?.id === 'retrieve-share') {
    shareVisible.value = false;
  }
  if (closed?.id === 'retrieve-field-config') {
    fieldConfigVisible.value = false;
  }
  if (closed?.id === 'retrieve-global-settings') {
    globalSettingsVisible.value = false;
  }
  if (closed?.id === 'retrieve-download') {
    downloadVisible.value = false;
  }
  if (closed?.id === 'retrieve-more') {
    moreVisible.value = false;
  }
  if (closed?.id === 'retrieve-context') {
    contextVisible.value = false;
  }
  if (closed?.id === 'retrieve-realtime') {
    realtimeVisible.value = false;
    realtimeController.stop();
  }
};

onMounted(() => {
  window.addEventListener('keydown', onEscape);
  void (async () => {
    const bootstrap = await loadRetrieveBootstrap(routeState);
    Object.assign(workspace, workspaceController.setIndexSet(bootstrap.route.indexSetId));
    workbenchController.dispatch({ type: 'route/replace', route: bootstrap.route });
    Object.assign(workspace, workspaceController.setTab(bootstrap.route.tab));
    indexSetController.replaceItems(bootstrap.indexSets, bootstrap.route.indexSetId);
    Object.assign(fields, fieldController.replaceFields(bootstrap.fields));
    if (bootstrap.errors.fields) {
      Object.assign(fields, fieldController.setError(bootstrap.errors.fields));
    }
    syncFavorite(favoriteController.replaceGroups(bootstrap.favorites, bootstrap.route.indexSetId));
    bootstrapping.value = false;
    await submitSearch({ resetPage: true, timeRange: toolbar.timeRange });
  })();
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onEscape);
  searchController.dispose();
  toolbarController.dispose();
  overlayManager.close('retrieve-help');
  overlayManager.close('retrieve-save-favorite');
  overlayManager.close('retrieve-share');
  overlayManager.close('retrieve-field-config');
  overlayManager.close('retrieve-global-settings');
  overlayManager.close('retrieve-download');
  overlayManager.close('retrieve-more');
  overlayManager.close('retrieve-context');
  overlayManager.close('retrieve-realtime');
  realtimeController.stop();
});
</script>
