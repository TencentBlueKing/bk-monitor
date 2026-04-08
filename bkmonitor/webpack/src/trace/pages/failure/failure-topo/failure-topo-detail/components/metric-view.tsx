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
import { type PropType, computed, ref as deepRef, defineComponent, nextTick, onMounted, onUnmounted, watch } from 'vue';

import { Button, Checkbox, Loading, Popover, Switcher } from 'bkui-vue';
import dayjs from 'dayjs';
import { fitPosition } from 'monitor-ui/chart-plugins/utils';
import { useI18n } from 'vue-i18n';

import ExceptionComp from '../../../../../components/exception';
import useMetrics from '../useMetrics';
import CustomEventMenu from './custom-event-menu';
import MetricChart from './metric-chart';

import type { IEventTagsItem, IMetricItem } from '../../types';

import './metric-view.scss';

export default defineComponent({
  components: {
    MetricChart,
  },
  props: {
    data: {
      type: Object as PropType<any>,
      required: true,
    },
    type: {
      type: String as PropType<'edge' | 'node'>,
      required: true,
    },
    getMetricsDataLength: {
      type: Function as PropType<(length: number) => void>,
      default: () => {},
    },
    refreshTime: {
      type: Number,
      required: true,
    },
    showServiceOverview: {
      type: Boolean,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n();
    // 事件分析开关状态
    const showEventAnalyze = deepRef(false);
    // 是否展示事件分析弹窗
    const popoverShow = deepRef(false);
    // 当前是否为"节点概览"
    const isNodeView = computed(() => props.type === 'node');
    // 自定义事件menu位置信息
    const customMenuPosition = deepRef({ left: 0, top: 0 });
    // 点击的事件项
    const clickEventItem = deepRef<IEventTagsItem>();
    // 存储当前打开的自定义事件弹窗元素
    const customMenuRef = deepRef<any>(null);
    // 是否在弹窗内点击
    const mousedownInMenu = deepRef(false);
    // 指标类型
    const metricType = computed(() => (isNodeView.value ? 'node' : props.data.edge_type));
    // 节点类型
    const nodeType = computed(() => props.data.entity.properties?.entity_category || props.data.entity.rank_name);
    // 边的指标数据
    const edgeMetricData = computed(() => props.data.events ?? []);
    // 数据自动刷新时间
    const refreshTime = computed(() => props.refreshTime);
    const showServiceOverview = computed(() => props.showServiceOverview);

    /** 获取接口请求的公共传参数据 */
    const commonParams = computed(() => {
      let index_info = null;
      if (isNodeView.value) {
        index_info = {
          index_type: 'entity',
          entity_type: props.data.entity.entity_type,
          entity_name: props.data.entity.entity_name,
          is_anomaly: props.data.entity.is_anomaly,
          dimensions: props.data.entity.dimensions || {},
        };
      } else {
        index_info = {
          index_type: 'edge',
          source_type: props.data.source_type,
          source_name: props.data.source_name,
          target_type: props.data.target_type,
          target_name: props.data.target_name,
          is_anomaly: props.data.is_anomaly,
        };
      }
      return {
        bk_biz_id: window.bk_biz_id,
        index_info,
      };
    });

    const {
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
      transformEventData,
      handleChartInit,
      handleChartDestroy,
      syncChartsDataZoom,
      handleCheckedAllChange,
      handleGroupChange,
    } = useMetrics(
      commonParams,
      metricType,
      refreshTime,
      showServiceOverview,
      props.getMetricsDataLength,
      edgeMetricData
    );

    /**
     * 所有图表共享的 x 轴时间轴（时间戳数组，单位 ms）。
     *
     * 为什么这里用“时间轴”做中转：
     * - 顶部 slider 交互用“索引”最方便（加减、边界 clamp 都是整数）
     * - ECharts 的 dataZoom 联动更适合用 startValue/endValue（时间戳）
     */
    const timeAxis = deepRef<number[]>([]);
    // 顶部 slider 当前选中窗口，索引范围（包含端点）
    const sliderRange = deepRef<[number, number]>([0, 0]);
    /**
     * 默认窗口策略：默认取“尾部5%”的数据（至少 50 点，最多 2000 点）
     * - 小数据量：仍然接近 50 点的体验
     * - 大数据量：窗口可见且可拖（不会小到抓不住）
     */
    const DEFAULT_WINDOW_SIZE = 50;
    const DEFAULT_WINDOW_RATIO = 0.05;
    const MAX_DEFAULT_WINDOW_SIZE = 2000;
    /**
     * 最小窗口（单位：点数）。
     * 注意：最小可操作宽度更多是“UI 命中问题”，我们会在 SCSS 里用最小像素宽度兜底；
     * 这里仍保持为较小的点数，避免用户无法缩到更细粒度。
     */
    const MIN_WINDOW_SIZE = 12;

    // 当前窗口包含的数据点数量（用于计算滑块宽度百分比）
    const dataWindowSize = deepRef(DEFAULT_WINDOW_SIZE);
    // slider 轨道 DOM，用于把鼠标位移(px)映射成索引位移
    const trackRef = deepRef<HTMLDivElement | null>(null);
    /**
     * 避免 `trackRef.value` 会一直为 null，导致 trackWidth 退化为 1，引发“轻拖直接跳到两端”。
     */
    const setTrackRef = (el: Element | null) => {
      trackRef.value = el as HTMLDivElement | null;
    };
    /**
     * 保存拖拽期间改写的 document 默认行为（选择/拖拽），用于 stopDrag 还原。
     * 这样可以避免拖动过程中选中文本导致体验很差。
     */
    const docDefaultHandlers = deepRef<null | {
      ondragstart: typeof document.ondragstart;
      onselectstart: typeof document.onselectstart;
    }>(null);

    const dragging = deepRef<{
      startEndIdx: number;
      startStartIdx: number;
      startX: number;
      trackWidth: number;
      type: '' | 'bar' | 'left' | 'right';
    }>({
      type: '',
      startX: 0,
      startStartIdx: 0,
      startEndIdx: 0,
      trackWidth: 1,
    });

    /**
     * 用 rAF 合并拖拽过程中的高频更新：
     * - UI 更新（window 位置/宽度）
     * - 可选的 dataZoom 同步（只在 shouldSync=true 时触发）
     */
    const rafState = deepRef<{ id: number; pending: null | { endIdx: number; shouldSync: boolean; startIdx: number } }>(
      {
        id: 0,
        pending: null,
      }
    );

    /**
     * 从接口返回的指标数据中提取时间戳（各指标图表的 x 轴时间范围一致，因此可以从第一条指标里抽）
     */
    const getTimeAxis = (metricItems: IMetricItem[]) => {
      if (!Array.isArray(metricItems) || metricItems.length === 0) return [];
      const firstItem = metricItems[0];
      const firstSeries = Object.values(firstItem.time_series || {})[0] as any;
      if (!firstSeries?.datapoints?.length) return [];
      return firstSeries.datapoints.map((item: any) => item[0]);
    };

    /** 二分：找到第一个 >= target 的位置 */
    const lowerBound = (arr: number[], target: number) => {
      let l = 0;
      let r = arr.length;
      while (l < r) {
        const m = (l + r) >> 1;
        if (arr[m] < target) l = m + 1;
        else r = m;
      }
      return l;
    };

    /**
     * 把 timestamp 映射到 timeAxis 的 index。
     * - 图表 `dataZoom` 事件有时返回 startValue/endValue（timestamp）
     * - slider 逻辑用 index 更容易做 clamp/拖拽计算
     */
    const findIndexByValue = (value: number) => {
      if (!timeAxis.value.length) return 0;
      const i = lowerBound(timeAxis.value, value);
      return Math.min(Math.max(i, 0), timeAxis.value.length - 1);
    };

    /**
     * 设置顶部 slider 的选中窗口（索引区间），并“可选”同步到所有图表。
     * - `shouldSync` 用于区分来源：
     *   - true：用户在顶部 slider 拖动，需要驱动图表 dataZoom
     *   - false：用户在图表里拖动/缩放，顶部 slider 只做“显示跟随”，避免互相触发造成循环
     * - 用 rAF 合并高频更新，让拖动更顺滑。
     */
    const scheduleSetRange = (startIdx: number, endIdx: number, shouldSync: boolean) => {
      const axisLen = timeAxis.value.length;
      if (axisLen < 2) {
        // 数据点不足 2 个时无法形成窗口，兜底为 [0,0]
        sliderRange.value = [0, 0];
        dataWindowSize.value = axisLen;
        return;
      }

      // 最小窗口：axisLen 可能小于 MIN_WINDOW_SIZE，需做 clamp
      const minSpan = Math.max(Math.min(MIN_WINDOW_SIZE, axisLen), 2);

      // 先把 start/end 做到 [0, axisLen-1]，再统一保证 span
      let s = Math.min(Math.max(startIdx, 0), axisLen - 1);
      let e = Math.min(Math.max(endIdx, 0), axisLen - 1);
      if (e < s) [s, e] = [e, s];

      // 保证窗口至少 minSpan 个点
      if (e - s + 1 < minSpan) {
        e = Math.min(s + minSpan - 1, axisLen - 1);
        s = Math.max(e - (minSpan - 1), 0);
      }

      // 兜底：保证 start < end（至少 2 个点）
      if (e <= s) {
        s = Math.min(s, axisLen - 2);
        e = s + 1;
      }

      rafState.value.pending = { startIdx: s, endIdx: e, shouldSync };
      if (rafState.value.id) return;

      rafState.value.id = window.requestAnimationFrame(() => {
        const pending = rafState.value.pending;
        rafState.value.id = 0;
        rafState.value.pending = null;
        if (!pending) return;

        const nextStart = pending.startIdx;
        const nextEnd = pending.endIdx;
        if (nextStart === sliderRange.value[0] && nextEnd === sliderRange.value[1]) return;

        // 更新 UI 状态
        sliderRange.value = [nextStart, nextEnd];
        dataWindowSize.value = nextEnd - nextStart + 1;

        // 按需同步到图表
        if (!pending.shouldSync) return;
        syncChartsDataZoom({ startValue: timeAxis.value[nextStart], endValue: timeAxis.value[nextEnd] });
      });
    };

    /**
     * 指标数据更新时刷新 timeAxis，并设置默认窗口。
     * 规则：默认选中“尾部 50 条”（与 ECharts dataZoom-slider 默认行为一致）。
     */
    const refreshAxisAndRange = (data: IMetricItem[]) => {
      const axis = getTimeAxis(data);
      timeAxis.value = axis;
      if (!axis.length) {
        sliderRange.value = [0, 0];
        dataWindowSize.value = 0;
        return;
      }
      const axisLen = axis.length;
      const ratioSize = Math.floor(axisLen * DEFAULT_WINDOW_RATIO);
      const windowSize = Math.min(axisLen, Math.max(DEFAULT_WINDOW_SIZE, Math.min(ratioSize, MAX_DEFAULT_WINDOW_SIZE)));
      dataWindowSize.value = windowSize;
      const startIdx = Math.max(axis.length - windowSize, 0);
      const endIdx = axis.length - 1;
      scheduleSetRange(startIdx, endIdx, true);
    };

    /**
     * 图表内部 dataZoom 变化时回写顶部 slider。
     * - 这里只更新 slider（shouldSync=false），避免反向再 dispatch 引起循环/卡顿
     */
    const handleChartDataZoom = (payload: { end?: number; endValue?: number; start?: number; startValue?: number }) => {
      if (!timeAxis.value.length) return;
      const axisLen = timeAxis.value.length;

      let startIdx: null | number = null;
      let endIdx: null | number = null;

      // 优先使用 startValue/endValue（timestamp）做映射（更精确）
      if (typeof payload.startValue === 'number' && typeof payload.endValue === 'number') {
        startIdx = findIndexByValue(payload.startValue);
        endIdx = findIndexByValue(payload.endValue);
      }
      // 兜底使用 start/end（percent）
      else if (typeof payload.start === 'number' && typeof payload.end === 'number') {
        startIdx = Math.round(((axisLen - 1) * payload.start) / 100);
        endIdx = Math.round(((axisLen - 1) * payload.end) / 100);
      }

      if (startIdx === null || endIdx === null) return;
      if (endIdx <= startIdx) endIdx = Math.min(startIdx + 1, axisLen - 1);

      scheduleSetRange(startIdx, endIdx, false);
    };

    const formatAxisLabel = (value?: number) => {
      if (!value) return '--';
      return dayjs(value).format('MM-DD HH:mm:ss');
    };

    /**
     * 图表 init
     */
    const handleChartInitWithSync = (chart: any) => {
      handleChartInit(chart);
      if (timeAxis.value.length < 2) return;
      const [s, e] = sliderRange.value;
      if (e <= s) return;

      // 当前新初始化的图表本身对齐到 slider 范围。
      try {
        chart?.dispatchAction?.({
          type: 'dataZoom',
          dataZoomIndex: 0,
          startValue: timeAxis.value[s],
          endValue: timeAxis.value[e],
        });
      } catch (err) {
        console.error('sync chart dataZoom failed:', err);
      }
    };

    /**
     * 开始拖拽 slider
     * - type='bar'：拖动窗口整体平移
     * - type='left'/'right'：拖动左右把手改变窗口宽度
     */
    const startDrag = (type: 'bar' | 'left' | 'right', event: MouseEvent) => {
      if (event.button !== 0) return; // 仅响应鼠标左键
      if (timeAxis.value.length < 2) return;

      event.preventDefault();

      // 禁止选中文本/拖拽图片等，避免拖动过程被浏览器默认行为打断
      if (!docDefaultHandlers.value) {
        docDefaultHandlers.value = {
          onselectstart: document.onselectstart,
          ondragstart: document.ondragstart,
        };
      }
      document.onselectstart = () => false;
      document.ondragstart = () => false;

      const trackWidth = Math.max(
        trackRef.value?.getBoundingClientRect?.().width || trackRef.value?.clientWidth || 0,
        1
      );
      dragging.value = {
        type,
        startX: event.clientX,
        startStartIdx: sliderRange.value[0],
        startEndIdx: sliderRange.value[1],
        trackWidth,
      };

      document.addEventListener('mousemove', handleDragging);
      document.addEventListener('mouseup', stopDrag);
    };

    const handleDragging = (event: MouseEvent) => {
      if (!timeAxis.value.length) return;
      if (!dragging.value.type) return;

      const axisLen = timeAxis.value.length;
      const trackWidth = Math.max(dragging.value.trackWidth, 1);
      const deltaPx = event.clientX - dragging.value.startX;

      /**
       * 将“鼠标位移(px)”映射为“索引位移(idx)”。
       * - bar：scale 使用 totalMove（可平移的最大跨度），保证拖动手感更接近 ECharts
       * - handle：scale 使用 (axisLen - 1)，更直观地按全量范围缩放
       */
      const calcDeltaIdx = (scale: number) => {
        const raw = (deltaPx / trackWidth) * scale;
        let d = Math.round(raw);
        // 很小的位移也希望能至少移动 1 个点，增强“跟手感”
        if (d === 0 && Math.abs(deltaPx) > 0) d = deltaPx > 0 ? 1 : -1;
        return d;
      };

      const start0 = dragging.value.startStartIdx;
      const end0 = dragging.value.startEndIdx;
      // 这里使用当前窗口大小作为“平移时的固定宽度”
      const size0 = Math.max(end0 - start0 + 1, 2);

      if (dragging.value.type === 'bar') {
        const totalMove = Math.max(axisLen - size0, 0);
        const deltaIdx = calcDeltaIdx(totalMove);
        const nextStart = Math.min(Math.max(start0 + deltaIdx, 0), totalMove);
        scheduleSetRange(nextStart, nextStart + size0 - 1, true);
        return;
      }

      const deltaIdx = calcDeltaIdx(axisLen - 1);
      if (dragging.value.type === 'left') {
        const nextStart = Math.min(Math.max(start0 + deltaIdx, 0), end0 - 1);
        scheduleSetRange(nextStart, end0, true);
        return;
      }

      // right
      const nextEnd = Math.min(Math.max(end0 + deltaIdx, start0 + 1), axisLen - 1);
      scheduleSetRange(start0, nextEnd, true);
    };

    /** 结束拖拽：清理监听并恢复 document 默认行为 */
    const stopDrag = () => {
      dragging.value.type = '';
      document.removeEventListener('mousemove', handleDragging);
      document.removeEventListener('mouseup', stopDrag);

      if (docDefaultHandlers.value) {
        document.onselectstart = docDefaultHandlers.value.onselectstart || null;
        document.ondragstart = docDefaultHandlers.value.ondragstart || null;
        docDefaultHandlers.value = null;
      }
    };

    watch(
      metricsData,
      val => {
        refreshAxisAndRange(val);
      },
      { deep: true }
    );

    // 数据变化时，重置图表
    watch(
      () => props.data,
      () => {
        getMetricsData();
        getEventsData();
      }
    );

    onMounted(() => {
      getMetricsData();
      showEventAnalyze.value = JSON.parse(localStorage.getItem('show-event-analyze')) || false;
      getEventsData();

      document.addEventListener('mousedown', handleDocumentMouseDown);
    });

    onUnmounted(() => {
      document.removeEventListener('mousedown', handleDocumentMouseDown);
      stopDrag();
    });

    /** 处理事件点击（定位自定义事件菜单） */
    const handleClick = params => {
      const start_time = Math.floor(params.value[0] / 1000);
      const { clientX, clientY } = params.event.event;
      // 计算菜单位置，确保在可视区域内
      const position = fitPosition(
        {
          left: clientX + 12,
          top: clientY + 12,
        },
        400,
        300
      );
      customMenuPosition.value = {
        left: position.left,
        top: position.top,
      };

      clickEventItem.value = {
        bk_biz_id: window.bk_biz_id,
        start_time,
        interval: eventInterval.value,
        index_info: {
          index_type: 'entity',
          entity_type: props.data.entity.entity_type,
          entity_name: props.data.entity.entity_name,
          is_anomaly: props.data.entity.is_anomaly,
          dimensions: props.data.entity.dimensions || {},
          source_filter: eventConfig.value.event_source.list || [],
          type_filter: eventConfig.value.event_level.list || [],
        },
        end_time: endTime.value,
      };
    };

    const handleDocumentMouseDown = event => {
      // 弹窗未显示时跳过
      if (!customMenuPosition.value.left) return;
      const target = event.target;
      const menuEl = customMenuRef.value?.$el;
      // 检测点击目标是否在弹窗内
      mousedownInMenu.value = menuEl?.contains(target);
      if (!mousedownInMenu.value) {
        handleChartBlur();
      }
    };

    /** 隐藏菜单 */
    const handleChartBlur = () => {
      nextTick(() => {
        customMenuPosition.value = {
          left: 0,
          top: 0,
        };
      });
    };

    const handleChangeSwitch = val => {
      localStorage.setItem('show-event-analyze', val);
      if (!val) {
        handleEventAnalyzeCancel();
      }
    };

    const handleShowPopover = () => {
      if (
        !showEventAnalyze.value ||
        !isEventsLoaded.value ||
        allEventsData.value.length === 0 ||
        disableEventAnalysis.value
      )
        return;
      popoverShow.value = !popoverShow.value;
    };

    const handleEventAnalyzeConfirm = () => {
      popoverShow.value = false;
      eventsData.value = transformEventData(eventConfig.value);
      localStorage.setItem('selected-event-config', JSON.stringify(eventConfig.value));
    };

    const handleEventAnalyzeCancel = () => {
      popoverShow.value = false;
      eventConfig.value = JSON.parse(localStorage.getItem('selected-event-config'));
    };

    /** 无数据处理或异常占位 */
    const handleException = () => {
      const { type, msg } = exceptionData.value;
      if (!type && !msg) return '';
      return (
        <ExceptionComp
          errorMsg={msg}
          imgHeight={100}
          isDarkTheme={true}
          isError={type === 'error'}
          title={type === 'noData' ? msg : t('查询异常')}
        />
      );
    };

    return {
      loading,
      eventConfig,
      eventColumns,
      showEventAnalyze,
      popoverShow,
      customMenuPosition,
      clickEventItem,
      metricsData,
      allEventsData,
      eventsData,
      isEventsLoaded,
      customMenuRef,
      isNodeView,
      exceptionData,
      nodeType,
      disableEventAnalysis,
      handleException,
      handleShowPopover,
      handleCheckedAllChange,
      handleGroupChange,
      handleEventAnalyzeConfirm,
      handleEventAnalyzeCancel,
      handleChangeSwitch,
      timeAxis,
      sliderRange,
      dataWindowSize,
      handleChartDataZoom,
      handleChartInitWithSync,
      handleChartDestroy,
      handleClick,
      formatAxisLabel,
      startDrag,
      trackRef,
      setTrackRef,
      t,
    };
  },
  render() {
    if (this.loading) {
      return (
        <Loading
          class='metric-view-loading'
          color='#1d2024'
          loading={this.loading}
        />
      );
    }
    if (this.exceptionData.showException) {
      return this.handleException();
    }
    return (
      <div class='metric-wrap'>
        {/* 事件分析 */}
        {this.isNodeView && (
          <div
            class='event-analyze'
            v-bk-tooltips={{
              content: this.t('暂无关联的事件数据'),
              disabled: this.allEventsData.length > 0 && !this.disableEventAnalysis,
            }}
          >
            <Switcher
              v-model={this.showEventAnalyze}
              disabled={this.allEventsData.length === 0 || this.disableEventAnalysis}
              size='small'
              theme='primary'
              onChange={this.handleChangeSwitch}
            />
            <span class='event-analyze_title'>{this.t('事件分析')}</span>
            <Popover
              extCls='event-analyze-popover'
              arrow={false}
              is-show={this.popoverShow}
              placement='bottom-start'
              theme='light'
              trigger='manual'
              onAfterHidden={this.handleEventAnalyzeCancel}
            >
              {{
                content: () => (
                  <div class='event-analyze-wrapper'>
                    <div class='event-content'>
                      {this.eventColumns.map(column => {
                        const config = this.eventConfig[column.name];
                        if (!config) return undefined;
                        return (
                          <div
                            key={column.name}
                            class='event-wrapper'
                          >
                            <div class='event-content-title'>{column.alias}</div>
                            <Checkbox
                              key={`${column.name}-all`}
                              v-model={config.is_select_all}
                              size='small'
                              onChange={v => this.handleCheckedAllChange(v, column.name, column.list)}
                            >
                              {this.t('全选')}
                            </Checkbox>
                            <Checkbox.Group
                              class='event-content-list'
                              v-model={config.list}
                              onChange={() => this.handleGroupChange(column)}
                            >
                              {column.list?.map(item => (
                                <Checkbox
                                  key={item.value}
                                  disabled={config.list.length === 1 && config.list.includes(item.value)}
                                  label={item.value}
                                  size='small'
                                >
                                  {`${item.alias} (${item.count})`}
                                </Checkbox>
                              ))}
                            </Checkbox.Group>
                          </div>
                        );
                      })}
                    </div>
                    <div class='event-footer'>
                      <Button
                        size='small'
                        theme='primary'
                        onClick={this.handleEventAnalyzeConfirm}
                      >
                        {this.t('确定')}
                      </Button>
                      <Button
                        size='small'
                        onClick={this.handleEventAnalyzeCancel}
                      >
                        {this.t('取消')}
                      </Button>
                    </div>
                  </div>
                ),
                default: () => (
                  <span
                    class='event-analyze_icon'
                    v-bk-tooltips={{
                      content: this.t('请先打开事件分析'),
                      disabled: this.showEventAnalyze || this.allEventsData.length === 0 || this.disableEventAnalysis,
                    }}
                    onClick={this.handleShowPopover}
                  >
                    <i
                      style={{
                        cursor:
                          this.showEventAnalyze &&
                          this.isEventsLoaded &&
                          this.allEventsData.length > 0 &&
                          !this.disableEventAnalysis
                            ? 'pointer'
                            : 'not-allowed',
                      }}
                      class={['icon-monitor icon-filter-fill', this.popoverShow && 'event-analyze_icon-active']}
                    />
                  </span>
                ),
              }}
            </Popover>
          </div>
        )}
        {/* 图表缩放 */}
        <div class='metric-wrap-header'>
          <div class={['metric-slider-wrap', { 'metric-slider-wrap--full-width': !this.isNodeView }]}>
            <span>{this.t('缩放')}</span>
            <div
              ref={this.setTrackRef}
              class='metric-slider'
            >
              {this.timeAxis.length > 0 && (
                <div
                  /**
                   * 这里把“索引窗口”换算成百分比，用于驱动滑块的 left/width。
                   * - 分母用 (len - 1) 是因为索引范围是 [0, len-1]
                   * - dataWindowSize 用点数表达，因此 width 也用 (size-1)/(len-1)
                   */
                  style={{
                    '--window-width': `${((this.dataWindowSize - 1) / Math.max(this.timeAxis.length - 1, 1)) * 100}%`,
                    '--window-left': `${(this.sliderRange?.[0] / Math.max(this.timeAxis.length - 1, 1)) * 100}%`,
                  }}
                  class='metric-slider__window'
                  onMousedown={(e: MouseEvent) => this.startDrag('bar', e)}
                >
                  {/* 滑块左把手 */}
                  <div
                    class='metric-slider__handle metric-slider__handle--left'
                    onMousedown={(e: MouseEvent) => {
                      e.stopPropagation();
                      this.startDrag('left', e);
                    }}
                  />
                  {/* 滑块右把手 */}
                  <div
                    class='metric-slider__handle metric-slider__handle--right'
                    onMousedown={(e: MouseEvent) => {
                      e.stopPropagation();
                      this.startDrag('right', e);
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
        <div class='metric-wrap-main'>
          {/* 指标图表 */}
          {this.metricsData.length > 0 &&
            this.metricsData.map((item, index) => (
              <div
                key={`metric-chart-${index}`}
                class='chart-wrap'
              >
                <MetricChart
                  eventsData={this.eventsData}
                  index={index}
                  isNodeView={this.isNodeView}
                  metricItem={item}
                  showEventAnalyze={this.showEventAnalyze}
                  onDataZoomChange={this.handleChartDataZoom}
                  onDestroy={this.handleChartDestroy}
                  onEventClick={this.handleClick}
                  onInit={this.handleChartInitWithSync}
                />
              </div>
            ))}
        </div>
        {/* 自定义事件菜单 */}
        {this.customMenuPosition?.left > 0 && (
          <CustomEventMenu
            ref={(el: any) => (this.customMenuRef = el)}
            eventItem={this.clickEventItem}
            nodeType={this.nodeType}
            position={this.customMenuPosition}
          />
        )}
      </div>
    );
  },
});
