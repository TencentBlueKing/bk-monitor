/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { computed, nextTick, onMounted, onScopeDispose, shallowRef, watch } from 'vue';

import { type DateValue, DateRange } from '@blueking/date-picker';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import { getApplications, getFavorite, getLabelKeys, getLabelValues, getServiceDetail } from '../services/profiling';
import {
  buildProfileQuery,
  clampSelection,
  createQueryState,
  restoreQueryState,
  restoreSelection,
} from '../utils/query';
import { type IFilterField, type IGetValueFnParams, EFieldType, EMethod } from '@/components/retrieval-filter/typing';
import { getDefaultTimezone, updateTimezone } from '@/i18n/dayjs';
import { useAppStore } from '@/store/modules/app';

import type {
  Application,
  CompareMode,
  ProfileQuery,
  ProfileViewState,
  ProfilingFavorite,
  QuerySide,
  QueryState,
  SelectionRange,
  ServiceDetail,
} from '../types';

export type UseProfilingQueryReturn = ReturnType<typeof useProfilingQuery>;

export function useProfilingQuery() {
  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();
  const app = useAppStore();
  // state 保存正在编辑的条件；图表只消费 submitted，避免输入过程触发请求。
  const state = shallowRef(createQueryState(getDefaultTimezone()));
  const submitted = shallowRef<null | ProfileQuery>(null);
  const applications = shallowRef<Application[]>([]);
  const detail = shallowRef<null | ServiceDetail>(null);
  const fields = shallowRef<IFilterField[]>([]);
  const loading = shallowRef(false);
  const error = shallowRef('');
  const labelError = shallowRef('');
  const initialFavorite = shallowRef<null | ProfilingFavorite>(null);
  const revision = shallowRef(0);
  const refreshBusy = shallowRef(false);
  const bounds = computed(() => state.value.resolvedTimeRange);
  const active = computed(() => state.value.view.tab === 'application');
  let controller: AbortController;
  let labelController: AbortController;
  let valueController = new AbortController();
  let timer: ReturnType<typeof setTimeout>;
  let disposed = false;
  let writingQuery = '';
  let initialized = false;
  let restoring = 0;
  let filterQueryPending = false;
  const pendingWrites = new Set<string>();
  const valueCache = new Map<string, Promise<string[]>>();

  const serviceOptions = applications;

  function patch(value: Partial<QueryState>) {
    state.value = {
      ...state.value,
      // 改变全局时间后旧边界不再有效，URL 应使用新时间；单纯切视图沿用查询现场。
      ...(value.timeRange || value.timezone ? { resolvedTimeRange: null } : {}),
      ...value,
    };
  }

  function patchView(value: Partial<ProfileViewState>) {
    patch({ view: { ...state.value.view, ...value } });
  }

  function changeFilters(
    value: Partial<Pick<QueryState, 'commonWhere' | 'comparisonCommonWhere' | 'comparisonWhere' | 'where'>>
  ) {
    if (
      Object.entries(value).every(
        ([key, conditions]) => JSON.stringify(state.value[key]) === JSON.stringify(conditions)
      )
    )
      return;
    patch(value);
    if (filterQueryPending) return;
    filterQueryPending = true;
    // 常驻条件转回搜索框会连续发出两次变更；等本轮状态更新完成后只查询一次。
    nextTick(() => {
      if (filterQueryPending && !disposed) executeQuery();
    });
  }

  function resolveRange(): SelectionRange {
    const range = new DateRange(state.value.timeRange as DateValue, 'YYYY-MM-DD HH:mm:ssZZ', state.value.timezone);
    const start = range.startDate?.valueOf();
    const end = range.endDate?.valueOf();
    if (!range.isValidate || !Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      throw new Error('请选择有效的时间范围');
    }
    return [start, end];
  }

  function syncUrl() {
    if (!initialized || restoring || loading.value || disposed) return;
    try {
      const range = bounds.value || resolveRange();
      // 收藏读取 state 中的原始时间表达式；只有 URL 快照固定为绝对时间。
      const snapshot = JSON.stringify({ ...state.value, timeRange: range, resolvedTimeRange: range });
      if (snapshot === route.query.profiling || snapshot === writingQuery) return;
      writingQuery = snapshot;
      pendingWrites.add(snapshot);
      router
        .replace({ query: { ...route.query, profiling: snapshot } })
        .catch(() => {
          if (writingQuery === snapshot) writingQuery = '';
        })
        .finally(async () => {
          await nextTick();
          pendingWrites.delete(snapshot);
        });
    } catch {
      // 输入中的无效时间不覆盖上一个可用链接，执行查询时会展示具体错误。
    }
  }

  async function loadLabels() {
    // 标签值缓存只属于当前查询；更新字段时同时取消旧值请求，避免跨服务复用。
    labelController?.abort();
    valueController.abort();
    valueController = new AbortController();
    valueCache.clear();
    labelController = new AbortController();
    const current = labelController;
    labelError.value = '';
    if (!submitted.value) return;
    try {
      const keys = await getLabelKeys(submitted.value, current.signal);
      if (current.signal.aborted) return;
      fields.value = keys
        .filter(key => !['start', 'end', '__proto__', 'constructor', 'prototype'].includes(key))
        .map(key => ({
          name: key,
          alias: key,
          type: EFieldType.keyword,
          isEnableOptions: true,
          methods: [{ value: EMethod.eq, alias: '=' }],
        }));
    } catch (e) {
      if (!current.signal.aborted) labelError.value = t('标签加载失败，请重试');
    }
  }

  function executeQuery(refreshLabels = false, refreshTrends = true) {
    // 搜索按钮/快捷键已提交时，取消本轮条件变更排队的查询。
    filterQueryPending = false;
    if (!state.value.appName || !state.value.serviceName || !state.value.dataType || loading.value) return;
    try {
      // 框选沿用已提交的绝对时间边界；重新解析 now 会让两侧选区和趋势发生漂移。
      const range = !refreshTrends && bounds.value ? bounds.value : resolveRange();
      const next = {
        ...state.value,
        baselineRange: restoreSelection(state.value, state.value.baselineRange, range),
        comparisonRange: restoreSelection(state.value, state.value.comparisonRange, range),
        resolvedTimeRange: range,
      };
      if (next.mode === 'time') {
        // 首次进入或重置某侧选区时，默认将全局时间平分为查询项和对比项。
        const middle = Math.floor((range[0] + range[1]) / 2);
        next.baselineRange ||= [range[0], middle];
        next.comparisonRange ||= [middle, range[1]];
      }
      const query = buildProfileQuery(next, Number(app.bizId), range);
      state.value = next;
      submitted.value = query;
      // 参数未变的手动/定时刷新也需要重取趋势；框选不会递增此版本号。
      if (refreshTrends) revision.value += 1;
      error.value = '';
      syncUrl();
      if (refreshLabels || !fields.value.length) loadLabels();
    } catch (e) {
      submitted.value = null;
      error.value = t((e as Error).message);
    }
  }

  async function loadService() {
    controller?.abort();
    labelController?.abort();
    valueController.abort();
    controller = new AbortController();
    const current = controller;
    submitted.value = null;
    detail.value = null;
    fields.value = [];
    error.value = '';
    loading.value = false;
    if (!state.value.appName || !state.value.serviceName) return;
    loading.value = true;
    try {
      const [start, end] = resolveRange();
      const result = await getServiceDetail(
        {
          bk_biz_id: Number(app.bizId),
          app_name: state.value.appName,
          service_name: state.value.serviceName,
          start_time: Math.floor(start / 1000),
          end_time: Math.floor(end / 1000),
        },
        current.signal
      );
      if (current.signal.aborted) return;
      detail.value = result;
      const selectedType = result.data_types.find(item => item.key === state.value.dataType);
      const dataType = selectedType || result.data_types[0];
      if (dataType) {
        patch({
          dataType: dataType.key,
          aggregation: selectedType ? state.value.aggregation : dataType.default_agg_method || 'SUM',
        });
      }
      loading.value = false;
      if (dataType) executeQuery(true);
    } catch (e) {
      if (!current.signal.aborted) error.value = (e as Error)?.message || t('应用服务加载失败，请重试');
    } finally {
      if (!current.signal.aborted) loading.value = false;
    }
  }

  async function initialize() {
    initialized = false;
    writingQuery = '';
    controller?.abort();
    controller = new AbortController();
    const current = controller;
    loading.value = true;
    error.value = '';
    try {
      let next = createQueryState(getDefaultTimezone());
      // URL 中的完整查询优先于收藏 ID，保证用户修改收藏后的分享链接可准确恢复。
      if (typeof route.query.profiling === 'string') {
        next = restoreQueryState(JSON.parse(route.query.profiling), next.timezone);
      } else if (route.query.favorite_id) {
        const favorite = await getFavorite(Number(route.query.favorite_id), current.signal);
        if (current.signal.aborted) return;
        if (!favorite.config?.profiling) throw new Error(t('收藏配置无效'));
        initialFavorite.value = favorite;
        next = restoreQueryState(favorite.config.profiling, next.timezone);
      }
      const result = await getApplications(Number(app.bizId), current.signal);
      if (current.signal.aborted) return;
      applications.value = result;
      if (!next.appName) {
        const first = result.find(item => item.services.length);
        next.appName = first?.app_name || '';
        next.serviceName = first?.services[0]?.name || '';
      }
      state.value = next;
      updateTimezone(next.timezone);
      if (
        next.appName &&
        !result.some(item => item.app_name === next.appName && item.services.some(s => s.name === next.serviceName))
      ) {
        throw new Error(t('选择的应用服务不存在，请重新选择'));
      }
      loading.value = false;
      await loadService();
      initialized = true;
      syncUrl();
    } catch (e) {
      if (!current.signal.aborted) {
        initialized = true;
        error.value = (e as Error)?.message || t('应用服务加载失败，请重试');
        loading.value = false;
      }
    }
  }

  function selectService(value: string[]) {
    // 忽略初始化空值和组件重复回填，避免取消初始化请求或清空已有筛选条件。
    if (value.length !== 2 || !value[0] || !value[1]) return;
    if (value[0] === state.value.appName && value[1] === state.value.serviceName) return;
    patch({
      appName: value[0],
      serviceName: value[1],
      dataType: '',
      where: [],
      commonWhere: [],
      comparisonWhere: [],
      comparisonCommonWhere: [],
      baselineRange: null,
      comparisonRange: null,
    });
    loadService();
  }

  function selectDataType(value: string) {
    const item = detail.value?.data_types.find(item => item.key === value);
    if (!item) return;
    patch({ dataType: value, aggregation: item.default_agg_method || 'SUM' });
    executeQuery(true);
  }

  function changeMode(mode: CompareMode) {
    patch({ mode, baselineRange: null, comparisonRange: null });
    if (mode !== 'none' && state.value.view.graphMode === 'callgraph') patchView({ graphMode: 'combined' });
    executeQuery();
  }

  function selectRange(side: QuerySide, range: null | SelectionRange) {
    if (!bounds.value) return;
    patch({
      [side === 'baseline' ? 'baselineRange' : 'comparisonRange']: range && clampSelection(range, bounds.value),
    });
    executeQuery(false, false);
  }

  async function applyState(value: unknown) {
    restoring += 1;
    try {
      state.value = restoreQueryState(value, getDefaultTimezone());
      updateTimezone(state.value.timezone);
      await loadService();
    } finally {
      restoring -= 1;
      syncUrl();
    }
  }

  async function getFieldValues(params: IGetValueFnParams) {
    const field = params.fields?.[0];
    if (!submitted.value || !field) return { count: 0, list: [] };
    const search = String(params.where?.find(item => item.key === field)?.value?.[0] ?? '').toLowerCase();
    const current = valueController;
    const limit = Math.max(params.limit || 50, 50);
    const key = `${field}:${limit}`;
    let request = valueCache.get(key);
    if (!request) {
      // 缓存 Promise 合并两侧筛选器的并发请求，搜索词在返回列表上本地过滤。
      request = getLabelValues(submitted.value, field, limit, valueController.signal);
      valueCache.set(key, request);
    }
    try {
      const values = await request;
      if (current.signal.aborted) return { count: 0, list: [] };
      const matched = values.filter(value => !search || value.toLowerCase().includes(search));
      return {
        count: values.length === limit ? limit + 1 : matched.length,
        list: matched.map(value => ({ id: value, name: value })),
      };
    } catch {
      if (!current.signal.aborted) {
        valueCache.delete(key);
        labelError.value = t('标签值加载失败，请重试');
      }
      return { count: 0, list: [] };
    }
  }

  function scheduleRefresh() {
    clearTimeout(timer);
    if (disposed || !active.value || state.value.refreshInterval < 60000) return;
    timer = setTimeout(() => {
      if (!document.hidden && !refreshBusy.value) executeQuery();
      scheduleRefresh();
    }, state.value.refreshInterval);
  }

  // 展示状态与未提交的筛选条件同样可分享，但不驱动数据请求。
  watch([state, loading], syncUrl, { flush: 'post' });
  watch(() => [state.value.refreshInterval, active.value], scheduleRefresh);
  watch(
    () => app.bizId,
    () => {
      submitted.value = null;
      initialFavorite.value = null;
      initialize();
    }
  );
  watch([() => route.query.profiling, () => route.query.favorite_id], ([value]) => {
    if (!initialized || pendingWrites.has(value as string) || value === writingQuery) return;
    writingQuery = '';
    if (typeof value !== 'string') {
      initialize();
      return;
    }
    try {
      applyState(JSON.parse(value)).catch(() => {
        error.value = t('查询参数无效');
      });
    } catch {
      error.value = t('查询参数无效');
    }
  });
  onMounted(initialize);
  onScopeDispose(() => {
    disposed = true;
    clearTimeout(timer);
    controller?.abort();
    labelController?.abort();
    valueController.abort();
  });

  return {
    state,
    active,
    submitted,
    applications,
    serviceOptions,
    detail,
    fields,
    loading,
    error,
    labelError,
    initialFavorite,
    revision,
    refreshBusy,
    bounds,
    patch,
    patchView,
    changeFilters,
    executeQuery,
    initialize,
    loadLabels,
    selectService,
    selectDataType,
    changeMode,
    selectRange,
    applyState,
    getFieldValues,
  };
}
