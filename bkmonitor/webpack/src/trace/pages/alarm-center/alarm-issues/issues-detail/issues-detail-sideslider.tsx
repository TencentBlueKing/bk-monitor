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
import { defineComponent, onUnmounted, shallowRef, watch } from 'vue';

import { Sideslider } from 'bkui-vue';
import { convertDurationArray } from 'monitor-common/utils';
import { updateTimezone } from 'monitor-pc/i18n/dayjs';
import { storeToRefs } from 'pinia';
import { appendQueryStringCondition } from 'trace/components/retrieval-filter/query-string-utils';
import { type IWhereItem, EMode } from 'trace/components/retrieval-filter/typing';

import IssuesImpactScopeDrawer from '../components/issues-impact-scope-drawer/issues-impact-scope-drawer';
import IssuesSliderHeader from './components/issues-slider-header';
import IssuesSliderWrapper from './components/issues-slider-wrapper';
import RefreshRate from '@/components/refresh-rate/refresh-rate';
import { mergeWhereList } from '@/components/retrieval-filter/utils';
import TimeRange from '@/components/time-range/time-range';
import { useIssuesDetailStore } from '@/store/modules/issues-detail';

import type { CommonCondition } from '../../typings';
import type { ImpactScopeEvent, ImpactScopeResource } from '../typing';
import type { ImpactScopeResourceKeyType, IssuePriorityType, IssueStatusType } from '../typing/constants';

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
    /** issues BizId */
    issueBizId: {
      type: Number,
      default: undefined,
    } /** 是否展示上一步和下一步按钮 */,
    showStepBtn: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['update:show', 'next', 'previous', 'createTapd'],
  setup(props, { emit }) {
    const issuesDetailStore = useIssuesDetailStore();
    const { bizId, issueId, detail, loading, timeRange, timezone, refreshInterval } = storeToRefs(issuesDetailStore);
    const isFullscreen = shallowRef(false);
    let timer = null;
    // 筛选条件状态
    const conditions = shallowRef<IWhereItem[]>([]);
    const queryString = shallowRef('');
    const filterMode = shallowRef<EMode>(EMode.ui);

    const impactScopeResource = shallowRef<ImpactScopeResource>(null);
    const impactScopeResourceKey = shallowRef<'' | ImpactScopeResourceKeyType>('');
    const impactScopeDrawerShow = shallowRef(false);
    // 同步 props 到 Store，驱动 Store 自动请求详情（仅 show 时同步；reset 由 handleShowChange / onUnmounted 负责）
    // 注意：TAPD 首次授权回调场景中，alarm-center 打开本侧滑后，此处同步会触发 store.fetchDetail，
    // detail 数据到达后反过来驱动 IssuesTapd 的弹窗显示（show = createTapdSliderShow && !!detail）。
    watch(
      () => [props.issueBizId, props.issueId],
      () => {
        if (props.show) {
          bizId.value = props.issueBizId;
          issueId.value = props.issueId;
        }
      },
      { immediate: true }
    );
    const handleShowChange = (isShow: boolean) => {
      // 关闭侧滑时主动重置 Store，避免 detail 残留污染下次打开（也切断 IssuesTapd 的 !!detail 条件）
      // alarm-center 所有运行时关闭均经此函数（无外部直接置 alarmDetailShow=false 的运行时路径）
      if (!isShow) {
        issuesDetailStore.reset();
      }
      emit('update:show', isShow);
    };

    // 组件被 v-if 卸载时兜底重置（如 alarmType 切换离开 ISSUES，show 来不及变 false）
    onUnmounted(() => {
      issuesDetailStore.reset();
    });

    /** 下一个 */
    const handleNext = () => {
      emit('next');
    };

    /** 上一个 */
    const handlePrevious = () => {
      emit('previous');
    };

    /** 时间范围变更 */
    const handleTimeRangeChange = value => {
      timeRange.value = value;
    };

    /** 时区变更 */
    const handleTimezoneChange = (value: string) => {
      timezone.value = value;
      window.timezone = value;
      updateTimezone(value);
    };

    /** 强制刷新 */
    const handleImmediateRefresh = () => {
      timeRange.value = [...timeRange.value];
      issuesDetailStore.refresh();
    };

    /** 自动刷新调整 */
    const handleRefreshChange = (value: number) => {
      refreshInterval.value = value;
      if (timer) {
        clearInterval(timer);
      }
      if (value > 0) {
        timer = setInterval(
          () => {
            handleImmediateRefresh();
          },
          Math.max(value, 1000 * 60)
        );
      }
    };

    /** 全屏切换 */
    const handleToggleFullscreen = (value: boolean) => {
      isFullscreen.value = value;
    };

    const handleCreateTapd = () => {
      emit('createTapd', true);
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

    /** issues 重命名 */
    const handleNameChange = (name: string) => {
      detail.value = { ...detail.value, name };
    };

    /** 负责人变更 */
    const handleAssigneeChange = (users: string[]) => {
      detail.value = { ...detail.value, assignee: users };
    };

    /** 优先级变更 */
    const handlePriorityChange = (priority: IssuePriorityType) => {
      detail.value = { ...detail.value, priority };
    };
    /** issues 基础信息状态操作 */
    const handleStatusAction = (status: IssueStatusType) => {
      detail.value = { ...detail.value, status };
    };

    /** 影响范围点击 */
    const handleImpactScopeClick = (event?: ImpactScopeEvent) => {
      impactScopeResourceKey.value = event?.resourceKey;
      impactScopeResource.value = event?.resource;
      impactScopeDrawerShow.value = !!event;
    };

    /** 告警分析添加条件 */
    const handleAddCondition = (condition: CommonCondition) => {
      if (filterMode.value === EMode.ui) {
        let conditionResult: CommonCondition[] = [condition];
        // 持续时间需要特殊处理
        if (condition.key === 'duration') {
          conditionResult = convertDurationArray(condition.value as string[]);
        }
        conditions.value = mergeWhereList(
          conditions.value.filter(item => item.key !== condition.key),
          conditionResult.map(condition => ({
            key: condition.key,
            method: condition.method,
            value: condition.value.map(item => {
              if (item.startsWith('"') && item.endsWith('"')) {
                return item.slice(1, -1);
              }
              return item;
            }),
            ...(conditions.value.length > 1 ? { condition: 'and' } : {}),
            ...(condition?.condition ? { condition: condition.condition } : {}),
          }))
        );
      } else {
        const newClause = `${condition.method === 'neq' ? '-' : ''}${condition.key}: ${condition.value[0]}`;
        queryString.value = appendQueryStringCondition(queryString.value, condition.key, newClause);
      }
    };

    return {
      isFullscreen,
      timeRange,
      timezone,
      refreshInterval,
      detail,
      loading,
      conditions,
      queryString,
      filterMode,
      impactScopeResource,
      impactScopeResourceKey,
      impactScopeDrawerShow,
      handleShowChange,
      handleNext,
      handlePrevious,
      handleTimeRangeChange,
      handleTimezoneChange,
      handleImmediateRefresh,
      handleRefreshChange,
      handleToggleFullscreen,
      handleCreateTapd,
      handleConditionChange,
      handleQueryStringChange,
      handleFilterModeChange,
      handleAssigneeChange,
      handlePriorityChange,
      handleStatusAction,
      handleImpactScopeClick,
      handleAddCondition,
      handleNameChange,
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
              isFullscreen={this.isFullscreen}
              loading={this.loading}
              showStepBtn={this.showStepBtn}
              onCreateTapdSliderShowChange={this.handleCreateTapd}
              onNameChange={this.handleNameChange}
              onNext={this.handleNext}
              onPrevious={this.handlePrevious}
              onToggleFullscreen={this.handleToggleFullscreen}
            />
          ),
          default: () => (
            <div class='issues-detail-side-slider-content'>
              {this.detail && (
                <IssuesSliderWrapper
                  conditions={this.conditions}
                  detail={this.detail}
                  filterMode={this.filterMode}
                  queryString={this.queryString}
                  timeRange={this.timeRange}
                  onAssigneeChange={this.handleAssigneeChange}
                  onConditionChange={this.handleConditionChange}
                  onFilterModeChange={this.handleFilterModeChange}
                  onImpactScopeClick={this.handleImpactScopeClick}
                  onPriorityChange={this.handlePriorityChange}
                  onQueryStringChange={this.handleQueryStringChange}
                  onStatusAction={this.handleStatusAction}
                />
              )}

              <IssuesImpactScopeDrawer
                resource={this.impactScopeResource}
                resourceKey={this.impactScopeResourceKey}
                show={this.impactScopeDrawerShow}
                onFilterByInstance={this.handleAddCondition}
                onUpdate:show={(v: boolean) => {
                  if (v) return;
                  this.handleImpactScopeClick();
                }}
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
