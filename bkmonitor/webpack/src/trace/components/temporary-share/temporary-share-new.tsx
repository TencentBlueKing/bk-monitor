/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { computed, defineComponent, inject, onMounted, reactive, ref, shallowRef } from 'vue';

import { PrimaryTable } from '@blueking/tdesign-ui';
import { bkTooltips, Button, Dialog, Message, Switcher } from 'bkui-vue';
import dayjs from 'dayjs';
import { createShareToken, updateShareToken } from 'monitor-api/modules/share';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import { useAppStore } from '../../store/modules/app';
// import TimeRangeComponent, { type TimeRangeType } from '../time-range/time-range';
import TimeRangeComp from '../time-range/time-range';
import TimeSelect, { type ITimeListItem } from '../time-select/time-select';
import HistoryShareManage from './history-share-manage';

import type { TimeRangeType } from '../time-range/utils';
import type { INavItem, NavBarMode } from './typings';

import './temporary-share-new.scss';

type TableColumn = Record<string, any>;

export default defineComponent({
  name: 'TemporaryShareNew',
  directives: {
    bkTooltips,
  },
  props: {
    navList: {
      type: Array as () => INavItem[],
      default: () => [],
    },
    customData: {
      type: Object,
      default: () => ({}),
    },
    positionText: String,
    icon: String,
    navMode: {
      type: String as () => NavBarMode,
      default: 'copy',
    },
    pageInfo: {
      type: Object,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useI18n();
    const route = useRoute();
    const store = useAppStore();

    const readonly = inject('readonly', ref(false));

    const show = ref(false);
    const timeRange = ref<string[]>([]);
    const timezone = ref(window.timezone);
    const validityPeriod = ref('1w');
    const validityList = ref<ITimeListItem[]>([]);
    const token = ref('');
    const historyData = reactive({ show: false });
    const validityPeriodErr = ref(false);
    const querySettings = ref([
      {
        id: 'time',
        name: t('变量选择'),
        canChange: true,
        timeRange: [],
        timezone: window.timezone,
      },
    ]);
    const typeMap = {
      'event-center': 'event',
      'incident-detail': 'incident',
      'event-center-detail': 'event',
    };

    const shareUrl = computed(() => {
      return `${location.origin}${location.pathname}?bizId=${store.bizId}/#/share/${token.value || ''}`;
    });
    const onlyCopy = computed(() => props.navMode === 'copy');
    const onlyDisplay = computed(() => props.navMode === 'display');

    const dialogStyles = computed(() => {
      return {
        '--maskOpacity': historyData.show ? 0 : 1,
      };
    });

    const columns = shallowRef<TableColumn[]>([
      {
        title: t('变量名称'),
        cell: () => <span>{t('时间选择')}</span>,
      },
      {
        title: t('是否可更改'),
        cell: (_, { row: data }) => (
          <Switcher
            theme='primary'
            value={data.canChange}
            onChange={(v: boolean) => handleCanChange(v, data)}
          />
        ),
      },
      {
        title: t('默认选项'),
        width: 386,
        cell: (_, { row: data }) => (
          <div class='time-warp'>
            <TimeRangeComp
              modelValue={data.timeRange}
              timezone={data.timezone || timezone.value}
              onUpdate:modelValue={(v: TimeRangeType) => handleTableTimeRangeChange(v, data)}
              onUpdate:timezone={(v: string) => handleTableTimezoneChange(v, data)}
            />
          </div>
        ),
      },
    ]);

    onMounted(() => {
      validityList.value = [
        { id: '1d', name: t('1 天') },
        { id: '1w', name: t('1 周') },
        { id: '1M', name: t('1 月') },
      ];
    });

    const setDefaultSettings = () => {
      const { from, to, timezone: routeTimezone } = route.query as Record<string, string>;
      querySettings.value = [
        {
          id: 'time',
          name: t('变量选择'),
          canChange: true,
          timeRange: [from || 'now-7d', to || 'now'],
          timezone: routeTimezone || window.timezone,
        },
      ];
    };

    const getShareTokenParams = () => {
      const period = validityPeriod.value.match(/([0-9]+)/)?.[0] || 1;
      let weWebData = {};
      if (window.__BK_WEWEB_DATA__) {
        const { $baseStore = null, ...data } = { ...window.__BK_WEWEB_DATA__ };
        weWebData = { ...data };
      }
      const { canChange, timeRange: settingsTimeRange, timezone: settingsTimezone } = querySettings.value[0];

      return {
        type: typeMap[route.name as keyof typeof typeMap] ?? route.query.sceneId,
        expire_time: dayjs()
          .add(period, (validityPeriod.value.split(period.toString())?.[1] || 'h') as any)
          .unix(),
        expire_period: validityPeriod.value,
        lock_search: !canChange,
        // start_time: dayjs(timeRange.value[0]).unix(),
        // end_time: dayjs(timeRange.value[1]).unix(),
        timezone: settingsTimezone,
        default_time_range: settingsTimeRange,
        data: {
          query: Object.assign(
            {},
            {
              ...route.query,
              timezone: settingsTimezone,
            },
            !canChange
              ? {
                  from: settingsTimeRange[0],
                  to: settingsTimeRange[1],
                }
              : {}
          ),
          name: route.name,
          params: route.params,
          path: route.path,
          navList: [],
          weWebData,
          ...(props.customData || {}),
        },
      };
    };

    const handleCreateShareToken = async () => {
      const data = await createShareToken(getShareTokenParams()).catch(() => ({ token: '' }));
      token.value = data.token;
    };

    const handleUpdateShareToken = async () => {
      const data = await updateShareToken({
        ...getShareTokenParams(),
        token: token.value,
      }).catch(() => ({ token: token.value }));
      token.value = data.token || token.value;
    };

    const handleShowDialog = async () => {
      if (readonly.value || onlyDisplay.value) return;
      if (onlyCopy.value) {
        handleCopyLink(location.href);
        return;
      }
      setDefaultSettings();
      await handleCreateShareToken();
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
      handleUpdateShareToken();
    };

    const handleCopyLink = (url?: string) => {
      let hasErr = false;
      copyText(typeof url === 'string' ? url : shareUrl.value, (errMsg: string) => {
        Message({ message: errMsg, theme: 'error' });
        hasErr = !!errMsg;
      });
      if (!hasErr) Message({ theme: 'success', message: t('复制成功') });
    };

    const commonItem = (title: string, child: JSX.Element) => (
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
          onClick={handleCopyLink}
        >
          {t('复制链接')}
        </Button>
      </div>
    );

    const shareDeadline = () => (
      <div class='share-deadline'>
        <TimeSelect
          list={validityList.value}
          tip={t('自定义输入格式: 如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年')}
          value={validityPeriod.value}
          onAddItem={handleAddTime}
          onChange={handleValidityChange}
        />
        {validityPeriodErr.value && <div class='validity-period-err'>{t('注意：最大值为90天')}</div>}
      </div>
    );

    const handleShowHistory = (v: boolean) => {
      historyData.show = v;
    };

    const handleTableTimeRangeChange = (val: TimeRangeType, row: any) => {
      row.timeRange = [...val];
      handleUpdateShareToken();
    };

    const handleTableTimezoneChange = (val: string, row: any) => {
      row.timezone = val;
      handleUpdateShareToken();
    };

    const handleCanChange = (v: boolean, row: any) => {
      row.canChange = v;
      handleUpdateShareToken();
    };

    return () => {
      const tipsOpts = {
        content: !onlyCopy.value ? t('临时分享') : t('复制链接'),
        delay: 200,
        boundary: 'window',
        placement: 'right',
        disabled: readonly.value || onlyDisplay.value,
      };

      const icon = props.icon
        ? [props.icon]
        : [onlyCopy.value ? 'icon-mc-target-link' : 'temporary-share-icon', 'icon-mc-share'];

      return (
        <div class='temporary-share-new'>
          {!props.positionText?.length ? (
            <span
              class={['icon-monitor', ...icon]}
              v-bk-tooltips={tipsOpts}
              onClick={handleShowDialog}
            />
          ) : (
            <div
              class={['position-bar', { readonly: readonly.value, display: onlyDisplay.value }]}
              v-bk-tooltips={tipsOpts}
              onClick={handleShowDialog}
            >
              <i
                style='font-size: 14px'
                class='icon-monitor icon-dingwei'
              />
              <span class='position-text'>{props.positionText}</span>
              {!onlyDisplay.value && !readonly.value && (
                <span
                  style='font-size: 12px; margin: 0px; color: #3A84FF'
                  class={[
                    'icon-monitor',
                    'copy-text-button',
                    onlyCopy.value ? 'icon-copy-link' : 'temporary-share-icon',
                    'icon-mc-share',
                  ]}
                />
              )}
            </div>
          )}
          {!onlyCopy.value && (
            <Dialog
              style={dialogStyles.value}
              width={700}
              class='temporary-share-new'
              isShow={show.value}
              title={t('临时分享')}
              transfer={true}
              onClosed={handleHideDialog}
            >
              {{
                header: () => (
                  <span class='header'>
                    <span>{t('临时分享')}</span>
                    <span
                      class='link-wrap'
                      onClick={() => handleShowHistory(true)}
                    >
                      <span class='icon-monitor icon-setting' />
                      <span>{t('管理历史分享')}</span>
                    </span>
                  </span>
                ),
                default: () => (
                  <>
                    <div
                      style='margin-top: 18px'
                      class='share-wrap'
                    >
                      {commonItem(t('分享链接'), shareLink())}
                    </div>
                    <div class='share-wrap'>{commonItem(t('链接有效期'), shareDeadline())}</div>
                    <div class='share-wrap'>
                      {commonItem(
                        t('查询设置'),
                        show.value && (
                          <PrimaryTable
                            class='temporary-share-table'
                            rowAttributes={{
                              height: '43',
                            }}
                            columns={columns.value}
                            data={querySettings.value}
                          />
                        )
                      )}
                    </div>
                  </>
                ),
              }}
            </Dialog>
          )}
          {historyData.show && (
            <HistoryShareManage
              navList={props.navList}
              pageInfo={props.pageInfo}
              positionText={props.positionText}
              shareUrl={shareUrl.value}
              show={historyData.show}
              onShowChange={handleShowHistory}
            />
          )}
        </div>
      );
    };
  },
});
