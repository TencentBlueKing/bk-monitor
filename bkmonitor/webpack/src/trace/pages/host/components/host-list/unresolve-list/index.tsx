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

import type { IHostAlarmCount } from '../../../types/host';

import './index.scss';

export default defineComponent({
  name: 'UnresolveList',
  props: {
    list: {
      type: Array as PropType<IHostAlarmCount[]>,
      default: () => [],
    },
  },
  setup(props) {
    const { t } = useI18n();
    const statusMap: Record<number, string> = {
      1: t('致命') as string,
      2: t('预警') as string,
      3: t('提醒') as string,
    };

    return () => (
      <ul class='unresolve-list'>
        {props.list.map(item => (
          <li
            key={item.level}
            class='unresolve-list__item'
          >
            <span class={['unresolve-list__status', `unresolve-list__status--${item.level}`]} />
            <span class='unresolve-list__name'>{`${statusMap[item.level] || ''}(${item.count || 0})`}</span>
          </li>
        ))}
      </ul>
    );
  },
});
