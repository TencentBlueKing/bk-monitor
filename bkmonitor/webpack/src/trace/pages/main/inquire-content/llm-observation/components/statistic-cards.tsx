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

import { type PropType, defineComponent } from 'vue';

import type { LlmStatCard } from '../utils/typings';

import './statistic-cards.scss';

/** 顶部概览统计卡（耗时、Token、缓存等，数据来自 buildStatCards） */
export default defineComponent({
  name: 'LlmStatisticCards',
  props: {
    /** buildStatCards 产物；value / unit 已格式化，组件只负责布局 */
    cards: {
      type: Array as PropType<LlmStatCard[]>,
      default: () => [],
    },
  },
  setup(props) {
    return () => (
      <div class='llm-statistic-cards'>
        {props.cards.map(item => (
          <div
            key={item.key}
            class='llm-statistic-card'
          >
            <span class='llm-statistic-card-label'>{item.label}</span>
            <div class='llm-statistic-card-value-wrap'>
              <span class={['llm-statistic-card-value', { 'is-success': item.theme === 'success' }]}>{item.value}</span>
              {item.unit ? <span class='llm-statistic-card-unit'>{item.unit}</span> : null}
            </div>
          </div>
        ))}
      </div>
    );
  },
});
