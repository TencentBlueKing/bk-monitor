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
import { defineComponent, inject, nextTick, shallowRef, watch } from 'vue';

import { useResizeObserver } from '@vueuse/core';
import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import { LLM_OBSERVATION_SEARCH_KEY } from '../utils/search';
import HighlightText from './highlight-text';

import './text-content-item.scss';

/** 折叠态最多展示行数（Figma 160px 卡片内 120px 正文 + 20px 展开） */
const MAX_VISIBLE_LINES = 6;
const LINE_HEIGHT = 20;

/** 文本消息条目：支持复制、溢出折叠、独立查看 */
export default defineComponent({
  name: 'LlmTextContentItem',
  props: {
    /** 展示序号，从 1 开始 */
    index: {
      type: Number,
      required: true,
    },
    content: {
      type: String,
      default: '',
    },
    /** 搜索命中块 id，用于高亮与定位展开 */
    searchBlockId: {
      type: String,
      default: '',
    },
  },
  emits: {
    viewAlone: (_content: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const expanded = shallowRef(false);
    /** 折叠态是否发生溢出 */
    const overflow = shallowRef(false);
    const textRef = shallowRef<HTMLElement>();
    const search = inject(LLM_OBSERVATION_SEARCH_KEY, null);

    // 折叠态 -webkit-line-clamp 会裁掉后面的命中，定位时先展开
    watch(
      () => [search?.activeIndex.value, search?.keyword.value, search?.activeHit.value?.blockId] as const,
      ([, , blockId]) => {
        if (props.searchBlockId && blockId === props.searchBlockId) {
          expanded.value = true;
        }
      },
      { immediate: true }
    );

    /** 按可见行高判断文本是否溢出 */
    const measureOverflow = () => {
      if (expanded.value) return;
      const el = textRef.value;
      if (!el) return;
      overflow.value = el.scrollHeight > MAX_VISIBLE_LINES * LINE_HEIGHT + 2;
    };

    // 详情面板可能在不可见时挂载；显示、缩放或切换宽度后重新判断，不能只在 mounted 时测量。
    useResizeObserver(textRef, measureOverflow);

    watch(
      () => props.content,
      () => {
        expanded.value = false;
        nextTick(measureOverflow);
      }
    );

    const handleCopy = () => {
      copyText(props.content, (msg: string) => {
        Message({ message: msg, theme: 'error' });
      });
      Message({ message: t('复制成功'), theme: 'success' });
    };

    const handleToggleExpand = () => {
      expanded.value = !expanded.value;
      if (!expanded.value) {
        nextTick(measureOverflow);
      }
    };

    return () => (
      <div
        class={[
          'llm-text-content-item',
          {
            'is-expanded': expanded.value,
            'is-overflow': overflow.value && !expanded.value,
          },
        ]}
      >
        <div class='llm-text-content-row'>
          <span class='llm-text-content-index'>[{props.index}]</span>
          <div class='llm-text-content-main'>
            <div class='llm-text-content-actions'>
              <div
                class='llm-text-content-action'
                onClick={handleCopy}
              >
                <i class='icon-monitor icon-mc-copy' />
                <span>{t('复制信息')}</span>
              </div>
              {overflow.value && (
                <div
                  class='llm-text-content-action'
                  onClick={() => emit('viewAlone', props.content)}
                >
                  <i class='icon-monitor icon-sidebar' />
                  <span>{t('独立查看')}</span>
                </div>
              )}
            </div>
            <div class='llm-text-content-clip'>
              <div
                ref={textRef}
                class='llm-text-content-body'
              >
                {props.searchBlockId ? (
                  <HighlightText
                    blockId={props.searchBlockId}
                    text={props.content}
                  />
                ) : (
                  props.content
                )}
              </div>
            </div>
            {overflow.value && (
              <div
                class='llm-text-content-expand'
                onClick={handleToggleExpand}
              >
                <span>{expanded.value ? t('收起') : t('展开')}</span>
                <i
                  style='font-size: 18px;'
                  class={['icon-monitor', 'icon-double-down', { 'is-expanded': expanded.value }]}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    );
  },
});
