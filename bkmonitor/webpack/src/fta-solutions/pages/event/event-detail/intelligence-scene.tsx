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
import { Component, Prop, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { multiAnomalyDetectGraph } from '../../../../monitor-api/modules/alert';
import { random } from '../../../../monitor-common/utils';
import { TimeRangeType } from '../../../../monitor-pc/components/time-range/time-range';
import { DEFAULT_TIME_RANGE } from '../../../../monitor-pc/components/time-range/utils';
import ChartWrapper from '../../../../monitor-ui/chart-plugins/components/chart-wrapper';
import { IViewOptions, PanelModel } from '../../../../monitor-ui/chart-plugins/typings';

import { createAutoTimerange } from './aiops-chart';

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

  panels: PanelModel[] = [];
  dashboardId = random(10);
  loading = false;

  async created() {
    this.loading = true;
    const data = await multiAnomalyDetectGraph({
      alert_id: this.params.id,
      bk_biz_id: this.params.bk_biz_id
    }).catch(() => []);
    const interval = this.params.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
    const { startTime, endTime } = createAutoTimerange(this.params.begin_time, this.params.end_time, interval);
    this.timeRange = [startTime, endTime];
    const result = data.map(item => {
      return {
        ...item,
        dashboardId: this.dashboardId,
        id: this.dashboardId,
        targets: item.targets.map(target => ({
          ...target,
          data: {
            ...target.data,
            id: this.params.id,
            bk_biz_id: this.params.bk_biz_id
          },
          datasource: 'time_series'
        }))
      };
    });
    this.panels = result.map(item => new PanelModel(item));
    this.loading = false;
  }

  render() {
    return (
      <div
        class='intelligence-scene-view-component'
        v-bkloading={{
          isLoading: this.loading
        }}
      >
        {this.panels.map((panel, index) => (
          <div
            class='intelligenc-scene-item'
            key={index}
          >
            <ChartWrapper
              panel={panel}
              needCheck={false}
            ></ChartWrapper>
          </div>
        ))}
      </div>
    );
  }
}
