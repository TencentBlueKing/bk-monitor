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
import { Component, Ref, Prop, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random, deepClone } from 'monitor-common/utils';
import MonitorDropdown from 'monitor-pc/components/monitor-dropdown';
import TimeRange, { type TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { getTimeDisplay } from 'monitor-pc/components/time-range/utils';
import { updateTimezone } from 'monitor-pc/i18n/dayjs';

import NewMetricChart from '../../metric-chart-view/metric-chart';
import { refreshList } from '../../metric-chart-view/utils';
import HeaderBox from '../header-box/index';
import CheckViewTable from './check-view-table';

import type { IDimensionItem, IRefreshItem, IResultItem } from '../../type';
import type { IMetricAnalysisConfig } from 'monitor-pc/pages/custom-escalation/new-metric-view/type';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

import './index.scss';
interface IViewConfig {
  config: IPanelModel;
  filterOption?: IMetricAnalysisConfig;
}
/** 维度下钻 */
interface IDrillAnalysisViewProps {
  dimensionsList?: IDimensionItem[];
  currentMethod?: string;
  panel?: IPanelModel;
  timeRangeData?: TimeRangeType;
}
interface IDrillAnalysisViewEvents {
  onClose?: () => void;
}
@Component
export default class CheckViewDetail extends tsc<IDrillAnalysisViewProps, IDrillAnalysisViewEvents> {
  // 图表panel实例
  @Prop({ default: () => ({}) }) panel: IViewConfig;
  @Prop({ default: () => ({}) }) timeRangeData: TimeRangeType;
  /** 当前汇聚方法 */
  @Prop({ default: '' }) currentMethod: string;
  @Ref('viewRef') viewRef: HTMLElement;
  @Ref('viewMain') viewMainRef: HTMLDivElement;
  @ProvideReactive('timeRange') timeRange: TimeRangeType = ['now-1h', 'now'];
  dimensionParams: Record<string, any> = {};
  /* 主动刷新图表 */
  chartKey = random(8);
  timezone = window.timezone;
  /* 刷新时间列表 */
  refreshList: IRefreshItem[] = [];
  refreshInterval = -1;
  /** 自动刷新定时器 */
  timer = null;
  panelData = {
    targets: [],
  };
  divHeight = 0;
  resizeObserver = null;
  showStatisticalValue = false;
  /* 拖拽数据 */
  drag = { height: 400, minHeight: 300, maxHeight: 550 };
  get titleName() {
    return this.panel?.config?.title || '';
  }

  mounted() {
    this.timeRange = this.timeRangeData;
    this.refreshList = refreshList;
    this.$nextTick(() => {
      /** 初始化数据 */
      this.panelData = deepClone(this.panel.config);
      this.dimensionParams = deepClone(this.panel.filterOption);
      if (this.viewMainRef) {
        // 初始化 ResizeObserver
        this.resizeObserver = new ResizeObserver(entries => {
          for (const entry of entries) {
            this.divHeight = entry.contentRect.height;
          }
        });
        // 观察目标元素
        this.resizeObserver.observe(this.viewMainRef);
      }
    });
    document.body.appendChild(this.viewRef);
    this.$once('hook:beforeDestroy', () => {
      this.viewRef?.parentNode?.removeChild(this.viewRef);
    });
  }
  beforeUnmount() {
    // 销毁观察器
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
  }

  beforeDestroy() {
    this.timer && clearInterval(this.timer);
  }
  /** 关闭按钮 */
  handleClose() {
    this.$emit('close');
  }

  /** 修改刷新间隔 */
  handleRefreshInterval(val: number) {
    this.refreshInterval = val;
    this.timer && clearInterval(this.timer);
    if (val > -1) {
      this.timer = setInterval(() => {
        this.handleImmediateRefresh();
      }, val);
    }
  }
  /** 手动刷新 */
  handleImmediateRefresh() {
    this.chartKey = random(8);
    this.getTableList();
  }
  /** 修改时间间隔 */
  handleTimeRangeChange(val: TimeRangeType) {
    this.timeRange = [...val];
    this.getTableList();
  }
  /** 修改时区 */
  handleTimezoneChange(timezone: string) {
    updateTimezone(timezone);
    this.getTableList();
  }
  getTableList() {}
  /** 支持上下拖拽 */
  handleResizing(height: number) {
    // this.drag.height = height;
    // this.chartKey = random(8);
  }
  /** 设置panel的值 */
  setPanelConfigAndRefresh(keys: string, value) {
    const keysArray = keys.split('.');
    let current = this.panelData.targets[0].query_configs[0];

    for (let i = 0; i < keysArray.length; i++) {
      const key = keysArray[i];
      if (i === keysArray.length - 1) {
        current[key] = value;
      } else {
        if (!current[key]) {
          current[key] = {};
        }
        current = current[key];
      }
    }
    this.panelData = deepClone(this.panelData);
  }
  /** 修改过滤值的时候重置panel的数据 */
  handleDimensionParamsChange(payload: any) {
    const { group_by, common_conditions, limit, where, compare } = payload;
    const commonConditions = {};
    common_conditions.map(item => {
      commonConditions[item.key] = item.value;
    });

    this.setPanelConfigAndRefresh(
      'group_by',
      group_by.map(item => item.field)
    );
    this.setPanelConfigAndRefresh('where', where);
    this.setPanelConfigAndRefresh('filter_dict.common_filter', commonConditions);
    this.setPanelConfigAndRefresh('functions', [
      {
        id: limit.function,
        params: [
          {
            id: 'n',
            value: limit.limit,
          },
        ],
      },
    ]);
    this.panelData.targets[0].function = !compare.type ? {} : { time_compare: compare.offset };
    this.dimensionParams = Object.freeze(payload);
  }

  /* 获取原始数据 */
  handleGetSeriesData(res) {
    const dataSeries = (res.series || []).map(set => {
      const { datapoints, dimensions, target, ...setData } = set;
      const metric = res.metrics[0];
      return {
        metric,
        dimensions,
        datapoints,
        ...setData,
        target,
      };
    });
    const dataList = dataSeries.reduce((data, item) => data.concat(item), []);
    console.log(res, 'res', dataList);
  }

  render() {
    return (
      <div
        ref='viewRef'
        class='check-view-detail'
      >
        <div class='check-view-detail-head'>
          <i
            class='icon-monitor icon-back-left close-btn'
            onClick={this.handleClose}
          />
          {this.$t('查看大图')}
          <span class='detail-head-title'>{this.titleName}</span>
          <div class='detail-head-right'>
            {/* 时间工具栏 */}
            {window.__BK_WEWEB_DATA__?.lockTimeRange ? (
              <span class='dashboard-tools-timerange'>{getTimeDisplay(this.timeRange)}</span>
            ) : (
              <TimeRange
                class='filter-tools-timerange'
                timezone={this.timezone}
                value={this.timeRange}
                onChange={this.handleTimeRangeChange}
                onTimezoneChange={this.handleTimezoneChange}
              />
            )}
            <span class='right-line' />
            <MonitorDropdown
              class='filter-tools-interval'
              icon='icon-zidongshuaxin'
              isRefreshInterval={true}
              list={this.refreshList}
              text-active={this.refreshInterval !== -1}
              value={this.refreshInterval}
              on-change={this.handleRefreshInterval}
              on-on-icon-click={this.handleImmediateRefresh}
            />
          </div>
        </div>
        <HeaderBox
          dimenstionParams={this.dimensionParams}
          exclude={['metric']}
          isShowExpand={false}
          onChange={this.handleDimensionParamsChange}
        >
          <template slot='actionExtend'>
            <bk-checkbox v-model={this.showStatisticalValue}>{this.$t('展示统计值')}</bk-checkbox>
          </template>
        </HeaderBox>
        <div
          ref='viewMain'
          class='check-view-main'
        >
          <bk-resize-layout
            extCls='check-view-main-layout'
            slot='aside'
            border={false}
            initial-divide={'50%'}
            max={680}
            min={340}
            placement='top'
            onResizing={this.handleResizing}
          >
            <div
              class='check-view-main-chart'
              slot='aside'
            >
              <NewMetricChart
                key={this.chartKey}
                style={{ height: `${this.drag.height - 30}px` }}
                chartHeight={this.drag.height}
                currentMethod={this.currentMethod}
                isShowLegend={true}
                isToolIconShow={false}
                panel={this.panelData}
                onSeriesData={this.handleGetSeriesData}
              />
            </div>
            <div
              style={{ height: `${this.divHeight - this.drag.height - 4}px` }}
              class='check-view-main-table'
              slot='main'
            >
              <CheckViewTable />
            </div>
          </bk-resize-layout>
        </div>
      </div>
    );
  }
}
