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

import { type PropType, defineComponent, onMounted, reactive } from 'vue';

import AlertInfoCard from './components/alert-info-card/alert-info-card';
import { fetchMockStrategyInfo } from './mock';

import type { AsyncDialogConfirmEvent, IRumAppConfig, IStrategyData } from '../../../typings';

import './data-state.scss';

export default defineComponent({
  name: 'DataState',
  props: {
    /** 应用基本信息数据 */
    detail: {
      type: Object as PropType<IRumAppConfig>,
      default: () => ({}),
    },
  },
  setup(_props) {
    const { detail } = _props;

    /** 告警策略信息 */
    const strategyInfo = reactive<IStrategyData>({
      id: 0,
      name: '',
      alert_status: 0,
      alert_count: 0,
      alert_graph: null,
      is_enabled: false,
      notice_group: [],
    });

    /**
     * @description 处理无数据告警开关变化，通过 AsyncDialogConfirmEvent 的 resolve/reject 控制 Switcher 状态
     * @param {AsyncDialogConfirmEvent<{ is_enabled: boolean }>} event - 异步确认事件
     * @returns {void}
     */
    const handleEnabledChange = (event: AsyncDialogConfirmEvent<{ is_enabled: boolean }>) => {
      // TODO: 替换为真实接口调用
      // 真实场景示例：
      //   updateStrategyEnabled(strategyInfo.id, event.payload.is_enabled)
      //     .then(() => {
      //       strategyInfo.is_enabled = event.payload.is_enabled;
      //       event.resolve();
      //     })
      //     .catch(() => event.reject());
      strategyInfo.is_enabled = event.payload.is_enabled;
      event.resolve();
    };

    // TODO: 替换为真实接口调用（GetNoDataStrategyInfoResource）
    onMounted(async () => {
      const data = await fetchMockStrategyInfo({ bk_biz_id: detail.bk_biz_id, app_name: detail.app_name });
      Object.assign(strategyInfo, data);
    });

    return () => {
      return (
        <div class='run-config-data-state'>
          <AlertInfoCard
            class='run-config-data-state-card'
            strategyInfo={strategyInfo}
            onEnabledChange={handleEnabledChange}
          />
          <div class='run-config-data-state-chart'>数据量趋势图区域</div>
          <div class='run-config-data-state-table'>数据表区域</div>
        </div>
      );
    };
  },
});
