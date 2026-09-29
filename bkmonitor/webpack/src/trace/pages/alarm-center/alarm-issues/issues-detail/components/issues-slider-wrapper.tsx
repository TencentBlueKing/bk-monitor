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
import { type PropType, computed, defineComponent, KeepAlive, onScopeDispose, shallowRef, watch } from 'vue';

import { Tab } from 'bkui-vue';
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
import { useTapdIssueActivities } from '../../issues-tapd/composables/use-tapd-issue-activities';
import { conditionAlertQueryFieldReplace } from '../utils';
import DimensionStats from './dimension-stats/dimension-stats';
import IssuesActivity from './issues-activity/issues-activity';
import IssuesBasicInfo from './issues-basic-info/issues-basic-info';
import IssuesDetailAlarmPanel from './issues-detail-alarm-panel/issues-detail-alarm-panel';
import IssuesDetailAlarmTable from './issues-detail-alarm-table/issues-detail-alarm-table';
import IssuesHistory from './issues-history/issues-history';
import IssuesRelationTapd from './issues-relation-tapd/issues-relation-tapd';
import IssuesRetrievalFilter from './issues-retrieval-filter/issues-retrieval-filter';
import IssuesTrendChart from './issues-trend-chart/issues-trend-chart';
import { type TimeRangeType, DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '@/components/time-range/utils';
import DetailLoading, { DetailLoadStatus } from '../../../common-detail/detail-loading';
import IssuesLoading from './issues-loading';

import type { ImpactScopeEvent, ImpactScopeResource, IssueActivityItem, IssueDetail } from '../../typing';
import type {
  ImpactScopeResourceKeyType,
  IssueDetailTabType,
  IssuePriorityType,
  IssueStatusType,
} from '../../typing/constants';
import type { AlarmCenterPanelTabType } from '@/pages/alarm-center/utils/constant';

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
    refreshKey: { type: String, default: '' },
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
    /** 告警详情页签（视图/日志/调用链等）默认选中项 */
    defaultInnerTab: {
      type: String as PropType<'' | AlarmCenterPanelTabType>,
      default: '',
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
    let disposed = false;
    const currentTab = shallowRef<IssueDetailTabType>(IssueDetailTabEnum.LATEST);

    /** 告警详情页签（视图/日志/调用链等）默认选中项（Sideslider 使用 v-if，每次打开为新实例） */
    const controllableDefaultInnerTab = shallowRef<'' | AlarmCenterPanelTabType>(props.defaultInnerTab);

    const latestAlertId = shallowRef('');
    const earliestAlertId = shallowRef('');
    const latestAlertIdLoading = shallowRef(false);
    const earliestAlertIdLoading = shallowRef(false);
    const latestAlertAbortController = shallowRef<AbortController>(null);
    const earliestAlertAbortController = shallowRef<AbortController>(null);
    const searchRefreshKey = shallowRef(random(8));
    /** 告警事件数量 */
    const alertCount = shallowRef(0);
    const latestAlertError = shallowRef(false);
    const earliestAlertError = shallowRef(false);
    const dimensionLoading = shallowRef(false);
    const dimensionLoaded = shallowRef(false);
    const dimensionError = shallowRef(false);
    let dimensionController: AbortController;
    let activityController: AbortController;
    /** 公共参数 */
    const commonParams = computed<Record<string, unknown>>(oldValue => {
      const issueIdCondition = { key: 'issue_id', value: [props.detail.id], method: 'eq' };
      const newValue = {
        bk_biz_ids: window.APM_QUERY_STRING ? [window.bk_biz_id] : [props.detail.bk_biz_id],
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

    /** TAPD 单据操作成功后的全局活动记录，用于回写到当前 Issue 活动列表 */
    const tapdIssueActivities = useTapdIssueActivities();

    /**
     * 监听 TAPD 全局活动记录变化，当与当前 issue 匹配时自动追加到活动列表
     * 触发时机：TAPD 侧滑栏中创建/关联单据成功后调用 setActivities
     */
    watch(
      () => tapdIssueActivities.activities.value,
      () => {
        if (
          tapdIssueActivities.activities.value?.issueId === props.detail?.id &&
          tapdIssueActivities.activities.value?.list?.length
        ) {
          handleActivitiesChange(tapdIssueActivities.activities.value.list);
        }
      }
    );

    const getAllAlertId = () => {
      if (!props.detail?.id) return;
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
      const fetchAlert = async (latest: boolean) => {
        const controllerRef = latest ? latestAlertAbortController : earliestAlertAbortController;
        const loading = latest ? latestAlertIdLoading : earliestAlertIdLoading;
        const error = latest ? latestAlertError : earliestAlertError;
        const id = latest ? latestAlertId : earliestAlertId;
        controllerRef.value?.abort();
        const controller = new AbortController();
        controllerRef.value = controller;
        const { signal } = controller;
        loading.value = true;
        error.value = false;
        try {
          const res = await alarmService.getFilterTableList({ ...params, ordering: [latest ? '-create_time' : 'create_time'] }, { signal, throwOnError: true });
          if (signal.aborted) return;
          id.value = res?.data?.[0]?.id || '';
          if (latest) alertCount.value = res?.total || 0;
        } catch {
          if (!signal.aborted) error.value = true;
        } finally {
          if (!signal.aborted) loading.value = false;
        }
      };
      fetchAlert(true);
      fetchAlert(false);
    };

    /** 获取维度统计数据 */
    const getDimensionStatsData = async () => {
      if (!props.detail.id) return;
      const [startTime, endTime] = handleTransformToTimestamp(props.timeRange);
      dimensionController?.abort();
      dimensionController = new AbortController();
      const { signal } = dimensionController;
      dimensionLoading.value = true;
      dimensionError.value = false;
      try {
      const data = await alertTopN({
        ...commonParams.value,
        start_time: startTime,
        end_time: endTime,
        fields: props.detail?.aggregate_config?.aggregate_dimensions?.map(item => item.field),
        size: 5,
      }, { signal })
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
        });
      if (signal.aborted) return;
      dimensionStatsData.value = data;
      dimensionLoaded.value = true;
      } catch {
        if (!signal.aborted) dimensionError.value = true;
      } finally {
        if (!signal.aborted) dimensionLoading.value = false;
      }
    };

    /** 活动列表 */
    const activities = shallowRef<IssueActivityItem[]>([]);
    const activityLoading = shallowRef(false);
    const activityError = shallowRef(false);
    const activityLoaded = shallowRef(false);
    const getActiveList = async () => {
      if (!props.detail?.id) return;
      activityController?.abort();
      activityController = new AbortController();
      const { signal } = activityController;
      activityLoading.value = true;
      activityError.value = false;
      try {
        const data = await listIssueActivities({ bk_biz_id: props.detail.bk_biz_id, issue_id: props.detail.id }, { signal });
        if (signal.aborted) return;
        activities.value = data;
        activityLoaded.value = true;
      } catch {
        if (!signal.aborted) activityError.value = true;
      } finally {
        if (!signal.aborted) activityLoading.value = false;
      }
    };

    watch(() => props.refreshKey, getActiveList, { immediate: true });
    watch(
      [commonParams, () => props.timeRange, searchRefreshKey, () => props.refreshKey],
      () => {
        getDimensionStatsData();
        getAllAlertId();
      },
      { immediate: true }
    );
    onScopeDispose(() => {
      disposed = true;
      latestAlertAbortController.value?.abort();
      earliestAlertAbortController.value?.abort();
      dimensionController?.abort();
      activityController?.abort();
    });

    const handleTabChange = (tab: IssueDetailTabType) => {
      controllableDefaultInnerTab.value = '';
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
      if (disposed) return;
      handleActivitiesChange(list);
      emit('assigneeChange', users);
    };

    /** 优先级变更 */
    const handlePriorityChange = (priority: IssuePriorityType, list: IssueActivityItem[]) => {
      if (disposed) return;
      handleActivitiesChange(list);
      emit('priorityChange', priority);
    };

    /** 状态变更 */
    const handleStatusAction = (status: IssueStatusType, list: IssueActivityItem[]) => {
      if (disposed) return;
      handleActivitiesChange(list);
      emit('statusAction', status);
    };

    const handleActivitiesChange = (list: IssueActivityItem[]) => {
      if (disposed) return;
      activityController?.abort();
      activityLoading.value = false;
      activityError.value = false;
      activityLoaded.value = true;
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
          return latestAlertIdLoading.value && !latestAlertId.value ? (
            <DetailLoading variant='detail' />
          ) : latestAlertId.value ? (
            <IssuesDetailAlarmPanel
              key={latestAlertId.value}
              refreshKey={`${searchRefreshKey.value}:${props.refreshKey}`}
              headerAffixedTop={{
                container: `.${leftPanelClass}`,
                offsetTop: 151,
              }}
              alarmId={latestAlertId.value || ''}
              bizId={props.detail.bk_biz_id}
              defaultTab={controllableDefaultInnerTab.value}
            />
          ) : (
            !latestAlertError.value && emptyRender()
          );
        case IssueDetailTabEnum.EARLIEST:
          return earliestAlertIdLoading.value && !earliestAlertId.value ? (
            <DetailLoading variant='detail' />
          ) : earliestAlertId.value ? (
            <IssuesDetailAlarmPanel
              key={earliestAlertId.value}
              refreshKey={`${searchRefreshKey.value}:${props.refreshKey}`}
              headerAffixedTop={{
                container: `.${leftPanelClass}`,
                offsetTop: 151,
              }}
              alarmId={earliestAlertId.value}
              bizId={props.detail.bk_biz_id}
            />
          ) : (
            !earliestAlertError.value && emptyRender()
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
              refreshKey={`${searchRefreshKey.value}:${props.refreshKey}`}
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
      activityLoaded,
      activityError,
      dimensionLoading,
      dimensionLoaded,
      dimensionError,
      latestAlertIdLoading,
      latestAlertError,
      panelLoading: computed(() => currentTab.value === IssueDetailTabEnum.LATEST ? latestAlertIdLoading.value && !!latestAlertId.value : currentTab.value === IssueDetailTabEnum.EARLIEST && earliestAlertIdLoading.value && !!earliestAlertId.value),
      panelError: computed(() => currentTab.value === IssueDetailTabEnum.LATEST ? latestAlertError.value : currentTab.value === IssueDetailTabEnum.EARLIEST && earliestAlertError.value),
      getDimensionStatsData,
      getActiveList,
      getAllAlertId,
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
            bizIds={[this.detail.bk_biz_id]}
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
              countLoading={this.latestAlertIdLoading}
              countError={this.latestAlertError}
              commonParams={this.commonParams}
              refreshKey={`${this.searchRefreshKey}:${this.refreshKey}`}
              timeRange={this.timeRange}
            />
            <DimensionStats data={this.dimensionStatsData.fields} loading={this.dimensionLoading} loaded={this.dimensionLoaded} error={this.dimensionError} onRetry={this.getDimensionStatsData} />
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
                label={item.name === IssueDetailTabEnum.LIST ? () => <span>{item.label} ({this.latestAlertIdLoading ? <IssuesLoading variant='count' /> : this.latestAlertError ? '--' : this.alertCount})</span> : item.label}
                name={item.name}
              />
            ))}
          </Tab>
          <div class='issues-alarm-panel-content'>
            <DetailLoadStatus loading={this.panelLoading} error={this.panelError} onRetry={this.getAllAlertId} />
            <KeepAlive key={this.currentTab}>{this.getPanelComponent()}</KeepAlive>
          </div>
        </div>
        <div class='issues-slider-right-panel'>
          <IssuesBasicInfo
            detail={this.detail}
            onAssigneeChange={this.handleAssigneeChange}
            onConfirm={this.handleStatusAction}
            onImpactScopeClick={this.handleImpactScopeClick}
            onPriorityChange={this.handlePriorityChange}
          />
          <IssuesRelationTapd detail={this.detail} refreshKey={this.refreshKey} />
          <IssuesHistory detail={this.detail} refreshKey={this.refreshKey} />
          <IssuesActivity
            detail={this.detail}
            list={this.activities}
            loading={this.activityLoading}
            loaded={this.activityLoaded}
            error={this.activityError}
            onRetry={this.getActiveList}
            onCommentChange={this.handleActivitiesChange}
          />
        </div>
      </div>
    );
  },
});
