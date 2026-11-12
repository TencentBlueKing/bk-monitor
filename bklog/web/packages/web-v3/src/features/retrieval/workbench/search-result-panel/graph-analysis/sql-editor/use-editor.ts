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

import { useApplicationStore } from '@/app/state/domains/application-store';
import { computed, onBeforeUnmount, onMounted, shallowRef, type Ref } from 'vue';

import { debounce } from 'lodash-es';
import type * as Monaco from 'monaco-editor';

import useResizeObserve from '../../../../../../shared/composables/use-resize-observe';

export default ({
  refRootElement,
  sqlContent,
  onValueChange,
}: {
  refRootElement: Ref<HTMLElement | undefined>;
  sqlContent: Ref<string>;
  onValueChange?: (value: string) => void;
}) => {
  // Monaco owns a cyclic imperative object graph. Vue2 left class instances
  // untouched; retain that identity when upgrading to Vue3 reactivity.
  const editorInstance = shallowRef<Monaco.editor.IStandaloneCodeEditor>();
  const listeners: Monaco.IDisposable[] = [];
  let unmounted = false;
  let resetLayoutTimer: ReturnType<typeof setTimeout> | undefined;
  let clearSuggestFields: (() => void) | undefined;
  let monacoApi: typeof import('monaco-editor') | undefined;
  let setDorisFields: typeof import('./lang').setDorisFields | undefined;
  const store = useApplicationStore();
  const fieldList = computed(() => store.filteredFieldList);

  const updateEditorHeight = () => {
    editorInstance.value?.layout(); // 重新布局编辑器
  };

  const debounceUpdateSqlValue = debounce(() => {
    if (!editorInstance.value) return;
    onValueChange?.(editorInstance.value.getValue());
    updateEditorHeight();
  });

  const initEditorInstance = () => {
    const monaco = monacoApi;
    // 初始化编辑器
    if (!refRootElement.value || !monaco) return;
    const editor = monaco.editor.create(refRootElement.value, {
      value: sqlContent.value,
      language: 'dorisSQL',
      theme: 'vs-dark',
      padding: { top: 10, bottom: 40 },
      automaticLayout: false,
      minimap: { enabled: false },
      scrollBeyondLastLine: false, // 避免空白行
      contextmenu: false, // 禁用右键菜单
    });

    editorInstance.value = editor;
    // 监听编辑器的键盘事件
    listeners.push(
      editor.onKeyDown((e) => {
        if (e.keyCode === monaco.KeyCode.Space) {
          // 阻止默认空格行为，使得我们可以手动处理
          e.preventDefault();

          // 获取当前光标位置
          const position = editor.getPosition();
          if (!position) return;

          // 手动插入空格
          editor.executeEdits(null, [
            {
              range: new monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column),
              text: ' ',
              forceMoveMarkers: true,
            },
          ]);

          // 触发自动补全
          editor.trigger('keyboard', 'editor.action.triggerSuggest', {});
        }
        if (e.keyCode === monaco.KeyCode.Enter) {
          // 阻止默认回车行为
          e.preventDefault();
          interface SuggestController extends Monaco.editor.IEditorContribution {
            model?: { state: number };
          }
          const suggestWidget = editor.getContribution('editor.contrib.suggestController') as SuggestController;
          const isSuggestVisible = suggestWidget?.model?.state === 2 || suggestWidget?.model?.state === 1;

          if (isSuggestVisible) {
            // 如果建议列表可见，则接受当前的建议
            editor.trigger('keyboard', 'acceptSelectedSuggestion', {});
            return;
          }
          const position = editor.getPosition();
          if (!position) return;
          const model = editor.getModel();
          if (!model) return;
          const lineContent = model.getLineContent(position.lineNumber);

          // 插入新行并保持缩进
          const indentLevel = lineContent.match(/^\s*/)![0]; // 获取当前行的缩进
          const newText = `\n${indentLevel}`; // 新行内容

          // 执行插入操作
          editor.executeEdits(null, [
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
          editor.setPosition(newPosition);
        }
      }),
    );

    listeners.push(editor.onDidChangeModelContent(() => debounceUpdateSqlValue()));
  };

  const setSuggestFields = () => {
    clearSuggestFields = setDorisFields?.(() =>
      fieldList.value.map((field: { field_name: any; field_type: any; description: any }) => {
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

      resetLayoutTimer = setTimeout(() => {
        isResizeLayout = false;
        resetLayoutTimer = undefined;
      }, 300);
    }
  }, 120);

  useResizeObserve(refRootElement, debounceLayout);

  onMounted(async () => {
    const [monaco, lang] = await Promise.all([import('monaco-editor'), import('./lang')]);
    if (unmounted) return;
    monacoApi = monaco;
    setDorisFields = lang.setDorisFields;
    initEditorInstance();
    setSuggestFields();
  });

  onBeforeUnmount(() => {
    unmounted = true;
    debounceUpdateSqlValue.cancel();
    debounceLayout.cancel();
    if (resetLayoutTimer !== undefined) clearTimeout(resetLayoutTimer);
    for (const listener of listeners.splice(0)) listener.dispose();
    clearSuggestFields?.();
    editorInstance.value?.dispose();
    editorInstance.value = undefined;
  });

  return {
    editorInstance,
  };
};
