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
import { computed, onMounted, Ref } from 'vue';

import JSONEditor from 'jsoneditor';

import segmentPopInstance from '../global/utils/segment-pop-instance';
import useSegmentPop from './use-segment-pop';

import 'jsoneditor/dist/jsoneditor.min.css';

export default ({
  target,
  options,
  fields,
  jsonValue,
  onSegmentClick,
}: {
  target: Ref<HTMLElement | null>;
  fields: any[];
  jsonValue: any;
  onSegmentClick: (args: any) => void;
  options?: Record<string, any>;
}) => {
  let editor = null;

  const getField = (fieldName: string) => {
    return fields.find(item => item.field_name === fieldName);
  };

  const onSegmentEnumClick = (val, isLink) => {
    const tippyInstance = segmentPopInstance.getInstance();
    const currentValue = tippyInstance.reference.innerText;
    const valueElement = tippyInstance.reference.closest('.jsoneditor-value') as HTMLElement;
    const fieldName = valueElement?.getAttribute('data-field-name');
    const activeField = getField(fieldName);
    const target = ['date', 'date_nanos'].includes(activeField?.field_type)
      ? jsonValue?.[activeField?.field_name]
      : currentValue;

    const option = {
      fieldName: activeField?.field_name,
      operation: val === 'not' ? 'is not' : val,
      value: (target ?? currentValue).replace(/<mark>/g, '').replace(/<\/mark>/g, ''),
    };
    onSegmentClick?.({ option, isLink });
    segmentPopInstance.hide();
  };
  const { getSegmentContent } = useSegmentPop({ onSegmentEnumClick });

  const handleSegmentClick = (e, value) => {
    if (!value.toString() || value === '--') return;
    segmentPopInstance.show(e.target, getSegmentContent());
  };

  /** 检索高亮分词字符串 */
  const markRegStr = '<mark>(.*?)</mark>';
  /** 默认分词字符串 */

  const segmentRegStr = ',&*+:;?^=!$<>\'"{}()|[]\\/\\s\\r\\n\\t-';

  const getCurrentFieldRegStr = (field: any) => {
    if (field.tokenize_on_chars) {
      return field.tokenize_on_chars;
    }

    return segmentRegStr;
  };

  const isTextField = (field: any) => {
    return field?.field_type === 'text';
  };

  const isAnalyzed = (field: any) => {
    return field?.is_analyzed ?? false;
  };

  const splitParticipleWithStr = (str: string, delimiterPattern: string) => {
    if (!str) return [];
    // 转义特殊字符，并构建用于分割的正则表达式
    const regexPattern = delimiterPattern
      .split('')
      .map(delimiter => `\\${delimiter}`)
      .join('|');

    // 构建正则表达式以找到分隔符或分隔符周围的文本
    const regex = new RegExp(`(${regexPattern})`);

    // 先根据高亮标签分割
    const markSplitRes = str.match(/(<mark>.*?<\/mark>|.+?(?=<mark|$))/gs);

    // 在高亮分割数组基础上再以分隔符分割数组
    const parts = markSplitRes.reduce((list, item) => {
      if (/^<mark>.*?<\/mark>$/.test(item)) {
        list.push(item);
      } else {
        const arr = item.split(regex);
        arr.forEach(i => i && list.push(i));
      }
      return list;
    }, []);

    // 转换结果为对象数组，包含分隔符标记
    const result = parts
      .filter(part => part?.length)
      .map(part => {
        return {
          text: part,
          isNotParticiple: regex.test(part),
          isMark: /^<mark>.*?<\/mark>$/.test(part),
        };
      });

    return result;
  };

  const getSplitList = (field: any, content: any) => {
    const value = `${content}`;
    if (isAnalyzed(field)) {
      // 这里进来的都是开了分词的情况
      return splitParticipleWithStr(value, getCurrentFieldRegStr(field));
    }

    return [
      {
        text: value.replace(/<mark>/g, '').replace(/<\/mark>/g, ''),
        isNotParticiple: isTextField(field),
        isMark: new RegExp(markRegStr).test(value),
      },
    ];
  };

  const getChildItem = item => {
    if (item.text === '\n') {
      const brNode = document.createElement('br');
      return brNode;
    }

    if (item.isMark) {
      const mrkNode = document.createElement('mark');
      mrkNode.innerText = item.text.replace(/<mark>/g, '').replace(/<\/mark>/g, '');
      return mrkNode;
    }

    if (!item.isNotParticiple) {
      const validTextNode = document.createElement('span');
      validTextNode.classList.add('valid-text');
      validTextNode.innerText = item.text;
      return validTextNode;
    }

    const textNode = document.createElement('span');
    textNode.classList.add('others-text');
    textNode.innerText = item.text;
    return textNode;
  };

  const creatSegmentNodes = (vlaues: any[]) => {
    const segmentNode = document.createElement('span');
    segmentNode.classList.add('segment-content');

    vlaues.forEach(item => {
      segmentNode.append(getChildItem(item));
    });

    return segmentNode;
  };

  const setNodeValueWordSplit = (path = '') => {
    Array.from(target.value?.querySelectorAll('.jsoneditor-value') ?? []).forEach(element => {
      if (!element.getAttribute('data-has-word-split')) {
        const text = (element as HTMLDivElement).innerText;
        let fieldName = element.parentElement.closest('tr').querySelector('.jsoneditor-field')?.innerHTML;

        if (path.length) {
          fieldName = path[0];
        }
        const field = getField(fieldName);
        const vlaues = getSplitList(field, text);
        element?.setAttribute('data-has-word-split', '1');
        element?.setAttribute('data-field-name', fieldName);
        element.innerHTML = '';
        element.append(creatSegmentNodes(vlaues));
        element.addEventListener('click', e => {
          if ((e.target as HTMLElement).classList.contains('valid-text')) {
            handleSegmentClick(e, (e.target as HTMLElement).innerHTML);
          }
        });
      }
    });
  };

  const handleExpandNode = args => {
    if (args.isExpand) {
      setNodeValueWordSplit(args.path);
    }
  };

  const computedOptions = computed(() => {
    return {
      mode: 'view',
      navigationBar: false,
      statusBar: false,
      mainMenuBar: false,
      onExpand: handleExpandNode,
      ...(options ?? {}),
    };
  });

  onMounted(() => {
    if (target) {
      editor = new JSONEditor(target?.value, computedOptions.value);
    }
  });

  const setValue = (val, depth = 3) => {
    console.log(depth);
    setTimeout(() => {
      editor.set(val);
      // editor.expand({
      //   path: Object.keys(val ?? {}),
      //   isExpand: false,
      //   recursive: true,
      // });

      setTimeout(() => {
        setNodeValueWordSplit();
      });
    });
  };
  return {
    setValue,
  };
};
