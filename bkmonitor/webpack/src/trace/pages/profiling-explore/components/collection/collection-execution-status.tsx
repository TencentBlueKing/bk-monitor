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

import { Popover, Tag } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { executionStatusLabels, resultStatusLabels } from '../../utils/collection-history';
import CommonStatus, { type CommonStatusType } from '@/components/common-detail/common-status/common-status';

import './collection-execution-status.scss';

const statusTypes: Record<string, CommonStatusType> = {
  succeed: 'success',
  failed: 'failed',
  timeout: 'failed',
  partial_succeed: 'waiting',
};

export default defineComponent({
  name: 'CollectionExecutionStatus',
  props: {
    status: { type: String, required: true },
    message: { type: String, default: '' },
    tag: { type: Boolean, default: false },
    result: { type: Boolean, default: false },
  },
  setup() {
    return { t: useI18n().t };
  },
  render() {
    const text = this.t((this.result ? resultStatusLabels : executionStatusLabels)[this.status] || '未知');
    if (this.tag) {
      return (
        <Tag
          class={['collection-execution-status-tag', `is-${this.status}`]}
          radius='4px'
          type='filled'
        >
          {text}
        </Tag>
      );
    }
    // 气泡内容需要承载可点击的按钮，改用 Tippy 组件渲染插槽，指令方式会把事件监听丢掉
    return (
      <span class='collection-execution-status'>
        <Popover
          disabled={!this.message}
          placement='top'
          theme='collection-execution-status'
        >
          {{
            default: () =>
              ['running', 'parsing'].includes(this.status) ? (
                <span class='collection-execution-running'>
                  <i aria-hidden='true' />
                  {text}
                </span>
              ) : (
                <CommonStatus
                  text={text}
                  type={statusTypes[this.status] || 'disabled'}
                />
              ),
            content: () => (
              <div class='collection-execution-status-tips'>
                {this.$slots.message?.() || <span>{this.message}</span>}
              </div>
            ),
          }}
        </Popover>
      </span>
    );
  },
});
