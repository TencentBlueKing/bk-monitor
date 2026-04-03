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
import { type PropType, computed, defineComponent, KeepAlive, shallowRef, watchEffect } from 'vue';

import { Tab } from 'bkui-vue';
import { alertTopN } from 'monitor-api/modules/alert_v2';
import { type IWhereItem, EMode } from 'trace/components/retrieval-filter/typing';
import { AlarmServiceFactory } from 'trace/pages/alarm-center/services/factory';
import {
  type AnalysisFieldAggItem,
  type AnalysisListItem,
  type AnalysisTopNDataResponse,
  AlarmType,
} from 'trace/pages/alarm-center/typings';
import { useI18n } from 'vue-i18n';

import { DIMENSION_NAME_MAP, DIMENSION_WHITE_LIST_FIELD, IssueDetailTabEnum } from '../../constant';
import DimensionStats from './dimension-stats/dimension-stats';
import IssuesActivity from './issues-activity/issues-activity';
import IssuesBasicInfo from './issues-basic-info/issues-basic-info';
import IssuesDetailAlarmPanel from './issues-detail-alarm-panel/issues-detail-alarm-panel';
import IssuesDetailAlarmTable from './issues-detail-alarm-table/issues-detail-alarm-table';
import IssuesHistory from './issues-history/issues-history';
import IssuesRetrievalFilter from './issues-retrieval-filter/issues-retrieval-filter';
import IssuesTrendChart from './issues-trend-chart/issues-trend-chart';
import { type TimeRangeType, DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '@/components/time-range/utils';

import type { ImpactScopeEvent, ImpactScopeResource, IssueDetail } from '../../typing';
import type { ImpactScopeResourceKeyType, IssueDetailTabType, IssuePriorityType } from '../../typing/constants';

import './issues-slider-wrapper.scss';

const leftPanelClass = 'issues-slider-left-panel';

// Tab 配置
const TAB_LIST: { label: string; name: IssueDetailTabType }[] = [
  { label: window.i18n.t('最近的告警'), name: IssueDetailTabEnum.LATEST },
  { label: window.i18n.t('最早的告警'), name: IssueDetailTabEnum.EARLIEST },
  { label: window.i18n.t('告警列表'), name: IssueDetailTabEnum.LIST },
];

export default defineComponent({
  name: 'IssuesSliderWrapper',
  props: {
    detail: {
      type: Object as PropType<IssueDetail>,
      default: () => ({}),
    },
    /** Issue ID */
    issueId: {
      type: String,
      default: '',
    },
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => DEFAULT_TIME_RANGE,
    },
    /** 筛选条件 */
    conditions: {
      type: Array as PropType<IWhereItem[]>,
      default: () => [],
    },
    /** 查询字符串 */
    queryString: {
      type: String,
      default: '',
    },
    /** 查询模式 */
    filterMode: {
      type: String as PropType<EMode>,
      default: EMode.ui,
    },
  },
  emits: {
    conditionChange: (_v: IWhereItem[]) => true,
    filterModeChange: (_v: EMode) => true,
    queryStringChange: (_v: string) => true,
    /** 负责人变更 */
    assigneeChange: (_v: string[]) => true,
    /** 优先级变更 */
    priorityChange: (_v: IssuePriorityType) => true,
    /** 状态变更 */
    statusAction: () => true,
    /** 影响范围点击 */
    impactScopeClick: (impactScope: ImpactScopeEvent) => impactScope,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const currentTab = shallowRef<IssueDetailTabType>(IssueDetailTabEnum.LATEST);
    // test
    const tempAlertId = shallowRef('');
    /** 告警事件数量 */
    const alertCount = shallowRef(0);
    /** 公共参数 */
    const commonParams = computed(() => {
      const issueIdCondition = { key: 'issue_id', value: [props.detail.id], method: 'eq' };
      return {
        bk_biz_ids: [props.detail.bk_biz_id],
        query_string: props.filterMode === EMode.ui ? '' : props.queryString,
        conditions: props.filterMode === EMode.ui ? [...props.conditions, issueIdCondition] : [issueIdCondition],
      };
    });
    /** 维度统计数据 */
    const dimensionStatsData = shallowRef<AnalysisTopNDataResponse<AnalysisListItem>>({
      doc_count: 0,
      fields: [],
    });

    const getTempAlertId = async () => {
      const alarmService = AlarmServiceFactory(AlarmType.ALERT);
      const [startTime, endTime] = handleTransformToTimestamp(props.timeRange);
      const params = {
        bk_biz_ids: [],
        conditions: props.conditions,
        query_string: props.queryString,
        start_time: startTime,
        end_time: endTime,
        page_size: 1,
        page: 1,
        ordering: [],
      };
      const res = await alarmService.getFilterTableList(params);
      tempAlertId.value = res.data?.[0]?.id;
    };
    getTempAlertId();

    /** 获取维度统计数据 */
    const getDimensionStatsData = async () => {
      const [startTime, endTime] = handleTransformToTimestamp(props.timeRange);
      dimensionStatsData.value = await alertTopN({
        ...commonParams,
        start_time: startTime,
        end_time: endTime,
        fields: props.detail?.aggregate_config?.aggregate_dimensions?.map(item =>
          DIMENSION_WHITE_LIST_FIELD.includes(item) ? item : `tags.${item}`
        ),
        size: 5,
      })
        .then((data: AnalysisTopNDataResponse<AnalysisFieldAggItem>) => {
          return {
            doc_count: data.doc_count,
            fields: data.fields.map(item => {
              /** 如果item的buckets所有的count总和小于doc_count则额外展示其他 */
              let otherCount = data.doc_count;
              const buckets = item.buckets.map(bucket => {
                otherCount -= bucket.count;
                return {
                  ...bucket,
                  percent: data.doc_count ? Number(((bucket.count / data.doc_count) * 100).toFixed(2)) : 0,
                };
              });

              if (otherCount > 0) {
                buckets.push({
                  count: otherCount,
                  percent: Number(((otherCount / data.doc_count) * 100).toFixed(2)),
                  id: 'other',
                  name: t('其他'),
                });
              }

              return {
                ...item,
                name: DIMENSION_NAME_MAP[item.field] || item.field,
                buckets,
              };
            }),
          };
        })
        .catch(() => ({
          doc_count: 0,
          fields: [],
        }));
    };

    watchEffect(() => {
      getDimensionStatsData();
    });

    const handleTabChange = (tab: IssueDetailTabType) => {
      currentTab.value = tab;
    };

    /** 新开告警详情页 */
    const handleShowAlertDetail = (id: string) => {
      const hash = `#/trace/alarm-center/detail/${id}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    };

    const handleConditionChange = (val: IWhereItem[]) => {
      emit('conditionChange', val);
    };

    const handleQueryStringChange = (val: string) => {
      emit('queryStringChange', val);
    };

    const handleFilterModeChange = (val: EMode) => {
      emit('filterModeChange', val);
    };

    /** 负责人变更 */
    const handleAssigneeChange = (users: string[]) => {
      emit('assigneeChange', users);
    };

    /** 优先级变更 */
    const handlePriorityChange = (priority: IssuePriorityType) => {
      emit('priorityChange', priority);
    };

    /** 状态变更 */
    const handleResolved = () => {
      emit('statusAction');
    };

    /**
     * 影响范围点击
     * @param resourceKey 影响范围资源key
     * @param resource 影响范围资源
     */
    const handleImpactScopeClick = (resourceKey: ImpactScopeResourceKeyType, resource: ImpactScopeResource) => {
      emit('impactScopeClick', {
        resourceKey,
        resource,
      });
    };

    const getPanelComponent = () => {
      switch (currentTab.value) {
        case IssueDetailTabEnum.LATEST:
          return (
            <IssuesDetailAlarmPanel
              key={props.detail?.latest_alert_id}
              alarmId={tempAlertId.value || ''}
            />
          );
        case IssueDetailTabEnum.EARLIEST:
          return (
            <IssuesDetailAlarmPanel
              key={props.detail?.earliest_alert_id}
              alarmId={tempAlertId.value || ''}
            />
          );
        case IssueDetailTabEnum.LIST:
          return (
            <IssuesDetailAlarmTable
              headerAffixedTop={{
                container: `.${leftPanelClass}`,
                offsetTop: 100,
              }}
              horizontalScrollAffixedBottom={{
                container: `.${leftPanelClass}`,
              }}
              conditions={props.conditions}
              queryString={props.queryString}
              scrollContainerSelector={`.${leftPanelClass}`}
              timeRange={props.timeRange}
              onShowAlertDetail={handleShowAlertDetail}
            />
          );
        default:
          return null;
      }
    };

    return {
      currentTab,
      alertCount,
      commonParams,
      dimensionStatsData,
      handleTabChange,
      getPanelComponent,
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
      <div class='issues-slider-wrapper'>
        <div class={leftPanelClass}>
          <IssuesRetrievalFilter
            conditions={this.conditions}
            filterMode={this.filterMode}
            queryString={this.queryString}
            timeRange={this.timeRange}
            onConditionChange={this.handleConditionChange}
            onFilterModeChange={this.handleFilterModeChange}
            onQueryStringChange={this.handleQueryStringChange}
          />
          <div class='issues-chart-wrapper'>
            <IssuesTrendChart
              alertCount={this.alertCount}
              commonParams={this.commonParams}
              timeRange={this.timeRange}
            />
            <DimensionStats data={this.dimensionStatsData.fields} />
          </div>
          <Tab
            class='issues-alarm-tab'
            active={this.currentTab}
            type='unborder-card'
            onUpdate:active={this.handleTabChange}
          >
            {TAB_LIST.map(item => (
              <Tab.TabPanel
                key={item.name}
                label={item.label}
                name={item.name}
              />
            ))}
          </Tab>
          <KeepAlive>{this.getPanelComponent()}</KeepAlive>
        </div>
        <div class='issues-slider-right-panel'>
          <IssuesBasicInfo
            detail={this.detail}
            onAssigneeChange={this.handleAssigneeChange}
            onConfirm={this.handleResolved}
            onImpactScopeClick={this.handleImpactScopeClick}
            onPriorityChange={this.handlePriorityChange}
          />
          <IssuesActivity detail={this.detail} />
          <IssuesHistory detail={this.detail} />
        </div>
      </div>
    );
  },
});
