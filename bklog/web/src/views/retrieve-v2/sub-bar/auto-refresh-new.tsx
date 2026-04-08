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

import { defineComponent, ref, onUnmounted } from 'vue';

import BklogPopover from '@/components/bklog-popover';
import RetrieveHelper, { RetrieveEvent } from '@/views/retrieve-helper';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import useStore from '@/hooks/use-store';
import useLocale from '@/hooks/use-locale';

import './auto-refresh-new.scss';

interface TimeOption {
  label: string;
  value: string;
}

export default defineComponent({
  name: 'AutoRefreshNew',
  setup() {
    const popoverRef = ref(null);
    const selectedValue = ref<string>('off');
    const store = useStore();
    const { t } = useLocale();

    const datasource = ref<TimeOption[]>([
      { label: '关闭(off)', value: 'off' },
      { label: '10s', value: '10s' },
      { label: '30s', value: '30s' },
      { label: '1m', value: '1m' },
      { label: '5m', value: '5m' },
      { label: '15m', value: '15m' },
      { label: '30m', value: '30m' },
      { label: '1h', value: '1h' },
      { label: '2h', value: '2h' },
      { label: '1d', value: '1d' },
    ]);

    /**
     * 将时间字符串转换为毫秒数
     * @param {string} timeValue
     * @returns {number} 毫秒数
     */
    const getTimeInMs = (timeValue: string): number => {
      if (timeValue === 'off') return 0;

      const unitMap: Record<string, number> = {
        s: 1000, // 秒
        m: 60 * 1000, // 分钟
        h: 60 * 60 * 1000, // 小时
        d: 24 * 60 * 60 * 1000, // 天
      };

      const unit = timeValue.slice(-1);
      const amount = parseInt(timeValue.slice(0, -1), 10);

      // 输入验证
      if (isNaN(amount) || amount <= 0) {
        return 0;
      }

      if (!unitMap[unit]) {
        return 0;
      }

      return amount * unitMap[unit];
    };

    const handleRefresh = () => {
      const formatValue = store.getters.retrieveParams.format;
      const val = store.state.indexItem.datePickerValue;
      const result = handleTransformToTimestamp(val, formatValue.value);

      store.commit('updateIndexItemParams', { start_time: result[0], end_time: result[1] });
      RetrieveHelper.fire(RetrieveEvent.AUTO_REFRESH);
    };

    let timerId = null;
    const createRefreshTimerTask = () => {
      const interval = getTimeInMs(selectedValue.value);
      timerId && clearTimeout(timerId);
      if (interval === 0) {
        return;
      }
      timerId = setTimeout(() => {
        handleRefresh();
        createRefreshTimerTask();
      }, interval);
    };

    onUnmounted(() => {
      timerId && clearTimeout(timerId);
    });

    const triggerHandler = (item: TimeOption) => {
      selectedValue.value = item.value;
      popoverRef.value?.hide();
      createRefreshTimerTask();
    };

    const renderContent = () => (
      <ul class='bk-dropdown-list'>
        {datasource.value.map(item => (
          <li key={item.value}>
            <a
              href='javascript:;'
              onClick={() => triggerHandler(item)}
            >
              {item.label}
            </a>
          </li>
        ))}
      </ul>
    );

    return () => (
      <BklogPopover
        ref={popoverRef}
        trigger='click'
        contentClass='auto-refresh-popover-content'
        options={
          {
            appendTo: document.body,
            arrow: false,
            offset: [0, 0],
          } as any
        }
        content={renderContent}
      >
        <div class='auto-refresh-sub-bar'>
          <div
            class='dropdown-trigger-text'
            v-bk-tooltips={{ content: t('自动刷新设置'), placement: 'bottom' }}
          >
            <i class='bklog-icon bklog-auto-refresh' />
            <span>{datasource.value.find(item => item.value === selectedValue.value)?.value || 'off'}</span>
          </div>
        </div>
      </BklogPopover>
    );
  },
});
