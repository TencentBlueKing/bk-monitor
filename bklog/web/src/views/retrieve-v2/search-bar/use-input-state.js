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
import { ref } from 'vue';

export default function useInputState() {
  // 记录输入状态
  const inputState = ref({
    focusPos: null, // focus时的光标位置
    hasNewInput: false, // 是否有新增输入
    hasSpace: false, // 是否包含空格
    isSelecting: false, // 是否正在选择填充
    lastSpacePos: null, // 最后一个空格的位置
    newContent: '', // focus后新增的内容
  });

  // 重置输入状态
  const resetInputState = () => {
    inputState.value = {
      focusPos: null,
      hasNewInput: false,
      hasSpace: false,
      isSelecting: false,
      lastSpacePos: null,
      newContent: '',
    };
  };

  // 更新输入状态
  const updateInputState = (state) => {
    const currentPos = state.selection.main.to;
    const currentValue = state.doc.toString();

    // 如果是新的focus，记录位置
    if (inputState.value.focusPos === null) {
      inputState.value.focusPos = currentPos;
      inputState.value.hasNewInput = false;
      inputState.value.hasSpace = false;
      inputState.value.lastSpacePos = null;
      inputState.value.isSelecting = false;
      return;
    }

    // 如果正在选择填充，不更新输入状态
    if (inputState.value.isSelecting) {
      return;
    }

    // 如果光标位置在focus位置之后，说明有新增内容
    if (currentPos > inputState.value.focusPos) {
      const newContent = currentValue.slice(
        inputState.value.focusPos,
        currentPos
      );
      // 检查是否包含空格
      const hasSpace = /\s/.test(newContent);

      inputState.value.newContent = newContent;
      inputState.value.hasNewInput = true;
      inputState.value.hasSpace = hasSpace;

      // 如果包含空格，找到最后一个空格的位置
      if (hasSpace) {
        const spaceMatch = newContent.match(/\s+$/);
        if (spaceMatch) {
          // 计算最后一个空格在文档中的位置
          inputState.value.lastSpacePos =
            inputState.value.focusPos + spaceMatch.index;
        }
      }
    } else if (currentPos < inputState.value.focusPos) {
      // 如果光标位置在focus位置之前，说明用户移动了光标，重置状态
      resetInputState();
      inputState.value.focusPos = currentPos;
    }
  };

  // 获取选择范围
  const getSelectionRange = (editorFocusPosition, replace = false) => {
    // 如果是替换模式，替换全部内容
    if (replace) {
      return {
        from: 0,
        to: Infinity,
      };
    }

    // 如果是选择填充，替换当前光标位置的内容
    if (inputState.value.isSelecting) {
      return {
        from: editorFocusPosition,
        to: editorFocusPosition,
      };
    }

    // 如果有focus位置且有新增输入，只替换新增的部分
    if (inputState.value.focusPos !== null && inputState.value.hasNewInput) {
      // 如果有空格，在最后一个空格的位置插入
      if (inputState.value.hasSpace && inputState.value.lastSpacePos !== null) {
        // 在最后一个空格的位置插入，保留空格
        return {
          from: inputState.value.lastSpacePos + 1, // 在空格后插入
          insertSpace: false,
          to: inputState.value.focusPos + inputState.value.newContent.length,
        };
      }

      // 如果没有空格，替换整个新增内容
      return {
        from: inputState.value.focusPos,
        to: inputState.value.focusPos + inputState.value.newContent.length,
      };
    }

    // 如果没有新增输入，在光标位置追加
    return {
      from: editorFocusPosition,
      to: editorFocusPosition,
    };
  };

  // 开始选择填充
  const startSelecting = () => {
    inputState.value.isSelecting = true;
  };

  // 结束选择填充
  const endSelecting = () => {
    inputState.value.isSelecting = false;
  };

  return {
    endSelecting,
    getSelectionRange,
    inputState,
    resetInputState,
    startSelecting,
    updateInputState,
  };
}
