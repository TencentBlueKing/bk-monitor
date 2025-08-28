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

import { defineComponent } from 'vue';
import useLocale from '@/hooks/use-locale';
import './index.scss';

export default defineComponent({
  name: 'RegexPopover',
  props: {
    placement: {
      type: String,
      default: 'bottom',
    },
    trigger: {
      type: String,
      default: 'click',
    },
    isCluster: {
      type: Boolean,
      default: true,
    },
    tippyOptions: {
      type: Object,
      default: () => {},
    },
    context: {
      type: String,
      require: true,
    },
  },
  setup(props, { slots, emit }) {
    const { t } = useLocale();

    const handleClick = (id: string, isLink = false) => {
      emit('event-click', id, isLink);
    };

    return () => (
      <bk-popover
        ext-cls='event-tippy'
        class={['retrieve-event-popover', { 'is-inline': !props.isCluster }]}
        placement={props.placement}
        tippy-options={props.tippyOptions}
        trigger={props.trigger}
        theme='light'
      >
        {slots.default?.()}
        <div
          class='event-icons'
          slot='content'
        >
          {props.isCluster && (
            <div class='event-box'>
              <span
                class='event-btn'
                on-click={() => handleClick('show original')}
              >
                <log-icon
                  common
                  type='eye'
                />
                <span>{t('查询命中pattern的日志')}</span>
              </span>
              <div
                class='new-link'
                v-bk-tooltips={t('新开标签页')}
                on-click={() => handleClick('show original', true)}
              >
                <log-icon type='jump' />
              </div>
            </div>
          )}
          <div class='event-box'>
            <span
              class='event-btn'
              on-click={() => handleClick('copy')}
            >
              <log-icon
                class='icon-copy'
                type='copy'
              />
              <span>{t('复制')}</span>
            </span>
          </div>
        </div>
      </bk-popover>
    );
  },
});
