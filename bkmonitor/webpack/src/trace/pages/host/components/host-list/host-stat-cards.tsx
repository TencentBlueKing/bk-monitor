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

import { type PropType, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import { HOST_QUICK_CARD_LIST } from '../../constants/host-list';

import type { EHostQuickCategory, IHostQuickCardStats } from '../../types/host-list';

import './host-stat-cards.scss';

export default defineComponent({
  name: 'HostStatCards',
  props: {
    /** 各分类命中主机数 */
    stats: {
      type: Object as PropType<IHostQuickCardStats>,
      required: true,
    },
    /** 当前激活的分类（空为未激活） */
    activeKey: {
      type: String as PropType<EHostQuickCategory | ''>,
      default: '',
    },
  },
  emits: {
    /** 点击卡片快速过滤（再次点击取消） */
    cardClick: (_key: EHostQuickCategory) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    return () => (
      <div class='host-stat-cards'>
        {HOST_QUICK_CARD_LIST.map(card => (
          <div
            key={card.key}
            class={['host-stat-cards__item', { 'is-active': props.activeKey === card.key }]}
            onClick={() => emit('cardClick', card.key)}
          >
            <i class={['icon-monitor', card.icon, 'host-stat-cards__icon']} />
            <div class='host-stat-cards__desc'>
              <span class='host-stat-cards__name'>{t(card.name)}</span>
              <span class='host-stat-cards__num'>{props.stats[card.key] ?? 0}</span>
            </div>
          </div>
        ))}
      </div>
    );
  },
});
