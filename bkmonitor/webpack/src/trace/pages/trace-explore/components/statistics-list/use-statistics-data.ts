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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { computed, onBeforeUnmount, reactive, shallowRef, watch } from 'vue';

import { CancelToken } from 'monitor-api/cancel';
import { downloadFile } from 'monitor-common/utils';

import { NULL_VALUE_NAME } from '../../../../components/retrieval-filter/utils';
import {
  type TimeRangeType,
  handleTransformTime,
  handleTransformToTimestamp,
} from '../../../../components/time-range/utils';
import { transformTableDataToCsvStr } from '../../../../plugins/utls/menu';
import { useAppStore } from '../../../../store/modules/app';
import { useTraceExploreStore } from '../../../../store/modules/explore';
import { topKColorList } from '../../utils';
import {
  type IDurationTopKField,
  type StatisticsMode,
  buildDurationTopK,
  EMPTY_DURATION_TOPK_FIELD,
  EMPTY_STATISTICS_INFO,
  EMPTY_TOPK_FIELD,
  formatUnitValue,
  parseRangeText,
  resolveStatisticsMode,
  resolveTopKAlias,
  setTopKData,
  UNIFORM_SERIES_COLOR,
} from './utils';

import type { IStatisticsFieldItem } from '../../../rum-explore/composables/use-field-statistics-popover';
import type { ICommonParams, IStatisticsGraph, IStatisticsInfo, ITopKField } from '../../typing';

/**
 * 统计分析依赖的四个接口。
 * 默认对接 apm_trace，其他检索场景（如 RUM 检索）通过 api prop 注入自己的实现即可复用本组件。
 */
export interface IStatisticsApi {
  downloadTopK: (params: Record<string, unknown>) => Promise<{ data: string; filename: string }>;
  /** 返回 { series }，结构与 field_statistics_graph 协议一致；失败时调用方兜底为 { series: [] } */
  fieldStatisticsGraph: (params: Record<string, unknown>, config?: Record<string, unknown>) => Promise<any>;
  /** 返回 IStatisticsInfo；失败时调用方有各自的兜底值，故此处不收紧类型 */
  fieldStatisticsInfo: (params: Record<string, unknown>, config?: Record<string, unknown>) => Promise<any>;
  fieldsTopK: (params: Record<string, unknown>, config?: Record<string, unknown>) => Promise<ITopKField[]>;
}

/** 数据流需要向外抛出的事件 */
export interface IStatisticsDataCallbacks {
  onShowMore: () => void;
  onSliderShowChange: (show: boolean) => void;
}

/** StatisticsList 中驱动数据流的 props，由组件原样传入 */
export interface IStatisticsDataProps {
  api: IStatisticsApi;
  commonParams: ICommonParams;
  /** 统计分析的字段对象；传数组时展示 Tab，字段名/单位/类型/枚举值/展示模式等均从当前激活字段取值 */
  field: IStatisticsFieldItem | IStatisticsFieldItem[] | null;
  isShow: boolean;
  timeRange: null | TimeRangeType;
}

/** 弹层 TopK 展示条数 */
const TOPK_POPOVER_LIMIT = 5;
/** 侧栏 TopK 每页拉取条数 */
const TOPK_SLIDER_PAGE_SIZE = 100;
/** 数值分布直方图的分桶数 */
const INTEGER_GRAPH_BUCKET_COUNT = 10;
/** 耗时区间直方图的分桶数 */
const DURATION_GRAPH_BUCKET_COUNT = 15;

/**
 * 统计分析数据流：按 mode（duration/integer/text）分发数据链路，统一管理请求取消与 loading 态。
 * 展示层（index.tsx 及各子组件）只消费返回的状态。
 */
export function useStatisticsData(props: IStatisticsDataProps, callbacks: IStatisticsDataCallbacks) {
  const appStore = useAppStore();
  const store = useTraceExploreStore();

  /** 归一化后的字段列表：field 为数组时对应多个 Tab，单字段只有一项 */
  const fieldList = computed<IStatisticsFieldItem[]>(() => {
    if (!props.field) return [];
    return Array.isArray(props.field) ? props.field : [props.field];
  });
  /** 当前激活的字段下标 */
  const activeFieldIndex = shallowRef(0);
  /** 当前激活的字段 */
  const activeField = computed<IStatisticsFieldItem | null>(() => fieldList.value[activeFieldIndex.value] || null);
  /** 展示模式：耗时 / 数值 / 文本，由字段自带的标记决定 */
  const mode = computed<StatisticsMode>(() =>
    resolveStatisticsMode(!!activeField.value?.isDuration, !!activeField.value?.isInteger)
  );
  /** 字段单位，未选字段时兜底空串 */
  const fieldUnit = computed(() => activeField.value?.field_unit || '');
  /** 字段类型，未选字段时兜底 text */
  const fieldType = computed(() => activeField.value?.type || 'text');
  const currentTimeRange = computed<TimeRangeType>(() => props.timeRange || store.timeRange);

  /** 展示的范围文本 */
  const rangeText = shallowRef<TimeRangeType>([]);
  const infoLoading = shallowRef(false);
  const popoverLoading = shallowRef(false);

  /** 当前统计的字段名 */
  const localField = computed(() => activeField.value?.name || '');
  /** 获取字段统计接口次数，用于判断接口取消后的逻辑 */
  const getStatisticsListCount = shallowRef(1);
  /** 获取字段信息接口次数 */
  const getStatisticsInfoCount = shallowRef(1);
  const statisticsInfo = shallowRef<IStatisticsInfo>({ ...EMPTY_STATISTICS_INFO });
  const statisticsList = reactive<ITopKField>({ ...EMPTY_TOPK_FIELD });
  let topKInfoCancelFn: (() => void) | null = null;
  let topKCancelFn: (() => void) | null = null;
  let topKChartCancelFn: (() => void) | null = null;
  const chartData = shallowRef<IStatisticsGraph[]>([]);
  const downloadLoading = shallowRef(false);

  /** '耗时字段' topk列表 */
  const durationTopkList = shallowRef<IDurationTopKField>({ ...EMPTY_DURATION_TOPK_FIELD });

  /** 侧栏（全量 topk）状态 */
  const sliderShow = shallowRef(false);
  const sliderLoading = shallowRef(false);
  const sliderLoadMoreLoading = shallowRef(false);
  const sliderListPage = shallowRef(1);
  const sliderDimensionList = reactive<ITopKField>({ ...EMPTY_TOPK_FIELD });
  /** 侧栏请求序号：切换字段 Tab 或关闭侧栏后递增，让在途的 loadMore 结果直接丢弃 */
  const sliderRequestCount = shallowRef(0);

  watch(
    () => props.isShow,
    async val => {
      if (val) {
        // 每次打开都从第一个字段开始
        activeFieldIndex.value = 0;
        // 上一次侧栏可能未关闭，重新打开时一并复位，避免侧栏残留上一个字段的数据
        resetSliderState();
        await handleShowStatistics();
      } else {
        resetStatisticsState();
      }
    }
  );

  /** 拼接公共查询参数与时间范围 */
  function withTimeParams(params: Record<string, unknown>) {
    const [startTime, endTime] = handleTransformToTimestamp(currentTimeRange.value);
    return { ...props.commonParams, ...params, start_time: startTime, end_time: endTime };
  }

  /** 创建请求取消令牌，并通过 onRegister 登记取消函数，供下次请求前或弹层关闭时取消 */
  function withCancelToken(onRegister: (cancel: () => void) => void) {
    return { cancelToken: new CancelToken(c => onRegister(c)) };
  }

  /** 计算展示别名 */
  function aliasFormatter(value: number | string) {
    return resolveTopKAlias(value as string, {
      fieldName: localField.value,
      optionValues: activeField.value?.option_values,
      unit: fieldUnit.value,
    });
  }

  /** 将接口返回的 topk 数据格式化别名后写入目标容器 */
  function applyTopKData(target: ITopKField, data?: ITopKField) {
    setTopKData(target, {
      ...data,
      list: data?.list.map(item => ({ ...item, value: String(item.value), alias: aliasFormatter(item.value) })) || [],
    });
  }

  /** 弹窗打开：耗时字段与普通字段走两条数据流 */
  async function handleShowStatistics() {
    infoLoading.value = true;
    if (mode.value !== 'duration') {
      rangeText.value = handleTransformTime(currentTimeRange.value);
      getStatisticsList();
      return;
    }
    popoverLoading.value = true;
    const requestId = getStatisticsInfoCount.value + 1;
    await getStatisticsGraphData();
    if (requestId !== getStatisticsInfoCount.value) return;
    popoverLoading.value = false;
    getDurationTopkList();
    rangeText.value = [
      formatUnitValue(durationTopkList.value.min, fieldUnit.value),
      formatUnitValue(durationTopkList.value.max, fieldUnit.value),
    ];
    setTopKData(statisticsList, {
      ...durationTopkList.value,
      list: durationTopkList.value.list.slice(0, TOPK_POPOVER_LIMIT),
    });
  }

  /** 弹窗关闭：取消在途请求并清空统计数据 */
  function resetStatisticsState() {
    // 递增请求计数使在途请求响应后的逻辑短路，再取消请求本身
    getStatisticsListCount.value += 1;
    getStatisticsInfoCount.value += 1;
    topKCancelFn?.();
    topKInfoCancelFn?.();
    topKChartCancelFn?.();
    infoLoading.value = false;
    popoverLoading.value = false;
    setTopKData(statisticsList);
    statisticsInfo.value = { ...EMPTY_STATISTICS_INFO };
    chartData.value = [];
  }

  /** 切换字段 Tab：清空当前统计数据后按新字段重新请求 */
  async function handleTabChange(index: number) {
    if (index === activeFieldIndex.value) return;
    activeFieldIndex.value = index;
    // 侧栏展示的是上一个字段的全量数据，切 Tab 时一并关闭并清空
    resetSliderState();
    resetStatisticsState();
    await handleShowStatistics();
  }

  /** 耗时topK列表逻辑特殊，通过traceFieldStatisticsGraph接口返回的数据由前端生成 */
  function getDurationTopkList() {
    const originValue = (chartData.value[0]?.originValue as [number, string][]) || [];
    const result = buildDurationTopK(originValue, localField.value);

    durationTopkList.value = {
      ...result,
      list: result.list.map(item => ({
        ...item,
        value: String(item.value),
        alias: parseRangeText(item.value, aliasFormatter) as string,
      })),
    };
  }

  /** 获取topk列表 */
  async function getStatisticsList() {
    popoverLoading.value = true;
    getStatisticsListCount.value += 1;
    const count = getStatisticsListCount.value;
    topKCancelFn?.();
    const data: ITopKField[] = await props.api
      .fieldsTopK(
        withTimeParams({ limit: TOPK_POPOVER_LIMIT, fields: [localField.value] }),
        withCancelToken(cancel => {
          topKCancelFn = cancel;
        })
      )
      .catch(() => [{ ...EMPTY_TOPK_FIELD }]);
    if (count !== getStatisticsListCount.value) return;
    applyTopKData(statisticsList, data[0]);
    popoverLoading.value = false;
    await getStatisticsGraphData();
  }

  /** 获取维度信息和维度图表数据 */
  async function getStatisticsGraphData() {
    getStatisticsInfoCount.value += 1;
    const count = getStatisticsInfoCount.value;
    topKInfoCancelFn?.();
    const info: IStatisticsInfo | null = await props.api
      .fieldStatisticsInfo(
        withTimeParams({
          field: {
            field_name: localField.value,
            field_type: fieldType.value,
          },
        }),
        withCancelToken(cancel => {
          topKInfoCancelFn = cancel;
        })
      )
      .catch(() => null);
    /** 如果是取消接口，不进行后续操作 */
    if (count !== getStatisticsInfoCount.value) return;
    /** topk没有数据且keyword类型不请求graph接口 */
    if (!info || info.distinct_count === 0 || (fieldType.value === 'keyword' && !statisticsList.list.length)) {
      infoLoading.value = false;
      return;
    }
    const { min, max, avg, median } = info.value_analysis || {};
    statisticsInfo.value = {
      ...info,
      value_analysis: {
        min: formatUnitValue(min, fieldUnit.value),
        max: formatUnitValue(max, fieldUnit.value),
        avg: formatUnitValue(avg, fieldUnit.value),
        median: formatUnitValue(median, fieldUnit.value),
      },
    };
    const values =
      mode.value === 'text'
        ? statisticsList.list.map(item => item.value)
        : [
            min,
            max,
            statisticsInfo.value.distinct_count,
            mode.value === 'duration' ? DURATION_GRAPH_BUCKET_COUNT : INTEGER_GRAPH_BUCKET_COUNT,
          ];
    topKChartCancelFn?.();
    const data = await props.api
      .fieldStatisticsGraph(
        withTimeParams({
          field: {
            field_name: localField.value,
            field_type: fieldType.value,
            values,
          },
        }),
        withCancelToken(cancel => {
          topKChartCancelFn = cancel;
        })
      )
      .catch(() => ({ series: [] }));

    if (count !== getStatisticsInfoCount.value) return;

    const series = data.series || [];
    chartData.value = series.map(item => {
      if (mode.value !== 'text') {
        return {
          datapoints: item.datapoints.map(point => [point[0], parseRangeText(point[1], aliasFormatter)]),
          originValue: item.datapoints,
          color: UNIFORM_SERIES_COLOR,
          name: localField.value,
        };
      }
      const name = item.dimensions?.[localField.value];
      const index = Math.max(
        0,
        statisticsList.list.findIndex(i => name === i.value)
      );
      return {
        color: topKColorList[index],
        name: parseRangeText(name, aliasFormatter) || NULL_VALUE_NAME,
        ...item,
      };
    });
    infoLoading.value = false;
  }

  onBeforeUnmount(resetStatisticsState);

  /** 展示侧栏 */
  async function showMore() {
    sliderShow.value = true;
    sliderLoading.value = true;
    /** 本次打开侧栏对应的请求序号，期间切 Tab 或重开侧栏后本次的 loading 不再有效 */
    const count = sliderRequestCount.value;
    sliderShowChange();
    callbacks.onShowMore();
    if (mode.value !== 'duration') {
      await loadMore();
    } else {
      setTopKData(sliderDimensionList, durationTopkList.value);
    }
    // 序号已变化说明 loading 已归新一次打开管理，避免旧请求收尾把新一次的加载态清掉
    if (count === sliderRequestCount.value) sliderLoading.value = false;
  }

  /** 加载更多（请求进行中时忽略重复触发） */
  async function loadMore() {
    if (sliderLoadMoreLoading.value) return;
    sliderLoadMoreLoading.value = true;
    const count = sliderRequestCount.value;
    const data = await props.api
      .fieldsTopK(withTimeParams({ limit: sliderListPage.value * TOPK_SLIDER_PAGE_SIZE, fields: [localField.value] }))
      .catch(() => []);
    // 期间切换了字段 Tab 或关闭了侧栏，丢弃过期结果，避免旧字段数据写进侧栏
    if (count !== sliderRequestCount.value) return;
    applyTopKData(sliderDimensionList, data[0]);
    sliderLoadMoreLoading.value = false;
    sliderListPage.value += 1;
  }

  /** 复位侧栏：关闭并清空全量列表，页码回到第一页，同时作废在途的 loadMore 并清掉侧栏加载态 */
  function resetSliderState() {
    sliderRequestCount.value += 1;
    sliderShow.value = false;
    sliderLoading.value = false;
    sliderLoadMoreLoading.value = false;
    sliderListPage.value = 1;
    setTopKData(sliderDimensionList);
  }

  function handleSliderShowChange(show: boolean) {
    if (show) {
      sliderShow.value = true;
    } else {
      resetSliderState();
    }
    sliderShowChange();
  }

  /** 下载：耗时字段本地生成 CSV，其余走接口 */
  async function handleDownload() {
    if (mode.value === 'duration') {
      const csvString = transformTableDataToCsvStr(
        [],
        durationTopkList.value.list.map(item => [
          { value: item.value },
          { value: item.count },
          { value: `${item.proportions}%` },
        ])
      );
      downloadFile(
        csvString,
        'text/csv;charset=utf-8;',
        `topk_${appStore.bizId}_${props.commonParams.app_name}_${localField.value}.csv`
      );
    } else {
      downloadLoading.value = true;
      const data = await props.api
        .downloadTopK(
          withTimeParams({
            limit: sliderShow.value ? sliderDimensionList?.distinct_count : statisticsList?.distinct_count,
            fields: [localField.value],
          })
        )
        .catch(() => null)
        .finally(() => {
          downloadLoading.value = false;
        });
      if (data) {
        downloadFile(data.data, 'txt', data.filename);
      }
    }
  }

  function sliderShowChange() {
    callbacks.onSliderShowChange(sliderShow.value);
  }

  return {
    mode,
    fieldList,
    activeField,
    activeFieldIndex,
    localField,
    rangeText,
    infoLoading,
    popoverLoading,
    statisticsInfo,
    statisticsList,
    chartData,
    downloadLoading,
    sliderShow,
    sliderLoading,
    sliderLoadMoreLoading,
    sliderDimensionList,
    showMore,
    loadMore,
    handleSliderShowChange,
    handleDownload,
    handleTabChange,
  };
}
