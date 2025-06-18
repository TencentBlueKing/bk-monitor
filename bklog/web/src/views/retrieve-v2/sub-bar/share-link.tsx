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

import BklogPopover from '@/components/bklog-popover';
import { computed, defineComponent, Ref, ref } from 'vue';
import useStore from '@/hooks/use-store';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import dayjs from 'dayjs';
import { useRoute } from 'vue-router/composables';
import useLocale from '@/hooks/use-locale';
import { copyMessage } from '@/common/util';
import { messageError } from '@/common/bkmagic';
import http from '@/api/index';
import { TimeRangeType } from '@/components/time-range/time-range';

export default defineComponent({
  setup() {
    const store = useStore();
    const route = useRoute();
    const { t } = useLocale();

    const timezone = ref(store.state.indexItem.timezone);
    const timeRange = ref(store.state.indexItem.datePickerValue);
    const expireTime = ref('1d');
    const expireTimeList = ref([
      { id: '1d', name: '1天' },
      { id: '1w', name: '1周' },
      { id: '1m', name: '1月' },
    ]);
    const link = ref('');

    const formatTimeRange: Ref<TimeRangeType> = ref([
      store.getters.retrieveParams.start_time,
      store.getters.retrieveParams.end_time,
    ]);
    const format = ref(store.getters.retrieveParams.format);
    const timeValueType = ref('static');
    let isDatePickerChange = false;

    const handleTimeValueTypeChange = (value: string) => {
      timeValueType.value = value;

      if (value === 'static') {
        formatTimeRange.value = [store.getters.retrieveParams.start_time, store.getters.retrieveParams.end_time];
      }

      if (value === 'dynamic') {
        formatTimeRange.value = [timeRange.value[0], timeRange.value[1]];
      }
    };

    handleTimeValueTypeChange(timeValueType.value);

    const placeholder = computed(() => {
      if (timeValueType.value === 'static') {
        return `"?start_time=${dayjs(formatTimeRange.value[0]).format(format.value)}&end_time=${dayjs(formatTimeRange.value[1]).format(format.value)}"`;
      }

      return `"?start_time=${formatTimeRange.value[0]}&end_time=${formatTimeRange.value[1]}"`;
    });

    const getExpireEndTime = (expire: string) => {
      // expire = '1d' | '1w' | '1m' | '\d+(d|w|m)'
      const match = expire.match(/^(\d+)([dw]|m)$/);
      if (!match) return dayjs().add(1, 'day').unix();

      const num = parseInt(match[1], 10);
      const unit = match[2];

      let duration;
      switch (unit) {
        case 'd':
          duration = num * 24 * 60 * 60 * 1000; // days to milliseconds
          break;
        case 'w':
          duration = num * 7 * 24 * 60 * 60 * 1000; // weeks to milliseconds
          break;
        case 'm':
          duration = num * 30 * 24 * 60 * 60 * 1000; // months to milliseconds
          break;
        default:
          return num * 24 * 60 * 60 * 1000;
      }

      return dayjs().add(duration, 'millisecond').unix();
    };

    const handleShareLinkClick = () => {
      const result = handleTransformToTimestamp(formatTimeRange.value, format.value);
      const params = {
        route: {
          name: route.name,
          path: route.path,
          params: { ...route.params },
          query: {
            ...route.query,
            start_time: formatTimeRange.value[0],
            end_time: formatTimeRange.value[1],
            timezone: timezone.value,
            format: format.value,
          },
        },
        store: {
          storage: store.state.storage,
          indexItem: {
            ...store.state.indexItem,
            datePickerValue: formatTimeRange.value,
          },

          catchFieldCustomConfig: store.state.retrieve.catchFieldCustomConfig,
        },
      };

      http
        .request('retrieve/createOrUpdateToken', {
          data: {
            type: 'search',
            expire_time: getExpireEndTime(expireTime.value), // 默认1天
            expire_period: expireTime.value,
            lock_search: false,
            start_time: result[0],
            end_time: result[1],
            timezone: timezone.value,
            default_time_range: timeRange.value,
            space_uid: store.state.spaceUid,
            data: params,
          },
        })
        .then(resp => {
          if (resp.result) {
            link.value = `${window.location.origin}/#/share/${resp.data.token}`;
            copyMessage(link.value, '复制成功！');
            return;
          }

          messageError(resp.message || t('生成链接失败，请稍后重试'));
        })
        .catch(err => {
          messageError(err.message || t('生成链接失败，请稍后重试'));
          console.error(err);
        });
    };

    const beforePopoverHide = (e: MouseEvent) => {
      if (isDatePickerChange) {
        isDatePickerChange = false;
        return false;
      }

      return !(e.target as HTMLElement).closest('.bklog-v3-select-popover');
    };

    /**
     * 处理链接有效期变化
     * @param val 链接有效期
     */
    const handleExpireTimeChange = (val: string) => {
      // val = '1d' | '1w' | '1m' | '\d+(d|w|m)'
      expireTime.value = val;
    };

    const handleCutomExpireTimeChange = (val: string) => {
      // 处理自定义链接有效期变化
      // val = '\d+(d|w|m)'
      if (/^\d+(d|w|m)$/.test(val)) {
        expireTime.value = val;
        const customNum = parseInt(val.slice(0, -1), 10);
        const customUnit = val.slice(-1);
        const validUnits = {
          d: 1,
          w: 7,
          m: 30,
        };
        const count = validUnits[customUnit] * customNum;
        if (count > 90) {
          messageError(t('链接有效期不能超过90天，请重新输入'));
          return;
        }

        expireTime.value = val;
        expireTimeList.value.push({ id: val, name: val });
      } else {
        messageError(t('链接有效期格式错误，请输入数字和单位[{number}d|w|m]'));
      }
    };

    const getContentView = () => {
      return (
        <div style='width: 600px; padding: 20px; display: flex; flex-direction: column; font-size: 12px;'>
          <div style='font-size: 20px; margin-bottom: 30px;'>
            <span class='bklog-icon bklog-share'></span>
            <span style='margin-left: 6px;'>{t('临时分享')}</span>
          </div>
          {/* <div style='display: flex; align-items: center; margin-bottom: 10px;'>
            <span>{t('时间设置')}：</span>
            <TimeRange
              timezone={timezone.value}
              value={timeRange.value}
              on-change={handleTimeRangeChange}
              on-timezone-change={handleTimezoneChange}
              on-format-change={handleFormatChange}
            ></TimeRange>
          </div> */}
          <div style='display: flex; align-items: flex-start; margin-bottom: 10px;'>
            <span style='display: inline-block; min-width: fit-content;'>{t('时间格式')}：</span>
            <div>
              <div style='margin-bottom: 6px;'>
                <bk-radio
                  checked={timeValueType.value === 'static'}
                  on-change={val => val && handleTimeValueTypeChange('static')}
                  style='font-size: 12px;'
                >
                  {t('静态时间')}
                </bk-radio>
                <span style='margin-left: 8px; font-size: 10px; color: #979BA5;'>
                  {t('会将时间转换为时间戳，按照访问人的时间进行载入')}
                </span>
              </div>
              <div>
                <bk-radio
                  checked={timeValueType.value === 'dynamic'}
                  on-change={val => val && handleTimeValueTypeChange('dynamic')}
                  style='font-size: 12px;'
                >
                  {t('动态时间')}
                </bk-radio>
                <span style='margin-left: 8px; font-size: 10px; color: #979BA5;'>
                  {t('会将近 xxx 这种时间保留，按照访问人的近 xxx 时间进行载入')}
                </span>
              </div>
            </div>
          </div>
          <div style='margin-bottom: 20px'>
            <span>{t('时间示例')}：</span>
            <span style='color: #979BA5;'>{placeholder.value}</span>
          </div>

          <div style='display: flex; align-items: center; margin-bottom: 12px;'>
            <span>{t('链接有效期')}:</span>
            <bk-select
              style='width: 200px; margin-left: 10px;'
              ext-popover-cls='bklog-v3-select-popover'
              value={expireTime.value}
              on-change={handleExpireTimeChange}
            >
              {expireTimeList.value.map(item => (
                <bk-option
                  key={item.id}
                  id={item.id}
                  name={item.name}
                >
                  {item.name}
                </bk-option>
              ))}

              <div
                class='bklog-v3-select-popover'
                style='display: flex; align-items: center; padding: 10px;'
              >
                <span style='display: inline-block; min-width: fit-content;'>{t('自定义')}:</span>
                <bk-input
                  style='width: 100%; height: 28px; margin-left: 4px;'
                  placeholder='{number}d|w|m'
                  on-enter={val => handleCutomExpireTimeChange(val)}
                ></bk-input>
              </div>
            </bk-select>
          </div>

          <div style='display: flex; width: 100%; margin-top: 12px;'>
            <bk-input
              readonly={true}
              placeholder={`{SITE_URL}/share/{LINK_ID}`}
              value={link.value}
            ></bk-input>
            <bk-button
              theme='primary'
              style='margin-left: -2px; border-radius: 0 2px 2px 0; min-width: fit-content;'
              on-click={handleShareLinkClick}
            >
              {t('生成并复制链接')}
            </bk-button>
          </div>
        </div>
      );
    };
    return () => {
      return (
        <BklogPopover
          trigger='click'
          beforeHide={beforePopoverHide}
          options={{ hideOnClick: false } as any}
          style='height: 100%;border-right: solid 1px #eaebf0; align-items: center; display: flex; justify-content: center; cursor: pointer; padding: 0 20px;'
          {...{
            scopedSlots: { content: getContentView },
          }}
        >
          <span class='bklog-icon bklog-share'></span>
          <span style='margin-left: 6px;'>{t('分享')}</span>
        </BklogPopover>
      );
    };
  },
});
