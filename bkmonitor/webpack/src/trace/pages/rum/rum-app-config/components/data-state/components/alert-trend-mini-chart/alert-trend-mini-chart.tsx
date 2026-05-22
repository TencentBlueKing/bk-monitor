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

import { type PropType, computed, defineComponent, getCurrentInstance, onBeforeUnmount, shallowRef, watch } from 'vue';

import dayjs from 'dayjs';
import { CancelToken } from 'monitor-api/cancel';
import tippy from 'tippy.js';
import { useI18n } from 'vue-i18n';

import { type TimeRangeType, handleTransformToTimestamp } from '../../../../../../../components/time-range/utils';
import {
  ALERT_BAR_ACTIVE_HEIGHT,
  ALERT_BAR_GAP,
  ALERT_BAR_HEIGHT,
  ALERT_BAR_WIDTH,
  ALERT_LEVEL_COLOR_MAP,
  ALERT_LEVEL_HOVER_COLOR_MAP,
  AlertLevelEnum,
} from '../../../../../constants';

import type { IAlertBarItem, IAlertGraphConfig } from '../../../../../typings';
import type { Instance } from 'tippy.js';

import './alert-trend-mini-chart.scss';

/** x 轴日期格式 */
const X_AXIS_FORMAT = 'MM-DD HH:mm';

export default defineComponent({
  name: 'AlertTrendMiniChart',
  props: {
    /** 告警趋势图配置 */
    alertGraph: {
      type: Object as PropType<IAlertGraphConfig | null>,
      default: null,
    },
    /** 时间范围 */
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => [],
    },
  },
  setup(props) {
    const { t } = useI18n();
    const instance = getCurrentInstance();
    const $api = instance?.appContext.config.globalProperties.$api;

    /** 色块数据列表 */
    const barItems = shallowRef<IAlertBarItem[]>([]);
    /** 加载中 */
    const loading = shallowRef(false);
    /** 当前 hover 的时间戳 */
    const hoverTime = shallowRef(-1);
    /** 取消令牌 */
    let cancelFn: (() => void) | null = null;

    /** 持久化 tippy 单例实例（首次 mouseenter 时创建，mouseleave 时仅 hide，组件卸载时 destroy） */
    let tippyInstance: Instance | null = null;

    /** 是否有有效配置 */
    const hasConfig = computed(() => !!props.alertGraph?.targets?.length);

    /** 图表整体宽度（px），每个色块 ALERT_BAR_WIDTH + ALERT_BAR_GAP，最后一个无间距 */
    const chartWidth = computed(() => {
      const len = barItems.value.length;
      return len > 0 ? len * (ALERT_BAR_WIDTH + ALERT_BAR_GAP) - ALERT_BAR_GAP : 0;
    });

    /** x 轴刻度标签：首尾两个时间点 */
    const xAxisLabels = computed(() => {
      const items = barItems.value;
      if (items.length < 2) return [];
      return [
        dayjs.tz(items[0].time).format(X_AXIS_FORMAT),
        dayjs.tz(items[items.length - 1].time).format(X_AXIS_FORMAT),
      ];
    });

    /**
     * @description 将 API 字符串拆分为模块名和函数名
     * @param {string} apiStr - API 标识，如 "apm_metric.alertQuery"
     * @returns {{ apiModule: string; apiFunc: string }} 模块名和函数名
     */
    const parseApiStr = (apiStr: string) => {
      const [apiModule = '', apiFunc = ''] = apiStr.split('.');
      return { apiModule, apiFunc };
    };

    /**
     * @description 将接口返回的 series 数据转换为告警色块数据列表
     * @param {{ datapoints?: unknown[][] }[]} seriesList - 接口返回的 series 数组
     * @returns {IAlertBarItem[]} 转换后的色块数据
     */
    const transformSeriesToBarItems = (seriesList: { datapoints?: unknown[][] }[]): IAlertBarItem[] => {
      const datapoints = seriesList?.[0]?.datapoints;
      if (!datapoints?.length) return [];

      return datapoints.map((point: unknown[]) => {
        const time = point[1] as number;

        // 告警 series 的 datapoint 结构: [[levelValue, count], timestamp]
        if (!point[0] || point[0] === null) {
          return { level: AlertLevelEnum.NO_DATA, time, value: null };
        }

        // point[0] 可能是数组 [告警级别, 告警数量] 或直接数值
        const isArrayValue = Array.isArray(point[0]);
        const levelValue = isArrayValue ? point[0][0] : point[0];
        const countValue = isArrayValue ? point[0][1] : point[0];

        if (countValue === null || levelValue === null) {
          return { level: AlertLevelEnum.NO_DATA, time, value: null };
        }

        // 1 = 致命, 2 = 预警, 其他 = 无告警
        let level: string = AlertLevelEnum.NORMAL;
        if (levelValue === 1) {
          level = AlertLevelEnum.FATAL;
        } else if (levelValue === 2) {
          level = AlertLevelEnum.WARNING;
        }

        return { level, time, value: countValue };
      });
    };

    /**
     * @description 根据 alertGraph 配置请求告警数据并转换为色块列表
     * @returns {Promise<void>}
     */
    const fetchAlertData = async () => {
      const graph = props.alertGraph;
      if (!graph?.targets?.length || !$api) {
        barItems.value = [];
        return;
      }

      // 取消上次请求
      cancelFn?.();
      cancelFn = null;

      loading.value = true;
      const target = graph.targets[0];
      const { apiModule, apiFunc } = parseApiStr(target.api);

      if (!apiModule || !apiFunc || !$api[apiModule]?.[apiFunc]) {
        loading.value = false;
        barItems.value = [];
        return;
      }

      try {
        const [startTime, endTime] = handleTransformToTimestamp(props.timeRange);
        const data = await $api[apiModule][apiFunc](
          { ...target.data, start_time: startTime, end_time: endTime },
          {
            cancelToken: new CancelToken((cb: () => void) => {
              cancelFn = cb;
            }),
            needMessage: false,
          }
        );
        barItems.value = Object.freeze(transformSeriesToBarItems(data?.series ?? [])) as IAlertBarItem[];
      } catch {
        barItems.value = [];
      } finally {
        loading.value = false;
      }
    };

    /**
     * @description 获取告警级别的中文状态文案
     * @param {string} level - 告警级别
     * @returns {string} 状态文案
     */
    const getLevelText = (level: string): string => {
      const textMap: Record<string, string> = {
        [AlertLevelEnum.FATAL]: t('致命'),
        [AlertLevelEnum.WARNING]: t('预警'),
        [AlertLevelEnum.NORMAL]: t('无告警'),
        [AlertLevelEnum.NO_DATA]: t('无请求数据'),
      };
      return textMap[level] ?? t('未知');
    };

    /**
     * @description 获取色块的背景色，根据 hover 状态切换颜色
     * @param {IAlertBarItem} item - 色块数据项
     * @returns {string} CSS 颜色值
     */
    const getBarColor = (item: IAlertBarItem): string => {
      const isHovered = hoverTime.value === item.time && item.level !== AlertLevelEnum.NO_DATA;
      const colorMap = isHovered ? ALERT_LEVEL_HOVER_COLOR_MAP : ALERT_LEVEL_COLOR_MAP;
      return colorMap[item.level] ?? ALERT_LEVEL_COLOR_MAP[AlertLevelEnum.NO_DATA];
    };

    /**
     * @description 获取色块的高度样式
     * @param {IAlertBarItem} item - 色块数据项
     * @returns {string} CSS 高度值（含 px）
     */
    const getBarHeight = (item: IAlertBarItem): string => {
      const isHovered = hoverTime.value === item.time && item.level !== AlertLevelEnum.NO_DATA;
      return `${isHovered ? ALERT_BAR_ACTIVE_HEIGHT : ALERT_BAR_HEIGHT}px`;
    };

    /**
     * @description 构建 tooltip 的 HTML 内容
     * @param {IAlertBarItem} item - 色块数据项
     * @returns {string} tooltip HTML 字符串
     */
    const buildTooltipContent = (item: IAlertBarItem): string => {
      const timeStr = dayjs.tz(item.time).format('YYYY-MM-DD HH:mm:ssZZ');
      const dotColor = ALERT_LEVEL_COLOR_MAP[item.level] ?? ALERT_LEVEL_COLOR_MAP[AlertLevelEnum.NO_DATA];
      const levelText = getLevelText(item.level);
      return `
        <div class="tooltip-time">${timeStr}</div>
        <div class="tooltip-status">
          <span class="tooltip-status-dot" style="background:${dotColor}"></span>
          <span class="tooltip-status-text">${levelText}</span>
        </div>`;
    };

    /**
     * @description 鼠标移入色块：复用持久化 tippy 实例，仅更新内容和锚点，避免闪烁
     * @param {MouseEvent} e - 鼠标事件
     * @param {IAlertBarItem} item - 当前色块数据项
     * @returns {void}
     */
    const handleBarMouseEnter = (e: MouseEvent, item: IAlertBarItem) => {
      hoverTime.value = item.time;
      const target = e.currentTarget as Element;
      const content = buildTooltipContent(item);

      if (tippyInstance) {
        // 复用已有实例：更新锚点和内容，不销毁重建
        tippyInstance.setProps({
          getReferenceClientRect: () => target.getBoundingClientRect(),
        });
        tippyInstance.setContent(content);
        if (!tippyInstance.state.isShown) {
          tippyInstance.show();
        }
      } else {
        // 首次创建：使用虚拟锚点模式（getReferenceClientRect）
        tippyInstance = tippy(document.createElement('div'), {
          content,
          getReferenceClientRect: () => target.getBoundingClientRect(),
          appendTo: () => document.body,
          placement: 'top',
          arrow: true,
          animation: false,
          interactive: false,
          allowHTML: true,
          theme: 'alert-trend-tooltip',
          showOnCreate: true,
          trigger: 'manual',
        });
      }
    };

    /**
     * @description 鼠标移出色块区域：仅隐藏 tooltip，不销毁实例
     * @returns {void}
     */
    const handleBarMouseLeave = () => {
      hoverTime.value = -1;
      tippyInstance?.hide();
    };

    // 组件卸载时销毁 tippy 实例
    onBeforeUnmount(() => {
      tippyInstance?.destroy();
      tippyInstance = null;
    });

    // 监听 alertGraph 和 timeRange 配置变化，重新拉取数据
    watch(
      () => [props.alertGraph, props.timeRange],
      () => fetchAlertData(),
      { immediate: true }
    );

    return {
      t,
      barItems,
      chartWidth,
      getBarColor,
      getBarHeight,
      handleBarMouseEnter,
      handleBarMouseLeave,
      hasConfig,
      hoverTime,
      loading,
      xAxisLabels,
    };
  },
  render() {
    // 无配置 — 显示暂无数据
    if (!this.hasConfig) {
      return (
        <span class='alert-trend-mini-chart'>
          <span class='no-data-text'>{this.t('暂无数据')}</span>
        </span>
      );
    }

    // 加载中 — 骨架条
    if (this.loading) {
      return (
        <div
          style={{ width: `${this.chartWidth || 238}px` }}
          class='alert-trend-mini-chart'
        >
          <div class='mini-chart-skeleton' />
        </div>
      );
    }

    // 无数据
    if (!this.barItems.length) {
      return (
        <span class='alert-trend-mini-chart'>
          <span class='no-data-text'>{this.t('暂无数据')}</span>
        </span>
      );
    }

    // 色块渲染
    return (
      <div
        style={{ width: `${this.chartWidth}px` }}
        class='alert-trend-mini-chart'
      >
        {/* 色块区域 */}
        <div
          class='mini-chart-bar-wrap'
          onMouseleave={this.handleBarMouseLeave}
        >
          {this.barItems.map(item => (
            <div
              key={item.time}
              style={{ background: this.getBarColor(item), height: this.getBarHeight(item) }}
              class={['mini-chart-bar', `alert-bar__${item.time}`]}
              onMouseenter={(e: MouseEvent) => this.handleBarMouseEnter(e, item)}
            />
          ))}
        </div>

        {/* X 轴 */}
        {this.xAxisLabels.length > 0 && (
          <div class='mini-chart-x-axis'>
            {this.xAxisLabels.map(label => (
              <span
                key={label}
                class='x-axis-label'
              >
                {label}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  },
});
