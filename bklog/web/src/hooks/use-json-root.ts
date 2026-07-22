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
import UseJsonFormatter from '../hooks/use-json-formatter';

import type { Ref } from 'vue';

type RootFieldOperator = {
  isJson: boolean;
  ref: Ref<HTMLElement>;
  value: boolean | number | object | string;
  /** 展示文本（可含时间格式化）；检索回取仍用 value 原始值 */
  stringValue?: string;
  editor?: UseJsonFormatter;
  field: any;
  precomputedSegments?: Record<string, any[]>;
  enableLeafTruncate?: boolean;
  parsedFromJsonString?: boolean;
  resolveFieldDisplayName?: (_fieldName: string) => string;
};

type RootField = {
  name: string;
  formatter: {
    isJson: boolean;
    ref: Ref<HTMLElement>;
    value: boolean | number | object | string;
    stringValue?: string;
    field: any;
    precomputedSegments?: Record<string, any[]>;
    enableLeafTruncate?: boolean;
    parsedFromJsonString?: boolean;
    resolveFieldDisplayName?: (_fieldName: string) => string;
  };
};

export default ({ fields: initialFields, onSegmentClick, onSegmentRenderUpdate }) => {
  const rootFieldOperator = new Map<string, RootFieldOperator>();
  let initEditPromise: Promise<any>;
  // json-formatter 仅在 setup 时传入 fieldList 快照；后续 Visible 增删字段必须随 rootList 同步，
  // 否则新增 Object 字段 getField 失败，分词会退化成整段 JSON。
  let fields = Array.isArray(initialFields) ? initialFields : [];

  const syncFieldsFromRootList = (rootFieldList: RootField[]) => {
    fields = rootFieldList.map(item => item.formatter.field).filter(Boolean);
  };

  const buildFormatterConfig = (value: RootFieldOperator) => ({
    target: value.ref,
    fields,
    jsonValue: value.value,
    onSegmentClick,
    onSegmentRenderUpdate,
    field: value.field,
    precomputedSegments: value.precomputedSegments,
    options: {
      enableLeafTruncate: !!value.enableLeafTruncate,
      parsedFromJsonString: !!value.parsedFromJsonString,
      resolveFieldDisplayName: value.resolveFieldDisplayName,
    },
  });

  const initRootOperator = (depth) => {
    initEditPromise = new Promise((resolve) => {
      for (const value of rootFieldOperator.values()) {
        if (!value.editor) {
          value.editor = new UseJsonFormatter(buildFormatterConfig(value));
        }

        if (value.isJson && value.ref.value) {
          value.editor?.initEditor(depth);
        }

        if (!value.isJson) {
          value.editor?.destroy();
          // value.editor?.initStringAsValue();
        }
      }

      resolve(rootFieldOperator);
    });

    return initEditPromise;
  };

  const setEditor = (depth) => {
    for (const value of rootFieldOperator.values()) {
      if (!value.editor) {
        value.editor = new UseJsonFormatter(buildFormatterConfig(value));
      } else {
        value.editor.update(buildFormatterConfig(value));
      }

      if (value.isJson && value.ref.value) {
        value.editor?.initEditor(depth);
        value.editor?.setValue.call(value.editor, depth);
      }

      if (!value.isJson) {
        // 优先用 stringValue 渲染（时间格式化后的展示串）；jsonValue 仍保留原始 value
        const displayText = value.stringValue !== undefined && value.stringValue !== null
          ? value.stringValue
          : value.value;
        value.editor?.initStringAsValue(displayText as string);
      }
    }
  };

  const destroy = () => {
    for (const value of rootFieldOperator.values()) {
      if (value.isJson && value.ref.value) {
        value.editor?.destroy();
      }

      if (!value.isJson) {
        value.editor?.destroy();
      }
    }
  };

  const updateRootFieldOperator = (rootFieldList: RootField[], depth: number) => {
    syncFieldsFromRootList(rootFieldList);

    for (const fieldItem of rootFieldList) {
      const { name, formatter } = fieldItem;
      if (rootFieldOperator.has(name)) {
        Object.assign(rootFieldOperator.get(name), {
          isJson: formatter.isJson,
          ref: formatter.ref,
          value: formatter.value,
          stringValue: formatter.stringValue,
          field: formatter.field,
          precomputedSegments: formatter.precomputedSegments,
          enableLeafTruncate: formatter.enableLeafTruncate,
          parsedFromJsonString: formatter.parsedFromJsonString,
          resolveFieldDisplayName: formatter.resolveFieldDisplayName,
        });

        rootFieldOperator.get(name).editor?.update(buildFormatterConfig(rootFieldOperator.get(name)));
      } else {
        rootFieldOperator.set(name, {
          isJson: formatter.isJson,
          ref: formatter.ref,
          value: formatter.value,
          stringValue: formatter.stringValue,
          field: formatter.field,
          precomputedSegments: formatter.precomputedSegments,
          enableLeafTruncate: formatter.enableLeafTruncate,
          parsedFromJsonString: formatter.parsedFromJsonString,
          resolveFieldDisplayName: formatter.resolveFieldDisplayName,
        });
      }
    }

    for (const key of rootFieldOperator.keys()) {
      if (!rootFieldList.some(f => f.name === key)) {
        const target = rootFieldOperator.get(key).editor;
        target?.destroy?.();
        rootFieldOperator.delete(key);
      }
    }

    return initRootOperator(depth);
  };

  const setExpand = (depth) => {
    for (const item of rootFieldOperator.values()) {
      if (item.isJson) {
        item.editor?.setExpand(depth);
      }
    }
  };

  return {
    updateRootFieldOperator,
    setExpand,
    setEditor,
    destroy,
  };
};
