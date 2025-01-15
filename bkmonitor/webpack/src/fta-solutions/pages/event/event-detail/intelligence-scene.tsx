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
import { Component, Prop, Provide, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { connect, disconnect } from 'echarts/core';
import { multiAnomalyDetectGraph } from 'monitor-api/modules/alert';
import { random } from 'monitor-common/utils';
import { DEFAULT_TIME_RANGE } from 'monitor-pc/components/time-range/utils';
import ChartWrapper from 'monitor-ui/chart-plugins/components/chart-wrapper';
import { type IViewOptions, PanelModel } from 'monitor-ui/chart-plugins/typings';

import { createAutoTimerange } from './aiops-chart';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './intelligence-scene.scss';

interface IProps {
  params: any;
}

@Component
export default class IntelligenceScene extends tsc<IProps> {
  @Prop({ type: Object, default: () => ({ id: 0, bk_biz_id: '' }) }) params: any;

  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];
  // 数据时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  // 是否展示复位
  @ProvideReactive('showRestore') showRestore = false;
  // 是否开启（框选/复位）全部操作
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;

  panels: PanelModel[] = [];
  dashboardId = random(10);

  // 时间范围缓存用于复位功能
  cacheTimeRange = [];

  loading = false;

  // 框选图表事件范围触发（触发后缓存之前的时间，且展示复位按钮）
  @Provide('handleChartDataZoom')
  handleChartDataZoom(value) {
    if (JSON.stringify(this.timeRange) !== JSON.stringify(value)) {
      this.cacheTimeRange = JSON.parse(JSON.stringify(this.timeRange));
      this.timeRange = value;
      this.showRestore = true;
    }
  }
  @Provide('handleRestoreEvent')
  handleRestoreEvent() {
    const cacheTime = JSON.parse(JSON.stringify(this.cacheTimeRange));
    this.timeRange = cacheTime;
    this.showRestore = false;
  }

  timeRangeInit() {
    const interval = this.params.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
    const { startTime, endTime } = createAutoTimerange(this.params.begin_time, this.params.end_time, interval);
    const currentTarget: Record<string, any> = {
      bk_target_ip: '0.0.0.0',
      bk_target_cloud_id: '0',
    };
    this.params.dimensions.forEach(item => {
      if (item.key === 'bk_host_id') {
        currentTarget.bk_host_id = item.value;
      }
      if (['bk_target_ip', 'ip', 'bk_host_id'].includes(item.key)) {
        currentTarget.bk_target_ip = item.value;
      }
      if (['bk_cloud_id', 'bk_target_cloud_id', 'bk_host_id'].includes(item.key)) {
        currentTarget.bk_target_cloud_id = item.value;
      }
    });
    this.viewOptions = {
      interval,
      current_target: currentTarget,
      strategy_id: this.params?.strategy_id,
    };
    this.timeRange = [startTime, endTime];
  }

  async created() {
    this.loading = true;
    const data = await multiAnomalyDetectGraph({
      alert_id: this.params.id,
      bk_biz_id: this.params.bk_biz_id,
    }).catch(() => []);
    this.timeRangeInit();
    const result = data.map(item => {
      return {
        ...item,
        type: 'performance-chart',
        dashboardId: this.dashboardId,
        targets: item.targets.map(target => ({
          ...target,
          data: {
            ...target.data,
            id: this.params.id,
            bk_biz_id: this.params.bk_biz_id,
          },
          datasource: 'time_series',
        })),
        options: {
          time_series: {
            custom_timerange: true,
            hoverAllTooltips: true,
            YAxisLabelWidth: 70,
            needAllAlertMarkArea: true,
          },
        },
      };
    });
    this.panels = result.map(item => new PanelModel(item));
    connect(this.dashboardId.toString());
    this.loading = false;
  }

  handledblClick() {
    this.timeRangeInit();
    // this.timeRange = DEFAULT_TIME_RANGE;
    this.showRestore = false;
  }

  destroyed() {
    disconnect(this.dashboardId.toString());
  }

  render() {
    return (
      <div
        class='intelligence-scene-view-component'
        v-bkloading={{
          isLoading: this.loading,
        }}
      >
        {this.panels.map((panel, index) => (
          <div
            key={index}
            class='intelligenc-scene-item'
          >
            <ChartWrapper
              needCheck={false}
              panel={panel}
              onDblClick={this.handledblClick}
            />
          </div>
        ))}
      </div>
    );
  }
}
