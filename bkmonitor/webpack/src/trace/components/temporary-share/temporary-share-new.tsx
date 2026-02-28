/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type Ref, computed, defineComponent, ref, shallowRef } from 'vue';

import { bkTooltips, Button, Dialog, Message, Switcher } from 'bkui-vue';
import dayjs from 'dayjs';
import { createShareToken, updateShareToken } from 'monitor-api/modules/share';
import { copyText } from 'monitor-common/utils/utils';
import { type TranslateResult, useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import { useAppStore } from '../../store/modules/app';
import TimeRangeComp from '../time-range/time-range';
import { type TimeRangeType, TimeRange } from '../time-range/utils';
import TimeSelect, { type ITimeListItem } from '../time-select/time-select';

import './temporary-share.scss';

const MomentFormater = 'YYYY-MM-DD HH:mm:ss';
export default defineComponent({
  name: 'TemporaryShareNew',
  directives: {
    bkTooltips,
  },
  props: {
    onlyCopy: Boolean,
    type: {
      type: String,
      default: 'trace',
    },
    formatTokenParams: {
      type: Function,
      default: (params: Record<string, any>) => params,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const store = useAppStore();
    const route = useRoute();
    const show = ref(false);
    const token = ref('');
    const isLockSearch = ref(true);
    const validityPeriod = ref('7d');
    // 有效期列表
    const validityList = ref<ITimeListItem[]>([
      {
        id: '1d',
        name: t('1 天'),
      },
      {
        id: '1w',
        name: t('1 周'),
      },
      {
        id: '1M',
        name: t('1 月'),
      },
    ]);
    /* 分享有效期的校验 */
    const validityPeriodErr = shallowRef(false);
    const timeRange: Ref<TimeRangeType> = ref([]);
    // 分享链接
    const shareUrl = computed(
      () => `${location.origin}${location.pathname}?bizId=${store.bizId}/#/share/${token.value || ''}`
    );

    async function handleShowDialog() {
      if (props.onlyCopy) {
        handleCopyLink(location.href);
        return;
      }
      const { from = 'now-1h', to = 'now' } = route.query;
      timeRange.value = new TimeRange([(from as any).toString(), (to as any).toString()]).format();
      // this.oldTimeRange = this.timeRange.slice();
      await createShareTokenfunc();
      show.value = true;
    }
    async function createShareTokenfunc() {
      const data = await createShareToken(getShareTokenParams()).catch(() => ({ token: '' }));
      token.value = data.token;
    }
    function handleCopyLink(url?: string) {
      let hasErr = false;
      copyText(typeof url === 'string' ? url : shareUrl.value, (errMsg: string) => {
        Message({
          message: errMsg,
          theme: 'error',
        });
        hasErr = !!errMsg;
      });
      if (!hasErr) Message({ theme: 'success', message: t('复制成功') });
    }
    // 通用api查询参数
    function getShareTokenParams() {
      const period = validityPeriod.value.match(/([0-9]+)/)?.[0] || 1;
      let weWebData = {};
      if (window.__BK_WEWEB_DATA__) {
        const { $baseStore = null, ...data } = { ...window.__BK_WEWEB_DATA__ };
        weWebData = { ...data };
      }
      return props.formatTokenParams({
        type: props.type,
        expire_time: dayjs
          .tz()
          .add(+period, (validityPeriod.value.split(period.toString())?.[1] || 'h') as any)
          .unix(),
        lock_search: isLockSearch.value,
        expire_period: validityPeriod.value,
        start_time: dayjs.tz(timeRange.value[0]).unix(),
        end_time: dayjs.tz(timeRange.value[1]).unix(),
        data: {
          query: Object.assign(
            {},
            route.query,
            isLockSearch.value
              ? {
                  from: dayjs.tz(timeRange.value[0]).format(MomentFormater),
                  to: dayjs.tz(timeRange.value[1]).format(MomentFormater),
                }
              : {}
          ),
          name: route.name,
          params: route.params,
          path: route.path,
          weWebData,
        },
      });
    }
    // 隐藏弹窗
    function handleHideDialog() {
      show.value = false;
    }
    // 更新token
    async function updateShareTokenFunc() {
      const data = await updateShareToken({
        ...getShareTokenParams(),
        token: token.value,
      }).catch(() => ({ token: token.value }));
      token.value = data.token || token.value;
    }
    function handleTimeRangeChange(v: TimeRangeType) {
      timeRange.value = v;
    }
    function handleLockSearchChange(v: boolean) {
      isLockSearch.value = v;
      updateShareTokenFunc();
    }

    // 自定义有效期时间
    const handleAddTime = (item: ITimeListItem) => {
      validityList.value.push(item);
    };
    /**
     * @description: 有效期变更事件
     * @param {string} v 有效期时间
     * @return {*}
     */
    const handleValidityChange = (v: string) => {
      validityPeriod.value = v;
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
        validityPeriodErr.value = true;
        return;
      }
      validityPeriodErr.value = false;
      updateShareTokenFunc();
    };

    function commonItem(title: TranslateResult, child, style?: Record<string, any>) {
      return (
        <div
          style={style}
          class='share-item'
        >
          <span class='share-item-title'>{title}</span>
          <div class='share-item-content'>{child}</div>
        </div>
      );
    }
    function shareLink() {
      return (
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
    }

    function linkValidityPeriod() {
      return (
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
    }

    function shareTimeRange() {
      return (
        <div class='share-timerange'>
          <TimeRangeComp
            modelValue={timeRange.value as any}
            onUpdate:modelValue={handleTimeRangeChange}
          />
        </div>
      );
    }
    function lockTimeRange() {
      return (
        <div class='lock-timerange'>
          <Switcher
            theme='primary'
            value={isLockSearch.value}
            onChange={handleLockSearchChange}
          />
        </div>
      );
    }
    return {
      show,
      token,
      shareUrl,
      isLockSearch,
      timeRange,
      validityPeriod,
      handleShowDialog,
      handleCopyLink,
      createShareTokenfunc,
      updateShareTokenFunc,
      handleHideDialog,
      commonItem,
      shareLink,
      linkValidityPeriod,
      shareTimeRange,
      lockTimeRange,
      t,
    };
  },
  render() {
    const tipsOpts = {
      content: !this.onlyCopy ? this.t('临时分享') : this.t('复制链接'),
      delay: 200,
      placement: 'right',
    };
    return (
      <div class='temporary-share'>
        <span
          style='font-size: 16px;'
          class={['icon-monitor', this.onlyCopy ? 'icon-mc-target-link' : 'temporary-share-icon', 'icon-mc-share']}
          v-bk-tooltips={tipsOpts}
          onClick={this.handleShowDialog}
        />
        {!this.onlyCopy && (
          <Dialog
            width={700}
            class='temporary-share'
            dialogType='show'
            isShow={this.show}
            title={this.t('临时分享').toString()}
            transfer={true}
            onClosed={this.handleHideDialog}
          >
            <div
              style='margin-top: 18px'
              class='share-wrap'
            >
              {this.commonItem(this.t('分享链接'), this.shareLink())}
            </div>
            <div class='share-wrap'>{this.commonItem(this.t('链接有效期'), this.linkValidityPeriod())}</div>
            <div class='share-wrap'>
              {this.commonItem(this.t('查询时间段'), this.shareTimeRange(), { flex: 1.5, marginRight: '16px' })}
              {this.commonItem(this.t('锁定查询时间'), this.lockTimeRange())}
            </div>
          </Dialog>
        )}
      </div>
    );
  },
});
