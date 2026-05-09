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
import { type PropType, computed, defineComponent, KeepAlive, onMounted, shallowRef, watch } from 'vue';

import { Loading, Tab } from 'bkui-vue';
import { alertTopN } from 'monitor-api/modules/alert_v2';
import { listIssueActivities } from 'monitor-api/modules/issue';
import { random } from 'monitor-common/utils';
import EmptyStatus from 'trace/components/empty-status/empty-status';
import { type IWhereItem, EMode } from 'trace/components/retrieval-filter/typing';
import { AlarmServiceFactory } from 'trace/pages/alarm-center/services/factory';
import {
  type AnalysisFieldAggItem,
  type AnalysisListItem,
  type AnalysisTopNDataResponse,
  AlarmType,
} from 'trace/pages/alarm-center/typings';
import { useI18n } from 'vue-i18n';

import { IssueDetailTabEnum } from '../../constant';
import { conditionAlertQueryFieldReplace } from '../utils';
import DimensionStats from './dimension-stats/dimension-stats';
import IssuesActivity from './issues-activity/issues-activity';
import IssuesBasicInfo from './issues-basic-info/issues-basic-info';
import IssuesDetailAlarmPanel from './issues-detail-alarm-panel/issues-detail-alarm-panel';
import IssuesDetailAlarmTable from './issues-detail-alarm-table/issues-detail-alarm-table';
import IssuesHistory from './issues-history/issues-history';
import IssuesRetrievalFilter from './issues-retrieval-filter/issues-retrieval-filter';
import IssuesTrendChart from './issues-trend-chart/issues-trend-chart';
import { type TimeRangeType, DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '@/components/time-range/utils';
import useRequestAbort from '@/hooks/useRequestAbort';

import type { ImpactScopeEvent, ImpactScopeResource, IssueActivityItem, IssueDetail } from '../../typing';
import type {
  ImpactScopeResourceKeyType,
  IssueDetailTabType,
  IssuePriorityType,
  IssueStatusType,
} from '../../typing/constants';

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
    statusAction: (_status: IssueStatusType) => true,
    /** 影响范围点击 */
    impactScopeClick: (impactScope: ImpactScopeEvent) => impactScope,
    search: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const currentTab = shallowRef<IssueDetailTabType>(IssueDetailTabEnum.LATEST);
    const latestAlertId = shallowRef('');
    const earliestAlertId = shallowRef('');
    const latestAlertIdLoading = shallowRef(false);
    const earliestAlertIdLoading = shallowRef(false);
    const latestAlertAbortController = shallowRef<AbortController>(null);
    const earliestAlertAbortController = shallowRef<AbortController>(null);
    const searchRefreshKey = shallowRef(random(8));
    /** 告警事件数量 */
    const alertCount = shallowRef(0);
    /** 公共参数 */
    const commonParams = computed<Record<string, unknown>>(oldValue => {
      const issueIdCondition = { key: 'issue_id', value: [props.detail.id], method: 'eq' };
      const newValue = {
        bk_biz_ids: [props.detail.bk_biz_id],
        query_string: props.filterMode === EMode.ui ? '' : props.queryString,
        conditions: [
          issueIdCondition,
          ...(props.filterMode === EMode.ui
            ? conditionAlertQueryFieldReplace(props.conditions, props.detail?.impact_scope || {})
            : []),
        ],
      };
      if (JSON.stringify(oldValue) === JSON.stringify(newValue)) {
        return oldValue;
      }
      return newValue;
    });
    /** 维度统计数据 */
    const dimensionStatsData = shallowRef<AnalysisTopNDataResponse<AnalysisListItem>>({
      doc_count: 0,
      fields: [],
    });
    /** 维度名称映射 */
    const dimensionNameMap = computed(() => {
      return (
        props.detail?.aggregate_config?.aggregate_dimensions?.reduce((pre, cur) => {
          pre[cur.field] = cur.display_name;
          return pre;
        }, {}) || {}
      );
    });

    const getAllAlertId = async () => {
      if (!props.detail?.id) {
        return;
      }
      latestAlertAbortController.value?.abort();
      earliestAlertAbortController.value?.abort();
      latestAlertAbortController.value = null;
      earliestAlertAbortController.value = null;
      latestAlertIdLoading.value = true;
      earliestAlertIdLoading.value = true;
      const [startTime, endTime] = handleTransformToTimestamp(props.timeRange);
      const alarmService = AlarmServiceFactory(AlarmType.ALERT);
      const params = {
        bk_biz_id: props.detail.bk_biz_id,
        ...commonParams.value,
        start_time: startTime,
        end_time: endTime,
        page: 1,
        page_size: 1,
        show_overview: false,
        show_aggs: false,
      };
      latestAlertAbortController.value = new AbortController();
      earliestAlertAbortController.value = new AbortController();
      const latestResFn = async () => {
        return await alarmService.getFilterTableList(
          {
            ...params,
            ordering: ['-create_time'],
          },
          {
            signal: latestAlertAbortController.value.signal,
          }
        );
      };
      const earliestResFn = async () => {
        return await alarmService.getFilterTableList(
          {
            ...params,
            ordering: ['create_time'],
          },
          {
            signal: earliestAlertAbortController.value.signal,
          }
        );
      };
      latestResFn()
        .then(res => {
          latestAlertId.value = res?.data?.[0]?.id || '';
          alertCount.value = res?.total || 0;
        })
        .finally(() => {
          latestAlertIdLoading.value = false;
        });
      earliestResFn()
        .then(res => {
          earliestAlertId.value = res?.data?.[0]?.id || '';
        })
        .finally(() => {
          earliestAlertIdLoading.value = false;
        });
    };

    const { run, signal } = useRequestAbort<AnalysisTopNDataResponse<AnalysisListItem>>(alertTopN);
    /** 获取维度统计数据 */
    const getDimensionStatsData = async () => {
      if (!props.detail.id) return;
      const [startTime, endTime] = handleTransformToTimestamp(props.timeRange);
      const data = await run({
        ...commonParams.value,
        start_time: startTime,
        end_time: endTime,
        fields: props.detail?.aggregate_config?.aggregate_dimensions?.map(item => item.field),
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
                name: dimensionNameMap.value[item.field] || item.field,
                buckets,
              };
            }),
          };
        })
        .catch(() => ({
          doc_count: 0,
          fields: [],
        }));

      if (signal?.aborted) return;
      dimensionStatsData.value = data;
    };

    /** 活动列表 */
    const activities = shallowRef<IssueActivityItem[]>([]);
    const activityLoading = shallowRef(false);
    const { run: getActiveListRun, signal: getActiveListSignal } =
      useRequestAbort<IssueActivityItem[]>(listIssueActivities);
    const getActiveList = async () => {
      if (!props.detail?.id) return;
      activityLoading.value = true;
      const data = await getActiveListRun({
        bk_biz_id: props.detail?.bk_biz_id,
        issue_id: props.detail?.id,
      });
      if (getActiveListSignal?.aborted) return;
      activities.value = data;
      activityLoading.value = false;
    };

    watch(
      () => props.detail?.id,
      id => {
        if (id) {
          getActiveList();
        }
      }
    );

    watch(
      [() => props.detail?.id, () => commonParams.value, () => props.timeRange, () => searchRefreshKey.value],
      () => {
        getDimensionStatsData();
        getAllAlertId();
      },
      { deep: true }
    );

    onMounted(() => {
      getDimensionStatsData();
      getAllAlertId();
      getActiveList();
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
    const handleAssigneeChange = (users: string[], list: IssueActivityItem[]) => {
      handleActivitiesChange(list);
      emit('assigneeChange', users);
    };

    /** 优先级变更 */
    const handlePriorityChange = (priority: IssuePriorityType, list: IssueActivityItem[]) => {
      handleActivitiesChange(list);
      emit('priorityChange', priority);
    };

    /** 状态变更 */
    const handleStatusAction = (status: IssueStatusType, list: IssueActivityItem[]) => {
      handleActivitiesChange(list);
      emit('statusAction', status);
    };

    const handleActivitiesChange = (list: IssueActivityItem[]) => {
      activities.value = list;
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

    const handleSearch = () => {
      searchRefreshKey.value = random(8);
      emit('search');
    };

    const loadingRender = () => {
      return (
        <div class='panel-loading'>
          <Loading loading />
        </div>
      );
    };

    const emptyRender = () => {
      return (
        <EmptyStatus
          type={
            (props.filterMode === EMode.ui ? !!props.conditions.length : !!props.queryString) ? 'search-empty' : 'empty'
          }
          onOperation={() => {
            if (props.filterMode === EMode.ui) {
              handleConditionChange([]);
            } else {
              handleQueryStringChange('');
            }
          }}
        />
      );
    };

    const getPanelComponent = () => {
      switch (currentTab.value) {
        case IssueDetailTabEnum.LATEST:
          return latestAlertIdLoading.value ? (
            loadingRender()
          ) : latestAlertId.value ? (
            <IssuesDetailAlarmPanel
              key={latestAlertId.value}
              alarmId={latestAlertId.value || ''}
              bizId={props.detail.bk_biz_id}
            />
          ) : (
            emptyRender()
          );
        case IssueDetailTabEnum.EARLIEST:
          return earliestAlertIdLoading.value ? (
            loadingRender()
          ) : earliestAlertId.value ? (
            <IssuesDetailAlarmPanel
              key={earliestAlertId.value}
              alarmId={earliestAlertId.value}
              bizId={props.detail.bk_biz_id}
            />
          ) : (
            emptyRender()
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
              detail={props.detail}
              filterMode={props.filterMode}
              queryString={props.queryString}
              refreshKey={searchRefreshKey.value}
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
      earliestAlertId,
      latestAlertId,
      activities,
      activityLoading,
      handleTabChange,
      getPanelComponent,
      handleConditionChange,
      handleQueryStringChange,
      handleFilterModeChange,
      handleAssigneeChange,
      handlePriorityChange,
      handleStatusAction,
      handleActivitiesChange,
      handleImpactScopeClick,
      handleSearch,
      searchRefreshKey,
    };
  },
  render() {
    return (
      <div class='issues-slider-wrapper'>
        <div class={leftPanelClass}>
          <IssuesRetrievalFilter
            conditions={this.conditions}
            filterMode={this.filterMode}
            issueId={this.detail.id}
            queryString={this.queryString}
            timeRange={this.timeRange}
            onConditionChange={this.handleConditionChange}
            onFilterModeChange={this.handleFilterModeChange}
            onQueryStringChange={this.handleQueryStringChange}
            onSearch={this.handleSearch}
          />
          <div class='issues-chart-wrapper'>
            <IssuesTrendChart
              alertCount={this.alertCount}
              commonParams={this.commonParams}
              refreshKey={this.searchRefreshKey}
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
                label={item.name === IssueDetailTabEnum.LIST ? `${item.label} (${this.alertCount})` : item.label}
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
            onConfirm={this.handleStatusAction}
            onImpactScopeClick={this.handleImpactScopeClick}
            onPriorityChange={this.handlePriorityChange}
          />
          <IssuesHistory detail={this.detail} />
          <IssuesActivity
            detail={this.detail}
            list={this.activities}
            loading={this.activityLoading}
            onCommentChange={this.handleActivitiesChange}
          />
        </div>
      </div>
    );
  },
});
