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
import { useI18n } from 'vue-i18n';

import { LLM_OBSERVATION_SEARCH_KEY } from '../utils/search';
import HighlightText from './highlight-text';

import './tool-desc-bar.scss';

/** 工具 / Agent 描述条：超长单行省略，支持原地展开 / 收起 */
export default defineComponent({
  name: 'LlmToolDescBar',
  props: {
    description: {
      type: String,
      default: '',
    },
    name: {
      type: String,
      default: '',
    },
    /** Agent 用蓝色条，工具保持绿色 */
    variant: {
      type: String as PropType<'agent' | 'tool'>,
      default: 'tool',
    },
    /** 工具名高亮锚点；可用工具 tag 已单独高亮时可不传 */
    nameBlockId: {
      type: String,
      default: '',
    },
    /** 描述高亮锚点；命中时把单行省略展开成多行 */
    descBlockId: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    const { t } = useI18n();
    const expanded = shallowRef(false);
    const search = inject(LLM_OBSERVATION_SEARCH_KEY, null);
    const textRef = shallowRef<HTMLElement | null>(null);
    /** 折叠态描述是否超出单行，用于展示「展开」 */
    const overflowing = shallowRef(false);

    const isHitOnBar = () => {
      const blockId = search?.activeHit.value?.blockId;
      return Boolean(
        (props.descBlockId && blockId === props.descBlockId) || (props.nameBlockId && blockId === props.nameBlockId)
      );
    };

    /** 命中被单行省略挡住时才展开，短描述保持折叠且不露出收起 */
    const expandIfHitHidden = () => {
      if (expanded.value || !overflowing.value || !isHitOnBar()) return;
      expanded.value = true;
    };

    /** 仅在折叠态测量：展开后文本换行，不能据此关掉展开按钮 */
    const syncOverflow = () => {
      if (expanded.value) return;
      const el = textRef.value;
      overflowing.value = Boolean(el && el.scrollWidth > el.clientWidth + 1);
      expandIfHitHidden();
    };

    useResizeObserver(textRef, syncOverflow);

    watch(
      () => [search?.activeIndex.value, search?.keyword.value, search?.activeHit.value?.blockId] as const,
      () => {
        expandIfHitHidden();
      },
      { immediate: true }
    );

    watch(
      () => [props.description, props.name],
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

    const displayName = computed(() => props.name.trim() || (props.variant === 'tool' ? t('工具描述') : ''));

    return () => (
      <div class={['llm-tool-desc-bar', { 'is-agent': props.variant === 'agent', 'is-expanded': expanded.value }]}>
        <div class='llm-tool-desc-bar-main'>
          {displayName.value ? (
            <span class='llm-tool-desc-bar-label'>
              {props.nameBlockId ? (
                <HighlightText
                  blockId={props.nameBlockId}
                  text={displayName.value}
                />
              ) : (
                displayName.value
              )}
            </span>
          ) : null}
          <span
            ref={textRef}
            class='llm-tool-desc-bar-text'
          >
            {props.descBlockId ? (
              <HighlightText
                blockId={props.descBlockId}
                text={props.description.trim() || '--'}
              />
            ) : (
              props.description.trim() || '--'
            )}
          </span>
        </div>
        {overflowing.value || expanded.value ? (
          <div
            class='llm-tool-desc-bar-expand'
            onClick={handleToggleExpand}
          >
            <i class={['icon-monitor', expanded.value ? 'icon-double-up' : 'icon-double-down']} />
            <span>{expanded.value ? t('收起') : t('展开')}</span>
          </div>
        ) : null}
      </div>
    );
  },
});
