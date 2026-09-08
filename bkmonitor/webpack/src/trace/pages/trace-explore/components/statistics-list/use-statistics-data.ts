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

import { computed, reactive, shallowRef, watch } from 'vue';

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
  /** 统计分析的字段对象，字段名/单位/类型/枚举值等均从这里取值 */
  field: IStatisticsFieldItem | null;
  isDuration: boolean;
  isInteger: boolean;
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

  /** 展示模式：耗时 / 数值 / 文本 */
  const mode = computed<StatisticsMode>(() => resolveStatisticsMode(props.isDuration, props.isInteger));
  /** 字段单位，未选字段时兜底空串 */
  const fieldUnit = computed(() => props.field?.field_unit || '');
  /** 字段类型，未选字段时兜底 text */
  const fieldType = computed(() => props.field?.type || 'text');
  const currentTimeRange = computed<TimeRangeType>(() => props.timeRange || store.timeRange);

  /** 展示的范围文本 */
  const rangeText = shallowRef<TimeRangeType>([]);
  const infoLoading = shallowRef(false);
  const popoverLoading = shallowRef(false);

  const localField = shallowRef('');
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

  watch(
    () => props.isShow,
    async val => {
      if (val) {
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
      optionValues: props.field?.option_values,
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
    localField.value = props.field?.name || '';
    if (mode.value !== 'duration') {
      rangeText.value = handleTransformTime(currentTimeRange.value);
      getStatisticsList();
      return;
    }
    popoverLoading.value = true;
    await getStatisticsGraphData();
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
    setTopKData(statisticsList);
    statisticsInfo.value = { ...EMPTY_STATISTICS_INFO };
    chartData.value = [];
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

  /** 展示侧栏 */
  async function showMore() {
    sliderShow.value = true;
    sliderLoading.value = true;
    sliderShowChange();
    callbacks.onShowMore();
    if (mode.value !== 'duration') {
      await loadMore();
    } else {
      setTopKData(sliderDimensionList, durationTopkList.value);
    }
    sliderLoading.value = false;
  }

  /** 加载更多（请求进行中时忽略重复触发） */
  async function loadMore() {
    if (sliderLoadMoreLoading.value) return;
    sliderLoadMoreLoading.value = true;
    const data = await props.api
      .fieldsTopK(withTimeParams({ limit: sliderListPage.value * TOPK_SLIDER_PAGE_SIZE, fields: [localField.value] }))
      .catch(() => []);
    applyTopKData(sliderDimensionList, data[0]);
    sliderLoadMoreLoading.value = false;
    sliderListPage.value += 1;
  }

  function handleSliderShowChange(show: boolean) {
    sliderShow.value = show;
    sliderShowChange();
    if (!show) {
      sliderListPage.value = 1;
      setTopKData(sliderDimensionList);
    }
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
  };
}
