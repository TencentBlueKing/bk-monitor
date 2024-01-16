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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';
import { throttle } from 'throttle-debounce';

import { IData as IBusinessCard } from '../../../fta-solutions/pages/home/business-item';
import { initUnit } from '../../../fta-solutions/pages/home/home';
import { fetchBusinessInfo } from '../../../monitor-api/modules/commons';
import { statistics } from '../../../monitor-api/modules/home';
import MonitorDialog from '../../../monitor-ui/monitor-dialog';
import EmptyStatus from '../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../components/empty-status/types';
import NoBussiness from '../no-business/no-business.vue';

import BusinessItemBig from './business-item-big';
import NoBusinessItem from './no-business-item';
import OverviewContent, { IData as IDataOverviewData } from './overview-content';

import './home.scss';

interface IDataOverview {
  timeChecked: number;
  timeOption: { id: number; name: string }[];
  data: IDataOverviewData[];
}
interface IBusinessOverview {
  searchValue: string;
  filterItem: number;
  filterList: { id: number; name: string }[];
  data: IBusinessCard[];
}

// 过滤选项
const FILTER_LIST = [
  { id: 1, name: window.i18n.tc('全部') },
  { id: 2, name: window.i18n.tc('有告警') },
  { id: 3, name: window.i18n.tc('无告警') },
  { id: 4, name: window.i18n.tc('测试中') },
  { id: 5, name: window.i18n.tc('已上线') },
  { id: 6, name: window.i18n.tc('置顶') }
];

// 过滤选项对应的参数
const FILTER_PARAMS_MAP = {
  1: {},
  2: { alert_filter: 'has_alert' },
  3: { alert_filter: 'no_alert' },
  4: { life_cycle: 1 },
  5: { life_cycle: 2 },
  6: { sticky_only: true }
};

@Component({
  name: 'Home'
})
export default class Home extends tsc<{}> {
  // 数据总览
  dataOverview: IDataOverview = {
    timeChecked: 7,
    timeOption: [
      { id: 1, name: window.i18n.tc('1 天') },
      { id: 7, name: window.i18n.tc('7 天') },
      { id: 15, name: window.i18n.tc('15 天') },
      { id: 30, name: window.i18n.tc('一个月') }
    ],
    data: [
      {
        id: 'business',
        name: window.i18n.tc('空间数'),
        icon: 'icon_business',
        num: 0,
        unit: '',
        type: 'num',
        borderRight: true,
        tip: window.i18n.tc('空间数量指个人有权限的空间数量')
      },
      {
        id: 'event',
        name: window.i18n.tc('事件数'),
        icon: 'icon_event',
        num: 0,
        unit: '',
        type: 'num',
        tip: window.i18n.tc('总事件数指通过策略检测产生的所有告警明细，具体查看告警事件的关联事件')
      },
      {
        id: 'alert',
        name: window.i18n.tc('告警数'),
        icon: 'icon_alert',
        num: 0,
        unit: '',
        type: 'num',
        tip: window.i18n.tc('总告警数指告警事件中告警数量的总和')
      },
      {
        id: 'action',
        name: window.i18n.tc('执行数'),
        icon: 'icon_action',
        num: 0,
        unit: '',
        type: 'num',
        borderRight: true,
        tip: window.i18n.tc('执行数指告警事件中执行记录数量的总和')
      },
      {
        id: 'noise_reduction_ratio',
        name: window.i18n.tc('降噪比'),
        icon: 'icon_noise_reduction_ratio',
        num: 0,
        unit: '',
        type: '%',
        tip: window.i18n.tc('降噪比=(总事件数-总告警数) / 总事件数 ， 降噪比越大表示告警收敛效果好')
      },
      {
        id: 'auto_recovery_ratio',
        name: window.i18n.tc('自愈覆盖率'),
        icon: 'icon_auto_recovery_ratio',
        num: 0,
        unit: '',
        type: '%',
        borderRight: true,
        tip: window.i18n.tc('自愈覆盖率指致命告警有告警处理(除工单外) / 总致命告警数，致命告警建议补齐自愈能力')
      },
      {
        id: 'mtta',
        name: 'MTTA',
        icon: 'icon_mtta',
        num: 0,
        unit: '',
        type: 'time',
        tip: 'mttaTipRef',
        allowHtml: true
      },
      {
        id: 'mttr',
        name: 'MTTR',
        icon: 'icon_mttr',
        num: 0,
        unit: '',
        type: 'time',
        tip: 'mttrTipRef',
        allowHtml: true
      }
    ]
  };

  businessOverview: IBusinessOverview = {
    searchValue: '',
    filterItem: 1,
    filterList: FILTER_LIST,
    data: []
  };

  emptyStatusType: EmptyStatusType = 'empty';
  // 更新时间
  updataTimeStr = window.i18n.t('更新于 {0} ', ['--']);
  updataTimeInstance = null;

  // 业务接入url
  newBizApply = '';
  businessLoading = false;

  scrollLoading = false;

  pageSize = 3;
  page = 1;
  firstPageSize = 0;
  isEnd = false;
  loading = false;

  oldSearchValue = '';
  showGuide = false;
  throttledScroll: Function = () => {};

  get homeDays() {
    return this.dataOverview.timeChecked;
  }

  created() {
    fetchBusinessInfo()
      .then(data => {
        this.newBizApply = data.new_biz_apply;
      })
      .catch(e => {
        console.info(e);
      });
    this.init(true);
  }

  mounted() {
    this.throttledScroll = throttle(300, false, this.handleScroll);
    const targetEl: HTMLDivElement = document.querySelector('.page-container');
    targetEl.addEventListener('scroll', this.throttledScroll as any);
  }

  beforeDestroy() {
    const targetEl: HTMLDivElement = document.querySelector('.page-container');
    targetEl.removeEventListener('scroll', this.throttledScroll as any);
  }
  /**
   *
   * @param isCreated 是否是初始化
   */
  async init(isCreated = false) {
    this.emptyStatusType = this.businessOverview.searchValue ? 'search-empty' : 'empty';
    this.page = 1;
    this.isEnd = false;
    if (!isCreated) {
      this.businessLoading = true;
    } else {
      this.loading = true;
    }
    this.firstPageSize = Math.floor((screen.availHeight - 344) / 278) + 1;
    const params = {
      search: this.businessOverview.searchValue,
      days: this.dataOverview.timeChecked,
      page: 1,
      page_size: this.firstPageSize,
      allowed_only: !Boolean(this.businessOverview.searchValue),
      ...FILTER_PARAMS_MAP[this.businessOverview.filterItem]
    };
    const data: any = await this.getStatistics(params);
    if (data.error) this.emptyStatusType = '500';
    this.getUpdataTime(data.update_time);
    this.autoRefreshUpdataTime(data.update_time);
    // 数据总览
    this.dataOverview.data.forEach(item => {
      const num = (data.overview[item.id]?.count === 0 ? '0' : data.overview[item.id]?.count) || data.overview[item.id];
      const numObj = initUnit(num, item.type);
      item.num = +(+numObj.num).toFixed(1);
      item.unit = numObj.unit;
    });
    // 业务概览
    this.businessOverview.data = this.getDetails(data.details);
    // 是否到底
    if (this.businessOverview.data.length < this.firstPageSize) {
      this.isEnd = true;
    } else {
      this.pageSize = this.firstPageSize;
      this.page = this.firstPageSize / this.pageSize;
    }
    this.businessLoading = false;
    this.loading = false;
  }

  // 业务概览数据
  getDetails(details) {
    return details.map(item => {
      if (item.is_allowed) {
        const event = initUnit(item.event.count, 'num');
        const alert = initUnit(item.alert.count, 'num');
        const action = initUnit(item.action.count, 'num');
        const noiseReductionRatio = initUnit(item.noise_reduction_ratio, '%');
        const autoRecoveryRatio = initUnit(item.auto_recovery_ratio, '%');
        const mtta = initUnit(item.mtta, 'time');
        const mttr = initUnit(item.mttr, 'time');
        let dataCounts = [
          {
            id: 'noise_reduction_ratio',
            name: window.i18n.tc('降噪比'),
            count: noiseReductionRatio.num,
            unit: noiseReductionRatio.unit
          },
          {
            id: 'auto_recovery_ratio',
            name: window.i18n.tc('自愈覆盖率'),
            count: autoRecoveryRatio.num,
            unit: autoRecoveryRatio.unit
          },
          { id: 'mtta', name: 'MTTA', count: mtta.num, unit: mtta.unit },
          { id: 'mttr', name: 'MTTR', count: mttr.num, unit: mttr.unit }
        ];
        dataCounts = dataCounts.map(item => {
          const target = this.dataOverview.data?.find?.(set => set.id === item.id);
          return {
            ...item,
            tip: target?.tip,
            allowHtml: target.allowHtml
          };
        });
        return {
          ...item,
          name: item.bk_biz_name,
          id: item.bk_biz_id,
          eventCounts: [
            { id: 'event', name: window.i18n.tc('事件数'), count: event.num, unit: event.unit },
            { id: 'alert', name: window.i18n.tc('告警数'), count: alert.num, unit: alert.unit },
            { id: 'action', name: window.i18n.tc('执行数'), count: action.num, unit: action.unit }
          ],
          seriesData: item.alert.levels,
          countSum: item.alert.levels.reduce((acc, cur) => acc + cur.count, 0),
          dataCounts,
          isFavorite: item.is_favorite,
          isSticky: item.is_sticky,
          isDemo: item.is_demo,
          isAllowed: item.is_allowed
        };
      }
      return {
        ...item,
        name: item.bk_biz_name,
        id: item.bk_biz_id,
        isAllowed: item.is_allowed
      };
    });
  }

  async handleScroll(e: any) {
    if (this.isEnd) return;
    if (this.scrollLoading) return;
    const { scrollHeight, scrollTop, clientHeight } = e.target;
    // 大屏有误差所以要+1
    const isEnd = scrollHeight - scrollTop <= clientHeight + 1 && scrollTop !== 0;
    if (isEnd) {
      this.scrollLoading = true;
      this.page += 1;
      const params = {
        search: this.businessOverview.searchValue,
        days: this.dataOverview.timeChecked,
        page: this.page,
        page_size: this.pageSize,
        allowed_only: !Boolean(this.businessOverview.searchValue),
        ...FILTER_PARAMS_MAP[this.businessOverview.filterItem]
      };
      const data: any = await this.getStatistics(params);
      this.getUpdataTime(data.update_time);
      this.autoRefreshUpdataTime(data.update_time);
      this.businessOverview.data.push(...this.getDetails(data.details));
      // 是否到底
      if (this.businessOverview.data.length < (this.page - 1) * this.pageSize || !data.details.length) {
        this.isEnd = true;
      }
      this.scrollLoading = false;
    }
  }

  isCanSearch() {
    if (this.businessOverview.searchValue === this.oldSearchValue) {
      return false;
    }
    this.oldSearchValue = `${this.businessOverview.searchValue}`;
    return true;
  }

  getStatistics(params) {
    return statistics(params).catch(() => ({ details: [], overview: [], update_time: 0, error: true }));
  }

  // 更新时间
  getUpdataTime(time: number) {
    const str = dayjs.tz(time * 1000).fromNow();
    this.updataTimeStr = window.i18n.t('更新于 {0} ', [str]);
  }
  // 刷新更新时间
  autoRefreshUpdataTime(time: number) {
    window.clearInterval(this.updataTimeInstance);
    this.updataTimeInstance = null;
    this.updataTimeInstance = window.setInterval(() => {
      this.getUpdataTime(time);
    }, 60 * 1000);
  }

  // 置顶
  async handleSticky() {
    this.init();
  }

  // 跳转至事件中心
  handleToEvent(params: { activeFilterId: any; id: string }) {
    if (!params.id) return;
    let query = '';
    if (params.activeFilterId) {
      query = `from=now-${this.homeDays}d&to=now&bizIds=${params.id}&activeFilterId=${params.activeFilterId}`;
    } else {
      query = `from=now-${this.homeDays}d&to=now&bizIds=${params.id}`;
    }
    const url = `${location.origin}${location.pathname}?bizId=${params.id}#/event-center?${query}`;
    location.href = url;
  }
  handleOpenGuide() {
    this.showGuide = true;
  }
  /**
   *
   * @param type 操作类型
   */
  handleOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.businessOverview.searchValue = '';
    }
    this.init();
  }

  render() {
    return (
      <div class='monitor-home'>
        <div class='monitor-home-wrapper'>
          <div class='monitor-home-content'>
            <div class='data-overview'>
              <div class='overview-title'>
                <span class='left'>
                  <span class='title'>{this.$t('数据总览')}</span>
                  <span class='msg'>{this.updataTimeStr}</span>
                </span>
                <span class='right'>
                  <bk-select
                    v-model={this.dataOverview.timeChecked}
                    ext-cls='time-select'
                    clearable={false}
                    popover-width={70}
                    on-change={() => this.init(true)}
                  >
                    {this.dataOverview.timeOption.map(option => (
                      <bk-option
                        key={option.id}
                        id={option.id}
                        name={option.name}
                      ></bk-option>
                    ))}
                  </bk-select>
                  <bk-button
                    theme={'primary'}
                    onClick={this.handleOpenGuide}
                  >
                    {this.$t('button-接入指引')}
                  </bk-button>
                </span>
              </div>
              <OverviewContent data={this.dataOverview.data}></OverviewContent>
            </div>
            <div class='business-overview'>
              <div class='overview-title'>
                <span class='left'>
                  <span class='title'>{this.$t('概览')}</span>
                  <span class='msg'>{this.updataTimeStr}</span>
                </span>
                <span class='right'>
                  <bk-input
                    placeholder={this.$t('输入空间ID、空间名')}
                    right-icon='bk-icon icon-search'
                    v-model={this.businessOverview.searchValue}
                    on-right-icon-click={() => this.isCanSearch() && this.init()}
                    on-enter={() => this.isCanSearch() && this.init()}
                    on-blur={() => this.isCanSearch() && this.init()}
                  ></bk-input>
                  <bk-select
                    v-model={this.businessOverview.filterItem}
                    clearable={false}
                    ext-cls='filter-select'
                    on-change={() => this.init()}
                  >
                    {this.businessOverview.filterList.map(option => (
                      <bk-option
                        key={option.id}
                        id={option.id}
                        name={option.name}
                      ></bk-option>
                    ))}
                  </bk-select>
                </span>
              </div>
              {this.businessOverview.data.length ? (
                <div
                  class='overview-content'
                  v-bkloading={{ isLoading: this.businessLoading }}
                >
                  {this.businessOverview.data.map(item =>
                    item.isAllowed ? (
                      <BusinessItemBig
                        key={item.id}
                        data={item}
                        homeDays={this.homeDays}
                        onSticky={() => this.handleSticky()}
                        onToEvent={this.handleToEvent}
                      ></BusinessItemBig>
                    ) : (
                      <NoBusinessItem data={{ ...item }}></NoBusinessItem>
                    )
                  )}
                </div>
              ) : (
                <EmptyStatus
                  type={this.emptyStatusType}
                  onOperation={this.handleOperation}
                />
              )}
            </div>
          </div>
        </div>
        <div
          class='home-scrollload'
          v-bkloading={{ isLoading: this.scrollLoading, opacity: 0, color: '#fff0' }}
        ></div>
        <MonitorDialog
          class='no-business-guide'
          value={this.showGuide}
          onChange={v => (this.showGuide = v)}
          needFooter={false}
          fullScreen={true}
        >
          <div class='no-business-guide-body'>
            <NoBussiness />
          </div>
        </MonitorDialog>
      </div>
    );
  }
}
