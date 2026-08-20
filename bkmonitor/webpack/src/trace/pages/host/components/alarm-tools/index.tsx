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

import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';

import { getStrategyAndEventCountApi } from '../../services/global-service';
import { useHostStore } from '@/store/modules/host';

import type { IHostTopoTreeNode } from '../../types/topo';

import './index.scss';

type CountStatus = 'error' | 'idle' | 'loading' | 'success';

export default defineComponent({
  name: 'AlarmTools',
  props: {
    /** 当前选中的拓扑节点 / 主机（决定内容区视角与各 Tab 数据） */
    selectedNode: {
      type: Object as PropType<IHostTopoTreeNode | null>,
      default: null,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const { refreshGeneration } = storeToRefs(useHostStore());
    /** 告警数 */
    const alarmNum = shallowRef<null | number>(0);
    /** 策略数 */
    const strategyNum = shallowRef<null | number>(0);
    /** 告警、策略数量请求状态 */
    const countStatus = shallowRef<CountStatus>('idle');
    /** 仅允许最新节点 / 刷新代次对应的请求提交状态 */
    let latestRequestId = 0;

    /** 获取告警、策略数量 */
    const fetchCount = async (node: IHostTopoTreeNode, requestId: number) => {
      countStatus.value = 'loading';
      alarmNum.value = null;
      strategyNum.value = null;
      try {
        const result = await getStrategyAndEventCountApi({
          scene_id: 'host',
          target: { ...node },
        });
        if (requestId !== latestRequestId) return;
        alarmNum.value = result.event_counts ?? 0;
        strategyNum.value = result.strategy_counts ?? 0;
        countStatus.value = 'success';
      } catch {
        if (requestId !== latestRequestId) return;
        countStatus.value = 'error';
      }
    };

    /** 失败后重试当前节点 */
    const handleRetry = () => {
      if (countStatus.value !== 'error' || !props.selectedNode) return;
      fetchCount(props.selectedNode, ++latestRequestId);
    };

    /** 跳转策略列表 */
    const handleToStrategy = () => {
      if (countStatus.value === 'error') {
        handleRetry();
        return;
      }
      if (countStatus.value === 'loading') return;
      const query = `filters=${encodeURIComponent(
        JSON.stringify([
          {
            key: 'scenario',
            value: ['host_process', 'os', 'host_device'],
          },
          {
            key: 'strategy_status',
            value: ['ON'],
          },
        ])
      )}`;
      window.open(location.href.replace(location.hash, `#/strategy-config?${query}`), '_blank');
    };

    /** 跳转告警中心 */
    const handleToAlarmCenter = () => {
      if (countStatus.value === 'error') {
        handleRetry();
        return;
      }
      if (countStatus.value === 'loading') return;
      if (!alarmNum.value) return;
      const query = `quickFilterValue=${encodeURIComponent(
        JSON.stringify([
          {
            key: 'category',
            value: ['hosts', 'host_process', 'os', 'host_device'],
          },
          {
            key: 'STATUS',
            value: ['NOT_SHIELDED_ABNORMAL'],
          },
        ])
      )}`;
      window.open(location.href.replace(location.hash, `#/trace/alarm-center?${query}`), '_blank');
    };

    watch(
      [() => props.selectedNode, refreshGeneration],
      ([node]) => {
        const requestId = ++latestRequestId;
        if (node) {
          fetchCount(node, requestId);
        } else {
          alarmNum.value = 0;
          strategyNum.value = 0;
          countStatus.value = 'idle';
        }
      },
      { immediate: true }
    );

    return () => (
      <div class='alarm-tools'>
        <span
          class='alarm-tools-strategy'
          v-bk-tooltips={{
            content:
              countStatus.value === 'error'
                ? `${t('加载失败')}，${t('点击重试')}`
                : countStatus.value === 'loading'
                  ? t('加载中...')
                  : t('策略'),
            delay: 200,
            boundary: 'window',
            placement: 'bottom',
          }}
          onClick={handleToStrategy}
        >
          <i class='icon-monitor icon-mc-strategy tool-icon' />
          {strategyNum.value ?? '--'}
        </span>
        <span
          class={['alarm-tools-alarm', { 'is-disabled': countStatus.value !== 'error' && !alarmNum.value }]}
          v-bk-tooltips={{
            content:
              countStatus.value === 'error'
                ? `${t('加载失败')}，${t('点击重试')}`
                : countStatus.value === 'loading'
                  ? t('加载中...')
                  : alarmNum.value < 1
                    ? t('无告警事件')
                    : t('当前有{0}个告警事件', [alarmNum.value]),
            delay: 200,
            boundary: 'window',
            placement: 'bottom',
            allowHTML: false,
          }}
          onClick={handleToAlarmCenter}
        >
          <i class='icon-monitor icon-mc-chart-alert tool-icon' />
          {alarmNum.value ?? '--'}
        </span>
      </div>
    );
  },
});
