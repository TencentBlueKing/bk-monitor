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
import { defineComponent, shallowReactive, shallowRef } from 'vue';

import { Sideslider } from 'bkui-vue';
import { random } from 'monitor-common/utils';
import { getDefaultTimezone } from 'monitor-pc/i18n/dayjs';
import { type IWhereItem, EMode } from 'trace/components/retrieval-filter/typing';

import IssuesSliderHeader from './components/issues-slider-header';
import IssuesSliderWrapper from './components/issues-slider-wrapper';
import RefreshRate from '@/components/refresh-rate/refresh-rate';
import TimeRange from '@/components/time-range/time-range';
import { type TimeRangeType, DEFAULT_TIME_RANGE } from '@/components/time-range/utils';

import type { IssueDetail } from '../typing';
import type { ImpactScopeResourceKeyType, IssuePriorityType } from '../typing/constants';

import './issues-detail-sideslider.scss';

export default defineComponent({
  name: 'IssuesDetailSideSlider',
  props: {
    show: {
      type: Boolean,
      required: true,
    },
    /** Issue ID */
    issueId: {
      type: String,
      default: '',
    },
    /** 告警ID */
    alarmId: {
      type: String,
      default: '',
    },
  },
  emits: ['update:show'],
  setup(_, { emit }) {
    const detail = shallowReactive<IssueDetail>({
      id: 'issue-0006',
      name: '[回归] 数据库连接池耗尽',
      status: 'unresolved',
      status_display: '未解决',
      priority: 'P2',
      priority_display: '低',
      assignee: ['sunqi'],
      is_regression: true,
      strategy_id: '1001',
      strategy_name: '主机 CPU 使用率过高',
      bk_biz_id: 100,
      bk_biz_name: '示例业务',
      labels: ['集群告警', '测试环境', 'BCS'],
      alert_count: 1129,
      anomaly_message: 'K8S Pod CrashLoopBackOff，重启次数 > 10',
      trend: [],
      first_alert_time: 1763538688,
      last_alert_time: 1774172004,
      create_time: 1763537110,
      update_time: 1774254865,
      resolved_time: null,
      is_resolved: false,
      duration: '124d 1h',
      impact_scope: {
        cluster: {
          count: 3,
          instance_list: [
            { bcs_cluster_id: 'BCS-K8S-80001', display_name: 'MOCK-SZ-TEST-80001-INNER(BCS-K8S-80001)' },
            { bcs_cluster_id: 'BCS-K8S-80002', display_name: '模拟集群-业务测试-V1.26.1(BCS-K8S-80002)' },
            { bcs_cluster_id: 'BCS-K8S-80003', display_name: 'demo-test-gz-0611(BCS-K8S-80003)' },
          ],
          link_tpl: '/k8s?filter-bcs_cluster_id={bcs_cluster_id}&sceneId=kubernetes&sceneType=overview',
        },
      },
      aggregate_config: { aggregate_dimensions: ['bk_target_ip'], conditions: [], alert_levels: [1, 2] },
    });

    const isFullscreen = shallowRef(false);
    const timeRange = shallowRef<TimeRangeType>(DEFAULT_TIME_RANGE);
    const timezone = shallowRef(getDefaultTimezone());
    const refreshInterval = shallowRef(-1);
    const refreshImmediate = shallowRef(random(4));
    // 筛选条件状态
    const conditions = shallowRef<IWhereItem[]>([]);
    const queryString = shallowRef('');
    const filterMode = shallowRef<EMode>(EMode.ui);

    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    const handleTimeRangeChange = (value: TimeRangeType) => {
      timeRange.value = value;
    };

    const handleTimezoneChange = (value: string) => {
      timezone.value = value;
    };

    const handleImmediateRefresh = () => {
      refreshImmediate.value = random(5);
    };

    const handleRefreshChange = (value: number) => {
      refreshInterval.value = value;
    };

    const handleConditionChange = (val: IWhereItem[]) => {
      conditions.value = val;
    };

    const handleQueryStringChange = (val: string) => {
      queryString.value = val;
    };

    const handleFilterModeChange = (val: EMode) => {
      filterMode.value = val;
    };

    /** 负责人变更 */
    const handleAssigneeChange = (users: string[]) => {
      detail.assignee = users;
    };

    /** 优先级变更 */
    const handlePriorityChange = (priority: IssuePriorityType) => {
      detail.priority = priority;
    };

    /** 标记已解决 */
    const handleResolved = () => {
      // 刷新数据
      detail.is_resolved = true;
    };

    /** 影响范围点击 */
    const handleImpactScopeClick = (resourceKey: ImpactScopeResourceKeyType, resource: any) => {
      console.log('handleImpactScopeClick', resourceKey, resource);
      // TODO: 展示影响范围侧栏
    };

    return {
      isFullscreen,
      timeRange,
      timezone,
      refreshInterval,
      detail,
      conditions,
      queryString,
      filterMode,
      handleShowChange,
      handleTimeRangeChange,
      handleTimezoneChange,
      handleImmediateRefresh,
      handleRefreshChange,
      handleConditionChange,
      handleQueryStringChange,
      handleFilterModeChange,
      handleAssigneeChange,
      handlePriorityChange,
      handleResolved,
      handleImpactScopeClick,
    };
  },
  render() {
    return (
      <Sideslider
        width={this.isFullscreen ? '100%' : '80%'}
        extCls='issues-detail-sidesSlider'
        v-slots={{
          header: () => (
            <IssuesSliderHeader
              v-slots={{
                tools: () => [
                  <TimeRange
                    key='time-range'
                    modelValue={this.timeRange}
                    timezone={this.timezone}
                    onUpdate:modelValue={this.handleTimeRangeChange}
                    onUpdate:timezone={this.handleTimezoneChange}
                  />,
                  <RefreshRate
                    key='refresh-rate'
                    value={this.refreshInterval}
                    onImmediate={this.handleImmediateRefresh}
                    onSelect={this.handleRefreshChange}
                  />,
                ],
              }}
              detail={this.detail}
            />
          ),
          default: () => (
            <div class='issues-detail-side-slider-content'>
              <IssuesSliderWrapper
                alarmId={this.alarmId}
                conditions={this.conditions}
                detail={this.detail}
                filterMode={this.filterMode}
                issueId={this.issueId}
                queryString={this.queryString}
                timeRange={this.timeRange}
                onAssigneeChange={this.handleAssigneeChange}
                onConditionChange={this.handleConditionChange}
                onFilterModeChange={this.handleFilterModeChange}
                onImpactScopeClick={this.handleImpactScopeClick}
                onPriorityChange={this.handlePriorityChange}
                onQueryStringChange={this.handleQueryStringChange}
                onResolved={this.handleResolved}
              />
            </div>
          ),
        }}
        isShow={this.show}
        render-directive='if'
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
