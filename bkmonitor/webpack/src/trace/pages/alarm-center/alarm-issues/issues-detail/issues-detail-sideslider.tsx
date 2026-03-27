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
import { defineComponent, shallowRef, watch, watchEffect } from 'vue';

import { Sideslider } from 'bkui-vue';
import { random } from 'monitor-common/utils';
import { getDefaultTimezone, updateTimezone } from 'monitor-pc/i18n/dayjs';
import { type IWhereItem, EMode } from 'trace/components/retrieval-filter/typing';

import IssuesImpactScopeDrawer from '../components/issues-impact-scope-drawer/issues-impact-scope-drawer';
import IssuesSliderHeader from './components/issues-slider-header';
import IssuesSliderWrapper from './components/issues-slider-wrapper';
import { fetchIssueDetailMock } from './mock-data';
import RefreshRate from '@/components/refresh-rate/refresh-rate';
import TimeRange from '@/components/time-range/time-range';
import { handleTransformToTimestamp } from '@/components/time-range/utils';

import type { ImpactScopeEvent, ImpactScopeResource, IssueDetail } from '../typing';
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
    /** issues 第一个告警产生时间 (秒级时间戳) */
    firstAlarmTime: {
      type: [Number, String],
      default: 'now-1h',
    },
    /** 告警ID */
    alarmId: {
      type: String,
      default: '',
    },
    /** issues BizId */
    bizId: {
      type: Number,
      default: undefined,
    } /** 是否展示上一步和下一步按钮 */,
    showStepBtn: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['update:show', 'next', 'previous'],
  setup(props, { emit }) {
    const detail = shallowRef<IssueDetail>(undefined);
    const loading = shallowRef(false);
    const isFullscreen = shallowRef(false);
    const timeRange = shallowRef<(number | string)[]>(['now-1h', 'now']);
    const timezone = shallowRef(getDefaultTimezone());
    const refreshInterval = shallowRef(-1);
    const refreshImmediate = shallowRef(random(4));
    let timer = null;
    // 筛选条件状态
    const conditions = shallowRef<IWhereItem[]>([]);
    const queryString = shallowRef('');
    const filterMode = shallowRef<EMode>(EMode.ui);

    const impactScopeResource = shallowRef<ImpactScopeResource>(null);
    const impactScopeResourceKey = shallowRef<'' | ImpactScopeResourceKeyType>('');
    const impactScopeDrawerShow = shallowRef(false);

    /** 初始化默认查询时间范围 */
    const initTimeRange = () => {
      const firstAlarmTime = props.firstAlarmTime || 'now-1h';
      const time = Number(firstAlarmTime);
      timeRange.value = [Number.isNaN(time) ? firstAlarmTime : time * 1000, 'now'];
    };

    watch(
      () => props.show,
      show => {
        if (show) {
          initTimeRange();
        }
      },
      {
        immediate: true,
      }
    );

    /** 获取Issue详情数据 */
    const getIssueDetailData = () => {
      loading.value = true;
      const [start, end] = handleTransformToTimestamp(timeRange.value);
      fetchIssueDetailMock({
        bk_biz_id: props.bizId,
        id: props.issueId,
        start_time: start,
        end_time: end,
      })
        .then(res => {
          detail.value = res;
        })
        .catch(() => {
          loading.value = false;
        });
    };

    watchEffect(() => {
      if (props.show) {
        getIssueDetailData();
      }
    });

    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

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
      refreshImmediate.value = random(5);
      getIssueDetailData();
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
      detail.value = { ...detail.value, assignee: users };
    };

    /** 优先级变更 */
    const handlePriorityChange = (priority: IssuePriorityType) => {
      detail.value = { ...detail.value, priority };
    };
    /** 标记已解决 */
    const handleResolved = () => {
      detail.value = { ...detail.value, is_resolved: true };
    };

    /** 影响范围点击 */
    const handleImpactScopeClick = (event?: ImpactScopeEvent) => {
      impactScopeResourceKey.value = event?.resourceKey;
      impactScopeResource.value = event?.resource;
      impactScopeDrawerShow.value = !!event;
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
              isFullscreen={this.isFullscreen}
              showStepBtn={this.showStepBtn}
              onNext={this.handleNext}
              onPrevious={this.handlePrevious}
              onToggleFullscreen={this.handleToggleFullscreen}
            />
          ),
          default: () => (
            <div class='issues-detail-side-slider-content'>
              <IssuesSliderWrapper
                alarmId={this.alarmId}
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
                onResolved={this.handleResolved}
              />
              <IssuesImpactScopeDrawer
                resource={this.impactScopeResource}
                resourceKey={this.impactScopeResourceKey}
                show={this.impactScopeDrawerShow}
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
