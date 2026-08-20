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

import { type Ref, computed, defineComponent, inject, ref, shallowRef, watch } from 'vue';

import { random } from 'monitor-common/utils/utils';

import FailureViewAlarmChart from './failure-view-alarm-chart';

import type { DateValue } from '@blueking/date-picker';

/**
 * @description 故障告警图表入口组件（仅告警视图使用）
 *
 * 由 ChartWrapper 渲染，detail 为 PanelModel（保留了原始 alert 全部字段）。
 * 图表展示复用告警侧滑中的 AlarmCharts（通过 provide 注入 FailureViewMonitorCharts），
 * 基础设施（echarts connect/disconnect、tooltip 边界裁剪、懒加载）由 LazyDashboardPanel 管理。
 *
 * 职责：
 *  1. 注入 LazyDashboardPanel 提供的作用域级 panelZoomRange / viewportPanelIds
 *  2. 将 dataZoom 事件广播给同 Collapse 组内其他图表
 *  3. 仅视口内图表响应 dataZoom / tooltip 联动
 *  4. 复位时清理自身 linkedZoomRange（复位不联动；缩放锁定由 FailureViewMonitorCharts 负责）
 *  5. 无数据图的「不复位 / 不吃联动」门禁在 FailureViewAlarmChart 内完成，此处仍广播 linkedZoomRange
 */
export default defineComponent({
  name: 'FailureViewChartEntry',
  props: {
    /** 告警面板数据（PanelModel，保留了 alert 所有字段） */
    detail: {
      type: Object,
      required: true,
    },
    /** echarts 联动组 ID（由 LazyDashboardPanel → ChartWrapper 透传） */
    groupId: {
      type: String,
      default: '',
    },
  },
  emits: ['successLoad'],
  setup(props, { emit }) {
    /** 每个实例的唯一标识，用于 sourceId 去重 */
    const instanceId = random(8);

    /**
     * 作用域级 dataZoom 事件广播（由 LazyDashboardPanel 提供）。
     * 结构：{ range: DateValue; sourceId: string } | null
     */
    const panelZoomRange = inject<Ref<{ range: DateValue; sourceId: string } | null>>(
      'lazyPanelZoomRange',
      shallowRef(null)
    );

    /**
     * 当前在视口范围内的 panel ID 集合（由 LazyDashboardPanel 的 IntersectionObserver 维护）。
     * 用于判断本图表是否在视口内，仅视口内的图表才响应 dataZoom 联动。
     */
    const viewportPanelIds = inject<Ref<Set<string>>>('viewportPanelIds', ref(new Set()));

    /** 本图表对应的 panel ID（字符串化，与 LazyDashboardPanel 的 data-panel-id 一致） */
    const panelId = String(props.detail?.id ?? '');

    /**
     * 本图表是否当前在视口范围内（响应式）。
     * 同时控制 tooltip 联动（仅视口内图表显示联动 tooltip）和 dataZoom 联动。
     */
    const isInViewport = computed(() => viewportPanelIds.value.has(panelId));

    /**
     * 来自同组其他图表的 zoom 范围。
     * 由 watch(panelZoomRange) 驱动，传递给 FailureViewAlarmChart → AlarmCharts。
     * 初始为 null，确保懒加载图表首次渲染时使用默认时间范围。
     */
    const linkedZoomRange = shallowRef<DateValue | null>(null);

    /**
     * 监听同组其他图表的 dataZoom 事件。
     * 仅当满足以下全部条件时才处理：
     *  1. 不是自身发起的 zoom（sourceId !== instanceId）
     *  2. 本图表当前在视口范围内（viewportPanelIds 包含 panelId）
     *  3. watch immediate: false → 挂载前的历史 zoom 不处理
     */
    watch(panelZoomRange, newVal => {
      if (!newVal || newVal.sourceId === instanceId) return;
      if (!viewportPanelIds.value.has(panelId)) return;
      linkedZoomRange.value = newVal.range;
    });

    /**
     * @description 本图框选缩放 → 广播给同组其他图表
     */
    const handleDataZoomChange = (value: DateValue) => {
      panelZoomRange.value = { range: value, sourceId: instanceId };
    };

    /**
     * @description 本图复位：清理联动 zoom 缓存，避免下次框选时被旧 range 污染
     * 复位不联动，仅清理自身收到的 linkedZoomRange
     */
    const handleRestore = () => {
      linkedZoomRange.value = null;
    };

    const handleSuccessLoad = () => {
      emit('successLoad');
    };

    return {
      isInViewport,
      linkedZoomRange,
      handleDataZoomChange,
      handleRestore,
      handleSuccessLoad,
    };
  },
  render() {
    return (
      <FailureViewAlarmChart
        alert={this.$props.detail}
        groupId={this.$props.groupId}
        isInViewport={this.isInViewport}
        linkedZoomRange={this.linkedZoomRange}
        onDataZoomChange={this.handleDataZoomChange}
        onRestore={this.handleRestore}
        onSuccessLoad={this.handleSuccessLoad}
      />
    );
  },
});
