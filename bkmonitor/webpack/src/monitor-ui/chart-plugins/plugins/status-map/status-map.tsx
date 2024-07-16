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
import { Component } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { deepClone } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

// import 'echarts/map/js/china.js';
import Mpalegend from '../../components/chart-legend/map-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { CHINA_MAP_OPTIONS } from '../../constants';
import { reviewInterval } from '../../utils';
import { VariablesService } from '../../utils/variable';
import MonitorBaseEchart from '../base-echart';
import { CommonSimpleChart } from '../common-simple-chart';

import type { ICommonCharts, IExtendDataItem, MonitorEchartOptions, PanelModel } from '../../typings';

import './status-map.scss';

interface IStatusMapProps {
  panel: PanelModel;
}

@Component
class StatusMap extends CommonSimpleChart implements ICommonCharts {
  chartOption: MonitorEchartOptions;
  inited = false;
  metrics = [];
  legendData = [];
  emptyText = window.i18n.tc('查无数据');
  empty = true;
  extendData: IExtendDataItem[] = [];
  colorList = ['rgba(45, 203, 86)', 'rgba(255, 235, 0)', 'rgba(255, 156, 1)', 'rgba(234, 54, 54)'];
  areaColorList = [
    'rgba(45, 203, 86, 0.2)',
    'rgba(255, 235, 0, 0.2)',
    'rgba(255, 156, 1, 0.2)',
    'rgba(234, 54, 54, 0.2)',
  ];

  getStatusColor(status: string) {
    return status;
  }

  updateChartOption(data) {
    const seriesData = data.map(data => ({
      ...data,
      itemStyle: {
        areaColor: this.areaColorList[data.status - 1],
      },
      emphasis: {
        itemStyle: {
          areaColor: this.areaColorList[data.status - 1],
          borderColor: this.colorList[data.status - 1],
        },
      },
    }));

    this.chartOption = deepClone(CHINA_MAP_OPTIONS);
    this.chartOption.series[0] = {
      ...this.chartOption.series[0],
      data: seriesData,
      tooltip: {
        formatter(params: any) {
          if (isNaN(params.value)) return '';
          return `${params.name}<br />${params.value}${params.data?.unit}`;
        }, // 数据格式化
      },
    };
  }

  async getPanelData(start_time?: string, end_time?: string) {
    if (!this.isInViewPort()) {
      if (this.intersectionObserver) {
        this.unregisterOberver();
      }
      this.registerObserver(start_time, end_time);
      return;
    }
    if (this.isFetchingData) return;
    this.isFetchingData = true;
    this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    try {
      this.unregisterOberver();
      let series = [];
      let extendData = [];
      let legend = [];
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
      };
      const interval = reviewInterval(
        this.viewOptions.interval,
        params.end_time - params.start_time,
        this.panel.collect_interval
      );
      const variablesService = new VariablesService({
        ...this.scopedVars,
        interval,
      });
      const promiseList = this.panel.targets.map(item =>
        (this as any).$api[item.apiModule]
          [item.apiFunc](
            {
              ...variablesService.transformVariables(item.data, {
                ...this.viewOptions.filters,
                ...this.viewOptions,
                interval,
              }),
              ...params,
            },
            { needMessage: false }
          )
          .then(res => {
            series = res.series || [];
            extendData = res.extend_data || [];
            legend = res.legend || [];
            this.clearErrorMsg();
          })
          .catch(error => {
            this.handleErrorMsgChange(error.msg || error.message);
          })
      );
      const res = await Promise.all(promiseList).catch(() => false);
      if (res && series.length) {
        this.updateChartOption(series);
        this.extendData = extendData;
        this.legendData = legend.map(item => ({
          ...item,
          color: this.colorList[item.status - 1],
        }));
        this.inited = true;
        this.empty = false;
      } else {
        this.emptyText = window.i18n.tc('查无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
      console.error(e);
    }
    this.isFetchingData = false;
    this.handleLoadingChange(false);
  }

  render() {
    return (
      <div class='status-map'>
        <ChartHeader
          class='draggable-handle'
          draging={this.panel.draging}
          isInstant={this.panel.instant}
          metrics={this.metrics}
          showMore={false}
          subtitle={this.panel.subTitle || ''}
          title={this.panel.title}
          onUpdateDragging={() => this.panel.updateDraging(false)}
        />

        {!this.empty ? (
          <div class='status-map-content'>
            <div class='status-map-message-wrap'>
              <div class='status-map-message'>
                <div class='extend-content'>
                  {this.extendData.map(item => (
                    <div class='extend-item'>
                      <div class='extend-item'>
                        <span class='extend-name'>{item.name}</span>
                        <span class='extend-value'>{item.value}</span>
                        <span class='extend-unit'>{item.unit}</span>
                      </div>
                    </div>
                  ))}
                </div>
                <Mpalegend legendData={this.legendData} />
              </div>
            </div>
            <div
              ref='chart'
              class='chart-instance'
            >
              <MonitorBaseEchart
                ref='baseChart'
                width={this.width}
                height={this.height}
                options={this.chartOption}
              />
            </div>
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}

export default ofType<IStatusMapProps>().convert(StatusMap);
