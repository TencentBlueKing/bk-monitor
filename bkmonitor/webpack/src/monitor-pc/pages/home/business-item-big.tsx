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
import { Component, Emit, Prop, Provide, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import BusinessItem, { type IData as IBusinessCard } from 'fta-solutions/pages/home/business-item';

import BusinessAlarmOverview from './components/business-alarm-overiview';
import BusinessRight from './skeleton/business-right';

import './business-item-big.scss';

interface IProps {
  data?: IBusinessCard;
  /* 首页的时间范围 */
  homeDays?: number;
}
interface IEvent {
  onSticky?: boolean;
  onToEvent?: {
    activeFilterId: any;
    id: string;
  };
}

@Component({
  name: 'BusinessItemBig',
})
export default class BusinessItemBig extends tsc<IProps, IEvent> {
  @Prop({
    type: Object,
    default: () => ({
      name: '',
      id: 0,
      eventCounts: [
        { id: 'event', name: '', count: 0, unit: '' },
        { id: 'alert', name: '', count: 0, unit: '' },
        { id: 'action', name: '', count: 0, unit: '' },
      ],
      seriesData: [
        { level: 2, count: 1 },
        { level: 3, count: 1 },
        { level: 1, count: 1 },
      ],
      countSum: 0,
      dataCounts: [
        { id: 'noise_reduction_ratio', name: '', count: 0, unit: '' },
        { id: 'auto_recovery_ratio', name: '', count: 0, unit: '' },
        { id: 'mtta', name: 'MTTA', count: 0, unit: '' },
        { id: 'mttr', name: 'MTTR', count: 0, unit: '' },
      ],
      isFavorite: false,
      isSticky: false,
      isDemo: false,
    }),
  })
  data: IBusinessCard;
  @Prop({ type: Number, default: 7 }) homeDays: number;

  businessAlarm = [];
  businessAlarmLoading = false;

  @Provide('homeItemBizId')
  get homeItemBizId() {
    return this.data.id;
  }

  @Watch('homeDays')
  handleWatchHomeDays() {
    this.getBusinessAlarmOverviewData();
  }

  created() {
    this.getBusinessAlarmOverviewData();
  }

  async getBusinessAlarmOverviewData() {
    this.businessAlarmLoading = true;
    const data = { uptimecheck: [], service: [], process: [], os: [] };
    this.businessAlarm = [data.uptimecheck, data.service, data.process, data.os];
    this.businessAlarmLoading = false;
  }
  // 置顶
  @Emit('sticky')
  handleSticky(v: boolean) {
    return v;
  }
  @Emit('toEvent')
  handleToEvent(v) {
    return v;
  }

  render() {
    return (
      <div class='home-business-item-big'>
        <BusinessItem
          data={this.data}
          isMakeTop={true}
          onFavorite={this.handleSticky}
          onToEvent={this.handleToEvent}
        />
        <div class='line' />
        {this.businessAlarmLoading ? (
          <BusinessRight />
        ) : (
          <div
            class='right-content'
            // v-bkloading={{ isLoading: this.businessAlarmLoading }}
          >
            <BusinessAlarmOverview
              businessAlarm={this.businessAlarm}
              homeDays={this.homeDays}
            />
          </div>
        )}
      </div>
    );
  }
}
