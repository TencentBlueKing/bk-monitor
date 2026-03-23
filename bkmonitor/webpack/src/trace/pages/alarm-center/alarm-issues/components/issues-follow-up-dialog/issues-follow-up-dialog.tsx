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

import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import { Button, Dialog } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import MarkdownEditor from '../../../../../components/markdown-editor/editor';
import { followUpIssues, showOperationResult } from '../../services/issues-operations';

import type { IssuesBatchActionEnum } from '../../constant';
import type { IssueIdentifier, IssuesOperationDialogEvent } from '../../typing';

import './issues-follow-up-dialog.scss';

export default defineComponent({
  name: 'IssuesFollowUpDialog',
  props: {
    /** 弹窗是否显示 */
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 跨业务批量操作 Issue 标识数据 */
    issuesData: {
      type: Array as PropType<IssueIdentifier[]>,
      default: () => [],
    },
    /** 弹窗标题 */
    title: {
      type: String,
    },
  },
  emits: {
    success: (event: IssuesOperationDialogEvent<typeof IssuesBatchActionEnum.FOLLOW_UP>) => event != null,
    cancel: () => true,
    'update:isShow': (val: boolean) => typeof val === 'boolean',
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 编辑器内容 */
    const editorValue = shallowRef('');
    /** 提交中 loading 状态 */
    const loading = shallowRef(false);

    /**
     * @description 获取弹窗标题
     * @returns { string } 弹窗标题
     */
    const getTitle = () => {
      if (props.title) return props.title;
      if (props.issuesData?.length > 1) return window.i18n.t('批量添加跟进信息');
      return window.i18n.t('添加跟进信息');
    };

    /**
     * @description 编辑器内容变更
     * @param {string} value - 编辑器 markdown 内容
     */
    const handleEditorInput = (value: string) => {
      editorValue.value = value;
    };

    /**
     * @description 确认提交跟进信息
     */
    const handleConfirm = async () => {
      const value = editorValue.value?.trim();
      if (!value) return;

      loading.value = true;
      try {
        const res = await followUpIssues({
          issues: props.issuesData,
          content: value,
        });

        showOperationResult(res, t('添加跟进信息成功'));
        emit('success', res);
      } finally {
        loading.value = false;
      }
    };

    /**
     * @description 取消操作
     */
    const handleCancel = () => {
      if (loading.value) return;
      emit('cancel');
    };

    // 每次弹窗打开时清空编辑器内容
    watch(
      () => props.isShow,
      val => {
        if (val) {
          editorValue.value = '';
          loading.value = false;
        }
      }
    );

    return {
      editorValue,
      loading,
      getTitle,
      handleEditorInput,
      handleConfirm,
      handleCancel,
    };
  },
  render() {
    return (
      <Dialog
        width={800}
        class='issues-follow-up-dialog'
        v-slots={{
          default: () => (
            <div class='issues-follow-up-dialog-content'>
              <MarkdownEditor
                height='420px'
                class='issues-follow-up-dialog-editor'
                value={this.editorValue}
                onInput={this.handleEditorInput}
              />
            </div>
          ),
          footer: () => (
            <div class='issues-follow-up-dialog-footer'>
              <Button
                disabled={!this.editorValue?.trim() || this.loading}
                loading={this.loading}
                theme='primary'
                onClick={this.handleConfirm}
              >
                {window.i18n.t('确定')}
              </Button>
              <Button
                disabled={this.loading}
                onClick={this.handleCancel}
              >
                {window.i18n.t('取消')}
              </Button>
            </div>
          ),
        }}
        header-position='left'
        isShow={this.isShow}
        title={this.getTitle()}
        onUpdate:isShow={(v: boolean) => {
          if (this.loading) return;
          this.$emit('update:isShow', v);
        }}
      />
    );
  },
});
