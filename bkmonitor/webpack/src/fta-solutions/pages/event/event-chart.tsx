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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import MonitorEcharts from '../../../monitor-ui/monitor-echarts/monitor-echarts.vue';

import { ICommonItem, SearchType } from './typings/event';

import './event-chart.scss';

interface IEventChartProps {
  chartInterval: string | number;
  getSeriesData: () => Promise<{ unit: string; series: any[] }>;
  intervalList?: ICommonItem[];
  chartKey: string;
  searchType: SearchType;
}

interface IEventChartEvent {
  onIntervalChange: string | number;
}
@Component({
  components: { MonitorEcharts }
})
export default class EventChart extends tsc<IEventChartProps, IEventChartEvent> {
  @Prop({
    default: () => [
      {
        id: 'auto',
        name: 'Auto'
      },
      {
        id: 60,
        name: '1 min'
      },
      {
        id: 5 * 60,
        name: '5 min'
      },
      {
        id: 60 * 60,
        name: '1 h'
      },
      {
        id: 24 * 60 * 60,
        name: '1 d'
      }
    ]
  })
  intervalList: ICommonItem[];
  @Prop({ default: 'auto', type: [String, Number] }) chartInterval: string | number;
  @Prop({ required: true, type: [Function] }) getSeriesData: () => Promise<any[]>;
  @Prop({ required: true, type: [String] }) chartKey: string;
  @Prop({ required: true, type: String }) searchType: SearchType;

  expand = true;
  chartOption = {
    tool: {
      show: true
    },
    grid: {
      right: '20'
    }
  };
  get chartColors() {
    return this.searchType === 'action'
      ? ['#8DD3B5', '#F59E9E', '#FED694', '#A3C4FD', '#CBCDD2']
      : ['#F59E9E', '#8DD3B5', '#CBCDD2'];
  }
  @Emit('intervalChange')
  handleIntervalChange(v: number | string) {
    return v;
  }
  handleExpandChange(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      this.expand = !this.expand;
      this.chartOption.tool.show = this.expand;
    }
  }
  render() {
    return (
      <div class={['event-chart', { 'is-expand': !this.expand }]}>
        <monitor-echarts
          height={200}
          key={this.chartKey}
          title={this.searchType === 'action' ? this.$t('执行趋势') : this.$t('告警趋势')}
          colors={this.chartColors}
          getSeriesData={this.getSeriesData}
          options={this.chartOption}
          chart-type='bar'
          needFullScreen={false}
        >
          <div
            slot='title'
            class='event-chart-title'
            onClick={this.handleExpandChange}
          >
            <i
              onClick={this.handleExpandChange}
              class={['icon-monitor icon-mc-triangle-down chart-icon', { 'is-expand': this.expand }]}
            />
            {this.searchType === 'action' ? this.$t('执行趋势') : this.$t('告警趋势')}
            {this.expand && [
              <span class='interval-label'>{this.$t('汇聚周期')}</span>,
              <bk-select
                class='interval-select'
                size='small'
                behavior='simplicity'
                clearable={false}
                value={this.chartInterval}
                onChange={this.handleIntervalChange}
              >
                {this.intervalList.map(item => (
                  <bk-option
                    id={item.id}
                    key={item.id}
                    name={item.name}
                  >
                    {item.name}
                  </bk-option>
                ))}
              </bk-select>
            ]}
          </div>
        </monitor-echarts>
      </div>
    );
  }
}
