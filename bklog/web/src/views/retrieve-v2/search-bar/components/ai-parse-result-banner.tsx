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

import { computed, defineComponent, onMounted, onUnmounted, ref, watch, nextTick, type PropType } from 'vue';
import { sql } from '@codemirror/lang-sql';
import { EditorState } from '@codemirror/state';
import { EditorView } from '@codemirror/view';

import useLocale from '@/hooks/use-locale';
import { copyMessage } from '@/common/util';

import './ai-parse-result-banner.scss';

interface AiQueryResult {
  parseResult?: 'PARTIAL_SUCCESS' | 'SUCCESS' | 'FAILED';
  explain?: string;
  queryString?: string;
}

export default defineComponent({
  name: 'AiParseResultBanner',
  props: {
    aiQueryResult: {
      type: Object as PropType<AiQueryResult | null>,
      default: () => null,
    },
    showBorder: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const { $t } = useLocale();

    const showFullStatement = ref(false);
    const isExpanded = ref(false);
    const textRef = ref<HTMLElement | null>(null);
    const hasOverflow = ref(false);
    const editorValidRef = ref<HTMLElement | null>(null);
    const editorInvalidRef = ref<HTMLElement | null>(null);
    let validEditorView: EditorView | null = null;
    let invalidEditorView: EditorView | null = null;

    const isSuccess = computed(() => props.aiQueryResult?.parseResult === 'SUCCESS');
    const isPartialSuccess = computed(() => props.aiQueryResult?.parseResult === 'PARTIAL_SUCCESS');
    const isFailed = computed(() => !isSuccess.value);

    // 检查文本是否溢出
    const checkOverflow = () => {
      if (!textRef.value) {
        return;
      }

      if (isPartialSuccess.value && !isExpanded.value) {
        // 部分成功时，需要检测两个子 span 的内容是否溢出
        const container = textRef.value;
        const firstSpan = container.querySelector('span:first-child') as HTMLElement;
        const lastSpan = container.querySelector('span:last-child') as HTMLElement;

        if (firstSpan && lastSpan) {
          // 检测第一个 span 的实际内容宽度（包括所有子元素）
          const firstSpanContent = firstSpan.querySelector('span:last-child') as HTMLElement;
          const lastSpanContent = lastSpan.querySelector('span:last-child') as HTMLElement;

          // 计算第一个 span 的实际内容宽度
          let firstActualWidth = 0;
          if (firstSpanContent) {
            // 临时移除 overflow 限制来测量真实宽度
            const originalOverflow = firstSpanContent.style.overflow;
            const originalWhiteSpace = firstSpanContent.style.whiteSpace;
            firstSpanContent.style.overflow = 'visible';
            firstSpanContent.style.whiteSpace = 'nowrap';
            firstActualWidth = firstSpanContent.scrollWidth;
            firstSpanContent.style.overflow = originalOverflow;
            firstSpanContent.style.whiteSpace = originalWhiteSpace;
          } else {
            firstActualWidth = firstSpan.scrollWidth;
          }

          // 计算第二个 span 的实际内容宽度
          let lastActualWidth = 0;
          if (lastSpanContent) {
            const originalOverflow = lastSpanContent.style.overflow;
            const originalWhiteSpace = lastSpanContent.style.whiteSpace;
            lastSpanContent.style.overflow = 'visible';
            lastSpanContent.style.whiteSpace = 'nowrap';
            lastActualWidth = lastSpanContent.scrollWidth;
            lastSpanContent.style.overflow = originalOverflow;
            lastSpanContent.style.whiteSpace = originalWhiteSpace;
          } else {
            lastActualWidth = lastSpan.scrollWidth;
          }

          // 检测两个 span 的可用宽度
          const firstAvailableWidth = firstSpan.clientWidth;
          const lastAvailableWidth = lastSpan.clientWidth;

          // 检测整个容器的内容是否溢出
          const containerActualWidth = container.scrollWidth;
          const containerAvailableWidth = container.clientWidth;

          // 如果任一 span 的内容溢出，或者整个容器溢出，则认为有溢出
          hasOverflow.value =
            firstActualWidth > firstAvailableWidth ||
            lastActualWidth > lastAvailableWidth ||
            containerActualWidth > containerAvailableWidth;
        } else {
          // 降级方案：检测整个容器
          hasOverflow.value = container.scrollWidth > container.clientWidth;
        }
      } else {
        // 非部分成功情况，直接检测容器
        hasOverflow.value = textRef.value.scrollWidth > textRef.value.clientWidth;
      }
    };

    // 创建只读的 CodeMirror 编辑器
    const createReadOnlyEditor = (container: HTMLElement, content: string) => {
      const state = EditorState.create({
        doc: content,
        extensions: [
          sql(),
          EditorView.editable.of(false), // 设置为只读
          EditorView.lineWrapping, // 自动换行
          EditorView.theme({
            '&': {
              fontSize: '12px',
              backgroundColor: 'transparent',
            },
            '.cm-scroller': {
              overflow: 'auto',
            },
            '.cm-content': {
              padding: '0',
            },
            '.cm-line': {
              padding: '0',
            },
          }),
        ],
      });

      return new EditorView({
        state,
        parent: container,
      });
    };

    // 初始化编辑器
    const initEditors = () => {
      nextTick(() => {
        if (showFullStatement.value && isPartialSuccess.value) {
          if (editorValidRef.value && props.aiQueryResult?.queryString) {
            validEditorView = createReadOnlyEditor(editorValidRef.value, props.aiQueryResult.queryString);
          }
          if (editorInvalidRef.value && props.aiQueryResult?.explain) {
            invalidEditorView = createReadOnlyEditor(editorInvalidRef.value, props.aiQueryResult.explain);
          }
        } else if (showFullStatement.value && editorValidRef.value) {
          const content = props.aiQueryResult?.queryString || props.aiQueryResult?.explain || '';
          validEditorView = createReadOnlyEditor(editorValidRef.value, content);
        }
      });
    };

    // 清理编辑器
    const destroyEditors = () => {
      if (validEditorView) {
        validEditorView.destroy();
        validEditorView = null;
      }
      if (invalidEditorView) {
        invalidEditorView.destroy();
        invalidEditorView = null;
      }
    };

    watch(showFullStatement, (newVal) => {
      if (newVal) {
        destroyEditors();
        initEditors();
      } else {
        destroyEditors();
      }
    });

    watch(() => [props.aiQueryResult?.explain, props.aiQueryResult?.queryString], () => {
      nextTick(checkOverflow);
    }, {
      immediate: true,
    });

    onMounted(() => {
      nextTick(checkOverflow);
      // 监听窗口大小变化
      window.addEventListener('resize', checkOverflow);
    });

    onUnmounted(() => {
      window.removeEventListener('resize', checkOverflow);
      destroyEditors();
    });

    /**
     * 关闭解析结果提示
     */
    const handleClose = () => {
      if (props.aiQueryResult) {
        (props.aiQueryResult as AiQueryResult).parseResult = undefined;
        (props.aiQueryResult as AiQueryResult).explain = undefined;
      }
    };

    /**
     * 复制语句到剪贴板
     */
    const handleCopy = () => {
      let content = '';

      if (isPartialSuccess.value) {
        // 部分成功：复制有效语句和无效内容
        const validPart = props.aiQueryResult?.queryString || '';
        const invalidPart = props.aiQueryResult?.explain || '';
        content = validPart
          ? `${validPart}\n\n${$t('无效内容')}:\n${invalidPart}`
          : invalidPart;
      } else if (isSuccess.value) {
        // 成功：复制查询语句
        content = props.aiQueryResult?.queryString || '';
      } else {
        // 失败：复制失败原因
        content = props.aiQueryResult?.explain || '';
      }

      if (!content) {
        window.mainComponent?.$bkMessage?.({
          theme: 'warning',
          message: $t('没有可复制的内容'),
        });
        return;
      }

      // 使用工具函数 copyMessage 进行复制
      copyMessage(content);
    };

    /**
     * 切换完整语句显示（内联展开）
     */
    const toggleExpanded = () => {
      isExpanded.value = !isExpanded.value;
    };


    /**
     * 渲染解析失败原因
     * @returns {JSX.Element | Array<JSX.Element>}
     */
    const renderFailedReason = () => {
      if (isPartialSuccess.value) {
        return [
          <span>
            <span>{$t('识别出部分语句')}</span>
            <span>{props.aiQueryResult.queryString}</span>
          </span>,
          <span>
            <span>{$t('和部分无效内容')}</span>
            <span>{props.aiQueryResult.explain}</span>
          </span>,
        ];
      }

      return props.aiQueryResult.explain;
    };

    /**
     * 获取操作按钮
     * @param isEmpty 是否为空
     * @returns {JSX.Element}
     */
    const getActions = (isEmpty: boolean = false) => {
      if (isEmpty) {
        return null;
      }

      return <div class={['ai-parse-actions', { 'is-expanded': isExpanded.value }]}>
        {hasOverflow.value && (
          <span
            class='ai-parse-action-btn'
            onClick={toggleExpanded}
          >
            {isExpanded.value ? $t('收起') : $t('完整语句')}
          </span>
        )}
        <span
          class='ai-parse-action-btn'
          onClick={handleCopy}
        >
          {$t('复制语句')}
        </span>
      </div>;
    }

    return () => {
      if (!props.aiQueryResult?.parseResult) {
        return null;
      }

      return (
        <div
          class={[
            'ai-parse-result-banner',
            {
              'is-success': isSuccess.value,
              'is-failed': isFailed.value,
              'show-border': props.showBorder,
              'is-expanded': isExpanded.value,
            },
          ]}
        >
          <div class={['ai-parse-result-left', { 'is-expanded': isExpanded.value }]}>
            {isSuccess.value && (
              [<span class='ai-parse-label'>
                <span class="ai-parse-label-left">
                  <i class='bklog-icon bklog-circle-correct-filled ai-parse-icon' />
                  <span class='ai-parse-success-label'>{$t('解析成功')}:</span>
                </span>
                {getActions(!isExpanded.value)}
              </span>,
              <span
                ref={textRef}
                class={['ai-parse-success-text', { 'is-expanded': isExpanded.value }]}
              >
                {props.aiQueryResult.queryString}
              </span>]
            )}
            {(isFailed.value || isPartialSuccess.value) && (
              [
                <span class='ai-parse-label'>
                  <span class="ai-parse-label-left">
                    <i class='bklog-icon bklog-circle-alert-filled ai-parse-icon' />
                    <span class='ai-parse-failed-label'>{$t('解析失败')}:</span>
                  </span>
                  {getActions(!isExpanded.value)}
                </span>,
                isPartialSuccess.value ? (
                  <span
                    ref={textRef}
                    class={['ai-parse-failed-reason', 'partial-success', { 'is-ellipsis': !isExpanded.value, 'is-expanded': isExpanded.value }]}
                  >
                    {renderFailedReason()}
                  </span>
                ) : (
                  <span
                    ref={textRef}
                    class={['ai-parse-failed-reason', { 'is-expanded': isExpanded.value }]}
                  >
                    {renderFailedReason()}
                  </span>
                ),
              ]
            )}
          </div>
          {
            getActions(isExpanded.value)
          }
        </div>
      );
    };
  },
});

