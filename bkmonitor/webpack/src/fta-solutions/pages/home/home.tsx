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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import Big from 'big.js';
import dayjs from 'dayjs';
import { throttle } from 'throttle-debounce';

import { fetchBusinessInfo } from '../../../monitor-api/modules/commons';
import { statistics } from '../../../monitor-api/modules/home';

import BusinessItem, { IData } from './business-item';

import './home.scss';

export const initUnit = (num: number, type: 'num' | '%' | 'time') => {
  const numObj: { num: number | string; unit: string } = {
    num: 0,
    unit: ''
  };
  if (num === null || num === undefined) {
    numObj.num = '--';
    numObj.unit = '';
    return numObj;
  }
  if (type === 'num') {
    const len = String(num).length;
    const REMAIN_LENGTH = 3;
    if (len <= 3) {
      numObj.num = num;
      numObj.unit = '';
    } else if (len < 7) {
      numObj.num = Big(num).div(1000).round(REMAIN_LENGTH, Big.roundDown).toString();
      numObj.unit = 'K';
    } else if (len < 10) {
      numObj.num = Big(num).div(1000000).round(REMAIN_LENGTH, Big.roundDown).toString();
      numObj.unit = 'M';
    } else if (len >= 10) {
      numObj.num = Big(num).div(1000000000).round(REMAIN_LENGTH, Big.roundDown).toString();
      numObj.unit = 'B';
    }
  }
  if (type === '%') {
    const REMAIN_LENGTH = 1;
    numObj.num = Big(num).times(100).round(REMAIN_LENGTH, Big.roundDown).toString();
    numObj.unit = '%';
  }
  if (type === 'time') {
    const minute = 60;
    const hour = 60 * 60;
    const day = 60 * 60 * 24;
    const REMAIN_LENGTH = 1;
    if (num >= 0 && num < minute) {
      numObj.num = num;
      numObj.unit = window.i18n.tc('秒');
    } else if (num < hour) {
      numObj.num = Big(num).div(minute).round(REMAIN_LENGTH, Big.roundDown).toString();
      numObj.unit = window.i18n.tc('分');
    } else if (num < day) {
      numObj.num = Big(num).div(hour).round(REMAIN_LENGTH, Big.roundDown).toString();
      numObj.unit = window.i18n.tc('小时');
    } else if (num >= day) {
      numObj.num = Big(num).div(day).round(REMAIN_LENGTH, Big.roundDown).toString();
      numObj.unit = window.i18n.tc('天');
    }
  }
  return numObj;
};

interface IDataOverview {
  timeChecked: number;
  timeOption: { id: number; name: string }[];
  data: {
    id: string;
    name: string;
    icon: string;
    num: number;
    unit: string;
    type: 'num' | '%' | 'time';
    borderRight?: boolean;
    tip?: string;
    allowHtml?: boolean;
  }[];
}
interface IBusinessOverview {
  searchValue: string;
  filterItem: number;
  filterList: { id: number; name: string }[];
  data: IData[];
}
interface IHomeProps {
  name: string;
}

@Component({
  name: 'Home'
})
export default class Home extends tsc<IHomeProps> {
  @Ref('mttaTipRef') mttaTipRef: HTMLDivElement;
  @Ref('mttrTipRef') mttrTipRef: HTMLDivElement;

  isShowDetail = false;

  // 数据总览
  dataOverview: IDataOverview = {
    timeChecked: 7,
    timeOption: [
      { id: 7, name: window.i18n.tc('7 天') },
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
        tip: window.i18n.tc('个人有权限查看的空间数')
      },
      {
        id: 'event',
        name: window.i18n.tc('总事件数'),
        icon: 'icon_event',
        num: 0,
        unit: '',
        type: 'num',
        tip: window.i18n.tc('所有业务的事件中心里面告警关联的事件的总和')
      },
      {
        id: 'alert',
        name: window.i18n.tc('总告警数'),
        icon: 'icon_alert',
        num: 0,
        unit: '',
        type: 'num',
        tip: window.i18n.tc('所有业务的事件中心列表中的告警事件的总和')
      },
      {
        id: 'action',
        name: window.i18n.tc('执行数'),
        icon: 'icon_action',
        num: 0,
        unit: '',
        type: 'num',
        borderRight: true,
        tip: window.i18n.tc('处理记录里面所有的执行记录数量')
      },
      {
        id: 'noise_reduction_ratio',
        name: window.i18n.tc('降噪比'),
        icon: 'icon_noise_reduction_ratio',
        num: 0,
        unit: '',
        type: '%',
        tip: window.i18n.tc('(总事件数-总告警数)/总事件数 ， 降噪比越大越好')
      },
      {
        id: 'auto_recovery_ratio',
        name: window.i18n.tc('自愈覆盖率'),
        icon: 'icon_auto_recovery_ratio',
        num: 0,
        unit: '',
        type: '%',
        borderRight: true,
        tip: window.i18n.tc('执行了处理套餐（除工单）的致命告警/总致命告警数，自愈率越高越好')
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
  // 业务概览
  businessOverview: IBusinessOverview = {
    searchValue: '',
    filterItem: 1,
    filterList: [
      { id: 1, name: window.i18n.tc('全部') },
      { id: 2, name: window.i18n.tc('收藏') }
    ],
    data: []
  };

  pageSize = 3;
  page = 1;
  firstPageSize = 0;
  isEnd = false;

  oldSearchValue = '';

  // 业务接入url
  newBizApply = '';
  // 更新时间
  updataTimeStr = window.i18n.t('更新于 {0} ', ['--']);
  updataTimeInstance = null;

  // loading
  loading = false;
  scrollLoading = false;
  businessLoading = false;
  scrollEl = null;
  throttledScroll: Function = () => {};

  created() {
    this.throttledScroll = throttle(300, false, this.handleScroll);
    this.$nextTick(() => {
      this.scrollEl = this.$el;
      this.scrollEl?.addEventListener('scroll', this.throttledScroll);
    });
    fetchBusinessInfo()
      .then(data => {
        this.newBizApply = data.new_biz_apply;
      })
      .catch(e => {
        console.error(e);
      });
    this.init(true);
  }

  beforeDestroy() {
    window.clearInterval(this.updataTimeInstance);
    this.updataTimeInstance = null;
  }

  // 滑动事件
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
        favorite_only: this.businessOverview.filterItem === 2
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

  getStatistics(params) {
    return statistics(params).catch(() => ({ details: [], overview: [], update_time: 0 }));
  }

  // 获取数据
  async init(isCreated = false) {
    // this.businessOverview.data = [];
    this.page = 1;
    this.isEnd = false;
    if (!isCreated) {
      this.businessLoading = true;
    } else {
      this.loading = true;
    }
    this.firstPageSize = (Math.floor((screen.availHeight - 344) / 278) + 1) * 3;
    const params = {
      search: this.businessOverview.searchValue,
      days: this.dataOverview.timeChecked,
      page: 1,
      page_size: this.firstPageSize,
      favorite_only: this.businessOverview.filterItem === 2
    };
    const data: any = await this.getStatistics(params);
    this.getUpdataTime(data.update_time);
    this.autoRefreshUpdataTime(data.update_time);
    // 数据总览
    this.dataOverview.data.forEach(item => {
      const num = (data.overview[item.id]?.count === 0 ? '0' : data.overview[item.id]?.count) || data.overview[item.id];
      const numObj = initUnit(num, item.type);
      item.num = numObj.num as number;
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
      const event = initUnit(item.event.count, 'num');
      const alert = initUnit(item.alert.count, 'num');
      const action = initUnit(item.action.count, 'num');
      const noiseReductionRatio = initUnit(item.noise_reduction_ratio, '%');
      const autoRecoveryRatio = initUnit(item.auto_recovery_ratio, '%');
      const mtta = initUnit(item.mtta, 'time');
      const mttr = initUnit(item.mttr, 'time');
      return {
        ...item,
        name: item.bk_biz_name,
        id: item.bk_biz_id,
        eventCounts: [
          { id: 'event', name: window.i18n.tc('总事件数'), count: event.num, unit: event.unit },
          { id: 'alert', name: window.i18n.tc('总告警数'), count: alert.num, unit: alert.unit },
          { id: 'action', name: window.i18n.tc('总执行数'), count: action.num, unit: action.unit }
        ],
        seriesData: item.alert.levels,
        countSum: item.alert.levels.reduce((acc, cur) => acc + cur.count, 0),
        dataCounts: [
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
        ].map(dataItem => {
          const target = this.dataOverview.data?.find?.(set => set.id === dataItem.id);
          return {
            ...dataItem,
            tip: target?.tip,
            allowHtml: target.allowHtml
          };
        }),
        isFavorite: item.is_favorite,
        isDemo: item.is_demo
      };
    });
  }

  /**
   *
   * @param time 更新时间
   * @description 根据时间戳获取更新时间
   */
  getUpdataTime(time: number) {
    const str = dayjs.tz(time * 1000).fromNow();
    this.updataTimeStr = window.i18n.t('更新于 {0} ', [str]);
  }

  /**
   *
   * @param time 更新时间
   * @description 自动刷新更新时间
   */
  autoRefreshUpdataTime(time: number) {
    window.clearInterval(this.updataTimeInstance);
    this.updataTimeInstance = null;
    this.updataTimeInstance = window.setInterval(() => {
      this.getUpdataTime(time);
    }, 60 * 1000);
  }

  // 收藏
  async handleFavorite(value: boolean, index: number) {
    this.businessOverview.data[index].isFavorite = value;
  }

  // 跳转至事件中心
  handleToEvent(params: { activeFilterId: any; id: string }) {
    if (params.id) {
      // const timeRange = 86400000 * this.dataOverview.timeChecked;
      if (params.activeFilterId) {
        window.open(
          `${location.origin}${location.pathname}?bizId=${params.id}/#/event-center?activeFilterId=${params.activeFilterId}`
        );
      } else {
        window.open(`${location.origin}${location.pathname}?bizId=${params.id}/#/event-center`);
      }
    }
  }

  // 判断搜索条件是否和上个搜索条件一样
  isCanSearch() {
    if (this.businessOverview.searchValue === this.oldSearchValue) {
      return false;
    }
    this.oldSearchValue = `${this.businessOverview.searchValue}`;
    return true;
  }

  getSvgIcon(icon) {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require(`../../static/img/home/${icon}.svg`);
  }

  protected render() {
    return (
      <div
        class='fta-home'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='fta-home-wrapper'>
          <div class='fta-home-content'>
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
                    onClick={() => {
                      window.open(this.newBizApply);
                    }}
                  >
                    {this.$t('接入业务')}
                  </bk-button>
                </span>
              </div>
              <div class='overview-content'>
                {this.dataOverview.data.map(item => (
                  <div
                    class={['data-item', { 'border-right': item?.borderRight }]}
                    v-bk-tooltips={{
                      content: item.allowHtml ? this[item.tip] || '' : item.tip,
                      delay: [500, 0],
                      theme: 'light',
                      placements: ['top'],
                      boundary: 'window',
                      maxWidth: 250
                    }}
                  >
                    <span class='item-top'>
                      <span class='num'>{item.num}</span>
                      <span class='unit'>{item.unit}</span>
                    </span>
                    <span class='item-bottom'>
                      <img
                        src={this.getSvgIcon(item.icon)}
                        alt=''
                      />
                      <span class='title'>{item.name}</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div class='business-overview'>
              <div class='overview-title'>
                <span class='left'>
                  <span class='title'>{this.$t('概览')}</span>
                  <span class='msg'>{this.updataTimeStr}</span>
                </span>
                <span class='right'>
                  <bk-input
                    placeholder={this.$t('输入')}
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
                  {this.businessOverview.data.map((item, index) => (
                    <BusinessItem
                      data={item}
                      key={index}
                      // eslint-disable-next-line @typescript-eslint/no-misused-promises
                      onFavorite={(v: boolean) => this.handleFavorite(v, index)}
                      onToEvent={this.handleToEvent}
                    ></BusinessItem>
                  ))}
                </div>
              ) : (
                <bk-exception
                  v-bkloading={{ isLoading: this.businessLoading }}
                  type='empty'
                  ext-cls='home-no-data'
                >
                  <span class='home-no-data-msg'>{this.$t('无数据')}</span>
                </bk-exception>
              )}
            </div>
          </div>
          <div
            class='home-scrollload'
            v-bkloading={{ isLoading: this.scrollLoading, opacity: 0, color: '#fff0' }}
          ></div>
        </div>
        <div style={{ display: 'none' }}>
          <div ref='mttaTipRef'>
            <div>
              {window.i18n.tc('平均应答时间，从告警真实发生到用户响应的平均时间。平均应答时间=总持续时间/总告警数量')}
            </div>
            <div>
              {window.i18n.tc(
                '总持续时间：所有告警的首次异常时间到下一个状态变更的时间点，如确认/屏蔽/恢复/关闭/已解决'
              )}
            </div>
          </div>
        </div>
        <div style={{ display: 'none' }}>
          <div ref='mttrTipRef'>
            <div>
              {window.i18n.tc('平均解决时间，从告警真实发生到告警被处理的平均时间。平均解决时间=总持续时间/总告警数量')}
            </div>
            <div>{window.i18n.tc('总持续时间: 所有告警的首次异常时间到告警标记为已解决或已恢复的时间。')}</div>
          </div>
        </div>
      </div>
    );
  }
}
