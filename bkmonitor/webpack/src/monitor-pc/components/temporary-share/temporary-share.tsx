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
import { VNode } from 'vue';
import { TranslateResult } from 'vue-i18n';
import { Component, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { createShareToken, deleteShareToken, updateShareToken } from '../../../monitor-api/modules/share';
import { copyText } from '../../../monitor-common/utils/utils';
import MonitorDialog from '../../../monitor-ui/monitor-dialog';
import { NavBarMode } from '../../pages/monitor-k8s/components/common-nav-bar';
import { INavItem } from '../../pages/monitor-k8s/typings';
import TimeRangeComponent, { TimeRangeType } from '../time-range/time-range';
import { shortcuts, TimeRange } from '../time-range/utils';
import TimeSelect, { ITimeListItem } from '../time-select/time-select';

import HistoryShareManage from './history-share-manage';

import './temporary-share.scss';
// const MomentFormater = 'YYYY-MM-DD HH:mm:ss';

export interface ITemporaryShareProps {
  navList?: INavItem[];
  onlyCopy?: boolean;
  navMode?: NavBarMode;
  customData?: Record<string, any>;
  positionText?: string;
  pageInfo?: Record<string, any>;
}
@Component
export default class TemporaryShareNew extends tsc<ITemporaryShareProps> {
  // 导航列表 用于缓存dashabord tile
  @Prop() navList: INavItem[];
  // 是否仅是复制 显示复制链接 否：显示临时分享
  // @Prop({ type: Boolean, default: true }) onlyCopy: boolean;
  // 一些自定义分享数据
  @Prop({ default: () => ({}) }) customData: Record<string, any>;
  /** 定位文本 */
  @Prop({ type: String }) positionText: string;
  @Prop({ type: String, default: 'copy' }) navMode: NavBarMode;
  /* 当前分享页的基本信息（用于页面路径显示） */
  @Prop({ type: Object, default: () => ({}) }) pageInfo: Record<string, any>;
  @InjectReactive('readonly') readonly readonly: boolean;

  // 展示弹窗
  show = false;
  // 查询时间段
  timeRange: string[] = [];
  // 时区
  timezone: string = window.timezone;
  // 缓存查询时间段
  oldTimeRange: string[] = [];
  // 是否锁定查询时间
  isLockSearch = true;
  // 分享有效期 默认 7d
  validityPeriod = '1w';
  // 有效期列表
  validityList: ITimeListItem[] = [];
  // 分享链接token
  token = '';
  // 初始化弹层层级
  zIndex: number = window.__bk_zIndex_manager?.nextZIndex();
  /** 时间快捷选项 */
  shortcuts = shortcuts;
  timeRangePanelShow = false;
  /* 查询设置 */
  querySettings = [
    {
      id: 'time',
      name: window.i18n.t('变量选择'),
      canChange: true,
      timeRange: [],
      timezone: window.timezone
    }
  ];
  /* 管理历史分享 */
  historyData = {
    show: false
  };
  /* 分享有效期的校验 */
  validityPeriodErr = false;
  // 分享链接
  get shareUrl() {
    return `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}/#/share/${this.token || ''}`;
  }
  get onlyCopy() {
    return this.navMode === 'copy';
  }
  get onlyDisplay() {
    return this.navMode === 'display';
  }

  created() {
    this.validityList = [
      {
        id: '1d',
        name: this.$tc('1 天')
      },
      {
        id: '1w',
        name: this.$tc('1 周')
      },
      {
        id: '1M',
        name: this.$tc('1 月')
      }
    ];
  }
  setDefaultSettings() {
    const { from, to, timezone } = this.$route.query as Record<string, string>;
    this.querySettings = [
      {
        id: 'time',
        name: window.i18n.t('变量选择'),
        canChange: true,
        timeRange: [from || 'now-7d', to || 'now'],
        timezone: timezone || window.timezone
      }
    ];
  }
  // 通用api查询参数
  getShareTokenParams() {
    const period = this.validityPeriod.match(/([0-9]+)/)?.[0] || 1;
    let weWebData = {};
    if (window.__BK_WEWEB_DATA__) {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { $baseStore = null, ...data } = { ...window.__BK_WEWEB_DATA__ };
      weWebData = { ...data };
    }
    const { canChange, timeRange, timezone } = this.querySettings[0];
    // const isDefaultTimeRange = timeRange.every(item => CUSTOM_TIME_RANGE_REG.test(item));
    return {
      type: this.$route.name === 'event-center' ? 'event' : this.$route.query.sceneId,
      expire_time: dayjs
        .tz()
        .add(period, (this.validityPeriod.split(period.toString())?.[1] || 'h') as any)
        .unix(),
      expire_period: this.validityPeriod,
      lock_search: !canChange,
      start_time: dayjs(this.timeRange[0]).unix(),
      end_time: dayjs(this.timeRange[1]).unix(),
      timezone,
      default_time_range: timeRange,
      data: {
        query: Object.assign(
          {},
          {
            ...this.$route.query,
            timezone
          },
          !canChange
            ? {
                from: timeRange[0],
                to: timeRange[1]
              }
            : {}
        ),
        name: this.$route.name,
        params: this.$route.params,
        path: this.$route.path,
        navList: this.navList,
        weWebData,
        ...(this.customData || {})
      }
    };
  }
  // 创建token
  async createShareToken() {
    const data = await createShareToken(this.getShareTokenParams()).catch(() => ({ token: '' }));
    this.token = data.token;
  }
  // 更新token
  async updateShareToken() {
    const data = await updateShareToken({
      ...this.getShareTokenParams(),
      token: this.token
    }).catch(() => ({ token: this.token }));
    this.token = data.token || this.token;
  }
  // 显示弹窗
  async handleShowDialog() {
    if (this.readonly || this.onlyDisplay) {
      return;
    }
    if (this.onlyCopy) {
      this.handleCopyLink(location.href);
      return;
    }
    this.zIndex = window.__bk_zIndex_manager.nextZIndex();
    // const { from = 'now-1h', to = 'now' } = this.$route.query;
    // this.timeRange = new TimeRange([from.toString(), to.toString()]).format();
    // this.oldTimeRange = this.timeRange.slice();
    this.setDefaultSettings();
    await this.createShareToken();
    this.show = true;
  }
  // 隐藏弹窗
  handleHideDialog() {
    this.show = false;
  }
  // 自定义有效期时间
  handleAddTime(item: ITimeListItem) {
    this.validityList.push(item);
  }
  /**
   * @description: 有效期变更事件
   * @param {string} v 有效期时间
   * @return {*}
   */
  handleValidityChange(v: string) {
    this.validityPeriod = v;
    // 最大有效期90天
    const num = Number(v.replace(/(m|h|d|w|M|y)$/, '') || 0);
    const unit = v.replace(/^([1-9][0-9]*)+/, '');
    if (
      !(
        (unit === 'm' && num <= 129600) ||
        (unit === 'h' && num <= 2160) ||
        (unit === 'd' && num <= 90) ||
        (unit === 'w' && num < 13) ||
        (unit === 'M' && num <= 3) ||
        (unit === 'y' && num <= 0.25)
      )
    ) {
      this.validityPeriodErr = true;
      return;
    }
    this.validityPeriodErr = false;
    this.updateShareToken();
  }
  /**
   * @description: 锁定查询变更
   * @param {boolean} v 是否锁定
   * @return {*}
   */
  handleLockSearchChange(v: boolean) {
    this.isLockSearch = v;
    this.updateShareToken();
  }
  /**
   * @description: 查询时间段变更
   * @param {string} v 查询时间段
   * @return {*}
   */
  handleTimeRangeChange(v: string[]) {
    this.oldTimeRange = v;
  }
  /**
   * @description: 查询时间段弹窗变更触发事件
   * @return {*}
   */
  async openChange(v: boolean) {
    this.timeRangePanelShow = v;
    setTimeout(() => (this.oldTimeRange = this.timeRange), 300);
  }
  /**
   * @description: 点击确认触发
   * @return {*}
   */
  handlePickSuccess() {
    this.timeRange = this.oldTimeRange;
    this.updateShareToken();
  }
  /**
   * @description: 点击复制链接触发
   * @param {string} url 分享链接
   * @return {*}
   */
  handleCopyLink(url?: string) {
    let hasErr = false;
    copyText(typeof url === 'string' ? url : this.shareUrl, (errMsg: string) => {
      this.$bkMessage({
        message: errMsg,
        theme: 'error'
      });
      hasErr = !!errMsg;
    });
    if (!hasErr) this.$bkMessage({ theme: 'success', message: this.$t('复制成功') });
  }
  /** 点击快捷时间选项 */
  handleShortcutChange(data) {
    if (!!data?.value) {
      this.timeRange = new TimeRange([...data.value] as TimeRangeType).format();
      this.oldTimeRange = this.timeRange.slice();
      this.timeRangePanelShow = false;
      this.updateShareToken();
    }
  }
  /**
   * @description: 点击收回访问权限触发
   * @return {*}
   */
  handleDeleteAuth() {
    this.$bkInfo({
      type: 'warning',
      title: this.$t('确定收回访问权限'),
      subTitle: this.$t('所有的历史分享链接都将失效'),
      confirmFn: async () =>
        deleteShareToken({
          type: this.getShareTokenParams().type
        })
          .then(() => {
            this.$bkMessage({
              theme: 'success',
              message: this.$t('回收成功')
            });
            this.show = false;
            return true;
          })
          .catch(() => false)
    });
  }
  /**
   * @description: 通用格式组件
   * @param {TranslateResult} title 名称
   * @param {VNode} child 子组件
   * @return {*} VNode
   */
  commonItem(title: TranslateResult, child: VNode) {
    return (
      <div class='share-item'>
        <span class='share-item-title'>{title}</span>
        <div class='share-item-content'>{child}</div>
      </div>
    );
  }
  /**
   * @description: 分享链接组件
   * @return {*} VNode
   */
  shareLink(): VNode {
    return (
      <div class='share-link'>
        <span class='share-link-input'>{this.shareUrl}</span>
        <bk-button
          class='share-link-btn'
          theme='primary'
          onClick={this.handleCopyLink}
        >
          {this.$t('复制链接')}
        </bk-button>
      </div>
    );
  }
  /**
   * @description: 锁定查询时间组件
   * @return VNode
   */
  lockTimeRange(): VNode {
    return (
      <div class='lock-timerange'>
        <bk-switcher
          value={this.isLockSearch}
          theme='primary'
          onChange={this.handleLockSearchChange}
        ></bk-switcher>
      </div>
    );
  }
  /**
   * @description: 查询时间段组件
   * @return VNode
   */
  shareTimeRange(): VNode {
    return (
      <div class='share-timerange'>
        <bk-date-picker
          placeholder={this.$t('选择查询时间段')}
          type='datetimerange'
          editable
          clearable={false}
          open={this.timeRangePanelShow}
          value={this.oldTimeRange}
          onChange={this.handleTimeRangeChange}
          onopen-change={this.openChange}
          onpick-success={this.handlePickSuccess}
        >
          <ul
            slot='shortcuts'
            class='shortcuts-list'
          >
            {this.shortcuts.map(item => (
              <li
                class='shortcuts-item'
                onClick={() => this.handleShortcutChange(item)}
              >
                {item.text}
              </li>
            ))}
          </ul>
        </bk-date-picker>
      </div>
    );
  }
  /**
   * @description: 有效期期行组件
   * @return VNode
   */
  shareDeadline(): VNode {
    return (
      <div class='share-deadline'>
        <TimeSelect
          value={this.validityPeriod}
          list={this.validityList}
          tip={this.$t('自定义输入格式: 如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年')}
          onAddItem={this.handleAddTime}
          onChange={this.handleValidityChange}
        />
        {this.validityPeriodErr && <div class='validity-period-err'>{this.$t('注意：最大值为90天')}</div>}
        {/* <bk-button class="share-deadline-btn" theme="primary" outline onClick={this.handleDeleteAuth}>
        {this.$t('收回访问权限')}
      </bk-button> */}
      </div>
    );
  }

  handleShowHistory(v: boolean) {
    this.historyData.show = v;
  }

  handleTableTimeRangeChange(val: TimeRangeType, row) {
    row.timeRange = [...val];
    this.updateShareToken();
  }
  handleTableTimezoneChange(val: string, row) {
    row.timezone = val;
    this.updateShareToken();
  }
  handleCanChange(v, row) {
    row.canChange = v;
    this.updateShareToken();
  }

  render() {
    const tipsOpts = {
      content: !this.onlyCopy ? this.$t('临时分享') : this.$t('复制链接'),
      delay: 200,
      boundary: 'window',
      placement: 'right',
      disabled: this.readonly || this.onlyDisplay
    };
    return (
      <div class='temporary-share'>
        {!this.positionText?.length ? (
          <span
            class={['icon-monitor', this.onlyCopy ? 'icon-mc-target-link' : 'temporary-share-icon', 'icon-mc-share']}
            v-bk-tooltips={tipsOpts}
            onClick={this.handleShowDialog}
          ></span>
        ) : (
          <div
            class={['position-bar', { readonly: this.readonly, display: this.onlyDisplay }]}
            v-bk-tooltips={tipsOpts}
            onClick={this.handleShowDialog}
          >
            <i
              class='icon-monitor icon-dingwei'
              style='font-size: 14px'
            />
            <span class='position-text'>{this.positionText}</span>
            {!this.onlyDisplay && !this.readonly && (
              <span
                class={[
                  'icon-monitor',
                  'copy-text-button',
                  this.onlyCopy ? 'icon-copy-link' : 'temporary-share-icon',
                  'icon-mc-share'
                ]}
                style='font-size: 12px; margin: 0px; color: #3A84FF'
              />
            )}
          </div>
        )}
        {!this.onlyCopy && (
          <MonitorDialog
            value={this.show}
            needFooter={false}
            width={700}
            title={this.$t('临时分享').toString()}
            appendToBody={true}
            zIndex={this.zIndex}
            class='temporary-share'
            onChange={this.handleHideDialog}
          >
            <span
              slot='header'
              class='header'
            >
              <span>{this.$t('临时分享')}</span>
              <span
                class='link-wrap'
                onClick={() => this.handleShowHistory(true)}
              >
                <span class='icon-monitor icon-setting'></span>
                <span>{this.$t('管理历史分享')}</span>
              </span>
            </span>
            <div
              class='share-wrap'
              style='margin-top: 18px'
            >
              {this.commonItem(this.$t('分享链接'), this.shareLink())}
            </div>
            <div class='share-wrap'>{this.commonItem(this.$t('链接有效期'), this.shareDeadline())}</div>
            <div class='share-wrap'>
              {this.commonItem(
                this.$t('查询设置'),
                this.show && (
                  <bk-table data={this.querySettings}>
                    <bk-table-column
                      label={this.$t('变量名称')}
                      scopedSlots={{
                        default: () => <span>{this.$t('时间选择')}</span>
                      }}
                    ></bk-table-column>
                    <bk-table-column
                      label={this.$t('是否可更改')}
                      scopedSlots={{
                        default: ({ row }) => (
                          <bk-switcher
                            value={row.canChange}
                            theme='primary'
                            onChange={v => this.handleCanChange(v, row)}
                          ></bk-switcher>
                        )
                      }}
                    ></bk-table-column>
                    <bk-table-column
                      label={this.$t('默认选项')}
                      width={386}
                      scopedSlots={{
                        default: ({ row }) => (
                          <div class='time-warp'>
                            <TimeRangeComponent
                              type={'normal'}
                              value={row.timeRange}
                              timezone={row.timezone || this.timezone}
                              onTimezoneChange={v => this.handleTableTimezoneChange(v, row)}
                              onChange={v => this.handleTableTimeRangeChange(v, row)}
                            ></TimeRangeComponent>
                          </div>
                        )
                      }}
                    ></bk-table-column>
                  </bk-table>
                )
              )}
            </div>
            {/* {
            this.$route.name !== 'event-center' && <div class="share-wrap">
              {
                this.commonItem(this.$t('查询时间段'), this.shareTimeRange())
              }
              {
                this.commonItem(this.$t('锁定查询时间'), this.lockTimeRange())
              }
            </div>
          } */}
          </MonitorDialog>
        )}
        {this.historyData.show && (
          <HistoryShareManage
            show={this.historyData.show}
            shareUrl={this.shareUrl}
            pageInfo={this.pageInfo}
            positionText={this.positionText}
            navList={this.navList}
            onShowChange={v => this.handleShowHistory(v)}
          ></HistoryShareManage>
        )}
      </div>
    );
  }
}
