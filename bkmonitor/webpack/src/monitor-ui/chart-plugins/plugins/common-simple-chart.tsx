/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import { Component, Inject, InjectReactive, Mixins, Prop, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import { ChartLoadingMixin, ErrorMsgMixins, IntersectionMixin, LegendMixin, ResizeMixin, ToolsMixin } from '../mixins';

import type { ICommonCharts, IViewOptions, PanelModel } from '../typings';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { IQueryData } from 'monitor-pc/pages/monitor-k8s/typings';

@Component
export class CommonSimpleChart
  extends Mixins<ChartLoadingMixin & ErrorMsgMixins & IntersectionMixin & LegendMixin & ResizeMixin & ToolsMixin>(
    IntersectionMixin,
    ChartLoadingMixin,
    ToolsMixin,
    ResizeMixin,
    LegendMixin,
    ErrorMsgMixins
  )
  implements ICommonCharts
{
  // 时序视图panel实例
  @Prop({ required: false }) readonly panel: PanelModel;
  // 高度
  height = 100;
  // 宽度度
  width = 300;
  // 自动刷新定时任务
  refreshIntervalInstance = null;
  // 是否配置初始化
  initialized = false;
  // 顶层注入数据
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  @InjectReactive('refreshInterval') readonly refreshInterval!: number;
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  @InjectReactive('refreshImmediate') readonly refreshImmediate: string;
  @InjectReactive('timezone') readonly timezone: string;
  @InjectReactive('queryData') readonly queryData!: IQueryData;
  /** 更新queryData */
  @Inject('handleUpdateQueryData') handleUpdateQueryData: (queryData: IQueryData) => void;
  // 当前使用的业务id
  @InjectReactive('bkBizId') readonly bkBizId: number | string;

  // 变量对应
  get scopedVars() {
    return {
      ...(this.viewOptions || {}),
      ...(this.viewOptions?.filters || {}),
      ...(this.viewOptions?.variables || {}),
      ...(this.viewOptions?.current_target || []),
      ...(this.viewOptions?.variables?.current_target || {}),
      ...{ current_target: this.viewOptions?.filters || {} },
    };
  }

  @Watch('viewOptions')
  // 用于配置后台图表数据的特殊设置
  handleFieldDictChange(val: IViewOptions, old: IViewOptions) {
    if (val && Object.keys(val).some(key => val[key] !== old?.[key])) {
      this.getPanelData();
    }
  }
  @Watch('timeRange')
  // 数据时间间隔
  handleTimeRangeChange() {
    this.getPanelData();
  }
  @Watch('refreshInterval', { immediate: true })
  // 数据刷新间隔
  handleRefreshIntervalChange(v: number) {
    if (this.refreshIntervalInstance) {
      window.clearInterval(this.refreshIntervalInstance);
    }
    if (!v || +v < 1000 * 60) return; // 最小间隔1分钟 刷新一次
    this.refreshIntervalInstance = window.setInterval(() => {
      this.initialized && this.getPanelData();
    }, v);
  }
  @Watch('refreshImmediate')
  // 立刻刷新
  handleRefreshImmediateChange(v: string) {
    if (v) this.getPanelData();
  }
  @Watch('timezone')
  // 时区变更刷新图表
  handleTimezoneChange(v: string) {
    if (v) this.getPanelData();
  }
  beforeGetPanelData(...p: any) {
    return new Promise(resolve => {
      if (!this.isInViewPort()) {
        if (this.intersectionObserver) {
          this.unregisterObserver();
        }
        this.registerObserver(...p);
        resolve(false);
      }
      resolve(true);
    });
  }
  async getPanelData(start_time?: string, end_time?: string) {
    this.beforeGetPanelData(start_time, end_time);
  }
  /* 粒度计算 */
  downSampleRangeComputed(downSampleRange: string, timeRange: number[], api: string) {
    if (downSampleRange === 'raw' || !['unifyQuery', 'graphUnifyQuery'].includes(api)) {
      return undefined;
    }
    if (downSampleRange === 'auto') {
      let width = 1;
      if (this.$refs.chart) {
        width = (this.$refs.chart as Element).clientWidth;
      } else {
        width = this.$el.clientWidth - (this.panel.options?.legend?.placement === 'right' ? 320 : 0);
      }
      if (width <= 0) {
        return undefined;
      }
      const size = (timeRange[1] - timeRange[0]) / width;
      return size > 0 ? `${Math.ceil(size)}s` : undefined;
    }
    return downSampleRange;
  }
  commonChartTooltipsPosition(pos, params, dom, rect, size: any) {
    const { contentSize } = size;
    const chartRect = this.$el.getBoundingClientRect();
    const posRect = {
      x: chartRect.x + +pos[0],
      y: chartRect.y + +pos[1],
    };
    const position = {
      left: 0,
      top: 0,
    };
    const canSetBottom = window.innerHeight - posRect.y - contentSize[1];
    if (canSetBottom > 0) {
      position.top = +pos[1] - Math.min(20, canSetBottom);
    } else {
      position.top = +pos[1] + canSetBottom - 20;
    }
    const canSetLeft = window.innerWidth - posRect.x - contentSize[0];
    if (canSetLeft > 0) {
      position.left = +pos[0] + Math.min(20, canSetLeft);
    } else {
      position.left = +pos[0] - contentSize[0] - 20;
    }
    return position;
  }
  render() {
    return <div />;
  }
}

export default ofType<{ panel?: PanelModel }>().convert(CommonSimpleChart);
