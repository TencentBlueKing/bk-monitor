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
import { intTimestampStr } from '../../../components/time-range/utils';
import { useRumExploreStore } from '../../../store/modules/rum-explore';
import { tryURLDecode, tryURLDecodeParse } from '../../trace-explore/utils';
import { RumModeEnum } from '../constants';
import { generateQueryString } from '../services/rum-search';

import type { IWhereItem } from '../../../components/retrieval-filter/typing';
import type { TimeRangeType } from '../../../components/time-range/utils';
import type { IRumCommonParams, IRumFilter, RumModeType } from '../typings';

interface IUseRumQueryOptions {
  /** 由快捷筛选等区域附加的查询条件，与检索条件区的条件合并后一起下发 */
  extraFilters: Ref<IRumFilter[]>;
}

const EMPTY_COMMON_PARAMS: IRumCommonParams = {
  app_name: '',
  mode: RumModeEnum.SPAN,
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

  /**
   * 取当前 URL 上的详情抽屉参数：详情打开期间原样带上，避免检索态同步把详情缓存冲掉；
   * 详情关闭后不再携带，让 URL 自然清掉残留的 false / null（关闭当次由页面显式传入覆盖）。
   */
  function pickDetailQuery(): Record<string, string> {
    const { detailShow, detailContext } = route.query;
    if (detailShow !== 'true' || typeof detailContext !== 'string') return {};
    return { detailShow, detailContext };
  }

  /** 当前可复现的查询状态对应的 URL 参数，setUrlParams 与新开页共用，避免两边字段不同步 */
  function buildUrlQuery(params?: Record<string, string>): Record<string, string> {
    const query: Record<string, string> = {
      mode: store.mode,
      app_name: encodeURIComponent(store.appName || ''),
      // 时间范围按分享组件的通用约定拆成 from / to（裸值交给 router 编码），供临时分享等通用组件直接读取
      from: `${store.timeRange[0] ?? ''}`,
      to: `${store.timeRange[1] ?? ''}`,
      refreshInterval: `${store.refreshInterval}`,
      filterMode: filterMode.value,
      spanType: store.spanType,
      timezone: encodeURIComponent(store.timezone),
      where: encodeURIComponent(JSON.stringify(where.value)),
      commonWhere: encodeURIComponent(JSON.stringify(commonWhere.value)),
      queryString: encodeURIComponent(queryString.value),
      showResidentBtn: `${showResidentBtn.value}`,
      // 记录用户意图而非当前生效值，避免把回落的 default_sort 固化成显式排序
      sortBy: encodeURIComponent(JSON.stringify(store.userSort)),
      ...pickDetailQuery(),
      ...(params || {}),
    };
    if (urlFavoriteId.value) {
      query.favorite_id = `${urlFavoriteId.value}`;
    }
    return query;
  }

  function setUrlParams(params?: Record<string, string>) {
    router.replace({ query: buildUrlQuery(params) }).catch(() => {
      // 相同路由重复跳转会 reject，这里忽略即可
    });
  }

  /**
   * 从 URL 还原时间范围：优先早期把整个数组存在 timeRange 里的旧参数，没有时再用分享组件通用的 from / to
   * （裸值，数字串按毫秒时间戳还原，其余按相对表达式 / 日期串原样透传）。
   * 旧分享 token 会同时带上页面真实的 timeRange 与弹窗按缺省近 1 小时写入的 from / to，此时 timeRange 才是原页面范围。
   */
  function parseUrlTimeRange(query: Record<string, string>): TimeRangeType | undefined {
    const legacy = tryURLDecodeParse<TimeRangeType>(query.timeRange, undefined);
    if (Array.isArray(legacy) && legacy[0] && legacy[1]) return legacy;
    // from / to 是通用约定，重复参数（?from=a&from=b）会解析成数组，非字符串一律忽略
    const { from, to } = query as Record<string, unknown>;
    if (typeof from === 'string' && typeof to === 'string' && from && to) {
      return [intTimestampStr(from) ?? from, intTimestampStr(to) ?? to];
    }
    return undefined;
  }

  /** 从 URL 恢复查询状态，在应用列表就绪前调用 */
  function initFromUrl() {
    const query = route.query as Record<string, string>;
    const urlSort = tryURLDecodeParse<null | string[]>(query.sortBy, null);
    store.init({
      mode: (query.mode as RumModeType) || RumModeEnum.SPAN,
      appName: tryURLDecode(query.app_name),
      timeRange: parseUrlTimeRange(query),
      timezone: tryURLDecode(query.timezone) || window.timezone,
      refreshInterval: query.refreshInterval ? Number(query.refreshInterval) : -1,
      spanType: query.spanType || '',
      // 三态透传：null 待视图配置就绪后回落 default_sort，[] 表示明确不排序
      sortParams: urlSort,
    });
    filterMode.value = (query.filterMode as EMode) || EMode.ui;
    where.value = tryURLDecodeParse<IWhereItem[]>(query.where, []);
    commonWhere.value = tryURLDecodeParse<IWhereItem[]>(query.commonWhere, []);
    queryString.value = tryURLDecode(query.queryString);
    if (typeof query.showResidentBtn === 'undefined') {
      showResidentBtn.value = true;
    } else {
      showResidentBtn.value = tryURLDecodeParse<boolean>(query.showResidentBtn, false);
    }
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
      const nextWhere =
        condition.value?.[0] === 'undefined'
          ? mergeWhereList(
              where.value,
              [
                {
                  ...condition,
                  value: [],
                  operator: condition.operator === 'equal' ? 'not exists' : 'exists',
                },
              ],
              isMergeSameKey
            )
          : mergeWhereList(where.value, [condition], isMergeSameKey);
      // 条件已存在（同字段同操作符且值已包含）时 where 无变化，跳过检索避免重复请求
      if (JSON.stringify(nextWhere) === JSON.stringify(where.value)) return;
      where.value = nextWhere;
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
    buildUrlQuery,
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
