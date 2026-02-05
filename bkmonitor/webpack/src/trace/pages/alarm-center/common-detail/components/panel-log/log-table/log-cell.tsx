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

import { defineComponent, nextTick, onMounted, onUnmounted, shallowRef, useTemplateRef } from 'vue';

import { debounce } from 'lodash';
import { useI18n } from 'vue-i18n';

import UseTextSegmentation from './hooks/use-text-segmentation';
import SegmentPop from './segment-pop';
import { formatDate, formatDateNanos, isNestedField, parseTableRowData } from './utils/utils';

import type { EClickMenuType, IFieldInfo } from './typing';

import './log-cell.scss';

export type WordListItem = {
  endIndex?: number;
  isBlobWord?: boolean;
  isCursorText: boolean;
  isMark: boolean;
  left?: number;
  line?: number;
  renderWidth?: number;
  split?: WordListItem[];
  startIndex?: number;
  text: string;
  top?: number;
  width?: number;
};

export default defineComponent({
  name: 'LogCell',
  props: {
    field: {
      type: Object as () => IFieldInfo,
      default: () => ({}),
    },
    row: {
      type: Object as () => Record<string, any>,
      default: () => null,
    },
    options: {
      type: Object as () => Record<string, any>,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useI18n();
    const wrapRef = useTemplateRef<HTMLDivElement>('wrap');
    const wordList = shallowRef<WordListItem[]>([]);
    const hasMore = shallowRef<boolean>(false);
    const isExpand = shallowRef<boolean>(false);
    const intersectionObserver = shallowRef<IntersectionObserver>(null);
    const resizeObserver = shallowRef<ResizeObserver>(null);

    const handleExpand = (e: MouseEvent) => {
      e.stopPropagation();
      isExpand.value = !isExpand.value;
    };

    const handleClickMenu = (opt: { type: EClickMenuType; value: string }) => {
      props.options.onClickMenu?.({
        ...opt,
        ...(props.field.field_type === 'date' && props.row[props.field.field_name]
          ? { value: props.row[props.field.field_name] }
          : {}),
        field: props.field,
      });
    };

    onMounted(() => {
      if (props.row && props.field) {
        let content = props.row[props.field.field_name] ?? parseTableRowData(props.row, props.field.field_name);
        if (props.field.field_type === 'date') {
          const markRegStr = '<mark>(.*?)</mark>';
          const isMark = new RegExp(markRegStr).test(content);
          if (isMark) {
            content = content.replace(/<mark>/g, '').replace(/<\/mark>/g, '');
            content = `<mark>${formatDate(Number(content)) || content || '--'}</mark>`;
          } else {
            content = formatDate(Number(content)) || content || '--';
          }
        }
        // 处理纳秒精度的UTC时间格式
        if (props.field.field_type === 'date_nanos') {
          content = formatDateNanos(content) || '--';
        }
        const textSegmentation = new UseTextSegmentation({
          options: {
            field: props.field,
            content,
            data: props.row || {},
          },
        });
        const fieldKeys = props.field.field_name.split('.');
        const isNestedValue = isNestedField(fieldKeys, props.row);
        wordList.value = textSegmentation.getChildNodes(isNestedValue);
        const checkHeight = () => {
          const segmentContentEl = wrapRef.value?.querySelector('.segment-content');
          hasMore.value = segmentContentEl.getBoundingClientRect().height > 60;
        };
        const debounceCheckHeight = debounce(checkHeight, 200);
        nextTick(() => {
          if (!intersectionObserver.value) {
            intersectionObserver.value = new IntersectionObserver(entries => {
              for (const entry of entries) {
                if (entry.intersectionRatio > 0) {
                  checkHeight();
                  if (!resizeObserver.value) {
                    resizeObserver.value = new ResizeObserver(() => {
                      debounceCheckHeight();
                    });
                    resizeObserver.value.observe(wrapRef.value);
                  }
                }
              }
            });
            intersectionObserver.value.observe(wrapRef.value);
          }
        });
      }
    });

    onUnmounted(() => {
      intersectionObserver.value?.disconnect();
      resizeObserver.value?.disconnect();
    });

    return {
      wordList,
      hasMore,
      isExpand,
      handleExpand,
      t,
      handleClickMenu,
    };
  },
  render() {
    return (
      <div
        ref='wrap'
        style={{
          'max-height': this.isExpand ? 'fit-content' : '60px',
        }}
        class={'log-table-new-log-cell'}
      >
        <div class='segment-content'>
          {this.wordList.map((item, index) => {
            const canClick = item.isCursorText && item.text;
            const isMark = item.isMark;
            return (
              <SegmentPop
                key={index}
                onClickMenu={this.handleClickMenu}
              >
                {{
                  default: ({ onClick: handleClick }) => (
                    <span
                      class={[canClick ? 'valid-text' : 'others-text', isMark ? 'mark-text' : '']}
                      onClick={(e: MouseEvent) => {
                        if (canClick) {
                          handleClick(e, {
                            value: item.text,
                          });
                        }
                      }}
                    >
                      {item.text || '--'}
                    </span>
                  ),
                }}
              </SegmentPop>
            );
          })}
        </div>
        {this.hasMore && (
          <span
            class='more-btn'
            onClick={this.handleExpand}
          >
            {' '}
            ...{this.t(this.isExpand ? '收起' : '更多')}
          </span>
        )}
      </div>
    );
  },
});
