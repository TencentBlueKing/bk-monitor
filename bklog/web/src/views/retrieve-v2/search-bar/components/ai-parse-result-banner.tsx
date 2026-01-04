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

import { computed, defineComponent, ref, watch, nextTick, type PropType } from 'vue';
import useLocale from '@/hooks/use-locale';
import { copyMessage } from '@/common/util';
import useElementEvent from '@/hooks/use-element-event';

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

    const isExpanded = ref(false);
    const textRef = ref<HTMLElement | null>(null);
    const hasOverflow = ref(false);

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
        const firstSpan = container.childNodes[0]?.childNodes[1] as HTMLElement;
        const lastSpan = container.childNodes[1]?.childNodes[1] as HTMLElement;

        hasOverflow.value = firstSpan.scrollWidth > firstSpan.clientWidth
          || lastSpan.scrollWidth > lastSpan.clientWidth;
      } else {
        // 非部分成功情况，直接检测容器
        hasOverflow.value = textRef.value.scrollWidth > textRef.value.clientWidth;
      }
    };

    watch(() => [props.aiQueryResult?.explain, props.aiQueryResult?.queryString], () => {
      nextTick(checkOverflow);
    }, {
      immediate: true,
    });

    const { addElementEvent } = useElementEvent();
    addElementEvent(document, 'resize', checkOverflow);

    /**
     * 复制语句到剪贴板
     */
    const handleCopy = () => {
      let content = '';

      if (isPartialSuccess.value) {
        // 部分成功：复制有效语句和无效内容
        const validPart = `${$t('识别出部分语句')}: ${props.aiQueryResult.queryString}`;
        const invalidPart = `${$t('部分无效内容')}: ${props.aiQueryResult?.explain || ''}`;
        content = validPart
          ? `${validPart}\n ${invalidPart}`
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
            <span>{getSementKeywordElements(props.aiQueryResult.queryString)}</span>
          </span>,
          <span>
            <span>{isExpanded.value ? $t('部分无效内容') : $t('和部分无效内容')}</span>
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

      const expandIcon = isExpanded.value ? 'bklog-collapse-small' : 'bklog-expand-small';

      return <div class={['ai-parse-actions', { 'is-expanded': isExpanded.value }]}>
        {hasOverflow.value && (
          <span
            class='ai-parse-action-btn'
            onClick={toggleExpanded}
          >
            <i class={['bklog-icon', expandIcon]}></i>
            {isExpanded.value ? $t('收起') : $t('完整语句')}
          </span>
        )}
        <span
          class='ai-parse-action-btn'
          onClick={handleCopy}
        >
          <i class='bklog-icon bklog-data-copy'></i>
          {$t('复制')}
        </span>
      </div>;
    }

    /**
     * 高亮渲染关键词
     * @param keyword 关键词
     * @returns 高亮渲染后的关键词
     */
    const getSementKeywordElements = (keyword: string) => {
      if (!keyword) return keyword;

      interface Match {
        type: 'keyword' | 'key' | 'value' | 'bracket';
        value: string;
        index: number;
        length: number;
      }

      const text = keyword;
      const matches: Match[] = [];

      // 1. 先匹配关键字（AND NOT 必须在 AND 之前，避免误匹配）
      const keywordPatterns = [
        /\b(AND\s+NOT)\b/gi,  // AND NOT
        /\b(AND|OR)\b/gi,      // AND 或 OR
      ];

      keywordPatterns.forEach((pattern) => {
        let match;
        pattern.lastIndex = 0;
        while ((match = pattern.exec(text)) !== null) {
          matches.push({
            type: 'keyword',
            value: match[0],
            index: match.index,
            length: match[0].length,
          });
        }
      });

      // 2. 匹配括号
      const bracketPattern = /([(){}[\]])/g;
      let match;
      bracketPattern.lastIndex = 0;
      while ((match = bracketPattern.exec(text)) !== null) {
        matches.push({
          type: 'bracket',
          value: match[0],
          index: match.index,
          length: match[0].length,
        });
      }

      // 3. 匹配 key: value 模式
      // 先找到所有 key: 的位置，然后确定对应的 value 范围
      // 匹配非空白字符序列（至少包含一个字母或下划线），后跟冒号
      const keyColonPattern = /([a-zA-Z_][\w.]*):/g;
      const keyColonMatches: Array<{ key: string; colonIndex: number; keyStart: number }> = [];

      keyColonPattern.lastIndex = 0;
      while ((match = keyColonPattern.exec(text)) !== null) {
        const key = match[1];
        const keyStart = match.index;
        const colonIndex = keyStart + key.length;

        // 检查 key 是否与已匹配的关键字重叠（排除括号，因为 key 可以在括号内）
        const isKeyOverlapped = matches.some(
          m => m.type === 'keyword' && m.index < colonIndex && m.index + m.length > keyStart
        );

        if (!isKeyOverlapped) {
          keyColonMatches.push({ key, colonIndex, keyStart });
        }
      }

      // 处理每个 key:value 对
      keyColonMatches.forEach(({ key, colonIndex, keyStart }, idx) => {
        // 添加 key
        matches.push({
          type: 'key',
          value: key,
          index: keyStart,
          length: key.length,
        });

        // 查找 value：从冒号后开始
        let valueStart = colonIndex + 1;
        // 跳过冒号后的空格
        while (valueStart < text.length && /\s/.test(text[valueStart])) {
          valueStart++;
        }

        if (valueStart >= text.length) return;

        // 确定 value 的结束位置
        let valueEnd = valueStart;

        // 检查是否是带引号的值（支持双引号和单引号）
        const quoteChar = text[valueStart];
        if (quoteChar === '"' || quoteChar === "'") {
          const endQuoteIndex = text.indexOf(quoteChar, valueStart + 1);
          if (endQuoteIndex !== -1) {
            // 包含引号在内的完整 value
            valueEnd = endQuoteIndex + 1;
            const value = text.substring(valueStart, valueEnd); // 包含引号
            matches.push({
              type: 'value',
              value: value,
              index: valueStart,
              length: value.length,
            });
          }
        } else {
          // 普通值：找到值的结束位置
          // 结束条件：遇到关键字、括号、或下一个 key:
          const nextKeyColon = idx < keyColonMatches.length - 1
            ? keyColonMatches[idx + 1].keyStart
            : text.length;

          valueEnd = valueStart;
          while (valueEnd < nextKeyColon && valueEnd < text.length) {
            const char = text[valueEnd];

            // 检查是否遇到关键字（前面有空格或开头）
            if (/\s/.test(char)) {
              const remaining = text.substring(valueEnd);
              const keywordMatch = remaining.match(/^\s+\b(AND\s+NOT|AND|OR)\b/i);
              if (keywordMatch) {
                break;
              }
            }

            // 检查是否遇到括号（但不在引号内）
            if (/[(){}[\]]/.test(char)) {
              break;
            }

            valueEnd++;
          }

          // 去除尾部空格
          while (valueEnd > valueStart && /\s/.test(text[valueEnd - 1])) {
            valueEnd--;
          }

          if (valueEnd > valueStart) {
            const value = text.substring(valueStart, valueEnd);
            matches.push({
              type: 'value',
              value: value,
              index: valueStart,
              length: value.length,
            });
          }
        }
      });

      // 4. 处理重叠：优先保留更长的匹配（AND NOT 优先于 AND）
      // key、value、bracket 可以相邻但不重叠，只有真正的字符重叠才需要处理
      const filteredMatches: Match[] = [];
      for (const current of matches) {
        let shouldAdd = true;
        let removeIndices: number[] = [];

        for (let j = 0; j < filteredMatches.length; j++) {
          const existing = filteredMatches[j];

          // 检查是否真正重叠（有字符重叠，不仅仅是相邻）
          const overlaps =
            (current.index < existing.index + existing.length && current.index + current.length > existing.index);

          if (overlaps) {
            // 如果当前是 AND NOT，且已存在的是 AND，则替换
            if (
              current.type === 'keyword' &&
              current.value.toUpperCase().includes('AND NOT') &&
              existing.type === 'keyword' &&
              existing.value.toUpperCase() === 'AND'
            ) {
              removeIndices.push(j);
            }
            // 同类型重叠，保留第一个（不应该有同类型重叠，但以防万一）
            else if (current.type === existing.type) {
              shouldAdd = false;
              break;
            }
            // 不同类型重叠：key/value/bracket 不应该重叠，如果重叠了可能是解析错误，保留第一个
            else {
              shouldAdd = false;
              break;
            }
          }
        }

        // 移除需要替换的项
        removeIndices.sort((a, b) => b - a).forEach(idx => filteredMatches.splice(idx, 1));

        if (shouldAdd) {
          filteredMatches.push(current);
        }
      }

      // 5. 按位置排序
      filteredMatches.sort((a, b) => a.index - b.index);

      // 6. 构建 token 列表并转换为 JSX
      const elements: JSX.Element[] = [];
      let lastIndex = 0;

      filteredMatches.forEach((match, idx) => {
        // 添加匹配前的普通文本
        if (match.index > lastIndex) {
          const textBefore = text.substring(lastIndex, match.index);
          if (textBefore) {
            elements.push(<span key={`text-${idx}`}>{textBefore}</span>);
          }
        }

        // 添加高亮的 token
        let style: { color?: string } = {};
        let className = '';

        switch (match.type) {
          case 'keyword':
            className = 'syntax-keyword';
            style.color = '#7C619E';
            break;
          case 'key':
            className = 'syntax-key';
            style.color = '#BE8125';
            break;
          case 'bracket':
            className = 'syntax-bracket';
            style.color = '#BE8125';
            break;
          case 'value':
            className = 'syntax-value';
            style.color = '#67A48D';
            break;
        }

        elements.push(
          <span key={`${match.type}-${idx}`} class={className} style={style}>
            {match.value}
          </span>
        );

        lastIndex = match.index + match.length;
      });

      // 添加剩余的文本
      if (lastIndex < text.length) {
        elements.push(
          <span key="text-end">{text.substring(lastIndex)}</span>
        );
      }

      return elements.length > 0 ? elements : keyword;
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
                {getSementKeywordElements(props.aiQueryResult.queryString)}
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

