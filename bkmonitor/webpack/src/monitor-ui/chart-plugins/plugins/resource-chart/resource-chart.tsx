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
import { getDataSourceConfig } from 'monitor-api/modules/grafana';
import { deepClone } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import ChartHeader from '../../components/chart-title/chart-title';
import { handleRelateAlert } from '../../utils/menu';
import { VariablesService } from '../../utils/variable';
import { CommonSimpleChart } from '../common-simple-chart';

import type {
  ChartTitleMenuType,
  IExtendMetricData,
  IMenuItem,
  IResourceData,
  ITitleAlarm,
  PanelModel,
} from '../../typings';

import './resource-chart.scss';

interface IResourceChartEvent {
  onFullScreen: PanelModel;
  onCollectChart?: () => void; // 保存到仪表盘
}
interface IResourceChartProps {
  panel: PanelModel;
  showHeaderMoreTool?: boolean;
}
@Component
class ResourceChart extends CommonSimpleChart {
  data: IResourceData[][] = [];
  emptyText = window.i18n.t('加载中...');
  empty = true;
  metrics: IExtendMetricData[] = [];

  get menuList() {
    const defaultMenu: ChartTitleMenuType[] = ['explore', 'relate-alert'];
    if (this.panel.options?.alert_filterable?.save_to_dashboard) defaultMenu.push('save');
    return defaultMenu;
  }

  /**
   * @description: 获取图表数据
   */
  async getPanelData(start_time?: string, end_time?: string) {
    this.handleLoadingChange(true);
    this.empty = true;
    this.emptyText = window.i18n.t('加载中...');
    try {
      this.unregisterObserver();
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
      };
      const variablesService = new VariablesService({
        ...this.scopedVars,
      });
      const promiseList = this.panel.targets.map(item =>
        (this as any).$api[item.apiModule]
          ?.[item.apiFunc](
            {
              ...variablesService.transformVariables(item.data),
              ...params,
              view_options: {
                ...this.viewOptions,
              },
            },
            { needMessage: false }
          )
          .then(res => {
            this.clearErrorMsg();
            return res;
          })
          .catch(error => {
            this.handleErrorMsgChange(error.msg || error.message);
          })
      );
      const res = await Promise.all(promiseList);
      if (res?.every?.(item => item?.length)) {
        this.initialized = true;
        this.empty = false;
        this.data = res;
      } else {
        this.emptyText = window.i18n.t('查无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.t('出错了');
      console.error(e);
    }
    this.handleLoadingChange(false);
  }

  /**
   * @description: 图表头部工具栏事件
   * @param {IMenuItem} menuItem
   * @return {*}
   */
  handleMenuToolsSelect(menuItem: IMenuItem) {
    const variablesService = new VariablesService({ ...this.viewOptions });
    switch (menuItem.id) {
      case 'save': // 保存到仪表盘
        this.handleCollectChart();
        break;
      case 'explore': // 跳转数据检索
        this.handleExplore(this.panel, {
          ...this.viewOptions.filters,
          ...(this.viewOptions.filters?.current_target || {}),
          ...this.viewOptions,
          ...this.viewOptions.variables,
        });
        break;
      case 'relate-alert': // 查看相关告警
        if (this.panel.options?.alert_filterable && this.panel.options?.alert_filterable.filter_type === 'event') {
          this.eventHandleRelateAlert();
        } else {
          this.panel?.targets?.forEach(target => {
            if (target.data?.query_configs?.length) {
              let queryConfig = deepClone(target.data.query_configs);
              queryConfig = variablesService.transformVariables(queryConfig);
              target.data.query_configs = queryConfig;
            }
          });
          handleRelateAlert(this.panel, this.timeRange);
        }
        break;
      default:
        break;
    }
  }

  async eventHandleRelateAlert() {
    const alertFilterable = this.panel.options?.alert_filterable;
    // 变量替换
    const variablesService = new VariablesService({
      ...this.viewOptions.filters,
      ...(this.viewOptions.filters?.current_target || {}),
      ...this.viewOptions,
      ...this.viewOptions.variables,
    });
    const {
      // eslint-disable-next-line @typescript-eslint/naming-convention
      data_source_label,
      // eslint-disable-next-line @typescript-eslint/naming-convention
      data_type_label,
      // eslint-disable-next-line @typescript-eslint/naming-convention
      bcs_cluster_id,
    } = variablesService.transformVariables(alertFilterable.data);
    const res = await getDataSourceConfig({
      data_source_label,
      data_type_label,
    });
    // 集群ID 换 数据ID
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const result_table_id = res.find(item => item.name.includes(bcs_cluster_id))?.id;
    const query =
      alertFilterable.event_center?.query_string.map(
        item => `指标ID : ${data_source_label}.${data_type_label}.${result_table_id}.${item.metric}`
      ) || [];
    query.length &&
      window.open(
        location.href.replace(
          location.hash,
          `#/event-center?queryString=${query.join(' or ')}&from=${this.timeRange[0]}&to=${this.timeRange[1]}`
        )
      );
  }

  /**
   * @description: 点击所有指标
   * @param {*}
   * @return {*}
   */
  handleAllMetricClick() {
    this.handleAddStrategy(this.panel, null, this.viewOptions, true);
  }

  /**
   * @description: 点击单个指标
   * @param {IExtendMetricData} metric
   * @return {*}
   */
  handleMetricClick(metric: IExtendMetricData) {
    this.handleAddStrategy(this.panel, metric, this.viewOptions);
  }

  handleJump(item: IResourceData) {
    if (!item.link?.url) return;
    let { target } = item.link;
    if (!target) target = '_target';
    if (target[0] !== '_') target = `_${target}`;
    window.open(item.link.url, target);
  }

  /** 处理点击左侧响铃图标 跳转策略的逻辑 */
  handleAlarmClick(alarmStatus: ITitleAlarm) {
    const metricIds = this.metrics.map(item => item.metric_id);
    switch (alarmStatus.status) {
      case 0:
        this.handleAddStrategy(this.panel, null, this.viewOptions, true);
        break;
      case 1:
        window.open(location.href.replace(location.hash, `#/strategy-config?metricId=${JSON.stringify(metricIds)}`));
        break;
      case 2: {
        const eventTargetStr = alarmStatus.targetStr;

        window.open(
          location.href.replace(
            location.hash,
            `#/event-center?queryString=${metricIds.map(item => `metric : "${item}"`).join(' AND ')}${
              eventTargetStr ? ` AND ${eventTargetStr}` : ''
            }&activeFilterId=NOT_SHIELDED_ABNORMAL&from=${this.timeRange[0]}&to=${this.timeRange[1]}`
          )
        );
        break;
      }
    }
  }

  chartContent() {
    return (
      <div class='resource-chart-content'>
        {this.data[0].map(item => (
          <div
            style={{ cursor: item.link ? 'pointer' : '' }}
            class='content-item'
            onClick={() => this.handleJump(item)}
          >
            <div
              style={{ color: item.color || '#313238' }}
              class={'content-header'}
            >
              <span class='item-val'>{item.value}</span>
              {item.tips && (
                <i
                  class='bk-icon icon-exclamation-circle-shape item-icon'
                  v-bk-tooltips={{
                    content: item.tips,
                    showOnInit: false,
                    trigger: 'mouseenter',
                    placements: ['top'],
                    allowHTML: false,
                  }}
                />
              )}
            </div>
            {item.name && <span class='item-title'>{item.name}</span>}
          </div>
        ))}
      </div>
    );
  }

  render() {
    return (
      <div class='resource-chart'>
        <ChartHeader
          class='draggable-handle'
          dragging={this.panel.dragging}
          isInstant={this.panel.instant && this.showHeaderMoreTool}
          menuList={this.menuList}
          metrics={this.metrics}
          showMore={!this.empty && this.showHeaderMoreTool && !!this.panel.options?.alert_filterable}
          title={this.panel.title}
          onAlarmClick={this.handleAlarmClick}
          onAllMetricClick={this.handleAllMetricClick}
          onMenuClick={this.handleMenuToolsSelect}
          onMetricClick={this.handleMetricClick}
        />
        {!this.empty ? this.chartContent() : <span class='empty-chart'>{this.emptyText}</span>}
      </div>
    );
  }
}
export default ofType<IResourceChartProps, IResourceChartEvent>().convert(ResourceChart);
