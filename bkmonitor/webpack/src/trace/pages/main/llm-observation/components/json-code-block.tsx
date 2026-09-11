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
import { type PropType, computed, defineComponent, nextTick, onMounted, ref, shallowRef, watch } from 'vue';

import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';
import VueJsonPretty from 'vue-json-pretty';

import { parseJsonValue, stringifyContent, toJsonPrettyData } from '../utils/helpers';

import 'vue-json-pretty/lib/styles.css';
import './json-code-block.scss';

/** JSON 代码块：复制、独立查看、原地展开/收起 */
export default defineComponent({
  name: 'LlmJsonCodeBlock',
  props: {
    title: {
      type: String,
      default: '',
    },
    data: {
      type: [Object, Array, String, Number, Boolean] as PropType<unknown>,
      default: null,
    },
    /** Tool 页独立卡片使用描边样式 */
    bordered: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    viewAlone: (_data: unknown, _title: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const expanded = shallowRef(false);
    const bodyRef = ref<HTMLElement | null>(null);
    /** 折叠态内容是否超出容器，用于决定是否展示底部渐变 */
    const overflowing = shallowRef(false);

    const prettyText = computed(() => stringifyContent(parseJsonValue(props.data)));
    const jsonData = computed(() => toJsonPrettyData(props.data));

    /** 同步折叠态是否溢出，用于控制底部渐变遮罩 */
    const syncOverflow = async () => {
      await nextTick();
      const el = bodyRef.value;
      overflowing.value = Boolean(el && el.scrollHeight > el.clientHeight + 2);
    };

    watch([() => props.data, expanded], () => {
      syncOverflow();
    });

    onMounted(syncOverflow);

    const handleCopy = () => {
      copyText(prettyText.value, (msg: string) => {
        Message({ message: msg, theme: 'error' });
      });
      Message({ message: t('复制成功'), theme: 'success' });
    };

    return () => (
      <div class={['llm-json-code-block', { 'is-bordered': props.bordered }]}>
        <div class='llm-json-code-block-header'>
          <span class='llm-json-code-block-title'>{props.title}</span>
          <div class='llm-json-code-block-actions'>
            <div
              class='llm-json-code-block-action'
              onClick={handleCopy}
            >
              <i class='icon-monitor icon-mc-copy' />
              <span>{t('复制')}</span>
            </div>
            <div
              class='llm-json-code-block-action'
              onClick={() => emit('viewAlone', props.data, props.title)}
            >
              <i class='icon-monitor icon-chakan1' />
              <span>{t('独立查看')}</span>
            </div>
            <div
              class='llm-json-code-block-action'
              onClick={() => {
                expanded.value = !expanded.value;
              }}
            >
              <i class={['icon-monitor', expanded.value ? 'icon-double-up' : 'icon-double-down']} style='font-size: 18px;'/>
              <span>{expanded.value ? t('收起') : t('原地展开')}</span>
            </div>
          </div>
        </div>
        <div
          ref={bodyRef}
          class={['llm-json-code-block-body', { 'is-expanded': expanded.value, 'is-overflowing': overflowing.value }]}
        >
          <VueJsonPretty
            collapsedOnClickBrackets={false}
            data={jsonData.value}
            deep={20}
            showIcon={false}
            showKeyValueSpace={true}
            showLine={false}
            showLineNumber={false}
          />
        </div>
      </div>
    );
  },
});
