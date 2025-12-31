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
import { defineComponent, ref, nextTick, PropType, onBeforeUnmount, onMounted } from 'vue';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import aiBluekingSvg from '@/images/ai/ai-bluking-2.svg';
import { AiQueryResult } from '../types';
import BklogPopover from '@/components/bklog-popover';
import EditInput from '@/global/edit-input';
import AiParseResultBanner from '@/views/retrieve-v2/search-bar/components/ai-parse-result-banner';

import './index.scss';

type AiModeStatus = 'default' | 'inputting' | 'searching';

export default defineComponent({
  name: 'V3AiMode',
  emits: ['height-change', 'text-to-query', 'edit-sql', 'filter-change'],
  props: {
    isAiLoading: {
      type: Boolean,
      default: false,
    },
    aiQueryResult: {
      type: Object as PropType<AiQueryResult>,
      default: () => ({ startTime: '', endTime: '', queryString: '' }),
    },
    filterList: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();
    const inputValue = ref('');
    const currentInput = ref(''); // 当前输入的文本
    const status = ref<AiModeStatus>('default');
    const textareaRef = ref<HTMLTextAreaElement | null>(null);
    const containerRef = ref<HTMLDivElement | null>(null);
    const aiModeRootRef = ref<HTMLDivElement | null>(null);
    const containerWidth = ref<number>(600);
    const parsedTextRef = ref<InstanceType<typeof BklogPopover> | null>(null);
    // 标记是否正在输入法组合过程中
    const isComposing = ref(false);

    const handleHeightChange = (height: number) => {
      emit('height-change', height);
    };

    const adjustTextareaHeight = () => {
      nextTick(() => {
        if (textareaRef.value) {
          textareaRef.value.style.height = 'auto';
          textareaRef.value.style.height = `${Math.max(24, textareaRef.value.scrollHeight)}px`;
        }
      });
    };

    const handleInput = (e: Event) => {
      const target = e.target as HTMLTextAreaElement;
      currentInput.value = target.value;

      if (inputValue.value.length > 0) {
        status.value = 'inputting';
      } else {
        status.value = 'default';
      }

      adjustTextareaHeight();
    };

    const handleFocus = () => {
      if (inputValue.value.length > 0) {
        status.value = 'inputting';
      }
    };

    const handleBlur = () => {
      if (inputValue.value.length === 0) {
        status.value = 'default';
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Enter') {
        // 如果正在输入法组合过程中，不处理Enter事件
        if (e.isComposing || isComposing.value) {
          return;
        }
        e.preventDefault();
        handleAiExecute();
      }
    };

    // 输入法组合开始
    const handleCompositionStart = () => {
      isComposing.value = true;
    };

    // 输入法组合结束
    const handleCompositionEnd = () => {
      isComposing.value = false;
    };

    useResizeObserve(aiModeRootRef, () => {
      if (aiModeRootRef.value) {
        handleHeightChange(aiModeRootRef.value.offsetHeight);
        containerWidth.value = aiModeRootRef.value.offsetWidth;
      }
    });

    const shortcutKeyStyle = {
      width: '20px',
      height: '20px',
      background: '#898EFF',
      borderRadius: '10px',
      color: '#ffffff',
      fontSize: '14px',
      textAlign: 'center' as const,
      display: 'inline-flex' as const,
      alignItems: 'center' as const,
      justifyContent: 'center' as const,
    };

    const handleAiExecute = () => {
      emit('text-to-query', currentInput.value);
    };

    // const handleEdit = () => {
    //   (parsedTextRef.value as any)?.hide?.();
    //   emit('edit-sql');
    // };

    const handleRemoveFilter = (item: string) => {
      const newFilterList = [...props.filterList];
      const index = newFilterList.indexOf(item);
      if (index > -1) {
        newFilterList.splice(index, 1);
        emit('filter-change', newFilterList);
      }
    };

    const handleFilterChange = (oldValue: string, newValue: string) => {
      const newFilterList = [...props.filterList];
      const index = newFilterList.indexOf(oldValue);

      if (index > -1) {
        const trimmedValue = newValue.trim();
        if (trimmedValue) {
          // 更新值
          newFilterList[index] = trimmedValue;
        } else {
          // 如果新值为空，删除该项
          newFilterList.splice(index, 1);
        }
        emit('filter-change', newFilterList);
      }
    };

    const handleClearAllFilters = () => {
      emit('filter-change', []);
    };

    const handleClearInputText = () => {
      inputValue.value = '';
      currentInput.value = '';
      status.value = 'default';
      adjustTextareaHeight();
      emit('text-to-query', currentInput.value);
    };

    // 手动设置焦点，避免 autofocus 警告
    onMounted(() => {
      nextTick(() => {
        // 只有在没有其他元素聚焦时才设置焦点
        if (textareaRef.value && document.activeElement !== textareaRef.value) {
          // 检查是否有其他输入元素已经聚焦
          const activeElement = document.activeElement;
          const isInputFocused =
            activeElement &&
            (activeElement.tagName === 'INPUT' ||
              activeElement.tagName === 'TEXTAREA' ||
              (activeElement instanceof HTMLElement && activeElement.isContentEditable));

          // 如果没有其他输入元素聚焦，则聚焦到 textarea
          if (!isInputFocused) {
            textareaRef.value.focus();
          }
        }
      });
    });

    onBeforeUnmount(() => {
      // 在组件卸载时强制关闭 popover
      // 先禁用交互，确保即使鼠标悬停也能关闭
      if (parsedTextRef.value) {
        const popoverRef = parsedTextRef.value as any;
        popoverRef.setProps?.({
          duration: 0,
          animation: 'none',
        });
        // 立即隐藏，不延迟
        popoverRef.hide?.(0);
      }
    });

    return () => (
      <div
        class='v3-ai-mode-root'
        ref={aiModeRootRef}
      >
        <div
          ref={containerRef}
          class='v3-ai-mode-container'
        >
          <div class='ai-mode-inner'>
            <div class='ai-input-wrapper'>
              <div class='ai-input-container'>
                <textarea
                  ref={textareaRef}
                  tabindex={1}
                  class='ai-input'
                  value={currentInput.value}
                  placeholder={t('输入查询内容，"帮我查询近 3 天的错误日志"，Tab 切换为普通模式')}
                  onInput={handleInput}
                  onFocus={handleFocus}
                  onBlur={handleBlur}
                  onKeydown={handleKeyDown}
                  onCompositionstart={handleCompositionStart}
                  onCompositionend={handleCompositionEnd}
                  rows={1}
                  style={{
                    height: '24px',
                  }}
                />
              </div>
              {currentInput.value.length > 0 ? (
                <span
                  class='bklog-icon bklog-qingkong'
                  onClick={handleClearInputText}
                ></span>
              ) : null}
              <div class='ai-mode-toggle-btn'>
                <img
                  src={aiBluekingSvg}
                  alt='AI模式'
                  style={{ width: '18px', height: '18px' }}
                />
                <span class='ai-mode-text'>{t('AI 模式')}</span>
                <span style={shortcutKeyStyle}>
                  <i class='bklog-icon bklog-key-tab'></i>
                </span>
              </div>
            </div>
            {props.isAiLoading && [
              <div
                class='ai-loading-info'
                key='loading-info'
              >
                <span class='ai-loading-text'>{t('AI 解析中...')}</span>
              </div>,
              <div
                class='ai-progress-bar'
                key='progress-bar'
              ></div>,
            ]}
          </div>
          <button
            class='ai-execute-btn'
            onClick={handleAiExecute}
          >
            <i class='bklog-icon bklog-publish-fill'></i>
          </button>
        </div>
        <AiParseResultBanner
          ai-query-result={props.aiQueryResult}
          show-border={true}
          style='border-radius: 4px; margin-top: 4px;'
        />
        {props.filterList.length > 0 && (
          <div class='query-list'>
            {props.filterList.map(item => (
              <EditInput
                key={item}
                value={item}
                showDelete={true}
                maxWidth={320}
                resize='both'
                on-change={(newValue: string) => {
                  handleFilterChange(item, newValue);
                }}
                on-delete={() => {
                  handleRemoveFilter(item);
                }}
              />
            ))}
            {props.filterList.length > 0 && (
              <i
                class='bklog-icon bklog-qingkong query-list-clear-all'
                onClick={handleClearAllFilters}
              ></i>
            )}
          </div>
        )}
      </div>
    );
  },
});
