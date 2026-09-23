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
import { type PropType, computed, defineComponent, inject, nextTick, shallowRef, watch } from 'vue';

import { useResizeObserver } from '@vueuse/core';
import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import { beautifyJsonValue, stringifyContent } from '../utils/helpers';
import { isActiveHitOnBlock, LLM_OBSERVATION_SEARCH_KEY } from '../utils/search';
import HighlightText from './highlight-text';
import JsonView from './json-view';

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
    /** JSON 搜索 path 前缀，叶子 path 可能是 prefix.key 或 prefix[0] */
    searchBlockId: {
      type: String,
      default: '',
    },
    /** 标题单独计数时的 blockId，例如输出侧工具结果名 */
    titleBlockId: {
      type: String,
      default: '',
    },
    /** 传入后为受控展开，供左右代码块联动 */
    expanded: {
      type: Boolean as PropType<boolean | undefined>,
      default: undefined,
    },
  },
  emits: {
    viewAlone: (_data: unknown, _title: string) => true,
    'update:expanded': (_value: boolean) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const innerExpanded = shallowRef(false);
    const bodyRef = shallowRef<HTMLElement | null>(null);
    /** 折叠态内容是否超出 max-height，用于渐变遮罩与展开按钮可用性 */
    const overflowing = shallowRef(false);
    const search = inject(LLM_OBSERVATION_SEARCH_KEY, null);
    const isExpanded = computed(() => (props.expanded === undefined ? innerExpanded.value : props.expanded));

    const setExpanded = (value: boolean) => {
      if (props.expanded === undefined) {
        innerExpanded.value = value;
      }
      emit('update:expanded', value);
    };

    // 命中折叠区后面的叶子时，先去掉 max-height 再滚到当前高亮，否则 scrollIntoView 看不见
    watch(
      () => [search?.activeIndex.value, search?.keyword.value, search?.activeHit.value] as const,
      async ([, , hit]) => {
        const inJson = isActiveHitOnBlock(hit, props.searchBlockId);
        const inTitle = Boolean(props.titleBlockId && hit?.blockId === props.titleBlockId);
        if (!inJson && !inTitle) return;
        if (!isExpanded.value) {
          setExpanded(true);
        }
        if (inJson) {
          await nextTick();
          bodyRef.value
            ?.querySelector('[data-llm-search-hit="current"]')
            ?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        }
      },
      { immediate: true }
    );

    // 复制仍输出合法 JSON（文本则保留原文），不使用含多行叶子的可读展示文本。
    const prettyText = computed(() => stringifyContent(beautifyJsonValue(props.data)));

    /** 仅在折叠态测量：展开后容器会撑开，不能据此关掉展开按钮 */
    const syncOverflow = () => {
      if (isExpanded.value) return;
      const el = bodyRef.value;
      overflowing.value = Boolean(el && el.scrollHeight > el.clientHeight + 2);
    };

    // JsonView / vue-json-pretty 渲染、宽度变化后都要重新判断。
    useResizeObserver(bodyRef, syncOverflow);

    watch(
      () => props.data,
      () => {
        setExpanded(false);
        nextTick(syncOverflow);
      }
    );

    watch(isExpanded, expanded => {
      if (!expanded) nextTick(syncOverflow);
    });

    const handleToggleExpand = () => {
      setExpanded(!isExpanded.value);
    };

    const handleCopy = () => {
      copyText(prettyText.value, (msg: string) => {
        Message({ message: msg, theme: 'error' });
      });
      Message({ message: t('复制成功'), theme: 'success' });
    };

    return () => (
      <div class={['llm-json-code-block', { 'is-bordered': props.bordered, 'is-expanded': isExpanded.value }]}>
        {props.title ? (
          <div class='llm-json-code-block-header'>
            <span class='llm-json-code-block-title'>
              {props.titleBlockId ? (
                <HighlightText
                  blockId={props.titleBlockId}
                  text={props.title}
                />
              ) : (
                props.title
              )}
            </span>
          </div>
        ) : null}
        <div class='llm-json-code-block-main'>
          <div class='llm-json-code-block-actions'>
            <div
              class='llm-json-code-block-action'
              onClick={handleCopy}
            >
              <i class='icon-monitor icon-mc-copy' />
              <span>{t('复制信息')}</span>
            </div>
            {overflowing.value && (
              <div
                class='llm-json-code-block-action'
                onClick={() => emit('viewAlone', props.data, props.title)}
              >
                <i class='icon-monitor icon-sidebar' />
                <span>{t('独立查看')}</span>
              </div>
            )}
          </div>
          <div
            ref={bodyRef}
            class={[
              'llm-json-code-block-body',
              { 'is-expanded': isExpanded.value, 'is-overflowing': overflowing.value },
            ]}
          >
            <JsonView
              data={props.data}
              searchBlockId={props.searchBlockId}
            />
          </div>
          {(overflowing.value || isExpanded.value) && (
            <div
              class='llm-json-code-block-expand'
              onClick={handleToggleExpand}
            >
              <span>{isExpanded.value ? t('收起') : t('展开')}</span>
              <i
                style='font-size: 18px;'
                class={['icon-monitor', 'icon-double-down', { 'is-expanded': isExpanded.value }]}
              />
            </div>
          )}
        </div>
      </div>
    );
  },
});
