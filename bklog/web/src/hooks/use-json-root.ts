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
import { Ref } from 'vue';

import UseJsonFormatter from '../hooks/use-json-formatter';

type RootFieldOperator = {
  isJson: boolean;
  ref: Ref<HTMLElement>;
  value: boolean | number | object | string;
  editor?: {
    setExpand: (depth: number) => void;
    destroy: () => void;
    initEditor: () => void;
    setValue(depth: any): Promise<any>;
  };
};

type RootField = {
  name: string;
  formatter: {
    isJson: boolean;
    ref: Ref<HTMLElement>;
    value: boolean | number | object | string;
  };
};

export default ({ fields, onSegmentClick }) => {
  const rootFieldOperator = new Map<string, RootFieldOperator>();
  let initEditPromise: Promise<any>;

  const initRootOperator = () => {
    initEditPromise = new Promise(resolve => {
      setTimeout(() => {
        rootFieldOperator.values().forEach(value => {
          if (!value.editor) {
            const instance = new UseJsonFormatter({
              target: value.ref,
              fields,
              jsonValue: value.value,
              onSegmentClick,
            });
            if (value.isJson && value.ref.value) {
              instance.initEditor();
            }

            if (!value.isJson) {
              instance.initStringAsValue();
            }

            value.editor = instance;
          }
        });

        resolve(rootFieldOperator);
      });
    });

    return initEditPromise;
  };

  const updateRootFieldOperator = (rootFieldList: RootField[], depth: number) => {
    rootFieldList.forEach(({ name, formatter }) => {
      rootFieldOperator.set(name, {
        isJson: formatter.isJson,
        ref: formatter.ref,
        value: formatter.value,
      });
    });

    rootFieldOperator.keys().forEach(key => {
      if (!rootFieldList.some(f => f.name === key)) {
        rootFieldOperator.get(key).editor?.destroy?.();
        rootFieldOperator.delete(key);
      }
    });

    initRootOperator().then(() => {
      rootFieldOperator.values().forEach(val => {
        if (val.isJson) {
          val.editor?.setValue(depth);
        }
      });
    });
  };

  const setExpand = depth => {
    rootFieldOperator.values().forEach(item => {
      if (item.isJson) {
        item.editor?.setExpand(depth);
      }
    });
  };

  return {
    updateRootFieldOperator,
    setExpand,
  };
};
