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
import { Component, InjectReactive, Watch, Inject } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import QuickAddStrategy from 'apm/pages/alarm-template/quick-add-strategy/quick-add-strategy';
import AlarmCenter from './alarm-center';
import type { IViewOptions } from '../../typings';
import { alertBuiltinFilter } from 'monitor-api/modules/model';
import { fetchItemStatus } from 'monitor-api/modules/strategies';
import { generateQueryString } from 'monitor-api/modules/alert_v2';
import type { TimeRangeType } from 'trace/components/time-range/utils';

import './index.scss';

@Component
export default class ApmAlarmCenter extends tsc<any, any> {
  // 图表特殊参数
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  // 图表的数据时间间隔
  @InjectReactive('timeRange') readonly timeRange: [string, string];
  // 图表刷新间隔
  @InjectReactive('refreshInterval') readonly panleRefleshInterval: number;
  // 立即刷新图表
  @InjectReactive('refreshImmediate') readonly panelRefleshImmediate: string;
  // dashboardId
  @Inject('handlePageTabChange') handlePageTabChange: (
    id: string,
    customRouterQuery: Record<string, number | string>
  ) => void;
  // 处理时间范围变化
  @Inject('handleTimeRangeChange') handleTimeRangeChange: (v: TimeRangeType) => void;

  // 告警关联下拉是否展示
  isDropdownShow = false;
  // 一键添加策略弹窗是否展示
  showQuickAddStrategy = false;
  // 页面加载状态
  pageLoading = false;
  // 告警策略数量（当前应用/服务标签下已关联策略数）
  strategyCount = 0;
  /** 告警关联范围选项，id 对应 builtin filter 的 target_types */
  alarmRelateList = [
    {
      id: 'APM-SERVICE',
      name: this.$t('本服务'),
      checked: true,
    },
    {
      id: 'HOST',
      name: this.$t('主机'),
      checked: false,
    },
    {
      id: 'K8S-WORKLOAD',
      name: this.$t('容器'),
      checked: false,
    },
  ];

  /** 由内置筛选接口生成的查询串，传给嵌入的告警中心作为初始条件 */
  queryString = '';
  /** 本地缓存的ui查询条件 */
  localConditions: unknown[] = [];
  /** 本地缓存的语句模式查询串 */
  localQueryString = '';
  /** ui条件转换成的语句模式查询串 */
  conditionsToQueryString = '';

  /** 告警关联选中展示的文本 */
  get alarmRelateListCheckedDisplay() {
    return this.alarmRelateList
      .filter(item => item.checked)
      .map(item => item.name)
      .join(', ');
  }

  /** 是否是 APM 服务 */
  get isApmService() {
    return this.viewOptions.filters?.app_name && this.viewOptions.filters?.service_name;
  }

  @Watch('alarmRelateList', { immediate: true, deep: true })
  handleAlarmRelateListChange() {
    this.getBuiltinFilter();
  }

  /** 告警关联下拉是否展示 */
  handleDropdownShow(isShow: boolean) {
    this.isDropdownShow = isShow;
  }

  /** 一键添加策略弹窗是否展示 */
  handleShowQuickAddStrategyChange(isShow: boolean) {
    this.showQuickAddStrategy = isShow;
  }

  /** 新窗口打开策略配置页，并按当前服务预填 label 过滤 */
  handleToStrategyListAndEvnetCenter() {
    const serviceName = this.viewOptions.filters?.service_name;
    const filters = serviceName ? [{ key: 'label_name', value: [`/APM-SERVICE(${serviceName})/`] }] : [];
    const { href } = this.$router.resolve({
      path: '/strategy-config',
      query: {
        filters: JSON.stringify(filters),
      },
    });
    const targetUrl = `/?bizId=${this.$store.getters.bizId}${href}`;
    window.open(targetUrl, '_blank');
  }

  /** 新窗口打开 Trace 告警中心，携带当前 queryString 与业务 ID */
  handleToAlarmCenter() {
    const { href } = this.$router.resolve({
      path: '/trace/alarm-center',
      query: {
        queryString: this.conditionsToQueryString,
        filterMode: 'queryString',
        alarmType: 'alert',
        from: this.timeRange[0],
        to: this.timeRange[1],
        bizIds: [this.$store.getters.bizId],
      },
    });
    const targetUrl = `/?bizId=${this.$store.getters.bizId}${href}`;
    window.open(targetUrl, '_blank');
  }

  /** 根据当前应用、服务与勾选的关联类型，拉取告警中心可用的 query_string */
  async getBuiltinFilter() {
    this.pageLoading = true;
    const params = {
      app_name: this.viewOptions.filters?.app_name,
      service_name: this.viewOptions.filters?.service_name,
      target_types: this.alarmRelateList.filter(item => item.checked).map(item => item.id),
    };
    try {
      const data = await alertBuiltinFilter(params);
      this.queryString = data.query_string;
      this.conditionsToQueryString = this.queryString;
    } finally {
      this.$nextTick(() => {
        this.pageLoading = false;
      });
    }
  }

  /** 查询当前 APM 应用/服务标签下的策略数量，用于头部展示 */
  async getAlarmStatus() {
    const data = await fetchItemStatus({
      labels: [
        `APM-APP(${this.viewOptions.filters?.app_name})`,
        `APM-SERVICE(${this.viewOptions.filters?.service_name})`,
      ],
    });
    this.strategyCount = data.strategy_count;
  }

  /** 嵌入告警中心（V3）透出的事件；conditionChange 为 UI 条件变化，其余可扩展处理查询变更等 */
  async handleV3EventChange(eventName: string, params: string | unknown[]) {
    if (eventName === 'alarmTrendChartZoomChange') {
      this.handleTimeRangeChange(params as TimeRangeType);
      return;
    }
    if (eventName === 'filterModeChange') {
      if (params === 'ui') {
        // 语句模式切换为ui模式
        const queryString = await generateQueryString({
          conditions: this.localConditions,
        });
        this.conditionsToQueryString = `${this.queryString} AND (${queryString})`;
      } else {
        // ui模式切换为语句模式
        this.conditionsToQueryString = `${this.queryString} AND (${this.localQueryString})`;
      }
      return;
    }
    if (params.length === 0) {
      this.conditionsToQueryString = this.queryString;
      return;
    }
    if (eventName === 'conditionChange') {
      this.localConditions = params as unknown[];
      const queryString = await generateQueryString({
        conditions: params,
      });
      this.conditionsToQueryString = `${this.queryString} AND (${queryString})`;
      return;
    }
    this.localQueryString = params as string;
    this.conditionsToQueryString = `${this.queryString} AND (${params as string})`;
  }

  handleAddAlarmStrategy() {
    this.handlePageTabChange('alarm_template', {});
  }

  created() {
    if (this.isApmService) {
      this.getAlarmStatus();
    }
  }

  render() {
    return (
      <div
        id='apm-alarm-center-main'
        class='apm-alarm-center-page'
      >
        <div class='apm-alarm-center-header'>
          <div class='header-left'>
            {this.isApmService && (
              <div class='alarm-relate-main'>
                <span>{this.$t('告警关联')}：</span>
                <bk-dropdown-menu
                  trigger='click'
                  onHide={() => this.handleDropdownShow(false)}
                  onShow={() => this.handleDropdownShow(true)}
                >
                  <span slot='dropdown-trigger'>
                    <span class='alarm-relate-text'>{this.alarmRelateListCheckedDisplay}</span>
                    <i class={['bk-icon icon-angle-down', { 'icon-flip': this.isDropdownShow }]} />
                  </span>
                  <ul
                    class='bk-dropdown-list alarm-relate-dropdown-list'
                    slot='dropdown-content'
                  >
                    {this.alarmRelateList.map(item => (
                      <li
                        key={item.id}
                        class='alarm-relate-dropdown-item'
                      >
                        <bk-checkbox
                          v-model={item.checked}
                          disabled={item.id === 'APM-SERVICE'}
                        >
                          {item.name}
                        </bk-checkbox>
                      </li>
                    ))}
                  </ul>
                </bk-dropdown-menu>
              </div>
            )}
            <span
              class='alarm-center-jump-main'
              onClick={this.handleToAlarmCenter}
            >
              <i class='icon-monitor icon-gaojing2' />
              <span>{this.$t('告警中心')}</span>
            </span>
          </div>
          {this.isApmService ? (
            <div class='header-right'>
              <span
                style='margin-right: 18px;'
                onClick={this.handleToStrategyListAndEvnetCenter}
              >
                <i18n
                  path='该服务已关联{0}个告警策略'
                  tag='span'
                >
                  <span
                    v-bk-tooltips={{ content: this.$t('查看策略列表') }}
                    style='color: #3a84ff;font-weight: 700;margin: 0 4px;'
                  >
                    {this.strategyCount}
                  </span>
                </i18n>
              </span>
              <span
                class='add-strategy-main'
                onClick={() => this.handleShowQuickAddStrategyChange(true)}
              >
                <i class='icon-monitor icon-gaojing2' />
                <span>{this.$t('一键添加策略')}</span>
              </span>
            </div>
          ) : (
            <div
              class='header-right'
              onClick={this.handleAddAlarmStrategy}
            >
              <span class='add-strategy-main'>
                <i class='icon-monitor icon-mc-add-strategy' />
                <span>{this.$t('添加告警策略')}</span>
              </span>
            </div>
          )}
        </div>
        <div
          class='apm-alarm-center-content'
          v-bkloading={{ isLoading: this.pageLoading }}
        >
          {!this.pageLoading && (
            <AlarmCenter
              v3Props={{
                queryString: this.queryString,
                timeRange: this.timeRange,
                refreshInterval: this.panleRefleshInterval,
                refreshImmediate: this.panelRefleshImmediate,
              }}
              onV3Event={this.handleV3EventChange}
            />
          )}
        </div>
        <QuickAddStrategy
          params={{
            app_name: this.viewOptions.filters?.app_name,
            service_name: this.viewOptions.filters?.service_name,
          }}
          show={this.showQuickAddStrategy}
          onShowChange={this.handleShowQuickAddStrategyChange}
        />
      </div>
    );
  }
}
