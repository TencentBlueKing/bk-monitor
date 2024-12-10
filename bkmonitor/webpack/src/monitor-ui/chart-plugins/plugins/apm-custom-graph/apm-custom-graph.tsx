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
import { Component, Watch } from 'vue-property-decorator';

import dayjs from 'dayjs';
import { start } from 'monitor-api/modules/apm_meta';
import { applicationInfoByAppName, metaConfigInfo } from 'monitor-api/modules/apm_meta';
import { Debounce, deepClone } from 'monitor-common/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import ListLegend from '../../components/chart-legend/common-legend';
import TableLegend from '../../components/chart-legend/table-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { handleRelateAlert } from '../../utils/menu';
import { reviewInterval } from '../../utils/utils';
import { VariablesService } from '../../utils/variable';
import BaseEchart from '../monitor-base-echart';
import TimeSeries from '../time-series/time-series';
import StatusTab from './status-tab';

import type { IMenuItem, IPanelModel } from '../../typings';

import './apm-custom-graph.scss';
const APM_CUSTOM_METHODS = ['SUM', 'AVG', 'MAX', 'MIN', 'INC'] as const;
@Component
export default class CustomChart extends TimeSeries {
  methodList = APM_CUSTOM_METHODS.map(method => ({
    id: method,
    name: method,
  }));
  method = this.viewOptions?.method || 'AVG';

  isEnabledMetric = false;
  isEnabledMetricLoading = false;
  guideUrl = ''; // 接入指引url
  noDataLoading = false;
  isSingleNoData = false;
  applicationId = -1;

  @Watch('viewOptions')
  // 用于配置后台图表数据的特殊设置
  handleFieldDictChange() {
    this.noDataInit();
    this.getPanelData();
  }
  handleMethodChange(method: (typeof APM_CUSTOM_METHODS)[number]) {
    this.method = method;
    this.customScopedVars = {
      method,
    };
    this.getPanelData();
  }

  /**
   * @description 判断是否是无数据(并且是单图模式), 展示自定义指标无数据提示
   */
  @Debounce(300)
  async noDataInit() {
    this.isSingleNoData = this.isSingleChart && !this.panel.targets.length;
    if (this.isSingleNoData) {
      this.noDataLoading = true;
      const { app_name } = this.viewOptions.filters as any;
      const data = await applicationInfoByAppName({
        app_name,
      }).catch(() => {});
      this.isEnabledMetric = !!data?.is_enabled_metric;
      this.applicationId = data?.application_id || -1;
      const config = await metaConfigInfo().catch(() => ({}));
      this.guideUrl = config?.setup?.guide_url?.access_url || '';
      this.noDataLoading = false;
    }
  }

  async handleEmptyEvent() {
    if (this.isEnabledMetric) {
      window.open(this.guideUrl);
    } else {
      if (this.isEnabledMetricLoading) {
        return;
      }
      this.isEnabledMetricLoading = true;
      await start({ application_id: this.applicationId, type: 'metric' })
        .then(() => {
          this.isEnabledMetric = true;
        })
        .finally(() => {
          this.isEnabledMetricLoading = false;
        });
    }
  }
  /**
   * @description: 图表头部工具栏事件
   * @param {IMenuItem} menuItem
   * @return {*}
   */
  handleMenuToolsSelect(menuItem: IMenuItem) {
    const variablesService = new VariablesService({ ...this.viewOptions, ...this.customScopedVars });
    switch (menuItem.id) {
      case 'save': // 保存到仪表盘
        this.handleCollectChart();
        break;
      case 'screenshot': // 保存到本地
        setTimeout(() => {
          this.handleStoreImage(this.panel.title || '测试');
        }, 300);
        break;
      case 'fullscreen': {
        // 大图检索
        let copyPanel: IPanelModel = JSON.parse(JSON.stringify(this.panel));
        const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);

        const variablesService = new VariablesService({
          ...this.viewOptions.filters,
          ...(this.viewOptions.filters?.current_target || {}),
          ...this.viewOptions,
          ...this.viewOptions.variables,
          interval: reviewInterval(
            this.viewOptions.interval,
            dayjs.tz(endTime).unix() - dayjs.tz(startTime).unix(),
            this.panel.collect_interval
          ),
          ...this.customScopedVars,
        });
        copyPanel = variablesService.transformVariables(copyPanel);
        copyPanel.targets.forEach((t, tIndex) => {
          const queryConfigs = this.panel.targets[tIndex].data.query_configs;
          t.data.query_configs.forEach((q, qIndex) => {
            q.functions = JSON.parse(JSON.stringify(queryConfigs[qIndex].functions));
          });
        });
        this.handleFullScreen(copyPanel as any);
        break;
      }
      case 'explore': // 跳转数据检索
        {
          const data = this.panel.toDataRetrieval();
          const url = `${location.origin}${location.pathname.toString()}?bizId=${
            this.panel.targets?.[0]?.data?.bk_biz_id || this.panel.bk_biz_id || this.$store.getters.bizId
          }#/data-retrieval/?targets=${encodeURIComponent(JSON.stringify(data))}&from=${
            this.toolTimeRange[0]
          }&to=${this.toolTimeRange[1]}&timezone=${(this as any).timezone || window.timezone}`;
          window.open(url);
        }
        break;
      case 'strategy': // 新增策略
        {
          const data = this.panel.toStrategy();
          const url = `${location.origin}${location.pathname.toString().replace('fta/', '')}?bizId=${
            this.panel.targets?.[0]?.data?.bk_biz_id || this.panel.bk_biz_id || this.$store.getters.bizId
          }#/strategy-config/add/?${data?.query_configs?.length ? `data=${JSON.stringify(data)}&` : ''}from=${this.toolTimeRange[0]}&to=${
            this.toolTimeRange[1]
          }&timezone=${(this as any).timezone || window.timezone}`;
          window.open(url);
        }
        break;
      case 'drill-down': // 下钻 默认主机
        this.handleDrillDown(menuItem.childValue);
        break;
      case 'relate-alert':
        for (const target of this.panel?.targets || []) {
          if (target.data?.query_configs?.length) {
            let queryConfig = deepClone(target.data.query_configs);
            queryConfig = variablesService.transformVariables(queryConfig);
            target.data.query_configs = queryConfig;
          }
        }
        handleRelateAlert(this.panel, this.timeRange);
        break;
      default:
        break;
    }
  }
  render() {
    const { legend } = this.panel?.options || ({ legend: {} } as any);
    return (
      <div class='time-series apm-custom-graph'>
        {this.showChartHeader && (
          <ChartHeader
            class='draggable-handle'
            collectIntervalDisplay={this.collectIntervalDisplay}
            descrition={this.panel.options?.header?.tips || ''}
            draging={this.panel.draging}
            drillDownOption={this.drillDownOptions}
            inited={this.inited}
            isInstant={this.panel.instant}
            menuList={this.menuList}
            metrics={this.metrics}
            showAddMetric={this.showAddMetric}
            showMore={this.showHeaderMoreTool}
            subtitle={this.panel.subTitle || ''}
            title={this.panel.title}
            onAlarmClick={this.handleAlarmClick}
            onAllMetricClick={this.handleAllMetricClick}
            onMenuClick={this.handleMenuToolsSelect}
            onMetricClick={this.handleMetricClick}
            onSelectChild={this.handleSelectChildMenu}
            onUpdateDragging={() => this.panel.updateDraging(false)}
          >
            <div
              class='custom-method-list'
              onClick={e => e.stopPropagation()}
            >
              <StatusTab
                maxWidth={this.width - 300}
                statusList={this.methodList}
                value={this.method}
                onChange={this.handleMethodChange}
              />
            </div>
          </ChartHeader>
        )}
        {!this.empty ? (
          <div class={`time-series-content ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
            <div
              ref='chart'
              class={`chart-instance ${legend?.displayMode === 'table' ? 'is-table-legend' : ''}`}
            >
              {this.inited && (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.height}
                  groupId={this.panel.dashboardId}
                  hoverAllTooltips={this.hoverAllTooltips}
                  needZrClick={this.panel.options?.need_zr_click_event}
                  options={this.options}
                  showRestore={this.showRestore}
                  onDataZoom={this.dataZoom}
                  onDblClick={this.handleDblClick}
                  onRestore={this.handleRestore}
                  onZrClick={this.handleZrClick}
                />
              )}
            </div>
            {legend?.displayMode !== 'hidden' && (
              <div class={`chart-legend ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
                {legend?.displayMode === 'table' ? (
                  <TableLegend
                    legendData={this.legendData}
                    onSelectLegend={this.handleSelectLegend}
                  />
                ) : (
                  <ListLegend
                    legendData={this.legendData}
                    onSelectLegend={this.handleSelectLegend}
                  />
                )}
              </div>
            )}
          </div>
        ) : this.isSingleNoData ? (
          <div
            class='empty-page'
            v-bkloading={{ isLoading: this.noDataLoading }}
          >
            <bk-exception type='building'>
              <span>{!this.isEnabledMetric ? this.$t('暂未开启 指标 功能') : this.$t('暂无 指标 数据')}</span>
              <div class='text-wrap'>
                <span class='text-row'>
                  {!this.isEnabledMetric
                    ? this.isEnabledMetricLoading
                      ? this.$t('开启中，请耐心等待...')
                      : this.$t('该服务所在 APM 应用未开启 指标 功能')
                    : this.$t('已开启 指标 功能，请参考接入指引进行数据上报')}
                </span>
                <bk-button
                  loading={this.isEnabledMetricLoading}
                  text={this.isEnabledMetric}
                  theme='primary'
                  onClick={() => this.handleEmptyEvent()}
                >
                  {this.isEnabledMetric ? this.$t('查看接入指引') : this.$t('立即开启')}
                </bk-button>
              </div>
            </bk-exception>
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}
