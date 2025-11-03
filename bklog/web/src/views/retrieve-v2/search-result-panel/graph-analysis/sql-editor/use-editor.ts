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

import { computed, onMounted, ref } from 'vue';

import useStore from '@/hooks/use-store';
import { debounce } from 'lodash-es';
import * as monaco from 'monaco-editor';

import useResizeObserve from '../../../../../hooks/use-resize-observe';
import { setDorisFields } from './lang';

export default ({ refRootElement, sqlContent, onValueChange }) => {
  const editorInstance = ref<monaco.editor.IStandaloneCodeEditor>();
  const store = useStore();
  const fieldList = computed(() => store.state.indexFieldInfo.fields);

  const updateEditorHeight = () => {
    editorInstance.value.layout(); // 重新布局编辑器
  };

  const debounceUpdateSqlValue = debounce(() => {
    onValueChange?.(editorInstance.value.getValue());
    updateEditorHeight();
  });

  const initEditorInstance = () => {
    // 初始化编辑器
    editorInstance.value = monaco.editor.create(refRootElement.value, {
      value: sqlContent.value,
      language: 'dorisSQL',
      theme: 'vs-dark',
      padding: { top: 10, bottom: 40 },
      automaticLayout: false,
      minimap: { enabled: false },
      scrollBeyondLastLine: false, // 避免空白行
      contextmenu: false, // 禁用右键菜单
    });

    // 监听编辑器的键盘事件
    editorInstance.value.onKeyDown(e => {
      if (e.keyCode === monaco.KeyCode.Space) {
        // 阻止默认空格行为，使得我们可以手动处理
        e.preventDefault();

        // 获取当前光标位置
        const position = editorInstance.value.getPosition();

        // 手动插入空格
        editorInstance.value.executeEdits(null, [
          {
            range: new monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column),
            text: ' ',
            forceMoveMarkers: true,
          },
        ]);

        // 触发自动补全
        editorInstance.value.trigger('keyboard', 'editor.action.triggerSuggest', {});
      }
      if (e.keyCode === monaco.KeyCode.Enter) {
        // 阻止默认回车行为
        e.preventDefault();
        interface SuggestController extends monaco.editor.IEditorContribution {
          model?: { state: number };
        }
        const suggestWidget = editorInstance.value.getContribution(
          'editor.contrib.suggestController',
        ) as SuggestController;
        const isSuggestVisible = suggestWidget?.model?.state === 2 || suggestWidget?.model?.state === 1;

        if (isSuggestVisible) {
          // 如果建议列表可见，则接受当前的建议
          editorInstance.value.trigger('keyboard', 'acceptSelectedSuggestion', {});
          return;
        }
        const position = editorInstance.value.getPosition();
        const model = editorInstance.value.getModel();
        const lineContent = model.getLineContent(position.lineNumber);

        // 插入新行并保持缩进
        const indentLevel = lineContent.match(/^\s*/)[0]; // 获取当前行的缩进
        const newText = `\n${indentLevel}`; // 新行内容

        // 执行插入操作
        editorInstance.value.executeEdits(null, [
          {
            range: new monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column),
            text: newText,
            forceMoveMarkers: true,
          },
        ]);

        // 移动光标到新行
        const newPosition = {
          lineNumber: position.lineNumber + 1,
          column: indentLevel.length + 1,
        };
        editorInstance.value.setPosition(newPosition);
      }
    });

    editorInstance.value.onDidChangeModelContent(() => debounceUpdateSqlValue());
  };

  const setSuggestFields = () => {
    setDorisFields(() =>
      fieldList.value.map(field => {
        return { name: field.field_name, type: field.field_type, description: field.description };
      }),
    );
  };

  let isResizeLayout = false;
  const debounceLayout = debounce(() => {
    if (refRootElement.value && !isResizeLayout) {
      isResizeLayout = true;
      const rect = refRootElement.value?.getBoundingClientRect();
      editorInstance.value?.layout({
        width: rect.width,
        height: rect.height,
      });

      setTimeout(() => {
        isResizeLayout = false;
      }, 300);
    }
  }, 120);

  useResizeObserve(refRootElement, debounceLayout);

  onMounted(() => {
    initEditorInstance();
    setSuggestFields();
  });

  return {
    editorInstance,
  };
};
