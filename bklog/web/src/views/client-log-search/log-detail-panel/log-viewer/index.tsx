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

import { computed, defineComponent, ref, watch, nextTick } from 'vue';

import { HighlightItem, renderHighlightHtml } from './highlight-html';

import './index.scss';

/** 高亮颜色项 */
interface ColorHighlightItem {
  heightKey: string;
  colorIndex: number;
  color: {
    dark: string;
    light: string;
  };
}

export default defineComponent({
  name: 'ClientLogViewer',
  props: {
    /** 日志列表，每项为 key-value 对象，如 { content: "行文本" } */
    logList: {
      type: Array as () => Record<string, any>[],
      default: () => [],
    },
    /** 过滤关键字 */
    filterKey: {
      type: Array as () => string[],
      default: () => [],
    },
    /** 过滤类型：include 包含 / uninclude 不包含 */
    filterType: {
      type: String,
      default: 'include',
    },
    /** 是否忽略大小写 */
    ignoreCase: {
      type: Boolean,
      default: false,
    },
    /** 高亮关键词列表（带颜色信息） */
    highlightList: {
      type: Array as () => ColorHighlightItem[],
      default: () => [],
    },
  },
  setup(props) {
    const isFilterEmpty = ref(false);

    /** HTML 实体反转映射 */
    const entityMap: Record<string, string> = {
      '&amp;': '&',
      '&lt;': '<',
      '&gt;': '>',
      '&quot;': '"',
      '&#x27;': "'",
    };
    const entityRegex = new RegExp(`(${Object.keys(entityMap).join('|')})`, 'g');

    /** 转义 HTML 实体（与原 LogView 的 escapeString 逻辑一致） */
    const escapeString = (item: Record<string, any>): Record<string, string> =>
      Object.fromEntries(
        Object.entries(item).map(([key, val]) => [
          key,
          typeof val !== 'string'
            ? String(val ?? ' ')
            : val.replace(entityRegex, match => entityMap[match]),
        ]),
      );

    /** 转义后的日志列表 */
    const escapedLogList = computed(() => props.logList.map(escapeString));

    /** 是否为"包含"过滤模式 */
    const isIncludeFilter = computed(() => props.filterType === 'include');

    /** 组装高亮列表（与原 LogView 的 getViewLightList 逻辑一致） */
    const getViewLightList = computed<HighlightItem[]>(() => {
      const list: HighlightItem[] = [];
      if (props.filterKey.length && isIncludeFilter.value) {
        props.filterKey.forEach((key) => {
          list.push({
            str: key,
            style: 'color: #FF5656; font-size: 12px; font-weight: 700;',
            isUnique: true,
          });
        });
      }
      list.push(
        ...props.highlightList.map(item => ({
          str: item.heightKey,
          style: getLineColor(item),
          isUnique: false,
        })),
      );
      return list;
    });

    /** 获取高亮行颜色样式（代码风格：深色背景+浅色文字） */
    const getLineColor = (item: ColorHighlightItem): string =>
      `background: ${item.color.light}; color: #313238; padding: 0 4px; border-radius: 2px; height: 22px; display: inline-block; line-height: 22px; font-weight: 500;`;

    /** 判断行文本是否匹配过滤关键字（AND 逻辑：所有关键词都必须匹配） */
    const handleMatch = (item: Record<string, any>): boolean => {
      const valStr = Object.values(item).join(' ');
      const keyVal = props.ignoreCase ? valStr : valStr.toLowerCase();
      return props.filterKey.every((key) => {
        const filterKeyVal = props.ignoreCase ? key : key.toLowerCase();
        return keyVal.includes(filterKeyVal);
      });
    };

    /** 判断某行是否应该显示 */
    const checkLineShow = (item: Record<string, any>): boolean => {
      if (isIncludeFilter.value) {
        return props.filterKey.length ? handleMatch(item) : true;
      }
      return props.filterKey.length ? !handleMatch(item) : true;
    };

    /** 监听过滤条件，判断过滤结果是否为空 */
    watch(
      () => [props.filterKey, props.filterType, props.ignoreCase, props.logList],
      () => {
        nextTick(() => {
          if (!props.filterKey.length) {
            isFilterEmpty.value = false;
            return;
          }
          const allHidden = escapedLogList.value.every(item => !checkLineShow(item));
          isFilterEmpty.value = allHidden;
        });
      },
      { immediate: true },
    );

    return () => (
      <div class='client-log-viewer'>
        <pre class='log-content'>
              {escapedLogList.value.map(
                (item, index) => checkLineShow(item) && (
                    <div class='line' key={index}>
                      {renderHighlightHtml(item, getViewLightList.value, props.ignoreCase, false)}
                    </div>
                ),
              )}
            </pre>
      </div>
    );
  },
});
