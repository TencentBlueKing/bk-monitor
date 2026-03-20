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
import { type PropType, defineComponent, KeepAlive, shallowRef } from 'vue';

import { Tab } from 'bkui-vue';
import { type IWhereItem, EMode } from 'trace/components/retrieval-filter/typing';
import { AlarmServiceFactory } from 'trace/pages/alarm-center/services/factory';
import { AlarmType } from 'trace/pages/alarm-center/typings';

import { IssueDetailTabEnum } from '../../constant';
import DimensionStats from './dimension-stats/dimension-stats';
import IssuesActivity from './issues-activity/issues-activity';
import IssuesBasicInfo from './issues-basic-info/issues-basic-info';
import IssuesDetailAlarmPanel from './issues-detail-alarm-panel/issues-detail-alarm-panel';
import IssuesDetailAlarmTable from './issues-detail-alarm-table/issues-detail-alarm-table';
import IssuesHistory from './issues-history/issues-history';
import IssuesRetrievalFilter from './issues-retrieval-filter/issues-retrieval-filter';
import IssuesTrendChart from './issues-trend-chart/issues-trend-chart';
import { type TimeRangeType, DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '@/components/time-range/utils';

import type { IssueDetailTabType } from '../../typing/constants';

import './issues-slider-wrapper.scss';

// Tab 配置
const TAB_LIST: { label: string; name: IssueDetailTabType }[] = [
  { label: window.i18n.t('最近的告警'), name: IssueDetailTabEnum.LATEST },
  { label: window.i18n.t('最早的告警'), name: IssueDetailTabEnum.EARLIEST },
  { label: window.i18n.t('告警列表'), name: IssueDetailTabEnum.LIST },
];

export default defineComponent({
  name: 'IssuesSliderWrapper',
  props: {
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
    queryStringChange: (_v: string) => true,
    filterModeChange: (_v: EMode) => true,
  },
  setup(props, { emit }) {
    const currentTab = shallowRef<IssueDetailTabType>(IssueDetailTabEnum.LATEST);
    // test
    const tempAlertId = shallowRef('');
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

    const getPanelComponent = () => {
      switch (currentTab.value) {
        case IssueDetailTabEnum.LATEST:
        case IssueDetailTabEnum.EARLIEST:
          return <IssuesDetailAlarmPanel alarmId={props.alarmId || tempAlertId.value} />;
        case IssueDetailTabEnum.LIST:
          return (
            <IssuesDetailAlarmTable
              conditions={props.conditions}
              queryString={props.queryString}
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
      handleTabChange,
      getPanelComponent,
      handleConditionChange,
      handleQueryStringChange,
      handleFilterModeChange,
    };
  },
  render() {
    return (
      <div class='issues-slider-wrapper'>
        <div class='issues-slider-left-panel'>
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
            <IssuesTrendChart />
            <DimensionStats />
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
          <IssuesBasicInfo />
          <IssuesActivity />
          <IssuesHistory />
        </div>
      </div>
    );
  },
});
