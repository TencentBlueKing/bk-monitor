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
import { defineComponent, shallowRef, watch } from 'vue';

import BkCrontab from '@blueking/crontab';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import '@blueking/crontab/vue3/vue3.css';

// bk-weweb 把子应用挂在 Shadow DOM 中。input 派发结束后，event.target 会指向宿主节点，
// 而 @blueking/crontab 在 100ms 防抖回调里才读取 event.target.value。
function pinShadowInputTarget(event: Event) {
  const input = event.composedPath()[0];
  if (!(input instanceof HTMLInputElement)) return;
  Object.defineProperty(event, 'target', {
    configurable: true,
    get: () => input,
  });
}

export default defineComponent({
  name: 'CollectionCrontab',
  props: {
    value: { type: String, default: '' },
    readonly: { type: Boolean, default: false },
    timezone: { type: String, required: true },
  },
  emits: { change: (_value: string) => true },
  setup(props, { emit }) {
    const { t, locale } = useI18n();
    const editor = shallowRef<InstanceType<typeof BkCrontab>>();
    const editorValue = shallowRef(props.value);
    const editorKey = shallowRef(0);
    let currentValue = props.value;
    watch(
      () => props.value,
      value => {
        if (value === currentValue) return;
        currentValue = value;
        editorValue.value = value;
        editorKey.value += 1;
      }
    );
    function handleChange(value: string) {
      // 组件会合并连续空格，避免将自身 change 值回写到输入框，打断正在编辑的文本和光标。
      currentValue = value;
      emit('change', value);
    }
    async function validate() {
      // beta.7 的 validate 返回错误状态；等待组件内部 100ms 输入防抖完成。
      await new Promise(resolve => setTimeout(resolve, 120));
      return !!editor.value && !(await editor.value.validate());
    }
    return { t, locale, editor, editorValue, editorKey, handleChange, validate };
  },
  render() {
    const local = this.locale === 'en' ? 'en' : 'zh-CN';
    if (this.readonly)
      return (
        <Tippy
          placement='top'
          theme='light'
        >
          {{
            default: () => <code class='collection-cron-expression'>{this.value}</code>,
            content: () => (
              <div class='collection-cron-summary'>
                <BkCrontab
                  local={local}
                  modelValue={this.value}
                />
                <div>
                  {this.t('时区')}：{this.timezone}
                </div>
              </div>
            ),
          }}
        </Tippy>
      );
    return (
      <div onInputCapture={pinShadowInputTarget}>
        <BkCrontab
          key={this.editorKey}
          ref='editor'
          class='collection-cron-editor'
          shortcuts={[
            { label: this.t('每分钟'), value: '* * * * *' },
            { label: this.t('每小时'), value: '0 * * * *' },
            { label: this.t('每天'), value: '0 0 * * *' },
            { label: this.t('每周'), value: '0 0 * * 1' },
            { label: this.t('每月'), value: '0 0 1 * *' },
          ]}
          local={local}
          modelValue={this.editorValue}
          onChange={this.handleChange}
        />
      </div>
    );
  },
});
