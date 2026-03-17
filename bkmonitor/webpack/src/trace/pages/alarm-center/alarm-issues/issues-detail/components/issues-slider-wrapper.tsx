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

import { IssueDetailTabEnum } from '../../constant';
import IssuesBasicInfo from './issues-basic-info/issues-basic-info';
import IssuesDetailAlarmPanel from './issues-detail-alarm-panel/issues-detail-alarm-panel';
import IssuesDetailAlarmTable from './issues-detail-alarm-table/issues-detail-alarm-table';
import IssuesHistory from './issues-history/issues-history';
import IssuesProcessRecord from './issues-process-record/issues-process-record';
import IssuesRetrievalFilter from './issues-retrieval-filter/issues-retrieval-filter';
import { type TimeRangeType, DEFAULT_TIME_RANGE } from '@/components/time-range/utils';

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
    /** 告警ID */
    alarmId: {
      type: String,
      default: '',
    },
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => DEFAULT_TIME_RANGE,
    },
  },
  setup(props) {
    const currentTab = shallowRef<IssueDetailTabType>(IssueDetailTabEnum.LATEST);

    const handleTabChange = (tab: IssueDetailTabType) => {
      currentTab.value = tab;
    };

    const getPanelComponent = () => {
      switch (currentTab.value) {
        case IssueDetailTabEnum.LATEST:
        case IssueDetailTabEnum.EARLIEST:
          return <IssuesDetailAlarmPanel alarmId={props.alarmId} />;
        case IssueDetailTabEnum.LIST:
          return <IssuesDetailAlarmTable timeRange={props.timeRange} />;
        default:
          return null;
      }
    };

    return {
      currentTab,
      handleTabChange,
      getPanelComponent,
    };
  },
  render() {
    return (
      <div class='issues-slider-wrapper'>
        <div class='issues-slider-left-panel'>
          <IssuesRetrievalFilter />
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
          <IssuesProcessRecord />
          <IssuesHistory />
        </div>
      </div>
    );
  },
});
