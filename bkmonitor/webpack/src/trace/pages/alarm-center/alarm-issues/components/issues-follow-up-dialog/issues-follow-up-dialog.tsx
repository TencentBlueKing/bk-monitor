/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { defineComponent, shallowRef, watch } from 'vue';

import { Button, Dialog } from 'bkui-vue';

import MarkdownEditor from '../../../../../components/markdown-editor/editor';

import './issues-follow-up-dialog.scss';

export default defineComponent({
  name: 'IssuesFollowUpDialog',
  props: {
    /** 弹窗是否显示 */
    isShow: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    confirm: (content: string) => typeof content === 'string',
    cancel: () => true,
    'update:isShow': (val: boolean) => typeof val === 'boolean',
  },
  setup(props, { emit }) {
    /** 编辑器内容 */
    const editorValue = shallowRef('');

    // 每次弹窗打开时清空编辑器内容
    watch(
      () => props.isShow,
      val => {
        if (val) {
          editorValue.value = '';
        }
      }
    );

    /**
     * @description 编辑器内容变更
     * @param value - 编辑器 markdown 内容
     */
    const handleEditorInput = (value: string) => {
      editorValue.value = value;
    };

    /**
     * @description 确认提交跟进信息
     */
    const handleConfirm = () => {
      const value = editorValue.value?.trim();
      if (!value) return;
      emit('confirm', value);
    };

    /**
     * @description 取消操作
     */
    const handleCancel = () => {
      emit('cancel');
    };

    return {
      editorValue,
      handleEditorInput,
      handleConfirm,
      handleCancel,
    };
  },
  render() {
    return (
      <Dialog
        width={720}
        class='issues-follow-up-dialog'
        v-slots={{
          default: () => (
            <div class='issues-follow-up-dialog-content'>
              <MarkdownEditor
                height={'300px'}
                previewStyle='tab'
                value={this.editorValue}
                onInput={this.handleEditorInput}
              />
            </div>
          ),
          footer: () => (
            <div class='issues-follow-up-dialog-footer'>
              <Button
                style='margin-right: 8px'
                disabled={!this.editorValue?.trim()}
                theme='primary'
                onClick={this.handleConfirm}
              >
                {window.i18n.t('确定')}
              </Button>
              <Button onClick={this.handleCancel}>{window.i18n.t('取消')}</Button>
            </div>
          ),
        }}
        header-position='left'
        isShow={this.isShow}
        title={window.i18n.t('批量添加跟进信息')}
        onUpdate:isShow={(v: boolean) => {
          this.$emit('update:isShow', v);
        }}
      />
    );
  },
});
