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

import { shallowRef } from 'vue';

import { createGlobalState } from '@vueuse/core';
import { Debounce } from 'monitor-common/utils';

import { EFieldType, EQueryStringTokenType } from './typing';

export const QUERY_STRING_METHODS = [
  {
    id: ':',
    name: window.i18n.t('等于'),
  },
  {
    id: ':*',
    name: window.i18n.t('存在'),
  },
  {
    id: '>',
    name: window.i18n.t('大于'),
  },
  {
    id: '<',
    name: window.i18n.t('小于'),
  },
  {
    id: '>=',
    name: window.i18n.t('大于或等于'),
  },
  {
    id: '<=',
    name: window.i18n.t('小于或等于'),
  },
];

export const QUERY_STRING_CONDITIONS = [
  {
    id: 'AND',
    name: window.i18n.t('两个参数都'),
  },
  {
    id: 'OR',
    name: window.i18n.t('一个或多个参数'),
  },
  {
    id: 'AND NOT',
    name: window.i18n.t('一个或多个参数'),
  },
];

/* 语句模式下字体颜色 */
export const queryStringColorMap = {
  [EQueryStringTokenType.key]: {
    color: '#B17313',
    background: '#FCE5C0',
    icon: 'icon-Key',
  },
  [EQueryStringTokenType.method]: {
    color: '#016BB4',
    background: '#E6F0F8',
    icon: 'icon-yunsuanfu',
  },
  [EQueryStringTokenType.value]: {
    color: '#02776E',
    background: '#E6F2F1',
    icon: 'icon-Value',
  },
  [EQueryStringTokenType.condition]: {
    color: '#7C609E',
    background: '#F3F1F8',
    icon: 'icon-Value',
  },
  [EQueryStringTokenType.valueCondition]: {
    color: '#7C609E',
    background: '#F3F1F8',
    icon: 'icon-Value',
  },
};
export const QUERY_STRING_DATA_TYPES = Object.keys(queryStringColorMap);

const defaultColor = '#313238';

export interface IStrItem {
  key?: string;
  type: EQueryStringTokenType;
  value: string;
}

interface IOptions {
  target: Element;
  value: string;
  keyFormatter?: (field: string) => string;
  onBlur?: () => void;
  onChange?: (value: string) => void;
  onInput?: (v: string) => void;
  onQuery?: (v?: string) => void;
  onSearch?: (value: string) => void;
  popDownFn?: () => void;
  popUpFn?: (type: EQueryStringTokenType, field: string) => void;
  valueFormatter?: (field: string, method: string, value: string) => string;
}

export class QueryStringEditor {
  /* 当前token类型 */
  curTokenType = EQueryStringTokenType.key;
  /* 容器 */
  editorEl: Element = null;
  isComposing = false;
  isPopUp = false;
  /* 初始化属性 */
  options: IOptions = null;
  /* 当前内容 */
  queryString = '';
  /* 格式化queryString */
  tokens = [];

  constructor(options: IOptions) {
    this.options = options;
    this.editorEl = this.options.target;
    this.editorEl.setAttribute('spellcheck', 'false');
    this.editorEl.setAttribute('contenteditable', 'true');
    this.editorEl.addEventListener('click', () => this.handleClick());
    this.editorEl.addEventListener('input', e => {
      this.options?.onInput?.(e?.target?.textContent);
      this.handleInput();
    });
    this.editorEl.addEventListener('compositionstart', () => {
      this.isComposing = true;
    });
    this.editorEl.addEventListener('compositionend', () => {
      this.isComposing = false;
    });
    this.editorEl.addEventListener('keydown', e => this.handleKeyDown(e as any));
    this.queryString = this.options.value;
    this.parseQueryString();
    this.setTokensToTarget(true);
  }

  /**
   * @description 输入时
   * @returns
   */
  @Debounce(300)
  handleInput() {
    if (this.isComposing) {
      return;
    }
    this.queryString = this.editorEl.textContent;
    this.parseQueryString();
    this.setTokensToTarget();
    const tokenItem = this.getCursorTokenItem();
    const { targetSpan: targetSpanEl, isLast } = tokenItem;
    const targetSpan = targetSpanEl || this.editorEl.children[this.tokens.length - 1];
    if (targetSpan) {
      const type = targetSpan.getAttribute('token-type') as EQueryStringTokenType;
      const index = Number(targetSpan.getAttribute('token-index'));
      if ([EQueryStringTokenType.value, EQueryStringTokenType.key].includes(type)) {
        this.options?.onSearch?.(targetSpan.textContent.replace(/^\s+|\s+$/g, ''));
      } else {
        this.options?.onSearch?.('');
      }
      // 弹出弹窗
      if (index === this.tokens.length - 1) {
        if (isLast) {
          if (type === EQueryStringTokenType.key) {
            const field = this.getCursorTokenField(index);
            this.popUp(EQueryStringTokenType.method, field);
          } else if (type === EQueryStringTokenType.condition) {
            this.popUp(EQueryStringTokenType.key, '');
          } else if (type === EQueryStringTokenType.value) {
            this.popUp(EQueryStringTokenType.condition, '');
          }
        } else {
          if (type === EQueryStringTokenType.key) {
            this.popUp(EQueryStringTokenType.key, '');
          } else if (type === EQueryStringTokenType.value) {
            const field = this.getCursorTokenField(index);
            this.popUp(EQueryStringTokenType.value, field);
          }
        }
      }
    } else {
      this.options?.onSearch?.('');
      this.popUp(EQueryStringTokenType.key, '');
    }
  }

  /**
   * @description 找到最近位置的key值
   * @param index
   */
  getCursorTokenField(index: number) {
    let field = '';
    for (let i = index; i >= 0; i--) {
      const token = this.tokens[i];
      if (token.type === EQueryStringTokenType.key) {
        field = token.value;
        break;
      }
    }
    return field.replace(/^\s+|\s+$/g, '');
  }

  /**
   * @description 获取当前位置
   * @returns
   */
  getCursorTokenItem() {
    const selection = window.getSelection();
    if (selection.rangeCount === 0) {
      return null;
    }
    const range = selection.getRangeAt(0);
    const startNode = range.startContainer;
    // 获取 Range 的结束位置
    const endContainer = range.endContainer;
    const endOffset = range.endOffset;
    let isLast = false;
    if (endContainer.nodeType === Node.TEXT_NODE) {
      // 如果是文本节点，判断偏移量是否等于文本长度
      isLast = endOffset === endContainer.textContent.length;
    } else {
      isLast = endOffset === endContainer.childNodes.length;
    }
    const targetSpan = startNode.parentElement.closest('span');
    return {
      targetSpan,
      isLast,
    };
  }

  /**
   * @description 点击了容器
   * @param _e
   */
  handleClick() {
    this.options?.onSearch?.('');
    if (this.isPopUp) {
      this.popDown();
    } else {
      this.popUpFn(true);
    }
  }
  handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      event.stopPropagation();
      event.preventDefault();
      if (!this.queryString) {
        // 针对粘贴后300ms内回车的情况
        const str = this.editorEl.textContent.replace(/^\s+|\s+$/g, '');
        this.options?.onChange(str);
      }
      this.options?.onQuery?.();
    }
  }

  /**
   * @description 语法解析
   */
  parseQueryString() {
    const result = [];
    const tokens = parseQueryString(this.queryString);
    const rightBrackets = ['}', ']', ')'];
    let i = 0;
    for (const item of tokens) {
      i += 1;
      const next = tokens?.[i]?.value;
      if (QUERY_STRING_DATA_TYPES.includes(item.type) || rightBrackets.some(v => v === item.value)) {
        const noAddNoSpace = rightBrackets.includes(next) && item.type === EQueryStringTokenType.value;
        result.push({
          ...item,
          value: noAddNoSpace ? item.value : `${item.value} `,
        });
      } else if (item.type !== EQueryStringTokenType.split) {
        result.push(item);
      }
    }
    this.tokens = result;
  }
  popDown() {
    this.options?.popDownFn?.();
    this.isPopUp = false;
  }
  popUp(type: EQueryStringTokenType, field: string) {
    this.options?.popUpFn?.(type, field);
    this.isPopUp = true;
  }

  popUpFn(isLast = false) {
    if (this.queryString && !/^\s*$/.test(this.queryString)) {
      // 最后一个坐标时弹出选项
      const targetSpan = this.getCursorTokenItem().targetSpan;
      if (targetSpan || isLast) {
        const index = isLast ? this.tokens.length - 1 : Number(targetSpan.getAttribute('token-index'));
        if (index >= this.tokens.length - 1) {
          const type = this.tokens[index].type;
          if (type === EQueryStringTokenType.method) {
            const field = this.getCursorTokenField(index);
            this.popUp(EQueryStringTokenType.value, field);
          } else if (type === EQueryStringTokenType.condition) {
            this.popUp(EQueryStringTokenType.key, '');
          } else if (type === EQueryStringTokenType.key) {
            const field = this.getCursorTokenField(index);
            this.popUp(EQueryStringTokenType.method, field);
          } else if (type === EQueryStringTokenType.value) {
            const field = this.getCursorTokenField(index);
            this.popUp(EQueryStringTokenType.condition, field);
          }
        }
      }
    } else {
      this.popUp(EQueryStringTokenType.key, '');
    }
  }

  setIsPopup(is: boolean) {
    this.isPopUp = is;
  }

  setQueryString(str: string) {
    this.queryString = str;
    this.parseQueryString();
    this.setTokensToTarget(true, false);
  }

  /**
   * @description 选择选项时插入到当前查询语句
   * @param str
   */
  setToken(str: string, type: EQueryStringTokenType) {
    const lastToken = this.tokens[this.tokens.length - 1];
    if (lastToken?.type === type) {
      let value = str;
      if (type === EQueryStringTokenType.key && this?.options?.keyFormatter) {
        value = this.options.keyFormatter(value);
      }
      lastToken.value = `${value} `;
    } else {
      let value = str;
      if (type === EQueryStringTokenType.key && this?.options?.keyFormatter) {
        value = this.options.keyFormatter(value);
      }
      if (type === EQueryStringTokenType.value && this?.options?.valueFormatter) {
        const len = this.tokens.length;
        let field = '';
        let method = '';
        for (let i = len - 1; i >= 0; i--) {
          const token = this.tokens[i];
          if (token.type === EQueryStringTokenType.method) {
            method = token.value.replace(/^\s+|\s+$/g, '');
          }
          if (token.type === EQueryStringTokenType.key) {
            field = token.value.replace(/^\s+|\s+$/g, '');
            break;
          }
        }
        value = this.options.valueFormatter(field, method, value);
      }
      this.queryString = `${this.queryString} ${value} `;
      this.parseQueryString();
      // if (this.tokens[this.tokens.length - 1].type === EQueryStringTokenType.value) {
      //   this.options?.onQuery?.();
      // }
    }
    this.setTokensToTarget(true);
    this.popUpFn(true);
  }

  /* 将解析完的数组填入目标元素 */
  setTokensToTarget(isLast = false, needChange = true) {
    const content = this.tokens
      .map(
        (item, index) =>
          `<span token-type="${item.type}" token-index="${index}" style="color: ${
            queryStringColorMap[item.type]?.color || defaultColor
          };" class="str-item">${item.value.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</span>`
      )
      .join('');
    replaceContent(this.editorEl, content, isLast);
    this.queryString = this.editorEl.textContent;
    if (needChange) {
      this.options?.onChange?.(this.queryString.replace(/^\s+|\s+$/g, ''));
    }
  }
}

export function getQueryStringMethods(fieldType: EFieldType) {
  if ([EFieldType.integer, EFieldType.long].includes(fieldType)) {
    return [...QUERY_STRING_METHODS];
  }
  return [
    {
      id: ':',
      name: window.i18n.t('等于'),
    },
    {
      id: ':*',
      name: window.i18n.t('存在'),
    },
  ];
}

export function parseQueryString(query: string): IStrItem[] {
  const tokens: IStrItem[] = [];

  // 增强正则表达式，支持完整括号集和运算符
  // const tokenRegex = /(\s+)|([(){}[\]])|(AND\s+NOT|AND|OR)|(<=|>=|:\*|:|>|<)|(".*?")|(\S+)/gi;
  const tokenRegex = /(\s+)|([(){}[\]])|(AND\s+NOT|AND|OR)|(<=|>=|:|>|<)|(".*?")|(\S+)/gi;

  let match: null | RegExpExecArray;
  while ((match = tokenRegex.exec(query)) !== null) {
    const [_full, space, bracket, condition, method, quoted, word] = match;
    if (space) {
      tokens.push({ value: space, type: EQueryStringTokenType.split });
    } else if (bracket) {
      tokens.push({ value: bracket, type: EQueryStringTokenType.bracket });
    } else if (condition) {
      tokens.push({ value: condition.toUpperCase(), type: EQueryStringTokenType.condition });
    } else if (method) {
      tokens.push({ value: method, type: EQueryStringTokenType.method });
    } else if (quoted) {
      tokens.push({ value: quoted, type: EQueryStringTokenType.value });
    } else if (word) {
      const match = word.match(/[)\]}]/);
      if (match?.input?.endsWith(match?.[0])) {
        tokens.push({ value: word.slice(0, match.index), type: EQueryStringTokenType.value });
        tokens.push({ value: match[0], type: EQueryStringTokenType.bracket });
      } else {
        if (tokens?.[tokens.length - 1]?.type === EQueryStringTokenType.value) {
          tokens[tokens.length - 1].value += word;
        } else {
          tokens.push({ value: word, type: EQueryStringTokenType.value });
        }
      }
    }
  }

  // 增强的括号层级处理
  let hasBracket = false;
  const leftBrackets = new Set(['(', '[', '{']);
  const rightBrackets = new Set([')', ']', '}']);

  if (tokens?.[0]?.type === EQueryStringTokenType.split) {
    tokens.splice(0, 1);
  }
  if (tokens?.[tokens.length - 1]?.type === EQueryStringTokenType.split) {
    tokens[tokens.length - 1].value = ' ';
  }

  let index = -1;
  for (const token of tokens) {
    index += 1;
    // 更新括号层级
    if (token.type === EQueryStringTokenType.bracket) {
      if (hasBracket) {
        const isRight = rightBrackets.has(token.value);
        hasBracket = !isRight;
        continue;
      }
      const isLeft = leftBrackets.has(token.value);
      hasBracket = isLeft;
      continue;
    }

    // 动态条件类型转换
    if (token.type === EQueryStringTokenType.condition) {
      token.type = hasBracket ? EQueryStringTokenType.valueCondition : EQueryStringTokenType.condition;
    }

    // 增强的键值类型推导
    if (token.type === EQueryStringTokenType.value) {
      const nextToken = tokens.slice(index + 1).find(t => t.type !== EQueryStringTokenType.split);
      const preToken = tokens
        .slice(0, index)
        .reverse()
        .find(t => t.type !== EQueryStringTokenType.split);

      // 检查后续是否存在方法运算符
      if (
        nextToken?.type === EQueryStringTokenType.method ||
        (!hasBracket && preToken?.type === EQueryStringTokenType.condition)
      ) {
        token.type = EQueryStringTokenType.key;
      }
    }
    if (index === 0 && token.value) {
      token.type = EQueryStringTokenType.key;
    }
  }
  return tokens;
}

// 获取光标全局字符偏移量
function getGlobalOffset(editor) {
  const ownerDocument = document.activeElement.shadowRoot || document;
  const selection = ownerDocument.getSelection();
  if (!selection.rangeCount) return 0;
  const range = selection.getRangeAt(0);
  let offset = 0;
  const nodeStack = [editor];
  let found = false;
  // 前序遍历所有文本节点
  while (nodeStack.length > 0 && !found) {
    const node = nodeStack.pop();
    if (node.nodeType === Node.TEXT_NODE) {
      if (node === range.startContainer) {
        offset += range.startOffset;
        found = true;
      } else {
        offset += node.textContent.length;
      }
    } else {
      // 逆序压栈保证遍历顺序
      for (let i = node.childNodes.length - 1; i >= 0; i--) {
        nodeStack.push(node.childNodes[i]);
      }
    }
  }
  return offset;
}

/**
 * @description 替换编辑器内容的同时保持聚焦状态
 * @param editor
 * @param content
 * @param isLast
 */
function replaceContent(editor, content: string, isLast = false) {
  // 保存原始偏移量
  const originalOffset = getGlobalOffset(editor);
  // 生成新内容（示例：随机长度的新文本）
  const newText = content;
  editor.innerHTML = newText;
  // 计算新内容总长度
  let newContentLength = 0;
  const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT, null);
  let node: Node;
  while ((node = walker.nextNode())) {
    newContentLength += node.textContent.length;
  }
  let adjustedOffset = Math.min(originalOffset, newContentLength);
  if (isLast) {
    adjustedOffset = newContentLength; // 将光标移动到最后
  }
  // 恢复光标
  setGlobalOffset(editor, adjustedOffset);
  // 保持聚焦
  editor.focus();
}
// 设置光标到指定偏移量
function setGlobalOffset(editor, targetOffset) {
  let currentOffset = 0;
  let targetNode = editor;
  let targetNodeOffset = 0;
  // 遍历所有文本节点
  const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT, null);
  let node: Node;
  while ((node = walker.nextNode())) {
    const nodeLength = node.textContent.length;
    if (currentOffset + nodeLength > targetOffset) {
      targetNode = node;
      targetNodeOffset = targetOffset - currentOffset;
      break;
    }
    currentOffset += nodeLength;
  }
  // 处理越界情况（放置到最后一个位置）
  if (!targetNode || targetNode.nodeType !== Node.TEXT_NODE) {
    const allChildren = editor.childNodes;
    targetNode = editor;
    targetNodeOffset = allChildren.length;
  }
  // 设置光标位置
  const range = document.createRange();
  range.setStart(targetNode, targetNodeOffset);
  range.collapse(true);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
}

export const useQueryStringParseErrorState = createGlobalState(() => {
  const errorData = shallowRef(null);
  const setErrorData = data => {
    errorData.value = data;
  };
  return { errorData, setErrorData };
});
