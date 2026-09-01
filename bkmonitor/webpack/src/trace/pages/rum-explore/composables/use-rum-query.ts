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
import { shallowRef } from 'vue';
import type { Ref } from 'vue';

import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import { EMethod, EMode } from '../../../components/retrieval-filter/typing';
import { mergeWhereList } from '../../../components/retrieval-filter/utils';
import { useRumExploreStore } from '../../../store/modules/rum-explore';
import { tryURLDecodeParse } from '../../trace-explore/utils';
import { generateQueryString } from '../services/rum-search';

import type { IWhereItem } from '../../../components/retrieval-filter/typing';
import type { TimeRangeType } from '../../../components/time-range/utils';
import type { IRumCommonParams, IRumFilter, RumMode } from '../typings';

interface IUseRumQueryOptions {
  /** 由快捷筛选等区域附加的查询条件，与检索条件区的条件合并后一起下发 */
  extraFilters: Ref<IRumFilter[]>;
}

const EMPTY_COMMON_PARAMS: IRumCommonParams = {
  app_name: '',
  mode: 'span',
  query_string: '',
  filters: [],
};

/**
 * 检索条件状态与查询触发。
 *
 * commonParams 只在 handleQuery 时整体替换，用户在检索框里编辑条件不会立刻打接口；
 * 同时把可复现的查询状态同步到 URL，方便刷新和分享。
 */
export function useRumQuery({ extraFilters }: IUseRumQueryOptions) {
  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();
  const store = useRumExploreStore();

  const filterMode = shallowRef<EMode>(EMode.ui);
  /** UI 模式条件 */
  const where = shallowRef<IWhereItem[]>([]);
  /** 常驻筛选条件 */
  const commonWhere = shallowRef<IWhereItem[]>([]);
  /** 语句模式条件 */
  const queryString = shallowRef('');
  /** 是否展示常驻筛选入口，默认展开，用户收起后写入 URL 以便复现 */
  const showResidentBtn = shallowRef(true);
  /** 从 URL 带入的收藏 id */
  const urlFavoriteId = shallowRef<null | number>(null);

  const commonParams = shallowRef<IRumCommonParams>({ ...EMPTY_COMMON_PARAMS });
  /** 生成查询字符串中 */
  const generateQueryStringLoading = shallowRef(false);

  function buildFilters(): IRumFilter[] {
    const merged = mergeWhereList(where.value || [], commonWhere.value || []) as IRumFilter[];
    return [...merged, ...extraFilters.value];
  }

  function handleQuery() {
    commonParams.value = {
      app_name: store.appName,
      mode: store.mode,
      query_string: filterMode.value === EMode.queryString ? queryString.value : '',
      filters: filterMode.value === EMode.queryString ? extraFilters.value : buildFilters(),
    };
    setUrlParams();
  }

  function setUrlParams() {
    const query: Record<string, string> = {
      mode: store.mode,
      app_name: store.appName || '',
      timeRange: JSON.stringify(store.timeRange),
      refreshInterval: `${store.refreshInterval}`,
      filterMode: filterMode.value,
      spanType: store.spanType,
      where: JSON.stringify(where.value),
      commonWhere: JSON.stringify(commonWhere.value),
      queryString: queryString.value,
      showResidentBtn: `${showResidentBtn.value}`,
      sortBy: JSON.stringify(store.sortParams),
    };
    if (urlFavoriteId.value) {
      query.favorite_id = `${urlFavoriteId.value}`;
    }
    router.replace({ query }).catch(() => {
      // 相同路由重复跳转会 reject，这里忽略即可
    });
  }

  /** 从 URL 恢复查询状态，在应用列表就绪前调用 */
  function initFromUrl() {
    const query = route.query as Record<string, string>;
    store.init({
      mode: (query.mode as RumMode) || 'span',
      appName: query.app_name || '',
      timeRange: query.timeRange ? tryURLDecodeParse<TimeRangeType>(query.timeRange, undefined) : undefined,
      timezone: window.timezone,
      refreshInterval: query.refreshInterval ? Number(query.refreshInterval) : -1,
      spanType: query.spanType || '',
      sortParams: tryURLDecodeParse<string[]>(query.sortBy, []),
    });
    filterMode.value = (query.filterMode as EMode) || EMode.ui;
    where.value = tryURLDecodeParse<IWhereItem[]>(query.where, []);
    commonWhere.value = tryURLDecodeParse<IWhereItem[]>(query.commonWhere, []);
    queryString.value = query.queryString || '';
    showResidentBtn.value = tryURLDecodeParse<boolean>(query.showResidentBtn, false);
    urlFavoriteId.value = query.favorite_id ? Number(query.favorite_id) : null;
  }

  function clearQuery() {
    where.value = [];
    commonWhere.value = [];
    queryString.value = '';
    handleQuery();
  }

  /**
   * 维度面板 / 表格单元格点击后追加检索条件。
   * @param isMergeSameKey 同字段的等于、不等于条件是否合并，表格里的「添加/排除」需要
   */
  function addCondition(condition: IWhereItem, isMergeSameKey = false) {
    if (filterMode.value === EMode.ui) {
      where.value = mergeWhereList(where.value, [condition], isMergeSameKey);
    } else {
      const isEq = condition.operator === EMethod.eq;
      const preStr = queryString.value ? `${queryString.value} ${isEq ? 'AND' : 'AND NOT'}` : `${isEq ? '' : 'NOT'}`;
      queryString.value = `${preStr} ${condition.key}: "${condition.value?.[0]}"`;
    }
    handleQuery();
  }

  async function generateQueryStringFn() {
    const filters = buildFilters();
    // 无条件时后端会返回空语句，直接短路省掉一次请求与 loading 抖动
    if (filters.length) {
      generateQueryStringLoading.value = true;
      const res = await generateQueryString({
        app_name: store.appName,
        mode: store.mode,
        filters,
      }).catch(() => null);
      generateQueryStringLoading.value = false;
      return res;
    }
    return '';
  }

  async function modeChange(mode: EMode) {
    const str = await generateQueryStringFn();
    filterMode.value = mode;
    queryString.value = str || '';
    handleQuery();
  }

  async function copyWhere() {
    const str = await generateQueryStringFn();
    if (str) {
      copyText(str, msg => {
        Message({
          message: msg,
          theme: 'error',
        });
        return;
      });
      Message({
        message: t('复制成功'),
        theme: 'success',
      });
    }
  }

  function whereChange(val: IWhereItem[]) {
    where.value = val;
    handleQuery();
  }

  /** 常驻筛选入口的展开/收起：只影响展示，不触发查询，但需要同步到 URL 保持复现一致 */
  function showResidentChange(val: boolean) {
    showResidentBtn.value = val;
    setUrlParams();
  }

  /** 语句模式下检索内容变更：与 whereChange 对齐，实时触发查询 */
  function queryStringChange(val: string) {
    queryString.value = val;
    handleQuery();
  }

  return {
    commonParams,
    commonWhere,
    filterMode,
    queryString,
    showResidentBtn,
    urlFavoriteId,
    where,
    generateQueryStringLoading,
    addCondition,
    clearQuery,
    handleQuery,
    initFromUrl,
    setUrlParams,
    copyWhere,
    modeChange,
    generateQueryStringFn,
    whereChange,
    showResidentChange,
    queryStringChange,
  };
}
