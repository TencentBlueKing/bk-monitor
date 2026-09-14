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
import { defineComponent } from 'vue';
import type { PropType } from 'vue';

import type { IRumDetailHeaderVM } from '../../typings';

import './detail-header.scss';

/**
 * Span 详情标题区：类型图标 + 标题 + 关键指标徽标 + 公共信息。
 * 只消费 useDetailOverview 产出的视图模型，不关心 span 类型差异。
 */
export default defineComponent({
  name: 'RumDetailHeader',
  props: {
    data: {
      type: Object as PropType<IRumDetailHeaderVM | null>,
      default: null,
    },
  },
  emits: {
    /** 点击公共信息里的链接项（会话 / 视图 / View 详情） */
    itemClick: (_key: string, _value: string) => true,
  },
  setup(props, { emit }) {
    return () => {
      const { data } = props;
      if (!data) return null;
      return (
        <div class='rum-detail-header'>
          {data.logo ? (
            <div class='header-logo'>
              <img
                alt=''
                src={data.logo}
              />
            </div>
          ) : null}
          <div class='header-main'>
            <div class='header-title-row'>
              <span
                class='header-title'
                title={data.title}
              >
                {data.title}
              </span>
              {data.badges.map(badge => (
                <span
                  key={badge.key}
                  style={{ backgroundColor: badge.bgColor, color: badge.color }}
                  class='header-badge'
                >
                  {badge.icon ? <i class={`header-badge-icon ${badge.icon}`} /> : null}
                  {badge.text}
                </span>
              ))}
            </div>
            {data.itemRows.map(row => (
              <div
                key={row.map(item => item.key).join('|')}
                class='header-item-row'
              >
                {row.map(item => (
                  <div
                    key={item.key}
                    class='header-item'
                  >
                    <span class='item-label'>{item.label}：</span>
                    <span
                      class={{ 'item-value': true, 'is-link': item.isLink && !!item.value }}
                      title={item.value}
                      onClick={() => item.isLink && item.value && emit('itemClick', item.key, item.value)}
                    >
                      {item.value || '--'}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      );
    };
  },
});
