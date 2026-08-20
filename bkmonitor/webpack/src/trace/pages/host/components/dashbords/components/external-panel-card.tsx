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

import {
  type MaybeRef,
  type PropType,
  computed,
  defineComponent,
  getCurrentInstance,
  inject,
  onScopeDispose,
  shallowRef,
  toValue,
  watch,
} from 'vue';

import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';
import { useI18n } from 'vue-i18n';

import { resolveVariables } from '../variables/resolve';
import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '@/components/time-range/utils';
import ChartTitle from '@/plugins/components/chart-title';

import type { HostViewsGraphPanel } from '../../../types/panels';
import type { ScopedVarMap } from '../variables/resolve';
import type { TimeRangeType } from '@/components/time-range/time-range';

import './external-panel-card.scss';

type ExternalPanelValue = PortStatusItem[] | TextUnitValue;

interface PortStatusItem {
  name: string;
  statusBgColor?: string;
  statusColor: string;
  value: string;
}

interface TextUnitValue {
  unit: string;
  value: number | string;
}

export default defineComponent({
  name: 'ExternalPanelCard',
  props: {
    panel: {
      type: Object as PropType<HostViewsGraphPanel>,
      required: true,
    },
    scopedVars: {
      type: Object as PropType<ScopedVarMap>,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useI18n();
    const instance = getCurrentInstance();
    const timeRange = inject<MaybeRef<TimeRangeType>>('timeRange', DEFAULT_TIME_RANGE);
    const refreshImmediate = inject<MaybeRef<number | string>>('refreshImmediate', '');
    const loading = shallowRef(false);
    const error = shallowRef(false);
    const value = shallowRef<ExternalPanelValue | null>(null);
    let requestId = 0;

    const requestData = async () => {
      const currentRequestId = ++requestId;
      loading.value = true;
      error.value = false;
      const [startTime, endTime] = handleTransformToTimestamp(toValue(timeRange));
      try {
        const results = await Promise.all(
          props.panel.targets.map(target => {
            const [apiModule, apiFunc] = target.api.split('.');
            const api = instance?.appContext.config.globalProperties.$api?.[apiModule]?.[apiFunc];
            if (typeof api !== 'function') {
              throw new Error(`unknown panel api: ${target.api}`);
            }
            return api(
              {
                ...resolveVariables(target.data, props.scopedVars),
                bk_biz_id: props.scopedVars.bk_biz_id || window.cc_biz_id,
                start_time: startTime,
                end_time: endTime,
              },
              { needMessage: false }
            );
          })
        );
        if (currentRequestId === requestId) {
          value.value = results[0] ?? null;
        }
      } catch {
        if (currentRequestId === requestId) {
          value.value = null;
          error.value = true;
        }
      } finally {
        if (currentRequestId === requestId) {
          loading.value = false;
        }
      }
    };

    watch(
      [() => props.panel, () => props.scopedVars, () => toValue(timeRange), () => toValue(refreshImmediate)],
      requestData,
      { deep: true, immediate: true }
    );
    onScopeDispose(() => {
      requestId += 1;
    });

    const formattedText = computed(() => {
      if (!value.value || Array.isArray(value.value)) return null;
      if (value.value.value === '' || value.value.value === null || value.value.value === undefined) return null;
      const formatted = getValueFormat(value.value.unit || '')(+value.value.value);
      return { text: formatted.text, unit: formatted.suffix };
    });

    const renderContent = () => {
      if (loading.value) return <div class='external-panel-card__empty'>{t('加载中...')}</div>;
      if (error.value) return <div class='external-panel-card__empty'>{t('加载失败')}</div>;
      if (props.panel.type === 'text-unit' && formattedText.value) {
        return (
          <div class='external-panel-card__text-unit'>
            <span class='external-panel-card__value'>{formattedText.value.text}</span>
            <span class='external-panel-card__unit'>{formattedText.value.unit}</span>
          </div>
        );
      }
      if (props.panel.type === 'port-status' && Array.isArray(value.value) && value.value.length) {
        return (
          <ul class='external-panel-card__ports'>
            {value.value.map(item => (
              <li
                key={`${item.value}-${item.name}`}
                class='external-panel-card__port'
              >
                <span class='external-panel-card__port-name'>{item.value}</span>
                <span class='external-panel-card__port-status'>
                  <span
                    style={{ backgroundColor: item.statusColor }}
                    class='external-panel-card__status-dot'
                  />
                  {item.name}
                </span>
              </li>
            ))}
          </ul>
        );
      }
      return <div class='external-panel-card__empty'>{t('暂无数据')}</div>;
    };

    return () => (
      <div class='external-panel-card'>
        <ChartTitle
          menuList={[]}
          metrics={[]}
          showAddMetric={false}
          showMetricAlarm={false}
          showMore={false}
          title={props.panel.title}
        />
        {renderContent()}
      </div>
    );
  },
});
