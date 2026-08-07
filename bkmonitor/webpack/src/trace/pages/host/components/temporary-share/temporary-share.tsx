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

import { type PropType, computed, defineComponent, inject, ref as deepRef, shallowRef } from 'vue';

import { PrimaryTable } from '@blueking/tdesign-ui';
import { bkTooltips, Button, Dialog, Message, Switcher } from 'bkui-vue';
import dayjs from 'dayjs';
import { createShareToken, updateShareToken } from 'monitor-api/modules/share';
import { copyText } from 'monitor-common/utils/utils';
import { type TranslateResult, useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import HistoryShareManage from './history-share-manage';
import TimeRangeComp from '@/components/time-range/time-range';
import { type TimeRangeType, TimeRange } from '@/components/time-range/utils';
import TimeSelect, { type ITimeListItem } from '@/components/time-select/time-select';
import { useAppStore } from '@/store/modules/app';

import type { INavItem, NavBarMode } from '@/components/nav-bar/type';

import './temporary-share.scss';

interface IQuerySettingItem {
  canChange: boolean;
  id: string;
  name: TranslateResult | string;
  timeRange: TimeRangeType;
  timezone: string;
}

const getNextZIndex = () => (window as any).__bk_zIndex_manager?.nextZIndex?.() || 2000;

export default defineComponent({
  name: 'TemporaryShare',
  directives: {
    bkTooltips,
  },
  props: {
    /** 导航列表，用于缓存 dashboard title */
    navList: {
      type: Array as PropType<INavItem[]>,
      default: () => [],
    },
    /** 一些自定义分享数据 */
    customData: {
      type: Object as PropType<Record<string, any>>,
      default: () => ({}),
    },
    /** 定位文本 */
    positionText: {
      type: String,
      default: '',
    },
    /** 自定义触发图标 class */
    icon: {
      type: String,
      default: '',
    },
    /** 导航模式：copy 仅复制 / display 仅展示 / share 临时分享 */
    navMode: {
      type: String as PropType<NavBarMode>,
      default: 'share',
    },
    /** 当前分享页的基本信息（用于页面路径显示） */
    pageInfo: {
      type: Object as PropType<Record<string, any>>,
      default: () => ({}),
    },
    /** 分享类型，优先于路由推导 */
    type: {
      type: String,
      default: '',
    },
    /** 自定义格式化 token 请求参数 */
    formatTokenParams: {
      type: Function as PropType<(params: Record<string, any>) => Record<string, any>>,
      default: (params: Record<string, any>) => params,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const store = useAppStore();
    const route = useRoute();
    const readonly = inject('readonly', false);

    const show = shallowRef(false);
    const token = shallowRef('');
    const timezone = shallowRef(window.timezone);
    const timeRange = deepRef<TimeRangeType>([]);
    const validityPeriod = shallowRef('1w');
    const validityPeriodErr = shallowRef(false);
    const zIndex = shallowRef(getNextZIndex());
    const historyShow = shallowRef(false);

    const validityList = deepRef<ITimeListItem[]>([
      { id: '1d', name: t('1 天') as string },
      { id: '1w', name: t('1 周') as string },
      { id: '1M', name: t('1 月') as string },
    ]);

    const querySettings = deepRef<IQuerySettingItem[]>([
      {
        id: 'time',
        name: t('变量选择'),
        canChange: true,
        timeRange: [],
        timezone: window.timezone,
      },
    ]);

    const typeMap: Record<string, string> = {
      'event-center': 'event',
      'incident-detail': 'incident',
      'event-center-detail': 'event',
      'alarm-center': 'event',
      'alarm-center-detail': 'event',
    };

    const shareUrl = computed(
      () => `${location.origin}${location.pathname}?bizId=${store.bizId}/#/share/${token.value || ''}`
    );
    const onlyCopy = computed(() => props.navMode === 'copy');
    const onlyDisplay = computed(() => props.navMode === 'display');
    const shareType = computed(
      () => props.type || typeMap[String(route.name)] || (route.query.sceneId as string) || 'host'
    );

    const queryColumns = computed(() => [
      {
        colKey: 'name',
        title: t('变量名称'),
        cell: () => <span>{t('时间选择')}</span>,
      },
      {
        colKey: 'canChange',
        title: t('是否可更改'),
        cell: (_: unknown, { row }: { row: IQuerySettingItem }) => (
          <Switcher
            theme='primary'
            value={row.canChange}
            onChange={v => handleCanChange(v, row)}
          />
        ),
      },
      {
        colKey: 'timeRange',
        title: t('默认选项'),
        width: 386,
        cell: (_: unknown, { row }: { row: IQuerySettingItem }) => (
          <div class='time-warp'>
            <TimeRangeComp
              modelValue={row.timeRange as TimeRangeType}
              timezone={row.timezone || timezone.value}
              onUpdate:modelValue={v => handleTableTimeRangeChange(v, row)}
              onUpdate:timezone={v => handleTableTimezoneChange(v, row)}
            />
          </div>
        ),
      },
    ]);

    const setDefaultSettings = () => {
      const { from, to, timeZone: queryTimezone } = route.query as Record<string, string>;
      querySettings.value = [
        {
          id: 'time',
          name: t('变量选择'),
          canChange: true,
          timeRange: [from || 'now-7d', to || 'now'],
          timezone: queryTimezone || window.timezone,
        },
      ];
      timeRange.value = new TimeRange([from || 'now-7d', to || 'now']).format();
      timezone.value = queryTimezone || window.timezone;
    };

    const getShareTokenParams = () => {
      const period = validityPeriod.value.match(/([0-9]+)/)?.[0] || '1';
      let weWebData = {};
      if (window.__BK_WEWEB_DATA__) {
        const { $baseStore = null, ...data } = { ...window.__BK_WEWEB_DATA__ };
        weWebData = { ...data };
      }
      const { canChange, timeRange: settingTimeRange, timezone: settingTimezone } = querySettings.value[0];
      return props.formatTokenParams({
        type: shareType.value,
        expire_time: dayjs
          .tz()
          .add(+period, (validityPeriod.value.split(period.toString())?.[1] || 'h') as dayjs.ManipulateType)
          .unix(),
        expire_period: validityPeriod.value,
        lock_search: !canChange,
        start_time: dayjs.tz(timeRange.value[0]).unix(),
        end_time: dayjs.tz(timeRange.value[1]).unix(),
        timezone: settingTimezone,
        default_time_range: settingTimeRange,
        data: {
          query: Object.assign(
            {},
            {
              ...route.query,
              timezone: settingTimezone,
            },
            !canChange
              ? {
                  from: settingTimeRange[0],
                  to: settingTimeRange[1],
                }
              : {}
          ),
          name: route.name,
          params: route.params,
          path: route.path,
          navList: props.navList,
          weWebData,
          ...(props.customData || {}),
        },
      });
    };

    const createShareTokenFn = async () => {
      const data = await createShareToken(getShareTokenParams()).catch(() => ({ token: '' }));
      token.value = data.token;
    };

    const updateShareTokenFn = async () => {
      const data = await updateShareToken({
        ...getShareTokenParams(),
        token: token.value,
      }).catch(() => ({ token: token.value }));
      token.value = data.token || token.value;
    };

    const handleShowDialog = async () => {
      if (readonly || onlyDisplay.value) {
        return;
      }
      if (onlyCopy.value) {
        handleCopyLink(location.href);
        return;
      }
      zIndex.value = getNextZIndex();
      setDefaultSettings();
      await createShareTokenFn();
      show.value = true;
    };

    const handleHideDialog = () => {
      show.value = false;
    };

    const handleAddTime = (item: ITimeListItem) => {
      validityList.value.push(item);
    };

    const handleValidityChange = (v: string) => {
      validityPeriod.value = v;
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
        validityPeriodErr.value = true;
        return;
      }
      validityPeriodErr.value = false;
      updateShareTokenFn();
    };

    const handleCopyLink = (url?: string) => {
      let hasErr = false;
      copyText(typeof url === 'string' ? url : shareUrl.value, (errMsg: string) => {
        Message({
          message: errMsg,
          theme: 'error',
        });
        hasErr = !!errMsg;
      });
      if (!hasErr) {
        Message({ theme: 'success', message: t('复制成功') });
      }
    };

    const handleShowHistory = (v: boolean) => {
      historyShow.value = v;
    };

    const handleTableTimeRangeChange = (val: TimeRangeType, row: IQuerySettingItem) => {
      row.timeRange = [...val];
      timeRange.value = new TimeRange([...val]).format();
      updateShareTokenFn();
    };

    const handleTableTimezoneChange = (val: string, row: IQuerySettingItem) => {
      row.timezone = val;
      timezone.value = val;
      updateShareTokenFn();
    };

    const handleCanChange = (v: boolean, row: IQuerySettingItem) => {
      row.canChange = v;
      updateShareTokenFn();
    };

    const commonItem = (title: TranslateResult | string, child: any) => (
      <div class='share-item'>
        <span class='share-item-title'>{title}</span>
        <div class='share-item-content'>{child}</div>
      </div>
    );

    const shareLink = () => (
      <div class='share-link'>
        <span class='share-link-input'>{shareUrl.value}</span>
        <Button
          class='share-link-btn'
          theme='primary'
          onClick={() => handleCopyLink()}
        >
          {t('复制链接')}
        </Button>
      </div>
    );

    const shareDeadline = () => (
      <div class='share-deadline'>
        <TimeSelect
          list={validityList.value}
          tip={t('自定义输入格式: 如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年') as string}
          value={validityPeriod.value}
          onAddItem={handleAddTime}
          onChange={handleValidityChange}
        />
        {validityPeriodErr.value && <div class='validity-period-err'>{t('注意：最大值为90天')}</div>}
      </div>
    );

    const querySettingTable = () =>
      show.value ? (
        <PrimaryTable
          columns={queryColumns.value as any}
          data={querySettings.value}
          rowKey='id'
          size='small'
        />
      ) : null;

    return {
      t,
      show,
      token,
      timezone,
      timeRange,
      validityPeriod,
      validityPeriodErr,
      validityList,
      querySettings,
      queryColumns,
      zIndex,
      historyShow,
      shareUrl,
      onlyCopy,
      onlyDisplay,
      shareType,
      readonly,
      handleShowDialog,
      handleHideDialog,
      handleCopyLink,
      handleShowHistory,
      commonItem,
      shareLink,
      shareDeadline,
      querySettingTable,
    };
  },
  render() {
    const tipsOpts = {
      content: !this.onlyCopy ? this.t('临时分享') : this.t('复制链接'),
      delay: 200,
      boundary: 'window',
      placement: 'right',
      disabled: !!this.readonly || this.onlyDisplay,
    };
    const icon = this.icon
      ? [this.icon]
      : [this.onlyCopy ? 'icon-mc-target-link' : 'temporary-share-icon', 'icon-mc-share'];

    return (
      <div class='temporary-share'>
        {!this.positionText?.length ? (
          <span
            class={['icon-monitor', ...icon]}
            v-bk-tooltips={tipsOpts}
            onClick={this.handleShowDialog}
          />
        ) : (
          <div
            class={['position-bar', { readonly: !!this.readonly, display: this.onlyDisplay }]}
            v-bk-tooltips={tipsOpts}
            onClick={this.handleShowDialog}
          >
            <i
              style='font-size: 14px'
              class='icon-monitor icon-dingwei'
            />
            <span class='position-text'>{this.positionText}</span>
            {!this.onlyDisplay && !this.readonly && (
              <span
                style='font-size: 12px; margin: 0px; color: #3A84FF'
                class={[
                  'icon-monitor',
                  'copy-text-button',
                  this.onlyCopy ? 'icon-copy-link' : 'temporary-share-icon',
                  'icon-mc-share',
                ]}
              />
            )}
          </div>
        )}
        {!this.onlyCopy && (
          <Dialog
            width={700}
            class='temporary-share'
            v-slots={{
              header: () => (
                <span class='header'>
                  <span>{this.t('临时分享')}</span>
                  <span
                    class='link-wrap'
                    onClick={e => {
                      e.stopPropagation();
                      this.handleShowHistory(true);
                    }}
                  >
                    <span class='icon-monitor icon-setting' />
                    <span>{this.t('管理历史分享')}</span>
                  </span>
                </span>
              ),
            }}
            dialogType='show'
            isShow={this.show}
            transfer={true}
            zIndex={this.zIndex}
            onClosed={this.handleHideDialog}
          >
            <div
              style='margin-top: 18px'
              class='share-wrap'
            >
              {this.commonItem(this.t('分享链接'), this.shareLink())}
            </div>
            <div class='share-wrap'>{this.commonItem(this.t('链接有效期'), this.shareDeadline())}</div>
            <div class='share-wrap'>{this.commonItem(this.t('查询设置'), this.querySettingTable())}</div>
          </Dialog>
        )}
        {this.historyShow && (
          <HistoryShareManage
            navList={this.navList}
            pageInfo={this.pageInfo}
            positionText={this.positionText}
            shareType={this.shareType}
            shareUrl={this.shareUrl}
            show={this.historyShow}
            onShowChange={v => this.handleShowHistory(v)}
          />
        )}
      </div>
    );
  },
});
