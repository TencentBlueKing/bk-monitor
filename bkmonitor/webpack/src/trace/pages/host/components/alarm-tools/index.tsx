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

import { defineComponent, onMounted, shallowRef } from 'vue';

import { openAlarmCenter } from 'monitor-common/utils/alarm-center-router';
import { useI18n } from 'vue-i18n';

import { getStrategyAndEventCountApi } from '../../services/global-service';

import './index.scss';

/** 主机场景告警中心跳转参数 */
const HOST_ALARM_CENTER_QUERY = {
  condition: JSON.stringify({
    category: ['hosts', 'host_process', 'os', 'host_device'],
  }),
  activeFilterId: 'NOT_SHIELDED_ABNORMAL',
};

export default defineComponent({
  name: 'AlarmTools',
  setup() {
    const { t } = useI18n();
    /** 告警数 */
    const alarmNum = shallowRef(0);
    /** 策略数 */
    const strategyNum = shallowRef(0);

    /** 获取告警、策略数量 */
    const fetchCount = async () => {
      const result = await getStrategyAndEventCountApi({ scene_id: 'host' });
      alarmNum.value = result.event_counts ?? 0;
      strategyNum.value = result.strategy_counts ?? 0;
    };

    /** 跳转策略列表 */
    const handleToStrategy = () => {
      window.open(location.href.replace(location.hash, '#/strategy-config'), '_blank');
    };

    /** 跳转告警中心 */
    const handleToAlarmCenter = () => {
      if (!alarmNum.value) return;
      openAlarmCenter(HOST_ALARM_CENTER_QUERY);
    };

    onMounted(() => {
      fetchCount();
    });

    return () => (
      <div class='alarm-tools'>
        <span
          class='alarm-tools-strategy'
          v-bk-tooltips={{ content: t('策略'), delay: 200, boundary: 'window', placement: 'bottom' }}
          onClick={handleToStrategy}
        >
          <i class='icon-monitor icon-mc-strategy tool-icon' />
          {strategyNum.value}
        </span>
        <span
          class={['alarm-tools-alarm', { 'is-disabled': !alarmNum.value }]}
          v-bk-tooltips={{
            content: alarmNum.value < 1 ? t('无告警事件') : t('当前有{0}个告警事件', [alarmNum.value]),
            delay: 200,
            boundary: 'window',
            placement: 'bottom',
            allowHTML: false,
          }}
          onClick={handleToAlarmCenter}
        >
          <i class='icon-monitor icon-mc-chart-alert tool-icon' />
          {alarmNum.value}
        </span>
      </div>
    );
  },
});
