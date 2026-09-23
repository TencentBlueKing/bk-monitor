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
import { defineComponent, nextTick, shallowRef, watch } from 'vue';

import { useResizeObserver } from '@vueuse/core';
import { Alert } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './error-alert.scss';

/** Span 错误提示：超过一行出现展开 / 收起 */
export default defineComponent({
  name: 'LlmErrorAlert',
  props: {
    message: {
      type: String,
      default: '--',
    },
  },
  setup(props) {
    const { t } = useI18n();
    const expanded = shallowRef(false);
    const textRef = shallowRef<HTMLElement | null>(null);
    /** 折叠态正文是否超出单行，用于展示「展开」 */
    const overflowing = shallowRef(false);

    /** 仅在折叠态测量：展开后文本换行，不能据此关掉展开按钮 */
    const syncOverflow = () => {
      if (expanded.value) return;
      const el = textRef.value;
      overflowing.value = Boolean(el && el.scrollWidth > el.clientWidth + 1);
    };

    useResizeObserver(textRef, syncOverflow);

    watch(
      () => props.message,
      () => {
        expanded.value = false;
        nextTick(syncOverflow);
      }
    );

    const handleToggleExpand = () => {
      if (!overflowing.value && !expanded.value) return;
      expanded.value = !expanded.value;
      if (!expanded.value) {
        nextTick(syncOverflow);
      }
    };

    return () => (
      <Alert
        class={['llm-error-alert', { 'is-expanded': expanded.value }]}
        theme='danger'
      >
        {{
          title: () => (
            <div class='llm-error-alert-body'>
              <p
                ref={textRef}
                class='llm-error-alert-text'
              >
                <span class='llm-error-alert-label'>{t('错误信息')}：</span>
                <span>{props.message}</span>
              </p>
              {overflowing.value || expanded.value ? (
                <div
                  class='llm-error-alert-expand'
                  onClick={handleToggleExpand}
                >
                  <i class={['icon-monitor', expanded.value ? 'icon-double-up' : 'icon-double-down']} />
                  <span>{expanded.value ? t('收起') : t('展开')}</span>
                </div>
              ) : null}
            </div>
          ),
        }}
      </Alert>
    );
  },
});
