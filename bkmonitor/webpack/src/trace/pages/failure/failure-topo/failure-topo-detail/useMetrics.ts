/* eslint-disable @typescript-eslint/naming-convention */
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
import { type Ref, computed, ref as deepRef, inject, onUnmounted, shallowRef, watch } from 'vue';

import { incidentEventsSearch, incidentMetricsSearch } from 'monitor-api/modules/incident';
import { echarts } from 'monitor-ui/monitor-echarts/types/monitor-echarts';
import { debounce } from 'throttle-debounce';
import { useI18n } from 'vue-i18n';

import { handleEndTime, scaleArrayToRange } from '../utils';

import type { IncidentDetailData } from '../types';
import type {
  EventColumnConfig,
  EventColumnItem,
  EventConfig,
  EventStatistics,
  IMetricItem,
  MetricEvent,
} from '../types';

// 定义固定的图表连接组ID
const CONNECT_GROUP_ID = 'incident-metric-chart-group';

// 统一 ECharts 实例类型，避免报错
type ChartInstance = {
  // 对当前图表派发动作（这里主要用于 dataZoom 联动）
  dispatchAction?: (payload: any) => void;
  getId?: () => string;
  // 联动组标识：`echarts.connect(groupId)` 会让同组图表联动
  group?: string;
  // 实例 id
  id?: string;
  // 实例是否已销毁
  isDisposed?: () => boolean;
};

export default function useMetrics(
  commonParams: Ref<any>,
  metricType: Ref<string>,
  refreshTime: Ref<number>,
  showServiceOverview: Ref<boolean>,
  getMetricsDataLength: (length: number) => void,
  edgeMetricData: Ref<Array<any>> // 边的指标数据
) {
  const { t } = useI18n();
  const loading = deepRef<boolean>(false);
  // 指标数据获取异常处理
  const exceptionData = deepRef({
    showException: false,
    type: '',
    msg: '',
  });
  // 指标数据
  const metricsData = shallowRef<IMetricItem[]>([]);
  // 图表实例引用集合
  const chartInstances = deepRef<ChartInstance[]>([]);
  // 事件接口是否加载完毕
  const isEventsLoaded = deepRef(false);
  // 事件分析弹窗列配置
  const eventColumns = deepRef<EventColumnConfig[]>([]);
  // 事件分析散点图数据
  const allEventsData = deepRef<MetricEvent[]>([]);
  // 筛选\转换后的散点图数据
  const eventsData = deepRef<any[]>([]);
  // 当前勾选的事件分析弹窗数据
  const eventConfig = deepRef<EventConfig>({
    event_source: {
      is_select_all: true,
      list: [],
    },
    event_level: {
      is_select_all: true,
      list: [],
    },
  });
  // 使用 ref 存储定时器，以便在 watch 中访问
  const refreshTimeout = deepRef<NodeJS.Timeout | null>(null);
  // 是否禁用事件分析弹窗相关功能
  const disableEventAnalysis = deepRef(false);
  // 故障结束时间戳
  const endTime = shallowRef(null);
  const metricInterval = shallowRef(0);
  const eventInterval = shallowRef(0);
  const incidentDetail = inject<Ref<IncidentDetailData>>('incidentDetail');
  const incidentDetailData: Ref<IncidentDetailData> = computed(() => {
    return incidentDetail.value;
  });
  // 图表联动状态（是否已对 `CONNECT_GROUP_ID` 调用过 connect）
  const isChartsConnected = deepRef(false);

  /**
   * 规范化 `chartInstances`（去重 + 过滤已销毁实例）。
   * 用“实例 id”去重，避免直接 `Set.has(chart)` 触发 TS 名义类型不兼容
   */
  const normalizeChartInstances = () => {
    const uniqueId = new Set<string>();

    chartInstances.value = chartInstances.value.filter(chart => {
      if (!chart) return false;

      // echarts 实例在 dispose 后通常会提供 isDisposed()，这里做兼容判断
      const isDisposed = (chart as any).isDisposed?.() === true;
      if (isDisposed) return false;

      const id = String((chart as any).id ?? (chart as any).getId?.() ?? '');
      if (!id) return true; // 极端兜底：拿不到 id 时不参与去重

      if (uniqueId.has(id)) return false;
      uniqueId.add(id);
      return true;
    });
  };

  /** 异常情况赋值 */
  const handleExceptionData = (type: string, msg: string) => {
    exceptionData.value.showException = true;
    exceptionData.value.type = type;
    exceptionData.value.msg = msg;
  };

  /** 清除定时器 */
  const clearRefreshTimer = () => {
    if (refreshTimeout.value) {
      clearTimeout(refreshTimeout.value);
      refreshTimeout.value = null;
    }
  };

  /** 启动/刷新定时器 */
  const startRefreshTimer = () => {
    clearRefreshTimer();

    // 只有在侧滑菜单打开且需要定时刷新时才启动新定时器
    if (showServiceOverview.value && refreshTime.value !== -1) {
      refreshTimeout.value = setTimeout(() => {
        getMetricsData();
        getEventsData();
      }, refreshTime.value);
    }
  };

  watch(refreshTime, startRefreshTimer);

  onUnmounted(() => {
    clearRefreshTimer();
    // 组件卸载时断开联动组，避免残留连接影响其它页面/实例
    echarts.disconnect(CONNECT_GROUP_ID);
    isChartsConnected.value = false;
    chartInstances.value = [];
  });

  /** 获取指标数据 */
  const getMetricsData = async () => {
    try {
      loading.value = true;
      clearRefreshTimer();

      const { begin_time, end_time } = incidentDetailData.value;
      // 获取最新的故障结束时间戳
      endTime.value = handleEndTime(begin_time, end_time);

      // 根据最新的故障结束时间戳，获取指标接口、事件接口的 interval
      const totalMinutes = (endTime.value - begin_time) / 60;
      eventInterval.value = Math.ceil(totalMinutes / 5) * 60;
      metricInterval.value = Math.ceil(totalMinutes / 150) * 60;

      // 如果是边概览，直接使用边的指标数据，无需请求接口
      if (metricType.value !== 'node') {
        if (edgeMetricData.value.length === 0) {
          handleExceptionData('noData', t('暂无数据'));
          return;
        }
        exceptionData.value.showException = false;
        // 对边的指标数据进行结构调整，保证节点和边的指标数据结构一致
        const trasformedEdgeData = edgeMetricData.value.map((event: any) => {
          return {
            display_by_dimensions: false,
            metric_alias: event.event_name,
            metric_name: event.event_name,
            metric_type: 'edge',
            time_series: {
              default: {
                datapoints: event.time_series,
                unit: '',
              },
            },
          };
        });
        metricsData.value = trasformedEdgeData;
        return;
      }

      const res = await incidentMetricsSearch({
        ...commonParams.value,
        start_time: begin_time - eventInterval.value,
        end_time: endTime.value,
        interval: metricInterval.value,
        metric_type: metricType.value,
      });

      if (Object.values(res.metrics).length === 0) {
        handleExceptionData('noData', t('暂无数据'));
      } else {
        exceptionData.value.showException = false;
      }
      metricsData.value = Object.values(res.metrics);
    } catch (err: any) {
      console.error('获取指标数据失败:', err);
      handleExceptionData('error', err.message || '');
      metricsData.value = [];
    } finally {
      // 获取指标数据数量
      getMetricsDataLength(metricsData.value.length);

      startRefreshTimer();

      setTimeout(() => {
        loading.value = false;
      }, 300);
    }
  };

  /** 图表初始化回调：添加图表实例到集合 */
  const handleChartInit = (chart: ChartInstance) => {
    if (!chart) return;
    chartInstances.value.push(chart);
    // `MetricChart` 内部可能在数据更新时重复触发 init，去重一下
    normalizeChartInstances();
    connectCharts();
  };

  /**
   * 图表销毁回调：从集合中移除图表实例，避免联动还指向旧实例。
   */
  const handleChartDestroy = (chart: ChartInstance) => {
    chartInstances.value = chartInstances.value.filter(instance => instance !== chart);
    normalizeChartInstances();
    connectCharts();
  };

  /**
   * 同步所有图表的 dataZoom 范围。
   * - 只需要对其中一个（primary）dispatchAction，其它图表会自动联动
   * - 这样可以显著减少重复派发，避免卡顿
   */
  const syncChartsDataZoom = (range: { endValue: number; startValue: number }) => {
    if (typeof range?.startValue === 'undefined' || typeof range.endValue === 'undefined') return;
    // 去重
    normalizeChartInstances();

    const primary = chartInstances.value[0];
    if (!primary) return;

    primary.dispatchAction?.({
      type: 'dataZoom',
      // 明确索引，避免未来 dataZoom 数组扩展后派发不到正确组件
      dataZoomIndex: 0,
      startValue: range.startValue,
      endValue: range.endValue,
      // 避免 primary 图表反复触发 `dataZoom` 事件链
      silent: true,
    });

    //  tooltip 状态清理。修复拖拽顶部滑块后，第一个图表 tooltip 不出现的问题。
    try {
      primary.dispatchAction?.({ type: 'hideTip', silent: true });
      (primary as any).resize?.();
    } catch (e) {
      console.warn('reset primary tooltip state failed:', e);
    }
  };

  /**
   * 连接所有图表实现联动
   */
  const connectCharts = () => {
    normalizeChartInstances();

    const len = chartInstances.value.length;
    // 图表实例数量不足 2 个时无需联动：如果之前连过，断开即可
    if (len <= 1) {
      if (isChartsConnected.value) {
        echarts.disconnect(CONNECT_GROUP_ID);
        isChartsConnected.value = false;
      }
      return;
    }

    // 2个以上图表：确保全部加入同一 group
    chartInstances.value.forEach(chart => {
      chart.group = CONNECT_GROUP_ID;
    });

    // connect 可重复调用（幂等），但这里用状态避免高频重复
    if (!isChartsConnected.value) {
      echarts.connect(CONNECT_GROUP_ID);
      isChartsConnected.value = true;
    } else {
      // 已连接但实例集合可能变化（新增/销毁），再 connect 一次确保新实例生效
      echarts.connect(CONNECT_GROUP_ID);
    }
  };

  /** 转换接口返回的事件分析弹窗数据为列配置 */
  const transformEventColumns = (statistics: EventStatistics): EventColumnConfig[] => {
    // 定义固定列配置
    const fixedColumns: Pick<EventColumnConfig, 'alias' | 'name'>[] = [
      { name: 'event_source', alias: t('事件来源') },
      { name: 'event_level', alias: t('事件等级') },
    ];

    return fixedColumns.map(column => {
      // 获取当前列的统计数据
      const columnData = statistics[column.name as keyof EventStatistics];
      // 转换统计对象为列表项格式
      const list: EventColumnItem[] = Object.entries(columnData || {}).map(([value, count]) => ({
        value,
        alias: value,
        count,
      }));

      return {
        ...column,
        list,
      };
    });
  };

  /**
   * 更新当前勾选的事件分析数据
   * @param newEventColumns - 最新的事件分析列表配置
   * @param localEventColumns - 缓存的事件分析列表配置
   */
  const updateEventConfig = (newEventColumns: EventColumnConfig[], localEventColumns: EventColumnConfig[]) => {
    for (const column of newEventColumns) {
      const columnName = column.name;
      const globalList = column.list.map(item => item.value);

      // 获取对应类型的本地列表
      const localColumn = localEventColumns.find(c => c.name === columnName);
      const localList = localColumn?.list?.map(item => item.value) || [];

      // 获取当前配置项
      const configItem = eventConfig.value[columnName];

      // 找出全局列表有但本地列表没有的项
      const missingValues = globalList.filter(value => !localList.includes(value) && !configItem.list.includes(value));
      // 更新配置项,将缺少的项添加到配置列表中
      configItem.list = [...configItem.list, ...missingValues];
      configItem.is_select_all = configItem.list.length === globalList.length;
    }
  };

  /**
   * 更新散点图数据
   * @param eventConfig - 事件分析弹窗勾选数据
   * @return 符合 ECharts 散点图的标准格式
   */
  const transformEventData = (eventConfig: EventConfig): any => {
    const events = allEventsData.value;
    const eventSourceList = eventConfig.event_source.list;
    const eventLevelList = eventConfig.event_level.list;

    let res = [];
    for (const event of events) {
      if (eventSourceList.includes(event.event_source) && eventLevelList.includes(event.event_level)) {
        const filtered = event.series[0].datapoints.filter(item => item[1]);
        res = res.concat(filtered);
      }
    }

    // 合并具有相同时间戳的值
    const valueMap = new Map<number, number>();
    for (const point of res) {
      const [timestamp, value] = point;
      const currentValue = valueMap.get(timestamp) || 0;
      valueMap.set(timestamp, currentValue + value);
    }

    const aggregatedData = Array.from(valueMap);
    // 按时间戳排序
    aggregatedData.sort((a, b) => a[0] - b[0]);
    // 调整散点大小
    const scaleList = scaleArrayToRange(aggregatedData.map(item => item[1]));

    return aggregatedData.reduce((pre, cur, index) => {
      pre.push([cur[0], cur[1], scaleList[index]]);
      return pre;
    }, []);
  };

  /** 判断统计值是否全为0 */
  const isSumZero = statistic => {
    const sourceValues = Object.values(statistic.event_source).map(Number);
    const levelValues = Object.values(statistic.event_level).map(Number);
    const total = [...sourceValues, ...levelValues].reduce((acc, curr) => acc + curr, 0);
    return total === 0;
  };

  /** 获取事件分析数据 */
  const getEventsData = debounce(100, async () => {
    // 边概览不需要事件分析相关功能
    if (metricType.value !== 'node') return;

    try {
      const res = await incidentEventsSearch({
        ...commonParams.value,
        start_time: incidentDetailData.value.begin_time,
        end_time: endTime.value,
        interval: eventInterval.value,
      });
      const { statistics, events } = res;

      // 处理事件分析弹窗配置
      const newEventColumns = transformEventColumns(statistics);
      eventColumns.value = newEventColumns;

      const selectedEventConfig = localStorage.getItem('selected-event-config');
      if (!selectedEventConfig) {
        // 本地存储没有配置，使用接口返回的配置
        eventConfig.value = {
          event_source: {
            is_select_all: true,
            list: newEventColumns.find(f => f.name === 'event_source')?.list.map(item => item.value) || [],
          },
          event_level: {
            is_select_all: true,
            list: newEventColumns.find(f => f.name === 'event_level')?.list.map(item => item.value) || [],
          },
        };
      } else {
        eventConfig.value = JSON.parse(selectedEventConfig);
        const localEventColumns = localStorage.getItem('event-columns');
        // 如果本地存储的事件列配置和当前接口返回的配置不一致，则更新eventConfig
        if (localEventColumns !== JSON.stringify(newEventColumns)) {
          updateEventConfig(newEventColumns, JSON.parse(localEventColumns));
        }
      }

      // 保存事件分析数据用于散点图
      allEventsData.value = Object.values(events);
      const newEventsData = transformEventData(eventConfig.value);
      eventsData.value = newEventsData;
      disableEventAnalysis.value = isSumZero(statistics);
    } catch (err) {
      console.error('获取事件分析数据失败:', err);
      eventColumns.value = [];
      eventsData.value = [];
    } finally {
      isEventsLoaded.value = true;
      localStorage.setItem('event-columns', JSON.stringify(eventColumns.value));
      localStorage.setItem('selected-event-config', JSON.stringify(eventConfig.value));
    }
  });

  /** 全选处理 */
  const handleCheckedAllChange = (v: boolean, columnName: string, columnList: EventColumnItem[]) => {
    const configItem = eventConfig.value[columnName];
    configItem.is_select_all = v;
    configItem.list = v ? columnList.map(item => item.value) : columnList.length > 0 ? [columnList[0].value] : [];
  };

  /** 处理单个选项变化 */
  const handleGroupChange = (column: EventColumnConfig) => {
    const columnName = column.name;
    const configItem = eventConfig.value[columnName];
    configItem.is_select_all = configItem.list.length === column.list.length;
  };

  return {
    endTime,
    eventInterval,
    metricsData,
    allEventsData,
    eventsData,
    eventColumns,
    eventConfig,
    isEventsLoaded,
    loading,
    exceptionData,
    disableEventAnalysis,
    getMetricsData,
    getEventsData,
    handleChartInit,
    handleChartDestroy,
    syncChartsDataZoom,
    handleCheckedAllChange,
    handleGroupChange,
    transformEventData,
  };
}
