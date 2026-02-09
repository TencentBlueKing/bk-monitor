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

import {
  type PropType,
  defineComponent,
  getCurrentInstance,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  shallowRef,
  useTemplateRef,
  watch,
} from 'vue';

import { parser } from '@prometheus-io/lezer-promql';
import { useThrottleFn } from '@vueuse/core';
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api';
import { validateQuery } from 'monitor-pc/components/promql-editor/validation';

import { defaultOptions, PlaceholderWidget } from './constants';
import { editorWillMount } from './utils';

import './promql-editor.scss';

export default defineComponent({
  name: 'PromqlEditor',
  props: {
    minHeight: {
      type: Number,
      default: 68,
    },
    isError: {
      type: Boolean,
      default: false,
    },
    value: {
      type: String,
      default: null,
    },
    defaultValue: {
      type: String,
      default: '',
    },
    language: {
      type: String,
      default: 'promql',
    },
    theme: {
      type: String,
      default: 'vs',
    },
    options: {
      type: Object,
      default: () => defaultOptions,
    },
    overrideServices: {
      type: Object,
      default: () => ({}),
    },
    className: {
      type: String,
      default: null,
    },
    executeQuery: {
      type: Function as PropType<(v: boolean) => void>,
      default: () => null,
    },
    uri: {
      type: Function as PropType<(v: any) => monaco.Uri>,
    },
    readonly: {
      type: Boolean,
      default: false,
    },
    /** 是否可拉伸调整高度 */
    resizable: {
      type: Boolean,
      default: true,
    },
  },
  setup(props, { emit }) {
    const currentInstance = getCurrentInstance();
    let editorInstance: monaco.editor.IStandaloneCodeEditor | null = null;
    let preventTriggerChangeEvent = false;
    let wrapWidth = 0;
    let roInstance: null | ResizeObserver = null;
    /** 是否处于 resize 拉伸状态中 */
    let isResizing = false;

    const containerElement = useTemplateRef<HTMLDivElement>('containerElement');
    const wrapHeight = shallowRef(0);
    watch(
      () => props.value,
      () => {
        if (!editorInstance || props.value === editorInstance?.getValue?.()) return;
        const model = editorInstance.getModel();
        preventTriggerChangeEvent = true;
        editorInstance.pushUndoStop();
        model.pushEditOperations(
          [],
          [
            {
              range: model.getFullModelRange(),
              text: props.value,
            },
          ],
          undefined
        );
        editorInstance.pushUndoStop();
        preventTriggerChangeEvent = false;
      }
    );
    watch(
      () => props.language,
      () => {
        if (!editorInstance) return;
        const model = editorInstance.getModel();
        monaco.editor.setModelLanguage(model, props.language);
      }
    );
    watch(
      () => [props.options, props.className],
      () => {
        if (!editorInstance) return;
        const { model: _, ...optionsWithoutModel } = props.options;
        editorInstance.updateOptions({
          ...(props.className ? { extraEditorClassName: props.className } : {}),
          ...optionsWithoutModel,
        });
      }
    );
    watch(
      () => props.theme,
      () => {
        if (!editorInstance) return;
        monaco.editor.setTheme(props.theme);
      }
    );
    onMounted(() => {
      initMonaco();
    });
    onBeforeUnmount(() => {
      destroyMonaco();
    });
    onDeactivated(() => {
      destroyMonaco();
    });

    const updateLayout = () => {
      const pixelHeight = editorInstance.getContentHeight();
      const height = Math.max(pixelHeight, props.minHeight);
      editorInstance.layout({ width: currentInstance.vnode.el.clientWidth, height });
      wrapHeight.value = height;
    };
    const throttleUpdateLayout = useThrottleFn(updateLayout, 300);
    /**
     * @description 初始化
     */
    const initMonaco = () => {
      const finalValue = props.value !== null ? props.value : props.defaultValue;
      if (containerElement.value) {
        const { suggest, ...restDefaultOptions } = defaultOptions;
        const finalOptions: monaco.editor.IStandaloneEditorConstructionOptions = {
          ...restDefaultOptions,
          suggest: suggest(),
          ...props.options,
          ...editorWillMount(monaco),
        };

        const modelUri = props.uri?.(monaco);
        let model = null;
        if (modelUri) {
          model = monaco.editor.getModel(modelUri);
        }
        if (model) {
          model.setValue(finalValue);
          monaco.editor.setModelLanguage(model, props.language);
        } else {
          model = monaco.editor.createModel(finalValue, props.language, modelUri);
        }
        editorInstance = monaco.editor.create(
          containerElement.value,
          {
            model,
            ...(props.className ? { extraEditorClassName: props.className } : {}),
            ...finalOptions,
            ...(props.theme ? { theme: props.theme } : {}),
            readOnly: props.readonly,
          },
          props.overrideServices
        );
        handleEditorDidMount();
      }
    };
    /**
     * @description 编辑器事件
     */
    const handleEditorDidMount = () => {
      roInstance = new ResizeObserver(entries => {
        for (const entry of entries) {
          const newW = entry.contentRect.width;
          if (wrapWidth !== newW) {
            throttleUpdateLayout();
            wrapWidth = newW;
          }
        }
      });

      roInstance.observe(currentInstance.vnode.el as Element);
      editorInstance.onDidContentSizeChange(_event => {
        if (isResizing) return;
        // 等到 DOM 渲染完成后再继续
        setTimeout(() => {
          updateLayout();
        }, 0);
      });
      const placeholderWidget = new PlaceholderWidget(editorInstance);
      editorInstance.onDidChangeModelContent(_event => {
        if (!preventTriggerChangeEvent) {
          emit('change', editorInstance?.getValue?.());
        }
        placeholderWidget.update();
        const model = editorInstance.getModel();
        if (!model) {
          return;
        }
        const query = model.getValue();
        const errors = validateQuery(query, query, model.getLinesContent(), parser) || [];
        const markers = errors.map(({ error, ...boundary }) => ({
          message: `${
            error ? `Error parsing "${error}"` : 'Parse error'
          }. The query appears to be incorrect and could fail to be executed.`,
          severity: monaco.MarkerSeverity.Error,
          ...boundary,
        }));
        monaco.editor.setModelMarkers(model, props.language, markers);
      });
      editorInstance.onDidBlurEditorText(() => {
        emit('blur', editorInstance.getValue(), getLinterStatus());
      });
      editorInstance.onDidFocusEditorText(() => {
        emit('focus');
      });
      editorInstance.addAction({
        keybindings: [monaco.KeyCode.Enter],
        id: 'enter',
        label: 'enter',
        run: (editor: monaco.editor.ICodeEditor): Promise<void> | void => {
          const suggestController = editor.getContribution('editor.contrib.suggestController') as any;
          const suggestCount = suggestController.widget.value._state || 0;
          if (suggestCount <= 0) {
            props.executeQuery(getLinterStatus());
          } else {
            editor.trigger('keyboard', 'acceptSelectedSuggestion', {});
          }
        },
      });
    };
    /**
     * @description 判断是否语法错误
     */
    const getLinterStatus = () => {
      let hasError = false;
      if (editorInstance) {
        const model = editorInstance.getModel();
        const markers = monaco.editor.getModelMarkers({ resource: model.uri });
        hasError = !!markers.length;
      }
      return hasError;
    };

    const destroyMonaco = () => {
      editorInstance?.dispose?.();
      for (const model of monaco.editor.getModels()) {
        model.dispose();
      }
      roInstance?.disconnect?.();
      editorInstance = null;
      roInstance = null;
    };
    const initResize = (e: Event) => {
      e.preventDefault();
      window.addEventListener('mousemove', resizeElement);
      window.addEventListener('mouseup', stopResize);
    };

    const resizeElement = (e: MouseEvent) => {
      isResizing = true;
      const start = currentInstance.vnode.el.getBoundingClientRect().top;
      const mouseY = e.clientY;
      const newHeight = mouseY - start + 5;
      if (newHeight < props.minHeight) {
        wrapHeight.value = props.minHeight;
      } else {
        wrapHeight.value = newHeight;
      }
      editorInstance.layout({ width: currentInstance.vnode.el.clientWidth, height: wrapHeight.value });
    };
    const stopResize = () => {
      isResizing = false;
      window.removeEventListener('mousemove', resizeElement);
    };

    return { wrapHeight, initResize };
  },
  render() {
    return (
      <div
        style={{
          minHeight: `${this.minHeight}px`,
          height: `${this.wrapHeight <= this.minHeight ? this.minHeight : this.wrapHeight}px`,
        }}
        class={['promql-editor', { 'is-error': this.isError }]}
      >
        <div
          ref='containerElement'
          class='promql-editor'
        />
        {this.resizable && (
          <div
            class='resize-vertical-drop'
            onMousedown={this.initResize}
          >
            <div class='lines'>
              <div class='line-1' />
              <div class='line-2' />
            </div>
          </div>
        )}
      </div>
    );
  },
});
