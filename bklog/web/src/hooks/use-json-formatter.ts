import { computed, onMounted, Ref } from 'vue';
import JSONEditor from 'jsoneditor';
import 'jsoneditor/dist/jsoneditor.min.css';

export default ({
  target,
  options,
  fields,
}: {
  target: Ref<HTMLElement | null>;
  fields: any[];
  options?: Record<string, any>;
}) => {
  let editor = null;

  const computedOptions = computed(() => {
    return {
      mode: 'view',
      navigationBar: false,
      statusBar: false,
      mainMenuBar: false,
      ...(options ?? {}),
    };
  });

  const getField = (fieldName: string) => {
    return fields.find(item => item.field_name === fieldName);
  };

  // Function to format objects to JSON string if depth exceeds maxDepth
  const formatNodes = (obj, currentDepth, maxDepth) => {
    if (currentDepth >= maxDepth && typeof obj === 'object' && obj !== null) {
      return JSON.stringify(obj);
    }

    if (typeof obj === 'object' && obj !== null) {
      for (let key in obj) {
        obj[key] = formatNodes(obj[key], currentDepth + 1, maxDepth);
      }
    }

    return obj;
  };

  onMounted(() => {
    if (target) {
      editor = new JSONEditor(target?.value, computedOptions.value);
    }
  });

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

  const isVirtuaField = (field: any) => {
    return field?.field_type === '__virtual__';
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
      .map((part, index) => {
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

  const setNodeValueWordSplit = () => {
    Array.from(target.value?.querySelectorAll('.jsoneditor-value') ?? []).forEach(element => {
      if (!element.getAttribute('data-has-word-split')) {
        const text = element.innerHTML;
        const fieldName = element.parentElement.closest('tr').querySelector('.jsoneditor-field')?.innerHTML;
        const field = getField(fieldName);
        const vlaues = getSplitList(field, text);
        element?.setAttribute('data-has-word-split', '1');
        element.innerHTML = '';
        element.append(creatSegmentNodes(vlaues));
      }
    });
  };

  const setValue = (val, depth = 1) => {
    setTimeout(() => {
      const targetValue = formatNodes(val, 0, depth);
      editor.set(targetValue);
      editor.expand({
        path: Object.keys(val ?? {}),
        isExpand: false,
        recursive: true,
      });

      setTimeout(() => {
        setNodeValueWordSplit();
      });
    });
  };
  return {
    setValue,
  };
};
