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
import { Component, Emit } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';

import ChartTitle from '../../components/chart-title/chart-title';
import { reviewInterval } from '../../utils';
import { VariablesService } from '../../utils/variable';
import CommonSimpleChart from '../common-simple-chart';
import TimeSeries from '../time-series/time-series';

// import { handleTimeRange } from 'monitor-pc/utils/index';
import type { ILegendItem, IPanelModel } from '../../typings';
import type { IUnifyQuerySeriesItem } from 'monitor-pc/pages/view-detail/utils';

import './event-log-chart.scss';

interface IEventLogChartEvents {
  onChangeHeight?: (v: number) => number;
}
interface ITextUnitSeriesItem {
  // 单位
  unit: number | string;
  // 值
  value: number | string;
}
@Component
class EventLogChart extends CommonSimpleChart {
  series: ITextUnitSeriesItem = { value: 0, unit: '' };
  empty = true;
  emptyText = '';
  tableData = [];
  columns = [];
  pagination = {
    current: 1,
    count: 100,
    limit: 10,
  };
  /* 此变量值用于点击图例时更新表格数据 */
  variables = {
    dimensions: [],
  };

  get timeSeriesPanel(): IPanelModel {
    return {
      ...this.panel,
      targets: this.panel.targets.filter(target => target.datasource === 'time_series'),
      options: {
        // todo 图例
        ...(this.panel?.options || {}),
        legend: {
          ...(this.panel?.options?.legend || {}),
          ...(this.panel.options?.dashboard_common?.static_width ? { displayMode: 'table' } : {}),
          placement: 'bottom',
        },
        time_series: {
          type: 'bar',
          echart_option: {
            color: ['#689DF3', '#4051A3'],
          },
        },
      },
    };
  }

  get tablePanel() {
    return {
      ...this.panel,
      targets: this.panel.targets.filter(target => target.datasource !== 'time_series'),
    };
  }

  async getPanelData(start_time?: string, end_time?: string): Promise<any> {
    this.beforeGetPanelData(start_time, end_time);
    this.handleLoadingChange(true);
    this.emptyText = window.i18n.t('加载中...').toString();
    try {
      this.unregisterObserver();
      // const { startTime, endTime } = handleTimeRange(this.timeRange);
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        data_format: 'scene_view',
        limit: this.pagination.limit,
        offset: (this.pagination.current - 1) * this.pagination.limit,
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
      };
      const variablesService = new VariablesService({
        ...this.scopedVars,
        ...this.variables,
        interval: reviewInterval(
          this.viewOptions.interval,
          params.end_time - params.start_time,
          this.panel.collect_interval
        ),
      });
      const promiseList = this.tablePanel.targets.map(item =>
        (this as any).$api[item.apiModule]
          [item.apiFunc](
            {
              ...variablesService.transformVariables(item.data),
              ...params,
              view_options: {
                ...this.viewOptions,
              },
            },
            { needMessage: false }
          )
          .then((res: any) => {
            this.series = res;
            this.clearErrorMsg();
            return res;
          })
          .catch((error: any) => {
            this.handleErrorMsgChange(error.msg || error.message);
            return null;
          })
      );
      const res = await Promise.all(promiseList);
      if (res?.[0]) {
        this.initialized = true;
        this.empty = false;
        this.columns = res[0].columns;
        this.tableData = res[0].data;
        this.pagination.count = res[0].total;
        return res;
      }
      this.emptyText = window.i18n.t('查无数据').toString();
      this.empty = true;
      return null;
    } catch (e: any) {
      this.empty = true;
      this.emptyText = window.i18n.t('出错了').toString();
      console.error(e);
      throw e;
    } finally {
      this.handleLoadingChange(false);
    }
  }

  handleTimeRangeChange() {
    this.pagination.current = 1;
    this.getPanelData();
  }

  /** 切换分页 */
  async handlePageChange(page: number) {
    const temp = this.pagination.current;
    this.pagination.current = page;
    await this.getPanelData().catch(() => {
      this.pagination.current = temp;
    });
  }
  /* 每页个数切换 */
  async handleLimitChange(limit: number) {
    const temp = this.pagination.limit;
    this.pagination.limit = limit;
    this.pagination.current = 1;
    await this.getPanelData().catch(() => {
      this.pagination.limit = temp;
    });
    this.$nextTick(() => {
      const height =
        56 + this.$el.querySelector('.time-series').clientHeight + this.$el.querySelector('.common-table').clientHeight;
      this.handleChangeHeight(height);
    });
  }
  /* 用于改变panel的高度 */
  @Emit('changeHeight')
  handleChangeHeight(height: number) {
    // 返回高度(px)
    return height;
  }

  handleEventLogSelectLegend(legendData: ILegendItem[]) {
    const series = (this.$refs.timeSeries as any).series as IUnifyQuerySeriesItem[];
    const selects = legendData.filter(item => item.show).map(item => item.name);
    if (selects.length === legendData.length) {
      this.variables.dimensions = [];
    } else {
      const temp = [];
      series.forEach(item => {
        if (selects.includes(item.name)) {
          temp.push(item.dimensions);
        }
      });
      this.variables.dimensions = temp as any;
    }
    this.pagination.current = 1;
    this.pagination.limit = 10;
    this.getPanelData();
  }

  render() {
    return (
      <div class='event-log-chart'>
        <ChartTitle
          class='draggable-handle text-header'
          dragging={this.panel.dragging}
          isInstant={this.panel.instant}
          showMore={false}
          title={this.panel.title}
          onUpdateDragging={() => this.panel.updateDragging(false)}
        />
        <div
          style={{ height: `${this.height}px` }}
          class='event-log-chart-main'
        >
          {[
            <TimeSeries
              key='time-series'
              ref='timeSeries'
              class='event-log-bar'
              needSetEvent={false}
              panel={this.timeSeriesPanel as any}
              showChartHeader={false}
              onSelectLegend={(v: ILegendItem[]) => this.handleEventLogSelectLegend(v)}
            />,
            !!this.tableData.length && (
              <CommonTable
                key='event-log-table'
                class='event-log-table'
                checkable={false}
                columns={this.columns as any}
                data={this.tableData}
                defaultSize='small'
                hasColumnSetting={false}
                pagination={this.pagination}
                paginationType='simple'
                showExpand={true}
                onLimitChange={this.handleLimitChange}
                onPageChange={this.handlePageChange}
              />
            ),
          ]}
        </div>
      </div>
    );
  }
}

export default ofType<IEventLogChartEvents>().convert(EventLogChart);
